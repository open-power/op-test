#!/usr/bin/env python2
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

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

class OpTestIPMILockMode(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()
        self.platform = conf.platform()

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
    def runTest(self):
        if not self.platform in ['habanero','firestone','garrison', 'p9dsu']:
            raise unittest.SkipTest("Platform %s doesn't support IPMI Lockdown mode" % self.platform)

        self.cv_SYSTEM.goto_state(OpSystemState.OS)

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
        l_res = self.cv_IPMI.enter_ipmi_lockdown_mode()

        try:
            self.run_inband_ipmi_whitelisted_cmds()
        except:
            l_msg = "One of white listed in-band ipmi command execution failed"
            print sys.exc_info()
        finally:
            # Issue a ipmi unlock command at the end of test.
            print "Issuing ipmi unlock command through authenticated interface"
            self.cv_IPMI.exit_ipmi_lockdown_mode()

    ##
    # @brief This function will execute whitelisted in-band ipmi commands
    #        and test the functionality in locked mode.
    def run_inband_ipmi_whitelisted_cmds(self):
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con.run_command("uname -a")

        # Test IPMI white listed commands those should be allowed through un-authenticated
        # in-band interface
        # 1.[App] Get Device ID
        print "Testing Get Device ID command"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_DEVICE_ID)

        # 2.[App] Get Device GUID
        print "Testing Get Device GUID"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_DEVICE_GUID)

        # 3.[App] Get System GUID
        print "Testing Get system GUID"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SYSTEM_GUID)

        # 4.[Storage] Get SEL info
        print "Testing Get SEL info"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SEL_INFO)

        # 5.[Storage] Get SEL time
        print "Testing Get SEL time"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SEL_TIME_RAW)

        # 6. [Storage] Reserve SEL
        print "Testing Reserve SEL"
        l_res = l_con.run_command(BMC_CONST.HOST_RESERVE_SEL)

        # 7. [Storage] Set SEL time (required for RTC)
        print "Testing Set SEL time"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SEL_TIME)
        l_res = l_con.run_command(BMC_CONST.HOST_SET_SEL_TIME + " \'" + l_res[-1] + "\'")
        l_con.run_command(BMC_CONST.HOST_GET_SEL_TIME)

        # 8. [Transport] Get LAN parameters
        print "Testing Get LAN parameters"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_LAN_PARAMETERS)

        # 9.[Chassis] Get System Boot Options
        print "Testing Get System Boot Options"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SYSTEM_BOOT_OPTIONS)

        # 10.[Chassis] Set System Boot Options
        print "Testing Set System Boot Options"
        l_res = l_con.run_command(BMC_CONST.HOST_SET_SYTEM_BOOT_OPTIONS)
        l_con.run_command(BMC_CONST.HOST_GET_SYSTEM_BOOT_OPTIONS)

        # 11. [App] Get BMC Global Enables
        print "Testing Get BMC Global Enables"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES_RAW)
        l_con.run_command(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES)

        # 12. [App] Set BMC Global Enables
        print "Testing Set BMC Global Enables"
        l_res = l_con.run_command(BMC_CONST.HOST_SET_BMC_GLOBAL_ENABLES_SEL_OFF)
        l_con.run_command(BMC_CONST.HOST_GET_BMC_GLOBAL_ENABLES)
        l_con.run_command(BMC_CONST.HOST_SET_BMC_GLOBAL_ENABLES_SEL_ON)

        # 13.[App] Get System Interface Capabilities
        if not self.platform in ['p9dsu']:
            print "Testing Get System Interface Capabilities"
            l_res = l_con.run_command(BMC_CONST.HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_SSIF)
            l_res = l_con.run_command(BMC_CONST.HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_KCS)

        # 14.[App] Get Message Flags
        print "Testing Get Message Flags"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_MESSAGE_FLAGS)

        # 15. [App] Get BT Capabilities
        print "Testing Get BT Capabilities"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_BT_CAPABILITIES)

        # 16. [App] Clear Message Flags
        print "Testing Clear Message Flags"
        l_res = l_con.run_command_ignore_fail(BMC_CONST.HOST_CLEAR_MESSAGE_FLAGS)

        if not self.platform in ['p9dsu']:
            # 17. [OEM] PNOR Access Status
            print "Testing the PNOR Access Status"
            l_res = l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_STATUS_DENY)
            l_res = l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_STATUS_GRANT)

        # 18. [Storage] Add SEL Entry
        print "Testing Add SEL Entry"
        print "Clearing the SEL list"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = l_con.run_command(BMC_CONST.HOST_ADD_SEL_ENTRY)
        time.sleep(1)
        l_res = self.cv_IPMI.last_sel()
        print "Checking for Reserved entry creation in SEL"
        print l_res
        if "eserved" not in l_res:
            raise Exception("IPMI: Add SEL Entry command, doesn't create an SEL event")

        # 19. [App] Set Power State
        print "Testing Set Power State"
        l_res = l_con.run_command(BMC_CONST.HOST_SET_ACPI_POWER_STATE)


        # 20.[Sensor/Event] Platform Event (0x02)
        print "Testing Platform Event"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = l_con.run_command(BMC_CONST.HOST_PLATFORM_EVENT)
        l_res = self.cv_IPMI.last_sel()
        if "eserved" not in l_res:
            raise Exception("IPMI: Platform Event command failed to log SEL event")

        # 21.[Chassis] Chassis Control
        print "Testing chassis power on"
        l_res = l_con.run_command(BMC_CONST.HOST_CHASSIS_POWER_ON)


        # 22. [App] Get ACPI Power State (0x06)
        print "Testing Get ACPI Power State"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_ACPI_POWER_STATE)

        # 23. [App] Set watchdog
        print "Testing Set watchdog"
        l_res = l_con.run_command(BMC_CONST.HOST_SET_WATCHDOG)
        self.cv_IPMI.mc_get_watchdog()

        if self.platform in ['p9dsu']:
            return

        # 24. [Sensor/Event] Get Sensor Type
        print "Testing Get Sensor Type"
        l_res = self.cv_IPMI.sdr_get_watchdog()
        matchObj = re.search( "Watchdog \((0x\d{1,})\)", l_res)
        if matchObj:
            print "Got sensor Id for watchdog: %s" % matchObj.group(1)
        else:
            raise Exception("Failed to get sensor id for watchdog sensor")
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SENSOR_TYPE_FOR_WATCHDOG + " " + matchObj.group(1))

        # 25.[Sensor/Event] Get Sensor Reading
        print "Testing Get Sensor Reading"
        l_res = self.cv_IPMI.sdr_get_watchdog()
        matchObj = re.search( "Watchdog \((0x\d{1,})\)", l_res)
        if matchObj:
            print "Got sensor Id for watchdog: %s" % matchObj.group(1)
        else:
            raise Exception("Failed to get sensor id for watchdog sensor")
        l_res = l_con.run_command(BMC_CONST.HOST_GET_SENSOR_READING + " " + matchObj.group(1))


        # 26. [OEM] PNOR Access Response (0x08)
        print "Testing PNOR Access Response"
        l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_STATUS_GRANT)
        l_res = l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_RESPONSE)
        l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_STATUS_DENY)
        l_res = l_con.run_command(BMC_CONST.HOST_PNOR_ACCESS_RESPONSE)

        # 27.[App] 0x38 Get Channel Authentication Cap
        print "Testing Get Channel Authentication Capabilities"
        l_res = l_con.run_command(BMC_CONST.HOST_GET_CHANNEL_AUTH_CAP)

        # 28.[App] Reset Watchdog (0x22)
        print "Testing reset watchdog"
        self.cv_IPMI.ipmi_sdr_clear()
        l_res = l_con.run_command(BMC_CONST.HOST_RESET_WATCHDOG)

        l_res = ''
        for x in range(0,25):
            # Reset watchdog should create a SEL event log
            print "# Looking for Watchdog SEL event try %d" % x
            l_res = self.cv_IPMI.last_sel()
            print l_res
            if "Watchdog" in l_res:
                break
            time.sleep(1)

        if "Watchdog" not in l_res:
            raise Exception("IPMI: Reset Watchdog command, doesn't create an SEL event")


        # Below commands will effect sensors and fru values and some care to be taken for
        # executing.
        # 29.[Storage] Write FRU
        # 30.[Sensor/Event] Set Sensor Reading
        # 31. [OEM] Partial Add ESEL (0xF0)
        # This is testsed by kernel itself, it will send messages to BMC internally
        # 32.[App] Send Message
