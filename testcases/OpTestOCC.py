#!/usr/bin/env python3
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

'''
OpTestOCC
---------

OCC Control package for OpenPower testing.

This class will test the functionality of following.

1. OCC Reset\Enable\Disable
'''

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

import testcases.OpTestEM

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestOCCBase(testcases.OpTestEM.OpTestEM):
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
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()  # use ssh, console is chatty
        if "OpenBMC" in self.bmc_type:
            self.occ_ids = self.rest.get_occ_ids()

    def do_occ_reset_fsp(self):
        cmd = "tmgtclient --reset_occ_clear=0xFF; echo $?"
        res = self.cv_FSP.fspc.run_command(cmd)
        self.assertEqual(int(res[-1]), 0, "occ reset command failed from fsp")

    def do_occ_reset(self):
        try:
            log.debug("OPAL-PRD: OCC Enable")
            self.c.run_command(BMC_CONST.OCC_ENABLE)
            log.debug("OPAL-PRD: OCC DISABLE")
            self.c.run_command(BMC_CONST.OCC_DISABLE)
            log.debug("OPAL-PRD: OCC Enable")
            self.c.run_command(BMC_CONST.OCC_ENABLE)
            log.debug("OPAL-PRD: OCC RESET")
            self.c.run_command(BMC_CONST.OCC_RESET)
        except Exception as e:
            log.debug("Unexpected problem, Exception={}".format(e))
            self.assertTrue(
                False, "Unexpected problem, Exception={}".format(e))

    def clear_occ_rr_count(self):
        # Clear the OCC reset reload count
        try:
            log.debug("OPAL-PRD: occ query reset reload count")
            self.c.run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)
            log.debug("OPAL-PRD: occ reset reset/reload count")
            self.c.run_command(BMC_CONST.OCC_SET_RESET_RELOAD_COUNT)
            log.debug("OPAL-PRD: occ query reset reload count")
            self.c.run_command(BMC_CONST.OCC_QUERY_RESET_COUNTS)
        except Exception as e:
            log.debug("Unexpected problem, Exception={}".format(e))
            self.assertTrue(
                False, "Unexpected problem, Exception={}".format(e))

    def check_occ_status(self):
        '''
        This function is used to get OCC status enable/disable.

        @return BMC_CONST.FW_SUCCESS - OCC's are active or
                BMC_CONST.FW_FAILED  - OCC's are not in active state
        '''
        if "OpenBMC" in self.bmc_type:
            for id in self.occ_ids:
                if not self.rest.is_occ_active(id):
                    return BMC_CONST.FW_FAILED
            return BMC_CONST.FW_SUCCESS

        l_status = self.cv_IPMI.ipmi_get_occ_status()
        log.debug(l_status)
        if BMC_CONST.OCC_DEVICE_ENABLED in l_status:
            log.debug("OCC's are up and active")
            return BMC_CONST.FW_SUCCESS
        else:
            log.warning("OCC's are not in active state")
            return BMC_CONST.FW_FAILED

    def get_cpu_freq(self):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.c.run_command(l_cmd)
        return cur_freq[0].strip()

    def dvfs_test(self):
        freq_list = self.get_list_of_cpu_freq()
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        for i in range(1, 20):
            i_freq = random.choice(freq_list)
            self.set_cpu_freq(i_freq)
            try:
                self.verify_cpu_freq(i_freq, and_measure=False)
            except AssertionError as ae:
                log.debug(str(ae))

    def set_and_get_cpu_freq(self):
        freq_list = self.get_list_of_cpu_freq()
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        i_freq = random.choice(freq_list)
        self.set_cpu_freq(i_freq)
        cur_freq = self.get_cpu_freq()  # Only cpu0 frequency
        return cur_freq

    def tearDown(self):
        try:
            pass
#            self.cv_HOST.host_gather_opal_msg_log()
#            self.cv_HOST.host_gather_kernel_log()
        except:
            log.debug("Failed to collect debug info")


class OpTestOCCBasic(OpTestOCCBase, unittest.TestCase):

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


class OpTestOCC(OpTestOCCBase, unittest.TestCase):

    def _test_occ_reset(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                            "OCC's are not in active state")
        cur_freq = self.set_and_get_cpu_freq()
        self.do_occ_reset()
        tries = 10
        for j in range(1, tries):
            log.debug("Waiting for OCC Enable\Disable (%d\%d)" % (j, tries))
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
            self.verify_cpu_freq(cur_freq, and_measure=False)
        except AssertionError as ae:
            log.debug(str(ae))
        self.dvfs_test()


