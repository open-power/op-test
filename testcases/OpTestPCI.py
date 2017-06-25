#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPCI.py $
#
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
# IBM_PROLOG_END_TAG

#  @package OpTestPCI.py
#   This testcase basically will test and gather PCI subsystem Info
#   Tools used are lspci and lsusb
#   any pci related tests will be added in this package

import time
import subprocess
import commands
import re
import sys
import os
import os.path

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed


class TestPCI():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.pci_good_data_file = conf.lspci_file()

    def pcie_link_errors(self):
        total_entries = link_down_entries = timeout_entries = []
        try:
            link_down_entries = self.c.run_command("grep 'PHB#.* Link down' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if link_down_entries:
            total_entries = total_entries + link_down_entries
        try:
            timeout_entries = self.c.run_command("grep 'Timeout waiting for' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if timeout_entries:
            total_entries = total_entries + timeout_entries
        msg = '\n'.join(filter(None, total_entries))
        self.assertTrue( len(total_entries) == 0, "pcie link down/timeout Errors in OPAL log:\n%s" % msg)

    def check_pci_devices(self):
        c = self.c
        l_res = c.run_command("lspci -mm -n")
        # We munge the result back to what we'd get
        # from "ssh user@host lspci -mm -n > host-lspci.txt" so that the diff
        # is simple to do
        self.pci_data_hostos = '\n'.join(l_res) + '\n'
        diff_process = subprocess.Popen(['diff', "-u", self.pci_good_data_file , "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_hostos)
        r = diff_process.wait()
        self.assertEqual(r, 0, "Stored and detected PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

    # Compare host "lspci -mm -n" output to known good
    def runTest(self):
        self.setup_test()
        c = self.c

        list_pci_devices_commands = ["lspci -mm -n",
                                     "lspci -m",
                                     "lspci -t",
                                     "lspci -n",
                                     "lspci -nn",
                                     "cat /proc/bus/pci/devices",
                                     "ls /sys/bus/pci/devices/ -l",
                                     "lspci -vvxxx",
                                     ]
        for cmd in list_pci_devices_commands:
            c.run_command(cmd, timeout=300)

        list_usb_devices_commands = ["lsusb",
                                     "lsusb -t",
                                     "lsusb -v",
                                     ]
        for cmd in list_usb_devices_commands:
            c.run_command(cmd)

        # Test we don't EEH on reading all config space
        c.run_command("hexdump -C /sys/bus/pci/devices/*/config", timeout=600)

        if not self.pci_good_data_file:
            self.skipTest("No good pci data provided")
        self.check_pci_devices()


class TestPCISkiroot(TestPCI, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class TestPCIHost(TestPCI, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()

class PcieLinkErrorsHost(TestPCIHost, unittest.TestCase):

    def runTest(self):
        self.setup_test()
        self.pcie_link_errors()

class PcieLinkErrorsSkiroot(TestPCISkiroot, unittest.TestCase):

    def runTest(self):
        self.setup_test()
        self.pcie_link_errors()

