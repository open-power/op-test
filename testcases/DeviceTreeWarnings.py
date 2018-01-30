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
# DeviceTreeWarnings
# This test read the device tree from /proc/device-tree using dtc
# and fails if there are any device tree warnings or errors present.
#

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

class DeviceTreeWarnings():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        log_entries = self.c.run_command("dtc -I fs /proc/device-tree -O dts -o dts")
        msg = '\n'.join(filter(None, log_entries))
        self.assertTrue(len(log_entries) == 0, "Warnings/Errors in Device Tree:\n%s" % msg)

class Skiroot(DeviceTreeWarnings, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class Host(DeviceTreeWarnings, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()
        self.cv_HOST.host_check_command("dtc")
