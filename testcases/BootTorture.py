#!/usr/bin/env python2
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

import pexpect
import unittest
import subprocess

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

from testcases.OpTestPCI import TestPCI

class BootTorture(unittest.TestCase, TestPCI):
    BOOT_ITERATIONS = 1024
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.pci_good_data_file = conf.lspci_file()

    def runTest(self):
        self.c = self.system.sys_get_ipmi_console()
        for i in range(1,self.BOOT_ITERATIONS):
            print "Boot iteration %d..." % i
            self.system.goto_state(OpSystemState.OFF)
            try:
                self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            except pexpect.EOF:
                continue
            self.system.host_console_unique_prompt()
            self.c.run_command_ignore_fail("head /sys/firmware/opal/msglog")
            self.c.run_command_ignore_fail("tail /sys/firmware/opal/msglog")
            if self.pci_good_data_file:
                self.check_pci_devices()
            self.c.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            self.c.run_command_ignore_fail("grep ',[0-4]\]' /sys/firmware/opal/msglog")

class BootTorture10(BootTorture):
    BOOT_ITERATIONS = 10

# Full Soft Reboot Torture
class ReBootTorture(unittest.TestCase, TestPCI):
    BOOT_ITERATIONS = 1024
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.pci_good_data_file = conf.lspci_file()

    def runTest(self):
        console = self.system.sys_get_ipmi_console()
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.system.host_console_unique_prompt()
        # Disable the fast-reset
        console.run_command("nvram -p ibm,skiboot --update-config fast-reset=0")
        for i in range(1,self.BOOT_ITERATIONS):
            print "Re-boot iteration %d..." % i
            self.system.host_console_unique_prompt()
            console.run_command_ignore_fail("uname -a")
            console.run_command_ignore_fail("cat /etc/os-release")
            if self.pci_good_data_file:
                self.check_pci_devices()
            console.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            console.run_command_ignore_fail("grep ',[0-4]\]' /sys/firmware/opal/msglog")
            console.sol.sendline("echo 10  > /proc/sys/kernel/printk")
            console.sol.sendline("reboot")
            self.system.set_state(OpSystemState.IPLing)
            try:
                self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            except pexpect.EOF:
                self.system.goto_state(OpSystemState.OFF)
                self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

class ReBootTorture10(ReBootTorture):
    BOOT_ITERATIONS = 10
