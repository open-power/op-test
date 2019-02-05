#!/usr/bin/env python2
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

'''
OpTestInbandIPMI
----------------

Test the inband ipmi{OPEN Interface} fucntionality package for OpenPower
platform.

This class will test the functionality of following commands

1. bmc, channel, chassis, dcmi, echo, event, exec, firewall, fru, lan
   mc, pef, power, raw, sdr, sel, sensor, session, user
'''

import time
import subprocess
import re
import commands
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestIPMI import IPMIConsoleState
from common.Exceptions import CommandFailed
import common.OpTestMambo as OpTestMambo

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class UnexpectedBootDevice(Exception):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
    def __str__(self):
        return "Expected to set %s but instead got %s" % (self.expected, self.actual)


class OpTestInbandIPMIBase(object):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        if (isinstance(self.cv_BMC, OpTestMambo.OpTestMambo)):
            raise unittest.SkipTest("Mambo so skipping InbandIPMI tests")

    def set_up(self):
        if self.test == "skiroot":
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.cv_SYSTEM.console
        elif self.test == "host":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.cv_SYSTEM.load_ipmi_drivers()
            self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        else:
            raise Exception("Unknown test type")
        return self.c

    def run_ipmi_cmds(self, c, cmds):
        '''
        Run a list of IPMI commands, skipping the test if we can determine that the
        command wouldn't be supported on the current system (e.g. system doesn't
        support the inband USB interface).
        '''
        try:
            for cmd in cmds:
                c.run_command(cmd, timeout=120)
        except CommandFailed as cf:
            my_responses = ["Invalid command",
                            "Error loading interface usb"]
            matching = [xs for xs in my_responses if any(xs in xa for xa in cf.output)]
            if len(matching):
                self.skipTest("Invalid command or Error loading interface usb")
            else:
                raise cf

class BasicInbandIPMI(OpTestInbandIPMIBase,unittest.TestCase):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(BasicInbandIPMI, self).setUp()

    def test_sensor_list(self):
        '''
        Run a fast and simple test (on IPMI sensors) to test base functionality
        of the inband IPMI interface.

        This test is designed an a smoke test rather than for completeness.
        '''
        c = self.set_up()
        log.debug("Inband IPMI[OPEN]: Sensor tests")
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SENSOR_LIST])


