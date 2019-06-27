#!/usr/bin/env python3
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

'''
BootTorture:
-------------------------------

Torture the machine with repeatedly trying to boot

Sample naming conventions below, see each test method for
the applicable options per method.

--run testcases.BootTorture.BootTorture
      ^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^
          module name        subclass

--run testcases.BootTorture.BootTorture10
      ^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^
          module name        subclass

'''

import pexpect
import unittest
import difflib

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class BootTorture(unittest.TestCase):
    '''
    BootTorture x1024

        --run testcases.BootTorture.BootTorture

    '''

    @classmethod
    def setUpClass(cls, boot_iterations=1024):
        cls.boot_iterations = boot_iterations
        cls.conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = cls.conf.system()
        cls.file_lspci = cls.get_lspci_file()

    @classmethod
    def get_lspci_file(cls):
        if cls.conf.lspci_file():
            with open(cls.conf.lspci_file(), 'r') as f:
                file_content = f.read().splitlines()
            log.debug("file_content={}".format(file_content))
            return file_content

    def _diff_my_devices(self,
                         listA=None,
                         listA_name=None,
                         listB=None,
                         listB_name=None):
        '''
        Performs unified diff of two lists
        '''
        unified_output = difflib.unified_diff(
            [_f for _f in listA if _f],
            [_f for _f in listB if _f],
            fromfile=listA_name,
            tofile=listB_name,
            lineterm="")
        unified_list = list(unified_output)
        log.debug("unified_list={}".format(unified_list))
        return unified_list

    def runTest(self):
        self.c = self.cv_SYSTEM.console
        for i in range(1, self.boot_iterations):
            log.debug("Boot iteration %d..." % i)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            try:
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            except pexpect.EOF:
                continue
            self.c.run_command_ignore_fail("head /sys/firmware/opal/msglog")
            self.c.run_command_ignore_fail("tail /sys/firmware/opal/msglog")
            if self.file_lspci:
                active_lspci = self.c.run_command("lspci -mm -n")
                compare_results = self._diff_my_devices(listA=self.file_lspci,
                                                        listA_name=self.conf.lspci_file(),
                                                        listB=active_lspci,
                                                        listB_name="Live System")
                log.debug("compare_results={}".format(compare_results))
                if len(compare_results):
                    self.assertEqual(len(compare_results), 0,
                                     "Stored ({}) and Active PCI devices differ:\n{}"
                                     .format(self.conf.lspci_file(), ('\n'.join(i for i in compare_results))))

            self.c.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            self.c.run_command_ignore_fail(
                "grep ',[0-4]\]' /sys/firmware/opal/msglog")


class BootTorture10(BootTorture, unittest.TestCase):
    '''
    Just boot 10 times. Just a little bit of peril.

        --run testcases.BootTorture.BootTorture10
    '''
    @classmethod
    def setUpClass(cls):
        super(BootTorture10, cls).setUpClass(boot_iterations=10)


class ReBootTorture(BootTorture, unittest.TestCase):
    '''
    Soft Reboot Torture - i.e. running 'reboot' from Petitboot shell.

        --run testcases.BootTorture.ReBootTorture
    '''
    @classmethod
    def setUpClass(cls):
        super(ReBootTorture, cls).setUpClass(boot_iterations=1024)

    def runTest(self):
        self.c = self.cv_SYSTEM.console
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        # Disable the fast-reset
        self.c.run_command(
            "nvram -p ibm,skiboot --update-config fast-reset=0")
        for i in range(1, self.boot_iterations):
            log.debug("Re-boot iteration %d..." % i)
            self.c.run_command_ignore_fail("uname -a")
            self.c.run_command_ignore_fail("cat /etc/os-release")
            if self.file_lspci:
                active_lspci = self.c.run_command("lspci -mm -n")
                compare_results = self._diff_my_devices(listA=self.file_lspci,
                                                        listA_name=self.conf.lspci_file(),
                                                        listB=active_lspci,
                                                        listB_name="Live System")
                log.debug("compare_results={}".format(compare_results))
                if len(compare_results):
                    self.assertEqual(len(compare_results), 0,
                                     "Stored ({}) and Active PCI devices differ:\n{}"
                                     .format(self.conf.lspci_file(), ('\n'.join(i for i in compare_results))))
            self.c.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            self.c.run_command_ignore_fail(
                "grep ',[0-4]\]' /sys/firmware/opal/msglog")
            self.c.pty.sendline("echo 10  > /proc/sys/kernel/printk")
            self.c.pty.sendline("reboot")
            self.cv_SYSTEM.set_state(OpSystemState.IPLing)
            try:
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            except pexpect.EOF:
                self.cv_SYSTEM.goto_state(OpSystemState.OFF)
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)


class ReBootTorture10(BootTorture, unittest.TestCase):
    '''
    Reboot Torture, but only 10x.

        --run testcases.BootTorture.ReBootTorture10
    '''
    @classmethod
    def setUpClass(cls):
        super(ReBootTorture10, cls).setUpClass(boot_iterations=10)
