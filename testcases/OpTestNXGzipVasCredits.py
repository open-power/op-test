#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestNXGzipVasCredits.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
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
# Author: Pavithra Prakash <pavrampu@linux.ibm.com>

'''
NX GZIP VAS Credits Test with CPU DLPAR and workload
----------------------------------------------------------------------

This test validates that NX GZIP VAS credits are properly updated when
CPUs are added or removed dynamically via HMC DLPAR operations in BOTH
dedicated and shared processor modes.

Test Flow:
1. Save current LPAR profile
2. Boot LPAR in dedicated mode and test (add/remove 1,2,4 processors)
3. Boot LPAR in shared mode and test (add/remove 0.1,0.2,0.4 processing units)
4. Restore original LPAR profile

Formula:
- Dedicated mode: credits = num_procs × 20
- Shared mode: credits = entitled_capacity (ent) × 20

Prerequisites:
- Required packages: git, gcc, make, zlib-devel
- HMC access with RMC connection
'''

import time
import subprocess
import re
import sys
import os

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestIPMI import IPMIConsoleState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestNXGzipVasCredits(unittest.TestCase):
    '''
    Comprehensive test for NX GZIP VAS credits in both processor modes.
    This test saves the current profile, tests in dedicated mode, tests in
    shared mode, and restores the original profile.
    '''

    VAS_CREDITS_PATH = "/sys/devices/virtual/misc/vas/vas0/gzip/default_capabilities/nr_total_credits"
    CREDITS_PER_UNIT = 20
    POWER_GZIP_URL = "https://github.com/libnxz/power-gzip"
    POWER_GZIP_BRANCH = "master"
    DEDICATED_MODE_PROCS = [1, 2, 4]
    SHARED_MODE_PROCUNITS = [0.1, 0.2, 0.4]

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.test_dir = None
        self.test_file = None
        self.workload_started = False
        self.host = conf.host()
        self.system = conf.system()
        self.util = OpTestUtil()
        self.test = "host"
        self.test_dir = None
        self.test_file = None
        self.original_profile = None
        self.proc_mode = None
        self.hmc = conf.hmc()
        self.lpar_name = conf.args.lpar_name
        self.system_name = conf.args.system_name
        dedicated_procs_arg = getattr(conf.args, 'nx_gzip_dedicated_procs', 4)
        shared_units_arg = getattr(conf.args, 'nx_gzip_shared_units', 2.5)
        self.dedicated_num_procs = int(dedicated_procs_arg) if dedicated_procs_arg else 4
        self.shared_proc_units = float(shared_units_arg) if shared_units_arg else 2.5
        if not self.hmc or not self.lpar_name or not self.system_name:
            raise Exception("HMC configuration required: hmc, lpar_name, and system_name must be configured")
        log.info("Configuration: dedicated_procs=%d, shared_units=%.1f" %
                 (self.dedicated_num_procs, self.shared_proc_units))

    def set_up(self):
        '''Get console connection'''
        self.system.goto_state(OpSystemState.OS)
        self.c = self.system.cv_HOST.get_ssh_connection()
        return self.c

    def save_lpar_profile(self):
        '''Save current LPAR configuration profile using HMC backup'''
        try:
            log.info("=" * 70)
            log.info("STEP 1: Saving current LPAR profile")
            log.info("=" * 70)
            self.hmc.profile_bckup()
            log.info("Profile backup created: %s_bck" % self.hmc.lpar_prof)
            curr_mode = self.hmc.get_proc_mode()
            log.info("Current processor mode: %s" % (curr_mode[0] if curr_mode else "unknown"))
            return True
        except Exception as e:
            log.error("Failed to save LPAR profile: %s" % str(e))
            return False

    def restore_lpar_profile(self):
        '''Restore original LPAR configuration profile from backup'''
        try:
            log.info("=" * 70)
            log.info("STEP 4: Restoring original LPAR profile")
            log.info("=" * 70)
            log.info("Shutting down LPAR...")
            self.c.run_command("shutdown -h now", timeout=10)
            time.sleep(30)
            log.info("Switching to backup profile: %s_bck" % self.hmc.lpar_prof)
            original_prof = self.hmc.lpar_prof
            self.hmc.lpar_prof = original_prof + "_bck"
            log.info("Booting LPAR with original profile...")
            self.hmc.poweron_lpar()
            log.info("Booting LPAR with restored profile...")
            boot_cmd = "chsysstate -r lpar -m %s -o on -n %s" % (self.system_name, self.lpar_name)
            self.hmc.run_command(boot_cmd, timeout=60)
            time.sleep(60)
            max_retries = 10
            for i in range(max_retries):
                try:
                    self.c.run_command("uname -a", timeout=30)
                    log.info("System restored and responsive")
                    break
                except:
                    if i < max_retries - 1:
                        log.info("Waiting for system... (attempt %d/%d)" % (i+1, max_retries))
                        time.sleep(30)
                    else:
                        raise Exception("System did not become responsive after restoration")
            log.info("Original LPAR profile restored successfully")
            return True
        except Exception as e:
            log.error("Failed to restore LPAR profile: %s" % str(e))
            return False

    def change_to_dedicated_mode(self, num_procs=4):
        '''Change LPAR to dedicated mode with specified processors'''
        try:
            log.info("=" * 70)
            log.info("STEP 2: Changing to DEDICATED mode with %d processors" % num_procs)
            log.info("=" * 70)
            log.info("Shutting down LPAR...")
            self.c.run_command("shutdown -h now", timeout=10)
            time.sleep(30)
            log.info("Configuring dedicated mode using HMC change_proc_mode...")
            self.hmc.change_proc_mode(
                proc_mode='ded',
                sharing_mode='share_idle_procs',
                min_proc_units=str(num_procs),
                desired_proc_units=str(num_procs),
                max_proc_units=str(num_procs + 7),
                min_memory="4096",
                desired_memory="40960",
                max_memory="81920"
            )
            log.info("Booting LPAR with modified profile...")
            self.hmc.poweron_lpar()
            time.sleep(60)
            max_retries = 10
            for i in range(max_retries):
                try:
                    self.c.run_command("uname -a", timeout=30)
                    log.info("System is up in dedicated mode")
                    break
                except:
                    if i < max_retries - 1:
                        log.info("Waiting for system... (attempt %d/%d)" % (i+1, max_retries))
                        time.sleep(30)
                    else:
                        raise Exception("System did not boot in dedicated mode")
            output = self.c.run_command("grep 'shared_processor_mode' /proc/ppc64/lparcfg")
            for line in output:
                if 'shared_processor_mode=0' in line:
                    log.info("Confirmed: System is in DEDICATED mode")
                    self.proc_mode = 'dedicated'
                    return True
            raise Exception("Failed to verify dedicated mode")
        except Exception as e:
            log.error("Failed to change to dedicated mode: %s" % str(e))
            return False

    def change_to_shared_mode(self, desired_proc_units=2.5):
        '''Change LPAR to shared mode with specified processing units'''
        try:
            log.info("=" * 70)
            log.info("STEP 3: Changing to SHARED mode with %.1f processing units" % desired_proc_units)
            log.info("=" * 70)
            log.info("Shutting down LPAR...")
            self.c.run_command("shutdown -h now", timeout=10)
            time.sleep(30)
            min_units = 0.5
            max_units = int(desired_proc_units + 2.5)
            overcommit_ratio = 3
            max_vprocs = overcommit_ratio * max_units
            min_vprocs = overcommit_ratio * 1
            desired_vprocs = overcommit_ratio * int(desired_proc_units + 0.5)
            log.info("Configuring shared mode using direct HMC command...")
            log.info("  min_proc_units: %.1f, desired: %.1f, max: %d" % (min_units, desired_proc_units, max_units))
            log.info("  min_procs: %d, desired: %d, max: %d" % (min_vprocs, desired_vprocs, max_vprocs))
            profile_name = self.hmc.lpar_prof
            cmd = ("chsyscfg -r prof -m %s --force -i 'name=%s,lpar_name=%s,"
                   "proc_mode=shared,sharing_mode=uncap,"
                   "min_proc_units=%.1f,desired_proc_units=%.1f,max_proc_units=%d,"
                   "min_procs=%d,desired_procs=%d,max_procs=%d,"
                   "min_mem=4096,desired_mem=40960,max_mem=81920'" %
                   (self.hmc.mg_system, profile_name, self.hmc.lpar_name,
                    min_units, desired_proc_units, max_units,
                    min_vprocs, desired_vprocs, max_vprocs))
            log.info("Executing: %s" % cmd)
            result = self.hmc.run_command(cmd)
            log.info("Profile modification result: %s" % str(result))
            log.info("Booting LPAR with modified profile...")
            self.hmc.poweron_lpar()
            time.sleep(60)
            max_retries = 10
            for i in range(max_retries):
                try:
                    self.c.run_command("uname -a", timeout=30)
                    log.info("System is up in shared mode")
                    break
                except:
                    if i < max_retries - 1:
                        log.info("Waiting for system... (attempt %d/%d)" % (i+1, max_retries))
                        time.sleep(30)
                    else:
                        raise Exception("System did not boot in shared mode")
            output = self.c.run_command("grep 'shared_processor_mode' /proc/ppc64/lparcfg")
            for line in output:
                if 'shared_processor_mode=1' in line:
                    log.info("Confirmed: System is in SHARED mode")
                    self.proc_mode = 'shared'
                    return True
            raise Exception("Failed to verify shared mode")
        except Exception as e:
            log.error("Failed to change to shared mode: %s" % str(e))
            return False

    def setup_power_gzip(self):
        '''Download and build power-gzip library with compdecomp_th test'''
        log.info("=" * 70)
        log.info("Setting up power-gzip library for workload testing")
        log.info("=" * 70)
        try:
            output = self.c.run_command("mktemp -d /home/nx_gzip_test.XXXXXX")
            self.test_dir = output[0].strip()
            log.info("Created test directory: %s" % self.test_dir)
        except CommandFailed as e:
            log.warning("Failed to create test directory: %s" % str(e))
            return False
        try:
            log.info("Cloning power-gzip from %s (branch: %s)" %
                     (self.POWER_GZIP_URL, self.POWER_GZIP_BRANCH))
            self.c.run_command("cd %s && git clone -b %s %s power-gzip" %
                               (self.test_dir, self.POWER_GZIP_BRANCH, self.POWER_GZIP_URL))
            log.info("Configuring and building power-gzip...")
            self.c.run_command("cd %s/power-gzip && ./configure" % self.test_dir)
            self.c.run_command("cd %s/power-gzip && make" % self.test_dir)
            log.info("Building benchmark binaries (make bench)...")
            self.c.run_command("cd %s/power-gzip && make bench" % self.test_dir)
            self.c.run_command("test -x %s/power-gzip/samples/compdecomp_th" % self.test_dir)
            log.info("Successfully built compdecomp_th binary")
            return True
        except CommandFailed as e:
            log.warning("Failed to build power-gzip: %s" % str(e))
            return False

    def create_test_file(self):
        '''Create 1GB test file using dd for compression testing'''
        log.info("Creating 1GB test file for compression workload...")
        try:
            test_file = "%s/power-gzip/samples/test-file" % self.test_dir
            log.info("Generating test file: %s" % test_file)
            self.c.run_command("cd %s/power-gzip/samples && dd if=/dev/urandom of=test-file bs=1048576 count=1024" %
                               self.test_dir, timeout=300)
            self.test_file = test_file
            log.info("Test file created successfully: %s" % self.test_file)
            return True
        except CommandFailed as e:
            log.warning("Failed to create test file: %s" % str(e))
            return False

    def start_compression_workload(self):
        '''Start compression/decompression workload in background'''
        if not self.test_file:
            log.warning("Test file not available, skipping workload")
            return False
        try:
            threads = 4
            iterations = 50
            workload_log = "%s/power-gzip/samples/nohup.out" % self.test_dir
            lib_path = "%s/power-gzip/lib/.libs" % self.test_dir
            compdecomp_cmd = "cd %s/power-gzip/samples && export LD_LIBRARY_PATH=%s:$LD_LIBRARY_PATH && nohup ./compdecomp_th test-file %d %d > nohup.out 2>&1 &" % (
                self.test_dir, lib_path, threads, iterations)
            log.info("=" * 70)
            log.info("Starting compression/decompression workload in background")
            log.info("=" * 70)
            log.info("Command: ./compdecomp_th test-file %d %d" % (threads, iterations))
            log.info("Note: Workload will run for ~150 seconds during DLPAR operations")
            log.info("Library path: %s" % lib_path)
            log.info("Workload log: %s" % workload_log)
            self.c.run_command(compdecomp_cmd)
            time.sleep(5)
            output = self.c.run_command("pgrep -f compdecomp_th")
            if output and output[0].strip():
                log.info("Workload started successfully with PID: %s" % output[0].strip())
                self.workload_started = True
                return True
            else:
                log.warning("Workload process not found after starting")
                try:
                    error_output = self.c.run_command("cat %s" % workload_log)
                    log.warning("Workload log content:")
                    for line in error_output:
                        log.warning(line)
                except:
                    pass
                return False
        except CommandFailed as e:
            log.warning("Failed to start workload: %s" % str(e))
            return False

    def check_workload_status(self):
        '''Check if compression workload is still running'''
        try:
            output = self.c.run_command("pgrep -f compdecomp_th")
            return bool(output and output[0].strip())
        except CommandFailed:
            return False

    def stop_workload(self):
        '''Stop the compression workload if running'''
        try:
            if self.check_workload_status():
                log.info("Stopping compression workload...")
                self.c.run_command("pkill -9 compdecomp_th")
                time.sleep(2)
        except:
            pass

    def wait_for_workload_completion(self):
        '''Wait for compression workload to complete'''
        if not self.workload_started:
            return
        log.info("=" * 70)
        log.info("Waiting for compression workload to complete...")
        log.info("=" * 70)
        max_wait = 1800
        wait_interval = 10
        elapsed = 0
        while elapsed < max_wait:
            if not self.check_workload_status():
                log.info("Workload completed after %d seconds" % elapsed)
                return
            if elapsed % 60 == 0:  # Log every minute
                log.info("Workload still running... (%d seconds elapsed)" % elapsed)
            time.sleep(wait_interval)
            elapsed += wait_interval
        log.warning("Workload did not complete within %d seconds, stopping it" % max_wait)
        self.stop_workload()

    def display_workload_results(self):
        '''Display the workload results from log file'''
        try:
            workload_log = "%s/power-gzip/samples/nohup.out" % self.test_dir
            log.info("=" * 70)
            log.info("Workload Results (from %s):" % workload_log)
            log.info("=" * 70)
            output = self.c.run_command("cat %s" % workload_log)
            for line in output:
                log.info(line)
        except CommandFailed:
            log.warning("Could not read workload log file")

    def get_vas_credits(self):
        '''Get current VAS credits value'''
        try:
            output = self.c.run_command("cat %s" % self.VAS_CREDITS_PATH)
            credits = int(output[0].strip())
            return credits
        except Exception as e:
            log.error("Failed to get VAS credits: %s" % str(e))
            raise

    def get_processing_units(self):
        '''Get current processing units based on mode
        For both dedicated and shared modes, VAS credits are calculated based on
        the entitled capacity (ent) value.
        Formula: credits = ent × 20
        '''
        try:
            output = self.c.run_command("lparstat 1 1")
            for line in output:
                match = re.search(r'ent[=\s]+([\d.]+)', line, re.IGNORECASE)
                if match:
                    ent_value = float(match.group(1))
                    log.debug("Current ent (%s mode): %.2f" % (self.proc_mode, ent_value))
                    return ent_value
            raise ValueError("Could not find ent value in lparstat output")
        except Exception as e:
            log.error("Failed to get processing units: %s" % str(e))
            raise

    def verify_credits(self, expected_units, operation=""):
        '''Verify VAS credits match formula'''
        credits = self.get_vas_credits()
        expected_credits = int(expected_units * self.CREDITS_PER_UNIT)
        if self.proc_mode == 'dedicated':
            log.info("%sprocs=%d, Expected: %d, Actual: %d" %
                     (operation + ": " if operation else "",
                      int(expected_units), expected_credits, credits))
        else:
            log.info("%sent=%.2f, Expected: %d (%.2f×20), Actual: %d" %
                     (operation + ": " if operation else "",
                      expected_units, expected_credits, expected_units, credits))
        tolerance = 20
        if abs(credits - expected_credits) > tolerance:
            raise Exception("VAS credits mismatch! Expected %d, got %d" %
                            (expected_credits, credits))

    def perform_dlpar_add(self, value):
        '''Add processors or processing units via HMC'''
        try:
            if self.proc_mode == 'dedicated':
                log.info("Adding %d processor(s)..." % value)
                cmd = "chhwres -r proc -m %s -o a -p %s --procs %d" % (
                    self.system_name, self.lpar_name, value)
            else:
                log.info("Adding %.1f processing unit(s)..." % value)
                cmd = "chhwres -r proc -m %s -o a -p %s --procunits %.1f" % (
                    self.system_name, self.lpar_name, value)
            self.hmc.run_command(cmd, timeout=120)
            time.sleep(8)
            return True
        except Exception as e:
            log.error("DLPAR add failed: %s" % str(e))
            return False

    def perform_dlpar_remove(self, value):
        '''Remove processors or processing units via HMC'''
        try:
            if self.proc_mode == 'dedicated':
                log.info("Removing %d processor(s)..." % value)
                cmd = "chhwres -r proc -m %s -o r -p %s --procs %d" % (
                    self.system_name, self.lpar_name, value)
            else:
                log.info("Removing %.1f processing unit(s)..." % value)
                cmd = "chhwres -r proc -m %s -o r -p %s --procunits %.1f" % (
                    self.system_name, self.lpar_name, value)
            self.hmc.run_command(cmd, timeout=120)
            time.sleep(8)
            return True
        except Exception as e:
            log.error("DLPAR remove failed: %s" % str(e))
            return False

    def _test_dedicated_mode(self):
        '''Test VAS credits in dedicated mode with parallel workload'''
        log.info("\n" + "=" * 70)
        log.info("Testing DEDICATED MODE with Parallel Workload")
        log.info("=" * 70)
        initial_units = self.get_processing_units()
        self.verify_credits(initial_units, "Initial")
        if self.start_compression_workload():
            log.info("Workload running in background during DLPAR operations")
        for procs in self.DEDICATED_MODE_PROCS:
            log.info("\n--- Adding %d processor(s) ---" % procs)
            if self.perform_dlpar_add(procs):
                units = self.get_processing_units()
                self.verify_credits(units, "After ADD %d" % procs)
                time.sleep(2)
        for procs in self.DEDICATED_MODE_PROCS:
            log.info("\n--- Removing %d processor(s) ---" % procs)
            if self.perform_dlpar_remove(procs):
                units = self.get_processing_units()
                self.verify_credits(units, "After REMOVE %d" % procs)
                time.sleep(2)
        self.wait_for_workload_completion()
        self.display_workload_results()
        log.info("\nDedicated mode testing completed successfully")

    def _test_shared_mode(self):
        '''Test VAS credits in shared mode with parallel workload'''
        log.info("\n" + "=" * 70)
        log.info("Testing SHARED MODE with Parallel Workload")
        log.info("=" * 70)
        initial_units = self.get_processing_units()
        self.verify_credits(initial_units, "Initial")
        if self.start_compression_workload():
            log.info("Workload running in background during DLPAR operations")
        for units in self.SHARED_MODE_PROCUNITS:
            log.info("\n--- Adding %.1f processing unit(s) ---" % units)
            if self.perform_dlpar_add(units):
                current_units = self.get_processing_units()
                self.verify_credits(current_units, "After ADD %.1f" % units)
                time.sleep(2)
        for units in self.SHARED_MODE_PROCUNITS:
            log.info("\n--- Removing %.1f processing unit(s) ---" % units)
            if self.perform_dlpar_remove(units):
                current_units = self.get_processing_units()
                self.verify_credits(current_units, "After REMOVE %.1f" % units)
                time.sleep(2)
        self.wait_for_workload_completion()
        self.display_workload_results()
        log.info("\nShared mode testing completed successfully")

    def runTest(self):
        '''Main test execution'''
        log.info("=" * 70)
        log.info("NX GZIP VAS Credits Comprehensive Test")
        log.info("Testing both Dedicated and Shared modes with profile save/restore")
        log.info("=" * 70)
        c = self.set_up()
        try:
            if not self.save_lpar_profile():
                self.fail("Failed to save LPAR profile")
            if not self.setup_power_gzip():
                self.fail("Failed to setup power-gzip")
            if not self.create_test_file():
                self.fail("Failed to create test file")
            if not self.change_to_dedicated_mode(num_procs=self.dedicated_num_procs):
                self.fail("Failed to change to dedicated mode")
            self._test_dedicated_mode()
            if not self.change_to_shared_mode(desired_proc_units=self.shared_proc_units):
                self.fail("Failed to change to shared mode")
            self._test_shared_mode()
            log.info("\n" + "=" * 70)
            log.info("ALL TESTS PASSED")
            log.info("=" * 70)
        finally:
            self.restore_lpar_profile()

    def tearDown(self):
        '''Cleanup after test'''
        try:
            self.stop_workload()
            if self.test_dir:
                self.c.run_command("rm -rf %s || true" % self.test_dir)
        except:
            pass
        log.info("Test cleanup completed")


def nx_gzip_vas_credits_suite():
    '''Test suite'''
    suite = unittest.TestSuite()
    suite.addTest(OpTestNXGzipVasCredits('runTest'))
    return suite
