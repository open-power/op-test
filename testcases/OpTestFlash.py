#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestFlash.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
# [+] International Business Machines Corp.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG
'''
OpTestFlash
-----------
Firmware flash tests for OpenPower testing.

This class contains the OpenPower Firmware flashing scripts for
all the OPAL PowerNV platforms(AMI, FSP, SMC and OpenBMC).

- Host PNOR Firmware Updates
- OPAL Lid Updates(Both Skiboot and Skiroot lids flashing)
- Out-of-band HPM Update
- In-band HPM Update

Tools needed (can vary per platform):

- ipmitool
- pflash
- pUpdate
'''

import os
import re
import time
import unittest
import tarfile

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed
from common import OpTestInstallUtil

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestFlashBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.util = conf.util
        self.OpIU = OpTestInstallUtil.InstallUtil()
        self.bmc_type = conf.args.bmc_type
        self.bmc_ip = conf.args.bmc_ip
        self.bmc_username = conf.args.bmc_username
        self.bmc_password = conf.args.bmc_password
        self.pupdate_binary = conf.args.pupdate
        self.pflash = conf.args.pflash

    def validate_side_activated(self):
        l_bmc_side, l_pnor_side = self.cv_IPMI.ipmi_get_side_activated()
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_bmc_side,
                      "BMC: Primary side is not active")
        if (l_pnor_side == BMC_CONST.GOLDEN_SIDE):
            log.info("PNOR: Primary side is not active")
            bios_sensor = self.cv_IPMI.ipmi_get_golden_side_sensor_id()
            self.assertNotEqual(bios_sensor, None,
                                "Failed to get the BIOS Golden side sensor id")
            boot_count_sensor = self.cv_IPMI.ipmi_get_boot_count_sensor_id()
            self.assertNotEqual(boot_count_sensor, None,
                                "Failed to get the Boot Count sensor id")
            self.cv_IPMI.ipmi_set_pnor_primary_side(
                bios_sensor, boot_count_sensor)
            l_bmc_side, l_pnor_side = self.cv_IPMI.ipmi_get_side_activated()
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_pnor_side,
                      "PNOR: Primary side is not active")

    def get_pnor_level(self):
        rc = self.cv_IPMI.ipmi_get_PNOR_level()
        log.info(rc)

    def bmc_down_check(self):
        self.assertTrue(self.util.ping_fail_check(
            self.cv_BMC.host_name), "FSP/BMC keeps on pinging up")

    def scp_file(self, src_file_path, dst_file_path):
        self.util.copyFilesToDest(src_file_path, self.bmc_username, self.bmc_ip,
                                  dst_file_path, self.bmc_password)

    def get_version_tar(self, file_path):
        version = None
        try:
            tar = tarfile.open(file_path)
            manifest = tar.getmember("MANIFEST")
            fd = tar.extractfile(manifest)
            # you probably shouldn't have bad characters in your PNOR version,
            # but if you do, it shouldn't stop op-test from running
            content = fd.read().decode("utf-8", errors="ignore")
            for line in content.split("\n"):
                if line.startswith("version="):
                    version = line.split("=")[-1]
                    break
            tar.close()
            log.info(version)

            if version is None:
                raise OpTestError("Couldn't find version in tar manifest")
        except Exception as e:
            log.debug("Unexpected failure Exception={}".format(e))
            self.assertTrue(False,
                            "Unexpected failure in get_version_tar, "
                            "check if you have the proper file, Exception={}".format(e))
        return version

    def get_image_version(self, path):
        output = self.cv_BMC.run_command("cat %s | grep \"version=\"" % path)
        return output[0].split("=")[-1]

    def delete_images_dir(self):
        try:
            self.cv_BMC.run_command("rm -rf /tmp/images/*")
        except CommandFailed:
            pass

    def get_image_path(self, image_version):
        retry = 0
        while (retry < 20):
            image_list = []
            try:
                image_list = self.cv_BMC.run_command(
                    "ls -1 -d /tmp/images/*/ --color=never")
            except CommandFailed as cf:
                pass
            for i in range(0, len(image_list)):
                version = self.get_image_version(image_list[i] + "MANIFEST")
                if (version == image_version):
                    return image_list[i]
            time.sleep(5)
            retry += 1

    def get_image_id(self, version):
        img_path = self.get_image_path(version)
        img_id = img_path.split("/")[-2]
        log.info("Image Data Info : {}".format(img_id))
        return img_id

    def wait_for_bmc_runtime(self):
        self.util.PingFunc(self.bmc_ip, BMC_CONST.PING_RETRY_FOR_STABILITY)
        if "SMC" in self.bmc_type:
            self.cv_IPMI.ipmi_wait_for_bmc_runtime()
        elif "OpenBMC" in self.bmc_type:
            self.cv_REST.wait_for_bmc_runtime()
        return


