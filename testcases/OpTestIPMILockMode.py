#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestIPMILockMode.py $
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

#  @package OpTestIPMILockMode.py
#  It will test in-band ipmi white-listed commands when ipmi is in locked mode
#
#  IPMI whitelist
#  These are the commands that will be available over an unauthenticated
#  interface when the BMC is in IPMI lockdown mode.
#  Generally one can access all in-band ipmi commands, But if we issue ipmi
#  lock command then one can access only specific whitelisted in-band ipmi commands.

import time
import subprocess
import re, sys

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil

class OpTestIPMILockMode():
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
    # @brief This function will cover following test steps
    #        1. It will get the OS level installed on power platform
    #        2. It will check for kernel version installed on the Open Power Machine
    #        3. It will check for ipmitool command existence and ipmitool package
    #        4. Load the necessary ipmi modules based on config values
    #        5. Issue a ipmi lock command through out-of-band authenticated interface
    #        6. Now BMC IPMI is in locked mode, at this point only white listed
    #           in-band ipmi commands sholud work(No other in-band ipmi command should work)
    #        7. Execute and test the functionality of whitelisted in-band ipmi
    #           commands in locked mode
    #        8. At the end of test issue a ipmi unlock command to revert the availablity of all
    #           in-band ipmi commands in unlocked mode.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_ipmi_lock_mode(self):
        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Checking for ipmitool command and lm_sensors package
        self.cv_HOST.host_check_command("ipmitool")

        l_pkg = self.cv_HOST.host_check_pkg_for_utility(l_oslevel, "ipmitool")
        print "Installed package: %s" % l_pkg

        # loading below ipmi modules based on config option
        # ipmi_devintf, ipmi_powernv and ipmi_masghandler
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_DEVICE_INTERFACE,
                                                      BMC_CONST.IPMI_DEV_INTF)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_POWERNV,
                                                      BMC_CONST.IPMI_POWERNV)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_HANDLER,
                                                      BMC_CONST.IPMI_MSG_HANDLER)

        # Issue a ipmi lock command through authenticated interface
        print "Issuing ipmi lock command through authenticated interface"
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_LOCK_CMD)
        l_res = l_res.splitlines()
        if int(l_res[-1]):
            l_msg = "IPMI:Lock command failed, There may be two reasons here.\n\
                a. check the corresponding parches available in AMI driver code,\n\
                b. if patches available then command is failing"
            print l_msg
            raise OpTestError(l_msg)
        print "IPMI:Lock command executed successfully"

        try:
            self.run_inband_ipmi_whitelisted_cmds()
        except:
            l_msg = "One of white listed in-band ipmi command execution failed"
            print sys.exc_info()
        finally:
            # Issue a ipmi unlock command at the end of test.
            print "Issuing ipmi unlock command through authenticated interface"
            self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_UNLOCK_CMD)

    ##
    # @brief This function will execute whitelisted in-band ipmi commands
    #        and test the functionality in locked mode.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def run_inband_ipmi_whitelisted_cmds(self):
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")

        # Test IPMI white listed commands those should be allowed through un-authenticated
        # in-band interface
        # 1.[App] Get Device ID
        print "Testing Get Device ID command"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_DEVICE_ID)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Device ID command failed"
            raise OpTestError(l_msg)

        # 2.[App] Get Device GUID
        print "Testing Get Device GUID"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_DEVICE_GUID)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Device GUID command failed"
            raise OpTestError(l_msg)

        # 3.[App] Get System GUID
        print "Testing Get system GUID"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SYSTEM_GUID)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get System GUID command failed"
            raise OpTestError(l_msg)

        # 4.[Storage] Get SEL info
        print "Testing Get SEL info"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SEL_INFO)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get SEL info command failed"
            raise OpTestError(l_msg)

        # 5.[Storage] Get SEL time
        print "Testing Get SEL time"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SEL_TIME_RAW)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get SEL time command failed"
            raise OpTestError(l_msg)

        # 6. [Storage] Reserve SEL
        print "Testing Reserve SEL"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_RESERVE_SEL)
        if l_res[-1] != "0":
            l_msg = "IPMI: Reserve SEL command failed"
            raise OpTestError(l_msg)

        # 7. [Storage] Set SEL time (required for RTC)
        print "Testing Set SEL time"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SEL_TIME)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_SEL_TIME + " \'" + l_res[-1] + "\'; echo $?")
        if l_res[-1] != "0":
            l_msg = "IPMI: Set SEL time command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SEL_TIME)

        # 8. [Transport] Get LAN parameters
        print "Testing Get LAN parameters"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_LAN_PARAMETERS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get LAN parameters command failed"
            raise OpTestError(l_msg)

        # 9.[Chassis] Get System Boot Options
        print "Testing Get System Boot Options"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SYSTEM_BOOT_OPTIONS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get System Boot Options command failed"
            raise OpTestError(l_msg)

        # 10.[Chassis] Set System Boot Options
        print "Testing Set System Boot Options"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_SYTEM_BOOT_OPTIONS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Set System Boot Options command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SYSTEM_BOOT_OPTIONS)

        # 11. [App] Get BMC Global Enables
        print "Testing Get BMC Global Enables"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES_RAW)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get BMC Global Enables command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES)

        # 12. [App] Set BMC Global Enables
        print "Testing Set BMC Global Enables"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_BMC_GLOBAL_ENABLES_SEL_OFF)
        if l_res[-1] != "0":
            l_msg = "IPMI: Set BMC Global Enables sel=off command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_BMC_GLOBAL_ENABLES_SEL_ON)

        # 13.[App] Get System Interface Capabilities
        print "Testing Get System Interface Capabilities"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_SSIF)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get System Interface Capabilities SSIF command failed"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_KCS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get System Interface Capabilities KCS command failed"
            raise OpTestError(l_msg)

        # 14.[App] Get Message Flags
        print "Testing Get Message Flags"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_MESSAGE_FLAGS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Message Flags command failed"
            raise OpTestError(l_msg)

        # 15. [App] Get BT Capabilities
        print "Testing Get BT Capabilities"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_BT_CAPABILITIES)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get BT Capabilities command failed"
            raise OpTestError(l_msg)

        # 16. [App] Clear Message Flags
        print "Testing Clear Message Flags"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_CLEAR_MESSAGE_FLAGS)
        if l_res[-1] != "0":
            l_msg = "IPMI: Clear Message Flags command failed"
            raise OpTestError(l_msg)

        # 17. [OEM] PNOR Access Status
        print "Testing the PNOR Access Status"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_STATUS_DENY)
        if l_res[-1] != "0":
            l_msg = "IPMI: PNOR Access Status:deny command failed"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_STATUS_GRANT)
        if l_res[-1] != "0":
            l_msg = "IPMI: PNOR Access Status:grant command failed"
            raise OpTestError(l_msg)

        # 18. [Storage] Add SEL Entry
        print "Testing Add SEL Entry"
        print "Clearing the SEL list"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_ADD_SEL_ENTRY)
        if l_res[-1] != "0":
            l_msg = "IPMI: Add SEL Entry command failed"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_LIST_LAST_SEL_EVENT)
        print "Checking for Reserved entry creation in SEL"
        if "Reserved" not in l_res:
            l_msg = "IPMI: Add SEL Entry command, doesn't create an SEL event"
            raise OpTestError(l_msg)

        # 19. [App] Set Power State
        print "Testing Set Power State"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_ACPI_POWER_STATE)
        if l_res[-1] != "0":
            l_msg = "IPMI: Set Power State command failed"
            raise OpTestError(l_msg)

        # 20. [App] Set watchdog
        print "Testing Set watchdog"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_SET_WATCHDOG)
        if l_res[-1] != "0":
            l_msg = "IPMI: Set watchdog command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_MC_WATCHDOG_GET)

        # 21. [Sensor/Event] Get Sensor Type
        print "Testing Get Sensor Type"
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_SDR_GET_WATCHDOG)
        matchObj = re.search( "Watchdog \((0x\d{1,})\)", l_res)
        if matchObj:
            print "Got sensor Id for watchdog: %s" % matchObj.group(1)
        else:
            l_msg = "Failed to get sensor id for watchdog sensor"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SENSOR_TYPE_FOR_WATCHDOG + " " + matchObj.group(1) + " ;echo $?")
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Sensor Type command failed"
            raise OpTestError(l_msg)

        # 22.[Sensor/Event] Get Sensor Reading
        print "Testing Get Sensor Reading"
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_SDR_GET_WATCHDOG)
        matchObj = re.search( "Watchdog \((0x\d{1,})\)", l_res)
        if matchObj:
            print "Got sensor Id for watchdog: %s" % matchObj.group(1)
        else:
            l_msg = "Failed to get sensor id for watchdog sensor"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_SENSOR_READING + " " + matchObj.group(1) + " ;echo $?")
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Sensor Reading command failed"
            raise OpTestError(l_msg)

        # 23.[Sensor/Event] Platform Event (0x02)
        print "Testing Platform Event"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PLATFORM_EVENT)
        if l_res[-1] != "0":
            l_msg = "IPMI: Platform Event command failed"
            raise OpTestError(l_msg)
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_LIST_LAST_SEL_EVENT)
        if "Reserved" not in l_res:
            l_msg = "IPMI: Platform Event command failed to log SEL event"
            raise OpTestError(l_msg)

        # 24. [OEM] PNOR Access Response (0x08)
        print "Testing PNOR Access Response"
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_STATUS_GRANT)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_RESPONSE)
        if l_res[-1] != "0":
            l_msg = "IPMI: PNOR Access Response command failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_STATUS_DENY)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_PNOR_ACCESS_RESPONSE)
        if l_res[-1] != "0":
            l_msg = "IPMI: PNOR Access Response command failed"
            raise OpTestError(l_msg)

        # 25.[Chassis] Chassis Control
        print "Testing chassis power on"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_CHASSIS_POWER_ON)
        if l_res[-1] != "0":
            l_msg = "IPMI: chassis power on command failed"
            raise OpTestError(l_msg)

        # 26.[App] 0x38 Get Channel Authentication Cap
        print "Testing Get Channel Authentication Capabilities"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_CHANNEL_AUTH_CAP)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get Channel Authentication Capabilities command failed"
            raise OpTestError(l_msg)

        # 27.[App] Reset Watchdog (0x22)
        print "Testing reset watchdog"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_RESET_WATCHDOG)
        if l_res[-1] != "0":
            l_msg = "IPMI: Reset Watchdog command failed"
            raise OpTestError(l_msg)

        time.sleep(10)
        # Reset watchdog should create a SEL event log
        l_res = self.cv_IPMI.ipmitool_execute_command(BMC_CONST.IPMI_LIST_LAST_SEL_EVENT)
        if "Watchdog" not in l_res:
            l_msg = "IPMI: Reset Watchdog command, doesn't create an SEL event"
            raise OpTestError(l_msg)

        # 28. [App] Get ACPI Power State (0x06)
        print "Testing Get ACPI Power State"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_GET_ACPI_POWER_STATE)
        if l_res[-1] != "0":
            l_msg = "IPMI: Get ACPI Power State command failed"
            raise OpTestError(l_msg)

        # Below commands will effect sensors and fru values and some care to be taken for
        # executing.
        # 27.[Storage] Write FRU
        # 28.[Sensor/Event] Set Sensor Reading
        # 29. [OEM] Partial Add ESEL (0xF0)
        # This is testsed by kernel itself, it will send messages to BMC internally
        # 30.[App] Send Message
