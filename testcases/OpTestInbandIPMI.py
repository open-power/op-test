#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestInbandIPMI.py $
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
#  Test the inband ipmi{OPEN Interface} fucntionality package for OpenPower platform.
#
#  This class will test the functionality of following commands
#  1. bmc, channel, chassis, dcmi, echo, event, exec, firewall, fru, lan
#     mc, pef, power, raw, sdr, sel, sensor, session, user

import time
import subprocess
import re
import commands
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestIPMI import IPMIConsoleState
from common.Exceptions import CommandFailed

class UnexpectedBootDevice(Exception):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
    def __str__(self):
        return "Expected to set %s but instead got %s" % (self.expected, self.actual)


class OpTestInbandIPMIBase(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.util = OpTestUtil()
        pass

    def set_up(self):
        if self.test == "skiroot":
            self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.system.sys_get_ipmi_console()
            self.system.host_console_unique_prompt()
            if self.c.state == IPMIConsoleState.DISCONNECTED:
                self.c = self.system.sys_get_ipmi_console()
                self.system.host_console_unique_prompt()
            # if sol console drops in b/w
            elif not self.c.sol.isalive():
                print "Console is not active"
                self.c = self.system.sys_get_ipmi_console()
        elif self.test == "host":
            self.system.goto_state(OpSystemState.OS)
            self.system.load_ipmi_drivers()
            self.c = self.host.get_ssh_connection()
        else:
            raise Exception("Unknow test type")
        return self.c

    def run_ipmi_cmds(self, c, cmds):
        try:
            for cmd in cmds:
                c.run_command(cmd)
        except CommandFailed as cf:
            if 'Error loading interface usb' in cf.output:
                self.skipTest("No USB IPMI interface")
            else:
                raise cf

class BasicInbandIPMI(OpTestInbandIPMIBase):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(BasicInbandIPMI, self).setUp()
    ##
    # @brief  It will execute and test the ipmi sensor list functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_list(self):
        c = self.set_up()
        print "Inband IPMI[OPEN]: Sensor tests"
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SENSOR_LIST])

