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

import time
import subprocess
import commands
import re
import sys
import os

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class OOBHostLogin(unittest.TestCase):
    '''Log into the host via out of band console'''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()

    def runTest(self):
        self.system.goto_state(OpSystemState.OS)
        self.system.host_console_login()
        self.system.host_console_unique_prompt()
        l_con = self.system.sys_get_ipmi_console()
        r = l_con.run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = l_con.run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)

class SSHHostLogin(unittest.TestCase):
    '''Log into the host via SSH'''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.host = conf.host()

    def runTest(self):
        self.system.goto_state(OpSystemState.OS)
        r = self.host.host_run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = self.host.host_run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)
