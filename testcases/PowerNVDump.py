#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/PowerNVDump.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018-2019
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

#  @package PowerNVDump.py
#  This module can contain testcases related to Firmware & Kernel dump feature
#  including kdump, fadump aka MPIPL, opaldump, etc.
#
#   fadump aka MPIPL:
#   The goal of firmware-assisted dump is to enable the dump of
#   a crashed system, and to do so from a fully-reset system.
#   For more details refer
#       https://www.kernel.org/doc/Documentation/powerpc/firmware-assisted-dump.txt
#
#   kdump:
#   Kdump uses kexec to quickly boot to a dump-capture kernel whenever a
#   dump of the system kernel's memory needs to be taken (for example, when
#   the system panics).
#   For more details refer
#       https://www.kernel.org/doc/Documentation/kdump/kdump.txt
#
#   opaldump:
#   With MPIPL we support capturing opalcore. We can use gdb to debug OPAL
#   issues. For details refer `doc/mpipl.rst` under skiboot source tree.
#
#   Test scenarios:
#   1. Verify SBE initiated MPIPL flow (trigger SBE S0 interrupt directly)
#   2. Verify OPAL crash (trigger OPAL assert via pdbg)
#   3. Enable fadump - trigger a kernel crash
#   4. Enable kdump  - trigger a kernel crash
#   5. Disable dump  - trigger a kernel crash
#
#      and verify boot progress and collected dump components
#      (vmcore and opalcore).
#
#   NOTE: For remote kdump, network to be configured manually via static sysfs IP, before test starts.
#

import os
import pexpect
import unittest
import time
import re
import tempfile

import OpTestConfiguration
import OpTestLogger
from common import OpTestInstallUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import KernelOOPS, KernelPanic, KernelCrashUnknown, KernelKdump, KernelFADUMP, PlatformError, CommandFailed, SkibootAssert
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
import testcases.OpTestDlpar

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class BootType():
    NORMAL = 1
    MPIPL = 2
    KDUMPKERNEL = 3
    INVALID = 4


