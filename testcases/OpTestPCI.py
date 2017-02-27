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

class OpTestPCI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.pci_good_data_file = conf.lspci_file()

class OpTestPCISkiroot(OpTestPCI):
    # compare petitboot "lspci -mm -n" to known good data
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        cmd = "lspci -mm -n"
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_set_unique_prompt()
        c.run_command("uname -a")
        c.run_command("cat /etc/os-release")

        res = '\n'.join(c.run_command(cmd))

        self.pci_data_petitboot = res
        diff_process = subprocess.Popen(['diff', "-u", self.pci_good_data_file , "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_petitboot + '\n')
        r = diff_process.wait()
        self.assertEqual(r, 0, "Stored and detected PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

class OpTestPCIHost(OpTestPCI):
    # Compare host "lspci -mm -n" output to known good
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        self.cv_HOST.host_check_command("lspci", "lsusb")
        self.cv_HOST.host_list_pci_devices()
        self.cv_HOST.host_get_pci_verbose_info()
        self.cv_HOST.host_list_usb_devices()
        l_res = self.cv_HOST.host_run_command("lspci -mm -n")
        # FIXME: why do we get a blank line in l_res ?
        self.pci_data_hostos = l_res.replace("\r\n", "\n")
        diff_process = subprocess.Popen(['diff', "-u", self.pci_good_data_file , "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_hostos)
        r = diff_process.wait()
        self.assertEqual(r, 0, "Stored and detected PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

