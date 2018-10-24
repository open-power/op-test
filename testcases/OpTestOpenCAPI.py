#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestOpenCAPI.py $
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
OpTestOpenCAPI
----------

OpenCAPI tests for OpenPower testing.

This class will test the functionality of OpenCAPI

Prerequisites:

1. Host must have a OpenCAPI FPGA card
2. OpenCAPI card must have been flashed with memcpy3 AFU
'''

import time
import subprocess
import re

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestOpenCAPI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()

    def set_up(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        # Check that host has a OpenCAPI FPGA card
        if (self.cv_HOST.host_has_opencapi_fpga_card() != True):
            raise unittest.SkipTest("No OpenCAPI card available on host \
                                     Skipping the OpenCAPI tests")

        self.cv_HOST.host_check_command("git", "gcc")

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module ocxl based on config option
        l_config = "CONFIG_OCXL"
        l_module = "ocxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, \
                                                   l_module)


class OcxlDeviceFileTest(OpTestOpenCAPI, unittest.TestCase):
    '''
    If the system has a OpenCAPI FPGA card, then this test load the ocxl module
    if required and check that the ocxl device files afu0.0m and afu0.0s exist
    '''
    def setUp(self):
        super(OcxlDeviceFileTest, self).setUp()

    def runTest(self):
        self.set_up()
        # Check device files /dev/ocxl/IBM,MEMCPY3.* existence
        l_cmd = "ls -l /dev/ocxl/IBM,MEMCPY3.*; echo $?"
        try:
            self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed:
            self.assertTrue(False, "ocxl device file tests fail")


class MemCpy3AFUTest(OpTestOpenCAPI, unittest.TestCase):
    '''
    If the system has a OpenCAPI FPGA card, then this test load the ocxl module
    if required and test the memcpy3 AFU with ocxl_memcpy
    '''
    def setUp(self):
        super(MemCpy3AFUTest, self).setUp()

    def runTest(self):
        self.set_up()

        # Check that the afutests binary are available
        # If not, clone and build libocxl and afutests
        l_dir = "/tmp/libocxl"
        if (self.cv_HOST.host_check_binary(l_dir, "afuobj/ocxl_memcpy") != True):
            self.cv_HOST.host_clone_libocxl(l_dir)
            self.cv_HOST.host_build_libocxl(l_dir)

        # Run memcpy3 afu tests
        l_exec = "afuobj/ocxl_memcpy -p100 -l100 >/tmp/ocxl_memcpy.log"
        cmd = "cd %s; ./%s; echo $?" % (l_dir, l_exec)
        log.debug(cmd)
        try:
            self.cv_HOST.host_run_command(cmd)
            l_msg = "ocxl_memcpy tests pass"
            log.debug(l_msg)
        except CommandFailed:
            self.assertTrue(False, "ocxl_memcpy tests failed")


def opencapi_test_suite():
    s = unittest.TestSuite()
    s.addTest(OcxlDeviceFileTest())
    s.addTest(MemCpy3AFUTest())
    return s
