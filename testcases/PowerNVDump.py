#!/usr/bin/python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/PowerNVDump.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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
#  This module can contain testcases related to FW & Kernel interaction features
#  like kdump, fadump and MPIPL etc.
#
#   fadump:
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
#   1. Enable both fadump and kdump - trigger a kernel crash
#   2. Enable only kdump - trigger a kernel crash
#   3. Disable both - trigger kernel crash
#   And verify boot progress and collected dump components(vmcore and opalcore)
#

import time
import commands
import re
import os
import sys
import pexpect

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.Exceptions import KernelOOPS, KernelCrashUnknown, KernelKdump, KernelFADUMP, PlatformError, CommandFailed, SkibootAssert

OPAL_MSG_LOG = "cat /sys/firmware/opal/msglog"
PROC_CMDLINE = "cat /proc/cmdline"
OPAL_DUMP_NODE = "/proc/device-tree/ibm,opal/dump/"

class BootType():
    NORMAL = 1
    MPIPL = 2
    KDUMPKERNEL = 3
    INVALID = 4

class PowerNVDump(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_BMC = conf.bmc()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.pdbg = conf.args.pdbg
        self.basedir = conf.basedir

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def is_fadump_param_enabled(self):
        res = self.cv_HOST.host_run_command(PROC_CMDLINE)

        if "fadump=on" in " ".join(res):
            return True

        return False

    def is_fadump_enabled(self):
        res = self.c.run_command("cat /sys/kernel/fadump_enabled")[-1]
        if int(res) == 1:
            return True
        elif int(res) == 0:
            return False
        else:
            raise Exception("Unknown fadump_enabled value")

    def is_fadump_supported(self):
        try:
            self.c.run_command("ls /sys/kernel/fadump_enabled")
            return True
        except CommandFailed:
            return False

    def is_mpipl_supported(self):
        try:
            self.c.run_command("ls %s" % OPAL_DUMP_NODE)
            return True
        except CommandFailed:
            return False

    def verify_dump_dt_node(self, boot_type=BootType.NORMAL):
        self.c.run_command_ignore_fail("lsprop  %s" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/fw-source-table" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/compatible" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/name" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/phandle" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/fw-load-area" % OPAL_DUMP_NODE)
        self.c.run_command("ls %s/cpu-data-version" % OPAL_DUMP_NODE)
        if boot_type == BootType.MPIPL:
            self.c.run_command("ls %s/result-table" % OPAL_DUMP_NODE)

    def verify_fadump_reg(self):
        res = self.c.run_command("cat /sys/kernel/fadump_registered")[-1]
        if int(res) == 1:
            self.c.run_command("echo 0 > /sys/kernel/fadump_registered")

        self.c.run_command("dmesg > /tmp/dmesg_log")
        self.c.run_command("%s > /tmp/opal_log" % OPAL_MSG_LOG)
        self.c.run_command("echo 1 > /sys/kernel/fadump_registered")

        opal_data = " ".join(self.c.run_command_ignore_fail("%s | diff -a /tmp/opal_log -" % OPAL_MSG_LOG))
        if "FADUMP: Payload registered for MPIPL" in opal_data:
            print "OPAL: Payload registered successfully for MPIPL"
        else:
            raise OpTestError("Payload failed to register for MPIPL")

        dmesg_data = " ".join(self.c.run_command_ignore_fail("dmesg | diff -a /tmp/dmesg_log -"))
        if "powernv fadump: Registration is successful!" in dmesg_data:
            print "Kernel powernv fadump registration successful"
        else:
            raise OpTestError("Kernel powernv fadump registration failed")


    def verify_fadump_unreg(self):
        res = self.c.run_command("cat /sys/kernel/fadump_registered")[-1]
        if int(res) == 0:
            self.c.run_command("echo 1 > /sys/kernel/fadump_registered")

        self.c.run_command("%s > /tmp/opal_log" % OPAL_MSG_LOG)
        self.c.run_command("echo 0 > /sys/kernel/fadump_registered")

        opal_data = " ".join(self.c.run_command_ignore_fail("%s | diff -a /tmp/opal_log -" % OPAL_MSG_LOG))
        if "FADUMP: Payload unregistered for MPIPL" in opal_data:
            return True
        else:
            raise OpTestError("Payload failed to unregister for MPIPL")

    ##
    # @brief This function will test the kernel crash followed by system
    #        reboot. it has below steps
    #        1. Enable reboot on kernel panic: echo 10  > /proc/sys/kernel/panic
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def kernel_crash(self):
        console = self.cv_SYSTEM.console.get_console()
        console.run_command("uname -a")
        console.run_command("cat /etc/os-release")
        # Disable fast-reboot, otherwise MPIPL may lead to fast-reboot
        console.run_command("nvram -p ibm,skiboot --update-config fast-reset=0")
        console.run_command("echo 10  > /proc/sys/kernel/panic")
        # Enable sysrq before triggering the kernel crash
        console.sendline("echo 1 > /proc/sys/kernel/sysrq")
        console.sendline("echo c > /proc/sysrq-trigger")
        done = False
        boot_type = BootType.NORMAL
        rc = -1
        while not done:
            try:
                rc = console.expect(['ISTEP', "kdump: saving vmcore complete"], timeout=300)
            except KernelFADUMP:
                print "====================MPIPL boot started======================"
                # if fadump is enabled & kdump is disabled, system should start MPIPL after kernel crash(oops)
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                boot_type = BootType.MPIPL
            except KernelOOPS:
                print "==================Normal Boot============================="
                # if both fadump and kdump is disabled, system should do normal IPL after kernel crash(oops)
                boot_type = BootType.NORMAL
            except KernelKdump:
                print "================Kdump kernel boot========================="
                # if only kdump is enabled, kdump kernel should boot after kernel crash
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
            if rc == 1:
                print "Kdump finished collecting vmcore, waiting for IPL to start"


        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        #self.cv_HOST.ssh.state = SSHConnectionState.DISCONNECTED
        print "System booted fine to host OS..."
        return boot_type

class OPALCrash_MPIPL(PowerNVDump):

    def runTest(self):
        if not self.pdbg or not os.path.exists(self.pdbg):
            self.fail("pdbg file %s doesn't exist" % self.pdbg)
        self.setup_test()
        cmd = "rm /tmp/pdbg; rm /tmp/deadbeef"
        try:
            self.cv_BMC.run_command(cmd)
        except CommandFailed:
            pass
        # copy the pdbg file to BMC
        self.cv_BMC.image_transfer(self.pdbg)
        deadbeef = os.path.join(self.basedir, "test_binaries", "deadbeef")
        self.cv_BMC.image_transfer(deadbeef)
        if "OpenBMC" in self.bmc_type:
            cmd = "/tmp/pdbg putmem 0x300000f8 < /tmp/deadbeef"
        elif "SMC" in self.bmc_type:
            cmd = "/tmp/rsync_file/pdbg putmem 0x300000f8 < /tmp/rsync_file/deadbeef"
        console = self.cv_SYSTEM.console.get_console()
        self.cv_BMC.run_command(cmd)
        #console.sendline()
        done = False
        boot_type = BootType.NORMAL
        rc = -1
        while not done:
            try:
                rc = console.expect(['\n', 'ISTEP'], timeout=300)
            except(SkibootAssert, KernelFADUMP):
                print "====================MPIPL boot started======================"
                # if fadump is enabled & kdump is disabled, system should start MPIPL after kernel crash(oops)
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
        #self.cv_HOST.ssh.state = SSHConnectionState.DISCONNECTED
        print "System booted fine to host OS..."
        return boot_type


class KernelCrash_FadumpEnable(PowerNVDump):


    def runTest(self):
        self.setup_test()
        if not self.is_mpipl_supported():
            self.skipTest("MPIPL support is not found")
        if not self.is_fadump_param_enabled():
            raise OpTestError("fadump=on not added in kernel param, please add and re-try")
        if not self.is_fadump_supported():
            raise OpTestError("fadump not enabled in the kernel, does system has right firmware!!!")
        if not self.is_fadump_enabled():
            raise OpTestError("fadump_enabled is off")
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.verify_dump_dt_node()
        self.verify_fadump_unreg()
        self.verify_fadump_reg()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        print "======================fadump is supported========================="
        boot_type = self.kernel_crash()
        if boot_type != BootType.MPIPL:
            msg = "Invalid boot %d after kernel crash instead of MPIPL" % int(boot_type)
            raise OpTestError(msg)
        self.verify_dump_dt_node(boot_type)

class KernelCrash_OnlyKdumpEnable(PowerNVDump):


    def runTest(self):
        self.setup_test()
        if self.is_fadump_supported():
            raise OpTestError("fadump is enabled, please disable(remove fadump=on \
                               kernel parameter and re-try")
        if self.is_fadump_param_enabled():
            raise OpTestError("fadump=on added in kernel param, please remove and re-try")
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        boot_type = self.kernel_crash()
        if boot_type != BootType.KDUMPKERNEL:
            msg = "Invalid boot %d after kernel crash instead of KDUMP kernel boot" % int(boot_type)
            raise OpTestError(msg)

class KernelCrash_DisableAll(PowerNVDump):


    def runTest(self):
        self.setup_test()
        if self.is_fadump_param_enabled():
            raise OpTestError("fadump=on added in kernel param, please remove and re-try")
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_disable_kdump_service(os_level)
        boot_type = self.kernel_crash()
        if boot_type != BootType.NORMAL:
            msg = "Invalid boot %d after kernel crash instead of normal boot" % int(boot_type)
            raise OpTestError(msg)


class SkirootKernelCrash(PowerNVDump, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        output = self.c.run_command(PROC_CMDLINE)
        res = ""
        found = False
        update = False
        for pair in output[0].split(" "):
            if "xmon" in pair:
                if pair == "xmon=off":
                    found = True
                    continue
                pair = "xmon=off"
                update = True
            res = "%s %s" % (res, pair)
        if found:
            return
        if not update:
            pair = "xmon=off"
            res = "%s %s" % (res, pair)
        bootargs = "\'%s\'" % res
        print bootargs
        self.c.run_command("nvram -p ibm,skiboot --update-config bootargs=%s" % bootargs)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    ##
    # @brief This tests the Skiroot kernel crash followed by system IPL
    #        1. Skiroot kernel has by default xmon is on, so made it off
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for system booting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        self.setup_test()
        self.cv_SYSTEM.sys_set_bootdev_no_override()
        self.kernel_crash()

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_KdumpEnable())
    s.addTest(KernelCrash_KdumpDisable())
    s.addTest(SkirootKernelCrash())
    return s
