#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

import unittest
import re
import time
import pexpect

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class RebootTime():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()

        rc = self.c.run_command("uname -a") # run any command to get console setup, if expected to be logged in

        # now console is logged in and you can perform raw pexpect commands that assume log in
        self.c.sol.sendline("reboot")

        start = time.time()
        rc = self.c.sol.expect(["OPAL: Reboot request", "reboot: Restarting system", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
        if rc in [0,1]:
          log.debug("Time to OPAL reboot handler: {} seconds".format(time.time() - start))
        else:
          self.assertTrue(False, "Unexpected rc=%s from reboot request" % rc)

class Skiroot(RebootTime, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console

class Host(RebootTime, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.console