class PowerNVDump(unittest.TestCase):
    '''
    Main super class to test dump functionality for various dump targets
    '''

    def setUp(self):
        '''
        Pre setup before starting the dump test
        '''
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_BMC = conf.bmc()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.pdbg = conf.args.pdbg
        self.basedir = conf.basedir
        self.c = self.cv_SYSTEM.console
        if self.bmc_type == "FSP_PHYP" or self.bmc_type == "EBMC_PHYP" :
            self.is_lpar = True
            self.hmc_user = conf.args.hmc_username
            self.hmc_password = conf.args.hmc_password
            self.hmc_ip = conf.args.hmc_ip
            self.lpar_name = conf.args.lpar_name
            self.system_name = conf.args.system_name
            self.cv_HMC = self.cv_SYSTEM.hmc
            try: self.cpu_resource = conf.args.cpu_resource
            except AttributeError:
                self.cpu_resource = 1
            try: self.mem_resource = conf.args.mem_resource
            except AttributeError:
                self.mem_resource = 2048
        self.dump_server_ip = conf.args.dump_server_ip if 'dump_server_ip' in conf.args else ''
        self.dump_server_pw = conf.args.dump_server_pw if 'dump_server_pw' in conf.args else ''
        self.dump_path = conf.args.dump_path if 'dump_path' in conf.args else ''
        self.rsa_path = "/root/.ssh/dmp_id_rsa"
        try: self.url = conf.args.url
        except AttributeError:
            self.url = "http://liquidtelecom.dl.sourceforge.net/project/ebizzy/ebizzy/0.3/ebizzy-0.3.tar.gz"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        res = self.c.run_command("cat /etc/os-release")
        if "Ubuntu" in res[0] or "Ubuntu" in res[1]:
            self.distro = "ubuntu"
        elif 'Red Hat' in res[0] or 'Red Hat' in res[1]:
            self.distro = 'rhel'
            self.c.run_command("cp /etc/kdump.conf /etc/kdump.conf_bck")
        elif 'SLES' in res[0] or 'SLES' in res[1]:
            self.distro = 'sles'
            self.c.run_command("cp /etc/sysconfig/kdump /etc/sysconfig/kdump_bck")
        else:
            raise self.skipTest("Test currently supported only on ubuntu, sles and rhel")

    def setup_test(self, dump_place="local"):
        '''
        This methods does a pre configuration of kdump setup
        crash_content : a variable to point to right crash folder after core is
        generated by mpipl/kdump kernel. If dump failed this variable would be
        empty.
        '''
        if dump_place == "local":
            self.crash_content = self.c.run_command(
                "ls -l /var/crash | grep '^d'| awk '{print $9}'")
        if dump_place == "net":
            self.crash_content = self.c.run_command(
                "ssh -i %s root@%s \"ls -l %s | grep '^d'\" | awk '{print $9}'" % (self.rsa_path, self.dump_server_ip, self.dump_path))
            log.debug("crash content is %s" % (self.crash_content))

    def setup_pwdless_auth(self):
        # Setup Pulickey authentication for Kdump over ssh and NFS
        # creates key using ssh-keygen and copies key using sshpass
        # check for the successful ssh connection
        self.c.run_command("rm -f %s" % self.rsa_path)
        if self.distro == "rhel":
            cmd = "yum -y install sshpass"
        elif self.distro == "sles":
            cmd = "zypper install -y sshpass"
        else:
            cmd = "apt-get install -y sshpass"
        try:
            self.c.run_command(cmd, timeout=120)
        except CommandFailed:
            self.fail("sshpass package not available in Repository")
        try:
            self.c.run_command(
                "ssh-keygen -q -t rsa -f %s -P ''" % self.rsa_path)
            self.c.run_command("chmod 400 %s" % self.rsa_path)
            self.c.run_command("sshpass -p %s ssh-copy-id -o \"StrictHostKeyChecking no\" -i %s root@%s" %
                               (self.dump_server_pw, self.rsa_path, self.dump_server_ip))
        except CommandFailed:
            self.fail(
                "Failed to create/copy ssh key file")
        pwd_less = self.c.run_command(
            "ssh -i %s -o \"StrictHostKeyChecking no\" -o  \"NumberOfPasswordPrompts=0\" %s \"echo\"" % (self.rsa_path, self.dump_server_ip))

    def is_fadump_param_enabled(self):
        '''
        Method to verify fadump kernel parameter is set
        returns True if fadump=on 
        '''
        res = self.cv_HOST.host_run_command(BMC_CONST.PROC_CMDLINE)
        if "fadump=on" in " ".join(res):
            return True
        return False

    def is_fadump_enabled(self):
        '''
        Method to verify fadump is enabled
        returns True if fadump is configured
        '''
        res = self.c.run_command("cat /sys/kernel/fadump_enabled")[-1]
        if int(res) == 1:
            return True
        elif int(res) == 0:
            return False
        else:
            raise Exception("Unknown fadump_enabled value")

    def is_fadump_supported(self):
        '''
        Methods checks if fadump is supported 
        '''
        try:
            self.c.run_command("ls /sys/kernel/fadump_enabled")
            return True
        except CommandFailed:
            return False

    # Verify /ibm,opal/dump node is present int DT or not
    def is_mpipl_supported(self):
        '''
        Method to Verify /ibm,opal/dump node is present int DT or not
        '''
        try:
            self.c.run_command("ls %s" % BMC_CONST.OPAL_DUMP_NODE)
            return True
        except CommandFailed:
            return False

    def is_mpipl_boot(self):
        '''
        Method to verify MPIPL boot
        ''' 
        try:
            self.c.run_command("ls %s/mpipl-boot 2>/dev/null" % BMC_CONST.OPAL_DUMP_NODE)
            return True
        except CommandFailed:
            return False

    def verify_dump_dt_node(self, boot_type=BootType.NORMAL):
        '''
        Verify the dump DT node is enabled
        '''
        self.c.run_command("lsprop  %s" % BMC_CONST.OPAL_DUMP_NODE)
        self.c.run_command("lsprop %s/fw-load-area" % BMC_CONST.OPAL_DUMP_NODE)
        if boot_type == BootType.MPIPL:
            self.c.run_command("lsprop %s/mpipl-boot" % BMC_CONST.OPAL_DUMP_NODE)

    def verify_dump_file(self, boot_type=BootType.NORMAL, dump_place="local"):
        '''
        Verify if dump file present
        '''
        if self.distro == "rhel":
            self.c.run_command("cp /etc/kdump.conf_bck /etc/kdump.conf")
        if self.distro == "sles":
            self.c.run_command("cp /etc/sysconfig/kdump_bck /etc/sysconfig/kdump")
        if dump_place == "local":
            crash_content_after = self.c.run_command(
                "ls -l /var/crash | grep '^d'| awk '{print $9}'")
        if dump_place == "net":
            crash_content_after = self.c.run_command(
                "ssh root@%s -i %s \"ls -l %s | grep '^d'\" | awk '{print $9}'" % (self.dump_server_ip, self.rsa_path, self.dump_path))
        self.crash_content = list(
            set(crash_content_after) - set(self.crash_content))
        self.crash_content = list(filter(lambda x: re.search('\d{4}-\d{2}-\d{2}-\d{2}:\d{2}', x), self.crash_content))
        if len(self.crash_content):
            if dump_place == "net":
                self.c.run_command('scp -i %s -r root@%s:/%s/%s /var/crash/' %
                                  (self.rsa_path, self.dump_server_ip, self.dump_path, self.crash_content[0]), timeout=1200)
            if self.distro == "ubuntu":
                self.c.run_command("ls /var/crash/%s/dump*" %
                                   self.crash_content[0])
            else:
                res = self.c.run_command("ls /var/crash/%s/vmcore*" %
                                         self.crash_content[0])
                paths = res[0].split()
                file_names = [os.path.basename(path) for path in paths]
                # Check if vmcore-dmesg-incomplete.txt is present in file_names
                if "vmcore-dmesg-incomplete.txt" in file_names:
                    raise OpTestError("kdump failed to create vmcore file")
                else:
                    filtered_files = [f for f in file_names if f.startswith("vmcore") and not f == "vmcore-dmesg.txt"]
                    if filtered_files:
                        log.debug("vmcore file  %s exists in crash dir" % filtered_files)
                    else:
                        raise OpTestError("kdump failed to create vmcore file")
            if boot_type == BootType.MPIPL:
                self.c.run_command("ls /var/crash/%s/opalcore*" %
                                   self.crash_content[0])
        else:
            msg = "Dump directory not created"
            raise OpTestError(msg)
        self.c.run_command("rm -rf /var/crash/%s; sync" % self.crash_content[0])

    def verify_fadump_reg(self):
        '''
        Enable and verify fadump registered by checking opal/dmesg logs
        '''
        res = self.c.run_command("cat /sys/kernel/fadump_registered")[-1]
        if int(res) == 1:
            self.c.run_command("echo 0 > /sys/kernel/fadump_registered")

        if not self.is_lpar:
            self.c.run_command("dmesg > /tmp/dmesg_log")
            self.c.run_command("%s > /tmp/opal_log" % BMC_CONST.OPAL_MSG_LOG)
        self.c.run_command("echo 1 > /sys/kernel/fadump_registered")

        # Verify OPAL msglog to confirm whether registration passed or not
        if not self.is_lpar:
            opal_data = " ".join(self.c.run_command(
                "%s | diff -a /tmp/opal_log -" % BMC_CONST.OPAL_MSG_LOG))
            if "DUMP: Payload registered for MPIPL" in opal_data:
                log.debug("OPAL: Payload registered successfully for MPIPL")
            else:
                raise OpTestError("OPAL: Payload failed to register for MPIPL")

            # Verify kernel dmesg
            dmesg_data = " ".join(self.c.run_command(
                "dmesg | diff -a /tmp/dmesg_log -"))
            if "fadump: Registering for firmware-assisted kernel dump" in dmesg_data:
                log.debug("PowerNV: Registering for firmware-assisted kernel dump")
            else:
                raise OpTestError("PowerNV: Registering for firmware-assisted kernel dump failed")

            self.c.run_command("rm /tmp/opal_log")
            self.c.run_command("rm /tmp/dmesg_log")

    def verify_fadump_unreg(self):
        '''
        Disable and verify fadump unregistered by checking opal/dmesg logs
        '''
        res = self.c.run_command("cat /sys/kernel/fadump_registered")[-1]
        if int(res) == 0:
            self.c.run_command("echo 1 > /sys/kernel/fadump_registered")

        if not self.is_lpar:
            self.c.run_command("%s > /tmp/opal_log" % BMC_CONST.OPAL_MSG_LOG)
            self.c.run_command("dmesg > /tmp/dmesg_log")
            self.c.run_command("echo 0 > /sys/kernel/fadump_registered")

            opal_data = " ".join(self.c.run_command(
                "%s | diff -a /tmp/opal_log -" % BMC_CONST.OPAL_MSG_LOG))
            if "DUMP: Payload unregistered for MPIPL" in opal_data:
                log.debug("OPAL: Payload unregistered for MPIPL")
            else:
                raise OpTestError("OPAL: Payload failed to unregister for MPIPL")

            dmesg_data = " ".join(self.c.run_command(
                "dmesg | diff -a /tmp/dmesg_log -"))
            if "fadump: Un-register firmware-assisted dump" in dmesg_data:
                log.debug("PowerNV: Un-registering for firmware-assisted kernel dump")
            else:
                raise OpTestError("PowerNV: Un-registering for firmware-assisted kernel dump failed")

            self.c.run_command("rm /tmp/opal_log")
            self.c.run_command("rm /tmp/dmesg_log")

    def kernel_crash(self, crash_type="echo_c"):
        '''
        This function will test the kernel crash followed by system 
        reboot. It has below steps
            1. Enable reboot on kernel panic: echo 10 > /proc/sys/kernel/panic
            2. Trigger kernel crash: echo c > /proc/sysrq-trigger
        return BMC_CONST.FW_SUCCESS or raise OpTestError
        '''
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        # Disable fast-reboot, otherwise MPIPL may lead to fast-reboot
        if not self.is_lpar:
            self.c.run_command("nvram -p ibm,skiboot --update-config fast-reset=0")
        self.c.run_command("echo 10 > /proc/sys/kernel/panic")
        # Enable sysrq before triggering the kernel crash
        self.c.pty.sendline("echo 1 > /proc/sys/kernel/sysrq")
        if crash_type == "echo_c":
            self.c.pty.sendline("echo c > /proc/sysrq-trigger")
        elif crash_type == "hmc":
            self.cv_HMC.run_command("chsysstate -r lpar -m %s -n %s -o dumprestart" %
                                   (self.system_name, self.lpar_name), timeout=300)
        elif crash_type == "softlockup":
            self.c.pty.sendline("insmod /tmp/softlockup.ko")
        done = False
        boot_type = BootType.NORMAL
        rc = -1
        while not done:
            try:
                # MPIPL completion + system reboot would take time, keeping it
                # 600 seconds. Post MPIPL, kernel will offload vmcore and reboot
                # system. Hostboot will run istep 10.1 in normal boot only. So
                # check for istep 10.1 to detect normal boot.
                rc = self.c.pty.expect(
                    ["ISTEP 10. 1", "saving vmcore complete", "saved vmcore", "Rebooting."], timeout=600)
            except KernelFADUMP:
                log.debug("====================MPIPL boot started==================")
                # if fadump is enabled system should start MPIPL after kernel crash
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                boot_type = BootType.MPIPL
            except KernelOOPS:
                log.debug("==================Normal Boot===========================")
                # if both fadump and kdump is disabled, system should do normal
                # IPL after kernel crash(oops)
            except KernelPanic:
                log.debug("==================Normal Boot===========================")
                # if both fadump and kdump is disabled, system should do
                # normal IPL after kernel crash(oops)
                boot_type = BootType.NORMAL
            except KernelKdump:
                log.debug("================Kdump kernel boot=======================")
                # if kdump is enabled, kdump kernel should boot after kernel crash
                boot_type = BootType.KDUMPKERNEL
            except KernelCrashUnknown:
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
                done = True
                boot_type = BootType.NORMAL
            except pexpect.TIMEOUT:
                done = True
                boot_type = BootType.INVALID
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            except PlatformError:
                done = True
                boot_type = BootType.NORMAL
            if rc == 0:
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                done = True
            if rc == 1 or rc == 2 or rc == 3:
                log.debug("Kdump finished collecting core file, waiting for regular IPL to complete")
                if self.is_lpar:
                    log.debug("Kdump finished collecting core file, waiting for LPAR to boot")
                    self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
                    done = True

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.debug("System booted fine to host OS...")
        return boot_type


