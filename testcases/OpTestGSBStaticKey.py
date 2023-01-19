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
        self.hmc_con = self.cv_HMC.ssh
        # Variables required for this test
        self.os_secureboot = False
        self.dt_secureboot = False
        self.lockdown = False
        self.sys_lockdown = ""
        self.grubFilename = ""
        self.prepDisk = ""
        self.signature = "~Module signature appended~"

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        os_level = self.cv_HOST.host_get_OS_Level()
        if 'Red Hat' in os_level:
            self.distro = 'rhel'
        elif 'SLES' in os_level:
            self.distro = 'sles'
        else:
            raise self.skipTest("Test currently supported on "
                                "SLES and RHEL releases")

    def check_hmc_secureboot_state(self):
        '''
        Return
        'True' in case of Secure boot enabled
        'False' in case of Secure boot disabled
        '''
        # HMC command to know the current state of Secure Boot
        cmd = ("lssyscfg -r lpar -m %s -F curr_secure_boot --filter "
               "lpar_names=%s" %
               (self.cv_HMC.mg_system, self.cv_HMC.lpar_name))
        output = self.hmc_con.run_command(cmd, timeout=300)
        if int(output[0]) == 2: # Value '2' means Secure Boot enabled
            return True
        elif int(output[0]) == 0: # Value '0' means Secure Boot disabled
            return False

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
        hmc_secureboot = self.check_hmc_secureboot_state()
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

    def checkKernel(self):
        vmlinux = "vmlinuz" # RHEL
        if self.distro == 'sles':
            vmlinux = "vmlinux"
        # Checking whether the kernel is signed or not
        cmd = "strings /boot/%s-$(uname -r) | tail -1" % vmlinux
        out = self.c.run_command(cmd)
        fail_msg = "%s - Kernel is not signed" % self.distro
        self.assertIn(self.signature, out, fail_msg)

    def checkGrub(self):
        # Checking whether the grub is signed or not
        cmd = "strings %s | tail -1" % self.grubFilename
        out = self.c.run_command(cmd)
        fail_msg = "Grub is not signed"
        self.assertIn(self.signature, out, fail_msg)

    def getRHELFiles(self):
        '''
        Get the signed grub file details, this is the manual step required for
        RHEL OS
        '''
        cmd = "rpm -ql grub2-ppc64le"
        out = self.c.run_command(cmd)
        for line in out:
            if 'core.elf' in line:
                self.grubFilename = line
        if not self.grubFilename:
            self.fail("%s: Failed to get grub file" % self.distro)

    def os_secureboot_enable(self, enable=True):
        '''
        To enable/disable the Secure Boot at Operating System level.
        Parameter enable=True for enabling Secure Boot
        Parameter enable=False for disabling Secure Boot
        '''        
        self.checkKernel()
        if self.distro == 'rhel' and enable:
            # Get the PReP disk file
            self.getPRePDisk()
            # Get the all the required files
            self.getRHELFiles()
            self.checkGrub()
            # Running grub2-install on PReP disk
            out = self.c.run_command("grub2-install %s" % self.prepDisk)
            if "Installation finished. No error reported." not in out:
                self.fail("RHEL: Failed to install on PReP partition")
            # Copy the signed grub in to the PReP disk using 'dd' command
            out = self.c.run_command("dd if=%s of=%s || echo 'no'" %
                                     (self.grubFilename, self.prepDisk))
            if "no" in "".join(out):
                self.fail("RHEL: Failed to copy to PReP partition")
        elif self.distro == 'rhel' and not enable:
            # Nothing to do for Secure Boot disable for RHEL at OS level
            pass
        bfile = "/etc/sysconfig/bootloader"
        if self.distro == 'sles' and enable:
            # Add SECURE_BOOT="yes" at file  /etc/sysconfig/bootloader
            cmd = "sed -i '/SECURE_BOOT=\"no\"/c\SECURE_BOOT=\"yes\"' %s" % bfile
            self.c.run_command(cmd)
            out = self.c.run_command("pbl --install || echo 'no' ")
            if "no" in "".join(out):
                self.fail("SLES: Failed to enable Secure Boot")
        elif self.distro == 'sles' and not enable:
            # Add SECURE_BOOT="no" at file  /etc/sysconfig/bootloader
            cmd = "sed -i '/SECURE_BOOT=\"yes\"/c\SECURE_BOOT=\"no\"' %s" % bfile
            self.c.run_command(cmd)
            out = self.c.run_command("pbl --install || echo 'no'")
            if "no" in "".join(out):
                self.fail("SLES: Failed to disable Secure Boot")

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
        out = self.c.run_command("lsprop  /proc/device-tree/ibm,secure-boot")
        '''
        Possible output:
        /proc/device-tree/ibm,secure-boot
		 00000002
        '''
        for line in out:
            if '00000002' in line: # Value '2' indicates Secure Boot enabled.
                self.dt_secureboot = True
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
        hmc_secureboot = self.check_hmc_secureboot_state()
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
