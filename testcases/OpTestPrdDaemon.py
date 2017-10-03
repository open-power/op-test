#!/usr/bin/python2
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

# @package OpTestPrdDaemon
#  PRD daemon for OpenPower testing.
#
#  This class will test the functionality of following.
#  PRD (Processor Runtime Diagnostic) daemon should always be running in HOST OS.
#  For testing out this feature, we require to kill the opal-prd daemon and make sure that the daemon spawns back always.

import time
import subprocess
import re
import sys
import os
import random
import commands


from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed


class OpTestPrdDaemon(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.bmc_type = conf.args.bmc_type


    ##
    # @brief This function performs below steps
    #        1. Initially connecting to host console for execution.
    #        2. Check for whether opal-prd daemon is running or not
    #           if it is, get the PID of the opal-prd daemon
    #        3. Kill the opal-prd daemon using its PID
    #        4. Again check if opal-prd daemon spawns back
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" in self.bmc_type:
            self.skipTest("OpenPower specific")
        # In P9 FSP systems we need to enable this test

        self.cv_SYSTEM.host_console_login()

        # To check opal-prd daemon is running or not
        l_res = self.cv_HOST.host_run_command("pidof opal-prd")

        # To kill the opal-prd daemon using its PID
        l_cmd = "kill -9 %d" % int(l_res[0])
        l_res = self.cv_HOST.host_run_command(l_cmd)

        # To check if opal-prd daemon is spawned again even after killing
        try:
            l_res = self.cv_HOST.host_run_command("pidof opal-prd")
        except CommandFailed as c:
            self.assertEqual(c.exitcode, 0, "opal-prd daemon is not running always:Need to raise a bug: %s" % str(c))

        print "opal-prd daemon is always running"

        return BMC_CONST.FW_SUCCESS

