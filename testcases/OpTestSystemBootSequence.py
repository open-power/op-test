#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestSystemBootSequence.py $
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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestLpar import OpTestLpar
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestSystemBootSequence():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_lparip, i_lparuser, i_lparPasswd)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd, i_bmcIP, i_ffdcDir)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_lparip,
                         i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

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
    def testMcColdResetBootSequence(self):

        print "Testing MC Cold reset boot sequence"
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print "Setting the system power policy to always-off"
        self.cv_IPMI.ipmi_set_power_policy("always-off")

        # Perform a BMC Cold Reset Operation
        self.cv_IPMI.ipmi_cold_reset()

        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_IPMI.clear_ssh_keys(self.cv_LPAR.ip)

        print "Gathering the OPAL msg logs"
        self.cv_LPAR.lpar_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS

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
    def testMcWarmResetBootSequence(self):
        print "Testing MC Warm reset boot sequence"
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print "Setting the system power policy to always-off"
        self.cv_IPMI.ipmi_set_power_policy("always-off")

        # Perform a BMC Warm Reset Operation
        self.cv_IPMI.ipmi_warm_reset()

        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_IPMI.clear_ssh_keys(self.cv_LPAR.ip)

        print "Gathering the OPAL msg logs"
        self.cv_LPAR.lpar_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS
