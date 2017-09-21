#!/usr/bin/python2
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
#

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

class KernelLog():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        if "skiroot" in self.test:
            cmd = "dmesg -r|grep '<[4321]>'"
        elif "host" in self.test:
            cmd = "dmesg -T --level=alert,crit,err,warn"
        else:
            raise Exception("Unknow test type")

        log_entries = self.c.run_command_ignore_fail(cmd)
        msg = '\n'.join(filter(None, log_entries))
        self.assertTrue( len(log_entries) == 0, "Warnings/Errors in Kernel log:\n%s" % msg)

class Skiroot(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "skiroot"
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class Host(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "host"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()
