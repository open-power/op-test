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

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState


class OpTestMCColdResetEffects(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

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
    def runTest(self):
        print "Test BMC Cold reset effects versus Host Firmware Status"
        print "Issue BMC Cold reset"
        self.cv_SYSTEM.sys_cold_reset_bmc()
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        console.run_command("PATH=/usr/local/sbin:$PATH getscom -l")
        output = self.cv_HOST.host_run_command("sensors; echo $?")
        print "Gathering the OPAL msg logs"
        self.cv_HOST.host_gather_opal_msg_log()
        if "ERROR" in output:
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.assertIn("Error", output, "sensors not working after BMC Cold reset")

