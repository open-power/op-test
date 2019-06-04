#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/LightPathDiagnostics.py $
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
LightPathDiagnostics
--------------------

Currently runs only in FSP platforms.
'''

import time
import subprocess
import re

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class LightPathDiagnostics(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.fsp = self.system.bmc
        self.host = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.system.goto_state(OpSystemState.OS)

    def lpd_init(self):
        # Check if system has LED support
        if not self.system.has_host_led_support():
            self.skipTest("System has no LED support")

        self.assertTrue(self.host.host_check_dt_node_exist("ibm,opal/leds"),
                        "ibm,opal/leds DT Node doesn't exist")

        # If it has support, check for led's presence
        res = self.host.host_run_command("ls /sys/class/leds/ | wc -l")
        self.assertNotEqual(int(''.join(res).strip()), 0,
                            "No LED's found in sysfs /sys/class/leds/")

        self.fsp.fsp_get_console()
        if not self.fsp.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

    def get_location_codes(self):
        res = self.host.host_run_command("usysident")
        loc_codes = []
        for loc in res:
            loc_codes.append(loc.split("\t")[0])
        return loc_codes

    def get_sysattn_indicator_loc(self):
        res = self.host.host_run_command("usysattn")
        loc_codes = []
        for loc in res:
            loc_codes.append(loc.split("\t")[0])
        return loc_codes[0]


class UsysIdentifyTest(LightPathDiagnostics):
    '''
    This function tests usysident identification of LEDs
    '''

    def runTest(self):
        self.lpd_init()
        loc_codes = self.get_location_codes()
        log.debug("Executing indicator identify tests")
        # Using -l option(Location code) Identifying a single device
        for loc in loc_codes:
            log.debug("Turn on indicator {} from Host".format(loc))
            self.host.host_run_command(
                "usysident -l {} -s identify".format(loc))
            tries = 20
            for i in range(1, tries+1):
                response = self.host.host_run_command(
                    "usysident -l {}".format(loc))
                if "on" in ''.join(response):
                    break
                time.sleep(1)
            self.assertIn("on", response,
                          "Turn ON of indicator {} failed".format(loc))
            log.debug("Current identification state of {} is ON".format(loc))

        self.host.host_run_command("usysident")

        # Setting to normal state of device(Turn off Device)
        for loc in loc_codes:
            log.debug("Turn off {} from Host".format(loc))
            self.host.host_run_command("usysident -l {} -s normal".format(loc))
            tries = 20
            for i in range(1, tries+1):
                response = self.host.host_run_command(
                    "usysident -l {}".format(loc))
                if "off" in ''.join(response):
                    break
                time.sleep(1)
            self.assertIn("off", response,
                          "Turn OFF {} failed".format(loc))
            log.debug("Current identification state of {} is OFF".format(loc))


class UsysAttnFSPTest(LightPathDiagnostics):
    '''
    This function tests system attention indicator LED
    '''

    def runTest(self):
        self.lpd_init()
        loc_code = self.get_sysattn_indicator_loc()
        log.debug("Executing system attention indicator tests")
        response = self.fsp.fsp_run_command("ledscommandline -V")
        log.debug(response)
        # Setting system attention indicator from FSP
        log.debug("Setting system attention indicator from FSP")
        response = self.fsp.fsp_run_command("ledscommandline -a -s")
        log.debug(response)
        response = self.fsp.fsp_run_command("ledscommandline -a -q")
        log.debug(response)
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.host.host_run_command(cmd)
            if "on" in ''.join(response):
                break
            time.sleep(1)
        self.assertIn("on", response,
                      "Turn ON of system attention indicator is failed")
        log.debug("Current system attention indicator state is ON")

        # Clearing(resetting) system attention indicator from FSP
        log.debug("Clearing system attention indicator from FSP")
        response = self.fsp.fsp_run_command("ledscommandline -a -r")
        log.debug(response)
        response = self.fsp.fsp_run_command("ledscommandline -a -q")
        log.debug(response)
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.host.host_run_command(cmd)
            if "off" in ''.join(response):
                break
            time.sleep(1)
        self.assertIn("off", response,
                      "Turn OFF of system attention indicator is failed")
        log.debug("Current system attention indicator state is OFF")


class UsysAttnHostTest(LightPathDiagnostics):
    '''
    This function tests system attention indicator LED
    '''

    def runTest(self):
        self.lpd_init()
        loc_code = self.get_sysattn_indicator_loc()
        log.debug("Executing system attention indicator tests")
        # Setting system attention indicator from HOST
        log.debug("Setting system attention indicator from Host")
        cmd = "echo 1 > /sys/class/leds/%s:attention/brightness" % loc_code
        self.host.host_run_command(cmd)
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.host.host_run_command(cmd)
            if "on" in ''.join(response):
                break
            time.sleep(1)
        self.assertIn("on", response,
                      "Turn ON of system attention indicator is failed")
        log.debug("Current system attention indicator state is ON")

        # Clearing(resetting) system attention indicator
        log.debug("Clearing system attention indicator from Host")
        cmd = "echo 0 > /sys/class/leds/%s:attention/brightness" % loc_code
        self.host.host_run_command(cmd)
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.host.host_run_command(cmd)
            if "off" in ''.join(response):
                break
            time.sleep(1)
        self.assertIn("off", response,
                      "Turn OFF of system attention indicator is failed")
        log.debug("Current system attention indicator state is OFF")


class UsysFaultTest(LightPathDiagnostics):
    '''
    This function tests usysfault identification of LED's
    '''

    def runTest(self):
        self.lpd_init()
        loc_codes = self.get_location_codes()
        log.debug("Executing fault indicator tests for all fault locators")
        for indicator in loc_codes:
            log.debug("Test for {} locator".format(indicator))
            # Setting a fault indicator from HOST os
            log.debug("Setting fault indicator {} from Host".format(indicator))
            cmd = "echo 1 > /sys/class/leds/{}:fault/brightness".format(
                indicator)
            self.host.host_run_command(cmd)
            tries = 10
            for i in range(1, tries+1):
                cmd = "usysattn -l %s" % indicator
                response = self.host.host_run_command(cmd)
                if "on" in ''.join(response):
                    break
                time.sleep(1)
            self.assertIn("on", response,
                          "Turn ON of fault indicator {} is failed".format(
                              indicator))
            log.debug("Current fault indicator state of {} is ON".format(
                indicator))

            # Clearing fault indicator from Host OS
            log.debug("Clearing fault indicator %s from Host OS" % indicator)
            cmd = "usysattn -l %s -s normal" % indicator
            self.host.host_run_command(cmd)
            tries = 10
            for i in range(1, tries+1):
                cmd = "usysattn -l %s" % indicator
                response = self.host.host_run_command(cmd)
                if "off" in response:
                    break
                time.sleep(1)
            self.assertIn("off", response,
                          "Turn OFF of fault indicator %s is failed".format(
                              indicator))
            log.debug("Current fault indicator state of %s is OFF" % indicator)


def suite():
    s = unittest.TestSuite()
    s.addTest(UsysIdentifyTest())
    s.addTest(UsysAttnHostTest())
    s.addTest(UsysFaultTest())
    return s


def extended_suite():
    s = unittest.TestSuite()
    s.addTest(UsysIdentifyTest())
    s.addTest(UsysAttnFSPTest())
    s.addTest(UsysAttnHostTest())
    s.addTest(UsysFaultTest())
    return s
