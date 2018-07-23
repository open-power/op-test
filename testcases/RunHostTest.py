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
import os

import OpTestConfiguration
from common.OpTestSystem import OpSystemState


class RunHostTest(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.host_cmd = self.conf.args.host_cmd
        self.host_cmd_file = self.conf.args.host_cmd_file
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        if not (self.host_cmd or self.host_cmd_file):
            self.fail("Provide either --host-cmd and --host-cmd-file option")

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        if self.host_cmd:
            con.run_command(self.host_cmd, timeout=self.host_cmd_timeout)
        if self.host_cmd_file:
            if not os.path.isfile(self.host_cmd_file):
                self.fail("Provide valid host cmd file path")
            fd = open(self.host_cmd_file, "r")
            for line in fd.readlines():
                line = line.strip()
                if "reboot" in line:
                    self.cv_SYSTEM.goto_state(OpSystemState.OFF)
                    self.cv_SYSTEM.goto_state(OpSystemState.OS)
                    con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
                    continue
                con.run_command(line, timeout=self.host_cmd_timeout)
