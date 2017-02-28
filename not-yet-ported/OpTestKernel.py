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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestKernel():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, host=self.cv_HOST)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This function will test the kernel crash followed by system
    #        reboot. it has below steps
    #        1. Enable reboot on kernel panic: echo 10  > /proc/sys/kernel/panic
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_kernel_crash(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
	self.cv_SYSTEM.host_console_unique_prompt()
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("echo 10  > /proc/sys/kernel/panic")
        l_con.sendline("echo c > /proc/sysrq-trigger")
        try:
            l_con.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
            self.cv_IPMI.ipmi_close_console(l_con)
        except pexpect.EOF:
            print "Waiting for system to IPL...."
        except pexpect.TIMEOUT:
            raise OpTestError("System failed to reach Petitboot")
        self.cv_SYSTEM.sys_check_host_status_v1()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        print "System booted fine to host OS..."
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will test the kernel crash followed by crash kernel dump
    #        and subsequent system IPL
    #        1. Make sure kdump service is started before test
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for crash kernel boot followed full system IPL
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_kernel_crash_kdump_enable(self):
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_enable_kdump_service(os_level)
        self.test_kernel_crash()

    ##
    # @brief This function will test the kernel crash followed by system IPL
    #        1. Make sure kdump service is stopped before test
    #        2. Trigger kernel crash: echo c > /proc/sysrq-trigger
    #        3. Check for system booting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_kernel_crash_kdump_disable(self):
        self.cv_HOST.host_check_command("kdump")
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_disable_kdump_service(os_level)
        self.test_kernel_crash()