class OpTestOCCFull(OpTestOCCBase, unittest.TestCase):
    '''
    This function is used to test OCC Reset funtionality in BMC based systems.
    OCC Reset reload is limited to 3 times per full power cycle.
    '''

    def test_occ_reset_functionality(self):
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                            "OCC's are not in active state")
        self.clear_occ_rr_count()
        max_reset_count = 4
        for i in range(1, max_reset_count+1):
            log.debug(
                "*******************OCC Reset count %d*******************" % i)
            cur_freq = self.set_and_get_cpu_freq()
            self.do_occ_reset()
            tries = 30
            for j in range(1, tries):
                log.debug("Waiting for OCC Enable\Disable (%d\%d)" %
                          (j, tries))
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
                    self.verify_cpu_freq(cur_freq, and_measure=False)
                except AssertionError as ae:
                    log.debug(str(ae))
                self.dvfs_test()
        if rc == BMC_CONST.FW_FAILED:
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
        # After max_reset_count times occ reset, occ's will be disabled
        self.assertEqual(rc, BMC_CONST.FW_FAILED,
                         "OCC's are still in active state after max occ reset count %s" % max_reset_count)
        log.debug("OCC\'s are not in active state, rebooting the system")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

    def test_occ_reset_n_times(self):
        '''
        This function is used to test OCC Reset funtionality in BMC based systems.
        OCC Reset reload can be done more than 3 times per full power cycle, by
        resetting OCC resetreload count.
        '''
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                            "OCC's are not in active state")

        for i in range(1, BMC_CONST.OCC_RESET_RELOAD_COUNT):
            log.debug(
                "*******************OCC Reset count %d*******************" % i)
            self.do_occ_reset()
            tries = 30
            for j in range(1, tries):
                time.sleep(10)
                log.debug("Waiting for OCC Enable\Disable (%d\%d)" %
                          (j, tries))
                rc = self.check_occ_status()
                if rc == BMC_CONST.FW_SUCCESS:
                    break
            if rc == BMC_CONST.FW_FAILED:
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
            self.assertNotEqual(rc, BMC_CONST.FW_FAILED,
                                "OCC's are not in active state")
            self.dvfs_test()
            self.clear_occ_rr_count()

    def test_occ_enable_disable_functionality(self):
        '''
        This function is used to test OCC Enable and Disable funtionality in BMC based systems.
        There is no limit for occ enable and disable, as of now doing 10 times in a loop.
        '''
        if any(s in self.bmc_type for s in ("FSP", "QEMU")):
            self.skipTest("OpenPower OCC Reset test")
        self.assertNotEqual(self.check_occ_status(), BMC_CONST.FW_FAILED,
                            "OCC's are not in active state")
        for count in range(1, 7):
            try:
                log.debug("OPAL-PRD: OCC Enable")
                self.c.run_command(BMC_CONST.OCC_ENABLE)
                log.debug("OPAL-PRD: OCC Disable")
                self.c.run_command(BMC_CONST.OCC_DISABLE)
                log.debug("OPAL-PRD: OCC Enable")
                self.c.run_command(BMC_CONST.OCC_ENABLE)
            except Exception as e:
                log.debug("Unexpected problem, Exception={}".format(e))
                self.assertTrue(
                    False, "Unexpected problem, Exception={}".format(e))

            tries = 12
            for i in range(1, tries):
                log.debug("Waiting for OCC Enable\Disable (%d\%d)" %
                          (i, tries))
                time.sleep(10)
                rc = self.check_occ_status()
                if rc == BMC_CONST.FW_SUCCESS:
                    break
            # If occ's are disabled re-IPL the system
            if rc == BMC_CONST.FW_FAILED:
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
            self.dvfs_test()


class OCCRESET_FSP(OpTestOCCBase, unittest.TestCase):

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
                log.debug("Waiting for OCC Active (%d\%d)" % (j, tries))
                time.sleep(1)
                try:
                    res = self.c.run_command("dmesg | grep -i 'OCC Active'")
                    recovered = True
                    break
                except CommandFailed as cf:
                    pass

            self.assertTrue(
                recovered, "OCC's are not in active state or reset notification to host is failed")
            # verify pstate restored to last requested pstate before occ reset
            self.verify_cpu_freq(cur_freq, and_measure=False)
            self.dvfs_test()


class OCC_RESET(OpTestOCC, unittest.TestCase):
    def runTest(self):
        self._test_occ_reset()


def basic_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(OpTestOCCBasic)


def full_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(OpTestOCCFull)
