#!/usr/bin/python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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
# Secureboot IPL Tests

import unittest
import pexpect

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed
from testcases.OpTestFlash import PNORFLASH

class SecureBoot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.bmc_type = conf.args.bmc_type
        self.pupdate_binary = conf.args.pupdate
        self.pflash = conf.args.pflash
        self.pupdate = conf.args.pupdate
        self.securemode = conf.args.secure_mode

    def verify_boot_pass(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    def verify_boot_fail(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console().get_console()
        self.cv_SYSTEM.sys_power_on()
        count = 4
        boot = False
        while count != 0:
            try:
                console.expect("ISTEP", timeout=30)
                boot = True
            except pexpect.TIMEOUT:
                count -= 1
            if boot:
                return False
        return True

    def wait_for_sb_kt_start(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console().get_console()
        console.expect("sbe|Performing Secure Boot key transition", timeout=300)

    def wait_for_shutdown(self):
        console = self.cv_SYSTEM.sys_get_ipmi_console().get_console()
        console.expect("shutdown complete", timeout=100)

    def verify_opal_sb(self):
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
        data = " ".join(c.run_command("cat /sys/firmware/opal/msglog | grep -i stb"))
        part_list = ["CAPP", "IMA_CATALOG", "BOOTKERNEL", "VERSION"]
        if self.securemode:
            if not "secure mode on" in data:
                self.assertTrue(False, "OPAL: Secure mode is detected as OFF")
        for part in part_list:
            msg = "STB: %s verified" % part
            if not msg in data:
                self.assertTrue(False, "OPAL: %s is not verified" % part)

    def verify_dt_sb(self):
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
        c.run_command("lsprop /proc/device-tree/ibm,secureboot")
        if self.securemode:
            c.run_command("ls /proc/device-tree/ibm,secureboot/secure-enabled")
        c.run_command("ls /proc/device-tree/ibm,secureboot/compatible")
        c.run_command("ls /proc/device-tree/ibm,secureboot/hw-key-hash-size")
        c.run_command("ls /proc/device-tree/ibm,secureboot/hw-key-hash")
        c.run_command("ls /proc/device-tree/ibm,secureboot/name")
        value = c.run_command("cat /proc/device-tree/ibm,secureboot/compatible")[-1]
        if "ibm,secureboot-v2" in value:
            c.run_command("ls /proc/device-tree/ibm,secureboot/ibm,cvc")
            c.run_command("ls /proc/device-tree/ibm,secureboot/ibm,cvc/compatible")
            c.run_command("ls /proc/device-tree/ibm,secureboot/ibm,cvc/memory-region")

class VerifyOPALSecureboot(SecureBoot):

    def setUp(self):
        conf = OpTestConfiguration.conf
        super(VerifyOPALSecureboot, self).setUp()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_sb()
        self.verify_opal_sb()

class UnSignedPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot IPL test: Ensure prevention of boot with improperly signed PNOR.
    SB Mode  | sign mode | Boot result
    ----------------------------------
     ON      |  Unsigned |  Fail
     OFF     |  Unsigned |  Pass
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.un_signed_pnor
        super(UnSignedPNOR, self).setUp()

    def runTest(self):
        PNORFLASH.pnor = self.pnor
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        super(UnSignedPNOR, self).runTest()
        if not self.securemode:
            self.verify_boot_pass()
            self.verify_dt_sb()
            self.verify_opal_sb()
        else:
            self.assertTrue(self.verify_boot_fail(), "Unexpected system boot")
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)

class SignedPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot IPL test: Ensure successful boot with properly signed PNOR.
    SB Mode  | sign mode | Boot result
    ----------------------------------
     ON      |  Signed |  Pass
     OFF     |  Signed |  Pass
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.signed_pnor
        super(SignedPNOR, self).setUp()

    def runTest(self):
        PNORFLASH.pnor = self.pnor
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        super(SignedPNOR, self).runTest()
        self.verify_boot_pass()
        self.verify_dt_sb()
        self.verify_opal_sb()

class KeyTransitionPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot key transition test: Ensure successful key transition in SEEPROM
    Types of Key Transition PNOR images
    =============
    dev to dev
    dev to prod
    prod to dev
    prod to prod
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.kt_pnor = conf.args.key_transition_pnor
        super(KeyTransitionPNOR, self).setUp()

    def runTest(self):
        if not self.securemode:
            return
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        PNORFLASH.pnor = self.kt_pnor
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        super(KeyTransitionPNOR, self).runTest()
        self.cv_SYSTEM.sys_power_on()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.wait_for_sb_kt_start()
        # system should power off automatically after key transition finishes
        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        self.wait_for_shutdown()
        print "set state, going to off"
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

def secureboot_suite():
    s = unittest.TestSuite()
    s.addTest(UnSignedPNOR())
    s.addTest(SignedPNOR())
    s.addTest(KeyTransitionPNOR())
    s.addTest(SignedPNOR())
    return s
