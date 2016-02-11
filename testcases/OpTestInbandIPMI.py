#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestInbandIPMI.py $
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

#  @package OpTestInbandIPMI
#  Test the inband ipmi fucntionality package for OpenPower platform.
#
#  This class will test the functionality of following drivers
#  1. sdr
#  2. fru
#  3. chassis
#  4. mc
#  5. sel

import time
import subprocess
import re

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestLpar import OpTestLpar
from common.OpTestUtil import OpTestUtil

class OpTestInbandIPMI():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This function will cover following test steps
    #        1. It will get the OS level installed on powernv platform
    #        2. It will check for kernel version installed on the Open Power Machine 
    #        3. It will check for ipmitool command existence and ipmitool package
    #        4. Checking Inband ipmitool command functionality with different options
    #           using ipmitool.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_ipmi_inband_functionality(self):

        # Get OS level
        l_oslevel = self.cv_LPAR.lpar_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_LPAR.lpar_get_kernel_version()

        # Checking for ipmitool command and lm_sensors package
        self.cv_LPAR.lpar_check_command("ipmitool")

        l_pkg = self.cv_LPAR.lpar_check_pkg_for_utility(l_oslevel, "ipmitool")
        print "Installed package: %s" % l_pkg


        # Checking Inband ipmitool command functionality with different options
        l_cmd = "ipmitool sdr; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sdr not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool sdr elist full; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sdr elist full not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool sdr type temperature; echo $?"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        if l_res.__contains__("Temp"):
            print "ipmitool sdr type temperature is working"
        else:
            l_msg = "ipmitool sdr type temperature is not working"
            raise OpTestError(l_msg)


        l_cmd = "ipmitool lan print 1; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool lan print command is not working,exiting...."
            raise OpTestError(l_msg)


        l_cmd = "ipmitool fru print; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool fru print is not working,exiting...."
            raise OpTestError(l_msg)


        l_cmd = "ipmitool chassis status | grep \"System Power\""
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        if l_res.__contains__("System Power         : on"):
            print "ipmitool Chassis status is working"
        else:
            l_msg = "ipmitool chassis status is not working"
            raise OpTestError(l_msg)

        l_cmd = "ipmitool chassis identify 1; echo $?"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        if l_res.__contains__("Chassis identify interval: 1 seconds"):
            print "ipmitool Chassis identify interval is working"
        else:
            l_msg = "ipmitool Chassis identify interval is not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool chassis identify force; echo $?"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        if l_res.__contains__("Chassis identify interval: indefinite"):
            print "ipmitool Chassis identify interval is working"
        else:
            l_msg = "ipmitool Chassis identify interval is not working"
            raise OpTestError(l_msg)


        l_cmd = "ipmitool sensor list; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sensor list is not working,exiting...."
            raise OpTestError(l_msg)


        l_cmd = "ipmitool mc info; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool mc info is not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool mc selftest; echo $?"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        if l_res.__contains__("Selftest: passed"):
            print "ipmitool mc selftest is passed"
        else:
            l_msg = "ipmitool mc selftest is failing"
            raise OpTestError(l_msg)

        l_cmd = "ipmitool mc getenables; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool mc getenables is not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool mc watchdog get; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool mc watchdog get is not working,exiting...."
            raise OpTestError(l_msg)



        l_cmd = "ipmitool sel info; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sel info is not working,exiting...."
            raise OpTestError(l_msg)

        l_cmd = "ipmitool sel list; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sel list is not working,exiting...."
            raise OpTestError(l_msg)


        l_cmd = "ipmitool sel list last 3 | grep \"PCI resource configuration\" | awk \'{ print $1 }\'"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        l_cmd = "ipmitool sel get 0x" + response[1] + "; echo $?"
        output = self.cv_LPAR.lpar_run_command(l_cmd)
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "ipmitool sel get is not working,exiting...."
            raise OpTestError(l_msg)
        
        return BMC_CONST.FW_SUCCESS
