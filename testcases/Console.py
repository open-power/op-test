#!/usr/bin/python2
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

import unittest
import pexpect
import time

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class Console():
    bs = 1024
    count = 8
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.bmc = conf.bmc()
        self.system = conf.system()

    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.bmc.get_host_console()
        self.system.host_console_unique_prompt()
        bs = self.bs
        count = self.count
        self.assertTrue( (bs*count)%16 == 0, "Bug in test writer. Must be multiple of 16 bytes: bs %u count %u / 16 = %u" % (bs, count, (bs*count)%16))
        try:
            zeros = console.run_command("dd if=/dev/zero bs=%u count=%u|hexdump -C -v" % (bs, count), timeout=240)
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0)
        self.assertTrue( len(zeros) == 3+(count*bs)/16, "Unexpected length of zeros %u" % (len(zeros)))

class Console8k(Console, unittest.TestCase):
    bs = 1024
    count = 8

class Console16k(Console, unittest.TestCase):
    bs = 1024
    count = 16

class Console32k(Console, unittest.TestCase):
    bs = 1024
    count = 32

class ControlC(unittest.TestCase):
    CONTROL = 'c'
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.bmc = conf.bmc()
        self.system = conf.system()

    def cleanup(self):
        pass

    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.bmc.get_host_console()
        self.system.host_console_unique_prompt()
        # I should really make this API less nasty...
        raw_console = console.get_console()
        #raw_console.sendline("hexdump -C -v /dev/zero")
        raw_console.sendline("find /")
        time.sleep(2)
        raw_console.sendcontrol(self.CONTROL)
        BMC_DISCONNECT = 'SOL session closed by BMC'
        timeout = 15
        try:
            rc = raw_console.expect([BMC_DISCONNECT, "\[console-pexpect\]#$"], timeout)
            if rc == 0:
                raise BMCDisconnected(BMC_DISCONNECT)
            self.assertEqual(rc, 1, "Failed to find expected prompt")
        except pexpect.TIMEOUT as e:
            print e
            print "# TIMEOUT waiting for command to finish with ctrl-c."
            print "# Everything is terrible. Fail the world, power cycle (if lucky)"
            self.system.set_state(OpSystemState.UNKNOWN)
            self.fail("Could not ctrl-c running command in reasonable time")
        self.cleanup()

class ControlZ(ControlC):
    CONTROL='z'
    def cleanup(self):
        console = self.bmc.get_host_console()
        console.run_command("kill %1")
        console.run_command_ignore_fail("fg")

def suite():
    s = unittest.TestSuite()
    s.addTest(Console8k())
    s.addTest(Console16k())
    s.addTest(ControlZ())
    return s
