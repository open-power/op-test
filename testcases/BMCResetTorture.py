#!/usr/bin/env python3
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

'''
BMCResetTorture
---------------

This testcase does BMC reset torture in different scenarios.
'''

import time
import subprocess
import subprocess
import re
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class RuntimeBMCResetTorture(unittest.TestCase):
    '''
    Repeatedly does the BMC Reset at runtime (i.e at both skiroot and host)
    '''
    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.test = None

    def setUp(self):
        if self.test == "host":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        elif self.test == "skiroot":
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    def RunBMCReset(self):
        log.debug("Test BMC Cold reset versus Host Firmware Status")
        con = self.cv_SYSTEM.console
        for i in range(0, 256):
            log.debug("Issuing BMC Cold reset iteration %s" % i)
            self.cv_SYSTEM.sys_cold_reset_bmc()
            con = self.cv_SYSTEM.console
            if self.test == "host":
                con.run_command("uname -a")
                con.run_command_ignore_fail(
                    "PATH=/usr/local/sbin:$PATH getscom -l")
                con.run_command_ignore_fail("sensors")
                con.run_command_ignore_fail("ipmitool sdr elist")
                con.run_command("lspci")
            if "skiroot" in self.test:
                cmd = "dmesg -r|grep '<[4321]>'"
            elif "host" in self.test:
                cmd = "dmesg -T --level=emerg,alert,crit,err,warn"
            con.run_command_ignore_fail(cmd)
            con.run_command_ignore_fail(
                "grep ',[0-4]\]' /sys/firmware/opal/msglog")


class Skiroot(RuntimeBMCResetTorture, unittest.TestCase):
    def setUp(self):
        self.test = "skiroot"
        super(Skiroot, self).setUp()

    def runTest(self):
        self.RunBMCReset()


class Host(RuntimeBMCResetTorture, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(Host, self).setUp()

    def runTest(self):
        self.RunBMCReset()


class StandbyBMCResetTorture(RuntimeBMCResetTorture, unittest.TestCase):
    '''
    Repeatedly does the BMC reset at standby state
    '''

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

    def runTest(self):
        log.debug("BMC Reset Torture test for 256 cycles...")
        for i in range(0, 256):
            log.debug("Issuing BMC Cold reset iteration %s" % i)
            self.cv_SYSTEM.sys_cold_reset_bmc()


class BMCResetvsHostIPLTorture(RuntimeBMCResetTorture, unittest.TestCase):
    '''
    Repeatedly does the BMC Reset vs Host IPL Torture
    '''

    def setUp(self):
        pass

    def runTest(self):
        log.debug("BMC Reset vs Host IPL Torture test for 256 cycles...")
        for i in range(0, 256):
            log.debug("Issuing BMC Cold reset iteration %s" % i)
            self.cv_SYSTEM.sys_cold_reset_bmc()
            self.c = self.cv_SYSTEM.console
            log.debug("Boot iteration %d..." % i)
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c.run_command_ignore_fail("dmesg -r|grep '<[4321]>'")
            self.c.run_command_ignore_fail(
                "grep ',[0-4]\]' /sys/firmware/opal/msglog")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
