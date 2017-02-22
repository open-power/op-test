#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestOCC.py $
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

# @package OpTestOCC
#  OCC Control package for OpenPower testing.
#
#  This class will test the functionality of following.
#  1. OCC Reset\Enable\Disable

import time
import subprocess
import re
import sys
import os
import random

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestOCC():
    ## Initialize this object
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
    # @brief This function is used to test OCC Reset funtionality in BMC based systems.
    #        OCC Reset reload is limited to 3 times per full power cycle.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_reset_functionality(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        print "Performing a IPMI Power OFF Operation"
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            #raise OpTestError(l_msg)
        print "OPAL-PRD: OCC Enable"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_ENABLE)
        print "OPAL-PRD: OCC DISABLE"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_DISABLE)
        print "OPAL-PRD: OCC RESET"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_RESET)
        time.sleep(60)
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            #raise OpTestError(l_msg)
        print "OPAL-PRD: OCC Enable"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_ENABLE)
        print "OPAL-PRD: OCC DISABLE"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_DISABLE)
        print "OPAL-PRD: OCC RESET"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_RESET)
        time.sleep(60)
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            #raise OpTestError(l_msg)
        print "OPAL-PRD: OCC Enable"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_ENABLE)
        print "OPAL-PRD: OCC DISABLE"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_DISABLE)
        print "OPAL-PRD: OCC RESET"
        self.cv_HOST.host_run_command(BMC_CONST.OCC_RESET)
        time.sleep(60)
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state, rebooting the system"
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to test OCC Reset funtionality in BMC based systems.
    #        OCC Reset reload can be done more than 3 times per full power cycle, by
    #        resetting OCC resetreload count.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_reset_n_times(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state after rebooting"
            raise OpTestError(l_msg)

        for i in range(1, BMC_CONST.OCC_RESET_RELOAD_COUNT):
            print "*******************OCC Reset count %d*******************" % i
            print "OPAL-PRD: OCC Enable"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_ENABLE)
            print "OPAL-PRD: OCC DISABLE"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_DISABLE)
            print "OPAL-PRD: OCC RESET"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_RESET)
            time.sleep(60)
            if self.check_occ_status() == BMC_CONST.FW_FAILED:
                l_msg = "OCC's are not in active state"
                raise OpTestError(l_msg)
            print "OPAL-PRD: occ query reset reload count"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)
            print "OPAL-PRD: occ reset reset/reload count"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_SET_RESET_RELOAD_COUNT)
            print "OPAL-PRD: occ query reset reload count"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)

        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state after rebooting"
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to test OCC Enable and Disable funtionality in BMC based systems.
    #        There is no limit for occ enable and disable, as of now doing 10 times in a loop.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_enable_disable_functionality(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        for count in range(1,10):
            print "OPAL-PRD: OCC Enable"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_ENABLE)
            print "OPAL-PRD: OCC Disable"
            self.cv_HOST.host_run_command(BMC_CONST.OCC_DISABLE)
            time.sleep(60)
            if self.check_occ_status() == BMC_CONST.FW_FAILED:
                l_msg = "OCC's are not in active state"
                #raise OpTestError(l_msg)
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_SYSTEM.sys_hard_reboot()
        if self.check_occ_status() == BMC_CONST.FW_FAILED:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to get OCC status enable/disable.
    #
    # @return BMC_CONST.FW_SUCCESS - OCC's are active or 
    #         BMC_CONST.FW_FAILED  - OCC's are not in active state
    #
    def check_occ_status(self):
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
            return BMC_CONST.FW_SUCCESS
        else:
            print "OCC's are not in active state"
            return BMC_CONST.FW_FAILED