class OPALCrash_MPIPL(PowerNVDump):
    '''
    OPAL initiated MPIPL flow validation. This will verify whether OPAL
    supports MPIPL or not and then triggers OPAL assert. This will verify
    OPAL MPIPL flow and device tree property after dump. It will not
    verify whether core file is generated or not.
    '''

    def runTest(self):
        if not self.pdbg or not os.path.exists(self.pdbg):
            self.fail("pdbg file %s doesn't exist" % self.pdbg)

        self.setup_test()

        if not self.is_mpipl_supported():
            raise self.skipTest("MPIPL support is not found")

        # Verify device tree properties
        self.verify_dump_dt_node()

        pdbg_cmd = ""
        if "OpenBMC" in self.bmc_type:
            pdbg_cmd = "/tmp/pdbg -a putmem 0x300000f8 < /tmp/deadbeef"
        elif "SMC" in self.bmc_type:
            pdbg_cmd = "/tmp/rsync_file/pdbg -a putmem 0x300000f8 < /tmp/rsync_file/deadbeef"
        else:
            raise self.skipTest("pdbg not support on this BMC type : %s" % self.bmc_type)

        # To Verify OPAL MPIPL flow we don't need host kdump service.
        # Hence disable kdump service
        os_level = self.cv_HOST.host_get_OS_Level()
        if self.cv_HOST.host_check_pkg_kdump(os_level) is True:
            self.cv_HOST.host_disable_kdump_service(os_level)

        cmd = "rm /tmp/pdbg; rm /tmp/deadbeef"
        try:
            self.cv_BMC.run_command(cmd)
        except CommandFailed:
            pass
        # copy the pdbg file to BMC
        self.cv_BMC.image_transfer(self.pdbg)
        deadbeef = os.path.join(self.basedir, "test_binaries", "deadbeef")
        self.cv_BMC.image_transfer(deadbeef)
        # Trigger OPAL assert via pdbg
        self.cv_BMC.run_command(pdbg_cmd)

        done = False
        boot_type = BootType.NORMAL
        rc = -1
        while not done:
            try:
                # MPIPL boot will take time, keeping it 600 seconds.
                rc = self.c.pty.expect(['\n', 'ISTEP 14. 8'], timeout=600)
            except(SkibootAssert, KernelFADUMP):
                log.debug("====================MPIPL boot started===================")
                # System will start MPIPL flow after OPAL assert
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                boot_type = BootType.MPIPL
            except pexpect.TIMEOUT:
                done = True
                boot_type = BootType.INVALID
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            except PlatformError:
                done = True
                boot_type = BootType.NORMAL
            if rc == 1:
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                done = True

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.debug("System booted fine to host OS...")
        if not self.is_mpipl_boot():
            raise OpTestError("OPAL: MPIPL boot failed")
        self.verify_dump_dt_node(BootType.MPIPL)
        return boot_type


class SBECrash_MPIPL(PowerNVDump):
    '''
    Testcase to test SBE and hostboot part of MPIPL code.
    This test would trigger SBE S0 interrupt directly to initiate MPIPL.
    SBE will initiate MPIPL flow and eventually system boots back.
    '''

    def runTest(self):

        if "OpenBMC" not in self.bmc_type:
            raise self.skipTest(
                "SBE initiated MPIPL is not supported on non-OpenBMC machine yet")

        self.setup_test()

        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        # Get all chip ids on the machine
        xscom_dirs = self.c.run_command(
            "ls /sys/firmware/devicetree/base/ | grep xscom")
        secondary_chip_ids = []
        primary_chipid = None
        for node in xscom_dirs:
            if node:
                chip_id = self.c.run_command(
                    "lsprop /sys/firmware/devicetree/base/%s/ibm,chip-id" % node)
                # Check if chip_id is primary. For some reason os.path.exists is
                # failing. Hence using `ls` command to detect primary property
                try:
                    self.c.run_command("ls /sys/firmware/devicetree/base/%s/primary 2>/dev/null" % node)
                    primary_chipid = chip_id[-1].strip()
                except CommandFailed:
                    secondary_chip_ids.append(chip_id[-1].strip())
                    pass

        if not primary_chipid:
            raise OpTestError("BUG: Primary node property is missing!!")

        # To Verify SBE/hostboot MPIPL flow we don't need host kdump service.
        # Hence disable kdump service
        os_level = self.cv_HOST.host_get_OS_Level()
        if self.cv_HOST.host_check_pkg_kdump(os_level) is True:
            self.cv_HOST.host_disable_kdump_service(os_level)

        # Make sure /tmp/skiboot directory does not exist
        r_workdir = "/tmp/skiboot"
        self.c.run_command("rm -rf %s" % r_workdir)

        # Clone skiboot git repository
        r_cmd = "git clone --depth 1 https://github.com/open-power/skiboot.git %s" % r_workdir
        self.c.run_command(r_cmd)
        # Compile putscom utility
        r_cmd = "cd %s/external/xscom-utils; make; cd -" % r_workdir
        self.c.run_command(r_cmd)
        try:
            # Check existence of putscom utility after compiling
            r_cmd = "test -f %s/external/xscom-utils/putscom" % r_workdir
            self.c.run_command(r_cmd)
        except CommandFailed as cf:
            raise self.skipTest(
                "putscom utility missing after compiling!!! %s" % str(cf))
        # BMC is not aware of MPIPL. We have to reset MBOX so that it can point
        # to initial flash area and SBE can load it from LPC bus.
        cmd = "mboxctl --reset"
        self.cv_BMC.run_command(cmd)
        # trigger SBE initiated MPIPL starting with secondary chip ids followed
        # by primary chip (Send S0 interrupt to SBE).
        if secondary_chip_ids:
            for chip_id in secondary_chip_ids:
                self.c.pty.sendline(
                    "%s/external/xscom-utils/putscom -c %s 0x50008 0x0002000000000000" % (r_workdir, chip_id))
        self.c.pty.sendline(
            "%s/external/xscom-utils/putscom -c %s 0x50008 0x0002000000000000" % (r_workdir, primary_chipid))

        done = False
        boot_type = BootType.NORMAL
        rc = -1
        while not done:
            try:
                # Verify MPIPL boot (wait for 600 secs before throwing error)
                rc = self.c.pty.expect(['ISTEP 14. 8'], timeout=600)
            except pexpect.TIMEOUT:
                done = True
                boot_type = BootType.INVALID
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            except PlatformError:
                done = True
                boot_type = BootType.NORMAL
            if rc == 0:
                log.debug("===================MPIPL boot started===================")
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                boot_type = BootType.MPIPL
                done = True

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.debug("System booted fine to host OS...")
        log.debug("cleanup skiboot clone")
        r_cmd = "rm -rf %s" % r_workdir
        self.c.run_command(r_cmd)


