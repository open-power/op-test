#!/usr/bin/python
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
            zeros = console.run_command("dd if=/dev/zero bs=%u count=%u|hexdump -C -v" % (bs, count), timeout=120)
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

def suite():
    s = unittest.TestSuite()
    s.addTest(Console8k())
    s.addTest(Console16k())
    return s
