#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
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
import unittest
import time
import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil
from common.Exceptions import CommandFailed
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class GrubTimeoutBase(object):
    '''
    This test case validates GRUB menu timeout parameter handling,
    with GrubTimeout1Second and GrubTimeout10Seconds classes configuring
    the GRUB menu timeout to different durations.
    '''
    def setup_test(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.cv_HOST = self.conf.host()
        self.console = self.cv_SYSTEM.console
        self.grub_config_file = "/etc/default/grub"
        self.grub_cfg_file = "/boot/grub2/grub.cfg"
        self.util = OpTestUtil(self.conf)
        self.distro = self.util.distro_name()
        log.info(f"Detected distribution: {self.distro}")

    def get_ssh_connection(self):
        '''Get SSH connection to the host'''
        return self.cv_HOST.get_ssh_connection()

    def backup_grub_config(self, connection):
        '''Backup the original GRUB configuration'''
        log.info("Backing up GRUB configuration...")
        connection.run_command(f"cp {self.grub_config_file} {self.grub_config_file}.backup")

    def restore_grub_config(self, connection):
        '''Restore the original GRUB configuration'''
        log.info("Restoring original GRUB configuration...")
        connection.run_command(f"cp {self.grub_config_file}.backup {self.grub_config_file}")
        connection.run_command("grub2-mkconfig -o /boot/grub2/grub.cfg")
        connection.run_command(f"rm -f {self.grub_config_file}.backup")

    def set_grub_timeout(self, connection, timeout_value):
        '''Set GRUB timeout value'''
        log.info(f"Setting GRUB_TIMEOUT to {timeout_value} seconds...")
        # Comment out GRUB_HIDDEN_TIMEOUT settings
        for setting in ['GRUB_HIDDEN_TIMEOUT', 'GRUB_HIDDEN_TIMEOUT_QUIET']:
            connection.run_command(
                f"sed -i 's/^{setting}=/#&/' {self.grub_config_file} 2>/dev/null || true"
            )
        # Set or update GRUB settings
        for param, value in [('GRUB_TIMEOUT_STYLE', 'menu'), ('GRUB_TIMEOUT', str(timeout_value))]:
            try:
                connection.run_command(f"grep -q '^{param}=' {self.grub_config_file}")
                connection.run_command(f"sed -i 's/^{param}=.*/{param}={value}/' {self.grub_config_file}")
            except CommandFailed:
                connection.run_command(f"echo '{param}={value}' >> {self.grub_config_file}")
        # Regenerate GRUB configuration and fix timeout=0
        connection.run_command("grub2-mkconfig -o /boot/grub2/grub.cfg")
        connection.run_command(
            f"sed -i 's/set timeout=0/set timeout={timeout_value}/g' {self.grub_cfg_file}"
        )
        # Clear caches and GRUB environment
        for cmd in [
            "rm -f /var/petitboot/*.cache 2>/dev/null || true",
            "rm -f /boot/grub2/*.cache 2>/dev/null || true",
            "grub2-editenv /boot/grub2/grubenv unset next_entry 2>/dev/null || true",
            "grub2-editenv /boot/grub2/grubenv unset saved_entry 2>/dev/null || true",
            "sync"
        ]:
            connection.run_command(cmd)
    
    def measure_grub_timeout(self):
        '''Measure GRUB timeout by rebooting and timing'''
        # Ensure we're in OS
        if self.cv_SYSTEM.get_state() != OpSystemState.OS:
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_SYSTEM.console
        start_time = time.time()
        # Reboot and wait for GRUB
        log.info("Rebooting system...")
        self.console.pty.sendline("reboot")
        time.sleep(5)
        # Wait for GRUB menu with multiple patterns for different distros
        log.info("Waiting for GRUB menu...")
        grub_patterns = [
            'GNU GRUB.*version',      # SLES pattern
            'Welcome to GRUB!',       # RHEL pattern
            'GRUB version',           # Generic pattern
            'Booting.*command list'   # Alternative pattern
        ]
        try:
            self.console.pty.expect(grub_patterns, timeout=60)
            grub_time = time.time() - start_time
            log.info(f"GRUB menu appeared at {grub_time:.2f}s")
        except:
            log.error("Failed to detect GRUB menu")
            return 0
        # Wait for kernel loading with multiple patterns
        log.info("Waiting for kernel to load...")
        kernel_patterns = [
            'Loading Linux',                    # SLES pattern
            'Loading initial ramdisk',          # SLES pattern
            'Booting.*Red Hat',                 # RHEL pattern (Booting `Red Hat...)
            'Booting.*SUSE',                    # SLES pattern (Booting `SUSE...)
            'Booting Linux via __start',        # RHEL/PowerPC pattern
            'Preparing to boot Linux',          # Alternative RHEL pattern
            'Booting the kernel',               # Generic pattern
            'Starting kernel',                  # Generic pattern
            r'\[.*\] Linux version'             # Kernel boot message
        ]
        try:
            self.console.pty.expect(kernel_patterns, timeout=self.timeout_value + 30)
            kernel_time = time.time() - start_time
            log.info(f"Kernel loading started at {kernel_time:.2f}s")
        except:
            log.error("Failed to detect kernel loading")
            return 0
        actual_timeout = kernel_time - grub_time
        log.info(f"Measured GRUB timeout: {actual_timeout:.2f}s")
        return actual_timeout
    
    def run_grub_timeout_test(self, test_case):
        '''Main test execution - to be called by subclasses'''
        log.info("=" * 60)
        log.info(f"GRUB Timeout Test: {self.timeout_value} seconds")
        log.info("=" * 60)
        connection = None
        try:
            # Setup: backup config and set timeout
            connection = self.get_ssh_connection()
            self.backup_grub_config(connection)
            self.set_grub_timeout(connection, self.timeout_value)
            connection = None  # Close before reboot
            # Execute: measure actual timeout
            actual_timeout = self.measure_grub_timeout()
            difference = abs(actual_timeout - self.timeout_value)
            # Report results
            log.info("=" * 60)
            log.info(f"Expected: {self.timeout_value}s | Actual: {actual_timeout:.2f}s | "
                    f"Difference: {difference:.2f}s | Tolerance: {self.tolerance}s")
            log.info("=" * 60)
            # Validate
            if difference > self.tolerance:
                test_case.fail(f"Timeout validation failed! Expected: {self.timeout_value}s, "
                              f"Actual: {actual_timeout:.2f}s, Difference: {difference:.2f}s")
            log.info("Test PASSED")
        finally:
            # Cleanup: restore original config
            if connection is None:
                time.sleep(30)
                try:
                    connection = self.get_ssh_connection()
                except:
                    log.warning("Could not reconnect to restore config")
            if connection:
                try:
                    self.restore_grub_config(connection)
                except Exception as e:
                    log.error(f"Failed to restore config: {e}")

class GrubTimeout1Second(GrubTimeoutBase, unittest.TestCase):
    '''Test GRUB timeout with 1 second'''
    
    def setUp(self):
        self.setup_test()
        self.timeout_value = 1
        self.tolerance = 3
    
    def runTest(self):
        '''Run 1-second timeout test'''
        self.run_grub_timeout_test(self)


class GrubTimeout10Seconds(GrubTimeoutBase, unittest.TestCase):
    '''Test GRUB timeout with 10 seconds'''
    
    def setUp(self):
        self.setup_test()
        self.timeout_value = 10
        self.tolerance = 5
    
    def runTest(self):
        '''Run 10-second timeout test'''
        self.run_grub_timeout_test(self)