class KernelCrash_FadumpEnable(PowerNVDump):
    '''
    This Class test KDUMP functionality with firmware assisted dump enabled 
    It performs all similar steps as kdump with fadump=on in kernel commandline
    '''

    def setup_fadump(self):
        '''
        Pre setup for fadump configuration
        '''
        self.cv_SYSTEM.set_state(OpSystemState.OS)
        if self.distro == "rhel":
            self.c.run_command("sed -e '/nfs/ s/^#*/#/' -i /etc/kdump.conf; sync")
            obj = OpTestInstallUtil.InstallUtil()
            if not obj.update_kernel_cmdline(self.distro, args="fadump=on crashkernel=2G-128G:2048M,128G-:8192M",
                                             reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
        if self.distro == "sles":
            self.c.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"/var/crash\"\' /etc/sysconfig/kdump;')
            self.c.run_command("sed -i '/KDUMP_FADUMP=\"no\"/c\KDUMP_FADUMP=\"yes\"' /etc/sysconfig/kdump")
            self.c.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=180)
            self.c.run_command("mkdumprd -f", timeout=120)
            self.c.run_command("update-bootloader --refresh")
            self.c.run_command("zypper install -y ServiceReport; servicereport -r -p kdump;"
                               "update-bootloader --refresh", timeout=240)
            time.sleep(5)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def runTest(self):
        self.setup_test()
        self.setup_fadump()
        self.c.run_command("fsfreeze -f /boot; fsfreeze -u /boot")
        if not self.is_lpar:
            if not self.is_mpipl_supported():
                raise self.skipTest("MPIPL support is not found")
            self.verify_dump_dt_node()
        if not self.is_fadump_param_enabled():
            raise self.skipTest(
                "fadump=on not added in kernel param, please add and re-try")
        if not self.is_fadump_supported():
            raise self.skipTest(
                "fadump not enabled in the kernel, does system has right firmware!!!")
        if not self.is_fadump_enabled():
            raise self.skipTest("fadump_enabled is off")
        if self.distro == "ubuntu":
            self.cv_HOST.host_check_command("kdump")
        elif self.distro == "rhel":
            self.cv_HOST.host_check_command("kdumpctl")
        elif self.distro == "sles":
            self.cv_HOST.host_check_command("kdumptool")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.verify_fadump_unreg()
        self.verify_fadump_reg()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        log.debug("======================fadump is supported=======================")
        boot_type = self.kernel_crash()
        if not self.is_lpar:
            self.verify_dump_dt_node(boot_type)
        self.verify_dump_file(boot_type)


