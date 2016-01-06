#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestSensors.py $
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

#  @package OpTestSensors
#  Sensors package for OpenPower testing.
#
#  This class will test the functionality of following drivers
#  1. Hardware monitoring sensors(hwmon driver) using sensors utility

import time
import subprocess
import re

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestLpar import OpTestLpar
from common.OpTestUtil import OpTestUtil


class OpTestSensors():
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
    #        1. It will check for kernel config option CONFIG_SENSORS_IBMPOWERNV
    #        2. It will load ibmpowernv driver only on powernv platform
    #        3. It will check for sensors command existence and lm_sensors package
    #        4. start the lm_sensors service and detect any sensor chips
    #           using sensors-detect.
    #        5. At the end it will test sensors command functionality
    #           with different options
    #
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_hwmon_driver(self):

        # Get OS level
        l_oslevel = self.cv_LPAR.lpar_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_LPAR.lpar_get_kernel_version()

        # Checking for sensors config option CONFIG_SENSORS_IBMPOWERNV
        l_config = "CONFIG_SENSORS_IBMPOWERNV"

        l_val = self.cv_LPAR.lpar_check_config(l_kernel, l_config)
        if l_val == "y":
            print "Driver build into kernel itself"
        else:
            print "Driver will be built as module"

        # Loading ibmpowernv driver only on powernv platform
        self.cv_LPAR.lpar_load_ibmpowernv(l_oslevel)

        # Checking for sensors command and lm_sensors package
        self.cv_LPAR.lpar_check_command("sensors")

        l_pkg = self.cv_LPAR.lpar_check_pkg_for_utility(l_oslevel, "sensors")
        print "Installed package: %s" % l_pkg

        # Restart the lm_sensor service
        self.cv_LPAR.lpar_start_lm_sensor_svc(l_oslevel)

        # To detect different sensor chips and modules
        res = self.cv_LPAR.lpar_run_command("yes | sensors-detect")
        print res

        # Checking sensors command functionality with different options
        output = self.cv_LPAR.lpar_run_command("sensors; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR.lpar_run_command("sensors -f; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -f not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR.lpar_run_command("sensors -A; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -A not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR.lpar_run_command("sensors -u; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -u not working,exiting...."
            raise OpTestError(l_msg)
        print output
        return BMC_CONST.FW_SUCCESS
