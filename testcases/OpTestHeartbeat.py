#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestHeartbeat.py $
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

#  @package OpTestHeartbeat
#  Heartbeat tests for OpenPower testing.
#
#  This class will test the functionality of ipmi heartbeat 
#  1. kopald service should be running by defaulut since host should poll OPAL at time interval requested by OPAL

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

class OpTestHeartbeat(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_IPMI.ipmi_host_set_unique_prompt()
        res = self.cv_IPMI.run_host_cmd_on_ipmi_console("ps -o comm|grep opal")
        print res
        self.assertIn("kopald", res, "kopald not running in petitboot");
