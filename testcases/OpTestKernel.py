#!/usr/bin/python
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


class OpTestKernelBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.cv_SYSTEM.goto_state(OpSystemState.OS)


    ##
    # @brief This function will test the kernel crash followed by system
    #        reboot. it has below steps
    #        1. Enable reboot on kernel panic: echo 10  > /proc/sys/kernel/panic
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def kernel_crash(self):
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
	self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        console.run_command("cat /etc/os-release")
        console.run_command("echo 10  > /proc/sys/kernel/panic")
        console.sol.sendline("echo c > /proc/sysrq-trigger")
        try:
            console.sol.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
            console.close()
        except pexpect.EOF:
            print "Waiting for system to IPL...."
        except pexpect.TIMEOUT:
            raise OpTestError("System failed to reach Petitboot")
        # Seeing an issue here autoboot is disabling, stops at petitboot(It will effect other tests to fail)
        # TODO: Remove this extra IPL it is not necessary.
        try:
            self.cv_SYSTEM.sys_check_host_status_v1()
        except OpTestError:
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)

        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        print "System booted fine to host OS..."
        return BMC_CONST.FW_SUCCESS

class KernelCrash_KdumpEnable(OpTestKernelBase):

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
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_enable_kdump_service(os_level)
        self.kernel_crash()

class KernelCrash_KdumpDisable(OpTestKernelBase):

    ##
    # @brief This function will test the kernel crash followed by system IPL
    #        1. Make sure kdump service is stopped before test
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for system booting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        self.cv_HOST.host_disable_kdump_service(os_level)
        self.kernel_crash()

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_KdumpEnable())
    s.addTest(KernelCrash_KdumpDisable())
    return s