class KernelCrash_OnlyKdumpEnable(PowerNVDump):
    '''
    This classs does preconfiguration and enablement for kdump test
    '''

    def runTest(self):
        self.setup_test()
        if not self.is_lpar:
            if self.is_fadump_supported():
                raise self.skipTest("fadump is enabled, please disable(remove fadump=on \
                                   kernel parameter and re-try")
        if self.is_fadump_param_enabled():
            raise self.skipTest(
                "fadump=on added in kernel param, please remove and re-try")
        if self.distro == "ubuntu":
            self.cv_HOST.host_check_command("kdump")
        elif self.distro == "rhel":
            self.cv_HOST.host_check_command("kdumpctl")
            obj = OpTestInstallUtil.InstallUtil()
            if not obj.update_kernel_cmdline(self.distro, args="crashkernel=2G-16G:512M,16G-64G:1G,64G-128G:2G,128G-:4G",
                                             reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
        elif self.distro == "sles":
            self.cv_HOST.host_check_command("kdumptool")
            self.c.run_command("zypper install -y ServiceReport; servicereport -r -p kdump;"
                               "update-bootloader --refresh", timeout=240)
            time.sleep(5)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        if self.is_lpar:
            boot_type = self.kernel_crash(crash_type="hmc")
            self.verify_dump_file(boot_type)


class KernelCrash_DisableAll(PowerNVDump):
    '''
    Disable kdump service and boot back to normal
    '''

    def runTest(self):
        self.setup_test()
        if self.is_fadump_param_enabled():
            raise self.skipTest(
                "fadump=on added in kernel param, please remove and re-try")
        if self.distro == "ubuntu":
            self.cv_HOST.host_check_command("kdump")
        elif self.distro == "rhel":
            self.cv_HOST.host_check_command("kdumpctl")
        elif self.distro == "sles":
            self.cv_HOST.host_check_command("kdumptool")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_disable_kdump_service(os_level)
        boot_type = self.kernel_crash()
        if boot_type != BootType.NORMAL:
            msg = "Invalid boot %d after kernel crash instead of normal boot" % int(
                boot_type)
            raise OpTestError(msg)


class SkirootKernelCrash(PowerNVDump, unittest.TestCase):
    '''
    KDUMP test wth skiroot configurations enabled
    brief This tests the Skiroot kernel crash followed by system IPL
            1. Skiroot kernel has by default xmon is on, so made it off
            2. Trigger kernel crash: echo c > /proc/sysrq-trigger
            3. Check for system booting
    return BMC_CONST.FW_SUCCESS or raise OpTestError
    '''

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        output = self.c.run_command(BMC_CONST.PROC_CMDLINE)
        res = ""
        update = False
        for pair in output[0].split(" "):
            if "xmon" in pair:
                if pair == "xmon=off":
                    return
                pair = "xmon=off"
                update = True
            res = "%s %s" % (res, pair)

        if not update:
            pair = "xmon=off"
            res = "%s %s" % (res, pair)
        bootargs = "\'%s\'" % res
        log.debug(bootargs)
        self.c.run_command(
            "nvram -p ibm,skiboot --update-config bootargs=%s" % bootargs)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    def runTest(self):
        self.setup_test()
        self.cv_SYSTEM.sys_set_bootdev_no_override()
        self.kernel_crash()


class KernelCrash_KdumpSSH(PowerNVDump):
    '''
    This test verifies kdump/fadump over ssh.
    Need to pass --dump-server-ip and --dump-server-pw in command line.
    Needs passwordless authentication setup between test machine and ssh server.
    '''

    def setUp(self):
        super(KernelCrash_KdumpSSH, self).setUp()

        conf = OpTestConfiguration.conf
        self.dump_location = self.dump_server_ip
        self.dump_server_private_ip = conf.args.dump_server_private_ip if 'dump_server_private_ip' in conf.args else None
        if self.dump_server_private_ip:
            self.interface = conf.args.interface
            self.interface_ip = conf.args.interface_ip
            self.netmask = conf.args.netmask
            self.dump_location = self.dump_server_private_ip

    def setup_ssh(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if self.distro == "rhel":
            self.c.run_command("sed -i -e '/^nfs/ s/^#*/#/' /etc/kdump.conf; sync")
            self.c.run_command("sed -i '/ssh user@my.server.com/c\ssh root@%s' /etc/kdump.conf; sync" % self.dump_server_ip)
            self.c.run_command("sed -i '/sshkey \/root\/.ssh\/kdump_id_rsa/c\sshkey %s' /etc/kdump.conf; sync" % self.rsa_path)
            self.c.run_command("sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf; sync")
            self.c.run_command("sed -i '/^path/ s/^#*/#/' /etc/kdump.conf;"
                               "echo 'path %s' >> /etc/kdump.conf; sync" % self.dump_path)
            self.c.run_command("systemctl restart kdump.service", timeout=180)
            self.c.run_command("fsfreeze -f /boot; fsfreeze -u /boot")
            time.sleep(5)
            res = self.c.run_command("service kdump status | grep active")
            if 'dead' in res:
                self.fail("Kdump service is not configured properly")
        elif self.distro == "ubuntu":
            self.c.run_command("sed -i '/SSH=\"<user at server>\"/c\SSH=\"root@%s\"' /etc/default/kdump-tools" % self.dump_server_ip)
            self.c.run_command("sed -i '/SSH_KEY=\"<path>\"/c\SSH_KEY=%s' /etc/default/kdump-tools" % self.rsa_path)
            self.c.run_command("kdump-config unload;")
            self.c.run_command("kdump-config load;")
            time.sleep(5)
        else:
            self.c.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"ssh:\/\/root@%s\/%s\"\' /etc/sysconfig/kdump;' %
                               (self.dump_server_ip, self.dump_path))
            self.c.run_command('sed -i \'/^KDUMP_SSH_IDENTITY=/c\KDUMP_SSH_IDENTITY=\"%s\"\' /etc/sysconfig/kdump;' % self.rsa_path)
            self.c.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=180)
            time.sleep(5)

    def runTest(self):
        if not (self.dump_server_ip or self.dump_server_pw):
            raise self.skipTest("Provide --dump-server-ip and --dump-server-pw "
                                "for network dumps")
        self.setup_pwdless_auth()
        self.setup_test("net")
        self.setup_ssh()
        log.info("=============== Testing kdump/fadump over ssh ===============")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type, dump_place="net")
        self.setup_test("net")

class KernelCrash_KdumpNFS(PowerNVDump):
    '''
    This test verifies kdump/fadump over nfs.
    Need to pass --dump-server-ip and --dump-server-pw in command line.
    Needs passwordless authentication setup between test machine and nfs server.
    '''

    def setUp(self):
        super(KernelCrash_KdumpNFS, self).setUp()

        conf = OpTestConfiguration.conf
        self.dump_location = self.dump_server_ip
        self.dump_server_private_ip = conf.args.dump_server_private_ip if 'dump_server_private_ip' in conf.args else None
        if self.dump_server_private_ip:
            self.interface = conf.args.interface
            self.interface_ip = conf.args.interface_ip
            self.netmask = conf.args.netmask
            self.dump_location = self.dump_server_private_ip

    def setup_nfs(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if self.distro == "rhel":
            self.c.run_command("sed -i '/ssh root@%s/c\#ssh user@my.server.com' /etc/kdump.conf; sync" % self.dump_server_ip)
            self.c.run_command("sed -i '/sshkey %s/c\#sshkey \/root\/.ssh\/kdump_id_rsa' /etc/kdump.conf; sync" % self.rsa_path)
            self.c.run_command("yum -y install nfs-utils", timeout=180)
            self.c.run_command("service nfs-server start")
            self.c.run_command("sed -i -e '/^nfs/ s/^#*/#/' /etc/kdump.conf;"
                               "echo 'nfs %s:%s' >> /etc/kdump.conf; sync" % (self.dump_location, self.dump_path))
            self.c.run_command("sed -i 's/-l -F --message-level/-l --message-level/' /etc/kdump.conf; sync")
            self.c.run_command("sed -i '/^path/ s/^#*/#/' /etc/kdump.conf; echo 'path /' >> /etc/kdump.conf; sync")
            self.c.run_command("mount -t nfs %s:%s /var/crash" % (self.dump_location, self.dump_path))
            self.c.run_command("systemctl restart kdump.service", timeout=180)
            self.c.run_command("fsfreeze -f /boot; fsfreeze -u /boot")
            res = self.c.run_command("service kdump status | grep active")
            if 'dead' in res:
                self.fail("Kdump service is not configured properly")
        elif self.distro == "ubuntu":
            self.c.run_command("sed -e '/NFS/ s/^#*/#/' -i /etc/default/kdump-tools;")
            self.c.run_command("apt-get install -y nfs-common;")
            self.c.run_command("apt-get install -y nfs-kernel-server;")
            self.c.run_command("service nfs-server start;")
            self.c.run_command("mount -t nfs %s:%s /var/crash;" % (self.dump_location, self.dump_path))
            self.c.run_command("sed -e '/SSH/ s/^#*/#/' -i /etc/default/kdump-tools;")
            self.c.run_command("sed -i '/NFS=\"<nfs mount>\"/c\\NFS=\"%s:%s\"' /etc/default/kdump-tools" % (self.dump_location, self.dump_path))
            time.sleep(5)
        else:
            self.c.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"nfs:\/\/%s\%s\"\' /etc/sysconfig/kdump;' % (self.dump_server_ip, self.dump_path))
            self.c.run_command('sed -i \'/^KDUMP_SSH_IDENTITY=/c\KDUMP_SSH_IDENTITY=\"%s\"\' /etc/sysconfig/kdump;' % self.rsa_path)
            self.c.run_command("zypper install -y nfs-kernel-server; service nfs start")
            self.c.run_command("mount -t nfs %s:%s /var/crash" % (self.dump_location, self.dump_path))
            self.c.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=180)
            time.sleep(5)

    def runTest(self):
        if not (self.dump_server_ip or self.dump_server_pw):
            raise self.skipTest("Provide --dump-server-ip and --dump-server-pw "
                                "for network dumps")
        self.setup_pwdless_auth()
        self.setup_test("net")
        self.setup_nfs()
        log.info("=============== Testing kdump/fadump over nfs ===============")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type, dump_place="net")
        self.setup_test("net")


