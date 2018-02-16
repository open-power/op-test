#!/usr/bin/python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestCAPI.py $
#
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
# IBM_PROLOG_END_TAG

#  @package OpTestCAPI
#  CAPI tests for OpenPower testing.
#
#  This class will test the functionality of CAPI
#
#  Prerequisites:
#  1. Host must have a CAPI FPGA card
#  2. CAPI card must have been flashed with memcpy AFU
#
#  Extra timebase sync tests prerequisite:
#  3. PSL must support timebase sync

import time
import subprocess
import re

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed


class OpTestCAPI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.host = conf.host()

    def set_up(self):
        self.system.goto_state(OpSystemState.OS)
        # Check that host has a CAPI FPGA card
        if (self.host.host_has_capi_fpga_card() != True):
            raise unittest.SkipTest("No CAPI card available on host \
                                     Skipping the CAPI tests")

        self.host.host_check_command("git", "gcc")

        # Get OS level
        l_oslevel = self.host.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.host.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.host.host_load_module_based_on_config(l_kernel, l_config, \
                                                   l_module)

class CxlDeviceFileTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and check that the cxl device files afu0.0m and afu0.0s exist
    '''
    def setUp(self):
        super(CxlDeviceFileTest, self).setUp()

    def runTest(self):
        self.set_up()
        # Check device files /dev/cxl/afu0.0{m,s} existence
        l_cmd = "ls -l /dev/cxl/afu0.0{m,s}; echo $?"
        try:
            self.host.host_run_command(l_cmd)
        except CommandFailed:
            self.assertTrue(False, "cxl device file tests fail")

class SysfsABITest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and run the sysfs ABI tests from libcxl_tests
    '''
    def setUp(self):
        super(SysfsABITest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.host.host_check_binary(l_dir, "libcxl_tests") != True or
            self.host.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.host.host_clone_cxl_tests(l_dir)
            self.host.host_build_cxl_tests(l_dir)

        # Run sysfs abi tests
        l_exec = "libcxl_tests >/tmp/libcxl_tests.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s;" % (l_dir, l_exec)
        print cmd
        try:
            self.host.host_run_command(cmd)
            l_msg = "sysfs abi libcxl_tests pass"
            print l_msg
        except CommandFailed:
            self.assertTrue(False, "sysfs abi libcxl_tests have failed")


class MemCpyAFUTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and test the memcpy AFU with memcpy_afu_ctx
    '''
    def setUp(self):
        super(MemCpyAFUTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.host.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
            self.host.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.host.host_clone_cxl_tests(l_dir)
            self.host.host_build_cxl_tests(l_dir)

        # Run memcpy afu tests
        l_exec = "memcpy_afu_ctx -p1 -l1 >/tmp/memcpy_afu_ctx.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s; echo $?" % (l_dir, l_exec)
        print cmd
        try:
            self.host.host_run_command(cmd)
            l_msg = "memcpy_afu_ctx tests pass"
            print l_msg
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx tests failed")

class TimeBaseSyncTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and also check if the card PSL supports timebase sync, if it
    supports runs the timebase sync with memcpy_afu_ctx -t tests from libcxl
    '''
    def setUp(self):
        super(TimeBaseSyncTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check PSL timebase sync support
        l_cmd = "grep -q -w 1 /sys/class/cxl/card0/psl_timebase_synced;"
        try:
            self.host.host_run_command(l_cmd)
        except CommandFailed:
            l_msg = "PSL does not support timebase sync; skipping test"
            raise unittest.SkipTest(l_msg)

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.host.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
            self.host.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.host.host_clone_cxl_tests(l_dir)
            self.host.host_build_cxl_tests(l_dir)

        # Run timebase sync tests
        l_exec = "memcpy_afu_ctx -t -p1 -l1 >/tmp/memcpy_afu_ctx-t.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s; echo $?" % (l_dir, l_exec)
        print cmd
        try:
            self.host.host_run_command(cmd)
            print "memcpy_afu_ctx -t tests pass"
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx -t tests failed")

def capi_test_suite():
    s = unittest.TestSuite()
    s.addTest(CxlDeviceFileTest())
    s.addTest(SysfsABITest())
    s.addTest(MemCpyAFUTest())
    s.addTest(TimeBaseSyncTest())
    return s
