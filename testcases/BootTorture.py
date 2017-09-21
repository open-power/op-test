#!/usr/bin/python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

# Torture the machine with repeatedly trying to boot

import unittest
import subprocess

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

from testcases.OpTestPCI import TestPCI

class BootTorture(unittest.TestCase, TestPCI):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.pci_good_data_file = conf.lspci_file()

    def runTest(self):
        self.c = self.system.sys_get_ipmi_console()
        for i in range(1,1024):
            print "Boot iteration %d..." % i
            self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.system.host_console_unique_prompt()
            self.c.run_command("cat /sys/firmware/opal/msglog")
            self.check_pci_devices()
            self.c.run_command("dmesg -r|grep '<[4321]>'")
            self.c.run_command("grep ',[0-4]\]' /sys/firmware/opal/msglog")
            self.system.goto_state(OpSystemState.OFF)

