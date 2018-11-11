#!/usr/bin/env python3
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

'''
Kernel Log
----------

Check the Linux kernel log in skiroot and the OS for warnings and errors,
filtering for known benign problems (or problems that are just a Linux issue
rather than a firmware issue).

'''

import unittest

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.OpTestUtil import filter_dmesg
import common.OpTestUtil as Util
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class KernelLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conf = OpTestConfiguration.conf
        cls.opcheck = Util.OpCheck(cls=cls) # OpCheck helper for standard setup

    @classmethod
    def tearDownClass(cls):
        cls.opcheck.check_up(stage="stop") # performs standard checks POST Class

class HostKlog(KernelLog, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OS
        super(HostKlog, cls).setUpClass()

    def test_klog_check(self):
        '''
        Shared klog_check for Host and Skiroot
        -- run testcases.KernelLog.HostKlog.test_klog_check
        -- run testcases.KernelLog.SkirootKlog.test_klog_check
        '''
        log_entries = []
        # Depending on where we're running, we may need to do all sorts of
        # things to get a sane dmesg output. Urgh.
        try:
            log_entries = self.c.run_command(
                "dmesg --color=never -T --level=alert,crit,err,warn")
        except CommandFailed:
            try:
                log_entries = self.c.run_command(
                    "dmesg -T --level=alert,crit,err,warn")
            except CommandFailed:
                try:
                    log_entries = self.c.run_command(
                        "dmesg -r|grep '<[4321]>'")
                except CommandFailed as cf:
                    # An exit code of 1 and no output can mean success.
                    # as it means we're not successfully grepping out anything
                    if cf.exitcode == 1 and len(cf.output) == 0:
                        pass

        status, updated_list = filter_dmesg(log_entries, self.conf)

        msg = '\n'.join(filter(None, updated_list))
        self.assertTrue(len(updated_list) == 0,
                        "Warnings/Errors in Kernel log:\n%s" % msg)

class SkirootKlog(HostKlog):
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.PETITBOOT_SHELL
        super(HostKlog, cls).setUpClass()

def host_klog_suite():
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(HostKlog))
    return s

def skiroot_klog_suite():
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(SkirootKlog))
    return s

