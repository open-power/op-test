#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestRTCdriver.py $
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
OpTestRTCdriver
---------------

RTC (Real Time Clock) package for OpenPower testing.

This class will test the functionality of following drivers

1. RTC driver: Real time clock
'''


import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class FullRTC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_HOST = conf.host()
        cls.cv_IPMI = conf.ipmi()
        cls.cv_SYSTEM = conf.system()
        cls.test = None

    def setUp(self):
        if self.test == "host":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)

            # Get hwclock version
            l_hwclock = self.cv_HOST.host_run_command("hwclock -V")
            # Get Kernel Version
            l_kernel = self.cv_HOST.host_get_kernel_version()

            # loading rtc_opal module based on config option
            l_config = "CONFIG_RTC_DRV_OPAL"
            l_module = "rtc_opal"
            self.cv_HOST.host_load_module_based_on_config(
                l_kernel, l_config, l_module)

        elif self.test == "skiroot":
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.cv_SYSTEM.console

    # We have a busy box version hwclock with limited options
    # to access the HW RTC
    def skiroot_read_hwclock(self):
        log.debug("Reading the hwclock")
        self.c.run_command("hwclock -r")

    def skiroot_set_hwclock_time(self):
        log.debug("Setting the hwclock time from system time")
        self.c.run_command("hwclock -w")

    def skiroot_set_system_time(self):
        log.debug("Setting the system time from hwclock time")
        self.c.run_command("hwclock -s")

    def skiroot_assume_hwclock_utc(self):
        log.debug("Assume hardware clock is kept in UTC")
        self.c.run_command("hwclock -u")

    def skiroot_assume_hwclock_localtime(self):
        log.debug("Assume hardware clock is kept in local time")
        self.c.run_command("hwclock -l")

    def RunFullRTC(self):
        '''
        This function will cover following test steps

        1. Getting host information(OS and Kernel info)
        2. Loading rtc_opal module based on config option
        3. Testing the rtc driver functions:

            - Display the current time,
            - set the Hardware Clock to a specified time,
            - set the Hardware Clock from the System Time, or
            - set the System Time from the Hardware Clock
            - keep the Hardware clock in UTC or local time format
            - Hardware clock compare, predict and adjust functions
            - Hardware clock debug and test modes
            - Reading the Hardware clock from special file instead of default
        4. After executing above each function reading the Hardware clock in b/w functions.
        '''
        # Get the device files for rtc driver
        l_files = self.cv_HOST.host_run_command(
            "ls --color=never /dev/ | grep -i --color=never rtc")
        l_list = []
        for name in l_files:
            if name.__contains__("rtc"):
                l_file = "/dev/" + name
                l_list.append(l_file)
            else:
                continue
        log.debug(l_list)
        # Display the time of hwclock from device files
        for l_file in l_list:
            self.read_hwclock_from_file(l_file)

        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_set_hwclock_time("2015-01-01 10:10:10")
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_set_hwclock_time("2016-01-01 20:20:20")
        self.cv_HOST.host_read_hwclock()
        self.set_hwclock_in_utc("2017-01-01 10:10:10")
        self.cv_HOST.host_read_hwclock()
        self.set_hwclock_in_localtime("2014-01-01 05:05:05")
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_read_systime()
        self.systime_to_hwclock()
        self.cv_HOST.host_read_hwclock()
        self.systime_to_hwclock_in_utc()
        self.cv_HOST.host_read_hwclock()
        self.systime_to_hwclock_in_localtime()
        self.cv_HOST.host_read_hwclock()
        self.hwclock_to_systime()
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_read_systime()
        self.hwclock_in_utc()
        self.cv_HOST.host_read_hwclock()
        self.hwclock_in_localtime()
        self.cv_HOST.host_read_hwclock()
        self.hwclock_predict("2015-01-01 10:10:10")
        self.cv_HOST.host_read_hwclock()
        self.hwclock_debug_mode()
        self.cv_HOST.host_read_hwclock()
        self.hwclock_test_mode("2018-01-01 10:10:10")
        self.cv_HOST.host_read_hwclock()
        self.hwclock_adjust()
        self.cv_HOST.host_read_hwclock()

    def read_hwclock_from_file(self, i_file):
        '''
        This function reads hwclock from special /dev/... file instead of default
        '''
        log.debug("Reading the hwclock from special file /dev/ ...: %s" % i_file)
        try:
            self.cv_HOST.host_run_command("hwclock -r -f %s" % i_file)
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "reading the hwclock from file failed: %s" % str(c))

    def set_hwclock_in_utc(self, i_time):
        '''
        This function sets hwclock in UTC format

        :param i_time: time to set hwclock e.g. "2016-01-01 12:12:12"
        :type i_time: str
        '''
        log.debug("Setting the hwclock in UTC: %s" % i_time)
        try:
            self.cv_HOST.host_run_command(
                "hwclock --set --date \'%s\' --utc" % i_time)
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the hwclock in UTC failed: %s" % str(c))

    def set_hwclock_in_localtime(self, i_time):
        '''
        This function sets hwclock in local time format

        :param i_time: Time to set hwclock
        '''
        log.debug("Setting the hwclock in localtime: %s" % i_time)
        try:
            self.cv_HOST.host_run_command(
                "hwclock --set --date \'%s\' --localtime" % i_time)
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the hwclock in localtime failed: %s" % str(c))

    def systime_to_hwclock(self):
        '''
        This function sets the time of hwclock from system time
        '''
        log.debug("Setting the hwclock from system time")
        try:
            self.cv_HOST.host_run_command("hwclock --systohc")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the hwclock from system time failed: %s" % str(c))

    def systime_to_hwclock_in_utc(self):
        '''
        This function sets the time of hwclock from system time in UTC format
        '''
        log.debug("Setting the hwclock from system time, in UTC format")
        try:
            self.cv_HOST.host_run_command("hwclock --systohc --utc")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the hwclock from system time in UTC format failed: %s" % str(c))

    def systime_to_hwclock_in_localtime(self):
        '''
        This function sets the time of hwclock from system time in local time format
        '''
        log.debug("Setting the hwclock from system time, in localtime format")
        try:
            self.cv_HOST.host_run_command("hwclock --systohc --localtime")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the hwclock from system time in localtime format failed: %s" % str(c))

    def hwclock_to_systime(self):
        '''
        This function sets the system time from hwclock.
        '''
        log.debug("Setting the system time from hwclock")
        try:
            self.cv_HOST.host_run_command("hwclock --hctosys")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Setting the system time from hwclock failed: %s" % str(c))

    def hwclock_in_utc(self):
        '''
        This function keeps hwclock in UTC format.
        '''
        log.debug("Keeping the hwclock in UTC format")
        try:
            self.cv_HOST.host_run_command("hwclock --utc")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Keeping the hwclock in UTC is failed: %s" % str(c))

    def hwclock_in_localtime(self):
        '''
        This function keeps hwclock in local time format.
        '''
        log.debug("Keeping the hwclock in localtime")
        try:
            self.cv_HOST.host_run_command("hwclock --localtime")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "Keeping the hwclock in localtime is failed: %s" % str(c))

    def hwclock_predict(self, i_time):
        '''
        This function predict RTC reading at time given with --date

        :param i_time: time at which predict hwclock reading
        '''
        log.debug("Testing the hwclock predict function to a time: %s" % i_time)
        try:
            self.cv_HOST.host_run_command(
                "hwclock --predict --date \'%s\'" % i_time)
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "hwclock predict function failed: %s" % str(c))

    def hwclock_debug_mode(self):
        '''
        This function tests hwclock debug mode.
        In this mode setting hwclock from system time
        and setting system time from hwclock
        '''
        log.debug("Testing the hwclock debug mode")
        try:
            self.cv_HOST.host_run_command("hwclock --systohc --debug")
            self.cv_HOST.host_run_command("hwclock --hctosys --debug")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "hwclock debug mode failed: %s" % str(c))

    def hwclock_test_mode(self, i_time):
        '''
        This function tests the hwclock test mode. In this mode setting the
        hwclock time using ``--set`` option. Here it just execute but should
        not set hwclock time.

        :param i_time: time to set hwclock in test mode
        :type i_time: str
        '''
        log.debug("Testing the hwclock test mode, set time to: %s" % i_time)
        try:
            self.cv_HOST.host_run_command(
                "hwclock --set --date \'%s\' --test" % i_time)
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "hwclock test function failed: %s" % str(c))

    def hwclock_adjust(self):
        '''
        This function tests hwclock adjust functionality
        '''
        log.debug("Testing the hwclock adjust function")
        try:
            self.cv_HOST.host_run_command("hwclock --adjust")
        except CommandFailed as c:
            self.assertEqual(
                c.exitcode, 0, "hwclock adjust function failed: %s" % str(c))
        l_res = self.cv_HOST.host_run_command("cat /etc/adjtime")
        log.debug('\n'.join(l_res))


class BasicRTC(FullRTC):
    def setUp(self):
        self.test = "host"
        super(BasicRTC, self).setUp()

    def runTest(self):
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_read_systime()


class HostRTC(FullRTC):
    def setUp(self):
        self.test = "host"
        super(HostRTC, self).setUp()

    def runTest(self):
        self.RunFullRTC()


class SkirootRTC(FullRTC):
    def setUp(self):
        self.test = "skiroot"
        super(SkirootRTC, self).setUp()

    def runTest(self):
        self.skiroot_read_hwclock()
        self.skiroot_assume_hwclock_utc()
        self.skiroot_assume_hwclock_localtime()
        self.skiroot_set_hwclock_time()
        self.skiroot_set_system_time()
