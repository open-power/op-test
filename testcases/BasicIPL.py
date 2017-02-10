#!/usr/bin/python
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

class BasicIPL(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.bmc = conf.system().bmc()
        self.util = OpTestUtil()
        self.pci_good_data_file = conf.lspci_file()

class BootToPetitboot(BasicIPL):
    def runTest(self):
        self.system.goto_state(OpSystemState.OFF)
        self.system.goto_state(OpSystemState.PETITBOOT)

class SoftPowerOff(BasicIPL):
    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT)
        self.ipmi.ipmi_power_soft()
        print "soft powered off"
        self.system.set_state(OpSystemState.POWERING_OFF)
        print "set state, going to off"
        self.system.goto_state(OpSystemState.OFF)

class BMCReset(BasicIPL):
    def runTest(self):
        self.system.goto_state(OpSystemState.OFF)
        self.bmc.reboot()
        c = 0
        while True:
            try:
                self.ipmi.ipmi_wait_for_standby_state()
            except OpTestError as e:
                c+=1
                if c == 10:
                    raise e
            else:
                break

        self.system.set_state(OpSystemState.POWERING_OFF)
        self.system.goto_state(OpSystemState.OFF)

class BootToOS(BasicIPL):
    def runTest(self):
        print "Currently powered off!"
        self.system.goto_state(OpSystemState.OFF)
        self.system.goto_state(OpSystemState.OS)
        # We booted, SHIP IT!

class OutOfBandWarmReset(BasicIPL):
    def runTest(self):
        # FIXME currently we have to go via OFF to ensure we go to petitboot
        self.system.goto_state(OpSystemState.OFF)
        self.system.goto_state(OpSystemState.PETITBOOT)
        # TODO skip if no IPMI
        # TODO use abstracted out-of-band warm reset
        self.ipmi.ipmi_warm_reset()

class PowerOff(BasicIPL):
    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT)
        self.system.sys_power_off()
        self.system.set_state(OpSystemState.POWERING_OFF)
        self.system.goto_state(OpSystemState.OFF)

def suite():
    suite = unittest.TestSuite()
    # We add these in a somewhat hard-coded order simply to minimise
    # needless reboots
    suite.addTest(BootToPetitboot())
    suite.addTest(SoftPowerOff())
    suite.addTest(BMCReset())
    suite.addTest(BootToOS())
    suite.addTest(OutOfBandWarmReset())
    suite.addTest(PowerOff())
    return suite
