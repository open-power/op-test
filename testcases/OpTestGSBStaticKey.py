#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestGSBStaticKey.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
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
OpTestGSBStaticKey
------------
Test Enable and Disable Secure boot

Steps:
Grub and kernel files should be signed with appended signatures
Enable/Disable Secure boot at Operating System level
Shutdown LPAR
Enable/Disable Secure boot at HMC level
Activate LPAR
'''
import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil

class OpTestGSBStaticKey(unittest.TestCase):
    """
    Class OpTestGSBStaticKey:
    """
    def setUp(self):
        # Connection variables
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.c = self.cv_HMC.get_host_console()
        self.cs = self.cv_SYSTEM.console
        self.hmc_con = self.cv_HMC.ssh
        # Variables required for this test
        self.os_secureboot = False
        self.dt_secureboot = False
        self.lockdown = False
        self.sys_lockdown = ""
        self.prepDisk = ""
        self.backup_prep_filename = "/root/save-prep"

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        os_level = self.cv_HOST.host_get_OS_Level()
        if 'Red Hat' in os_level:
            self.distro = 'rhel'
        elif 'SLES' in os_level:
            self.distro = 'sles'
        else:
            raise self.skipTest("Test currently supported on "
                                "SLES and RHEL releases")

        self.util = OpTestUtil(conf)
        self.distro_version = self.util.get_distro_version()
        self.kernel_signature = self.util.check_kernel_signature()
        self.grub_filename = self.util.get_grub_file()
        self.grub_signature = self.util.check_grub_signature(self.grub_filename)
        self.dt_secureboot = self.util.check_os_level_secureboot_state()

    def hmc_secureboot_on_off(self, enable=True):
        '''
        Enable/Disable Secure Boot from HMC
        1. PowerOFF/Shutdown LPAR from HMC
        2. Enable/Disable Secure boot using 'chsyscfg' command
        3. PowerON/Activate the LPAR and boot to Operating System
        '''
        # PowerOFF/shutdown LPAR from HMC
        self.cv_HMC.poweroff_lpar()
        # Set Secure Boot value using HMC command
        cmd = ('chsyscfg -r lpar -m %s -i "name=%s, secure_boot=' %
               (self.cv_HMC.mg_system, self.cv_HMC.lpar_name))
        if enable: # Value '2' to enable Secure Boot
            cmd = '%s2"' % cmd
        else: # Value '0' to disable Secure Boot
            cmd = '%s0"' % cmd
        self.hmc_con.run_command(cmd, timeout=300)
        # PowerON/Activate LPAR and Boot the Operating System
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
 
        # Checking What Secure Boot state got set,
        # according to the required enable/disable
        hmc_secureboot = self.cv_HMC.check_lpar_secureboot_state(self.hmc_con)
        if enable and not hmc_secureboot:
                self.fail("HMC: Failed to enable Secure Boot")
        elif not enable and hmc_secureboot:
                self.fail("HMC: Failed to disable Secure Boot")

    def getPRePDisk(self):
        '''
        Identify the PReP partition, this disk name is required to copy
        signed grub. This manual step required for RHEL OS only.
        '''
        out = self.c.run_command('sfdisk -l')
        for line in out:
            if "PPC PReP Boot" in line:
                self.prepDisk = line.split(" ")[0]
                break
        if not self.prepDisk:
            self.fail("%s: Failed to get PReP partition name" % self.distro)
    
    def backup_restore_PRepDisk(self, action):
        if action == "backup":
            out = self.c.run_command("dd if=%s of=%s" % (self.prepDisk, self.backup_prep_filename))
        if action == "restore":
            out = self.c.run_command("dd if=%s of=%s" % (self.backup_prep_filename, self.prepDisk))
        for line in out:
            if "No" in line:
                self.fail("Failed to %s the PRep partition." % (action))

    def os_secureboot_enable(self, enable=True):
        '''
        To enable/disable the Secure Boot at Operating System level.
        Parameter enable=True for enabling Secure Boot
        Parameter enable=False for disabling Secure Boot
        '''
        if self.kernel_signature == True:
            if self.distro == 'rhel' and enable:
                # Check if Secure Boot is already enabled at HMC.
                # If yes, then disable the same.
                # This has to be done to handle the issue seen while copying core.elf into 
                # PReP partition on RHEL8.x versions
                if "8." in self.distro_version:
                    hmc_secureboot = self.cv_HMC.check_lpar_secureboot_state(self.hmc_con)
                    if hmc_secureboot:
                        # disable the SB at hmc and then proceed ahead.
                        enable = False
                        self.hmc_secureboot_on_off(enable=enable)
                        # now check if it has been disabled correctly.
                        hmc_secureboot = self.cv_HMC.check_lpar_secureboot_state(self.hmc_con)
                        enable = True
                        if hmc_secureboot and not enable:
                            self.fail("HMC: Failed to disable Secure Boot")

                # Get the PReP disk file
                self.getPRePDisk()
                self.backup_restore_PRepDisk(action="backup")
                #Proceed ahead only if the grub is signed
                if self.grub_signature == True:
                    # Running grub2-install on PReP disk
                    out = self.c.run_command("grub2-install %s" % self.prepDisk)
                    for line in out:
                        if "Installation finished. No error reported." not in out:
                            # Restore the PRep partition back to its original state
                            self.backup_restore_PRepDisk(action="restore")
                            self.fail("RHEL: Failed to install on PReP partition")
                    
                    out = self.c.run_command("dd if=%s of=%s; echo $?" % 
                                             (self.grub_filename, self.prepDisk))
                    if "0" not in out[3]:
                        # Restore the PRep partition back to its original state
                        self.backup_restore_PRepDisk(action="restore")
                        self.fail("RHEL: Failed to copy to PReP partition")
            elif self.distro == 'rhel' and not enable:
                # Nothing to do for Secure Boot disable for RHEL at OS level
                pass
        else:
            self.fail("%s - Kernel is not signed" % (self.distro))

    def collectData(self):
        self.c.run_command("uname -a")
        self.c.run_command("lsmcode")
        self.c.run_command("cat /etc/os-release")

        # Reset the global variables else these variables will contain 'true'
        # for secure boot disable case
        self.os_secureboot = False
        self.lockdown = False
        self.dt_secureboot = False

        # From 'dmesg' output collect Secure Boot and Lockdown status
        out = self.c.run_command("dmesg | grep -i 'secure boot\|lockdown'")
        '''
        Possible output:
        Secure boot mode disabled
        Secure boot mode enabled
        Kernel is locked down from Power secure boot; see man kernel_lockdown.7
        '''
        # Parsing 'dmesg' output and checking what features are enabled
        for line in out:
            if 'Secure boot' in line and 'enabled' in line:
                    self.os_secureboot = True
            if 'locked down' in line:
                self.lockdown = True

        # Reading the device tree property of Secure Boot        
        self.dt_secureboot = self.util.check_os_level_secureboot_state()

        # Reading lockdown value
        out = self.c.run_command("cat /sys/kernel/security/lockdown")
        '''
        Possible output:
        none [integrity]
        none [integrity] confidentiality
        [none] integrity confidentiality
        '''
        # Starting index
        index1 = int(out[0].index('[')) + 1
        # Ending index
        index2 = int(out[0].index(']'))
        # Reading the lockdown current value
        self.sys_lockdown = out[0][index1:index2]

    def validateData(self, enable=True):
        # Check the hmc secure boot state
        hmc_secureboot = self.cv_HMC.check_lpar_secureboot_state(self.hmc_con)

        if enable: # enable state
            fail_msg = ("Lockdown expected mode: 'integrity', actual mode: %s"
                        % self.sys_lockdown)
            self.assertEqual(self.sys_lockdown, "integrity", fail_msg)
            # Expecting all the boolean values 'and' operation to be 'True'.
            if not (self.os_secureboot and self.lockdown and 
                    self.dt_secureboot and hmc_secureboot):
                self.fail("Secure boot enable states are inconsistent")
        else: # disable state
            fail_msg = ("Lockdown expected mode: 'none', actual mode: %s"
                        % self.sys_lockdown)
            self.assertEqual(self.sys_lockdown, "none", fail_msg)
            # Expecting all the boolean values 'or' operation to be 'False'.
            if (self.os_secureboot or self.lockdown or
                self.dt_secureboot or hmc_secureboot):
                self.fail("Secure boot disable states are inconsistent")

    def SecureBootEnable(self, enable=True):
        # Enable/Disable Secure Boot at Operating System
        self.os_secureboot_enable(enable=enable)
        # Enable/Disable Secure Boot at HMC
        self.hmc_secureboot_on_off(enable=enable)
        self.collectData()
        self.validateData(enable=enable)

class GSBStaticDisable(OpTestGSBStaticKey):
    '''
    Disable Secure Boot
    '''
    def runTest(self):
        super(OpTestGSBStaticKey, self).setUp()
        self.SecureBootEnable(enable=False)

class GSBStaticEnable(OpTestGSBStaticKey):
    '''
    Enable Secure Boot
    '''
    def runTest(self):
        super(OpTestGSBStaticKey, self).setUp()
        self.SecureBootEnable(enable=True)

def GSB_suite():
    s = unittest.TestSuite()
    s.addTest(GSBStaticEnable())
    s.addTest(GSBStaticDisable())
    return s
