#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017, 2018
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

'''
System Login
------------

Really simple tests to ensure we can simply log into a booted host.
'''

import time
import subprocess
import commands
import re
import sys
import os

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
import common.OpTestQemu as OpTestQemu
import common.OpTestMambo as OpTestMambo

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OOBHostLogin(unittest.TestCase):
    '''
    Log into the host via out of band console and run different commands
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        l_con = self.cv_SYSTEM.console
        r = l_con.run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = l_con.run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)
        for i in range(2):
            l_con.run_command("dmesg|tail", timeout=60)
        l_con.run_command("lscpu")
        try:
            r = l_con.run_command("sleep 2", timeout=10)
        except CommandFailed as r:
            log.debug(str(r))
        l_con.run_command("lscpu")

class BMCLogin(unittest.TestCase):
    '''
    Log into the BMC via SSH and run different commands
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()

    def runTest(self):
        if (isinstance(self.cv_BMC, OpTestMambo.OpTestMambo)) \
            or (isinstance(self.cv_BMC, OpTestQemu.OpTestQemu)):
                raise unittest.SkipTest("QEMU/Mambo so skipping BMCLogin test")
        r = self.cv_BMC.run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = self.cv_BMC.run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)
        for i in range(2):
            self.cv_BMC.run_command("dmesg")

class SSHHostLogin(unittest.TestCase):
    '''
    Log into the host via SSH and run different commands
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        r = self.cv_HOST.host_run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = self.cv_HOST.host_run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)
        for i in range(2):
            self.cv_HOST.host_run_command("dmesg")
        self.cv_HOST.host_run_command("whoami")
        self.cv_HOST.host_run_command("sudo -s")
        self.cv_HOST.host_run_command("lscpu")
        try:
            r = self.cv_HOST.host_run_command("echo \'hai\';sleep 20", timeout=10)
        except CommandFailed as r:
            log.debug(str(r))
        self.cv_HOST.host_run_command("whoami")
        self.cv_HOST.host_run_command("lscpu")

class ExampleRestAPI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific Rest API Tests")
        self.cv_SYSTEM.sys_inventory()
        self.cv_SYSTEM.sys_sensors()
        self.cv_SYSTEM.sys_bmc_state()

def system_access_suite():
    s = unittest.TestSuite()
    s.addTest(OOBHostLogin())
    s.addTest(BMCLogin())
    s.addTest(SSHHostLogin())
    s.addTest(ExampleRestAPI())
    return s
