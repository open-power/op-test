#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEnergyScale.py $
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
OpTestEnergyScale
-----------------

While OpTestEM is concerned with runtime energy management such as
CPU frequency scaling and stop states, OpTestEnergyScale is concerned
with system level power consumption limits.

'''

import time
import subprocess
import commands
import re
import sys

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

class OpTestEnergyScale(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = conf.util
        self.cv_PLATFORM = conf.platform()

    def run_ipmi_cmd(self, i_cmd):
        l_cmd = i_cmd
        l_res = self.cv_IPMI.ipmitool.run(l_cmd)
        print(l_res)
        return l_res

    def get_platform_power_limits(self, i_platform):
        '''
        Get platform power limits. This is a hardcoded list for each
        platform type. We do not (yet) have a way to determine this
        dynamically.

        Returns a tuple of low_limit,high_limit.
        '''
        l_platform = i_platform
        if BMC_CONST.HABANERO in l_platform:
            l_power_limit_high = BMC_CONST.HABANERO_POWER_LIMIT_HIGH
            l_power_limit_low = BMC_CONST.HABANERO_POWER_LIMIT_LOW
        elif BMC_CONST.FIRESTONE in l_platform:
            l_power_limit_high = BMC_CONST.FIRESTONE_POWER_LIMIT_HIGH
            l_power_limit_low = BMC_CONST.FIRESTONE_POWER_LIMIT_LOW
        elif BMC_CONST.GARRISON in l_platform:
            l_power_limit_high = BMC_CONST.GARRISON_POWER_LIMIT_HIGH
            l_power_limit_low = BMC_CONST.GARRISON_POWER_LIMIT_LOW
        else:
            l_msg = "New platform, add power limit support to this platform and retry"
            raise OpTestError(l_msg)
        return l_power_limit_low, l_power_limit_high

class OpTestEnergyScaleStandby(OpTestEnergyScale):
    '''
    This test will test Energy scale features at standby state:

    1. Power OFF the system.
    2. Validate below Energy scale features at standby state ::

         ipmitool dcmi power get_limit                # Get the configured power limits.
         ipmitool dcmi power set_limit limit <value>  # Power Limit Requested in Watts.
         ipmitool dcmi power activate                 # Activate the set power limit.
         ipmitool dcmi power deactivate               # Deactivate the set power limit.

    3. Once platform power limit activated execute below dcmi commands at standby state. ::

         ipmitool dcmi discover                       # This command is used to discover supported  capabilities in DCMI.
         ipmitool dcmi power reading                  # Get power related readings from the system.
         ipmitool dcmi power get_limit                # Get the configured power limits.
         ipmitool dcmi power sensors                  # Prints the available DCMI sensors.
         ipmitool dcmi get_temp_reading               # Get Temperature Sensor Readings.

    4. Power ON the system.
    5. Check after system booted to runtime, whether occ's are active or not.
    6. Again in runtime execute all dcmi commands to check the functionality.
    '''
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        print("Energy Scale Test 1: Get, Set, activate and deactivate platform power limit at power off")
        l_power_limit_low, l_power_limit_high = self.get_platform_power_limits(self.cv_PLATFORM)

        self.cv_IPMI.ipmi_sdr_clear()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_activate_power_limit()
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_deactivate_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_low)
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_get_power_limit()
        print("Get All dcmi readings at power off")
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)


class OpTestEnergyScaleRuntime(OpTestEnergyScale):
    '''
    Test Energy scale features at runtime:

    1. Power OFF the system.
    2. Power On the system to boot to host OS
    3. Validate below Energy scale features at runtime state ::

        ipmitool dcmi power get_limit                # Get the configured power limits.
        ipmitool dcmi power set_limit limit <value>  # Power Limit Requested in Watts.
        ipmitool dcmi power activate                 # Activate the set power limit.
        ipmitool dcmi power deactivate               # Deactivate the set power limit.

    4. Once platform power limit activated execute below dcmi commands at runtime state. ::

        ipmitool dcmi discover                       # This command is used to discover supported  capabilities in DCMI.
        ipmitool dcmi power reading                  # Get power related readings from the system.
        ipmitool dcmi power get_limit                # Get the configured power limits.
        ipmitool dcmi power sensors                  # Prints the available DCMI sensors.
        ipmitool dcmi get_temp_reading               # Get Temperature Sensor Readings.

    5. Issue Power OFF/ON to check whether system boots after setting platform power limit at runtime.
    6. Again in runtime execute all dcmi commands to check the functionality.
    '''
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        print("Energy Scale Test 2: Get, Set, activate and deactivate platform power limit at runtime")
        l_power_limit_low, l_power_limit_high = self.get_platform_power_limits(self.cv_PLATFORM)

        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print(l_status)
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print("OCC's are up and active")
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_low)
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        self.cv_IPMI.ipmi_activate_power_limit()
        print(self.cv_IPMI.ipmi_get_power_limit())
        print("Get All dcmi readings at runtime")
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)

class OpTestEnergyScaleDCMIstandby(OpTestEnergyScale):
    '''
    Test below dcmi commands at both standby and runtime states ::

      ipmitool dcmi discover         # This command is used to discover supported  capabilities in DCMI.
      ipmitool dcmi power reading    # Get power related readings from the system.
      ipmitool dcmi power get_limit  # Get the configured power limits.
      ipmitool dcmi power sensors    # Prints the available DCMI sensors.
      ipmitool dcmi get_temp_reading # Get Temperature Sensor Readings.
      ipmitool dcmi get_mc_id_string # Get management controller identifier string.
      ipmitool dcmi get_conf_param   # Get DCMI Configuration Parameters.
      ipmitool dcmi oob_discover     # Ping/Pong Message for DCMI Discovery.
    '''
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        print("Energy scale Test 3: Get Sensors, Temperature and Power reading's at power off and runtime")
        print("Performing a IPMI Power OFF Operation")
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        rc = int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY))
        if rc == BMC_CONST.FW_SUCCESS:
            print("System is in standby/Soft-off state")
        elif rc == BMC_CONST.FW_PARAMETER:
            print("Host Status sensor is not available")
            print("Skipping stand-by state check")
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print("Get All dcmi readings at power off")
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)

class OpTestEnergyScaleDCMIruntime(OpTestEnergyScale):
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        print("Performing a IPMI Power ON Operation")
        # Perform a IPMI Power ON Operation
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print(l_status)
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print("OCC's are up and active")
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print("Get All dcmi readings at runtime")
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)

def runtime_suite():
    s = unittest.TestSuite()
    s.addTest(OpTestEnergyScaleRuntime())
    s.addTest(OpTestEnergyScaleDCMIruntime())
    return s;

def standby_suite():
    s = unittest.TestSuite()
    s.addTest(OpTestEnergyScaleStandby())
    s.addTest(OpTestEnergyScaleDCMIstandby())
    return s