class OpTestInbandIPMI(OpTestInbandIPMIBase):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(OpTestInbandIPMI, self).setUp()

    ##
    # @brief  It will execute and test the ipmitool chassis <cmd> commands
    #         cmd: status, poh, restart_cause, policy list and policy set
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_chassis(self):
        print "Inband IPMI[OPEN]: Chassis tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POH,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_RESTART_CAUSE,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POLICY_LIST,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POLICY_ALWAYS_OFF])

    ##
    # @brief  It will execute and test the ipmi chassis identify commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_chassis_identifytests(self):
        print "Inband IPMI[OPEN]: Chassis Identify tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY_5,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY_FORCE,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY])

    ##
    # @brief  It will execute and test the functionality of ipmi chassis bootdev <dev>
    #         dev: none,pxe,cdrom,disk,bios,safe,diag,floppy and none.
    #
    # @return BMC_CONST.FW_SUCCESS on success or raise OpTestError
    #
    def test_chassis_bootdev(self):
        print "Inband IPMI[OPEN]: Chassis Bootdevice tests"
        c = self.set_up()
        boot_devices = {
            "none" : "No override",
            "pxe"  : "Force PXE",
            "cdrom": "Force Boot from CD/DVD",
            "disk" : "Force Boot from default Hard-Drive",
            "bios" : "Force Boot into BIOS Setup",
            "safe" : "Force Boot from default Hard-Drive, request Safe-Mode",
            "diag" : "Force Boot from Diagnostic Partition",
            "floppy" : "Force Boot from Floppy/primary removable media",
        }
        for bootdev,ipmiresponse in boot_devices.iteritems():
            try:
                try:
                    r = c.run_command(self.ipmi_method + 'chassis bootdev %s' % (bootdev))
                except CommandFailed as cf:
                    if 'Error loading interface usb' in cf.output:
                        self.skipTest("No USB IPMI interface")
                    self.fail("Could not set boot device %s. Errored with %s" % (bootdev,str(cf)))
                self.verify_bootdev(bootdev, ipmiresponse)
            except UnexpectedBootDevice as e:
                self.fail(str(e))
        # reset to bootdev none
        try:
            c.run_command(self.ipmi_method + 'chassis bootdev none')
            self.verify_bootdev("none",boot_devices["none"])
        except UnexpectedBootDevice as e:
            self.fail(str(e))
        pass

    def verify_bootdev(self, i_dev, l_msg):
        c = self.set_up()
        l_res = c.run_command(self.ipmi_method + "chassis bootparam get 5")
        for l_line in l_res:
            if l_line.__contains__(l_msg):
                print "Verifying bootdev is successfull for %s" % i_dev
                return BMC_CONST.FW_SUCCESS
        else:
            raise UnexpectedBootDevice(i_dev, l_res)

    ##
    # @brief  It will execute and test the ipmi sdr list <all/fru/event/mcloc/compact/full/generic>
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_list_by_type(self):
        print "Inband IPMI[OPEN]: SDR list tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_LIST,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_ALL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_FRU,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_EVENT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_MCLOC,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_COMPACT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_FULL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_GENERIC])

    ##
    # @brief  It will execute and test the ipmi sdr elist <all/fru/event/mcloc/compact/full/generic>
    #         commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_elist_by_type(self):
        print "Inband IPMI[OPEN]: SDR elist tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_ALL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_FRU,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_EVENT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_MCLOC,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_COMPACT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_FULL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_GENERIC])

    ##
    # @brief  It will execute and test the ipmi sdr type <Temp/fan/Powersupply> commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_type_list(self):
        print "Inband IPMI[OPEN]: SDR type list tests"
        c = self.set_up()
        self.run_ipmi_cmnds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_LIST,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_TEMPERATURE,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_FAN,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_POWER_SUPPLY])

    ##
    # @brief  It will execute and test the ipmi sdr get <sensor-id> command
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_get_id(self):
        print "Inband IPMI[OPEN]: SDR get tests"
        l_cmd = self.ipmi_method + "sdr get \'Watchdog\'"
        c = self.set_up()
        self.run_ipmi_cmds(c, [l_cmd])

    ##
    # @brief  It will execute and test the ipmi fru print command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_fru_print(self):
        print "Inband IPMI[OPEN]: FRU Print Test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_FRU_PRINT])


    ##
    # @brief  It will execute and test the ipmi fru read command.
    #         then the output file is displayed by hexdump
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_fru_read(self):
        print "Inband IPMI[OPEN]: FRU Read Test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + "fru read 0 /tmp/file_fru"])

        l_res = c.run_command("hexdump -C /tmp/file_fru")
        # TODO: Check for file output

    ##
    # @brief  It will execute and test the management controller(mc) commands functionality
    #         info-Displays information about the BMC hardware, including device revision,
    #              firmware revision, IPMI version supported, manufacturer ID,  and  information
    #               on additional device support
    #         watchdog get-Show current Watchdog Timer settings and countdown state.
    #         watchdog off-Turn off a currently running Watchdog countdown timer.
    #         watchdog reset-Reset the Watchdog Timer to its most recent state and restart the countdown timer.
    #         selftest- Check on the basic health of the BMC by executing the
    #                   Get Self Test results command and report the results.
    #         setenables-Enables  or disables the given option
    #         getenables-Displays a list of the currently enabled options for the BMC.
    #         getsysinfo-Retrieves system info from bmc for given argument
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_mc(self):
        print "Inband IPMI[OPEN]: MC tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_INFO,
                               self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_GET,
                               self.ipmi_method + BMC_CONST.IPMI_MC_SELFTEST,
                               self.ipmi_method + BMC_CONST.IPMI_MC_SELFTEST,
                               self.ipmi_method + BMC_CONST.IPMI_MC_SETENABLES_OEM_0_OFF,
                               self.ipmi_method + BMC_CONST.IPMI_MC_GETENABLES,
                               self.ipmi_method + BMC_CONST.IPMI_MC_SETENABLES_OEM_0_ON,
                               self.ipmi_method + BMC_CONST.IPMI_MC_GETENABLES,
                               self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_OFF,
                               self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_RESET,
                               self.ipmi_method + BMC_CONST.IPMI_MC_GETSYS_INFO])

    ##
    # @brief  It will execute and test the ipmi sel info functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_info(self):
        print "Inband IPMI[OPEN]: SEL Info test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_INFO])

    ##
    # @brief  It will execute and test ipmi sel list functionality.
    #         the entire contents of the System Event Log are displayed.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list(self):
        print "Inband IPMI[OPEN]: SEL List test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_LIST])


    ##
    # @brief  It will execute and test the ipmi sel elist functionality
    #         If invoked as elist (extended list) it will also use the
    #         Sensor Data Record entries to display the sensor ID for
    #           the sensor that caused each event.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_elist(self):
        print "Inband IPMI[OPEN]: SEL elist test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_ELIST])


    ##
    # @brief  It will execute and test the ipmi sel time get functionality
    #         Displays the SEL clock's current time.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_time_get(self):
        print "Inband IPMI[OPEN]: SEL Time get test"
        c = self.set_up()
        l_res = c.run_command(self.ipmi_method + BMC_CONST.IPMI_SEL_TIME_GET)
        return l_res

    ##
    # @brief  It will execute and test the ipmi sel list first <n entries>
    #
    # @param i_num @type string:The num of entries of sel to be listed
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_first_n_entries(self, i_num=1):
        l_cmd = "sel list first %i" % int(i_num)
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])

    ##
    # @brief  It will execute and test the ipmi sel list last <n entries>
    #
    # @param i_num @type string:The num of entries of sel to be listed
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_last_n_entries(self, i_num=1):
        l_cmd = "sel list last %i" % int(i_num)
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])

    ##
    # @brief  It will execute the ipmi sel clear command
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_clear(self):
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_CLEAR])

    ##
    # @brief  It will execute and test the ipmi sel get <id> functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_get_functionality(self):
        c = self.set_up()
        l_res = c.run_command(self.ipmi_method + "sel list first 3 | awk '{print $1}'")
        for entry in l_res:
            if entry.__contains__("SEL has no entries"):
                print "IPMI: There are no sel entries to fetch"
                pass
            else:
                l_id = "0x" + entry
                l_cmd = "sel get %s" % l_id
                c.run_command(self.ipmi_method + l_cmd)

    ##
    # @brief  It will execute and test the ipmi sel clear functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_clear_functionality(self):
        self.test_sel_clear()
        c = self.set_up()
        l_res = c.run_command("ipmitool sel list")
        for l_line in l_res:
            if l_line.__contains__("SEL has no entries"):
                print "Sel clear function got cleared event entries"
                break
        else:
            l_msg = "Inband IPMI[OPEN]: sel clear function failing in clearing entries"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief  It will execute and test the ipmi sensor get <id> functionality
    #
    # @param i_sensor @type string:sensor id to retrieve the data
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_byid(self, i_sensor=BMC_CONST.SENSOR_HOST_STATUS):
        l_cmd = self.ipmi_method + "sensor get \"%s\"" % i_sensor
        c = self.set_up()
        c.run_command(l_cmd)

    ##
    # @brief  It will execute and test the dcmi related ipmi commands.
    #         discover-This command is used to discover supported capabilities in DCMI
    #         Power reading-Get power related readings from the system.
    #               get_limit-Get the configured power limits.
    #         sensors-Prints the available DCMI sensors.
    #         get_mc_id_string-Get management controller identifier string
    #         get_temp_reading-Get Temperature Sensor Readings.
    #         get_conf_param-Get DCMI Configuration Parameters.
    #         oob_discover-Ping/Pong Message for DCMI Discovery
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_dcmi(self):
        print "Inband IPMI[OPEN]: dcmi tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_DCMI_DISCOVER,
                               self.ipmi_method + BMC_CONST.IPMI_DCMI_POWER_READING,
                               #self.ipmi_method + BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT,
                               self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING,
                               self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_TEMP_READING,
                               self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_CONF_PARAM,
                               self.ipmi_method + BMC_CONST.IPMI_DCMI_SENSORS])


    ##
    # @brief  It will execute and test the functionality of ipmi echo command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_echo(self):
        print "Inband IPMI[OPEN]: echo tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_ECHO_DONE])

    ##
    # @brief  It will execute and test event related commands to test sel functionality.
    #         Send a pre-defined test event to the System Event Log.  The following
    #         events are included as a means to test the functionality of  the  System
    #         Event Log component of the BMC (an entry will be added each time the
    #         event N command is executed)
    #         Currently supported values for N are:
    #         1    Temperature: Upper Critical: Going High
    #         2    Voltage Threshold: Lower Critical: Going Low
    #         3    Memory: Correctable ECC
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_event(self):
        print "Inband IPMI[OPEN]: event tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_EVENT_1,
                               self.ipmi_method + BMC_CONST.IPMI_EVENT_2,
                               self.ipmi_method + BMC_CONST.IPMI_EVENT_3])

    ##
    # @brief  It will execute and test ipmi exec command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_exec(self):
        print "Inband IPMI[OPEN]: exec tests"
        pass
        # TODO: need to execute ipmi commands from a file

    ##
    # @brief  It will execute and test firmware firewall info command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_firewall(self):
        print "Inband IPMI[OPEN]: Firewall test"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_FIREWALL_INFO])

    ##
    # @brief  It will execute and test pef related commands:
    #         info:This command will query the BMC and print information about the PEF supported features.
    #         status: This command prints the current PEF status
    #         policy: This command lists the PEF policy table entries
    #         list: This  command  lists  the PEF table entries.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #

    def test_pef(self):
        print "Inband IPMI[OPEN]: Pef tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_PEF_INFO,
                               self.ipmi_method + BMC_CONST.IPMI_PEF_STATUS,
                               self.ipmi_method + BMC_CONST.IPMI_PEF_POLICY,
                               self.ipmi_method + BMC_CONST.IPMI_PEF_LIST])

    ##
    # @brief This will test raw IPMI commands. For example to query the POH counter with a raw command
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_raw(self):
        print "Inband IPMI[OPEN]: raw command execution tests"
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_RAW_POH])

    ##
    # @brief  It will execute and test the ipmi sel set <time string> functionality
    #         Sets the SEL clock.  Future SEL entries will use the time set by this command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_set_time(self):
        l_res = self.test_sel_time_get()
        i_time = l_res[-1]
        print "Inband IPMI[OPEN]: SEL Time set test"
        l_cmd = "sel time set \'%s\'" % i_time
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])

    ##
    # @brief  It will execute and test the ipmi sel list first <3 entries>
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_first_3_entries(self):
        self.test_sel_list_first_n_entries(BMC_CONST.IPMI_SEL_LIST_ENTRIES)

    ##
    # @brief  It will execute and test the ipmi sel list last <3 entries>
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_last_3_entries(self):
        self.test_sel_list_last_n_entries(BMC_CONST.IPMI_SEL_LIST_ENTRIES)

    ##
    # @brief  It will execute and test the ipmi sensor get "Host Status" functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_get_host_status(self):
        self.test_sensor_byid(BMC_CONST.SENSOR_HOST_STATUS)

    ##
    # @brief  It will execute and test the ipmi sensor get "OS Boot" functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_get_os_boot(self):
        self.test_sensor_byid(BMC_CONST.SENSOR_OS_BOOT)

    ##
    # @brief  It will execute and test the ipmi sensor get "OCC Active" functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_get_occ_active(self):
        self.test_sensor_byid(BMC_CONST.SENSOR_OCC_ACTIVE)

