#!/usr/bin/env python2
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
# Trustedboot IPL Tests
# This tests expect a TPM chip to be installed/removed on the system
# and also a secureboot mode enabled/disabled accordingly.
# If TPM chip is installed --> provide --trusted-mode in command line
# If secureboot is enabled --> provide --secure-mode in command line
#
# The "TPM Required" policy means:
# enabled: Node must have at least 1 functional TPM to boot, otherwise system will terminate
# disabled: Node can boot without a functional TPM
# ==================
# If system has a working TPM, the policy is a don't care.  If secure mode is not enabled, the policy is a don't care.
# if you set policy to "enabled" and remove/inject error on TPM -and- system is in secure mode,  system boot will terminate
# if you set policy to disable and remove/inject error on the TPM -and- system is in secure mode, system will still boot
#

import unittest
import pexpect

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

class TrustedBoot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.bmc_type = conf.args.bmc_type
        self.trustedmode = conf.args.trusted_mode
        self.tpm_policy = True
        self.securemode = conf.args.secure_mode

    def wait_for_system_shutdown(self):
        console = self.cv_SYSTEM.console.get_console()
        console.expect("System shutting down with error status", timeout=100)
        console.expect("RC_TPM_NOFUNCTIONALTPM_FAIL", timeout=50)
        console.expect("================================================", timeout=20)

    def verify_opal_tb(self):
        c = self.cv_SYSTEM.console
        self.cpu = ''.join(c.run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))
        print self.cpu
        if self.cpu in ["POWER9"]:
            part_list = ["CAPP", "IMA_CATALOG", "BOOTKERNEL", "VERSION"]
        elif self.cpu in ["POWER8"]:
            part_list = ["CAPP", "BOOTKERNEL"]
        else:
           self.skipTest("OPAL TB test not supported on %s" % self.cpu)

        data = " ".join(c.run_command("cat /sys/firmware/opal/msglog | grep -i stb")) 
        if self.trustedmode:
            if not "trusted mode on" in data:
                self.assertTrue(False, "OPAL: trusted mode is detected as OFF")
        else:
            if not "trusted mode off" in data:
                self.assertTrue(False, "OPAL: trusted mode is detected as ON")
            return

        for part in part_list:
            msg = "STB: %s hash calculated" % part
            if not msg in data:
                self.assertTrue(False, "OPAL: %s hash not calculated" % part)
            msg = "STB: %s measured on pcr" % part
            if not msg in data:
                self.assertTrue(False, "OPAL: %s hash not measured on TPM PCR register" % part)

        msg = "STB: EV_SEPARATOR measured on pcr"
        if not msg in data:
            self.assertTrue(False, "OPAL: EV_SEPARATOR measured on TPM PCR registers")

    def verify_dt_tb(self):
        c = self.cv_SYSTEM.console
        c.run_command("lsprop /proc/device-tree/ibm,secureboot")

        if not self.trustedmode:
            return

        c.run_command("ls --color=never /proc/device-tree/ibm,secureboot/trusted-enabled")
        res = c.run_command("find /proc/device-tree/ -name *tpm*")
        tpm_path = res[-1]
        c.run_command("lsprop %s" % tpm_path)
        c.run_command("cat %s/compatible" % tpm_path)
        c.run_command("cat %s/status" % tpm_path)
        c.run_command("cat %s/name" % tpm_path)
        c.run_command("cat %s/label" % tpm_path)
        c.run_command("ls --color=never %s/linux,sml-base" % tpm_path)
        c.run_command("ls --color=never %s/linux,sml-size" % tpm_path)
        c.run_command("ls --color=never %s/link-id" % tpm_path)

    def tearDown(self):
        if self.securemode and not self.trustedmode:
            self.cv_SYSTEM.sys_disable_tpm()
        return

class VerifyOPALTrustedBoot(TrustedBoot):
    '''
    a. It verify whether OPAL measures and records of all the resources
       it loads from PNOR.
    b. It also verifies the corresponding DT properties for trustedboot
       and TPM device.
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        super(VerifyOPALTrustedBoot, self).setUp()

    def runTest(self):
        if not self.trustedmode:
            return

        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_tb()
        self.verify_opal_tb()

class FunctionalTPM_PolicyOFF(TrustedBoot):
    '''
    Functional TPM, TPM Required(cleared)
        - Test IPL, Measurements & event logs(Secure Mode Override jumper(s) ON or OFF)
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        super(FunctionalTPM_PolicyOFF, self).setUp()

    def runTest(self):
        if not self.trustedmode:
            self.skipTest("This test needs a functional TPM installed on system")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_disable_tpm()
        self.assertFalse(self.cv_SYSTEM.sys_is_tpm_enabled(), "BMC failed to disable TPM policy")
        self.tpm_policy = False
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_tb()
        self.verify_opal_tb()


class FunctionalTPM_PolicyON(TrustedBoot):
    '''
    Functional TPM, TPM Required(set) 
        - Test IPL, Measurements & event logs(Secure Mode Override jumper(s) can be ON or OFF)
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        super(FunctionalTPM_PolicyON, self).setUp()

    def runTest(self):
        if not self.trustedmode:
            self.skipTest("This test needs a functional TPM installed on system")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_enable_tpm()
        self.assertTrue(self.cv_SYSTEM.sys_is_tpm_enabled(), "BMC failed to enable TPM policy")
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_tb()
        self.verify_opal_tb()

class NoFunctionalTPM_PolicyOFF(TrustedBoot):
    '''
    No Functional TPM, TPM Required(cleared)
        - Test IPL, Measurements & event logs(Secure Mode Override jumper(s) can be ON or OFF)
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        super(NoFunctionalTPM_PolicyOFF, self).setUp()

    def runTest(self):
        if self.trustedmode:
            self.skipTest("This test needs a functional TPM removed from system")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_disable_tpm()
        self.assertFalse(self.cv_SYSTEM.sys_is_tpm_enabled(), "BMC failed to disable TPM setting policy")
        self.tpm_policy = False
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_tb()
        self.verify_opal_tb()

class NoFunctionalTPM_PolicyON(TrustedBoot):
    '''
    No Functional TPM, TPM Required(set)
        - Test IPL, Measurements & event logs(Secure Mode Override jumper(s) can be ON or OFF)
    '''
    def setUp(self):
        conf = OpTestConfiguration.conf
        super(NoFunctionalTPM_PolicyON, self).setUp()

    def runTest(self):
        if self.trustedmode:
            self.skipTest("This test needs a functional TPM removed from system")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_enable_tpm()
        self.assertTrue(self.cv_SYSTEM.sys_is_tpm_enabled(), "BMC failed to enable TPM policy")
        if self.securemode:
            self.cv_SYSTEM.sys_power_on()
            self.wait_for_system_shutdown()
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.sys_disable_tpm() 
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.verify_dt_tb()
        self.verify_opal_tb()

def trustedboot_suite():
    s = unittest.TestSuite()
    s.addTest(VerifyOPALTrustedBoot())
    s.addTest(FunctionalTPM_PolicyOFF())
    s.addTest(FunctionalTPM_PolicyON())
    s.addTest(NoFunctionalTPM_PolicyOFF())
    s.addTest(NoFunctionalTPM_PolicyON())
    return s
