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
#
#   Test Dropbear SSH is not present in skiroot
#
# The skiroot (pettiboot environment) firmware contains dropbear for it's ssh
# client functioanlity. We do not want to enable network accessable system in
# the environemnt for security reasons.
#
# This test ensures that the ssh server is not running at boot

import time
import subprocess
import commands
import re
import sys

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class PetitbootDropbearServer(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        print "Test Dropbear server not running in Petitboot"

        c = self.cv_SYSTEM.sys_get_ipmi_console()
        c.run_command("uname -a")
        # we don't grep for 'dropbear' so that our naive line.count
        # below doesn't hit a false positive.
        res = c.run_command("ps|grep drop")
        print res
        for line in res:
            if line.count('dropbear'):
                self.fail("drobear is running in the skiroot")
        pass
