#!/usr/bin/python
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

#  @package LightPathDiagnostics
#  Currently runs only in FSP platforms
#

import time
import subprocess
import re

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class LightPathDiagnostics(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()

    def lpd_init(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL LPD tests")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        msg = "usysident is not supported on the PowerKVM Host platform"
        res = self.cv_HOST.host_run_command("usysident")
        self.assertNotIn(msg, res, "LightPathDiagnostics is not supported")

    def get_location_codes(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        res = console.run_command("usysident")
        loc_codes = []
        for loc in res:
            loc_codes.append(loc.split("\t")[0])
        return loc_codes

    def get_sysattn_indicator_loc(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        res = console.run_command("usysattn")
        loc_codes = []
        for loc in res:
            loc_codes.append(loc.split("\t")[0])
        return loc_codes[0]

class UsysIdentifyTest(LightPathDiagnostics):

    ##
    # @brief This function tests usysident identification of LED's
    #
    def runTest(self):
        self.lpd_init()
        loc_codes = self.get_location_codes()
        print "Executing indicator identify tests"
        # Using -l option(Location code) Identifying a single device
        for loc in loc_codes:
            print "Turn on identification indicator %s from Host OS" % loc
            self.cv_HOST.host_run_command("usysident -l %s -s identify" % (loc))
            tries = 20
            for i in range(1, tries+1):
                response = self.cv_HOST.host_run_command("usysident -l %s" % (loc))
                if "on" in response:
                    break
                time.sleep(1)
            self.assertIn("on", response,
                    "Turn ON of identification indicator %s is failed" % loc)
            print "Current identification state of %s is ON" % loc

        self.cv_HOST.host_run_command("usysident")

        # Setting to normal state of device(Turn off Device)
        for loc in loc_codes:
            print "Turn off identification indicator %s from Host OS" % loc
            self.cv_HOST.host_run_command("usysident -l %s -s normal" % (loc))
            tries = 20
            for i in range(1, tries+1):
                response = self.cv_HOST.host_run_command("usysident -l %s" % (loc))
                if "off" in response:
                    break
                time.sleep(1)
            self.assertIn("off", response,
                    "Turn OFF of identification indicator %s is failed" % loc)
            print "Current identification state of %s is OFF" % loc

class UsysAttnTest(LightPathDiagnostics):

    ##
    # @brief This function tests system attention indicator LED
    #
    def runTest(self):
        self.lpd_init()
        loc_code = self.get_sysattn_indicator_loc()
        print "Executing system attention indicator tests"
        response = self.cv_FSP.fsp_run_command("ledscommandline -V")
        print response
        # Setting system attention indicator from FSP
        print "Setting system attention indicator from FSP"
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -s")
        print response
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -q")
        print response
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.cv_HOST.host_run_command(cmd)
            if "on" in response:
                break
            time.sleep(1)
        self.assertIn("on", response,
                "Turn ON of system attention indicator is failed")
        print "Current system attention indicator state is ON"

        # Clearing(resetting) system attention indicator from FSP
        print "Clearing system attention indicator from FSP"
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -r")
        print response
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -q")
        print response
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.cv_HOST.host_run_command(cmd)
            if "off" in response:
                break
            time.sleep(1)
        self.assertIn("off", response,
                "Turn OFF of system attention indicator is failed")
        print "Current system attention indicator state is OFF"

        # Setting system attention indicator from HOST
        print "Setting system attention indicator from Host"
        cmd = "echo 1 > /sys/class/leds/%s:attention/brightness" % loc_code
        self.cv_HOST.host_run_command(cmd)
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -q")
        print response
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.cv_HOST.host_run_command(cmd)
            if "on" in response:
                break
            time.sleep(1)
        self.assertIn("on", response,
                "Turn ON of system attention indicator is failed")
        print "Current system attention indicator state is ON"

        # Clearing(resetting) system attention indicator
        print "Clearing system attention indicator from FSP"
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -r")
        print response
        response = self.cv_FSP.fsp_run_command("ledscommandline -a -q")
        print response
        tries = 10
        for i in range(1, tries+1):
            cmd = "usysattn -l %s" % loc_code
            response = self.cv_HOST.host_run_command(cmd)
            if "off" in response:
                break
            time.sleep(1)
        self.assertIn("off", response,
                "Turn OFF of system attention indicator is failed")
        print "Current system attention indicator state is OFF"

class UsysFaultTest(LightPathDiagnostics):

    ##
    # @brief This function tests usysfault identification of LED's
    #
    def runTest(self):
        self.lpd_init()
        loc_codes = self.get_location_codes()
        print "Executing fault indicator tests for all fault locators"
        for indicator in loc_codes:
            print "***************Test for %s locator*************" % indicator
            # Setting a fault indicator from HOST os
            print "Setting fault indicator %s from Host OS" % indicator
            cmd = "echo 1 > /sys/class/leds/%s:fault/brightness" % indicator
            self.cv_HOST.host_run_command(cmd)
            tries = 10
            for i in range(1, tries+1):
                cmd = "usysattn -l %s" % indicator
                response = self.cv_HOST.host_run_command(cmd)
                if "on" in response:
                    break
                time.sleep(1)
            self.assertIn("on", response,
                    "Turn ON of fault indicator %s is failed" % indicator)
            print "Current fault indicator state of %s is ON" % indicator

            # Clearing fault indicator from Host OS
            print "Clearing fault indicator %s from Host OS" % indicator
            cmd = "usysattn -l %s -s normal" % indicator
            self.cv_HOST.host_run_command(cmd)
            tries = 10
            for i in range(1, tries+1):
                cmd = "usysattn -l %s" % indicator
                response = self.cv_HOST.host_run_command(cmd)
                if "off" in response:
                    break
                time.sleep(1)
            self.assertIn("off", response,
                    "Turn OFF of fault indicator %s is failed" % indicator)
            print "Current fault indicator state of %s is OFF" % indicator

def suite():
    s = unittest.TestSuite()
    s.addTest(UsysIdentifyTest())
    s.addTest(UsysAttnTest())
    s.addTest(UsysFaultTest())
    return s