class OpTestInbandIPMI(OpTestInbandIPMIBase,unittest.TestCase):
    '''
    A more complete test of inband IPMI functionality.
    '''
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(OpTestInbandIPMI, self).setUp()

    def test_chassis_poh(self):
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POH])
        except CommandFailed as cf:
            if 'Get Chassis Power-On-Hours failed: Invalid command' in cf.output[0]:
                self.skipTest("OpenBMC doesn't implement POH yet")
            self.fail(str(cf))

    def test_chassis(self):
        log.debug("Inband IPMI[OPEN]: Chassis tests")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_RESTART_CAUSE])
        except CommandFailed as cf:
            if 'Get Chassis Restart Cause failed: Invalid command' in cf.output[0]:
                self.skipTest("OpenBMC doesn't implement restart_cause yet")
            self.fail(str(cf))

        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POLICY_LIST,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_POLICY_ALWAYS_OFF])

    def test_chassis_identifytests(self):
        '''
        It will execute and test the ipmi chassis identify commands
        '''
        log.debug("Inband IPMI[OPEN]: Chassis Identify tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY_5,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY_FORCE,
                               self.ipmi_method + BMC_CONST.IPMI_CHASSIS_IDENTIFY])

    def test_chassis_bootdev(self):
        '''
        It will execute and test the functionality of
        `ipmi chassis bootdev <dev>` where dev is
        none,pxe,cdrom,disk,bios,safe,diag,floppy, and none.

        See the implementation for how nothing is as simple as it seems
        and we need weird exceptions.
        '''
        log.debug("Inband IPMI[OPEN]: Chassis Bootdevice tests")
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
                    if not self.cv_BMC.has_inband_bootdev():
                        self.skipTest("Does not support inband bootdev")
                    self.fail("Could not set boot device %s. Errored with %s" % (bootdev,str(cf)))
                self.verify_bootdev(bootdev, ipmiresponse)
            except UnexpectedBootDevice as e:
                # allow floppy to fail, as realistically,
                # there's never a floppy and this is insane.
                # We know that OpenBMC doesn't accept 'floppy'
                # due to https://github.com/openbmc/phosphor-dbus-interfaces/blob/master/xyz/openbmc_project/Control/Boot/Source.interface.yaml
                # not having a mapping for it.
                # The same for diag: there's no current mapping.
                if bootdev in ["floppy", "diag"]:
                    continue
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
                log.debug("Verifying bootdev is successfull for %s" % i_dev)
                return BMC_CONST.FW_SUCCESS
        else:
            raise UnexpectedBootDevice(i_dev, l_res)

    def test_sdr_list_by_type(self):
        '''
        It will execute and test the
        ipmi sdr list <all/fru/event/mcloc/compact/full/generic>
        '''
        log.debug("Inband IPMI[OPEN]: SDR list tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_LIST,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_ALL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_FRU,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_EVENT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_MCLOC,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_COMPACT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_FULL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_LIST_GENERIC])

    def test_sdr_elist_by_type(self):
        '''
        It will execute and test the commands:
        ipmi sdr elist <all/fru/event/mcloc/compact/full/generic>
        '''
        log.debug("Inband IPMI[OPEN]: SDR elist tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_ALL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_FRU,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_EVENT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_MCLOC,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_COMPACT,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_FULL,
                               self.ipmi_method + BMC_CONST.IPMI_SDR_ELIST_GENERIC])

    def test_sdr_type_list(self):
        '''
        It will execute and test the ipmi sdr type <Temp/fan/Powersupply>
        commands
        '''
        log.debug("Inband IPMI[OPEN]: SDR type list tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_LIST,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_TEMPERATURE,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_FAN,
                                self.ipmi_method + BMC_CONST.IPMI_SDR_TYPE_POWER_SUPPLY])

    def test_sdr_get_id(self):
        '''
        It will execute and test the ipmi sdr get <sensor-id> command
        '''
        log.debug("Inband IPMI[OPEN]: SDR get tests")
        l_cmd = self.ipmi_method + "sdr get \'Watchdog\'"
        c = self.set_up()
        self.run_ipmi_cmds(c, [l_cmd])

    def test_fru_print(self):
        '''
        It will execute and test the ipmi fru print command.
        '''
        log.debug("Inband IPMI[OPEN]: FRU Print Test")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_FRU_PRINT])

    def test_fru_read(self):
        '''
        It will execute and test the ipmi fru read command.
        then the output file is displayed by hexdump

        A FIXME is to check the *content* of the FRU for sanity.
        '''
        log.debug("Inband IPMI[OPEN]: FRU Read Test")
        c = self.set_up()
        # Not every system has FRU0. But if nothing all the way up to 100, probably a bug.
        fru_id = 0
        found_one = False
        nr_sequential_fail = 0
        for fru_id in range(0,100):
            if nr_sequential_fail > 25:
                # If we don't see one for a while, there's probably no more
                break
            try:
                self.run_ipmi_cmds(c, [self.ipmi_method + "fru print %d" % fru_id])
            except CommandFailed as cf:
                log.debug("FRU {} failed: {} {}".format(fru_id, cf.exitcode, cf.output))
                if cf.exitcode in [1, -1]:
                    nr_sequential_fail = nr_sequential_fail + 1
                    continue
                nr_sequential_fail = 0

            found_one = True
            self.run_ipmi_cmds(c, [self.ipmi_method + "fru read %d /tmp/file_fru" % fru_id])
            # TODO: Check for file output
            l_res = c.run_command("hexdump -C /tmp/file_fru")

        self.assertTrue(found_one, "Didn't find any FRUs")

    def test_mc(self):
        '''
        It will execute and test the management controller(mc) commands functionality.

        info
          Displays information about the BMC hardware, including device
          revision, firmware revision, IPMI version supported,
          manufacturer ID, and information on additional device support.
        watchdog get
          Show current Watchdog Timer settings and countdown state.
        watchdog off
          Turn off a currently running Watchdog countdown timer.
        watchdog reset
          Reset the Watchdog Timer to its most recent state and restart the
          countdown timer.
        selftest
          Check on the basic health of the BMC by executing the
          Get Self Test results command and report the results.
        setenables
          Enables  or disables the given option
        getenables
          Displays a list of the currently enabled options for the BMC.
        getsysinfo
          Retrieves system info from bmc for given argument
        '''
        log.debug("Inband IPMI[OPEN]: MC tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_INFO])
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_GET])
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_OFF,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_WATCHDOG_RESET])
        except CommandFailed as cf:
            if 'Get Watchdog Timer command failed: Unspecified error' in cf.output[0]:
                pass
            else:
                self.fail(str(cf))
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_SETENABLES_OEM_0_OFF,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_GETENABLES,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_SETENABLES_OEM_0_ON,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_GETENABLES])
        except CommandFailed as cf:
            # It's valid to fail these tests
            if 'Get Global Enables command failed: Invalid command' in cf.output[0]:
                pass

        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_MC_GETSYS_INFO,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_SELFTEST,
                                   self.ipmi_method + BMC_CONST.IPMI_MC_SELFTEST])
        except CommandFailed as cf:
            # It's valid to not implement selftest, so let's not fail things on it.
            if 'Selftest: not implemented' in cf.output[0]:
                pass
            else:
                raise cf

    def test_sel_info(self):
        '''
        It will execute and test the ipmi sel info functionality
        '''
        log.debug("Inband IPMI[OPEN]: SEL Info test")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_INFO])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_list(self):
        '''
        It will execute and test ipmi sel list functionality.
        the entire contents of the System Event Log are displayed.
        '''
        log.debug("Inband IPMI[OPEN]: SEL List test")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_LIST])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_elist(self):
        '''
        It will execute and test the ipmi sel elist functionality
        If invoked as elist (extended list) it will also use the
        Sensor Data Record entries to display the sensor ID for
        the sensor that caused each event.
        '''
        log.debug("Inband IPMI[OPEN]: SEL elist test")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_ELIST])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_time_get(self):
        '''
        It will execute and test the ipmi sel time get functionality
        Displays the SEL clock's current time.
        '''
        log.debug("Inband IPMI[OPEN]: SEL Time get test")
        c = self.set_up()
        l_res = None
        try:
            l_res = c.run_command(self.ipmi_method + BMC_CONST.IPMI_SEL_TIME_GET)
        except CommandFailed as cf:
            if 'Error loading interface usb' in cf.output:
                self.skipTest("No USB IPMI interface")
            raise cf
        except OpTestError as e:
            self.skipTest("IPMI: Insufficient resources")
        return l_res

    def test_sel_list_first_n_entries(self, i_num=1):
        '''
        It will execute and test the ipmi sel list first <n entries>

        :param i_num: The number of SELs to list
        :type i_num: int
        '''
        l_cmd = "sel list first %i" % int(i_num)
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_list_last_n_entries(self, i_num=1):
        '''
        It will execute and test the ipmi sel list last <n entries>

        :param i_num: The number of last SEL entries to list.
        :type i_num: int
        '''
        l_cmd = "sel list last %i" % int(i_num)
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_clear(self):
        '''
        It will execute the ipmi sel clear command.

        Not all BMCs support this (notably simulators such as Qemu). In that
        case, we try anyway and skip the test rather than fail.
        '''
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_SEL_CLEAR])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_get_functionality(self):
        '''
        It will execute and test the ipmi sel get <id> functionality.
        '''
        c = self.set_up()
        try:
            l_res = c.run_command(self.ipmi_method + "sel list first 3 | awk '{print $1}'")
            for entry in l_res:
                if entry.__contains__("SEL has no entries"):
                    log.debug("IPMI: There are no sel entries to fetch")
                    pass
                else:
                    l_id = "0x" + entry
                    l_cmd = "sel get %s" % l_id
                    c.run_command(self.ipmi_method + l_cmd)
        except CommandFailed as cf:
            if 'Error loading interface usb' in cf.output:
                self.skipTest("No USB IPMI interface")
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_clear_functionality(self):
        '''
        It will execute and test the ipmi sel clear functionality.
        '''
        self.test_sel_clear()
        c = self.set_up()
        l_res = c.run_command("ipmitool sel list")
        for l_line in l_res:
            if l_line.__contains__("SEL has no entries"):
                log.debug("Sel clear function got cleared event entries")
                break
        else:
            l_msg = "Inband IPMI[OPEN]: sel clear function failing in clearing entries"
            log.error(l_msg)
            raise OpTestError(l_msg)

    def sensor_byid(self, i_sensor=BMC_CONST.SENSOR_HOST_STATUS):
        '''
        It will execute and test the ipmi sensor get <id> functionality

        :param i_sensor: sensor ID to retrieve data from
        :type i_sensor: str
        '''
        l_cmd = self.ipmi_method + "sensor get \"%s\"" % i_sensor
        c = self.set_up()
        c.run_command(l_cmd)

    def test_dcmi(self):
        '''
        It will execute and test the dcmi related ipmi commands.

        discover
          This command is used to discover supported capabilities in DCMI
        Power reading
          Get power related readings from the system.
        get_limit
          Get the configured power limits.
        sensors
          Prints the available DCMI sensors.
        get_mc_id_string
          Get management controller identifier string
        get_temp_reading
          Get Temperature Sensor Readings.
        get_conf_param
          Get DCMI Configuration Parameters.
        oob_discover
          Ping/Pong Message for DCMI Discovery
        '''
        log.debug("Inband IPMI[OPEN]: dcmi tests")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_DCMI_DISCOVER,
                                   # disable for now, unreliable at best
                                   # self.ipmi_method + BMC_CONST.IPMI_DCMI_POWER_READING,
                                   # opened ipmitool inband issue for dcmi get_limit
                                   # https://github.com/open-power/boston-openpower/issues/1396
                                   # self.ipmi_method + BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT,
                                   self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING,
                                   self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_TEMP_READING,
                                   self.ipmi_method + BMC_CONST.IPMI_DCMI_GET_CONF_PARAM,
                                   self.ipmi_method + BMC_CONST.IPMI_DCMI_SENSORS])
        except CommandFailed as cf:
            if self.cv_BMC.supports_ipmi_dcmi():
                raise cf
            else:
                self.skipTest("BMC Implementation doesn't support DCMI commands")

    def test_echo(self):
        '''
        It will execute and test the functionality of ipmi echo command.
        '''
        log.debug("Inband IPMI[OPEN]: echo tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_ECHO_DONE])

    def test_event(self):
        '''
        It will execute and test event related commands to test sel
        functionality.

        Send a pre-defined test event to the System Event Log.  The following
        events are included as a means to test the functionality of  the  System
        Event Log component of the BMC (an entry will be added each time the
        event N command is executed)

        Currently supported values for N are:

        1. Temperature: Upper Critical: Going High
        2. Voltage Threshold: Lower Critical: Going Low
        3. Memory: Correctable ECC
        '''
        log.debug("Inband IPMI[OPEN]: event tests")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_EVENT_1,
                               self.ipmi_method + BMC_CONST.IPMI_EVENT_2,
                               self.ipmi_method + BMC_CONST.IPMI_EVENT_3])

    def test_exec(self):
        '''
        It will execute and test ipmi exec command.

        FIXME: not yet implemented.
        '''
        log.debug("Inband IPMI[OPEN]: exec tests")
        pass
        # TODO: need to execute ipmi commands from a file

    def test_firewall(self):
        '''
        It will execute and test firmware firewall info command.
        '''
        log.debug("Inband IPMI[OPEN]: Firewall test")
        c = self.set_up()
        self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_FIREWALL_INFO])

    def test_pef(self):
        '''
        It will execute and test pef related commands:

        info
          This command will query the BMC and print information about the PEF
          supported features.
        status
          This command prints the current PEF status
        policy
          This command lists the PEF policy table entries
        list
          This  command  lists  the PEF table entries.
        '''
        log.debug("Inband IPMI[OPEN]: Pef tests")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_PEF_INFO,
                                   self.ipmi_method + BMC_CONST.IPMI_PEF_STATUS,
                                   self.ipmi_method + BMC_CONST.IPMI_PEF_POLICY,
                                   self.ipmi_method + BMC_CONST.IPMI_PEF_LIST])
        except CommandFailed as cf:
            if 'IPMI command failed: Invalid command' in cf.output[0]:
                self.skipTest("BMC doesn't implement PEF, this is valid.")
            self.fail(str(cf))

    def test_raw(self):
        '''
        This will test raw IPMI commands. For example to query the POH counter
        with a raw command.

        Practically speaking, this tests ipmitool itself more than any firmware
        or OS functionality (when compared to the non-raw test).
        '''
        log.debug("Inband IPMI[OPEN]: raw command execution tests")
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + BMC_CONST.IPMI_RAW_POH])
        except CommandFailed as cf:
            if 'Unable to send RAW command (channel=0x0 netfn=0x0 lun=0x0 cmd=0xf rsp=0xc1): Invalid command' in cf.output:
                self.skipTest("OpenBMC doesn't implement POH yet")
            self.fail(str(cf))

    def test_sel_set_time(self):
        '''
        It will execute and test the ipmi sel set <time string> functionality
        Sets the SEL clock.  Future SEL entries will use the time set by this command.
        '''
        l_res = self.test_sel_time_get()
        if l_res is not None:
          i_time = l_res[-1]
        log.debug("Inband IPMI[OPEN]: SEL Time set test")
        l_cmd = "sel time set \'%s\'" % i_time
        c = self.set_up()
        try:
            self.run_ipmi_cmds(c, [self.ipmi_method + l_cmd])
        except CommandFailed as cf:
            if self.cv_BMC.has_ipmi_sel():
                raise cf
            else:
                self.skipTest("BMC doesn't support SEL (e.g. qemu)")

    def test_sel_list_first_3_entries(self):
        '''
        It will execute and test the ipmi sel list first <3 entries>
        '''
        self.test_sel_list_first_n_entries(BMC_CONST.IPMI_SEL_LIST_ENTRIES)

    def test_sel_list_last_3_entries(self):
        '''
        It will execute and test the ipmi sel list last <3 entries>
        '''
        self.test_sel_list_last_n_entries(BMC_CONST.IPMI_SEL_LIST_ENTRIES)

    def test_sensor_get_host_status(self):
        '''
        It will execute and test the ipmi sensor get "Host Status" functionality.

        Not all BMCs support this sensor, so if we think a BMC doesn't, and it
        fails, we skip the test rather than failing it.
        '''
        try:
            self.sensor_byid(BMC_CONST.SENSOR_HOST_STATUS)
        except CommandFailed as cf:
            if not self.cv_BMC.has_host_status_sensor():
                if 'not found' in ''.join(cf.output):
                    self.skipTest("Platform doesn't Sensor")
                if 'Error loading interface usb' in cf.output:
                    self.skipTest("No USB IPMI interface")
            self.fail(str(cf))

    def test_sensor_get_os_boot(self):
        '''
        It will execute and test the ipmi sensor get "OS Boot" functionality.

        If the BMC doesn't support the 'OS Boot' sensor, we try anyway and
        skip the test.
        '''
        try:
            self.sensor_byid(BMC_CONST.SENSOR_OS_BOOT)
        except CommandFailed as cf:
            if not self.cv_BMC.has_os_boot_sensor():
                if 'not found' in ''.join(cf.output):
                    self.skipTest("Platform doesn't Sensor")
                if 'Error loading interface usb' in cf.output:
                    self.skipTest("No USB IPMI interface")
            self.fail(str(cf))

    def test_sensor_get_occ_active(self):
        '''
        It will execute and test the ipmi sensor get "OCC Active" functionality
        '''
        try:
            self.sensor_byid(BMC_CONST.SENSOR_OCC_ACTIVE)
        except CommandFailed as cf:
            if not self.cv_BMC.has_occ_active_sensor():
                if 'not found' in ''.join(cf.output):
                    self.skipTest("Platform doesn't Sensor")
                if 'Error loading interface usb' in cf.output:
                    self.skipTest("No USB IPMI interface")
            self.fail(str(cf))


class ExperimentalInbandIPMI(OpTestInbandIPMIBase,unittest.TestCase):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_OPEN):
        self.ipmi_method = ipmi_method
        self.test = "host"
        super(ExperimentalInbandIPMI, self).setUp()

    def test_Info(self):
        '''
        It will execute and test the ipmi <sdr/sel/mc/channel> info related
        commands.

        Currently in the Experimental pool as the "ipmitool BLAH info" commands
        seem to have random return codes, so failure is common.
        '''
        log.debug("Inband IPMI[OPEN]: Info tests")
        c = self.set_up()
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_CHANNEL_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_MC_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_SEL_INFO)
        c.run_command(self.ipmi_method + BMC_CONST.IPMI_SDR_INFO)

    def test_channel(self):
        '''
        It will check basic channel functionalities: info and authentication
        capabilities.
        '''
        log.debug("Inband IPMI[OPEN]: Channel tests")
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
