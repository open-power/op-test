#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestFastReboot.py $
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
#

'''
OpTestFastReboot
----------------

Issue fast reboot in petitboot and host OS, on a system having
skiboot 5.4 rc1(which has fast-reset feature). Any further tests
on fast-reset system will be added here.
'''

import time
import pexpect
import subprocess
import commands
import re
import sys

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestFastReboot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type

    def number_reboots_to_do(self):
        return 2

    def boot_to_os(self):
        return False

    def do_things_while_booted(self):
        pass

    def reboot_command(self):
        return "reboot"

    def get_fast_reset_count(self, c):
        count = 0
        try:
            l = c.run_command(
                "grep 'RESET: Initiating fast' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            if cf.exitcode == 1:
                count = 0
                l = []
            else:
                raise cf
        for line in l:
            m = re.search('RESET: Initiating fast reboot ([0-9]*)', line)
            if m:
                if (int(m.group(1)) > count):
                    count = int(m.group(1))
        return count

    def runTest(self):
        '''
        This function tests fast reset of power systems.
        It will check booting sequence when reboot command
        getting executed in both petitboot and host OS
        '''

        if "qemu" in self.bmc_type:
            self.skipTest("Qemu platform doesn't have fast-reboot support")

        if self.boot_to_os():
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        else:
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        c = self.cv_SYSTEM.console

        try:
            fast_reboot_state = ''.join(c.run_command(
                "cat /proc/device-tree/ibm,opal/fast-reboot"))
            # skipTest throws exception when passing null at end
            # exception from skipTest produces malformed XML
            if fast_reboot_state[:4] != "okay":
                    self.skipTest("Fast reboot currently NOT supported, "
                        "/proc/device-tree/ibm,opal/fast-reboot: {}"
                                  .format(fast_reboot_state[:-1]))
        except CommandFailed as cf:
            if cf.exitcode is not 1:
                raise cf

        cpu = ''.join(c.run_command(
            "grep '^cpu' /proc/cpuinfo|uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))
        log.debug(repr(cpu))
        if cpu not in ["POWER9", "POWER8", "POWER8E"]:
            self.skipTest("Fast Reboot not supported on %s" % cpu)

        if not self.cv_SYSTEM.has_mtd_pnor_access():
            self.skipTest("OpTestSystem does not have MTD PNOR access,"
                          "so skipping Fast Reboot")

        c.run_command("nvram -p ibm,skiboot --update-config fast-reset=1")
        res = c.run_command("nvram --print-config=fast-reset -p ibm,skiboot")
        self.assertNotIn("0", res, "Failed to set the fast-reset mode")
        c.run_command(BMC_CONST.NVRAM_SET_FAST_RESET_MODE)
        res = c.run_command(BMC_CONST.NVRAM_PRINT_FAST_RESET_VALUE)
        self.assertIn("feeling-lucky", res,
                      "Failed to set the fast-reset mode")
        initialResetCount = self.get_fast_reset_count(c)
        log.debug("INITIAL reset count: %d" % initialResetCount)
        for i in range(0, self.number_reboots_to_do()):
            loopResetCount = self.get_fast_reset_count(c)
            # We do some funny things with the raw pty here, as
            # 'reboot' isn't meant to return
            self.pty = self.cv_SYSTEM.console.get_console()
            self.pty.sendline(self.reboot_command())
            self.cv_SYSTEM.set_state(OpSystemState.IPLing)
            # We're looking for a skiboot log message, that it's doing fast
            # reboot. We *may* not get this, as on some systems (notably IBM
            # FSP based systems) the skiboot log is *not* printed to IPMI
            # console
            if self.cv_SYSTEM.skiboot_log_on_console():
                rc = self.pty.expect([" RESET: Initiating fast reboot",
                                      pexpect.TIMEOUT, pexpect.EOF],
                                     timeout=100)
                if rc in [1, 2]:
                    c.close()  # close the console obj
            if self.boot_to_os():
                self.cv_SYSTEM.goto_state(OpSystemState.OS)
            else:
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            newResetCount = self.get_fast_reset_count(c)
            self.assertTrue(loopResetCount < newResetCount,
                            "Did not do fast reboot")
            self.assertTrue(initialResetCount < newResetCount,
                            "Did not do fast reboot")
            log.debug("Completed Fast reboot cycle %d" % i)
            self.do_things_while_booted()

        c.run_command(BMC_CONST.NVRAM_DISABLE_FAST_RESET_MODE)
        try:
            res = c.run_command(BMC_CONST.NVRAM_PRINT_FAST_RESET_VALUE)
        except CommandFailed as cf:
            self.assertEqual(cf.exitcode, 255,
                             "getting unset fast-reboot is meant to fail!")
        else:
            self.assertTrue(False, "We expected to fail at getting cleared "
                            "fast-reset nvram variable")


class FastRebootHost(OpTestFastReboot):
    def boot_to_os(self):
        return True


class FastRebootHostTorture(FastRebootHost):
    def boot_to_os(self):
        return True

    def number_reboots_to_do(self):
        return 1000

class FastRebootHostStress(FastRebootHost):
    def number_reboots_to_do(self):
        return 2

    def reboot_command(self):
        return "reboot -ff"

    def do_things_while_booted(self):
        c = self.cv_SYSTEM.console
        c.run_command("stress --cpu `nproc` --vm `nproc` --vm-bytes 128M > /dev/null &")
        c.run_command("sleep 120",timeout=200)
        c.run_command("uptime")

class FastRebootHostStressTorture(FastRebootHostStress):
    def number_reboots_to_do(self):
        return 200

class FastRebootTorture(OpTestFastReboot):
    def number_reboots_to_do(self):
        return 1000
