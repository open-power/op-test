#!/usr/bin/env python3
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

'''
OpTestCAPI
----------

CAPI tests for OpenPower testing.

This class will test the functionality of CAPI

Prerequisites:

1. Host must have a CAPI FPGA card
2. CAPI card must have been flashed with memcpy AFU

Extra timebase sync tests prerequisite:

3. PSL must support timebase sync
'''


import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestCAPI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()

    def set_up(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        # Check that host has a CAPI FPGA card
        if (self.cv_HOST.host_has_capi_fpga_card() != True):
            raise unittest.SkipTest("No CAPI card available on host \
                                     Skipping the CAPI tests")

        self.cv_HOST.host_check_command("git", "gcc")

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config,
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
        l_cmd = "ls -l /dev/cxl/afu0.0{m,s}"
        try:
            self.cv_HOST.host_run_command(l_cmd)
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
        if (self.cv_HOST.host_check_binary(l_dir, "libcxl_tests") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Unconditionally unload incompatible module cxl_memcpy,
        # then run sysfs abi tests
        l_exec = "libcxl_tests >/tmp/libcxl_tests.log"
        cmd = "rmmod cxl_memcpy; cd %s && LD_LIBRARY_PATH=libcxl ./%s;" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "sysfs abi libcxl_tests pass"
            log.debug(l_msg)
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
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run memcpy afu tests
        l_exec = "memcpy_afu_ctx -p0 -l10000 >/tmp/memcpy_afu_ctx.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "memcpy_afu_ctx tests pass"
            log.debug(l_msg)
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx tests failed")


class MemCpyAFUIrqTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and test the memcpy AFU with memcpy_afu_ctx -i
    '''

    def setUp(self):
        super(MemCpyAFUIrqTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run memcpy afu tests
        l_exec = "memcpy_afu_ctx -p100 -i5 -I5 -l10000 >/tmp/memcpy_afu_ctx-i.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "memcpy_afu_ctx -i tests pass"
            log.debug(l_msg)
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx -i tests failed")


class MemCpyAFUReallocTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and test the memcpy AFU with memcpy_afu_ctx -r
    '''

    def setUp(self):
        super(MemCpyAFUReallocTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run memcpy afu tests
        l_exec = "memcpy_afu_ctx -p0 -r -l3000 >/tmp/memcpy_afu_ctx-r.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "memcpy_afu_ctx -r tests pass"
            log.debug(l_msg)
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx -r tests failed")


class TimeBaseSyncTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl module
    if required and also check if the card PSL supports timebase sync. If it
    supports it, then test timebase sync with memcpy_afu_ctx -t
    '''

    def setUp(self):
        super(TimeBaseSyncTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check PSL timebase sync support
        l_cmd = "grep -q -w 1 /sys/class/cxl/card0/psl_timebase_synced;"
        try:
            self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed:
            l_msg = "PSL does not support timebase sync; skipping test"
            raise unittest.SkipTest(l_msg)

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run timebase sync tests
        l_exec = "memcpy_afu_ctx -t -p1 -l1 >/tmp/memcpy_afu_ctx-t.log"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            log.debug("memcpy_afu_ctx -t tests pass")
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx -t tests failed")


class KernelAPITest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then this test load the cxl and
    the cxl_memcpy modules if required, and test the kernel API of memcpy
    with memcpy_afu_ctx -K.
    '''

    def setUp(self):
        super(KernelAPITest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Load module cxl_memcpy if required
        l_cmd = "lsmod | grep cxl_memcpy || (cd %s && (make cxl-memcpy.ko && insmod ./cxl-memcpy.ko))" % l_dir
        try:
            self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed:
            l_msg = "Could not load module cxl_memcpy"
            raise unittest.SkipTest(l_msg)

        # Run memcpy kernel API tests
        l_exec = "memcpy_afu_ctx -K -p1 -l1 >/tmp/memcpy_afu_ctx-K.log"
        cmd = "(cd %s && LD_LIBRARY_PATH=libcxl ./%s);" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            log.debug("memcpy_afu_ctx -K tests pass")
        except CommandFailed:
            self.assertTrue(False, "memcpy_afu_ctx -K tests failed")


class CxlResetTest(OpTestCAPI, unittest.TestCase):
    '''
    If a given system has a CAPI FPGA card, then load the cxl module
    if required, and test reset with cxl_eeh_tests.sh and memcpy_afu_ctx.
    '''

    def setUp(self):
        super(CxlResetTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
                self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run memcpy afu reset tests
        l_exec = "cxl_eeh_tests.sh -l10"
        cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "cxl reset tests pass"
            log.debug(l_msg)
        except CommandFailed:
            self.assertTrue(False, "cxl reset tests failed")


def capi_test_suite():
    s = unittest.TestSuite()
    s.addTest(CxlDeviceFileTest())
    s.addTest(SysfsABITest())
    s.addTest(MemCpyAFUTest())
    s.addTest(MemCpyAFUIrqTest())
    s.addTest(MemCpyAFUReallocTest())
    s.addTest(TimeBaseSyncTest())
    s.addTest(KernelAPITest())
    s.addTest(CxlResetTest())
    return s
