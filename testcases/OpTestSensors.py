#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSensors.py $
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

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed


class OpTestSensors(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()

    def tearDown(self):
        if self.cv_SYSTEM.get_state() == OpSystemState.OS:
          self.cv_HOST.host_gather_opal_msg_log()
          self.cv_HOST.host_gather_kernel_log()

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
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Checking for sensors config option CONFIG_SENSORS_IBMPOWERNV
        l_config = "CONFIG_SENSORS_IBMPOWERNV"

        l_val = self.cv_HOST.host_check_config(l_kernel, l_config)
        if l_val == "y":
            print "Driver build into kernel itself"
        else:
            print "Driver will be built as module"
            # Loading ibmpowernv driver only on powernv platform
            self.cv_HOST.host_load_ibmpowernv(l_oslevel)

        # Checking for sensors command and lm_sensors package
        self.cv_HOST.host_check_command("sensors")

        l_pkg = self.cv_HOST.host_check_pkg_for_utility(l_oslevel, "sensors")
        print "Installed package: %s" % l_pkg

        # Restart the lm_sensor service
        self.cv_HOST.host_start_lm_sensor_svc(l_oslevel)

        # To detect different sensor chips and modules
        res = self.cv_HOST.host_run_command("yes | sensors-detect")

        # Checking sensors command functionality with different options
        try:
            for cmd in ["", "-f", "-A", "-u"]:
                response = self.cv_HOST.host_run_command("sensors " + cmd)
        except CommandFailed as c:
            self.assertEqual(c.exitcode, 0, str(c))

        return
