#!/usr/bin/python
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

#  @package OpTestEnergyScale.py
#  

import time
import subprocess
import commands
import re
import sys

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestEnergyScale():
    ##  Initialize this object
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
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This function will test Energy scale features at standby state
    #         1. Power OFF the system.
    #         2. Validate below Energy scale features at standby state
    #            ipmitool dcmi power get_limit                :Get the configured power limits.
    #            ipmitool dcmi power set_limit limit <value>  :Power Limit Requested in Watts.
    #            ipmitool dcmi power activate                 :Activate the set power limit.
    #            ipmitool dcmi power deactivate               :Deactivate the set power limit.
    #         3. Once platform power limit activated execute below dcmi commands at standby state.
    #            ipmitool dcmi discover                       :This command is used to discover  
    #                                                           supported  capabilities in DCMI.
    #            ipmitool dcmi power reading                  :Get power related readings from the system.
    #            ipmitool dcmi power get_limit                :Get the configured power limits.
    #            ipmitool dcmi power sensors                  :Prints the available DCMI sensors.
    #            ipmitool dcmi get_temp_reading               :Get Temperature Sensor Readings.
    #         4. Power ON the system.
    #         5. Check after system booted to runtime, whether occ's are active or not.
    #         6. Again in runtime execute all dcmi commands to check the functionality.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_energy_scale_at_standby_state(self):
        print "Energy Scale Test 1: Get, Set, activate and deactivate platform power limit at power off"
        l_power_limit_low, l_power_limit_high = self.cv_IPMI.ipmi_get_platform_power_limits()
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_sdr_clear()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_activate_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_activate_power_limit()
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_deactivate_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_low)
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_get_power_limit()
        print "Get All dcmi readings at power off"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)
        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print self.cv_IPMI.ipmi_get_power_limit()
        print "Get All dcmi readings at runtime"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)


    ##
    # @brief  This function will test Energy scale features at standby state
    #         1. Power OFF the system.
    #         2. Power On the system to boot to host OS
    #         2. Validate below Energy scale features at runtime state
    #            ipmitool dcmi power get_limit                :Get the configured power limits.
    #            ipmitool dcmi power set_limit limit <value>  :Power Limit Requested in Watts.
    #            ipmitool dcmi power activate                 :Activate the set power limit.
    #            ipmitool dcmi power deactivate               :Deactivate the set power limit.
    #         3. Once platform power limit activated execute below dcmi commands at runtime state.
    #            ipmitool dcmi discover                       :This command is used to discover  
    #                                                           supported  capabilities in DCMI.
    #            ipmitool dcmi power reading                  :Get power related readings from the system.
    #            ipmitool dcmi power get_limit                :Get the configured power limits.
    #            ipmitool dcmi power sensors                  :Prints the available DCMI sensors.
    #            ipmitool dcmi get_temp_reading               :Get Temperature Sensor Readings.
    #         4. Issue Power OFF/ON to check whether system boots after setting platform power limit at runtime.
    #         5. Again in runtime execute all dcmi commands to check the functionality.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_energy_scale_at_runtime_state(self):
        print "Energy Scale Test 2: Get, Set, activate and deactivate platform power limit at runtime"
        l_power_limit_low, l_power_limit_high = self.cv_IPMI.ipmi_get_platform_power_limits()

        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print "Get All dcmi readings at power off"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)
        self.cv_IPMI.ipmi_sdr_clear()
        print self.cv_IPMI.ipmi_get_power_limit()
        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_high)
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_set_power_limit(l_power_limit_low)
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_deactivate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        self.cv_IPMI.ipmi_activate_power_limit()
        print self.cv_IPMI.ipmi_get_power_limit()
        print "Get All dcmi readings at runtime"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print "Get All dcmi readings at runtime"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)

    ##
    # @brief  This function will test below dcmi commands at both standby and runtime states
    #            ipmitool dcmi discover                       :This command is used to discover  
    #                                                           supported  capabilities in DCMI.
    #            ipmitool dcmi power reading                  :Get power related readings from the system.
    #            ipmitool dcmi power get_limit                :Get the configured power limits.
    #            ipmitool dcmi power sensors                  :Prints the available DCMI sensors.
    #            ipmitool dcmi get_temp_reading               :Get Temperature Sensor Readings.
    #            ipmitool dcmi get_mc_id_string               :Get management controller identifier string.
    #            ipmitool dcmi get_conf_param                 :Get DCMI Configuration Parameters.
    #            ipmitool dcmi oob_discover                   :Ping/Pong Message for DCMI Discovery.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_dcmi_at_standby_and_runtime_states(self):
        print "Energy scale Test 3: Get Sensors, Temperature and Power reading's at power off and runtime"
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print "Get All dcmi readings at power off"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)
        print "Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
        else:
            l_msg = "OCC's are not in active state"
            raise OpTestError(l_msg)
        print "Get All dcmi readings at runtime"
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)


    ##
    # @brief  It will execute and test the return code of ipmi command.
    #
    # @param i_cmd @type string:The ipmitool command, for example: chassis power on; echo $?
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def run_ipmi_cmd(self, i_cmd):
        l_cmd = i_cmd
        l_res = self.cv_IPMI.ipmitool_execute_command(l_cmd)
        print l_res
        l_res = l_res.splitlines()
        if int(l_res[-1]):
            l_msg = "IPMI: command failed %c" % l_cmd
            raise OpTestError(l_msg)
        return l_res
