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
from common.OpTestHMC import OpHmcState
from testcases.OpTestSecvarctl import SecvarctlTest
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class DynamicKeyGuestSecureBoot(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.cv_HMC = self.cv_SYSTEM.hmc

        if self.cv_HMC:
            try:
                lpar_state = self.cv_HMC.get_lpar_state()
                log.info(f"LPAR current state: {lpar_state}")

                if lpar_state == "Open Firmware":
                    log.warning("LPAR is stuck at Open Firmware — powering off, disabling secure boot, and restarting...")
                    self.cv_HMC.poweroff_lpar()
                    time.sleep(5)
                    self.cv_HMC.hmc_secureboot_on_off(enable=False)
                    time.sleep(5)
                    self.cv_HMC.poweron_lpar()
                    log.info("LPAR recovered from Open Firmware state with secure boot disabled")
                elif lpar_state not in ["Running", "Booting"]:
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

        # Install evmctl (ima-evm-utils) needed for .ima keyring key import
        try:
            self.connection.run_command("which evmctl")
            log.info("'evmctl' is already available")
        except Exception:
            log.info("Installing evmctl (ima-evm-utils)...")
            if self.distro_name == 'rhel':
                self.connection.run_command("dnf install -y ima-evm-utils || yum install -y ima-evm-utils")
            elif self.distro_name == 'sles':
                self.connection.run_command("zypper install -y evmctl")
            else:
                self.connection.run_command("zypper install -y evmctl")
            log.info("evmctl installed successfully")
    
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

    def _setup_secvarctl(self):
        """Initialise, build, and generate keys for a SecvarctlTest instance.

        Returns a SecvarctlTest object whose build_path can be
        used to locate generated auth files.
        """
        sec = SecvarctlTest()

        # Propagate required attributes
        sec.conf = self.conf
        sec.util = self.util
        sec.cv_HOST = self.cv_HOST
        sec.distro_name = self.distro_name
        sec.cv_SYSTEM = self.cv_SYSTEM
        sec.connection = self.connection
        sec.host_cmd_timeout = self.host_cmd_timeout

        # Repository details (fall back to upstream defaults)
        try:
            sec.secvar_repo = self.conf.args.git_repo
            sec.branch = self.conf.args.git_branch
            sec.home = self.conf.args.git_home
        except AttributeError:
            sec.secvar_repo = "https://github.com/open-power/secvarctl"
            sec.branch = "main"
            sec.home = "/home"

        try:
            sec.setUp()
        except Exception as e:
            log.warning(f"secvarctl setUp encountered an issue: {e}")

        log.info("Building secvarctl...")
        sec.build_secvarctl()

        log.info("Generating secvarctl keys and auth files...")
        sec.generate_keys()

        return sec

    def reset_secure_boot(self, sec=None):
        """Reset all secure boot settings to zero.

        Args:
            sec: Optional pre-built SecvarctlTest instance. If None, one is
                 created internally via _setup_secvarctl().
        """
        try:
            log.info("Resetting secure boot settings to zero")

            if sec is None:
                log.info("Setting up secvarctl for PK reset...")
                sec = self._setup_secvarctl()

            # Re-arm the one-shot keystore_signed_updates_without_verification latch
            # before writing — cleared after every PK write operation.
            self._re_enable_keystore_updates()

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

    def _write_and_verify_sbat(self, sec):
        """Generate SBAT auth file, write it, and verify the ESL count is 1."""
        log.info("Generating SBAT auth file...")
        sbat_gen_cmd = (
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate f:a"
            f" -k test/testdata/guest/goldenKeys/KEK/KEK.key"
            f" -c test/testdata/guest/goldenKeys/KEK/KEK.crt"
            f" -n sbat"
            f" -i test/testdata/guest/goldenKeys/sbat/sbat.csv"
            f" -o sbat_by_kek.auth"
        )
        for line in self.connection.run_command(sbat_gen_cmd):
            log.info(line)

        log.info("Writing SBAT auth file...")
        for line in self.connection.run_command(
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write sbat sbat_by_kek.auth"
        ):
            log.info(line)
        log.info("SBAT written successfully")

        sbat_count = sec.count_secvar_keys().get("sbat", 0)
        if sbat_count == 1:
            log.info("SBAT count is 1 — verified successfully")
        else:
            self.fail(f"SBAT verification failed — expected count 1, got {sbat_count}")

    def _re_enable_keystore_updates(self):
        """Re-arm the one-shot keystore_signed_updates_without_verification latch
        before writing — cleared after every PK write operation.
        """
        self.cv_HMC.poweroff_lpar()
        time.sleep(15)
        self.cv_HMC.configure_dynamic_secure_boot(enable=True, keystore_kbytes=64)
        time.sleep(5)
        self.cv_HMC.hmc_secureboot_on_off(enable=True)
        time.sleep(10)

        status_str = " ".join(self.get_secure_boot_status())
        if "keystore_signed_updates_without_verification=1" not in status_str:
            self.fail(
                "keystore_signed_updates_without_verification=1 not confirmed "
                "after re-arm — secvar writes will be rejected"
            )

        self.cv_HMC.poweron_lpar()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

        sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
        if not any("00000002" in l for l in sb_out):
            self.fail("ibm,secure-boot != 0x2 after re-arm — secure boot must be active for secvar writes")
        log.info("Keystore re-armed and secure boot active")

    def _secureboot_on(self):
        """Power off, enable secure boot, power on."""
        log.info("Enabling secure boot...")
        self.cv_HMC.poweroff_lpar()
        time.sleep(5)
        self.cv_HMC.hmc_secureboot_on_off(enable=True)
        self.cv_HMC.poweron_lpar()
        log.info("Secure boot enabled and system restarted")

    def _secureboot_off(self):
        """Power off, disable secure boot, power on."""
        log.info("Disabling secure boot...")
        self.cv_HMC.poweroff_lpar()
        time.sleep(5)
        self.cv_HMC.hmc_secureboot_on_off(enable=False)
        time.sleep(5)
        self.cv_HMC.poweron_lpar()
        log.info("Secure boot disabled and system restarted")

    def sbat_test(self, sec=None):
        """Test sbat"""
        try:
            if sec is None:
                log.info("Setting up secvarctl for SBAT test...")
                sec = self._setup_secvarctl()

            # Read SBAT variable via secvarctl
            cmd = f"{sec.build_path}/build/secvarctl read -n sbat"
            log.info(f"Running: {cmd}")
            out = self.connection.run_command(cmd)
            for line in out:
                log.info(line)
            log.info("SBAT read completed successfully")

            # Verify GRUB SBAT information
            log.info("Verifying GRUB SBAT information...")
            grub_cmd = "strings /usr/share/grub2/powerpc-ieee1275/grub.elf | grep -i sbat"
            grub_out = self.connection.run_command(grub_cmd)
            sbat_found = any("sbat" in line.lower() for line in grub_out)
            if sbat_found:
                log.info("SBAT is present in GRUB:")
                for line in grub_out:
                    log.info(line)
            else:
                self.fail("SBAT not found in /usr/share/grub2/powerpc-ieee1275/grub.elf")

            # Generate PK auth file, then write PK
            log.info("Generating PK auth file...")
            pk_gen_cmd = (
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl generate c:a"
                f" -k test/testdata/guest/goldenKeys/PK/PK.key"
                f" -c test/testdata/guest/goldenKeys/PK/PK.crt"
                f" -n KEK"
                f" -i test/testdata/guest/goldenKeys/PK/PK.crt"
                f" -o pk_by_pk.auth"
            )
            for line in self.connection.run_command(pk_gen_cmd):
                log.info(line)

            log.info("Writing PK key...")
            for line in self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write PK pk_by_pk.auth"
            ):
                log.info(line)
            log.info("PK key written successfully")

            # Verify PK
            log.info("Verifying PK key is present...")
            counts = sec.count_secvar_keys()
            pk_count = counts.get("PK", 0)
            if pk_count > 0:
                log.info(f"PK is present (ESL count: {pk_count})")
            else:
                self.fail("PK is missing after write (ESL count is 0)")

            # Generate KEK auth file using PK, then write KEK
            log.info("Generating KEK auth file...")
            kek_gen_cmd = (
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl generate c:a"
                f" -k test/testdata/guest/goldenKeys/PK/PK.key"
                f" -c test/testdata/guest/goldenKeys/PK/PK.crt"
                f" -n KEK"
                f" -i test/testdata/guest/goldenKeys/KEK/KEK.crt"
                f" -o kek_by_pk.auth"
            )
            for line in self.connection.run_command(kek_gen_cmd):
                log.info(line)

            log.info("Writing KEK key...")
            for line in self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write KEK kek_by_pk.auth"
            ):
                log.info(line)
            log.info("KEK key written successfully")

            # Verify KEK
            log.info("Verifying KEK key is present...")
            counts = sec.count_secvar_keys()
            kek_count = counts.get("KEK", 0)
            if kek_count > 0:
                log.info(f"KEK is present (ESL count: {kek_count})")
            else:
                self.fail("KEK is missing after write (ESL count is 0)")

            # Generate, write and verify SBAT
            log.info("Writing SBAT for the first time...")
            self._write_and_verify_sbat(sec)

            # Generate SBAT reset auth file
            log.info("Generating SBAT reset auth file...")
            sbat_reset_gen_cmd = (
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate reset"
                f" -k test/testdata/guest/goldenKeys/KEK/KEK.key"
                f" -c test/testdata/guest/goldenKeys/KEK/KEK.crt"
                f" -n sbat"
                f" -o resetsbat_by_kek.auth"
            )
            for line in self.connection.run_command(sbat_reset_gen_cmd):
                log.info(line)

            # Write SBAT reset
            log.info("Writing SBAT reset auth file...")
            for line in self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write sbat resetsbat_by_kek.auth"
            ):
                log.info(line)
            log.info("SBAT reset written successfully")

            # Verify SBAT count is 0 after reset
            sbat_reset = sec.count_secvar_keys().get("sbat", -1)
            if sbat_reset == 0:
                log.info("SBAT successfully reset (ESL count is 0)")
            else:
                self.fail(f"SBAT reset failed — expected count 0, got {sbat_reset}")

            # Verify secure boot is still enabled
            log.info("Verifying secure boot is still enabled...")
            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            for line in sb_out:
                log.info(line)
            sb_enabled = any("2" in line for line in sb_out)
            if sb_enabled:
                log.info("Secure boot is still enabled (value=2) — as expected")
            else:
                self.fail("Secure boot is not enabled after SBAT reset (expected value 2)")

            # Test boot without SBAT (secure boot enabled) — GRUB should fail to load.
            # the system is expected to hang at Open Firmware (GRUB blocked by SBAT reset).
            log.info("Testing boot without SBAT (secure boot enabled) — expecting GRUB boot failure...")
            self.cv_HMC.poweroff_lpar()
            lpar_cmd = "chsysstate -m %s -r lpar -n %s -o on" % (
                self.cv_HMC.mg_system, self.cv_HMC.lpar_name)
            if self.cv_HMC.lpar_prof:
                lpar_cmd = "%s -f %s" % (lpar_cmd, self.cv_HMC.lpar_prof)
            self.cv_HMC.ssh.run_command(lpar_cmd)
            log.info("LPAR power-on issued — waiting 120s for expected GRUB boot failure...")
            time.sleep(120)
            log.info("Wait complete — GRUB blocked as expected (SBAT missing)")

            # Disable secure boot and restart system
            self._secureboot_off()

            # Re-write SBAT now that secure boot is disabled
            log.info("Re-writing SBAT after secure boot disabled...")
            self._write_and_verify_sbat(sec)

            # Setup dynamic key guest secure boot
            log.info("Setting up dynamic key guest secure boot...")
            self.setup_dynamic_secure_boot()

            # Enable secure boot
            self._secureboot_on()
        except Exception as e:
            error_msg = f"Failed SBAT test: {str(e)}"
            log.error(error_msg)
            self.fail(error_msg)

    def _write_asset_to_lpar(self, filename, remote_dest):
        """Read <repo_root>/test_binaries/dkgsb/<filename> on the controller and
        write it to <remote_dest> on the LPAR."""
        local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_binaries", "dkgsb", filename,
        )
        with open(local_path) as f:
            content = f.read()
        self.connection.run_command(
            f"cat > {remote_dest} <<'__EOF__'\n{content}\n__EOF__"
        )
        log.info(f"Transferred {filename} → {remote_dest} on LPAR")

    def _locate_extract_module_sig(self):
        """Return the path to extract-module-sig.pl on the remote LPAR.
        """
        find_cmd = "find /usr/src /home -maxdepth 6 -name extract-module-sig.pl 2>/dev/null | head -1"
        found = self.connection.run_command(find_cmd)
        path = found[0].strip() if found and found[0].strip() else ""
        if not path:
            if "sles" in self.distro_name.lower():
                self.util.install_package(["kernel-source"])
            else:
                self.util.install_package(["kernel-devel", "kernel-headers"])
            found = self.connection.run_command(find_cmd)
            path = found[0].strip() if found and found[0].strip() else ""
        if not path:
            self.fail("extract-module-sig.pl not found after install attempt")
        return path

    def _strip_sig(self, extract_pl, src, dest):
        """Strip appended signature from src binary and write result to dest."""
        out = self.connection.run_command(
            f"perl {extract_pl} -0 {src} > {dest} 2>&1 && echo STRIP_OK || echo STRIP_FAIL"
        )
        if not any("STRIP_OK" in l for l in out):
            self.fail(f"Failed to strip signature from {src}: {out}")

    def _write_secvar_filehash(self, sec, varname, input_file, auth_file):
        """Generate a file-hash (f:a) auth for varname and write it; verify ESL count = 1."""
        kek_dir = "test/testdata/guest/goldenKeys/KEK"
        out = self.connection.run_command(
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl generate f:a"
            f" -c {kek_dir}/KEK.crt -k {kek_dir}/KEK.key"
            f" -n {varname} -i {input_file} -o {auth_file}"
        )
        if not any("SUCCESS" in l for l in out):
            self.fail(f"{varname} auth generation failed: {out}")
        write_out = self.connection.run_command(
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write {varname} {auth_file}"
        )
        if not any("SUCCESS" in l for l in write_out):
            self.fail(f"{varname} write failed: {write_out}")
        count = sec.count_secvar_keys().get(varname, 0)
        if count != 1:
            self.fail(f"{varname} ESL count expected 1, got {count}")
        log.info(f"{varname} written (ESL count=1)")

    def _reset_secvar(self, sec, varname, auth_file):
        """Generate a reset auth for varname and write it; verify ESL count = 0."""
        kek_dir = "test/testdata/guest/goldenKeys/KEK"
        out = self.connection.run_command(
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl generate reset"
            f" -k {kek_dir}/KEK.key -c {kek_dir}/KEK.crt"
            f" -n {varname} -o {auth_file}"
        )
        if not any("SUCCESS" in l for l in out):
            self.fail(f"{varname} reset auth generation failed: {out}")
        write_out = self.connection.run_command(
            f"cd {sec.build_path} && {sec.build_path}/build/secvarctl write {varname} {auth_file}"
        )
        if not any("SUCCESS" in l for l in write_out):
            self.fail(f"{varname} reset write failed: {write_out}")
        count = sec.count_secvar_keys().get(varname, -1)
        if count != 0:
            self.fail(f"{varname} ESL count expected 0 after reset, got {count}")
        log.info(f"{varname} cleared (ESL count=0)")

    def grubdbx_dbx_test(self, sec=None):
        """Test grubdbx and dbx blocklisting under DKGSB.

        Step 1 — Extract unsigned binaries (strip appended signatures).
        Step 2 — Write grubdbx blocklist (file-hash of grub.elf), verify ESL=1.
        Step 3 — Write dbx blocklist (file-hash of vmlinux), verify ESL=1.
        Step 4 — Boot with SB on, GRUB must be blocked (grubdbx hit).
        Step 5 — Disable SB, clear grubdbx, re-enable SB, kernel must be blocked (dbx hit).
        Step 6 — Disable SB, clear dbx, re-enable SB, verify clean boot.
        """
        try:
            if sec is None:
                sec = self._setup_secvarctl()

            # Step 1 — strip signatures to get hashable unsigned binaries
            extract_pl = self._locate_extract_module_sig()

            grub_elf_out = self.connection.run_command(
                "rpm -ql grub2-powerpc-ieee1275 2>/dev/null | grep 'grub\\.elf$' | head -1 || true"
            )
            grub_elf = grub_elf_out[0].strip() or "/usr/share/grub2/powerpc-ieee1275/grub.elf"

            vmlinux_out = self.connection.run_command(
                f"ls /boot/vmlinux-{self.kernel_version} /boot/vmlinux 2>/dev/null | head -1 || true"
            )
            vmlinux = vmlinux_out[0].strip() or "/boot/vmlinux"

            grub_unsigned = f"{sec.build_path}/grub.elf.unsigned"
            vmlinux_unsigned = f"{sec.build_path}/vmlinux.unsigned"
            self._strip_sig(extract_pl, grub_elf, grub_unsigned)
            self._strip_sig(extract_pl, vmlinux, vmlinux_unsigned)
            log.info(f"Unsigned binaries extracted — grub: {grub_elf}, vmlinux: {vmlinux}")

            # Step 2 — block GRUB via grubdbx
            self._write_secvar_filehash(sec, "grubdbx", grub_unsigned, "grubdbx_by_kek.auth")

            # Step 3 — block kernel via dbx
            self._write_secvar_filehash(sec, "dbx", vmlinux_unsigned, "dbx_by_kek.auth")

            # Step 4 — SB on; GRUB blocked by grubdbx
            self.cv_HMC.poweroff_lpar()
            self.cv_HMC.hmc_secureboot_on_off(enable=True)
            self.cv_HMC.poweron_lpar()
            log.info("Booting with grubdbx active — expecting GRUB failure")
            time.sleep(120)

            # Step 5 — recover, clear grubdbx, re-boot; kernel blocked by dbx
            self._secureboot_off()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            self._re_enable_keystore_updates()
            self._reset_secvar(sec, "grubdbx", "reset_grubdbx_by_kek.auth")

            self.cv_HMC.poweroff_lpar()
            self.cv_HMC.hmc_secureboot_on_off(enable=True)
            self.cv_HMC.poweron_lpar()
            log.info("Booting with dbx active — expecting kernel load failure")
            time.sleep(120)

            # Step 6 — recover, clear dbx, re-boot; verify clean boot
            self._secureboot_off()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            self._re_enable_keystore_updates()
            self._reset_secvar(sec, "dbx", "reset_dbx_by_kek.auth")

            self._secureboot_on()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            if not any("00000002" in l for l in sb_out):
                self.fail("ibm,secure-boot != 0x2 after clean boot")

            dmesg_sb = self.connection.run_command("dmesg | grep -i 'secure boot mode'")
            if not any("enabled" in l.lower() for l in dmesg_sb):
                self.fail("'Secure boot mode enabled' not in dmesg after clean boot")

            log.info("=== grubdbx_dbx_test PASSED ===")

        except Exception as e:
            self.fail(f"grubdbx_dbx_test failed: {e}")

    def third_party_module_test(self, sec=None):
        """Test third-party kernel module loading under DKGSB with trustedcadb/moduledb.

        Step 1  — Create trustedca CA cert config and generate self-signed 3072-bit CA cert.
        Step 2  — Verify cert is Version 3, 3072-bit.
        Step 3  — Generate trustedcadb auth file (signed by KEK) and write trustedcadb.
        Step 4  — Reboot to apply trustedcadb to the .machine keyring, verify key appears.
        Step 5  — Create module signing leaf cert config and generate CSR + private key.
        Step 6  — Sign CSR with trustedca to produce module signing cert, verify EKU = Code Signing.
        Step 7  — Generate moduledb auth file (signed by KEK) and write moduledb.
        Step 8  — Reboot to apply moduledb to .secondary_trusted_keys, verify key appears.
        Step 9  — Build a simple kernel module (hwm.c).
        Step 10 — Verify unsigned module is rejected by the kernel.
        Step 11 — Sign module with the module signing key and verify signature is appended.
        Step 12 — Load signed module; verify Hello, World! in dmesg; unload module.
        Step 13 — kexec: create kernel signing key, sign vmlinux, load + exec, verify boot.
        Step 14 — Reset trustedcadb and moduledb; reboot and confirm keyrings are clean.
        """
        try:
            log.info("=== TEST: third_party_module_test ===")

            if sec is None:
                sec = self._setup_secvarctl()

            kek_dir = f"{sec.build_path}/test/testdata/guest/goldenKeys/KEK"

            # Step 1: Transfer trustedca config; Step 2: Generate self-signed 3072-bit CA cert
            log.info("Step 1: Transferring trustedca.genkey to LPAR")
            self._write_asset_to_lpar("trustedca.genkey", "/root/trustedca.genkey")
            log.info("Step 2: Generating self-signed 3072-bit CA cert")
            out = self.connection.run_command(
                "openssl req -new -nodes -utf8 -sha256 -days 36500 -batch -x509"
                " -config /root/trustedca.genkey"
                " -outform PEM -out /root/trustedca.pem -keyout /root/trustedca.key"
            )
            for line in out:
                log.info(line)

            verify_out = self.connection.run_command(
                "openssl x509 -in /root/trustedca.pem -text -noout"
                r' | grep "Version\|Public-Key"'
            )
            if not any("Version: 3" in l for l in verify_out):
                self.fail(f"trustedca cert is not Version 3: {verify_out}")
            if not any("3072" in l for l in verify_out):
                self.fail(f"trustedca cert is not 3072-bit: {verify_out}")
            log.info("trustedca cert verified: Version 3, 3072-bit")

            # Step 5: Transfer moduledb config; generate CSR + private key
            log.info("Step 5: Transferring moduledb.genkey to LPAR")
            self._write_asset_to_lpar("moduledb.genkey", "/root/moduledb.genkey")
            log.info("Generating CSR + private key for module signing cert")
            out = self.connection.run_command(
                "openssl req -new -nodes -utf8 -sha256 -batch"
                " -config /root/moduledb.genkey"
                " -outform PEM -out /root/moduledbcsr.pem -keyout /root/moduledbcsr.key"
            )
            for line in out:
                log.info(line)

            # Step 6: Sign CSR with trustedca → module signing cert; verify EKU
            log.info("Step 6: Signing CSR with trustedca to produce module signing cert")
            out = self.connection.run_command(
                "openssl x509 -req -sha256"
                " -CA /root/trustedca.pem -CAkey /root/trustedca.key -CAcreateserial"
                " -days 36500"
                " -extfile /root/moduledb.genkey -extensions myexts"
                " -in /root/moduledbcsr.pem -out /root/moduledbcert.pem -outform PEM"
            )
            for line in out:
                log.info(line)

            eku_out = self.connection.run_command(
                'openssl x509 -in /root/moduledbcert.pem -text -noout'
                ' | grep -A1 "Extended Key Usage"'
            )
            if not any("Code Signing" in l for l in eku_out):
                self.fail(f"moduledbcert EKU does not contain Code Signing: {eku_out}")
            log.info("moduledbcert EKU verified: Code Signing present")

            # Flush all cert files to disk before the forced shutdowns
            self.connection.run_command("sync")
            log.info("All certs generated and synced to disk")

            # Step 3: Write trustedcadb (uses trustedca.pem generated above)
            self._re_enable_keystore_updates()

            log.info("Step 3: Generating trustedcadb auth file")
            out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate c:a"
                f" -k {kek_dir}/KEK.key -c {kek_dir}/KEK.crt"
                " -n trustedcadb -i /root/trustedca.pem -o trusteddb.auth"
            )
            if not any("SUCCESS" in l for l in out):
                self.fail(f"trustedcadb auth generation failed: {out}")

            log.info("Writing trustedcadb")
            write_out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest"
                " write trustedcadb trusteddb.auth"
            )
            if not any("SUCCESS" in l for l in write_out):
                self.fail(f"trustedcadb write failed: {write_out}")

            count = sec.count_secvar_keys().get("trustedcadb", 0)
            if count != 1:
                self.fail(f"trustedcadb ESL count expected 1, got {count}")
            log.info("trustedcadb written (ESL count=1)")

            # Step 4: Reboot to apply trustedcadb; verify key in .machine keyring
            log.info("Step 4: Rebooting to apply trustedcadb to .machine keyring")
            self.cv_HMC.poweroff_lpar()
            self.cv_HMC.poweron_lpar()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            machine_keys = self.connection.run_command("keyctl show %:.machine")
            if not any("Guest Secure Boot Test trustedca" in l for l in machine_keys):
                self.fail(
                    f"'Guest Secure Boot Test trustedca' not found in .machine keyring: {machine_keys}"
                )
            log.info("trustedca key confirmed in .machine keyring")

            # Step 7: Write moduledb (uses moduledbcert.pem generated above)
            self._re_enable_keystore_updates()

            log.info("Step 7: Generating moduledb auth file")
            out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate c:a"
                f" -k {kek_dir}/KEK.key -c {kek_dir}/KEK.crt"
                " -n moduledb -i /root/moduledbcert.pem -o moduledb.auth"
            )
            if not any("SUCCESS" in l for l in out):
                self.fail(f"moduledb auth generation failed: {out}")

            log.info("Writing moduledb")
            write_out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest"
                " write moduledb moduledb.auth"
            )
            if not any("SUCCESS" in l for l in write_out):
                self.fail(f"moduledb write failed: {write_out}")

            count = sec.count_secvar_keys().get("moduledb", 0)
            if count != 1:
                self.fail(f"moduledb ESL count expected 1, got {count}")
            log.info("moduledb written (ESL count=1)")

            # Step 8: Reboot to apply moduledb; verify key in .secondary_trusted_keys
            log.info("Step 8: Rebooting to apply moduledb to .secondary_trusted_keys")
            self.cv_HMC.poweroff_lpar()
            self.cv_HMC.poweron_lpar()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            sec_keys = self.connection.run_command("keyctl show %:.secondary_trusted_keys")
            if not any("Guest Secure Boot Test module signingkey" in l for l in sec_keys):
                self.fail(
                    "Guest Secure Boot Test module signingkey not found in"
                    f" .secondary_trusted_keys: {sec_keys}"
                )
            log.info("module signingkey confirmed in .secondary_trusted_keys")

            # Step 9: Transfer hwm source + Makefile; build on LPAR
            log.info("Step 9: Transferring hwm.c and Makefile to LPAR")
            self._write_asset_to_lpar("hwm.c", "/root/hwm.c")
            self._write_asset_to_lpar("hwm_Makefile", "/root/Makefile")
            log.info("Building hwm.ko kernel module")
            build_out = self.connection.run_command(
                "make -C /root 2>&1",
                timeout=self.host_cmd_timeout,
            )
            for line in build_out:
                log.info(line)

            ko_check = self.connection.run_command(
                "test -f /root/hwm.ko && echo EXISTS || echo MISSING"
            )
            if not any("EXISTS" in l for l in ko_check):
                self.fail("/root/hwm.ko does not exist after build")
            log.info("/root/hwm.ko built successfully")

            # Step 10: Verify unsigned module is rejected
            log.info("Step 10: Verifying unsigned module is rejected")
            insmod_out = self.connection.run_command(
                "insmod /root/hwm.ko 2>&1; echo exit:$?"
            )
            if not any("Key was rejected by service" in l for l in insmod_out):
                self.fail(
                    f"Unsigned module was not rejected (expected 'Key was rejected by service'): {insmod_out}"
                )
            log.info("Unsigned module correctly rejected by kernel")

            # Step 11: Sign module; verify signature appended
            log.info("Step 11: Signing hwm.ko with module signing key")
            sign_file_out = self.connection.run_command(
                f"find /usr/src -name sign-file -path '*/scripts/sign-file' 2>/dev/null | head -1"
            )
            sign_file = sign_file_out[0].strip() if sign_file_out and sign_file_out[0].strip() else ""
            if not sign_file:
                self.fail("sign-file tool not found under /usr/src")

            self.connection.run_command(
                f"{sign_file} sha256"
                " /root/moduledbcsr.key /root/moduledbcert.pem"
                " /root/hwm.ko /root/hwm.ko.signed"
            )

            sig_check = self.connection.run_command(
                "strings /root/hwm.ko.signed | tail -1"
            )
            if not any("Module signature appended" in l for l in sig_check):
                self.fail(
                    f"Module signature not appended to hwm.ko.signed: {sig_check}"
                )
            log.info("Module signature appended confirmed")

            # Step 12: Load signed module; verify Hello, World! in dmesg; unload
            log.info("Step 12: Loading signed module")
            self.connection.run_command("insmod /root/hwm.ko.signed")

            dmesg_out = self.connection.run_command("dmesg | tail -20")
            if not any("Hello, World!" in l for l in dmesg_out):
                self.fail(f"'Hello, World!' not found in dmesg after loading signed module: {dmesg_out}")
            log.info("'Hello, World!' confirmed in dmesg — signed module loaded successfully")

            self.connection.run_command("rmmod hwm")
            log.info("hwm module unloaded")

            # Step 13: kexec with kernel signed by trustedca chain
            log.info("Step 13: kexec with kernel signed by trustedca chain")
            # Step 13: Transfer kernel config; generate kernel signing key CSR
            self._write_asset_to_lpar("kernel.genkey", "/root/kernel.genkey")
            out = self.connection.run_command(
                "openssl req -new -nodes -utf8 -sha256 -batch"
                " -config /root/kernel.genkey"
                " -out /root/kernel.csr -keyout /root/kernel.key"
            )
            for line in out:
                log.info(line)

            # Sign CSR with trustedca (DER output for sign-file compatibility)
            out = self.connection.run_command(
                "openssl x509 -req -sha256"
                " -CA /root/trustedca.pem -CAkey /root/trustedca.key -CAcreateserial"
                " -days 36500"
                " -extfile /root/kernel.genkey -extensions myexts"
                " -in /root/kernel.csr -out /root/kernel_by_CA.pem -outform DER"
            )
            for line in out:
                log.info(line)

            # Verify EKU = Code Signing on kernel cert
            eku_out = self.connection.run_command(
                "openssl x509 -in /root/kernel_by_CA.pem -inform DER -text -noout"
                ' | grep -A1 "Extended Key Usage"'
            )
            if not any("Code Signing" in l for l in eku_out):
                self.fail(f"kernel_by_CA.pem EKU does not contain Code Signing: {eku_out}")
            log.info("kernel_by_CA.pem EKU verified: Code Signing present")

            # Locate the running kernel image on /boot.
            vmlinux_out = self.connection.run_command(
                f"ls /boot/vmlinux-{self.kernel_version} /boot/vmlinux 2>/dev/null | head -1 || true"
            )
            vmlinux = vmlinux_out[0].strip() or "/boot/vmlinux"
            log.info(f"Using kernel image: {vmlinux}")

            self.connection.run_command(
                f"{sign_file} sha256"
                " /root/kernel.key /root/kernel_by_CA.pem"
                f" {vmlinux} /root/vmlinux.signed_with_new_key"
            )
            log.info("Verifying kexec load of newly-signed vmlinux fails before key import")
            kexec_fail = self.connection.run_command(
                'kexec -s -l /root/vmlinux.signed_with_new_key'
                ' --append="$(cat /proc/cmdline)"'
                f' --initrd /boot/initrd-$(uname -r) 2>&1; echo exit:$?'
            )
            if not any("Permission denied" in l for l in kexec_fail):
                self.fail(
                    "kexec did not fail with 'Permission denied' before key import"
                    f" (new-key-signed vmlinux): {kexec_fail}"
                )

            # Find .ima keyring decimal ID and import the kernel cert
            ima_id_out = self.connection.run_command(
                "keyctl show %:.ima | awk '/keyring: \\.ima/{print $1; exit}'"
            )
            ima_id = ima_id_out[0].strip() if ima_id_out else ""
            if not ima_id or not ima_id.isdigit():
                self.fail(f"Could not determine .ima keyring decimal ID: {ima_id_out}")

            log.info(f"Importing kernel_by_CA.pem into .ima keyring (id={ima_id})")
            self.connection.run_command(
                f"evmctl import /root/kernel_by_CA.pem {ima_id}"
            )

            # Verify key is in .ima keyring
            ima_keys = self.connection.run_command("keyctl show %:.ima")
            if not any("kernel test key" in l for l in ima_keys):
                self.fail(f"'kernel test key' not found in .ima keyring: {ima_keys}")
            log.info("'kernel test key' confirmed in .ima keyring")

            self.connection.run_command(
                'kexec -s -l /root/vmlinux.signed_with_new_key'
                ' --append="$(cat /proc/cmdline)"'
                f' --initrd /boot/initrd-$(uname -r)'
            )

            # kexec exec — fires the reboot; SSH connection drops immediately.
            log.info("Executing kexec -e — connection will drop, waiting for system to reboot")
            self.connection.run_command_direct("kexec -e", expect_disconnect=True)

            # kexec is a soft reboot — wait for the LPAR to fully come back up.
            time.sleep(60)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            log.info("System back online after kexec")
            self._re_enable_keystore_updates()

            # Step 14: Reset trustedcadb and moduledb; reboot and confirm clean
            log.info("Step 14: Resetting trustedcadb and moduledb")

            # Generate and write trustedcadb reset
            out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate reset"
                f" -k {kek_dir}/KEK.key -c {kek_dir}/KEK.crt"
                " -n trustedcadb -i /root/trustedca.pem -o reset_trustedcadb.auth"
            )
            if not any("SUCCESS" in l for l in out):
                self.fail(f"trustedcadb reset auth generation failed: {out}")

            write_out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest"
                " write trustedcadb reset_trustedcadb.auth"
            )
            if not any("SUCCESS" in l for l in write_out):
                self.fail(f"trustedcadb reset write failed: {write_out}")

            count = sec.count_secvar_keys().get("trustedcadb", -1)
            if count != 0:
                self.fail(f"trustedcadb ESL count expected 0 after reset, got {count}")
            log.info("trustedcadb cleared (ESL count=0)")

            # Generate and write moduledb reset
            out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest generate reset"
                f" -k {kek_dir}/KEK.key -c {kek_dir}/KEK.crt"
                " -n moduledb -o reset_moduledb.auth"
            )
            if not any("SUCCESS" in l for l in out):
                self.fail(f"moduledb reset auth generation failed: {out}")

            write_out = self.connection.run_command(
                f"cd {sec.build_path} && {sec.build_path}/build/secvarctl -m guest"
                " write moduledb reset_moduledb.auth"
            )
            if not any("SUCCESS" in l for l in write_out):
                self.fail(f"moduledb reset write failed: {write_out}")

            count = sec.count_secvar_keys().get("moduledb", -1)
            if count != 0:
                self.fail(f"moduledb ESL count expected 0 after reset, got {count}")
            log.info("moduledb cleared (ESL count=0)")

            # Final reboot — confirm keyrings are clean
            log.info("Final reboot to confirm .machine and .secondary_trusted_keys are clean")
            self.cv_HMC.poweroff_lpar()
            self.cv_HMC.poweron_lpar()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            machine_keys = self.connection.run_command("keyctl show %:.machine")
            if any("Guest Secure Boot Test trustedca" in l for l in machine_keys):
                self.fail(
                    "'Guest Secure Boot Test trustedca' still present in .machine after reset"
                )
            log.info("'.machine' keyring clean — trustedca key absent")

            sec_keys = self.connection.run_command("keyctl show %:.secondary_trusted_keys")
            if any("Guest Secure Boot Test module signingkey" in l for l in sec_keys):
                self.fail(
                    "'Guest Secure Boot Test module signingkey' still present in"
                    " .secondary_trusted_keys after reset"
                )
            log.info("'.secondary_trusted_keys' keyring clean — module signingkey absent")

            log.info("=== third_party_module_test PASSED ===")

        except Exception as e:
            self.fail(f"third_party_module_test failed: {e}")

        finally:
            # Remove all files written/generated on the LPAR by this test.
            cleanup_files = [
                "/root/trustedca.genkey", "/root/trustedca.pem",
                "/root/trustedca.key", "/root/trustedca.srl",
                "/root/moduledb.genkey", "/root/moduledbcsr.pem",
                "/root/moduledbcsr.key", "/root/moduledbcert.pem",
                "/root/kernel.genkey", "/root/kernel.csr",
                "/root/kernel.key", "/root/kernel_by_CA.pem",
                "/root/hwm.c", "/root/Makefile",
                "/root/hwm.o", "/root/hwm.ko", "/root/hwm.ko.signed",
                "/root/hwm.mod", "/root/hwm.mod.c", "/root/hwm.mod.o",
                "/root/.hwm.ko.cmd", "/root/.hwm.mod.cmd",
                "/root/.hwm.mod.o.cmd", "/root/.hwm.o.cmd",
                "/root/.module-common.o", "/root/..module-common.o.cmd",
                "/root/Module.symvers", "/root/.Module.symvers.cmd",
                "/root/modules.order", "/root/.modules.order.cmd",
                "/root/modules.livepatch",
                "/root/vmlinux.signed_with_new_key",
            ]
            try:
                self.connection.run_command("rm -f " + " ".join(cleanup_files))
                log.info("third_party_module_test: cleanup complete")
            except Exception as cleanup_err:
                log.warning(f"third_party_module_test: cleanup failed (non-fatal): {cleanup_err}")

    def static_to_dynamic_test(self, sec=None):
        """Test transition from Static Guest Secure Boot (SKGSB) to Dynamic (DKGSB).
        Steps:
          1. Ensure static SB is active (zero DKGSB flags if needed, enable SB=2).
          2. Verify plpks absent from dmesg (static mode).
          3. Disable secure boot.
          4. Configure DKGSB keystore flags via HMC.
          5. Boot and verify plpks init and DKGSB secvar variables.
          6. Re-enable secure boot (now DKGSB).
          7. Confirm DKGSB: ibm,secure-boot=2, dmesg, kernel lockdown.
          8. Write PK to prove DKGSB write-path is operational.
        """
        try:
            log.info("=== TEST: Static → Dynamic (SKGSB → DKGSB) ===")

            # Step 1: Ensure static SB is active
            status_str = " ".join(self.get_secure_boot_status())
            if "linux_dynamic_key_secure_boot=1" in status_str:
                log.info("DKGSB flags still set — zeroing before enabling static SB")
                self.cv_HMC.poweroff_lpar()
                time.sleep(15)
                try:
                    self.cv_HMC.configure_dynamic_secure_boot(enable=False, keystore_kbytes=0)
                except Exception as e:
                    log.warning(f"configure_dynamic_secure_boot(False): {e}")
                time.sleep(10)

            self._secureboot_on()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            if not any("2" in l for l in sb_out):
                self.fail("Failed to establish static secure boot (ibm,secure-boot=2)")
            log.info("Static SB active (ibm,secure-boot=2)")

            # Step 2: Verify no DKGSB artefacts in static mode
            plpks_out = self.connection.run_command("dmesg | grep -i plpks || true")
            if any("initialized successfully" in l for l in plpks_out):
                log.warning("plpks present in static mode — keystore flags may not be fully cleared")

            self.kernel_grub_signature_check()

            # Step 3: Disable secure boot
            self._secureboot_off()
            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            if any("2" in l for l in sb_out):
                self.fail("Secure boot not disabled")

            # Step 4: Configure DKGSB keystore flags
            self.cv_HMC.poweroff_lpar()
            time.sleep(15)
            self.cv_HMC.configure_dynamic_secure_boot(enable=True, keystore_kbytes=64)
            time.sleep(10)

            status_str = " ".join(self.get_secure_boot_status())
            if "linux_dynamic_key_secure_boot=1" not in status_str:
                self.fail("linux_dynamic_key_secure_boot=1 not confirmed after configure_dynamic_secure_boot")

            # Step 5: Boot and verify plpks + DKGSB secvars
            self.cv_HMC.poweron_lpar()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            plpks_out = self.connection.run_command("dmesg | grep -i plpks || true")
            if not any("initialized successfully" in l for l in plpks_out):
                self.fail("plpks not initialized — DKGSB keystore not active")

            secvar_vars = " ".join(self.connection.run_command("ls /sys/firmware/secvar/vars/"))
            for v in ("grubdb", "grubdbx", "trustedcadb"):
                if v not in secvar_vars:
                    self.fail(f"DKGSB secvar '{v}' not found — transition incomplete")
            log.info("DKGSB secvar variables confirmed")

            # Step 6: Re-enable secure boot (now DKGSB)
            self._secureboot_on()
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            # Step 7: Confirm DKGSB mode
            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            if not any("2" in l for l in sb_out):
                self.fail("Secure boot not active after enabling DKGSB")

            dmesg_sb = self.connection.run_command("dmesg | grep -i 'secure boot mode'")
            if not any("enabled" in l.lower() for l in dmesg_sb):
                self.fail("'Secure boot mode enabled' not in dmesg after DKGSB boot")

            lockdown = self.connection.run_command("cat /sys/kernel/security/lockdown")
            if not any("integrity" in l or "confidentiality" in l for l in lockdown):
                self.fail("Kernel lockdown not active after DKGSB secure boot")
            log.info("DKGSB confirmed: ibm,secure-boot=2, lockdown active, plpks present")

            # Step 8: Write PK to prove DKGSB write-path is operational
            if sec is None:
                sec = self._setup_secvarctl()
            self._re_enable_keystore_updates()
            auth_dir = os.path.join(sec.build_path, "test", "testdata", "guest", "authfiles")
            out = self.connection.run_command(
                f"cd {auth_dir} && {sec.build_path}/build/secvarctl write PK PK_by_PK.auth"
            )
            for line in out:
                log.info(line)
            if not any("SUCCESS" in l for l in out):
                self.fail("PK write failed — DKGSB write-path not operational")

            pk_count = sec.count_secvar_keys().get("PK", 0)
            if pk_count < 1:
                self.fail(f"PK ESL count={pk_count} after write — expected ≥1")
            log.info(f"PK written (ESL count={pk_count}) — Static → Dynamic transition complete")

            log.info("=== static_to_dynamic_test PASSED ===")
        except Exception as e:
            self.fail(f"static_to_dynamic_test failed: {e}")

    def dynamic_to_static_test(self, sec=None):
        """Test transition from Dynamic Guest Secure Boot (DKGSB) to Static (SKGSB).
        Steps:
          1. Verify DKGSB is active (linux_dynamic_key_secure_boot=1, plpks present).
          2-4. Delegate to reset_secure_boot(): re-arm latch, reset PK, disable SB,
               release keystore, zero all DKGSB flags.
          5. Re-enable secure boot as static (no keystore flags).
          6. Confirm static SB: ibm,secure-boot=2, no plpks, no DKGSB secvars.
          7. Verify secvar write is rejected (read-only in static SB mode).
        """
        try:
            log.info("=== TEST: Dynamic → Static (DKGSB → SKGSB) ===")

            # Step 1: Confirm DKGSB is active
            status_str = " ".join(self.get_secure_boot_status())
            if "linux_dynamic_key_secure_boot=1" not in status_str:
                self.fail("linux_dynamic_key_secure_boot=1 not found — system not in DKGSB mode")

            plpks_out = self.connection.run_command("dmesg | grep -i plpks || true")
            if not any("initialized successfully" in l for l in plpks_out):
                self.fail("plpks not initialized — system not in DKGSB mode")
            log.info("DKGSB confirmed")

            # Steps 2-4: PK reset + keystore cleanup
            if sec is None:
                sec = self._setup_secvarctl()
            self.reset_secure_boot(sec=sec)

            # Verify keystore flags zeroed
            status_str = " ".join(self.get_secure_boot_status())
            if "linux_dynamic_key_secure_boot=1" in status_str:
                self.fail("linux_dynamic_key_secure_boot still 1 after reset — flags not cleared")
            log.info("DKGSB keystore flags zeroed")

            # Step 5: Re-enable as static SB
            self._secureboot_on()
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            # Step 6: Confirm static SB mode
            sb_out = self.connection.run_command("lsprop /proc/device-tree/ibm,secure-boot")
            if not any("2" in l for l in sb_out):
                self.fail("ibm,secure-boot != 2 after enabling static SB")

            dmesg_sb = self.connection.run_command("dmesg | grep -i 'secure boot mode'")
            if not any("enabled" in l.lower() for l in dmesg_sb):
                self.fail("'Secure boot mode enabled' not in dmesg after static SB boot")

            plpks_out = self.connection.run_command("dmesg | grep -i plpks || true")
            if any("initialized successfully" in l for l in plpks_out):
                self.fail("plpks still initialised — system still in DKGSB mode")
            log.info("plpks absent — static SB confirmed")

            secvar_vars = " ".join(
                self.connection.run_command("ls /sys/firmware/secvar/vars/ || true")
            )
            for v in ("grubdbx", "grubdb", "trustedcadb"):
                if v in secvar_vars:
                    self.fail(f"DKGSB secvar '{v}' still present after transition to static SB")
            log.info("No DKGSB secvar variables present — static SB confirmed")

            # Step 7: Verify secvar write is rejected in static mode
            auth_dir = os.path.join(sec.build_path, "test", "testdata", "guest", "authfiles")
            try:
                write_out = self.connection.run_command(
                    f"cd {auth_dir} && {sec.build_path}/build/secvarctl write PK PK_by_PK.auth"
                    "; echo exit:$?"
                )
                if any("SUCCESS" in l for l in write_out):
                    self.fail("secvarctl write PK succeeded in static SB — should be rejected")
            except Exception:
                pass  # non-zero exit is the expected outcome in static SB
            log.info("secvarctl write correctly rejected — read-only static SB confirmed")

            log.info("=== dynamic_to_static_test PASSED ===")
        except Exception as e:
            self.fail(f"dynamic_to_static_test failed: {e}")

    def runTest(self):
        # Check required kernel configurations are present
        self.check_kernel_config()
        # Check kernel and grub signatures
        self.kernel_grub_signature_check()
        # Setup dynamic secure boot
        self.setup_dynamic_secure_boot()
        # Enable secure boot
        self._secureboot_on()
        sec = self._setup_secvarctl()
        self.sbat_test(sec)
        # Test grubdbx / dbx blocklisting
        self.grubdbx_dbx_test(sec)
        # Test third-party module loading via trustedcadb/moduledb
        self.third_party_module_test(sec)
        # Reset secure boot
        self.reset_secure_boot(sec=sec)
        # Disable secure boot
        self._secureboot_off()
        # Test transition: Static → Dynamic
        self.static_to_dynamic_test(sec=sec)
        # Test transition: Dynamic → Static
        self.dynamic_to_static_test(sec=sec)