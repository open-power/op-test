#!/usr/bin/env python2
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

'''
Console tests
-------------

A bunch of really simple console tests that have managed to break *every*
BMC implementation we've ever thrown it at. Since we're highly reliant
on the BMC providing a reliable host console, if these tests fail at all,
then we're likely going to get spurious failures elsewhere in the test suite.
'''

import unittest
import pexpect
import time

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
import common.OpTestMambo as OpTestMambo

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Console():
    bs = 1024
    count = 8

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_BMC = conf.bmc()
        self.cv_SYSTEM = conf.system()
        self.util = conf.util

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.cv_BMC.get_host_console()
        adjustment = 3  # mambo echo now disabled in initial setup
        bs = self.bs
        count = self.count
        self.assertTrue((bs * count) % 16 == 0,
                        "Bug in test writer. Must be multiple of 16 bytes: "
                        "bs {} count {} / 16 = {}".format(bs, count,
                                                          (bs * count) % 16))
        try:
            zeros = console.run_command(
                "dd if=/dev/zero bs={} count={}|hexdump -C -v".format(bs,
                                                                      count),
                timeout=240)
        except CommandFailed as cf:
            if cf.exitcode == 0:
                pass
            else:
                raise cf
        expected = adjustment + (count * bs) / 16
        self.assertTrue(len(zeros) == expected,
                        "Unexpected length of zeros {} != {}".format(
                            len(zeros), expected))


class Console8k(Console, unittest.TestCase):
    '''
    hexdump 8kb of zeros and check we get all the lines of hexdump output on
    the console.
    '''
    bs = 1024
    count = 8


class Console16k(Console, unittest.TestCase):
    '''
    hexdump 16kb of zeros and check we get all the lines of hexdump output on
    the console.
    '''
    bs = 1024
    count = 16


class Console32k(Console, unittest.TestCase):
    '''
    hexdump 32kb of zeros and check we get all the lines of hexdump output on
    the console. The idea is that console buffers on BMCs are likely to be less
    than 32kb, so we'll be able to catch any silent wrapping of it.
    '''
    bs = 1024
    count = 32


class ControlC(unittest.TestCase):
    '''
    Start a process that does a bunch of console output, and then try and
    'control-c' it to stop the process and get a prompt back.
    '''
    CONTROL = 'c'

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_BMC = conf.bmc()
        self.cv_SYSTEM = conf.system()
        self.util = conf.util
        self.prompt = self.util.build_prompt()

    def cleanup(self):
        pass

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.cv_BMC.get_host_console()
        if (isinstance(self.cv_BMC, OpTestMambo.OpTestMambo)):
            raise unittest.SkipTest("Mambo so skipping Control-C tests")
        raw_pty = console.get_console()
        raw_pty.sendline("find /")
        time.sleep(2)
        raw_pty.sendcontrol(self.CONTROL)
        BMC_DISCONNECT = 'SOL session closed by BMC'
        timeout = 60
        try:
            rc = raw_pty.expect([BMC_DISCONNECT, self.prompt,
                                 pexpect.TIMEOUT, pexpect.EOF], timeout)
            if rc == 0:
                raise BMCDisconnected(BMC_DISCONNECT)
            self.assertEqual(rc, 1, "Failed to find expected prompt")
        except pexpect.TIMEOUT as e:
            raw_pty.sendcontrol('z')
            rc = raw_pty.expect([self.prompt, pexpect.TIMEOUT], 10)
            if rc == 0:
                console.run_command_ignore_fail("kill %1")
                console.run_command_ignore_fail("fg")
                self.fail("Had to ctrl-z rather than ctrl-c")
                pass
            log.debug(e)
            log.debug("# TIMEOUT waiting for command to finish with ctrl-c.")
            log.debug("# Everything is terrible. Fail the world, "
                      "power cycle (if lucky)")
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            self.fail("Could not ctrl-c running command in reasonable time")
        self.cleanup()


class ControlZ(ControlC):
    '''
    Run a console output heavy task, try to control-z it, then kill it and get
    back to a prompt.
    '''
    CONTROL = 'z'

    def cleanup(self):
        console = self.cv_BMC.get_host_console()
        console.run_command_ignore_fail("kill %1")
        console.run_command_ignore_fail("fg")


def suite():
    s = unittest.TestSuite()
    s.addTest(Console32k())
    s.addTest(ControlZ())
    s.addTest(ControlC())
    return s
