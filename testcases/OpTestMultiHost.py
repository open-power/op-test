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

import OpTestConfiguration
from common.OpTestSystem import OpSystemState


class OpTestMultiHost(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        # retrieve the multi hosts objects
        self.hosts = self.conf.get_all_hosts()

    def runTest(self):
        for host in self.hosts:
            self.cv_SYSTEM = host.system()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            con.run_command("hostname -f", timeout=60)
