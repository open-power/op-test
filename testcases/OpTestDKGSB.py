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
import shlex

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class DynamicKeyGuestSecureBoot(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        # HMC object for performing HMC-level operations
        try:
            self.cv_HMC = self.cv_SYSTEM.hmc
        except Exception:
            self.cv_HMC = None
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.kernel_version = self.connection.run_command("cd /boot && uname -r")[0]
    
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
        """
        Check kernel and grub signatures.
        """
        try:
            if not getattr(self, 'util', None):
                self.util = OpTestUtil(self.conf)
            self.kernel_signature = self.util.check_kernel_signature()
            self.grub_filename = self.util.get_grub_file()
            try:
                self.grub_signature = self.util.check_grub_signature(self.grub_filename)
            except Exception as e:
                log.error("Grub signature check failed for '%s': %s", self.grub_filename, e)
                self.fail(f"Grub signature check failed for '{self.grub_filename}': {e}")
            log.info("Kernel signed: %s, Grub file: %s, Grub signed: %s",
                     self.kernel_signature, self.grub_filename, self.grub_signature)
            return True

        except Exception as e:
            log.error("Kernel/Grub signature check failed: %s", e)
            self.fail(f"Kernel/Grub signature check failed: {e}")

    def execute_hmc_command(self, command):
        """
        Execute HMC command and handle errors
        """
        self.ensure_hmc_available()
        try:
            result = self.cv_HMC.run_command(command)
            log.info(f"Command executed successfully on HMC: {command}")
            return result
        except Exception as e:
            error_msg = f"Failed to execute HMC command on HMC '{command}': {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def ensure_hmc_available(self):
        """
        Ensure the HMC object is available.
        """
        if not getattr(self, 'cv_HMC', None):
            msg = (
                "HMC object is not available (self.cv_HMC is None). "
            )
            log.error(msg)
            self.fail(msg)

    def get_secure_boot_status(self, host_name, system_name):
        """
        Get current secure boot and keystore status
        """
        self.ensure_hmc_available()
        command = f"lssyscfg -r lpar -m {system_name} --filter \"lpar_names={host_name}\" | sed s/,/\\\n/g | grep \"secure_boot\\|keystore\""
        return self.execute_hmc_command(command)

    def shutdown_lpar(self, host_name, system_name, sleep_time=5):
        """
        Shutdown LPAR and wait
        """
        self.ensure_hmc_available()
        command = f"chsysstate -o shutdown -r lpar -n {host_name} -m {system_name}"
        self.execute_hmc_command(command)
        time.sleep(sleep_time)

    def start_lpar(self, host_name, system_name, sleep_time=5):
        """
        Start LPAR and wait
        """
        self.ensure_hmc_available()
        command = f"chsysstate -o on -r lpar -n {host_name} -m {system_name}"
        self.execute_hmc_command(command)
        time.sleep(sleep_time)

    def configure_secure_boot(self, host_name, system_name, config_params):
        """
        Configure secure boot parameters
        """
        self.ensure_hmc_available()
        command = f"chsyscfg -r lpar -m {system_name} -i \"name={host_name}, {config_params}\""
        self.execute_hmc_command(command)

    def setup_dynamic_secure_boot(self, host_name, system_name):
        """
        Setup dynamic secure boot environment
        """
        try:
            log.info(f"Starting dynamic secure boot setup for host: {host_name}, system: {system_name}")
            # Ensure HMC is available
            self.ensure_hmc_available()
            # Step: Shutdown LPAR and wait ~30s
            self.shutdown_lpar(host_name, system_name, sleep_time=30)
            # Configure combined secure-boot parameters
            config_params = (
                "keystore_signed_updates_without_verification=1,"
                "keystore_signed_updates=1,"
                "linux_dynamic_key_secure_boot=1,"
                "keystore_kbytes=64"
            )
            self.configure_secure_boot(host_name, system_name, config_params)
            # Allow the HMC to settle
            time.sleep(10)
            # Get and log current status
            status = self.get_secure_boot_status(host_name, system_name)
            log.info("Current secure boot status:")
            for line in status:
                log.info(line)
            # Start the LPAR
            self.start_lpar(host_name, system_name)
            log.info("Dynamic secure boot environment setup completed successfully")
        except Exception as e:
            error_msg = f"Failed to setup dynamic secure boot environment: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def reset_secure_boot(self, host_name, system_name):
        """
        Reset all secure boot settings to zero by running HMC commands to
        configure the LPAR secure-boot-related parameters to zero.
        """
        try:
            log.info(f"Resetting secure boot settings to zero for host: {host_name}, system: {system_name}")

            # Run guest-side secvarctl to generate auth files.
            from testcases.OpTestSecvarctl import SecvarctlTest
            sec = SecvarctlTest()
            sec.connection = self.connection

            # Search for the parent workspace that contains the cloned repo
            try_paths = []
            if getattr(self, 'home', None):
                try_paths.append(os.path.join(self.home, 'secvarctl_*'))
            try_paths.append('/home/secvarctl_*')

            repo_root = None
            for p in try_paths:
                rc = self.connection.run_command(f"bash -c 'ls -d {p} 2>/dev/null | head -n1' || true")
                if rc and rc[0].strip():
                    repo_root = rc[0].strip()
                    break

            auth_dir = None
            if repo_root:
                candidate = os.path.join(repo_root, 'secvarctl', 'test', 'testdata', 'guest', 'authfiles')
                rc = self.connection.run_command(f"bash -c 'ls -d {candidate} 2>/dev/null | head -n1' || true")
                if rc and rc[0].strip():
                    auth_dir = rc[0].strip()

            if auth_dir:
                log.info(f"Found authfiles at {auth_dir}; running secvarctl write PK reset_PK_by_PK.auth")
                try:
                    cmd = f"bash -c 'cd {shlex.quote(auth_dir)} && secvarctl write PK reset_PK_by_PK.auth'"
                    out = self.connection.run_command(cmd)
                    for l in out:
                        log.info(l)
                except Exception as e:
                    self.fail(f"Failed to run secvarctl write on guest: {e}")
            else:
                log.warning("secvarctl authfiles directory not found")

            # After PK reset, zero the HMC secure-boot parameters
            self.ensure_hmc_available()
            # Shutdown LPAR and wait ~30s
            self.shutdown_lpar(host_name, system_name, sleep_time=30)
            # Configure secure-boot related params to zero
            config_params = (
                "keystore_signed_updates_without_verification=0,"
                "keystore_signed_updates=0,"
                "linux_dynamic_key_secure_boot=0,"
                "keystore_kbytes=0"
            )
            self.configure_secure_boot(host_name, system_name, config_params)
            # Allow HMC to settle
            time.sleep(10)
            # Get and log current status
            output = self.get_secure_boot_status(host_name, system_name)
            log.info("Current secure boot status after resetting to zero:")
            for line in output:
                log.info(line)
            # Start the LPAR
            self.start_lpar(host_name, system_name)

            # Cleanup via SecvarctlTest.tearDown()
            try:
                if repo_root:
                    sec.home = repo_root
                sec.tearDown()
            except Exception as e:
                log.warning(f"secvarctl tearDown reported an error: {e}")

            log.info("Secure boot reset completed and secvarctl artifacts cleaned up")
        except Exception as e:
            error_msg = f"Failed to reset secure boot settings: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def enable_secure_boot(self, host_name, system_name):
        """
        Enable secure boot (set to mode 2)
        """
        try:
            log.info(f"Enabling secure boot for host: {host_name}, system: {system_name}")
            self.shutdown_lpar(host_name, system_name)
            self.configure_secure_boot(host_name, system_name, "secure_boot=2")
            self.start_lpar(host_name, system_name)
            log.info("Secure boot enabled successfully")
            
        except Exception as e:
            error_msg = f"Failed to enable secure boot: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def disable_secure_boot(self, host_name, system_name):
        """
        Disable secure boot (set to mode 0)
        """
        try:
            log.info(f"Disabling secure boot for host: {host_name}, system: {system_name}")
            self.shutdown_lpar(host_name, system_name, sleep_time=30)
            self.configure_secure_boot(host_name, system_name, "secure_boot=0")
            time.sleep(5)
            self.start_lpar(host_name, system_name)
            log.info("Secure boot disabled successfully")
        except Exception as e:
            error_msg = f"Failed to disable secure boot: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def runTest(self):
        # Get host and system names from configuration
        host_name = self.conf.args.lpar_name
        system_name = self.conf.args.system_name
        # Check required kernel configurations are present
        self.check_kernel_config()
        # Check kernel and grub signatures
        self.kernel_grub_signature_check()
        # Setup dynamic secure boot
        self.setup_dynamic_secure_boot(host_name, system_name)
        # Enable secure boot
        self.enable_secure_boot(host_name, system_name)
        # Reset secure boot
        self.reset_secure_boot(host_name, system_name)
        # Disable secure boot
        self.disable_secure_boot(host_name, system_name)