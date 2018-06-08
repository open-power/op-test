#!/usr/bin/python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestOCC.py $
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

# @package OpTestOCC
#  OCC Control package for OpenPower testing.
#
#  This class will test the functionality of following.
#  1. OCC Reset\Enable\Disable

import time
import subprocess
import re
import sys
import os
import random

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class OpTestOCCBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_FSP = conf.bmc()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.rest = conf.system().rest
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        if "OpenBMC" in self.bmc_type:
            self.occ_ids = self.rest.get_occ_ids()

    def do_occ_reset_fsp(self):
        cmd = "tmgtclient --reset_occ_clear=0xFF; echo $?"
        res = self.cv_FSP.fspc.run_command(cmd)
        self.assertEqual(int(res[-1]), 0, "occ reset command failed from fsp")

    def do_occ_reset(self):
        print "OPAL-PRD: OCC Enable"
        self.c.run_command(BMC_CONST.OCC_ENABLE)
        print "OPAL-PRD: OCC DISABLE"
        self.c.run_command(BMC_CONST.OCC_DISABLE)
        print "OPAL-PRD: OCC RESET"
        self.c.run_command(BMC_CONST.OCC_RESET)

    ##
    # @brief This function is used to get OCC status enable/disable.
    #
    # @return BMC_CONST.FW_SUCCESS - OCC's are active or 
    #         BMC_CONST.FW_FAILED  - OCC's are not in active state
    #
    def check_occ_status(self):
        if "OpenBMC" in self.bmc_type:
            for id in self.occ_ids:
                if not self.rest.is_occ_active(id):
                    return BMC_CONST.FW_FAILED
            return BMC_CONST.FW_SUCCESS

        l_status = self.cv_IPMI.ipmi_get_occ_status()
        print l_status
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            print "OCC's are up and active"
            return BMC_CONST.FW_SUCCESS
        else:
            print "OCC's are not in active state"
            return BMC_CONST.FW_FAILED

    def get_cpu_freq(self):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.c.run_command(l_cmd)
        return cur_freq[0].strip()

    ##
    # @brief sets the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency of cpu to be set
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def set_cpu_freq(self, i_freq):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo %s > $i; done" % i_freq
        self.c.run_command(l_cmd)

    ##
    # @brief verify the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency to be verified with cpu frequency
    def verify_cpu_freq(self, i_freq):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.c.run_command(l_cmd)
        if not cur_freq[0].strip() == i_freq:
            # (According to Vaidy) it may take milliseconds to have the
            # request for a frequency change to come into effect.
            # So, if we happen to be *really* quick checking the result,
            # we may have checked before it has taken effect. So, we
            # sleep for a (short) amount of time and retry.
            time.sleep(0.2)
            cur_freq = self.c.run_command(l_cmd)

        self.assertEqual(cur_freq[0].strip(), i_freq,
                         "CPU frequency not changed to %s" % i_freq)

    ##
    # @brief sets the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be set for all cpu's
    def set_cpu_gov(self, i_gov):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo %s > $i; done" % i_gov
        self.c.run_command(l_cmd)

    ##
    # @brief verify the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be verified with cpu governer
    def verify_cpu_gov(self, i_gov):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        cur_gov = self.c.run_command(l_cmd)
        self.assertEqual(cur_gov[0].strip(), i_gov, "CPU governor not changed to %s" % i_gov)


    def get_list_of_cpu_freq(self):
        # Get available cpu scaling frequencies
        l_res = self.c.run_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies")
        freq_list = l_res[0].split(' ')[:-1] # remove empty entry at end
        print freq_list
        return freq_list

    def dvfs_test(self):
        freq_list = self.get_list_of_cpu_freq()
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        for i in range(1, 20):
            i_freq = random.choice(freq_list)
            self.set_cpu_freq(i_freq)
            try:
                self.verify_cpu_freq(i_freq)
            except AssertionError as ae:
                print str(ae)

    def set_and_get_cpu_freq(self):
        freq_list = self.get_list_of_cpu_freq()
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        i_freq = random.choice(freq_list)
        self.set_cpu_freq(i_freq)
        cur_freq = self.get_cpu_freq() # Only cpu0 frequency
        return cur_freq


    def tearDown(self):
        try:
            pass
#            self.cv_HOST.host_gather_opal_msg_log()
#            self.cv_HOST.host_gather_kernel_log()
        except:
            print "Failed to collect debug info"

class OpTestOCCBasic(OpTestOCCBase):

    # Check basic test of occ disable when system is in standby
    # and occ enable when it is in runtime
    def test_occ_active(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        if self.cv_SYSTEM.get_state() in [OpSystemState.PETITBOOT, OpSystemState.PETITBOOT_SHELL,
                                           OpSystemState.BOOTING, OpSystemState.OS]:
            self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                                "OCC's are not in active state")
        elif self.cv_SYSTEM.get_state() == OpSystemState.OFF:
            self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_SUCCESS,
                                "OCC's are still in active state")