class KernelCrash_KdumpSAN(PowerNVDump):
    '''
    This test verifies kdump/fadump over SAN disk with FS and raw disk.
    '''

    def setUp(self):
        super(KernelCrash_KdumpSAN, self).setUp()

        conf = OpTestConfiguration.conf
        self.dev_path = conf.args.dev_path
        self.filesystem = conf.args.filesystem if 'filesystem' in conf.args else ''

    def setup_san(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if self.distro == "rhel":
            self.c.run_command("sfdisk --delete %s" % self.dev_path)
            self.c.run_command("echo , | sfdisk --force %s" % self.dev_path, timeout=120)
            try: self.c.run_command("umount %s1" % self.dev_path)
            except: pass
            self.c.run_command("dd if=/dev/zero bs=512 count=512 of=%s1" % self.dev_path)
            if self.filesystem:
                self.c.run_command("yes | mkfs.%s %s1" % (self.filesystem, self.dev_path))
                self.c.run_command("sed -i '/^path/ s/^#*/#/' /etc/kdump.conf; echo 'path /' >> /etc/kdump.conf; sync")
                self.c.run_command("sed -i '/^%s/ s/^#*/#/' /etc/kdump.conf; echo '%s %s1' >> /etc/kdump.conf; sync" % (
                                   self.filesystem, self.filesystem, self.dev_path))
                self.c.run_command("sed -i '/\/var\/crash %s/d' /etc/fstab;"
                                   "echo '%s1 /var/crash %s defaults 0 0' >> /etc/fstab; sync" % (
                                   self.filesystem, self.dev_path, self.filesystem))
                self.c.run_command("mount -t %s %s1 /var/crash" % (self.filesystem, self.dev_path))
            else:
                self.c.run_command("sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf; sync")
                self.c.run_command("sed -i '/^raw/ s/^#*/#/' /etc/kdump.conf;"
                                   "echo 'raw %s1' >> /etc/kdump.conf; sync" % (self.dev_path))
                self.c.run_command("sed -i '/^path/ s/^#*/#/' /etc/kdump.conf; sync")
            self.c.run_command("systemctl restart kdump.service; sync", timeout=600)

    def runTest(self):
        self.setup_test()
        self.setup_san()
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        self.setup_test()
        if self.filesystem:
            self.c.run_command("sed -i '/\/var\/crash %s/d' /etc/fstab; sync" % self.filesystem)


class KernelCrash_KdumpSMT(PowerNVDump):
    '''
    This test tests kdump/fadump with smt=1,2,4 and 
    kdump/fadump with smt=1,2,4 and dumprestart from HMC.
    '''

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        for i in ["off", "2", "4"]:
            self.setup_test()
            self.c.run_command("ppc64_cpu --smt=%s" % i, timeout=180)
            self.c.run_command("ppc64_cpu --smt")
            log.info("=============== Testing kdump/fadump with smt=%s ===============" % i)
            boot_type = self.kernel_crash()
            self.verify_dump_file(boot_type)
        self.setup_test()
        self.c.run_command("ppc64_cpu --cores-on=1", timeout=180)
        self.c.run_command("ppc64_cpu --cores-on")
        log.info("=============== Testing kdump/fadump with single core ===============")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        self.setup_test()
        self.c.run_command("ppc64_cpu --cores-on=1", timeout=180)
        self.c.run_command("ppc64_cpu --smt=off", timeout=180)
        log.info("=============== Testing kdump/fadump with single cpu ===============")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        if self.is_lpar:
            for i in ["off", "2", "4", "on"]:
                self.setup_test()
                self.c.run_command("ppc64_cpu --smt=%s" % i, timeout=180)
                self.c.run_command("ppc64_cpu --smt")
                log.info("=============== Testing kdump/fadump with smt=%s and dumprestart from HMC ===============" % i)
                boot_type = self.kernel_crash(crash_type="hmc")
                self.verify_dump_file(boot_type)

class KernelCrash_KdumpDLPAR(PowerNVDump, testcases.OpTestDlpar.OpTestDlpar):

    # This test verifies kdump/fadump after cpu and memory add/remove.
    # cpu_resource and mem_resource must be defined in ~/.op-test-framework.conf.
    # cpu_resource - max number of CPU
    # mem_resource - max memory in MB
    # Ex: cpu_resource=4
    #     mem_resource=2048

    def runTest(self):
        self.extended = {'loop':0,'wkld':0,'smt':8}
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        for component in ['proc', 'mem']:
            for operation in ['a', 'r']:
                self.setup_test()
                if component == "proc":
                    self.AddRemove("proc", "--procs", operation, self.cpu_resource)
                else:
                    self.AddRemove("mem", "-q", operation, self.mem_resource)
                log.info("=============== Testing kdump/fadump after %s %s ===============" % (component, operation))
                boot_type = self.kernel_crash()
                self.verify_dump_file(boot_type)


class KernelCrash_KdumpWorkLoad(PowerNVDump):

    # This test verifies kdump/fadump after running ebizzy.
    # ebizzy url needs to be given in ~/.op-test-framework.conf.
    # Ex: url=http://liquidtelecom.dl.sourceforge.net/project/ebizzy/ebizzy/0.3/ebizzy-0.3.tar.gz


    def runTest(self):
        if not self.url:
            raise self.skipTest("Provide ebizzy url in op-test-framework.conf")
        self.setup_test()
        if self.distro == "rhel":
            cmd = "yum -y install make gcc wget"
        elif self.distro == "ubuntu":
            cmd = "apt-get install -y make gcc wget"
        else:
            cmd = "zypper install -y make gcc wget"
        self.c.run_command(cmd, timeout=120)
        try:
            self.c.run_command("wget %s -P /tmp" % self.url)
        except CommandFailed:
            self.fail("Failed to download ebizzy tar")
        self.c.run_command("tar -xf /tmp/ebizzy*.tar.gz -C /tmp")
        self.c.run_command("cd /tmp/ebizzy*/")
        try:
            self.c.run_command("./configure; make")
        except CommandFailed:
            self.fail("Failed to compile ebizzy")
        self.c.run_command("./ebizzy -S 60&")
        self.c.run_command("./ebizzy -s 10737418240 -S 60 &")
        time.sleep(50)
        self.c.run_command("ps -ef|grep ebizzy")
        self.c.run_command("free -h")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        self.c.run_command("rm -rf /tmp/ebizzy*")

class KernelCrash_hugepage_checks(PowerNVDump):
    '''
    This test checks hugepage size set after kdump/fadump
    '''

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.setup_test()
        log.info("=============== Testing kdump/fadump with default hugepage size ===============")
        hugepage_size = self.c.run_command("awk '$1 == \"Hugepagesize:\" {print $2}' /proc/meminfo")[0]
        log.info("Hugepage size is {} kB".format(hugepage_size))
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        hugepage_size = self.c.run_command("awk '$1 == \"Hugepagesize:\" {print $2}' /proc/meminfo")[0]
        log.info("After dump/restart, Hugepage size is {} kB".format(hugepage_size))
        if hugepage_size != '2048' :
            raise OpTestError("Failed to set  default hugepage size 2MB")
        else:
            log.info("PASSED: Hugepage size is {} kB".format(hugepage_size))

        mmu = self.c.run_command("awk '$1 == \"MMU\" {print $3}' /proc/cpuinfo")[0]
        log.debug(" MMU '{}'".format(mmu))
        if mmu == "Radix":
            log.info("=============== Testing kdump/fadump with 1GB hugepage size ===============")
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.setup_test()
            obj = OpTestInstallUtil.InstallUtil()
            if not obj.update_kernel_cmdline(self.distro, args="default_hugepagesz=1GB hugepagesz=1GB hugepages=80",
                                             reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            boot_type = self.kernel_crash()
            self.verify_dump_file(boot_type)
            hugepage_size = self.c.run_command("awk '$1 == \"Hugepagesize:\" {print $2}' /proc/meminfo")[0]
            log.info("After dump/restart , Hugepage size set is {}".format(hugepage_size))
            if hugepage_size != '1048576' :
                raise OpTestError("Failed to set hugepage size to 1GB")
            else:
                log.info("PASSED: Hugepage size is {} kB".format(hugepage_size))

class KernelCrash_XIVE_off(PowerNVDump):
    '''
    This test checks kdump/fadump with kernel parameter option xive=off 
    with different levels of SMT levels
    '''

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.setup_test()
        log.info("=============== Testing kdump/fadump with xive=off ===============")
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        obj = OpTestInstallUtil.InstallUtil()
        if not obj.update_kernel_cmdline(self.distro, args="xive=off",
                                         reboot=True, reboot_cmd=True):
            self.fail("KernelArgTest failed to update kernel args")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        kernel_boottime_arg = self.c.run_command("cat /proc/cmdline | grep -o 'xive=off'")[0]
        if kernel_boottime_arg != 'xive=off' :
            raise OpTestError("Failed to set kernel parameter xive=off")
        else:
            log.info("The kernel parameter was set to {}".format(kernel_boottime_arg))
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)

        log.info("Test Kdump with xive=off along with different SMT levels")
        for i in ["off", "2", "4", "on"]:
            self.setup_test()
            self.c.run_command("ppc64_cpu --smt=%s" % i, timeout=180)
            self.c.run_command("ppc64_cpu --smt")
            log.info("Testing kdump/fadump with smt=%s and dumprestart from HMC" % i)
            boot_type = self.kernel_crash(crash_type="hmc")
            self.verify_dump_file(boot_type)

        log.info("Cleanup: Set SMT level to default and remove XIVE=off")
        self.c.run_command("ppc64_cpu --smt=8", timeout=180)
        self.c.run_command("ppc64_cpu --smt")

        obj = OpTestInstallUtil.InstallUtil()
        if not obj.update_kernel_cmdline(self.distro, remove_args="xive=off",
                                         reboot=True, reboot_cmd=True):
            self.fail("KernelArgTest failed to update kernel args")

class KernelCrash_disable_radix(PowerNVDump):
    '''
    This test checks kdump/fadump with kernel parameter option disable_radix
    '''

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.setup_test()
        log.info("Testing kdump/fadump with disable_radix")
        mmu = self.c.run_command("awk '$1 == \"MMU\" {print $3}' /proc/cpuinfo")[0]
        log.debug(" MMU '{}'".format(mmu))
        if mmu == "Radix":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            obj = OpTestInstallUtil.InstallUtil()
            if not obj.update_kernel_cmdline(self.distro, args="disable_radix",
                                             reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            kernel_boottime_arg = self.c.run_command("cat /proc/cmdline | grep -o 'disable_radix'")[0]
            if kernel_boottime_arg != 'disable_radix' :
                raise OpTestError("Failed to set kernel parameter disable_radix")
            else:
                log.info("The kernel parameter was set to {}".format(kernel_boottime_arg))
            boot_type = self.kernel_crash()
            self.verify_dump_file(boot_type)
            log.info("Test Kdump with xive=off along with different SMT levels")
            for i in ["off", "2", "4", "on"]:
                self.setup_test()
                self.c.run_command("ppc64_cpu --smt=%s" % i, timeout=180)
                self.c.run_command("ppc64_cpu --smt")
                log.info("Testing kdump/fadump with smt=%s and dumprestart from HMC" % i)
                boot_type = self.kernel_crash(crash_type="hmc")
                self.verify_dump_file(boot_type)

            log.info("Cleanup: Set  SMT level to default and remove disable_radix")
            self.c.run_command("ppc64_cpu --smt=8", timeout=180)
            self.c.run_command("ppc64_cpu --smt")

            obj = OpTestInstallUtil.InstallUtil()
            if not obj.update_kernel_cmdline(self.distro, remove_args="disable_radix",
                                             reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
        else:
            raise self.skipTest("Hash MMU detected, skipping the test")

class OpTestMakedump(PowerNVDump):
    '''
    function will trigger crash kernel and  run the makedumpfile on collected vmcore
    '''

    def check_run(self, cmd, condition):
        res = self.c.run_command(cmd)
        for value in res:
            if condition in value:
                log.info("command %s works well" % cmd)
                return
        self.fail("commnd %s failed" % cmd)

    def makedump_check(self):
        '''
        Function will verify all makdump options on already colleted vmcore
        '''
        res = self.c.run_command("ls -1 /var/crash/")
        crash_dir = self.c.run_command("cd /var/crash/%s" % res[0])
        res = self.c.run_command("ls")
        if 'vmcore' not in res[0]:
            self.fail("vmcore is not saved")
        else:
            log.info("vmcore is saved")
        self.c.run_command("makedumpfile -v")
        self.check_run("makedumpfile --split -d 31 -l vmcore dump3 dump4",
                       "The dumpfiles are saved to dump3, and dump4")
        self.check_run("makedumpfile --reassemble dump3 dump4 dump5",
                       "The dumpfile is saved to dump5")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile -b 8 -d 31 -l vmcore dump2",
                       "The dumpfile is saved to dump2")
        self.check_run("makedumpfile -f -d 31 -l vmcore dump6",
                       "The dumpfile is saved to dump6")
        self.check_run("makedumpfile --dump-dmesg vmcore log",
                       "The dmesg log is saved to log")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("rm -rf log")
        self.check_run("makedumpfile --cyclic-buffer 1024 vmcore dump10",
                       "The dumpfile is saved to dump10")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile --split --splitblock-size 1024 vmcore dump12 dump13 dump14",
                       "The dumpfiles are saved to dump12, dump13, and dump14")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile --work-dir /tmp vmcore dump20",
                       "The dumpfile is saved to dump20")
        self.check_run("makedumpfile --non-mmap vmcore dump22",
                       "The dumpfile is saved to dump22")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile -D -d 31 -l vmcore dump1",
                       "The dumpfile is saved to dump1")
        self.check_run("makedumpfile -D -d 31 -l vmcore dump41 --num-threads 8",
                       "The dumpfile is saved to dump41")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile -d 31 -c vmcore dump42",
                       "The dumpfile is saved to dump42")
        self.check_run("makedumpfile -d 31 -p vmcore dump43",
                       "The dumpfile is saved to dump43")
        self.c.run_command("rm -rf dump*")
        self.check_run("makedumpfile -d 31 -e vmcore --work-dir /tmp dump44",
                       "The dumpfile is saved to dump44")
        self.c.run_command(
            "makedumpfile -d 31 -c vmcore dump51 --message-level 21")
        self.c.run_command("rm -rf dump*")

    def runTest(self):
        self.kernel_crash()
        self.makedump_check()


