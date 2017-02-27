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


import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

class OpTestFastReboot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    ##
    # @brief  This function tests fast reset of power systems.
    #         It will check booting sequence when reboot command
    #         getting executed in both petitboot and host OS
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_IPMI.ipmi_host_set_unique_prompt()
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        c.run_command(BMC_CONST.NVRAM_SET_FAST_RESET_MODE)
        res = c.run_command(BMC_CONST.NVRAM_PRINT_FAST_RESET_VALUE)
        self.assertIn("feeling-lucky", res, "Failed to set the fast-reset mode")
        initialResetCount = c.run_command("grep -c 'RESET: Initiating fast' /sys/firmware/opal/msglog")
        # We do some funny things with the raw console here, as
        # 'reboot' isn't meant to return, so we want the raw
        # pexpect 'console'.
        self.con = self.cv_SYSTEM.sys_get_ipmi_console().get_console()
        self.con.sendline("reboot")
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        # We're looking for a skiboot log message, that it's doing fast
        # rebot. We *may* not get this, as on some systems (notably IBM
        # FSP based systems) the skiboot log is *not* printed to IPMI
        # console
        if self.cv_SYSTEM.skiboot_log_on_console():
            self.con.expect(" RESET: Initiating fast reboot", timeout=60)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_IPMI.ipmi_host_set_unique_prompt()
        c.run_command(BMC_CONST.NVRAM_DISABLE_FAST_RESET_MODE)
        res = c.run_command(BMC_CONST.NVRAM_PRINT_FAST_RESET_VALUE)
        self.assertNotIn("feeling-lucky", res, "Failed to set the fast-reset mode")
        newResetCount = c.run_command("grep -c 'RESET: Initiating fast' /sys/firmware/opal/msglog")
        self.assertTrue( int(''.join(initialResetCount)) < int(''.join(newResetCount)), "Did not do fast reboot")
