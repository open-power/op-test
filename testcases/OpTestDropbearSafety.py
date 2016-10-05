#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDropbearSafety.py $
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
#
#  @package OpTestDropbearSafety.py
#
#   Test Dropbear SSH is not present in skiroot
#
# The skiroot (pettiboot environment) firmware contains dropbear for it's ssh
# client functioanlity. We do not want to enable network accessable system in
# the environemnt for security reasons.
#
# This test ensures that the ssh server is not running at boot

import time
import subprocess
import commands
import re
import sys

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestDropbearSafety():
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
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This function will tests Dropbear running functionality in skiroot
    #         1. Power Off the system
    #         2. Power on the system
    #         3. Exit to the petitboot shell
    #         4. Execute ps command
    #         5. test will fail incase dropbear is running and listed out by ps
    #         6. At the end of test reboot the system to OS.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_dropbear_running(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        print "Test Dropbear running in Petitboot"
        print "Performing IPMI Power Off Operation"
        try:
            # Perform a IPMI Power OFF Operation(Immediate Shutdown)
            self.cv_IPMI.ipmi_power_off()
            if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
                print "System is in standby/Soft-off state"
            else:
                l_msg = "System failed to reach standby/Soft-off state"
                raise OpTestError(l_msg)
            self.cv_IPMI.ipmi_power_on()
            self.console = self.cv_SYSTEM.sys_get_ipmi_console()

            # Exiting to petitboot shell
            self.console.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
            # Exiting to petitboot
            self.console.sendcontrol('l')
            self.console.send('\x1b[B')
            self.console.send('\x1b[B')
            self.console.send('\r')
            self.console.expect('Exiting petitboot')
            self.console.send('\r')
            self.console.send('\x08')
            self.cv_IPMI.ipmi_host_set_unique_prompt(self.console)
            self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
            res = self.cv_IPMI.run_host_cmd_on_ipmi_console("ps")
            if res[-1] == '0':
                print 'ps command worked'
            else:
                raise OpTestError('failed to run ps command')

        except OpTestError:
            self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        print res
        for line in res:
            if line.count('dropbear'):
                raise OpTestError("drobear is running in the skiroot")
        return BMC_CONST.FW_SUCCESS
