#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestAt24driver.py $
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

# @package OpTestAt24driver
#  At24(Atmel24) eeprom driver to support openpower platform
#
#  This driver has following functionalities.
#  'at24' is the i2c client driver that interface the EEPROMs on the system.
#   In P8 system, EEPROM devices contain the system VPDs information and this
#   driver is capable of reading and programming the data to these devices.
#

import time
import subprocess
import re
import sys

import unittest

import OpTestConfiguration
from testcases.I2C import I2C
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed, KernelModuleNotLoaded, KernelConfigNotSet
import difflib

class AT24driver(I2C, unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()
        self.test = "host"

    def at24_init(self):
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Check whether i2cdump and hexdump commands are available on host
        self.cv_HOST.host_check_command("i2cdump", "hexdump")

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        mods = {"CONFIG_I2C_OPAL": "i2c_opal",
                "CONFIG_I2C_CHARDEV": "i2c_dev",
                "CONFIG_EEPROM_AT24": "at24"
            }

        try:
            for (c,m) in mods.items():
                self.cv_HOST.host_load_module_based_on_config(l_kernel, c, m)
        except KernelConfigNotSet as ns:
            self.assertTrue(False, str(ns))
        except KernelModuleNotLoaded as km:
            if km.module == "at24":
                pass # We can fail if we don't load it, not all systems have it
            else:
                self.assertTrue(False, str(km))

        # Get infomtion of EEPROM chips
        self.host_get_info_of_eeprom_chips()

    ##
    # @brief  This function has following test steps
    #         1. Getting the host infromation(OS and kernel information)
    #         2. Loading the necessary modules to test at24 device driver functionalites
    #            (i2c_dev, i2c_opal and at24)
    #         3. Getting the list of i2c buses and eeprom chip addresses
    #         4. Accessing the registers visible through the i2cbus using i2cdump utility
    #         5. Getting the eeprom device data using hexdump utility in hex + Ascii format

    def runTest(self):
        self.set_up()

        if self.test == "host":
            self.at24_init()

        # Get list of pairs of i2c bus and EEPROM device addresses in the host
        l_chips = self.host_get_list_of_eeprom_chips()
        if self.cv_SYSTEM.has_host_accessible_eeprom():
            self.assertNotEqual(len(l_chips), 0, "No EEPROMs detected, while OpTestSystem says there should be")
        else:
            self.assertEqual(len(l_chips), 0)

        # Getting the list of sysfs eeprom interfaces
        try:
            l_res = self.c.run_command("find /sys/ -name eeprom")
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0, "EEPROM sysfs entries are not created")

        for l_dev in l_res:
            if l_dev.__contains__("eeprom"):
                # Getting the eeprom device data using hexdump utility in hex + Ascii format
                self.host_hexdump(l_dev)
            else:
                pass
        pass

    def diff_commands(self, cmds, i_dev, err="Result doesn't match"):
        last_r = None
        last_cmd = None
        for cmd in cmds:
            r = None
            try:
                r = self.c.run_command(cmd)
                r = [x+'\n' for x in r]
            except CommandFailed as cf:
                self.assertEqual(cf.exitcode, 0, "i2cdump failed on addr %s" % i_dev)
            if last_r is not None:
                diff = ''
                for l in difflib.unified_diff(r, last_r,fromfile=last_cmd,tofile=cmd):
                    diff = diff + l
                print diff
                self.assertMultiLineEqual(''.join(r),''.join(last_r), "%s:\n%s" % (err,diff))
            last_r = r
            last_cmd = cmd

    def host_hexdump(self, i_dev):
        cmds = ["hexdump -C %s" % i_dev] * 5
        self.diff_commands(cmds, i_dev, err="hexdump of EEPROM doesn't match")

class SkirootAT24(AT24driver, unittest.TestCase):
    def setUp(self):
        self.test = "skiroot"
        super(AT24driver, self).setUp()
