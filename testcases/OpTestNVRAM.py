#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestNVRAM.py $
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
#

'''
OpTestNVRAM
-----------

This testcase will deal with testing nvram partition
access functions like getting the list of partitions
print/update config data in all the supported partitions
'''

import time
import subprocess
import commands
import re
import sys
import os
import os.path

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed
import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class NVRAMUpdateError(Exception):
    def __init__(self, part, key, value, output):
        self.part = part
        self.key = key
        self.value = value
        self.output = output
    def __str__(self):
        return "Error Updating NVRAM partition '%s' with %s=%s. Output was %s" % (self.part, self.key, self.value, self.output)


class OpTestNVRAM(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def nvram_update_part_config(self, i_part, key='test-cfg', value='test-value'):
        part = i_part
        try:
            self.console.run_command("nvram -p %s --update-config '%s=%s'" % (part,key,value))
        except CommandFailed as cf:
            if "nvram: ERROR: partition name maximum length is 12" in cf.output:
                raise NVRAMUpdateError(i_part, key, value, ''.join(cf.output))

        try:
            res_list = self.console.run_command("nvram -p %s --print-config=%s" % (part,key))
        except CommandFailed as cf:
            if "nvram: ERROR: partition name maximum length is 12" in cf.output:
                raise NVRAMUpdateError(i_part, key, value, ''.join(cf.output))
        res = ''.join(res_list)
        if "test-value" in res:
            log.debug("Update config to the partition %s works fine" % part)
        else:
            raise NVRAMUpdateError(i_part, key, value, res)

    def doNVRAMTest(self, console):
        c = console
        self.console = c
        c.run_command("uname -a")
        c.run_command("cat /etc/os-release")
        c.run_command("nvram -v")
        try:
            c.run_command("nvram --print-config -p ibm,skiboot")
            c.run_command("nvram --print-config -p lnx,oops-log")
        except CommandFailed as cf:
            # These partitions may not exist, so not existing is not a failure
            log.debug(cf.output)
            m = re.match("nvram: ERROR: There is no.*partition", ''.join(cf.output))
            log.debug(repr(m))
            if not m:
                raise cf

        c.run_command("nvram --print-config -p common")

        with self.assertRaises(CommandFailed) as cm:
            c.run_command("nvram --print-config -p wwwwwwwwwwww")
            c.run_command("nvram --print-vpd")
            c.run_command("nvram --print-all-vpd")
            c.run_command("nvram --print-err-log")
            c.run_command("nvram --print-event-scan")
        self.assertEqual(cm.exception.exitcode, 255)

        c.run_command("nvram --partitions")
        c.run_command("nvram --dump common|head")
        try:
            c.run_command("nvram --dump ibm,skiboot|head")
            c.run_command("nvram --dump lnx,oops-log|head")
        except CommandFailed as cf:
            # These partitions may not exist, so not existing is not a failure
            log.debug(cf.output)
            m = re.match("nvram: ERROR: There is no.*partition", ''.join(cf.output))
            if not m:
                raise cf

        c.run_command("nvram --dump wwwwwwwwwwww|head")

        c.run_command("nvram --ascii common|head -c512; echo")
        try:
            c.run_command("nvram --ascii ibm,skiboot|head -c512; echo")
            c.run_command("nvram --ascii lnx,oops-log|head -c512; echo")
        except CommandFailed as cf:
            # These partitions may not exist, so not existing is not a failure
            log.debug(cf.output)
            m = re.match("nvram: ERROR: There is no.*partition", ''.join(cf.output))
            if not m:
                raise cf

        c.run_command("nvram --ascii wwwwwwwwwwww|head -c512; echo")

        try:
            self.nvram_update_part_config("common")
            self.nvram_update_part_config("ibm,skiboot")
            # below two are Disabled due to nvram off-by-one bug
            #self.nvram_update_part_config("lnx,oops-log")
            #self.nvram_update_part_config("wwwwwwwwwwww")
        except NVRAMUpdateError as e:
            self.fail(msg=str(e))

        try:
            self.nvram_update_part_config("a-very-long-and-invalid-name")
        except NVRAMUpdateError as e:
            self.assertEqual(e.part, "a-very-long-and-invalid-name")
        else:
            self.fail(msg="Expected to fail with NVRAM part name>12 but didn't")


class HostNVRAM(OpTestNVRAM):
    '''
    This function tests nvram partition access, print/update
    the config data and dumping the partition's data. All
    these operations are done on supported partitions in both
    host OS and Petitboot.
    '''
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.doNVRAMTest(self.cv_SYSTEM.cv_HOST.get_ssh_connection())

class SkirootNVRAM(OpTestNVRAM):
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        # Execute these tests in petitboot
        if not self.cv_SYSTEM.has_mtd_pnor_access():
            self.skipTest("OpTestSystem Skiroot does not have MTD PNOR access, probably running QEMU")
        self.doNVRAMTest(self.cv_SYSTEM.console)
