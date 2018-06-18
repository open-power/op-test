#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestKernel.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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

#  @package OpTestKernel.py
#  This module can contain testcases related to FW & Kernel Interactions.
#   Ex: 1. Trigger a kernel crash(Both by enabling and disabling the kdump)
#       2. Check Firmware boot progress

import time
import subprocess
import commands
import re
import sys
import pexpect

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.Exceptions import KernelOOPS, KernelCrashUnknown, KernelKdump

class OpTestKernelBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util

    ##
    # @brief This function will test the kernel crash followed by system
    #        reboot. it has below steps
    #        1. Enable reboot on kernel panic: echo 10  > /proc/sys/kernel/panic
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def kernel_crash(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console()
	self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        console.run_command("cat /etc/os-release")
        console.run_command("nvram -p ibm,skiboot --update-config fast-reset=0")
        console.run_command("echo 10  > /proc/sys/kernel/panic")
        console.sol.sendline("echo c > /proc/sysrq-trigger")
        done = False
        rc = -1
        # TODO: We may need to move this kdump expect path to OPexpect wrapper
        # so that in real kernel crashes we can track kdump vmcore collection as well
        while not done:
            try:
                rc = console.sol.expect(['ISTEP', "kdump: saving vmcore complete"], timeout=300)
            except KernelOOPS:
                # if kdump is disabled, system should IPL after kernel crash(oops)
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
            except KernelKdump:
                print "Kdump kernel started booting, waiting for dump to finish"
            except KernelCrashUnknown:
                self.cv_SYSTEM.goto_state(OpSystemState.OFF)
                done = True
            if rc == 0:
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                done = True
            if rc == 1:
                print "Kdump finished collecting vmcore, waiting for IPL to start"

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.cv_HOST.ssh.state = SSHConnectionState.DISCONNECTED
        print "System booted fine to host OS..."
        return BMC_CONST.FW_SUCCESS

class KernelCrash_KdumpEnable(OpTestKernelBase):

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()

    ##
    # @brief This function will test the kernel crash followed by crash kernel dump
    #        and subsequent system IPL
    #        1. Make sure kdump service is started before test
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for crash kernel boot followed full system IPL
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        self.setup_test()
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        self.kernel_crash()

class KernelCrash_KdumpDisable(OpTestKernelBase):

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()

    ##
    # @brief This function will test the kernel crash followed by system IPL
    #        1. Make sure kdump service is stopped before test
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for system booting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        self.setup_test()
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_disable_kdump_service(os_level)
        self.kernel_crash()

class SkirootKernelCrash(OpTestKernelBase, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
        output = self.c.run_command("cat /proc/cmdline")
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
