#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2025
# [+] International Business Machines Corp.
# Author: Krishan Gopal Saraswat <krishang@linux.ibm.com>
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

'''
This test validates the Dynamic Key Guest Secure Boot process by 
checking kernel configurations, verifying kernel and GRUB signatures, 
setting up the required environment, and toggling the secure boot 
state on and off.
'''

import unittest
import os
import time
import OpTestConfiguration
import OpTestLogger
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class DynamicKeyGuestSecureBoot(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.cv_HMC = self.cv_SYSTEM.hmc

        # Power on LPAR if it's not running
        # This is needed because the test shuts down LPAR during execution
        if self.cv_HMC:
            from common.OpTestHMC import OpHmcState
            try:
                lpar_state = self.cv_HMC.get_lpar_state()
                log.info(f"LPAR current state: {lpar_state}")
                
                # If LPAR is not running, power it on
                if lpar_state not in ["Running", "Booting"]:
                    log.info(f"LPAR is '{lpar_state}'. Powering on LPAR...")
                    self.cv_HMC.poweron_lpar()
                    log.info("LPAR powered on successfully")
                else:
                    log.info(f"LPAR is already {lpar_state}")
            except Exception as e:
                log.warning(f"Could not check/power on LPAR: {e}")
        
        # Ensure LPAR is in OS state
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        
        # Get SSH connection to the LPAR
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.kernel_version = self.connection.run_command("cd /boot && uname -r")[0]
        self.distro_name = self.util.distro_name()
        try:
            self.cv_HOST.host_run_command("which strings")
            log.info("'strings' command is available")
        except Exception:
            log.warning("'strings' command not found. Installing binutils package...")
            try:
                if self.distro_name == 'rhel':
                    self.cv_HOST.host_run_command("dnf install -y binutils || yum install -y binutils")
                elif self.distro_name == 'sles':
                    self.cv_HOST.host_run_command("zypper install -y binutils")
                log.info("binutils package installed successfully")
            except Exception as install_error:
                self.fail(f"Failed to install binutils package: {install_error}. "
                         "The 'strings' command is required for signature verification.")
    
    def check_kernel_config(self):
        try:
            # List of required kernel configurations
            required_configs = [
                "CONFIG_PPC_MEM_KEYS",
                "CONFIG_TRUSTED_KEYS",
                "CONFIG_PPC_SECURE_BOOT",
                "CONFIG_IMA_SECURE_AND_OR_TRUSTED_BOOT",
                "CONFIG_IMA_MEASURE_ASYMMETRIC_KEYS",
                "CONFIG_LOAD_PPC_KEYS",
                "CONFIG_INTEGRITY_TRUSTED_KEYRING",
                "CONFIG_INTEGRITY_PLATFORM_KEYRING",
                "CONFIG_INTEGRITY_MACHINE_KEYRING",
                "CONFIG_SECONDARY_TRUSTED_KEYRING",
                "CONFIG_SYSTEM_BLACKLIST_KEYRING",
                "CONFIG_MODULE_SIG_KEY_TYPE_RSA"
            ]

            # First check if kernel config file exists
            config_file = f"/boot/config-{self.kernel_version}"
            try:
                self.cv_HOST.host_run_command(f"test -e {config_file}")
                log.info(f"Found kernel config file: {config_file}")
            except Exception as e:
                self.fail(f"Kernel config file not found at {config_file}: {str(e)}")
            
            # Check each required configuration
            missing_configs = []
            for config in required_configs:
                try:
                    result = self.cv_HOST.host_check_config(self.kernel_version, config)
                    if result not in ['y', 'm']:
                        missing_configs.append(f"{config} (not set)")
                    else:
                        log.info(f"Found {config}={result}")
                except Exception as e:
                    if "not set" in str(e):
                        missing_configs.append(f"{config} (not set)")
                    else:
                        log.error(f"Error checking config {config}: {str(e)}")
                        missing_configs.append(f"{config} (error: {str(e)})")
            
            # If any configurations are missing, fail the test with detailed message
            if missing_configs:
                error_msg = "Missing or incorrectly configured kernel options:\n"
                for config in missing_configs:
                    error_msg += f"- {config}\n"
                error_msg += "\nPlease ensure these kernel configurations are enabled (y) or built as modules (m)."
                self.fail(error_msg)
            
            log.info("All required kernel configurations are present")
            
        except Exception as e:
            self.fail(f"Error checking kernel configurations: {str(e)}")
                

    def kernel_grub_signature_check(self):
        """Check kernel and grub signatures"""
        try:
            self.kernel_signature = self.util.check_kernel_signature()
            self.grub_filename = self.util.get_grub_file()
            self.grub_signature = self.util.check_grub_signature(self.grub_filename)
            
            log.info("Kernel signed: %s, Grub file: %s, Grub signed: %s",
                     self.kernel_signature, self.grub_filename, self.grub_signature)
            if not self.kernel_signature:
                self.fail("Kernel is not signed - required for secure boot")
            if not self.grub_signature:
                self.fail(f"Grub is not signed - required for secure boot: {self.grub_filename}")
                
        except Exception as e:
            log.error("Kernel/Grub signature check failed: %s", e)
            self.fail(f"Kernel/Grub signature check failed: {e}")

    def get_secure_boot_status(self):
        """
        Get current secure boot and keystore status.
        """
        command = f"lssyscfg -r lpar -m {self.cv_HMC.mg_system} --filter \"lpar_names={self.cv_HMC.lpar_name}\" | sed s/,/\\\n/g | grep \"secure_boot\\|keystore\""
        return self.cv_HMC.ssh.run_command(command)

    def setup_dynamic_secure_boot(self):
        """Setup dynamic secure boot environment"""
        try:
            log.info("Starting dynamic secure boot setup")
            # Shutdown LPAR and wait ~30s
            self.cv_HMC.poweroff_lpar()
            time.sleep(30)
            
            # Configure dynamic secure boot parameters using HMC utility method
            self.cv_HMC.configure_dynamic_secure_boot(enable=True, keystore_kbytes=64)
            
            # Allow the HMC to settle
            time.sleep(10)
            
            # Get and log current status
            status = self.get_secure_boot_status()
            log.info("Current secure boot status:")
            for line in status:
                log.info(line)
            
            # Start the LPAR
            self.cv_HMC.poweron_lpar()
            log.info("Dynamic secure boot environment setup completed successfully")
        except Exception as e:
            error_msg = f"Failed to setup dynamic secure boot environment: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def reset_secure_boot(self):
        """Reset all secure boot settings to zero"""
        try:
            log.info("Resetting secure boot settings to zero")

            # Setup and run secvarctl to reset PK
            from testcases.OpTestSecvarctl import SecvarctlTest
            sec = SecvarctlTest()
            
            # Initialize SecvarctlTest with required attributes
            sec.conf = self.conf
            sec.util = self.util
            sec.cv_HOST = self.cv_HOST
            sec.distro_name = self.distro_name
            sec.cv_SYSTEM = self.cv_SYSTEM
            sec.connection = self.connection
            sec.host_cmd_timeout = self.host_cmd_timeout
            
            # Set up secvarctl repository details
            try:
                sec.secvar_repo = self.conf.args.git_repo
                sec.branch = self.conf.args.git_branch
                sec.home = self.conf.args.git_home
            except AttributeError:
                sec.secvar_repo = "https://github.com/open-power/secvarctl"
                sec.branch = "main"
                sec.home = "/home"
            
            log.info("Setting up secvarctl for PK reset...")
            
            # Run setUp to install dependencies and configure
            try:
                sec.setUp()
            except Exception as e:
                log.warning(f"secvarctl setUp encountered an issue: {e}")
            
            # Build secvarctl
            log.info("Building secvarctl...")
            sec.build_secvarctl()
            
            # Generate keys and auth files
            log.info("Generating secvarctl keys and auth files...")
            sec.generate_keys()
            
            # Now use the generated auth files to reset PK
            auth_dir = os.path.join(sec.build_path, 'test', 'testdata', 'guest', 'authfiles')
            log.info(f"Using authfiles at {auth_dir} to reset PK")
            
            try:
                cmd = f"cd {auth_dir} && {sec.build_path}/build/secvarctl write PK reset_PK_by_PK.auth"
                out = self.connection.run_command(cmd)
                for l in out:
                    log.info(l)
                log.info("PK reset completed successfully using secvarctl")
            except Exception as e:
                self.fail(f"Failed to run secvarctl write on guest: {e}")

            # After PK reset, zero the HMC secure-boot parameters
            # Shutdown LPAR and wait ~30s
            self.cv_HMC.poweroff_lpar()
            time.sleep(30)
            
            # First, disable secure boot (must be done before disabling keystore)
            log.info("Disabling secure boot before resetting keystore parameters")
            self.cv_HMC.hmc_secureboot_on_off(enable=False)
            time.sleep(5)
            
            # Start LPAR to release keystore, then shutdown again
            log.info("Starting LPAR to release keystore")
            self.cv_HMC.poweron_lpar()
            time.sleep(30)
            log.info("Shutting down LPAR to reset keystore parameters")
            self.cv_HMC.poweroff_lpar()
            time.sleep(30)
            
            # Now configure keystore-related params to zero using HMC utility method
            # Note: This may fail with HSCL0DC8 if keystore is in use, which is expected
            log.info("Attempting to reset keystore parameters to zero")
            try:
                self.cv_HMC.configure_dynamic_secure_boot(enable=False, keystore_kbytes=0)
                log.info("Keystore parameters reset successfully")
            except Exception as e:
                # Keystore reset may fail if it's been used - this is expected behavior
                log.warning(f"Keystore parameters could not be reset: {e}")
                log.warning("This is expected when keystore has been used. Secure boot has been disabled.")
            
            # Allow HMC to settle
            time.sleep(10)
            # Get and log current status
            output = self.get_secure_boot_status()
            log.info("Current secure boot status after reset attempt:")
            for line in output:
                log.info(line)
            # Start the LPAR
            self.cv_HMC.poweron_lpar()

            # Cleanup via SecvarctlTest.tearDown()
            try:
                sec.tearDown()
                log.info("secvarctl artifacts cleaned up successfully")
            except Exception as e:
                log.warning(f"secvarctl tearDown reported an error: {e}")

            log.info("Secure boot reset completed")
        except Exception as e:
            error_msg = f"Failed to reset secure boot settings: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def runTest(self):
        # Check required kernel configurations are present
        self.check_kernel_config()
        # Check kernel and grub signatures
        self.kernel_grub_signature_check()
        # Setup dynamic secure boot
        self.setup_dynamic_secure_boot()
        
        # Enable secure boot - must poweroff first (LPAR must be off to change secure boot)
        log.info("Enabling secure boot")
        self.cv_HMC.poweroff_lpar()
        time.sleep(5)
        self.cv_HMC.hmc_secureboot_on_off(enable=True)
        self.cv_HMC.poweron_lpar()
        
        # Reset secure boot
        self.reset_secure_boot()
        
        # Disable secure boot - must poweroff first
        log.info("Disabling secure boot")
        self.cv_HMC.poweroff_lpar()
        time.sleep(5)
        self.cv_HMC.hmc_secureboot_on_off(enable=False)
        self.cv_HMC.poweron_lpar()