class KernelCrash_KdumpPMEM(PowerNVDump):
    '''
    This test verifies kdump/fadump on pmem device.
    '''

    def setUp(self):
        super(KernelCrash_KdumpPMEM, self).setUp()

        conf = OpTestConfiguration.conf
        try: self.dev_pmem = conf.args.dev_pmem
        except AttributeError:
            log.info("Considering pmem0 as no pmem device is configured in config file.")
            self.dev_pmem = "pmem0"
        self.pmem_id = self.dev_pmem[len(self.dev_pmem)-1]

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.setup_test()
        if self.distro == "rhel":
            cmd = "yum -y install ndctl"
        elif self.distro == "sles":
            cmd = "zypper install -y ndctl"
        try:
            self.c.run_command(cmd, timeout=120)
        except CommandFailed:
            self.fail("ndctl package not available in Repository")
        if not self.c.run_command("ndctl list -Ru"):
            self.skipTest("Please configure pmem from HMC and try again.")
        try:
            self.c.run_command("ndctl create-namespace -m fsdax -r region%s" % self.pmem_id)
        except CommandFailed:
            try: self.c.run_command("ndctl destroy-namespace all -f")
            except CommandFailed: 
                self.c.run_command("umount /pmem%s" % self.pmem_id)
                self.c.run_command("ndctl destroy-namespace all -f")
                self.c.run_command("ndctl create-namespace -m fsdax -r region%s" % self.pmem_id)
        try: self.c.run_command("mkfs.xfs -f -b size=64k -s size=4k -m reflink=0 /dev/pmem%s" % self.pmem_id)
        except CommandFailed: 
            self.c.run_command("umount /pmem%s" % self.pmem_id)
            self.c.run_command("mkfs.xfs -f -b size=64k -s size=4k -m reflink=0 /dev/pmem%s" % self.pmem_id)
        self.c.run_command("mkdir -p /pmem%s" % self.pmem_id)
        self.c.run_command("mount -o dax /dev/pmem%s /pmem%s" % (self.pmem_id, self.pmem_id))
        self.c.run_command("echo '/dev/pmem%s /pmem%s                   xfs     defaults        0 0' >> /etc/fstab"
                           % (self.pmem_id, self.pmem_id))
        if self.distro == "rhel":
            self.c.run_command("echo 'add_drivers+=\"papr_scm\"' > /etc/dracut.conf.d/99-pmem-workaround.conf")
            self.c.run_command("sed -i 's/path \/var\/crash/path \/pmem%s/' /etc/kdump.conf; sync" % self.pmem_id)
            self.c.run_command("kdumpctl restart", timeout=120)
        if self.distro == "sles":
            self.c.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"/pmem%s\"\' /etc/sysconfig/kdump;' % self.pmem_id)
            self.c.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync")
        log.info("=============== Testing kdump/fadump over pmem ===============")
        boot_type = self.kernel_crash()
        self.c.run_command("cp -r /pmem%s/* /var/crash" % self.pmem_id)
        self.c.run_command("umount /pmem%s" % self.pmem_id)
        self.c.run_command("ndctl destroy-namespace all -f")
        self.c.run_command("sed -i '$d' \/etc\/fstab")
        if self.distro == "rhel":
            self.c.run_command("sed -i 's/path \/pmem%s/path \/var\/crash/' /etc/kdump.conf; sync" % self.pmem_id)
        if self.distro == "sles":
            self.c.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"/var/crash\"\' /etc/sysconfig/kdump;')
        self.verify_dump_file(boot_type)


