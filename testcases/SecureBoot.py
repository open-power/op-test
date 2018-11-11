#!/usr/bin/env python3
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

'''
Secureboot IPL Tests
--------------------
'''

import unittest
import pexpect

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed
from testcases.OpTestFlash import PNORFLASH
from testcases.OpTestFlash import OpalLidsFLASH

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


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
        raw_pty = self.cv_SYSTEM.console.get_console()
        self.cv_SYSTEM.sys_power_on()
        count = 4
        boot = False
        while count != 0:
            try:
                raw_pty.expect("ISTEP", timeout=30)
                boot = True
            except pexpect.TIMEOUT:
                count -= 1
            if boot:
                return False
        return True

    def wait_for_secureboot_enforce(self):
        raw_pty = self.cv_SYSTEM.console.get_console()
        self.cv_SYSTEM.sys_power_on()
        raw_pty.expect("STB: secure mode enforced, aborting.", timeout=300)
        raw_pty.expect("secondary_wait", timeout=20)
        raw_pty.expect("host_voltage_config", timeout=100)

    def wait_for_sb_kt_start(self):
        raw_pty = self.cv_SYSTEM.console.get_console()
        raw_pty.expect(
            "sbe|Performing Secure Boot key transition", timeout=300)

    def wait_for_shutdown(self):
        raw_pty = self.cv_SYSTEM.console.get_console()
        raw_pty.expect("shutdown complete", timeout=100)

    def verify_opal_sb(self):
        c = self.cv_SYSTEM.console

        self.cpu = ''.join(c.run_command(
            "grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))
        log.debug(self.cpu)
        if self.cpu in ["POWER9"]:
            part_list = ["CAPP", "IMA_CATALOG", "BOOTKERNEL", "VERSION"]
        elif self.cpu in ["POWER8"]:
            part_list = ["CAPP", "BOOTKERNEL"]
        else:
            self.skipTest("OPAL SB test not supported on %s" % self.cpu)

        data = " ".join(c.run_command(
            "cat /sys/firmware/opal/msglog | grep -i stb"))
        if self.securemode:
            if not "secure mode on" in data:
                self.assertTrue(
                    False, "OPAL-SB: Secure mode is detected as OFF")
        for part in part_list:
            msg = "STB: %s verified" % part
            if not msg in data:
                self.assertTrue(
                    False, "OPAL-SB: %s verification failed or not happened" % part)

    def verify_dt_sb(self):
        c = self.cv_SYSTEM.console

        # Check for STB support - /ibm,secureboot DT node should exist
        try:
            c.run_command("ls --color=never /proc/device-tree/ibm,secureboot")
        except CommandFailed:
            if self.securemode:
                self.assertTrue(
                    False, "OPAL-SB: ibm,secureboot DT node not created")
            else:
                self.skipTest("Secureboot not supported on this system")
        c.run_command("lsprop /proc/device-tree/ibm,secureboot")
        if self.securemode:
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/secure-enabled")
        c.run_command(
            "ls --color=never /proc/device-tree/ibm,secureboot/compatible")
        c.run_command(
            "ls --color=never /proc/device-tree/ibm,secureboot/hw-key-hash")
        c.run_command("ls --color=never /proc/device-tree/ibm,secureboot/name")
        value = c.run_command(
            "cat /proc/device-tree/ibm,secureboot/compatible")[-1]
        if "ibm,secureboot-v2" in value:
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/hw-key-hash-size")
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/ibm,cvc")
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/ibm,cvc/compatible")
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/ibm,cvc/memory-region")
        elif "ibm,secureboot-v1" in value:
            c.run_command(
                "ls --color=never /proc/device-tree/ibm,secureboot/hash-algo")


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

    ======= ========= ===========
    SB Mode sign mode Boot result
    ======= ========= ===========
    ON      Unsigned  Fail
    OFF     Unsigned  Pass
    ======= ========= ===========
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.un_signed_pnor
        super(UnSignedPNOR, self).setUp()

    def runTest(self):
        if not self.pnor:
            self.skipTest("Un-signed/improper signed PNOR image not provided")
        PNORFLASH.pnor = self.pnor
        super(UnSignedPNOR, self).runTest()
        if not self.securemode:
            self.verify_boot_pass()
            self.verify_dt_sb()
            self.verify_opal_sb()
        else:
            self.assertTrue(self.verify_boot_fail(), "Unexpected system boot")
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)


class SignedPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot IPL test: Ensure successful boot with properly signed PNOR.

    ======= ========= ===========
    SB Mode sign mode Boot result
    ======= ========= ===========
    ON      Signed    Pass
    OFF     Signed    Pass
    ======= ========= ===========
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.signed_pnor
        super(SignedPNOR, self).setUp()

    def runTest(self):
        if not self.pnor:
            self.skipTest("signed PNOR image not provided")
        PNORFLASH.pnor = self.pnor
        super(SignedPNOR, self).runTest()
        self.verify_boot_pass()
        self.verify_dt_sb()
        self.verify_opal_sb()


class SignedToPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot IPL test: Ensure successful boot with properly
    signed to PNOR(To match the keys which are got replaced after
    KeyTransitionPNOR flash test).

    ======= ========= ===========
    SB Mode sign mode Boot result
    ======= ========= ===========
    ON      Signed    Pass
    OFF     Signed    Pass
    ======= ========= ===========
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.pnor = conf.args.signed_to_pnor
        super(SignedToPNOR, self).setUp()

    def runTest(self):
        if not self.pnor:
            self.skipTest("signed PNOR image not provided")
        PNORFLASH.pnor = self.pnor
        super(SignedToPNOR, self).runTest()
        self.verify_boot_pass()
        self.verify_dt_sb()
        self.verify_opal_sb()


class KeyTransitionPNOR(SecureBoot, PNORFLASH):
    '''
    Secure boot key transition test: Ensure successful key transition in SEEPROM
    Types of Key Transition PNOR images:

    - dev to dev
    - dev to prod
    - prod to dev
    - prod to prod
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.kt_pnor = conf.args.key_transition_pnor
        super(KeyTransitionPNOR, self).setUp()

    def runTest(self):
        if not self.kt_pnor:
            self.skipTest("No key transition PNOR image is provided")
        console = self.cv_SYSTEM.console
        PNORFLASH.pnor = self.kt_pnor
        super(KeyTransitionPNOR, self).runTest()
        self.cv_SYSTEM.sys_power_on()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.wait_for_sb_kt_start()
        # system should power off automatically after key transition finishes
        self.cv_SYSTEM.set_state(OpSystemState.POWERING_OFF)
        self.wait_for_shutdown()
        log.debug("set state, going to off")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)


class OPALContainerTest(SecureBoot, OpalLidsFLASH):
    '''
    System having Signed PNOR(either production or developement mode)
    Flash signed containers with wrong keys
    Secureboot verify should fail and boot should abort
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.skiboot = None
        self.skiroot_kernel = None
        self.skiroot_initramfs = None
        self.test_containers = conf.args.test_container
        super(OPALContainerTest, self).setUp()

    def runTest(self):
        test_list = []
        if not self.test_containers:
            self.skipTest("No test containers provided")
        known_part_list = ["BOOTKERNEL", "CAPP", "IMA_CATALOG", "VERSION"]
        # sort list with known order list
        for item in known_part_list:
            for pair in self.test_containers:
                if item in pair[0]:
                    test_list.append(pair)
        for container in test_list:
            OpalLidsFLASH.flash_part_list = [container]
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            super(OPALContainerTest, self).runTest()
            if self.securemode:
                self.wait_for_secureboot_enforce()
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
                self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            else:
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)


def secureboot_suite():
    s = unittest.TestSuite()
    s.addTest(UnSignedPNOR())
    s.addTest(SignedPNOR())
    s.addTest(OPALContainerTest())
    s.addTest(SignedPNOR())
    s.addTest(KeyTransitionPNOR())
    s.addTest(SignedToPNOR())
    return s
