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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpTestSystem


class OpTestAt24driver():
    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd,i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                 i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This function has following test steps
    #         1. Getting the host infromation(OS and kernel information)
    #         2. Loading the necessary modules to test at24 device driver functionalites
    #            (i2c_dev, i2c_opal and at24)
    #         3. Getting the list of i2c buses and eeprom chip addresses
    #         4. Accessing the registers visible through the i2cbus using i2cdump utility
    #         5. Getting the eeprom device data using hexdump utility in hex + Ascii format
    #
    # @return BMC_CONST.FW_SUCCESS-success or raise OpTestError
    #
    def testAt24driver(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Check whether i2cdump and hexdump commands are available on host
        self.cv_HOST.host_check_command("i2cdump")
        self.cv_HOST.host_check_command("hexdump")

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Loading i2c_opal module based on config option
        l_config = "CONFIG_I2C_OPAL"
        l_module = "i2c_opal"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Loading i2c_dev module based on config option
        l_config = "CONFIG_I2C_CHARDEV"
        l_module = "i2c_dev"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Loading at24 module based on config option
        l_config = "CONFIG_EEPROM_AT24"
        l_module = "at24"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Get infomtion of EEPROM chips
        self.cv_HOST.host_get_info_of_eeprom_chips()

        # Get list of pairs of i2c bus and EEPROM device addresses in the host
        l_chips = self.cv_HOST.host_get_list_of_eeprom_chips()
        for l_args in l_chips:
            # Accessing the registers visible through the i2cbus using i2cdump utility
            # l_args format: "0 0x51","1 0x53",.....etc
            self.i2c_dump(l_args)

        # Getting the list of sysfs eeprom interfaces
        l_res = self.cv_HOST.host_run_command("find /sys/ -name eeprom; echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            pass
        else:
            l_msg = "EEPROM sysfs entries are not created"
            print l_msg
            raise OpTestError(l_msg)
        for l_dev in l_res:
            if l_dev.__contains__("eeprom"):
                # Getting the eeprom device data using hexdump utility in hex + Ascii format
                self.cv_HOST.host_hexdump(l_dev)
            else:
                pass
        return BMC_CONST.FW_SUCCESS

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
        l_res = self.cv_HOST.host_run_command("i2cdump -f -y %s; echo $?" % i_args)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "i2cdump failed on addr %s" % i_args
            print l_msg
            raise OpTestError(l_msg)