class BmcImageFlash(OpTestFlashBase):
    '''
    Flashes the BMC with BMC firmware.
    This enables a single op-test incantation to test with a specific
    BMC firmware build.

    Currently supports SuperMicro (SMC) BMCs and OpenBMC.
    FSP systems need to use a separate mechanism.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.bmc_image = conf.args.bmc_image
        self.pupdate = conf.args.pupdate
        super(BmcImageFlash, self).setUp()

    def runTest(self):
        if not self.bmc_image:
            self.skipTest("BMC image not provided, so skipping test")
        else:
            if not os.path.exists(self.bmc_image):
                log.error("BMC image {} does not exist".format(self.bmc_image))
                self.fail("BMC image {} does not exist".format(self.bmc_image))

        if "SMC" in self.bmc_type and not self.pupdate:
            self.fail("pupdate tool is needed for flashing BMC on SMC platforms")

        # FORCE us to not detect system state.
        # Since we're flashing, we need to ignore what's currently on the
        # machine as it may be pretty garbage firmware left over from previous
        # test runs.
        self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()

        if "SMC" in self.bmc_type:
            self.cv_IPMI.pUpdate.set_binary(self.pupdate_binary)
            self.cv_IPMI.pUpdate.run(" -f  %s" % self.bmc_image)
            self.wait_for_bmc_runtime()
        elif "OpenBMC" in self.bmc_type:
            # Assume all new systems has new BMC code update via REST
            log.debug("Assume BMC has code for the new PNOR Code update via REST")
            if self.cv_REST.has_field_mode_set():
                log.debug("has_field_mode_set so calling clear_field_mode")
                self.cv_BMC.clear_field_mode()
                self.assertFalse(self.cv_REST.has_field_mode_set(), "Field mode disable failed")
            else:
                log.debug("has_field_mode_set NOT true, so did not clear")
            try:
                # because openbmc
                l_res = self.cv_BMC.run_command(
                    "rm -f /usr/local/share/pnor/* /media/pnor-prsv/GUARD")
            except CommandFailed as cf:
                # Ok to just keep giong, may not have patched firmware
                pass
            # OpenBMC implementation for updating code level 'X' to 'X' is really a no-operation
            # it only updates the code from 'X' to 'Y' or 'Y' to 'X'  to avoid duplicates
            self.delete_images_dir()
            self.cv_REST.upload_image(self.bmc_image)
            version = self.get_version_tar(self.bmc_image)
            id = self.get_image_id(version)
            img_ids = self.cv_REST.bmc_image_ids()

            if self.cv_REST.is_image_already_active(id):
                log.info("BMC image {} is active on the system".format(id))
                if self.cv_REST.validate_functional_bootside(id):
                    log.info("BMC image {} is also set as the functional image, so all is good".format(id))
                    return True
                # If non functional set the priority and reboot the BMC
                log.info("Now setting BMC image {} as the functional image on the system".format(id))
                self.cv_REST.set_image_priority(id, "0")
                log.info("Now rebooting the BMC to refresh")
                self.cv_BMC.reboot()
                self.wait_for_bmc_runtime()
                return True

            retries = 60
            while retries > 0:
                time.sleep(1)
                img_ids = self.cv_REST.bmc_image_ids()
                retries = retries - 1
                for img_id in img_ids:
                    d = self.cv_REST.image_data(img_id)
                    log.debug("img_id={} d={}".format(img_id, d))
                    if d['data']['Activation'] == "xyz.openbmc_project.Software.Activation.Activations.Ready":
                        log.debug(
                            "BMC image %s is ready to activate" % img_id)
                        break
                else:
                    log.debug("img_id={} continue".format(img_id))
                    continue
                break
            self.assertTrue(
                retries > 0, "Uploaded image but it never is ready to activate it")
            log.debug("Going to activate image id: %s" % img_id)
            self.assertIsNotNone(img_id, "Could not find Image ID")
            self.cv_REST.activate_image(img_id)
            self.assertTrue(self.cv_REST.wait_for_image_active_complete(
                img_id), "Failed to activate image")
            # On SMC reboot will happen automatically, but on OpenBMC needs manual reboot to upgrade the BMC FW.
            self.cv_BMC.reboot()
            self.wait_for_bmc_runtime()
            # Once BMC comes up, verify whether BMC really booted from the code which we flashed.
            # As BMC maintains two levels of code, so there may be possibilities/bugs which causes
            # the boot from alternate side or other code.
            self.assertTrue(self.cv_REST.validate_functional_bootside(
                img_id), "BMC failed to boot from the right code")
            log.info(
                "# BMC booting from the right code with image ID: %s" % img_id)
        c = 0
        while True:
            time.sleep(5)
            try:
                self.cv_SYSTEM.sys_wait_for_standby_state()
            except OpTestError as e:
                c += 1
                if c == 10:
                    raise e
            else:
                break

        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        raw_pty = self.cv_SYSTEM.console.get_console()
        self.cv_SYSTEM.sys_sel_check()


class PNORFLASH(OpTestFlashBase):
    '''
    Flash full PNOR image

    For OpenBMC, uses REST image upload
    For SMC, uses pUpdate for regular images or pflash for upstream images
    For AMI, relies on pflash

    op-test needs to be provided locations of pUpdate and pflash
    binaries to successfully flash machines that need them.

    Supports SMC, AMI and OpenBMC based BMCs.

    FSP systems use a different mechanism.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.host_pnor
        self.pupdate = conf.args.pupdate
        super(PNORFLASH, self).setUp()

    def runTest(self):
        if not self.pnor:
            self.skipTest("PNOR image not provided, so skipping test")
        else:
            if not os.path.exists(self.pnor):
                log.error("PNOR image {} does not exist".format(self.pnor))
                self.fail("PNOR image {} does not exist".format(self.pnor))

        if any(s in self.bmc_type for s in ("FSP", "QEMU", "qemu")):
            self.skipTest("OP AMI/OpenBMC PNOR Flash test")

        if "AMI" in self.bmc_type and not self.pflash:
            self.fail("pflash tool is needed for flashing PNOR on AMI platforms")
        elif "SMC" in self.bmc_type:
            self.cv_BMC.ssh.run_command("rm -rf /tmp/rsync_file/*")
            if self.pupdate:
                pass
            elif not self.pflash:
                self.fail(
                    "pupdate or pflash tool is needed for flashing PNOR on SMC platforms")
        else:
            pass

        if self.pflash:
            self.cv_BMC.image_transfer(self.pflash, "pflash")

        if "AMI" in self.bmc_type:
            if not self.cv_BMC.validate_pflash_tool("/tmp"):
                raise OpTestError("No pflash on BMC")
            self.validate_side_activated()
        elif "SMC" in self.bmc_type:
            if self.pupdate:
                self.cv_IPMI.pUpdate.set_binary(self.pupdate_binary)
            elif self.pflash:
                self.assertTrue(self.cv_BMC.validate_pflash_tool(
                    "/tmp/rsync_file"), "No pflash on BMC")
        # FORCE us to not detect system state.
        # Since we're flashing, we need to ignore what's currently on the
        # machine as it may be pretty garbage firmware left over from previous
        # test runs.
        self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        if "AMI" in self.bmc_type:
            self.cv_BMC.image_transfer(self.pnor)
            self.cv_BMC.pnor_img_flash_ami("/tmp", os.path.basename(self.pnor))
        elif "SMC" in self.bmc_type:
            if self.pupdate:
                output = self.cv_IPMI.pUpdate.run(" -pnor {}".format(self.pnor))
                if "failed to update PNOR" in output:
                    self.assertTrue(False, "We failed to update the SMC PNOR, please retry")
            elif self.pflash:
                self.cv_BMC.image_transfer(self.pnor)
                self.cv_BMC.pnor_img_flash_smc(
                    "/tmp/rsync_file", os.path.basename(self.pnor))
        elif "OpenBMC" in self.bmc_type:
            if self.cv_BMC.query_vpnor():
                log.info("BMC has VPNOR")
                try:
                    # because openbmc
                    l_res = self.cv_BMC.run_command(
                        "rm -f /usr/local/share/pnor/* /media/pnor-prsv/GUARD")
                except CommandFailed as cf:
                    # Ok to just keep giong, may not have patched firmware
                    pass
                version = self.get_version_tar(self.pnor)

                # Because OpenBMC does not have a way to determine what the image ID
                # is in advance, and can fill up the filesystem and fail weirdly,
                # along with the fun of setting priorities...
                img_ids = self.cv_REST.host_image_ids()
                for img_id in img_ids:
                    d = self.cv_REST.delete_image(img_id)

                self.cv_REST.upload_image(self.pnor)
                img_ids = self.cv_REST.host_image_ids()
                retries = 60
                while len(img_ids) == 0 and retries > 0:
                    time.sleep(1)
                    img_ids = self.cv_REST.host_image_ids()
                    retries = retries - 1
                self.assertTrue(
                    retries > 0, "Uploaded image but it never showed up")
                for img_id in img_ids:
                    d = self.cv_REST.image_data(img_id)
                    if d['data']['Activation'] == "xyz.openbmc_project.Software.Activation.Activations.Ready":
                        break
                log.info("Going to activate image id: %s" % img_id)
                self.assertIsNotNone(img_id, "Could not find Image ID")
                self.cv_REST.activate_image(img_id)
                self.assertTrue(self.cv_REST.wait_for_image_active_complete(
                    img_id), "Failed to activate image")
                # We need to have below check after power on of the host.
                #self.assertTrue(self.cv_REST.validate_functional_bootside(img_id), "PNOR failed to boot from the right code")
                log.debug(
                    "# PNOR boots from the right code with image ID: %s" % img_id)
            else:
                log.debug("Fallback to old code update method using pflash tool")
                self.cv_BMC.image_transfer(self.pnor)
                self.cv_BMC.pnor_img_flash_openbmc(os.path.basename(self.pnor))

        raw_pty = self.cv_SYSTEM.console.get_console()
        if "AMI" in self.bmc_type:
            self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class OpalLidsFLASH(OpTestFlashBase):
    '''
    Flash specific LIDs (partitions).
    Can be combined with a full PNOR flash to test a base firmware image
    plus new code. For example, if testing a new skiboot (before incorporating
    it into upstream) you can test a base image plus new skiboot.

    Compatible with AMI, SMC, OpenBMC and FSP.

    This just flashes the raw file you provide, so you need to provide it
    with the correct format for the system.

    e.g. for skiboot:
    FSP systems needs raw skiboot.lid
    AMI,SMC,OpenBMC systems need skiboot.lid.xz
    unless secure boot is enabled, and then they need skiboot.lid.xz.stb
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pflash = conf.args.pflash
        self.skiboot = conf.args.flash_skiboot
        self.skiroot_kernel = conf.args.flash_kernel
        self.skiroot_initramfs = conf.args.flash_initramfs
        self.flash_part_list = conf.args.flash_part
        self.smc_presshipmicmd = conf.args.smc_presshipmicmd
        self.ext_lid_test_path = "/opt/extucode/lid_test"

        for lid in [self.skiboot, self.skiroot_kernel, self.skiroot_initramfs]:
            if lid:
                self.assertNotEqual(os.path.exists(lid), 0,
                                    "OPAL lid %s not doesn't exist" % lid)
        super(OpalLidsFLASH, self).setUp()

    def runTest(self):
        if not self.skiboot and not self.skiroot_kernel and not self.skiroot_initramfs \
                and not self.flash_part_list:
            self.skipTest("No custom skiboot/kernel to flash")
        if any(s in self.bmc_type for s in ("QEMU", "qemu")):
            self.skipTest("Skipping OpalLidsFLASH on QEMU machine")

        if self.bmc_type in ["AMI", "SMC"] and not self.pflash:
            self.fail("pflash tool is needed for flashing OPAL lids")

        if "SMC" in self.bmc_type and self.smc_presshipmicmd:
            self.cv_IPMI.ipmitool.run(self.smc_presshipmicmd)

        if self.pflash and "FSP" not in self.bmc_type:
            self.cv_BMC.image_transfer(self.pflash, "pflash")

        if "AMI" in self.bmc_type:
            if not self.cv_BMC.validate_pflash_tool("/tmp"):
                raise OpTestError("No pflash on BMC")
            self.validate_side_activated()
        elif "SMC" in self.bmc_type:
            if not self.cv_BMC.validate_pflash_tool("/tmp/rsync_file"):
                raise OpTestError("No pflash on BMC")

        # FORCE us to not detect system state.
        # Since we're flashing, we need to ignore what's currently on the
        # machine as it may be pretty garbage firmware left over from previous
        # test runs.
        self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        if "FSP" in self.bmc_type:
            self.cv_BMC.fsp_get_console()
            if not self.cv_BMC.mount_exists():
                raise OpTestError("Please mount NFS and retry the test")
            self.cv_BMC.fsp_run_command("/usr/sbin/sshd")
            cmd = "rm -fr {0} 2> /dev/null; mkdir -p {0}".format(
                self.ext_lid_test_path)
            self.cv_BMC.fsp_run_command(cmd)
            if self.skiboot:
                self.cv_BMC.fsp_run_command(
                    "cp -f /opt/extucode/80f00100.lid %s/80f00100_bkp.lid" % self.ext_lid_test_path)
                log.debug("Backup of skiboot lid is in %s/80f00100_bkp.lid" %
                          self.ext_lid_test_path)
                self.cv_BMC.fsp_run_command("rm -f /opt/extucode/80f00100.lid")
                self.scp_file(self.skiboot, "/opt/extucode/80f00100.lid")

            if not self.skiroot_kernel and not self.skiroot_initramfs:
                log.debug("No skiroot lids provided, Flashing only skiboot")
            else:
                self.cv_BMC.fsp_run_command(
                    "cp -f /opt/extucode/80f00101.lid %s/80f00101_bkp.lid" % self.ext_lid_test_path)
                log.debug(
                    "Backup of skiroot kernel lid is in %s/80f00101_bkp.lid" % self.ext_lid_test_path)
                self.cv_BMC.fsp_run_command(
                    "cp -f /opt/extucode/80f00102.lid %s/80f00102_bkp.lid" % self.ext_lid_test_path)
                log.debug(
                    "Backup of skiroot initrd lid is in %s/80f00102_bkp.lid" % self.ext_lid_test_path)
                self.cv_BMC.fsp_run_command("rm -f /opt/extucode/80f00101.lid")
                self.cv_BMC.fsp_run_command("rm -f /opt/extucode/80f00102.lid")
                self.scp_file(self.skiroot_kernel,
                              "/opt/extucode/80f00101.lid")
                self.scp_file(self.skiroot_initramfs,
                              "/opt/extucode/80f00102.lid")
            log.info("Regenerating the hashes by running command cupdmfg -opt")
            self.cv_BMC.fsp_run_command("cupdmfg -opt")

        if "AMI" in self.bmc_type:
            if self.skiboot:
                self.cv_BMC.image_transfer(self.skiboot)
                self.cv_BMC.skiboot_img_flash_ami(
                    "/tmp", os.path.basename(self.skiboot))
            if self.skiroot_kernel:
                self.cv_BMC.image_transfer(self.skiroot_kernel)
                self.cv_BMC.skiroot_img_flash_ami(
                    "/tmp", os.path.basename(self.skiroot_kernel))
            if self.flash_part_list:
                for part_pair in self.flash_part_list:
                    self.cv_BMC.image_transfer(part_pair[1])
                    self.cv_BMC.flash_part_ami("/tmp", os.path.basename(part_pair[1]),
                                               part_pair[0])

        if "SMC" in self.bmc_type:
            if self.skiboot:
                self.cv_BMC.image_transfer(self.skiboot)
                self.cv_BMC.skiboot_img_flash_smc(
                    "/tmp/rsync_file", os.path.basename(self.skiboot))
            if self.skiroot_kernel:
                self.cv_BMC.image_transfer(self.skiroot_kernel)
                self.cv_BMC.skiroot_img_flash_smc(
                    "/tmp/rsync_file", os.path.basename(self.skiroot_kernel))
            if self.flash_part_list:
                for part_pair in self.flash_part_list:
                    self.cv_BMC.image_transfer(part_pair[1])
                    self.cv_BMC.flash_part_smc("/tmp/rsync_file", os.path.basename(part_pair[1]),
                                               part_pair[0])

        if "OpenBMC" in self.bmc_type:
            # Check for field mode first, if it is enabled, clear that and flash host firmware.
            # otherwise OpenBMC won't allow to patch any Host FW code in field mode.
            if self.cv_REST.has_field_mode_set():
                log.debug("has_field_mode_set so calling clear_field_mode")
                self.cv_BMC.clear_field_mode()
                self.assertFalse(self.cv_REST.has_field_mode_set(),
                                 "Field mode disable failed")
            else:
                log.debug("has_field_mode_set NOT true, so did not clear")

            log.debug("passed field_mode_set checks")
            try:
                # OpenBMC started removing overrides *after* flashing new image
                # but on boot of the host, so we can't assume that just writing
                # new overrides is going to work. We're going to have to do
                # this sequence.
                log.debug("run_command systemctl restart mboxd.service")
                self.cv_BMC.run_command("systemctl restart mboxd.service")
            except CommandFailed as cf:
                log.debug("run_command systemctl restart mboxd.service failed cf={}".format(cf))
                pass
            if self.skiboot:
                self.cv_BMC.image_transfer(self.skiboot)
                self.cv_BMC.skiboot_img_flash_openbmc(
                    os.path.basename(self.skiboot))
            if self.skiroot_kernel:
                self.cv_BMC.image_transfer(self.skiroot_kernel)
                self.cv_BMC.skiroot_img_flash_openbmc(
                    os.path.basename(self.skiroot_kernel))
            if self.flash_part_list:
                for part_pair in self.flash_part_list:
                    self.cv_BMC.image_transfer(part_pair[1])
                    self.cv_BMC.flash_part_openbmc(
                        os.path.basename(part_pair[1]), part_pair[0])

        raw_pty = self.cv_SYSTEM.console.get_console()
        if "AMI" in self.bmc_type:
            self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class OOBHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.hpm_path = conf.args.host_hpm
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
                            "HPM File %s not doesn't exist" % self.hpm_path)
        super(OOBHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC Out-of-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        # FORCE us to not detect system state.
        # Since we're flashing, we need to ignore what's currently on the
        # machine as it may be pretty garbage firmware left over from previous
        # test runs.
        self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_IPMI.ipmi_code_update(self.hpm_path, str(
            BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class InbandHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.hpm_path = conf.args.host_hpm
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
                            "HPM File %s not doesn't exist" % self.hpm_path)
        super(InbandHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC In-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        self.cv_HOST.host_code_update(self.hpm_path, str(
            BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class FSPFWImageFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.image = conf.args.host_img_url
        super(FSPFWImageFLASH, self).setUp()

    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP In-band firmware Update test")
        if not self.image:
            self.skipTest("No FSP firmware image provided")

        self.cv_BMC.fsp_get_console()
        # Fetch the FSP side of flash active to verify after the update
        preup_boot = self.cv_BMC.fsp_run_command(
            "cupdcmd -f | grep \"Current Boot Side\"")
        preup_build = self.cv_BMC.fsp_run_command(
            "cupdcmd -f | grep \"Current Side Driver\"")
        log.info("System boot side %s, build: %s" % (preup_boot, preup_build))
        preup_boot = re.search('.*([T|P])', preup_boot)
        preup_boot = preup_boot.group(1)

        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        # Wait until we have a route (i.e. network is up)
        log.debug('#Waiting for network (by waiting for a route)')
        self.OpIU.configure_host_ip()
        con.run_command("wget %s -O /tmp/firm.img" % self.image)
        con.run_command("update_flash -d")
        con.pty.sendline("update_flash -f /tmp/firm.img")
        con.pty.expect('Projected Flash Update Results')
        con.pty.expect('FLASH: Image ready...rebooting the system...')
        con.pty.sendcontrol(']')
        con.pty.send('quit\r')
        con.close()
        self.bmc_down_check()
        self.util.PingFunc(self.cv_BMC.host_name,
                           BMC_CONST.PING_RETRY_POWERCYCLE)
        time.sleep(10)
        self.cv_BMC.fsp_get_console()
        con = self.cv_SYSTEM.console
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con.run_command("update_flash -d")
        postup_boot = self.cv_BMC.fsp_run_command(
            "cupdcmd -f | grep \"Current Boot Side\"")
        postup_boot = re.search('.*([T|P])', postup_boot)
        postup_boot = postup_boot.group(1)
        postup_build = self.cv_BMC.fsp_run_command(
            "cupdcmd -f | grep \"Current Side Driver\"")
        log.info("System Boot side: %s, build: %s" %
                 (postup_boot, postup_build))
        self.assertEqual(preup_boot, postup_boot,
                         "System booted from different bootside")
