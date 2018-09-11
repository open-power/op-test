#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSystemBootSequence.py $
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

#  @package OpTestSystemBootSequence.py
#  It will test below system boot sequence operations
#  Mc cold reset boot sequence.
#   @ Power off state (and auto reboot policy should be off)
#   1) Make sure BMC is pinging
#   2) Issue Cold reset to BMC   =>   ipmitool <...> mc reset cold
#   3) Ensure BMC stops pinging, wait until BMC fully boots
#   4) Open network sol console =>                  ipmitool <...> sol activate
#   5) Power on system   =>   ipmitool <...> chassis power on
#   Make sure boots to Host OS, SOL fine
#
#  Mc warm reset boot sequence
#   @ Power off state (and auto reboot policy should be off)
#   1) Make sure BMC is pinging
#   2) Issue warm reset to BMC   =>   ipmitool <...> mc reset warm
#   3) Ensure BMC stops pinging, wait until BMC fully boots
#   4) Open network sol console =>                  ipmitool <...> sol activate
#   5) Power on system   =>   ipmitool <...> chassis power on
#   Make sure boots to Host OS, SOL fine

import time
import subprocess
import commands
import re
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class OpTestSystemBootSequence(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.util = self.cv_SYSTEM.util
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        # Reset the system power policy back to "always-off" at the end of test
        self.cv_IPMI.ipmi_set_power_policy("always-off")

class ColdReset_IPL(OpTestSystemBootSequence):

    ##
    # @brief This function will test mc cold reset boot sequence
    #        It has below steps
    #        1. Do a system Power OFF(Host should go down)
    #        2. Set auto reboot policy to off(chassis policy always-off)
    #        3. Issue a BMC Cold reset.
    #        4. After BMC comes up, Issue a Power ON of the system
    #        5. Check for system status and gather OPAL msg log.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        print("Testing MC Cold reset boot sequence")
        print("Performing a IPMI Power OFF Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Setting the system power policy to always-off")
        self.cv_IPMI.ipmi_set_power_policy("always-off")

        # Perform a BMC Cold Reset Operation
        self.cv_IPMI.ipmi_cold_reset()

        print("Performing a IPMI Power ON Operation")
        # Perform a IPMI Power ON Operation
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

class WarmReset_IPL(OpTestSystemBootSequence):

    ##
    # @brief This function will test mc warm reset boot sequence
    #        It has below steps
    #        1. Do a system Power OFF(Host should go down)
    #        2. Set auto reboot policy to off(chassis policy always-off)
    #        3. Issue a BMC Warm reset.
    #        4. After BMC comes up, Issue a Power ON of the system
    #        5. Check for system status and gather OPAL msg log.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        print("Testing MC Warm reset boot sequence")
        print("Performing a IPMI Power OFF Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Setting the system power policy to always-off")
        self.cv_IPMI.ipmi_set_power_policy("always-off")

        # Perform a BMC Warm Reset Operation
        self.cv_IPMI.ipmi_warm_reset()

        print("Performing a IPMI Power ON Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

class PowerPolicyOFF_IPL(OpTestSystemBootSequence):

    ##
    # @brief This function will test system auto reboot policy always-off.
    #        It has below steps
    #        1. Do a system Power OFF(Host should go down)
    #        2. Set auto reboot policy to off(chassis policy always-off)
    #        3. Issue a BMC Cold reset.
    #        4. After BMC comes up, expect the system to not boot.
    #        5. Issue a Power ON of the system
    #        6. Check for system status and gather OPAL msg log.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        print("Testing System Power Policy:always-off")
        print("Performing a IPMI Power OFF Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Setting the system power policy to always-off")
        self.cv_IPMI.ipmi_set_power_policy("always-off")

        fail = False
        l_msg = ""
        # Perform a BMC Cold Reset Operation
        if int(self.cv_SYSTEM.sys_cold_reset_bmc()) == BMC_CONST.FW_SUCCESS:
            print("System auto reboot policy for always-off works as expected")
            print("System Power status not changed")
            print("Performing a IPMI Power ON Operation")
            # Perform a IPMI Power ON Operation
            self.cv_IPMI.ipmi_power_on()
        else:
            print("Power restore policy failed")
            fail = True
            l_msg = "IPLTest: chassis policy always-off making the system to auto boot"
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.assertFalse(fail, l_msg)

class PowerPolicyON_IPL(OpTestSystemBootSequence):

    ##
    # @brief This function will test system auto reboot policy always-on.
    #        It has below steps
    #        1. Do a system Power OFF(Host should go down)
    #        2. Set auto reboot policy to on(chassis policy always-on)
    #        3. Issue a BMC Cold reset.
    #        4. After BMC comes up, Here expect the system to boot,
    #           If not power policy is not working as expected
    #        5. Check for system status and gather OPAL msg log.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        print("Testing System Power Policy:Always-ON")
        print("Performing a IPMI Power OFF Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Setting the system power policy to always-on")
        self.cv_IPMI.ipmi_set_power_policy("always-on")

        fail = False
        l_msg = ""
        # Perform a BMC Cold Reset Operation
        if int(self.cv_SYSTEM.sys_cold_reset_bmc()) == BMC_CONST.FW_FAILED:
            print("System auto reboot policy for always-on works as expected")
            print("System Power status changed as expected")
        else:
            print("Power restore policy failed")
            fail = True
            l_msg = "IPLTest: chassis policy always-on making the system not to auto boot"
            print("Performing a IPMI Power ON Operation")
            # Perform a IPMI Power ON Operation
            self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.assertFalse(fail, l_msg)

class PowerPolicyPrevious_IPL(OpTestSystemBootSequence):

    ##
    # @brief This function will test system auto reboot policy previous
    #        It has below steps
    #        1. Do a system Power OFF(Host should go down)
    #        2. Set auto reboot policy to previous(chassis policy previous)
    #        3. Issue a BMC Cold reset.
    #        4. After BMC comes up, system power status will change based on
    #           previous power status before issuing cold reset.
    #        5. Check for system status and gather OPAL msg log.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        print("Testing System Power Policy:previous")
        print("Performing a IPMI Power OFF Operation")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Setting the system power policy to previous")
        self.cv_IPMI.ipmi_set_power_policy("previous")
        fail = False
        l_msg = ""
        # Perform a BMC Cold Reset Operation
        if int(self.cv_SYSTEM.sys_cold_reset_bmc()) == BMC_CONST.FW_SUCCESS:
            print("System auto reboot policy for previous works as expected")
            print("System Power status not changed")
            print("Performing a IPMI Power ON Operation")
            # Perform a IPMI Power ON Operation
            self.cv_IPMI.ipmi_power_on()
        else:
            print("Power restore policy failed")
            fail = True
            l_msg = "IPLTest: chassis policy previous making the system to auto boot"
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.assertFalse(fail, l_msg)

        print("Gathering the OPAL msg logs")
        self.cv_HOST.host_gather_opal_msg_log()
        # Perform a BMC Cold Reset Operation
        if int(self.cv_SYSTEM.sys_cold_reset_bmc()) == BMC_CONST.FW_SUCCESS:
            print("System auto reboot policy for previous works as expected")
            print("System Power status not changed")
        else:
            print("Power restore policy previous failed")
            l_msg = "IPLTest: chassis policy previous making the system to change power status"
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            raise l_msg

def suite():
    s = unittest.TestSuite()
    s.addTest(ColdReset_IPL())
    s.addTest(WarmReset_IPL())
    s.addTest(PowerPolicyOFF_IPL())
    s.addTest(PowerPolicyON_IPL())
    s.addTest(PowerPolicyPrevious_IPL())
    return s