class KernelCrash_FadumpNocma(PowerNVDump):

    # This test verifies fadump with nocma.

    def runTest(self):
        obj = OpTestInstallUtil.InstallUtil()
        if not obj.update_kernel_cmdline(self.distro, args="fadump=nocma", reboot=True, reboot_cmd=True):
            self.fail("KernelArgTest failed to update kernel args")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.setup_test()
        log.info("=============== Testing fadump with nocma ===============")
        boot_type = self.kernel_crash()
        self.verify_dump_file(boot_type)
        if self.distro == "rhel":
            if not obj.update_kernel_cmdline(self.distro, args="fadump=on", reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")
        if self.distro == "sles":
            if not obj.update_kernel_cmdline(self.distro, remove_args="fadump=nocma", reboot=True, reboot_cmd=True):
                self.fail("KernelArgTest failed to update kernel args")

class KernelCrash_KdumpSoftlockup(PowerNVDump):

    '''
    This test verifies kdump/fadump after inserting softlockup kernel module.
    '''

    def runTest(self):
        self.setup_test()
        # Make sure softlockup related file does not exist
        self.c.run_command("cd /tmp; ls -1; rm -rf soft* Makefile", timeout=60)

        #copy the source files from test_binaries to /tmp
        self.cv_HOST.copy_test_file_to_host("softlockup.c")
        self.cv_HOST.copy_test_file_to_host("Makefile")
       
        #compile source files to get kernel modules
        self.c.run_command("cd /tmp; make", timeout=60)
        
        #Enable softlockup
        self.c.run_command("sysctl -w kernel.softlockup_panic=1")

        boot_type = self.kernel_crash(crash_type="softlockup")
        self.verify_dump_file(boot_type)

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_OnlyKdumpEnable())
    s.addTest(KernelCrash_KdumpSMT())
    s.addTest(KernelCrash_KdumpSSH())
    s.addTest(KernelCrash_KdumpNFS())
    s.addTest(KernelCrash_KdumpSAN())
    s.addTest(KernelCrash_KdumpDLPAR())
    s.addTest(KernelCrash_KdumpWorkLoad())
    s.addTest(KernelCrash_hugepage_checks())
    s.addTest(KernelCrash_XIVE_off())
    s.addTest(KernelCrash_disable_radix())
    s.addTest(KernelCrash_KdumpPMEM())
    s.addTest(OpTestMakedump())
    s.addTest(KernelCrash_FadumpEnable())
    s.addTest(KernelCrash_KdumpSMT())
    s.addTest(KernelCrash_KdumpSSH())
    s.addTest(KernelCrash_KdumpNFS())
    s.addTest(KernelCrash_KdumpSAN())
    s.addTest(KernelCrash_KdumpDLPAR())
    s.addTest(KernelCrash_KdumpWorkLoad())
    s.addTest(KernelCrash_hugepage_checks())
    s.addTest(KernelCrash_XIVE_off())
    s.addTest(KernelCrash_disable_radix())
    s.addTest(KernelCrash_KdumpPMEM())
    s.addTest(KernelCrash_FadumpNocma())
    s.addTest(OpTestMakedump())
    s.addTest(KernelCrash_DisableAll())
    s.addTest(SkirootKernelCrash())
    s.addTest(OPALCrash_MPIPL())
    s.addTest(KernelCrash_KdumpSoftlockup())

    return s
