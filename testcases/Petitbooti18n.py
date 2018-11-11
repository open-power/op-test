#!/usr/bin/env python3
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
# Do a basic sanity check of the Petitboot UI to see if unicode strings are
# being displayed correctly. We do this by moving to the Language screen and
# checking each example string is present. These representations match the
# layout and encoding in ui/ncurses/nc-lang.c

'''
Petitboot Internationalization (i8n)
------------------------------------

Test that Petitboot can correctly display languages other than English.
'''

import time
import pexpect
import unittest

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
import common.OpTestMambo as OpTestMambo
import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Petitbooti18n(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        log.debug("Test i18n strings appear correctly in Petitboot")
        if (isinstance(self.cv_SYSTEM.console, OpTestMambo.MamboConsole)):
            raise unittest.SkipTest("Mambo so skipping Language tests")

        # Wait a moment for pb-discover to connect
        time.sleep(3)

        raw_pty = self.cv_SYSTEM.console.get_console()
        raw_pty.sendcontrol('l')  # refresh the screen
        rc = raw_pty.expect(
            ['Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=5)

        raw_pty.send("l")  # key press L
        rc = raw_pty.expect(
            ['Deutsch', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['English', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['Español', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['Français', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['Italiano', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(['日本語', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(['한국어', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['Português/Brasil', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(
            ['Русский', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(['简体中文', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        rc = raw_pty.expect(['繁體中文', pexpect.TIMEOUT, pexpect.EOF], timeout=5)

        # Return to the Petitboot main menu
        raw_pty.sendcontrol('l')  # refresh the screen to Languages
        raw_pty.send("x")  # exit to main petitboot menu
        raw_pty.sendcontrol('l')  # refresh the main petitboot menu
        raw_pty.sendcontrol('u')  # clear from cursor move cursor
        rc = raw_pty.expect(
            ['x=exit', pexpect.TIMEOUT, pexpect.EOF], timeout=10)

        pass
