#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDPO.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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

'''
Delayed Power Off (DPO)
-----------------------

Delayed Power off testcase is to test OS graceful shutdown request
to be notified from OPAL and OS should process the request.
We will use "ipmitool power soft" command to issue DPO.
'''

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import pexpect
import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
import common.OpTestQemu as OpTestQemu
import common.OpTestMambo as OpTestMambo

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Base(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type


class DPOSkiroot(Base):

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.host = "Skiroot"
        log.debug("Starting DPO test in Skiroot")

    def runTest(self):
        '''
        This will test DPO feature in skiroot and Host
        '''
        self.setup_test()
        # retry added for IPMI cases, seems more sensitive with initial start
        # of state=4
        if isinstance(self.cv_SYSTEM.console, OpTestQemu.QemuConsole) \
                or isinstance(self.cv_SYSTEM.console, OpTestMambo.MamboConsole):
            raise self.skipTest("Performing \"ipmitool power soft\" will "
                                "terminate QEMU/Mambo so skipped")
        self.cv_SYSTEM.console.run_command("uname -a", retry=5)
        if self.host == "Host":
            self.cv_SYSTEM.load_ipmi_drivers(True)
        self.cv_SYSTEM.console.pty.sendline("ipmitool power soft")
        rc = self.cv_SYSTEM.console.pty.expect_exact([
            "reboot: Power down",
            "Chassis Power Control: Soft",
            "Power down",
            "OPAL: Shutdown request type 0x0",
            "Invalid command",
            "Unspecified error",
            "Could not open device at",
            pexpect.TIMEOUT,
            pexpect.EOF], timeout=120)
        self.assertIn(rc, [0, 1, 2, 3], "Failed to power down")
        rc = self.cv_SYSTEM.sys_wait_for_standby_state()
        log.debug(rc)
        self.cv_SYSTEM.console.pty.expect_exact(
            ['.*', pexpect.TIMEOUT], timeout=3)
        # Force the system state to be detected again.
        self.cv_SYSTEM.set_state(OpSystemState.OFF)
