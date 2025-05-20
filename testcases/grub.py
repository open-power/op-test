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


import unittest
import time
import pexpect

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Grub(unittest.TestCase):
    '''
    Test case to measure system boot timing
    '''
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.cv_HOST = self.conf.host()
        self.console = self.cv_SYSTEM.console

    def measure_system_boot_time(self):
        '''
        Measure system boot time from reboot to grub menu
        and from grub menu to kernel loading.
        '''
        # Start timing
        start_time = time.time()
        log.info("Starting boot time measurement at: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            # Ensure we're in the OS
            if self.cv_SYSTEM.get_state() != OpSystemState.OS:
                log.info("Moving to OS state...")
                self.cv_SYSTEM.goto_state(OpSystemState.OS)
            # Get console connection
            self.console = self.cv_SYSTEM.console
            # Issue reboot command
            log.info("Issuing reboot command...")
            self.console.pty.sendline("reboot")
            # Wait for system to start rebooting
            log.info("Waiting for system to start rebooting...")
            time.sleep(5)  # Give system time to start rebooting
            # Wait for GRUB menu with more patterns
            log.info("Waiting for GRUB menu...")
            self.console.pty.expect([
                'GNU GRUB',
                'Press any key to enter the menu',
                'Welcome to GRUB',
                'Booting a command list',
                'Booting \'GNU/Linux\'',
                'Loading Linux',
                'Loading initial ramdisk',
                'Starting kernel',
                'Linux version'
            ], timeout=300)
            grub_time = time.time() - start_time
            log.info("GRUB menu detected at: %.2f seconds" % grub_time)
            # Wait for kernel loading with more patterns
            log.info("Waiting for kernel loading...")
            self.console.pty.expect([
                'Loading Linux',
                'Loading initial ramdisk',
                'Booting the kernel',
                'Starting kernel',
                'Linux version',
                'Command line: BOOT_IMAGE'
            ], timeout=300)
            kernel_time = time.time() - start_time
            log.info("Kernel loading detected at: %.2f seconds" % kernel_time)
            # Calculate time from GRUB to kernel
            grub_to_kernel = kernel_time - grub_time
            log.info("Time from GRUB menu to kernel loading: %.2f seconds" % grub_to_kernel)
        except Exception as e:
            log.error("Unexpected error during boot sequence: %s" % str(e))
        return {
            'reboot_to_grub': grub_time,
            'grub_to_kernel': grub_to_kernel,
            'total_boot_time': kernel_time
        }

    def runTest(self):
        '''
        Run the boot time measurement test
        '''
        log.info("Starting boot time measurement test")
        boot_times = self.measure_system_boot_time()
        log.info("Boot Time Results:")
        log.info("-----------------")
        log.info("Reboot to GRUB menu: %.2f seconds" % boot_times['reboot_to_grub'])
        log.info("GRUB menu to kernel loading: %.2f seconds" % boot_times['grub_to_kernel'])
        log.info("Total boot time: %.2f seconds" % boot_times['total_boot_time'])
        # Verify boot times are within reasonable limits
        if boot_times['reboot_to_grub'] > 300:
            self.fail("Time to GRUB menu exceeded 180 seconds")
        if boot_times['grub_to_kernel'] > 300:
            self.fail("Time from GRUB to kernel loading exceeded 180 seconds")
