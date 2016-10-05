#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEM.py $
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

#  @package OpTestEM
#  Energy Management package for OpenPower testing.
#
#  This class will test the functionality of following drivers
#  1. powernv cpuidle driver
#  2. powernv cpufreq driver

import time
import subprocess
import re
import random

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpTestSystem


class OpTestEM():
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
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This function will cover following test steps
    #        1. It will get the OS and kernel versions.
    #        2. Check the cpupower utility is available in host.
    #        3. Get available cpu scaling frequencies
    #        4. Set the userspace governer for all cpu's
    #        5. test the cpufreq driver by set/verify cpu frequency
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_cpu_freq_states(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        self.cv_HOST.host_check_command("cpupower")
        # Get available cpu scaling frequencies
        l_res = self.cv_HOST.host_run_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies")
        freq_list = (l_res.strip()).split(' ')
        print freq_list

        # Set the cpu governer to userspace
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        for i in range(1, 100):
            i_freq = random.choice(freq_list)
            self.set_cpu_freq(i_freq)
            self.verify_cpu_freq(i_freq)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will cover following test steps
    #        1. It will get the OS and kernel versions.
    #        2. Check the cpupower utility is available in host.
    #        3. Set the userspace governer for all cpu's
    #        4. test the cpuidle driver by enable/disable/verify the idle states
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_cpu_idle_states(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        self.cv_HOST.host_check_command("cpupower")
        # currently p8 cpu has 3 states
        for i in (0, 1, 2):
            self.enable_idle_state(i)
            self.verify_enable_idle_state(i)
        for i in (0, 1, 2):
            self.disable_idle_state(i)
            self.verify_disable_idle_state(i)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief sets the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency of cpu to be set
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def set_cpu_freq(self, i_freq):
        l_cmd = "cpupower frequency-set -f %s" % i_freq
        self.cv_HOST.host_run_command(l_cmd)

    ##
    # @brief verify the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency to be verified with cpu frequency
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def verify_cpu_freq(self, i_freq):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.cv_HOST.host_run_command(l_cmd)
        if cur_freq.strip() == i_freq:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "CPU frequency not changed to %s" % i_freq
            raise OpTestError(l_msg)

    ##
    # @brief sets the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be set for all cpu's
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def set_cpu_gov(self, i_gov):
        l_cmd = "cpupower frequency-set -g %s" % i_gov
        self.cv_HOST.host_run_command(l_cmd)

    ##
    # @brief verify the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be verified with cpu governer
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def verify_cpu_gov(self, i_gov):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        cur_gov = self.cv_HOST.host_run_command(l_cmd)
        if cur_gov.strip() == i_gov:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "CPU governor not changed to %s" % i_gov
            raise OpTestError(l_msg)

    ##
    # @brief enable cpu idle state i_idle
    #
    # @param i_idle @type str: this is the cpu idle state to be enabled
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def enable_idle_state(self, i_idle):
        l_cmd = "cpupower idle-set -e %s" % i_idle
        self.cv_HOST.host_run_command(l_cmd)

    ##
    # @brief disable cpu idle state i_idle
    #
    # @param i_idle @type str: this is the cpu idle state to be disabled
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def disable_idle_state(self, i_idle):
        l_cmd = "cpupower idle-set -d %s" % i_idle
        self.cv_HOST.host_run_command(l_cmd)

    ##
    # @brief verify whether cpu idle state i_idle enabled
    #
    # @param i_idle @type str: this is the cpu idle state to be verified for enable
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def verify_enable_idle_state(self, i_idle):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.cv_HOST.host_run_command(l_cmd)
        if cur_value.strip() == "0":
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "CPU state%s not enabled" % i_idle
            raise OpTestError(l_msg)

    ##
    # @brief verify whether cpu idle state i_idle disabled
    #
    # @param i_idle @type str: this is the cpu idle state to be verified for disable
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def verify_disable_idle_state(self, i_idle):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.cv_HOST.host_run_command(l_cmd)
        if cur_value.strip() == "1":
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "CPU state%s not disabled" % i_idle
            raise OpTestError(l_msg)
