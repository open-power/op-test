#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSwitchEndianSyscall.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
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
OpTestSwitchEndianSyscall
-------------------------

Switch endian system call package for OpenPower testing.

This class will test the functionality of following.

1. It will test switch_endian() system call by executing the registers
   changes in other endian. By calling switch_endian sys call,
   should not effect register and memory space.
2. This functionality is implemented in linux git repository
   /linux/tools/testing/selftests/powerpc/switch_endian
3. In this test, will clone latest linux git repository and make required
   files. At the end will execute switch_endian_test executable file.
'''

import time
import subprocess
import re

import unittest

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestSwitchEndianSyscall(unittest.TestCase):
    '''
    If git and gcc commands are availble on host, this function will clone linux
    git repository and check for switch_endian_test directory and make
    the required files. And finally execute bin file switch_endian_test.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Check whether git and gcc commands are available on host
        self.cv_HOST.host_check_command("git", "gcc")

        # Clone latest linux git repository into l_dir
        l_dir = "/tmp/linux"
        self.cv_HOST.host_clone_linux_source(l_dir)

        # Check for switch_endian test directory.
        self.check_dir_exists(l_dir)

        # make the required files
        self.make_test(l_dir)

        # Run the switch_endian sys call test once
        l_rc = self.run_once(l_dir)
        if int(l_rc) == 1:
            log.debug("Switch endian sys call test got succesful")
            return
        else:
            raise "Switch endian sys call test failed"

    def check_dir_exists(self, i_dir):
        '''
        It will check for existence of switch_endian directory in the cloned repository

        :param i_dir: linux source directory
        '''
        l_dir = '%s/tools/testing/selftests/powerpc/switch_endian' % i_dir
        l_cmd = "test -d %s; echo $?" % l_dir
        try:
            l_res = self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed as c:
            self.assertEqual(c.exitcode, 0, str(c))

    def make_test(self, i_dir):
        '''
        It will prepare for executable bin files using make command
        At the end it will check for bin file switch_endian_test and
        will throw an exception in case of missing bin file after make

        :param i_dir: linux source directory
        '''
        l_cmd = "cd %s/tools/testing/selftests/;make;" % i_dir
        try:
            l_res = self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed as c:
            self.assertEqual(c.exitcode, 0, str(c))

        l_cmd = "test -f %s/tools/testing/selftests/powerpc/switch_endian/switch_endian_test; echo $?" % i_dir
        try:
            l_res = self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed as c:
            self.assertEqual(c.exitcode, 0, str(c))

    def run_once(self, i_dir):
        '''
        This function will run executable file switch_endian_test and
        check for switch_endian() sys call functionality

        :param i_dir: linux source directory
        '''
        l_cmd = "cd %s/tools/testing/selftests/powerpc/switch_endian/;\
                 ./switch_endian_test" % i_dir
        l_res = self.cv_HOST.host_run_command(l_cmd)
        if ("\n".join(l_res).__contains__('success: switch_endian_test')):
            return 1
        else:
            return 0
