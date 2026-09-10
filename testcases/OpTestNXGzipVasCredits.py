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
import re
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
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
        self.system = conf.system()
        self.proc_mode = None
        self.hmc = conf.hmc()
        self.util = OpTestUtil(conf)
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

    def change_to_dedicated_mode(self, num_procs=4):
        '''Change LPAR to dedicated mode with specified processors'''
        log.info("Changing to dedicated mode with %d processors" % num_procs)
        self.hmc.change_proc_mode(
            proc_mode='ded',
            sharing_mode='share_idle_procs',
            min_proc_units=num_procs,
            desired_proc_units=num_procs,
            max_proc_units=num_procs + 7,
            min_memory="4096",
            desired_memory="40960",
            max_memory="81920"
        )
        self.hmc.poweroff_lpar()
        self.hmc.poweron_lpar()
        self.system.goto_state(OpSystemState.OS)
        self.c = self.system.cv_HOST.get_ssh_connection()
        output = self.c.run_command("grep 'shared_processor_mode' /proc/ppc64/lparcfg")
        for line in output:
            if 'shared_processor_mode=0' in line:
                log.info("System verified in dedicated mode")
                self.proc_mode = 'dedicated'
                return True
        raise Exception("Failed to verify dedicated mode")

    def change_to_shared_mode(self, desired_proc_units=2.5):
        '''Change LPAR to shared mode with specified processing units'''
        log.info("Changing to shared mode with %.1f processing units" % desired_proc_units)
        min_units = 1.0
        max_units = int(desired_proc_units + 2.5)
        overcommit_ratio = 3
        self.hmc.change_proc_mode(
            proc_mode='shared',
            sharing_mode='uncap',
            min_proc_units=min_units,
            desired_proc_units=desired_proc_units,
            max_proc_units=max_units,
            min_memory="4096",
            desired_memory="40960",
            max_memory="81920",
            overcommit_ratio=overcommit_ratio
        )
        self.hmc.poweroff_lpar()
        self.hmc.poweron_lpar()
        self.system.goto_state(OpSystemState.OS)
        self.c = self.system.cv_HOST.get_ssh_connection()
        output = self.c.run_command("grep 'shared_processor_mode' /proc/ppc64/lparcfg")
        for line in output:
            if 'shared_processor_mode=1' in line:
                log.info("System verified in shared mode")
                self.proc_mode = 'shared'
                return True
        raise Exception("Failed to verify shared mode")

    def install_required_packages(self):
        '''Install build dependencies including zlib-static for power-gzip'''
        distro = self.util.distro_name()
        log.info("Detected distro: %s" % distro)
        if distro == 'rhel':
            packages = ['git', 'gcc', 'make', 'zlib-devel', 'zlib-static']
        elif distro == 'sles':
            packages = ['git', 'gcc', 'make', 'zlib-devel', 'zlib-devel-static']
        else:
            self.fail("Unsupported distribution '%s': cannot install required packages" % distro)
        log.info("Installing packages: %s" % packages)
        self.util.install_package(packages)
        log.info("Required packages installed successfully")

    def setup_power_gzip(self):
        '''Download and build power-gzip library with compdecomp_th test'''
        self.install_required_packages()
        try:
            output = self.c.run_command("mktemp -d /home/nx_gzip_test.XXXXXX")
            self.test_dir = output[0].strip()
            self.c.run_command("cd %s && git clone -b %s %s power-gzip" %
                               (self.test_dir, self.POWER_GZIP_BRANCH, self.POWER_GZIP_URL))
            self.c.run_command("cd %s/power-gzip && ./configure && make && make bench" % self.test_dir)
            self.c.run_command("test -x %s/power-gzip/samples/compdecomp_th" % self.test_dir)
            log.info("Successfully built power-gzip benchmark binary")
            return True
        except CommandFailed as e:
            log.warning("Failed to build power-gzip: %s" % str(e))
            return False

    def create_test_file(self):
        '''Create 1GB test file using dd for compression testing'''
        try:
            self.test_file = "%s/power-gzip/samples/test-file" % self.test_dir
            self.c.run_command("cd %s/power-gzip/samples && dd if=/dev/urandom of=test-file bs=1048576 count=1024" %
                               self.test_dir, timeout=300)
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
            self.c.run_command(compdecomp_cmd)
            time.sleep(5)
            output = self.c.run_command("pgrep -f compdecomp_th")
            if output and output[0].strip():
                log.info("Compression workload started in background (PID: %s)" % output[0].strip())
                self.workload_started = True
                return True
            else:
                log.warning("Workload process not found after starting")
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
                self.c.run_command("pkill -9 compdecomp_th")
                time.sleep(2)
        except:
            pass

    def wait_for_workload_completion(self):
        '''Wait for compression workload to complete'''
        if not self.workload_started:
            return
        max_wait = 1800
        wait_interval = 10
        elapsed = 0
        while elapsed < max_wait:
            if not self.check_workload_status():
                log.info("Workload completed after %d seconds" % elapsed)
                return
            time.sleep(wait_interval)
            elapsed += wait_interval
        log.warning("Workload did not complete within %d seconds, stopping it" % max_wait)
        self.stop_workload()

    def display_workload_results(self):
        '''Display the workload results from log file'''
        try:
            workload_log = "%s/power-gzip/samples/nohup.out" % self.test_dir
            output = self.c.run_command("cat %s" % workload_log)
            for line in output:
                log.debug(line)
        except CommandFailed:
            log.warning("Could not read workload log file")

    def get_vas_credits(self):
        '''Get current VAS credits value'''
        try:
            output = self.c.run_command("cat %s" % self.VAS_CREDITS_PATH)
            return int(output[0].strip())
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
        log.info("Testing dedicated mode with parallel workload")
        initial_units = self.get_processing_units()
        self.verify_credits(initial_units, "Initial")
        self.start_compression_workload()
        for procs in self.DEDICATED_MODE_PROCS:
            if self.perform_dlpar_add(procs):
                units = self.get_processing_units()
                self.verify_credits(units, "After ADD %d" % procs)
                time.sleep(2)
        for procs in self.DEDICATED_MODE_PROCS:
            if self.perform_dlpar_remove(procs):
                units = self.get_processing_units()
                self.verify_credits(units, "After REMOVE %d" % procs)
                time.sleep(2)
        self.wait_for_workload_completion()
        self.display_workload_results()
        log.info("Dedicated mode testing completed successfully")

    def _test_shared_mode(self):
        '''Test VAS credits in shared mode with parallel workload'''
        log.info("Testing shared mode with parallel workload")
        initial_units = self.get_processing_units()
        self.verify_credits(initial_units, "Initial")
        self.start_compression_workload()
        for units in self.SHARED_MODE_PROCUNITS:
            if self.perform_dlpar_add(units):
                current_units = self.get_processing_units()
                self.verify_credits(current_units, "After ADD %.1f" % units)
                time.sleep(2)
        for units in self.SHARED_MODE_PROCUNITS:
            if self.perform_dlpar_remove(units):
                current_units = self.get_processing_units()
                self.verify_credits(current_units, "After REMOVE %.1f" % units)
                time.sleep(2)
        self.wait_for_workload_completion()
        self.display_workload_results()
        log.info("Shared mode testing completed successfully")

    def runTest(self):
        '''Main test execution'''
        log.info("Starting NX GZIP VAS credits test")
        self.set_up()
        try:
            self.hmc.profile_bckup()
            if not self.setup_power_gzip():
                self.fail("Failed to setup power-gzip")
            if not self.create_test_file():
                self.fail("Failed to create test file")
            self.change_to_dedicated_mode(num_procs=self.dedicated_num_procs)
            self._test_dedicated_mode()
            self.change_to_shared_mode(desired_proc_units=self.shared_proc_units)
            self._test_shared_mode()
            log.info("NX GZIP VAS credits test completed successfully")
        finally:
            log.info("Restoring original LPAR profile")
            self.hmc.profile_restore()
            self.system.goto_state(OpSystemState.OS)

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
