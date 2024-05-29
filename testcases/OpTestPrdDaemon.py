#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPrdDaemon.py $
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
OpTestPrdDaemon
---------------

PRD daemon for OpenPower testing.

This class will test the functionality of following.

- PRD (Processor Runtime Diagnostic) daemon should always be running in
  HOST OS.
- For testing out this feature, we require to kill the opal-prd daemon
  and make sure that the daemon spawns back always.
'''

import time


from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestPrdDaemon(unittest.TestCase):
    '''
    This function performs below steps

    1. Initially connecting to host console for execution.
    2. Check for whether opal-prd daemon is running or not
       if it is, get the PID of the opal-prd daemon
    3. Kill the opal-prd daemon using its PID
    4. Again check if opal-prd daemon spawns back
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.bmc_type = conf.args.bmc_type

    def runTest(self):
        l_res = None

        if not self.cv_HOST.host_prd_supported(self.bmc_type):
            log.debug(
                "opal-prd NOT supported on this system, bmc_type={}".format(self.bmc_type))
            self.skipTest("opal-prd.service is NOT supported on this system")

        # Check opal-prd command
        self.cv_HOST.host_check_command("opal-prd")

        # To check opal-prd daemon is running or not
        try:
            l_res = self.cv_HOST.host_run_command("pidof opal-prd")
            log.debug("pidof opal-prd output={}".format(l_res))
        except CommandFailed:
            try:
                start_res = self.cv_HOST.host_run_command(
                    "/bin/systemctl start opal-prd.service")
                log.debug(
                    "We had to attempt startng opal-prd (which means it was NOT running) output={}".format(start_res))
                l_res = self.cv_HOST.host_run_command("pidof opal-prd")
                log.debug(
                    "Second attempt pidof opal-prd output={}".format(l_res))
            except CommandFailed as c:
                log.debug(
                    "CommandFailed starting or getting pidof opal-prd, we probably didn't get a PID")
                self.assertEqual(
                    c.exitcode, 0, "We failed to start the opal-prd.service, raise a bug: {}".format(c))

        # Kill the opal-prd daemon using its PID
        try:
            l_cmd = "kill -9 %d" % int(l_res[0])
            l_res = self.cv_HOST.host_run_command(l_cmd)
            log.debug("kill -9 output={}".format(l_res))
        except CommandFailed as c:
            log.debug(
                "CommandFailed trying to kill opal-prd.service, CommandFailed={}".format(c))
            self.assertEqual(
                c.exitcode, 0, "We failed to kill the opal-prd.service (it may have died) raise a bug: {}".format(c))

        # Check if opal-prd daemon is spawned again after killing
        try:
            time.sleep(5)  # give time to either die or stay alive
            l_res = self.cv_HOST.host_run_command("pidof opal-prd")
            log.debug(
                "Verify opal-prd.service pidof opal-prd output={}".format(l_res))
        except CommandFailed as c:
            log.debug(
                "CommandFailed getting pidof opal-prd, we probably didn't get a PID")
            self.assertEqual(
                c.exitcode, 0, "We were not able to keep the opal-prd.service running, raise a bug: {}".format(c))

        log.debug("opal-prd.service was able to stay running!")

        return BMC_CONST.FW_SUCCESS