class OpTestOCC(OpTestOCCBase):

    def _test_occ_reset(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                "OCC's are not in active state")
        cur_freq = self.set_and_get_cpu_freq()
        self.do_occ_reset()
        tries = 10
        for j in range(1, tries):
            print "Waiting for OCC Enable\Disable (%d\%d)"%(j,tries)
            time.sleep(10)
            rc = self.check_occ_status()
            if rc == BMC_CONST.FW_SUCCESS:
                break
        if rc == BMC_CONST.FW_FAILED:
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
        self.assertNotEqual(rc, BMC_CONST.FW_FAILED,
                "OCC's are not in active state")
        # verify pstate restored to last requested pstate before occ reset
        # Make the fail less noisy, as it is less priority one
        try:
            self.verify_cpu_freq(cur_freq)
        except AssertionError as ae:
            print str(ae)
        self.dvfs_test()

class OpTestOCCFull(OpTestOCCBase):

    ##
    # @brief This function is used to test OCC Reset funtionality in BMC based systems.
    #        OCC Reset reload is limited to 3 times per full power cycle.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_reset_functionality(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
            "OCC's are not in active state")
        max_reset_count = 4
        for i in range(1, max_reset_count+1):
            print "*******************OCC Reset count %d*******************" % i
            cur_freq = self.set_and_get_cpu_freq()
            self.do_occ_reset()
            tries = 30
            for j in range(1, tries):
                print "Waiting for OCC Enable\Disable (%d\%d)"%(j,tries)
                time.sleep(10)
                rc = self.check_occ_status()
                if rc == BMC_CONST.FW_SUCCESS:
                    break
            # on 4th interation occ's will be disabled, do dvfs when occ's are active
            if i < max_reset_count:
                self.assertNotEqual(rc, BMC_CONST.FW_FAILED,
                    "OCC's are not in active state")
                # verify pstate restored to last requested pstate before occ reset
                try:
                    self.verify_cpu_freq(cur_freq)
                except AssertionError as ae:
                    print str(ae)
                self.dvfs_test()
        if rc == BMC_CONST.FW_FAILED:
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
        # After max_reset_count times occ reset, occ's will be disabled
        self.assertEqual(rc, BMC_CONST.FW_FAILED,
            "OCC's are still in active state after max occ reset count %s" % max_reset_count) 
        print "OCC\'s are not in active state, rebooting the system"
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

    ##
    # @brief This function is used to test OCC Reset funtionality in BMC based systems.
    #        OCC Reset reload can be done more than 3 times per full power cycle, by
    #        resetting OCC resetreload count.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_reset_n_times(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
            "OCC's are not in active state")

        for i in range(1, BMC_CONST.OCC_RESET_RELOAD_COUNT):
            print "*******************OCC Reset count %d*******************" % i
            self.do_occ_reset()
            tries = 30
            for j in range(1, tries):
                time.sleep(10)
                print "Waiting for OCC Enable\Disable (%d\%d)"%(j,tries)
                rc = self.check_occ_status()
                if rc == BMC_CONST.FW_SUCCESS:
                    break
            if rc == BMC_CONST.FW_FAILED:
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
            self.assertNotEqual(rc, BMC_CONST.FW_FAILED,
                "OCC's are not in active state")
            self.dvfs_test()
            print "OPAL-PRD: occ query reset reload count"
            self.c.run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)
            print "OPAL-PRD: occ reset reset/reload count"
            self.c.run_command(BMC_CONST.OCC_SET_RESET_RELOAD_COUNT)
            print "OPAL-PRD: occ query reset reload count"
            self.c.run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)

    ##
    # @brief This function is used to test OCC Enable and Disable funtionality in BMC based systems.
    #        There is no limit for occ enable and disable, as of now doing 10 times in a loop.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_occ_enable_disable_functionality(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
            "OCC's are not in active state")
        for count in range(1,7):
            print "OPAL-PRD: OCC Enable"
            self.c.run_command(BMC_CONST.OCC_ENABLE)
            print "OPAL-PRD: OCC Disable"
            self.c.run_command(BMC_CONST.OCC_DISABLE)
            tries = 12
            for i in range(1, tries):
                print "Waiting for OCC Enable\Disable (%d\%d)"%(i,tries)
                time.sleep(10)
                rc = self.check_occ_status()
                if rc == BMC_CONST.FW_SUCCESS:
                    break
            # If occ's are disabled re-IPL the system
            if rc == BMC_CONST.FW_FAILED:
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
            self.dvfs_test()

class OCCRESET_FSP(OpTestOCCBase):

    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP OCC Reset test")
        count = 10
        for i in range(1, count+1):
            self.c.run_command("dmesg -C")
            cur_freq = self.set_and_get_cpu_freq()
            self.do_occ_reset_fsp()
            tries = 50
            recovered = False
            for j in range(1, tries):
                print "Waiting for OCC Active (%d\%d)"%(j,tries)
                time.sleep(1)
                try:
                    res = self.c.run_command("dmesg | grep -i 'OCC Active'")
                    recovered = True
                    break
                except CommandFailed as cf:
                    pass

            self.assertTrue(recovered, "OCC's are not in active state or reset notification to host is failed")
            # verify pstate restored to last requested pstate before occ reset
            self.verify_cpu_freq(cur_freq)
            self.dvfs_test()

class OCC_RESET(OpTestOCC):
    def runTest(self):
        self._test_occ_reset()

def basic_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(OpTestOCCBasic)

def full_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(OpTestOCCFull)
