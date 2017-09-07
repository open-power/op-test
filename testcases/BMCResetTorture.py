#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/BMCResetTorture.py $
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

#  @package BMCResetTorture.py
#   This testcase does BMC reset torture in different scenarios.
#

import time
import subprocess
import commands
import re
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState


'''
Repeatedly does the BMC Reset at runtime (i.e at both skiroot and host)
'''
class RuntimeBMCResetTorture(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()

    def runTest(self):
        print "Test BMC Cold reset versus Host Firmware Status"
        self.setup_test()
        con = self.system.sys_get_ipmi_console()
        con.close()
        for i in range(0, 256):
            print "Issuing BMC Cold reset iteration %s" % i
            self.system.sys_cold_reset_bmc()
            con = self.system.sys_get_ipmi_console()
            if self.test == "host":
                self.system.host_console_login()
            self.system.host_console_unique_prompt()
            con.run_command("uname -a")
            con.run_command_ignore_fail("PATH=/usr/local/sbin:$PATH getscom -l")
            con.run_command_ignore_fail("sensors")
            con.run_command_ignore_fail("ipmitool sdr elist")
            con.run_command("lspci")
            if "skiroot" in self.test:
                cmd = "dmesg -r|grep '<[4321]>'"
            elif "host" in self.test:
                cmd = "dmesg -T --level=emerg,alert,crit,err,warn"
            con.run_command_ignore_fail(cmd)
            con.run_command_ignore_fail("grep ',[0-4]\]' /sys/firmware/opal/msglog")
            con.close()

class Skiroot(RuntimeBMCResetTorture, unittest.TestCase):
    def setup_test(self):
        self.test = "skiroot"
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

class Host(RuntimeBMCResetTorture, unittest.TestCase):
    def setup_test(self):
        self.test = "host"
        self.system.goto_state(OpSystemState.OS)

'''
Repeatedly does the BMC reset at standby state
'''
class StandbyBMCResetTorture(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.system.goto_state(OpSystemState.OFF)

    def runTest(self):
        print "BMC Reset Torture test for 256 cycles..."
        for i in range(0, 256):
            print "Issuing BMC Cold reset iteration %s" % i
            self.system.sys_cold_reset_bmc()

'''
Repeatedly does the BMC Reset vs Host IPL Torture
'''
class BMCResetvsHostIPLTorture(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()

    def runTest(self):
        print "BMC Reset vs Host IPL Torture test for 256 cycles..."
        for i in range(0, 256):
            print "Issuing BMC Cold reset iteration %s" % i
            self.system.sys_cold_reset_bmc()
            self.c = self.system.sys_get_ipmi_console()
            print "Boot iteration %d..." % i
            self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.system.host_console_unique_prompt()
            self.c.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            self.c.run_command_ignore_fail("grep ',[0-4]\]' /sys/firmware/opal/msglog")
            self.system.goto_state(OpSystemState.OFF)
            self.c.close()
