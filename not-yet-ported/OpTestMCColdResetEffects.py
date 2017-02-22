#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestMCColdResetEffects.py $
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

#  @package OpTestMCColdResetEffects.py
#   This testcase basically will test the status of Host FW when user trying to attempt
#   a BMC cold reset when system is in runtime.
#   test steps:
#   1. Boot the system to runtime
#   2. Issue BMC Cold reset
#   3. Check Host FW services
#      Ex: sensors, get the list of chips
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
from OpTestSensors import OpTestSensors


class OpTestMCColdResetEffects():
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
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, host=self.cv_HOST)
        self.cv_SYSTEM = OpTestSystem(bmc=self.cv_BMC,
                                      i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                                      i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

        self.opTestSensors = OpTestSensors(i_bmcIP, i_bmcUser, i_bmcPasswd,
                                           i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                                           i_hostuser, i_hostPasswd)

    ##
    # @brief  This function will test BMC Cold reset vs Host FW status
    #         1. When system is in runtime issue BMC Cold reset.
    #         2. Check Host FW services and drivers.
    #         3. Run sensors command
    #         4. Get list of chips
    #         5. This is expected to fail.
    #           https://github.com/open-power/op-build/issues/482
    #         6. Reboot the system at the end of test.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_bmc_cold_reset_effects(self):
        print "Test BMC Cold reset effects versus Host Firmware Status"
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        print "Issue BMC Cold reset"
        result = True
        try:
            self.cv_SYSTEM.sys_cold_reset_bmc()
            l_dir = BMC_CONST.SKIBOOT_WORKING_DIR
            self.cv_HOST.host_clone_skiboot_source(l_dir)
            self.cv_HOST.host_compile_xscom_utilities(l_dir)
            l_con = self.cv_SYSTEM.sys_get_ipmi_console()
            self.cv_IPMI.ipmi_host_login(l_con)
            self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
            self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("cd %s/external/xscom-utils/; ./getscom -l" % l_dir)
            self.opTestSensors.test_hwmon_driver()
            self.cv_SYSTEM.sys_ipmi_close_console(l_con)
        except:
            result = False
            pass
        print "Gathering the OPAL msg logs"
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_IPMI.ipmi_power_off()
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        if result is False:
            raise OpTestError("MC Cold reset vs Host FW Test failed")
