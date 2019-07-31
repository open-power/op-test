#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpalGard.py $
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
opal-gard
---------

Test different OPAL GARD Related functionality
'''

import re
import random

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpalGard(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def list_gard_records(self):
        cmd = "PATH=/usr/local/sbin:$PATH opal-gard list all"
        try:
            res = self.c.run_command(cmd, timeout=120)
        except CommandFailed as cf:
            self.assertEqual(
                cf.exitcode, 0, "List gard records operation failed: %s" % str(cf))

    def clear_gard_records(self):
        cmd = "PATH=/usr/local/sbin:$PATH opal-gard clear all"
        try:
            res = self.c.run_command(cmd, timeout=240)
        except CommandFailed as cf:
            self.assertEqual(
                cf.exitcode, 0, "Clear gard records operation failed: %s" % str(cf))

    def show_gard_record(self, id):
        cmd = "PATH=/usr/local/sbin:$PATH opal-gard show %s" % id
        try:
            res = self.c.run_command(cmd, timeout=240)
        except CommandFailed as cf:
            self.assertEqual(
                cf.exitcode, 0, "show gard records operation failed: %s" % str(cf))

    def tearDown(self):
        cmd = "dmesg -T --level=alert,crit,err,warn"
        res = self.c.run_command_ignore_fail(cmd, timeout=120)
        self.c.run_command_ignore_fail(
            "grep ',[0-4]\]' /sys/firmware/opal/msglog")

    def runTest(self):
        # opal-gard from host is not supported in FSP systems
        if "FSP" in self.bmc_type:
            self.skipTest("OpenPOWER BMC specific")

        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.cv_HOST.host_check_command("pflash")
        self.cv_HOST.host_copy_fake_gard()
        self.c.run_command("dmesg -D")
        data = self.cv_HOST.host_pflash_get_partition("GUARD")
        try:
            offset = hex(data["offset"]//16)
        except Exception as e:
            self.assertTrue(
                False, "OpenPOWER BMC unable to find valid offset for partition=GUARD")
        for i in range(0, 11):
            self.list_gard_records()
            self.c.run_command(
                "dd if=/tmp/fake.gard of=/dev/mtd0 bs=$((0x10)) seek=$((%s)) conv=notrunc" % offset)
            self.list_gard_records()
            self.show_gard_record("00000001")
            self.clear_gard_records()
