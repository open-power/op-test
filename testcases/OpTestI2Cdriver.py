#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestI2Cdriver.py $
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

# @package OpTestI2Cdriver
#  I2C driver to support openpower platform
#
#  This class will test functionality of following drivers
#  I2C Driver(Inter-Integrated Circuit) driver
#
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


class OpTestI2Cdriver():
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
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This function has following test steps
    #         1. Getting host information(OS and kernel info)
    #         2. Checking the required utilites are present on host or not
    #         3. Loading the necessary modules to test I2C device driver functionalites
    #            (i2c_dev, i2c_opal and at24)
    #         4. Getting the list of i2c buses
    #         5. Querying the i2c bus for devices
    #         3. Getting the list of i2c buses and eeprom chip addresses
    #         4. Accessing the registers visible through the i2cbus using i2cdump utility
    #         5. Listing the i2c adapter conetents and i2c bus entries to make sure sysfs entries
    #            created for each bus.
    #         6. Testing i2cget functionality for limited samples
    #            Avoiding i2cset functionality, it may damage the system.
    #
    # @return BMC_CONST.FW_SUCCESS-success or raise OpTestError-fail
    #
    def testI2Cdriver(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # make sure install "i2c-tools" package in-order to run the test

        # Check whether i2cdump, i2cdetect and hexdump commands are available on host
        self.cv_HOST.host_check_command("i2cdump")
        self.cv_HOST.host_check_command("i2cdetect")
        self.cv_HOST.host_check_command("hexdump")
        self.cv_HOST.host_check_command("i2cget")
        self.cv_HOST.host_check_command("i2cset")

        # Get Kernel Version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # loading i2c_opal module based on config option
        l_config = "CONFIG_I2C_OPAL"
        l_module = "i2c_opal"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # loading i2c_dev module based on config option
        l_config = "CONFIG_I2C_CHARDEV"
        l_module = "i2c_dev"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # loading at24 module based on config option
        l_config = "CONFIG_EEPROM_AT24"
        l_module = "at24"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Get information of EEPROM chips
        self.cv_HOST.host_get_info_of_eeprom_chips()

        # Get list of i2c buses available on host,
        # l_list=["0","1"....]
        # l_list1=["i2c-0","i2c-1","i2c-2"....]
        l_list, l_list1 = self.cv_HOST.host_get_list_of_i2c_buses()

        # Scanning i2c bus for devices attached to it.
        for l_bus in l_list:
            self.query_i2c_bus(l_bus)

        # Get list of pairs of i2c bus and EEPROM device addresses in the host
        l_chips = self.cv_HOST.host_get_list_of_eeprom_chips()
        for l_args in l_chips:
            # Accessing the registers visible through the i2cbus using i2cdump utility
            # l_args format: "0 0x51","1 0x53",.....etc
            self.i2c_dump(l_args)

        # list i2c adapter conetents
        l_res = self.cv_HOST.host_run_command("ls -l /sys/class/i2c-adapter; echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            pass
        else:
            l_msg = "listing i2c adapter contents through the sysfs entry failed"
            print l_msg
            raise OpTestError(l_msg)

        # Checking the sysfs entry of each i2c bus
        for l_bus in l_list1:
            l_res = self.cv_HOST.host_run_command("ls -l /sys/class/i2c-adapter/%s; echo $?" % l_bus)
            l_res = l_res.splitlines()
            if int(l_res[-1]) == 0:
                pass
            else:
                l_msg = "listing i2c bus contents through the sysfs entry failed"
                print l_msg
                raise OpTestError(l_msg)

        # Currently testing only getting the data from a data address, avoiding setting data.
        # Only four samples are gathered to check whether reading eeprom  data is working or not.
        # Setting eeprom data is dangerous and make your system UNBOOTABLE
        l_addrs = ["0x00", "0x10", "0x20", "0x30", "0x40", "0x50", "0x60", "0x70", "0x80", "0x90", "0xa0", "0xb0", "0xc0", "0xd0", "0xe0", "0xf0"]
        for l_addr in l_addrs:
            l_val = self.i2c_get(l_chips[1], l_addr)
            # self.i2c_set(l_list2[1], l_addr, "0x50")
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function query's the i2c bus for devices attached to it.
    #        i2cdetect is a utility to scan an I2C bus for devices
    #
    # @param i_bus @type string: i2c bus numer
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def query_i2c_bus(self, i_bus):
        print "Querying the i2c bus for devices attached to it"
        l_res = self.cv_HOST.host_run_command("i2cdetect -y %i; echo $?" % int(i_bus))
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Querying the i2cbus for devices failed:%s" % i_bus
            print l_msg
            raise OpTestError(l_msg)

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
            l_msg = "i2cdump failed for the device: %s" % i_args
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function i2cget read from I2C/SMBus chip registers
    #        command usage: i2cget [-f] [-y] i2cbus chip-address [data-address [mode]]
    #
    # @param i_args @type string: this is the argument to i2cget utility
    #                             args are in the form of "i2c-bus-number eeprom-chip-address"
    #                             Ex: "0 0x51","3 0x52" ....etc
    # @param i_addr @type string: this is the data-address on chip, from where data will be read
    #                             Ex: "0x00","0x10","0x20"...
    #
    # @return l_res @type string: data present on data-address or raise OpTestError
    #
    def i2c_get(self, i_args, i_addr):
        l_res = self.cv_HOST.host_run_command("i2cget -f -y %s %s;echo $?" % (i_args, i_addr))
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return l_res
        else:
            l_msg = "i2cget: Getting data from address %s failed" % i_addr
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function i2cset will be used for setting I2C registers
    #        command usage: i2cset [-f] [-y] [-m mask] [-r] i2cbus chip-address data-address [value] ...  [mode]
    #
    # @param i_args @type string: this is the argument to i2cset utility
    #                             args are in the form of "i2c-bus-number eeprom-chip-address"
    #                             Ex: "0 0x51","3 0x52" ....etc
    # @param i_addr @type string: this is the data-address on chip, where data will be set
    #                             Ex: "0x00","0x10","0x20"...
    # @param i_val @type string: this is the value which will be set into data-address i_addr
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def i2c_set(self, i_args, i_addr, i_val):
        l_res = self.cv_HOST.host_run_command("i2cset -f -y %s %s %s;echo $?" % (i_args, i_addr, i_val))
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "i2cset: Setting the data to a address %s failed" % i_addr
            print l_msg
            raise OpTestError(l_msg)
