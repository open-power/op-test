#!/usr/bin/python
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

#  @package OpTestFlash
#  Firmware flash tests for OpenPower testing.
#
#  This class contains the OpenPower Firmware flashing scripts for
#  AMI platforms 
#
#   PNOR Flash Update
#   Lid Updates(Currently skiboot lid) TODO: Add skiroot lid support
#   Out-of-band HPM Update
#   In-band HPM Update
# 
#  pre-requistes pflash tool should be in /tmp directory of BMC busy box
#


import os
import re
import time
import commands
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

class OpTestFlashBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.platform = conf.platform()
        self.util = OpTestUtil()
        self.bmc_type = conf.args.bmc_type

    def validate_side_activated(self):
        l_bmc_side, l_pnor_side = self.cv_IPMI.ipmi_get_side_activated()
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_bmc_side, "BMC: Primary side is not active")
        # TODO force setting of primary side to BIOS Golden side sensor
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_pnor_side, "PNOR: Primary side is not active")

    def get_pnor_level(self):
        rc = self.cv_IPMI.ipmi_get_PNOR_level()
        print rc

    def bmc_down_check(self):
        cmd = "ping -c 1 " + self.cv_BMC.host_name + " 1> /dev/null; echo $?"
        count = 0
        while count < 500:
            output = commands.getstatusoutput(cmd)
            if output[1] != '0':
                print "FSP/BMC Comes down"
                break
            count = count + 1
            time.sleep(2)
        else:
            self.assertTrue(False, "FSP/BMC keeps on pinging up")

        return True


class PNORFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.pnor_name = conf.args.host_pnor
        self.pnor_path = os.path.join(self.images_dir, self.pnor_name)
        self.assertNotEqual(os.path.exists(self.pnor_path), 0,
            "PNOR image %s not doesn't exist" % self.pnor_path)
        super(PNORFLASH, self).setUp()

    def runTest(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OP AMI/OpenBMC PNOR Flash test")
        if "AMI" in self.bmc_type:
            self.cv_BMC.validate_pflash_tool("/tmp")
            self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        self.cv_BMC.pnor_img_transfer(self.images_dir, self.pnor_name)
        if "AMI" in self.bmc_type:
            self.cv_BMC.pnor_img_flash_ami("/tmp", self.pnor_name)
        elif "OpenBMC" in self.bmc_type:
            self.cv_BMC.pnor_img_flash_openbmc(self.pnor_name)
        console = self.cv_SYSTEM.console.get_console()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if "AMI" in self.bmc_type:
            self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class SkibootLidFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.lid_name = conf.args.host_lid
        self.lid_path = os.path.join(self.images_dir, self.lid_name)
        self.assertNotEqual(os.path.exists(self.lid_path), 0,
            "Skiboot lid %s not doesn't exist" % self.lid_path)
        super(SkibootLidFLASH, self).setUp()

    def runTest(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OP AMI/OpenBMC PNOR Flash test")
        if "AMI" in self.bmc_type:
            self.cv_BMC.validate_pflash_tool("/tmp")
            self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        self.cv_BMC.pnor_img_transfer(self.images_dir, self.lid_name)
        if "AMI" in self.bmc_type:
            self.cv_BMC.skiboot_img_flash_ami("/tmp", self.lid_name)
        elif "OpenBMC" in self.bmc_type:
            self.cv_BMC.skiboot_img_flash_openbmc(self.lid_name)
        console = self.cv_SYSTEM.console.get_console()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if "AMI" in self.bmc_type:
            self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()

class OOBHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.hpm_name = conf.args.host_hpm
        self.hpm_path = os.path.join(self.images_dir, self.hpm_name)
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
            "HPM File %s not doesn't exist" % self.hpm_path)
        super(OOBHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC Out-of-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        try:
            self.cv_IPMI.ipmi_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        except OpTestError:
            self.cv_IPMI.ipmi_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class InbandHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.hpm_name = conf.args.host_hpm
        self.hpm_path = os.path.join(self.images_dir, self.hpm_name)
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
            "HPM File %s not doesn't exist" % self.hpm_path)
        super(InbandHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC In-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        try:
            self.cv_HOST.host_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        except OpTestError:
            self.cv_HOST.host_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class FSPFWImageFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.image = conf.args.host_img
        super(FSPFWImageFLASH, self).setUp()

    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP In-band firmware Update test")

        self.cv_BMC.fsp_get_console()
        # Fetch the FSP side of flash active to verify after the update
        preup_boot = self.cv_BMC.fsp_run_command("cupdcmd -f | grep \"Current Boot Side\"")
        preup_build = self.cv_BMC.fsp_run_command("cupdcmd -f | grep \"Current Side Driver\"")
        print "System boot side %s, build: %s" % (preup_boot, preup_build)
        preup_boot = re.search('.*([T|P])', preup_boot)
        preup_boot = preup_boot.group(1)

        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_SYSTEM.host_console_unique_prompt()
        con = self.cv_SYSTEM.sys_get_ipmi_console()
        con.run_command("wget %s -O /tmp/firm.img" % self.image)
        con.run_command("update_flash -d")
        con.sol.sendline("update_flash -f /tmp/firm.img")
        con.sol.expect('Projected Flash Update Results')
        con.sol.expect('Requesting system reboot')
        con.sol.sendcontrol(']')
        con.sol.send('quit\r')
        con.close()
        self.bmc_down_check()
        self.util.PingFunc(self.cv_BMC.host_name, BMC_CONST.PING_RETRY_POWERCYCLE)
        time.sleep(10)
        self.cv_BMC.fsp_get_console()
        con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_SYSTEM.host_console_unique_prompt()
        con.run_command("update_flash -d")
        postup_boot = self.cv_BMC.fsp_run_command("cupdcmd -f | grep \"Current Boot Side\"")
        postup_boot = re.search('.*([T|P])', postup_boot)
        postup_boot = postup_boot.group(1)
        postup_build = self.cv_BMC.fsp_run_command("cupdcmd -f | grep \"Current Side Driver\"")
        print "System Boot side: %s, build: %s" % (postup_boot, postup_build)
        self.assertEqual(preup_boot, postup_boot, "System booted from different bootside")
