#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestIPMIPowerControl.py $
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

#  @package OpTestIPMIPowerControl.py
#  It will test below system power control operations
#  Power OFF/ON/CYCLE/SOFT/RESET

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


class OpTestIPMIPowerControl():
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
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_lparip,
                         i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This function will test below system power control operations
    #        IPMI Power ON
    #             Power OFF
    #             Power Soft
    #             Power Cycle
    #             Power Reset
    #        So each operation is executed through ipmi commands. and
    #        check_system_status function will check whether FW and Host OS
    #        Boot completed or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def testIPMIPowerControl(self):

        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.check_system_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        print "Performing a IPMI Soft Power OFF Operation"
        # Perform a IPMI Soft Power OFF Operation(Graceful shutdown)
        self.cv_IPMI.ipmi_power_soft()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        print "Perform a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.check_system_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        print "Performing a IPMI Power Cycle(Soft reboot) Operation "
        # Perform a IPMI Power Cycle(Soft reboot) Operation only when system is in ON state
        self.cv_IPMI.ipmi_power_cycle()
        self.check_system_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        print "Performing a IPMI Power Hard Reset Operation"
        # Perform a IPMI Power Hard Reset Operation
        self.cv_IPMI.ipmi_power_reset()
        self.check_system_status()
        self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def check_system_status(self):
        if int(self.cv_SYSTEM.sys_ipl_wait_for_working_state()) == 0:
            print "System booted to working state"
        else:
            l_msg = "System failed to boot"
            raise OpTestError(l_msg)
        if int(self.cv_SYSTEM.sys_wait_for_os_boot_complete()) == 0:
            print "System booted to Host OS"
        else:
            l_msg = "System failed to boot Host OS"
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS
