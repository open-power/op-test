#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

# Basic IPL and reboot tests

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class BasicIPL(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.util = OpTestUtil()
        self.pci_good_data_file = conf.lspci_file()

class BootToPetitboot(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting BootToPetitboot test")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        log.debug("IPL: BootToPetitboot test passed")

class BootToPetitbootShell(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting BootToPetitbootShell test")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        log.debug("IPL: BootToPetitbootShell test passed")

class GotoPetitbootShell(BasicIPL):
    """
    We goto petitboot shell rather than do the off/on-to-petitboot
    shell so that the skiroot test suite time to run each test is
    a bit more accurate, rather than hiding the first IPL in the
    first test that's run.
    """
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

class SoftPowerOff(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting SoftPowerOff test")
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        self.cv_SYSTEM.sys_power_soft()
        log.debug("IPL: soft powered off")
        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        log.debug("set state, going to off")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        log.debug("IPL: SoftPowerOff test completed")

class BMCReset(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting BMCReset test")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_BMC.reboot()

        c = 0
        while True:
            try:
                self.cv_SYSTEM.sys_wait_for_standby_state()
            except OpTestError as e:
                c+=1
                if c == 10:
                    raise e
            else:
                break

        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        log.debug("IPL: BMCReset test completed")

class BootToOS(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting BootToOS test")
        log.debug("IPL: Currently powered off!")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.debug("IPL: BootToOS test completed")
        # We booted, SHIP IT!

class OutOfBandWarmReset(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting OutOfBandWarmReset test")
        # FIXME currently we have to go via OFF to ensure we go to petitboot
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        # TODO skip if no IPMI
        # TODO use abstracted out-of-band warm reset
        self.cv_SYSTEM.sys_warm_reset()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        log.debug("IPL: OutOfBandWarmReset test completed")

class HardPowerCycle(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting HardPowerCycle test")
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        self.cv_SYSTEM.sys_power_reset()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        log.debug("IPL: HardPowerCycle test completed")

class PowerOff(BasicIPL):
    def runTest(self):
        log.debug("IPL: starting PowerOff test")
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        self.cv_SYSTEM.sys_power_off()
        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        log.debug("IPL: PowerOff test completed")

def suite():
    suite = unittest.TestSuite()
    # We add these in a somewhat hard-coded order simply to minimise
    # needless reboots
    suite.addTest(BootToPetitboot())
    suite.addTest(SoftPowerOff())
    suite.addTest(BMCReset())
    suite.addTest(BootToOS())
    suite.addTest(OutOfBandWarmReset())
    suite.addTest(HardPowerCycle())
    suite.addTest(PowerOff())
    return suite
