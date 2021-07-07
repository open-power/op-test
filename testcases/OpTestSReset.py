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

'''
SRESET
----------

SRESET helps to trigger dump configured on system when the system and console
is in hung state.
'''

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import HTTPCheck
from common.OpTestError import OpTestError

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class sreset(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        if "OpenBMC" not in conf.args.bmc_type:
            raise unittest.SkipTest("SRESET test supported only on OpenBMC") 
        self.cv_HOST = conf.host()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = self.cv_SYSTEM.bmc
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.c = self.cv_SYSTEM.console

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.crash_content = self.c.run_command(
            "ls -l /var/crash | awk '{print $9}'")
        self.crash_content.pop(0)

    def verify_dump_file(self):
        crash_content_after = self.c.run_command(
            "ls -l /var/crash | awk '{print $9}'")
        crash_content_after.pop(0)
        self.crash_content = list(
            set(crash_content_after) - set(self.crash_content))
        if len(self.crash_content):
            self.c.run_command("ls /var/crash/%s/vmcore*" %
                               self.crash_content[0])
        else:
            msg = "Dump Directory not created"
            raise opTestError(msg)
        self.c.run_command("rm -rf /var/crash/%s" % self.crash_content[0])

    def runTest(self):
        self.cv_REST.is_sreset_supported()
        self.setup_test()
        os_level = self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_run_command("stty cols 300;stty rows 30")
        if self.cv_HOST.host_check_pkg_kdump(os_level) is False:
            self.cv_HOST.host_enable_kdump_service(os_level)
        self.cv_REST.inject_sreset()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.verify_dump_file()

