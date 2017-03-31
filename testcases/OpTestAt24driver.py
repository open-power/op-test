#!/usr/bin/python
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
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed, KernelModuleNotLoaded, KernelConfigNotSet

class OpTestAt24driver(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()

    ##
    # @brief  This function has following test steps
    #         1. Getting the host infromation(OS and kernel information)
    #         2. Loading the necessary modules to test at24 device driver functionalites
    #            (i2c_dev, i2c_opal and at24)
    #         3. Getting the list of i2c buses and eeprom chip addresses
    #         4. Accessing the registers visible through the i2cbus using i2cdump utility
    #         5. Getting the eeprom device data using hexdump utility in hex + Ascii format

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
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
        self.cv_HOST.host_get_info_of_eeprom_chips()

        # Get list of pairs of i2c bus and EEPROM device addresses in the host
        l_chips = self.cv_HOST.host_get_list_of_eeprom_chips()
        if self.cv_SYSTEM.has_host_accessible_eeprom():
            self.assertNotEqual(len(l_chips), 0, "No EEPROMs detected, while OpTestSystem says there should be")
        else:
            self.assertEqual(len(l_chips), 0)
        for l_args in l_chips:
            # Accessing the registers visible through the i2cbus using i2cdump utility
            # l_args format: "0 0x51","1 0x53",.....etc
            self.i2c_dump(l_args)

        # Getting the list of sysfs eeprom interfaces
        try:
            l_res = self.cv_HOST.host_run_command("find /sys/ -name eeprom")
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0, "EEPROM sysfs entries are not created")

        for l_dev in l_res:
            if l_dev.__contains__("eeprom"):
                # Getting the eeprom device data using hexdump utility in hex + Ascii format
                self.cv_HOST.host_hexdump(l_dev)
            else:
                pass
        pass

    ##
    # @brief This i2cdump function takes arguments in pair of a string like "i2cbus address".
    #        i2cbus indicates the number or name of the I2C bus to be scanned. This number should
    #        correspond  to  one  of  the busses listed by i2cdetect -l. address indicates
    #        the address to be scanned on that bus, and is an integer between 0x03 and 0x77
    #        i2cdump is a program to examine registers visible through the I2C bus
    #
    # @param i_args @type string: this is the argument to i2cdump utility
    #                             args are in the form of "i2c-bus-number eeprom-chip-address"
    #                             Ex: "0 0x51","3 0x52" ....etc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def i2c_dump(self, i_args):
        try:
            l_res = self.cv_HOST.host_run_command("i2cdump -f -y %s" % i_args)
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 0, "i2cdump failed on addr %s" % i_args)

