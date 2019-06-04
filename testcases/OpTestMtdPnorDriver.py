#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestMtdPnorDriver.py $
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
OpTestMtdPnorDriver
-------------------

Test MTD PNOR Driver package for OpenPower testing.

.. warning::

   This has been migrated along with other tests but never used in earnest.
   It is likely we could accomplish all of this on the host itself.
   I *severely* doubt this test case currently works as intended.
'''

import time
import subprocess
import re
import commands

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestMtdPnorDriver(unittest.TestCase):
    '''
    This function has following test steps

    1. Get host information(OS and Kernel information)
    2. Load the mtd module based on config value
    3. Check /dev/mtd0 character device file existence on host
    4. Copying the contents of the flash in a file /tmp/pnor
    5. Getting the /tmp/pnor file into local x86 machine using scp utility
    6. Remove existing /tmp/ffs directory and
       Clone latest ffs git repository in local x86 working machine
    7. Compile ffs repository to get fcp utility
    8. Check existence of fcp utility in ffs repository, after compiling
    9. Get the PNOR flash contents on an x86 machine using fcp utility
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = self.cv_SYSTEM.util
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.host_ip = conf.args.host_ip
        self.host_user = conf.args.host_user
        self.host_Passwd = conf.args.host_password
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()

    def runTest(self):
        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # loading mtd module based on config option
        l_config = "CONFIG_MTD_POWERNV_FLASH"
        l_module = "mtd"
        self.cv_HOST.host_load_module_based_on_config(
            l_kernel, l_config, l_module)

        # Check /dev/mtd0 file existence on host
        l_cmd = "ls -l /dev/mtd0"
        try:
            l_res = self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0,
                             "/dev/mtd0 character flash device file doesn't exist on host\n%s" % str(cf))
        log.debug("/dev/mtd0 character device file exists on host")

        # Copying the contents of the PNOR flash in a file /tmp/pnor
        l_file = "/tmp/pnor"
        l_cmd = "cat /dev/mtd0 > %s" % l_file
        try:
            l_res = self.cv_HOST.host_run_command(l_cmd)
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0,
                             "Fetching PNOR data is failed from /dev/mtd0 into temp file /tmp/pnor\n%s" % str(cf))

        # Getting the /tmp/pnor file into local x86 machine
        l_path = "/tmp/"
        self.util.copyFilesToDest(
            l_path, self.host_user, self.host_ip, l_file, self.host_Passwd)
        l_list = commands.getstatusoutput("ls -l %s" % l_path)
        log.debug(l_list)

        l_workdir = "/tmp/ffs"
        # Remove existing /tmp/ffs directory
        l_res = commands.getstatusoutput("rm -rf %s" % l_workdir)

        # Clone latest ffs git repository in local x86 working machine
        l_cmd = "git clone   https://github.com/open-power/ffs/ %s" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        self.assertEqual(int(l_res[0]), 0,
                         "Cloning ffs repository is failed")

        # Compile ffs repository to get fcp utility
        l_cmd = "cd %s/; autoreconf -i && ./configure && make" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        self.assertEqual(int(l_res[0]), 0, "Compiling fcp utility is failed")

        # Check existence of fcp utility in ffs repository, after compiling.
        l_cmd = "test -f %s/fcp/fcp" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        self.assertEqual(int(l_res[0]), 0, "Compiling fcp utility is failed")

        # Check the PNOR flash contents on an x86 machine using fcp utility
        l_cmd = "%s/fcp/fcp -o 0x0 -L %s" % (l_workdir, l_file)
        l_res = commands.getstatusoutput(l_cmd)
        log.debug(l_res[1])
        self.assertEqual(int(l_res[0]), 0,
                         "Getting the PNOR data using fcp utility failed")
        log.debug("Getting PNOR data successfull using fcp utility")