class ExperimentalInbandIPMI(OpTestInbandIPMIBase):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(ExperimentalInbandIPMI, self).setUp()
    ##
    # @brief  It will execute and test the ipmi <sdr/sel/mc/channel> info related commands.
    #
    # Currently in the Experimental pool as the "ipmitool BLAH info" commands
    # seem to have random return codes, so failure is common.
    def test_Info(self):
        print "Inband IPMI[OPEN]: Info tests"
        c = self.set_up()
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_CHANNEL_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_MC_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_SEL_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_SDR_INFO)

    ##
    # @brief  It will check basic channel functionalities: info and authentication capabilities.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_channel(self):
        print "Inband IPMI[OPEN]: Channel tests"
        c = self.set_up()
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_CHANNEL_AUTHCAP)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_CHANNEL_INFO)

class SkirootBasicInbandIPMI(BasicInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "skiroot"
        super(BasicInbandIPMI, self).setUp()

class SkirootFullInbandIPMI(OpTestInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "skiroot"
        super(OpTestInbandIPMI, self).setUp()

def full_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(OpTestInbandIPMI)

def basic_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(BasicInbandIPMI)

def skiroot_full_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(SkirootFullInbandIPMI)

def skiroot_basic_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(SkirootBasicInbandIPMI)

def experimental_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(ExperimentalInbandIPMI)
