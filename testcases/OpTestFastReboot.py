#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestFastReboot.py $
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
#  @package OpTestFastReboot.py
#
#   Issue fast reboot in petitboot and host OS, on a system having
#   skiboot 5.4 rc1(which has fast-reset feature). Any further tests
#   on fast-reset system will be added here
#

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


class OpTestFastReboot():
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
    # @brief  This function tests fast reset of power systems.
    #         It will check booting sequence when reboot command
    #         getting executed in both petitboot and host OS
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_opal_fast_reboot(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_SET_FAST_RESET_MODE)
        res = self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_FAST_RESET_VALUE)
        if "feeling-lucky" in res:
            print "Setting the fast-reset mode successful"
        else:
            raise OpTestError("Failed to set the fast-reset mode")
        self.con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(self.con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(self.con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.ipmi_set_boot_to_petitboot()
        self.con.sendline("reboot")
        self.con.expect(" RESET: Initiating fast reboot", timeout=60)
        # Exiting to petitboot shell
        self.con.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
        self.con.expect('x=exit', timeout=10)
        # Exiting to petitboot
        self.con.sendcontrol('l')
        self.con.send('\x1b[B')
        self.con.send('\x1b[B')
        self.con.send('\r')
        self.con.expect('Exiting petitboot')
        self.con.send('\r')
        self.con.send('\x08')
        self.cv_IPMI.ipmi_host_set_unique_prompt(self.con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.con.sendline("reboot")
        self.con.expect(" RESET: Initiating fast reboot", timeout=60)
        # Exiting to petitboot shell
        self.con.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
        self.con.expect('x=exit', timeout=10)
        print "fast-reset boots the system to runtime"
        self.cv_IPMI.ipmi_set_boot_to_disk()
        return BMC_CONST.FW_SUCCESS

