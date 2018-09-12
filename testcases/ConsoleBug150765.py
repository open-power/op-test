#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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
Console Bug 150765
------------------

A regresion test for a specific bug observed on FSP based systems.

Make sure ipmi sol console is connected before running this test
Observe sol console messages while system IPL's for two times
For second IPL, Petitboot Kernel messages will not come on active
SOL console.
'''

import time
import subprocess
import re
import pexpect
import threading

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState


class ConsoleBug150765(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.util = self.cv_SYSTEM.util
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific console test")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_power_on()
        self.cv_FSP.wait_for_runtime()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_SYSTEM.set_state(OpSystemState.PETITBOOT)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_power_on()
        self.cv_FSP.wait_for_runtime()
