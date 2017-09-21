#!/usr/bin/python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestIPMIReprovision.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2016
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

#  @package OpTestIPMIReprovision
#  Reset\Reprovision to default package for OpenPower testing.
#
#  This class will test the functionality of following Reset\Reprovision to default tests.
#  1. NVRAM Partition - IPMI Reprovision.
#  2. GARD Partition - IPMI Reprovision.


import time
import subprocess
import re

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

class OpTestIPMIReprovision(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()
        self.platform = conf.platform()

class NVRAM(OpTestIPMIReprovision):
    ##
    # @brief This function will cover following test steps
    #        Testcase: NVRAM Partition-IPMI Reprovision
    #        1. Update NVRAM config data with test config data
    #           i.e "nvram --update-config test-name=test-value"

    #        2. Issue an IPMI PNOR Reprovision request command, to reset NVRAM partition to default.
    #        3. Wait for PNOR Reprovision progress to complete(00).
    #        4. Do a Hard reboot(Power OFF/ON) to avoid nvram cache data.
    #        5. Once system booted, check for NVRAM parition whether the test config data
    #           got erased or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if not self.platform in ['habanero','firestone','garrison']:
            raise unittest.SkipTest("Platform %s doesn't support IPMI Reprovision" % self.platform)

        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        self.cv_HOST.host_check_command("ipmitool")
        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # loading below ipmi modules based on config option
        # ipmi_devintf, ipmi_powernv and ipmi_masghandler
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_DEVICE_INTERFACE,
                                                      BMC_CONST.IPMI_DEV_INTF)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_POWERNV,
                                                      BMC_CONST.IPMI_POWERNV)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_HANDLER,
                                                      BMC_CONST.IPMI_MSG_HANDLER)


        self.cv_HOST.host_run_command("uname -a")
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        print "IPMI_Reprovision: Updating the nvram partition with test cfg data"
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_UPDATE_CONFIG_TEST_DATA)
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        print "IPMI_Reprovision: issuing ipmi pnor reprovision request"
        self.cv_SYSTEM.sys_issue_ipmi_pnor_reprovision_request()
        print "IPMI_Reprovision: wait for reprovision to complete"
        self.cv_SYSTEM.sys_wait_for_ipmi_pnor_reprovision_to_complete()
        print "IPMI_Reprovision: gathering the opal message logs"
        self.cv_HOST.host_gather_opal_msg_log()
        print "IPMI_Reprovision: Performing a IPMI Power OFF Operation"

        # Power cycle
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        l_res = self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        if l_res.__contains__(BMC_CONST.NVRAM_TEST_DATA):
            l_msg = "NVRAM Partition - IPMI Reprovision not happening, nvram test config data still exists"
            raise OpTestError(l_msg)
        print "NVRAM Partition - IPMI Reprovision is done, cleared the nvram test config data"
        self.cv_HOST.host_gather_opal_msg_log()
        return

class GARD(OpTestIPMIReprovision):
    ##
    # @brief This function will cover following test steps
    #        Testcase: GARD Partition-IPMI Reprovision
    #        1. Inject core checkstop using existed function from OpTestHMIHandling.py
    #        2. Do a Hard reboot(IPMI Power OFF/ON)
    #        2. Issue an IPMI PNOR Reprovision request command, to reset GUARD partition to default.
    #        3. Wait for IPMI PNOR Reprovision progress to complete(00).
    #        4. Check for GUARD parition whether the existing gard records erased or not.
    #        6. Reboot the system back to see system is booting fine or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if not self.platform in ['habanero','firestone','garrison']:
            raise unittest.SkipTest("Platform %s doesn't support IPMI Reprovision" % self.platform)

        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        print "IPMI_Reprovision: Injecting system core checkstop to guard the phyisical cpu"
        self.opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_MALFUNCTION_ALERT)

        print "IPMI_Reprovision: Performing a IPMI Power OFF Operation"
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print "IPMI_Reprovision: Performing a IPMI Power ON Operation"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        print "IPMI_Reprovision: issuing ipmi pnor reprovision request"
        self.cv_SYSTEM.sys_issue_ipmi_pnor_reprovision_request()
        print "IPMI_Reprovision: wait for reprovision to complete"
        self.cv_SYSTEM.sys_wait_for_ipmi_pnor_reprovision_to_complete()
        print "IPMI_Reprovision: gathering the opal message logs"
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_get_OS_Level()
        g = self.cv_HOST.host_run_command("PATH=/usr/local/sbin:$PATH opal-gard list")
        if "No GARD entries to display" not in g:
            raise Exception("IPMI: Reprovision not happening, gard records are not erased")


def experimental_suite():
    s = unittest.TestSuite()
    s.addTest(NVRAM())
    return s

def broken_suite():
    s = unittest.TestSuite()
    s.addTest(GARD())
    return s
