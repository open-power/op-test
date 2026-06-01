#!/usr/bin/env python3
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

'''
OpTestVpmemBugFixTest:

This test suite verifies LPAR stability with vpmem namespace operations.
Tests are designed to detect crashes and calltraces related to:
- Bug 208717 - RHEL-60836: LPAR crashes while running ndctl operations
- Bug 212689 - SUSE1243298: LPAR crashes when destroying namespaces after reboot
'''

import unittest
import time
import re

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestVpmemBugFixTest(unittest.TestCase):
    '''
    Test class for LPAR boot with 20GB memory and 50GB vpmem configuration
    '''

    @classmethod
    def setUpClass(cls):
        """
        Set up the test environment
        """
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.bmc_type = conf.args.bmc_type

        if cls.bmc_type not in ["FSP_PHYP", "EBMC_PHYP"]:
            raise unittest.SkipTest("This test is only supported on LPAR (FSP_PHYP or EBMC_PHYP)")

        cls.hmc_user = conf.args.hmc_username
        cls.hmc_password = conf.args.hmc_password
        cls.hmc_ip = conf.args.hmc_ip
        cls.lpar_name = conf.args.lpar_name
        cls.system_name = conf.args.system_name
        cls.cv_HMC = cls.cv_SYSTEM.hmc
        cls.lpar_prof = conf.args.lpar_prof
        cls.desired_memory = "20480"  # 20GB in MB
        cls.min_memory = "20480"      # 20GB in MB
        cls.max_memory = "20480"      # 20GB in MB
        cls.vpmem_size = "51200"      # 50GB in MB
        cls.vpmem_name = "vpmem_bugfix_vol"

    def setUp(self):
        """
        Prepare the system for testing
        """
        log.info("=" * 80)
        log.info("Starting OpTestVpmemBugFixTest")
        log.info("=" * 80)

    def _ensure_ndctl_installed(self, console):
        """
        Helper method to ensure ndctl is installed on the system
        """
        try:
            console.run_command("which ndctl", timeout=30)
            log.info("  ndctl is already installed")
            return
        except CommandFailed:
            log.info("ndctl not found, attempting to install...")

        try:
            output = console.run_command("grep '^ID=' /etc/os-release", timeout=30)
            distro_name = 'unknown'
            for line in output:
                if 'ID=' in line:
                    distro_name = line.split('=')[1].strip().strip('"').strip("'").lower()
                    break
            log.info("  Detected OS distribution: {}".format(distro_name))
        except CommandFailed:
            log.warning("  Could not detect OS distribution")
            self.fail("Could not detect OS distribution. This test only supports RHEL and SLES.")

        try:
            if distro_name in ['rhel', 'centos', 'fedora']:
                console.run_command("yum install -y ndctl", timeout=300)
            elif distro_name in ['sles', 'suse', 'opensuse']:
                console.run_command("zypper install -y ndctl", timeout=300)
            else:
                self.fail("Unsupported distribution: {}. This test only supports RHEL and SLES.".format(distro_name))

            log.info("  ndctl installed successfully")
            console.run_command("which ndctl", timeout=30)
            log.info("  ndctl binary is available")

        except CommandFailed as e:
            self.fail("Failed to install ndctl. Please install it manually. Error: {}".format(str(e)))

    def test_single_vpmem_with_namespace_operations(self):
        """
        Test: Single 50GB vpmem with 5 namespace creation and destruction
        - 20GB memory, 50GB vpmem (affinity=0)
        - Create 5 namespaces of 10GB each
        - Destroy all namespaces
        - Verify no calltraces/crashes
        """
        try:
            log.info("[Step 1] Powering off LPAR...")
            self.cv_HMC.poweroff_lpar()
            time.sleep(10)
            log.info("[Step 2] Backing up current LPAR profile...")
            self.cv_HMC.profile_bckup()
            log.info("[Step 3] Configuring LPAR memory to 20GB...")
            log.info("  - Min Memory: %s MB" % self.min_memory)
            log.info("  - Desired Memory: %s MB" % self.desired_memory)
            log.info("  - Max Memory: %s MB" % self.max_memory)
            current_lmb = self.cv_HMC.get_lmb_size()
            log.info("  - Current LMB size: %s MB" % current_lmb[0])

            if int(self.vpmem_size) % int(current_lmb[0]) != 0:
                self.fail("vpmem_size (%s MB) must be a multiple of LMB size (%s MB)" %
                          (self.vpmem_size, current_lmb[0]))

            attrs = "min_mem={0},desired_mem={1},max_mem={2}".format(
                self.min_memory, self.desired_memory, self.max_memory)
            self.cv_HMC.set_lpar_cfg(attrs)
            log.info("  Memory configuration updated successfully")

            log.info("[Step 4] Checking for existing vpmem configuration...")
            vpmem_count = self.cv_HMC.vpmem_count()
            if int(vpmem_count[0]) >= 1:
                log.info("  Removing existing vpmem volumes...")
                self.cv_HMC.remove_vpmem()
                log.info("  Existing vpmem volumes removed")
            else:
                log.info("  No existing vpmem volumes found")

            log.info("[Step 5] Configuring 50GB vpmem device...")
            log.info("  - VPMEM Name: %s" % self.vpmem_name)
            log.info("  - VPMEM Size: %s MB (50GB)" % self.vpmem_size)
            log.info("  - Affinity: 0")
            self.cv_HMC.configure_vpmem(self.vpmem_name, self.vpmem_size, 0)
            curr_num_volumes = self.cv_HMC.vpmem_count()
            if int(curr_num_volumes[0]) >= 1:
                log.info("  Successfully configured vpmem volume")
            else:
                self.fail("Failed to configure vpmem device")

            log.info("[Step 6] Powering off LPAR to apply configuration changes...")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            log.info("  LPAR powered off successfully")

            log.info("[Step 7] Booting LPAR to OS with new configuration...")
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            log.info("  System successfully booted to OS")

            log.info("[Step 8] Verifying console connection...")
            console = self.cv_SYSTEM.console
            console.run_command("uname -a", timeout=60)
            log.info("  Console is working properly")

            log.info("[Step 9] Verifying memory configuration...")
            mem_output = console.run_command("free -m | awk '/^Mem:/ {print $2}'", timeout=60)
            if mem_output:
                total_mem_mb = int(mem_output[0].strip())
                log.info("  Total system memory: %d MB" % total_mem_mb)
                expected_mem = int(self.desired_memory)
                tolerance = 1024
                if abs(total_mem_mb - expected_mem) > tolerance:
                    log.warning("  Memory mismatch: Expected ~%d MB, got %d MB" %
                                (expected_mem, total_mem_mb))
                else:
                    log.info("  Memory configuration verified successfully")

            log.info("[Step 10] Verifying vpmem device availability...")
            self._ensure_ndctl_installed(console)

            try:
                regions = console.run_command("ndctl list -R", timeout=60)
                if regions:
                    log.info("  NVDIMM regions found:")
                    for line in regions:
                        log.info("    %s" % line.strip())
                else:
                    log.warning("  No NVDIMM regions found")
                pmem_check = console.run_command("ls -l /dev/pmem* 2>/dev/null || echo 'No pmem devices'",
                                                 timeout=30)
                if pmem_check:
                    log.info("  PMEM devices:")
                    for line in pmem_check:
                        log.info("    %s" % line.strip())
            except CommandFailed as e:
                log.warning("  Could not verify vpmem devices: %s" % str(e))

            log.info("[Step 11] Creating 5 namespaces of 10GB each...")
            try:
                log.info("  Destroying any existing namespaces...")
                console.run_command("ndctl destroy-namespace all -f", timeout=60)
                log.info("  Existing namespaces destroyed")
            except CommandFailed:
                log.info("  No existing namespaces to destroy")
            namespace_count = 5
            namespace_size = "10g"
            created_namespaces = []

            for i in range(namespace_count):
                try:
                    log.info("  Creating namespace %d/%d (size: %s)..." % (i+1, namespace_count, namespace_size))
                    cmd = "ndctl create-namespace --mode=dax --region=0 --size=%s" % namespace_size
                    output = console.run_command(cmd, timeout=120)
                    if output:
                        log.info("  Namespace %d created successfully:" % (i+1))
                        for line in output:
                            log.info("    %s" % line.strip())
                        created_namespaces.append(i+1)
                except CommandFailed as e:
                    log.error("  Failed to create namespace %d: %s" % (i+1, str(e)))
                    self.fail("Failed to create namespace %d" % (i+1))

            if len(created_namespaces) == namespace_count:
                log.info("  Successfully created all %d namespaces" % namespace_count)
            else:
                self.fail("Only created %d out of %d namespaces" % (len(created_namespaces), namespace_count))

            log.info("  Listing all created namespaces...")
            try:
                ns_list = console.run_command("ndctl list -N", timeout=60)
                if ns_list:
                    log.info("  Created namespaces:")
                    for line in ns_list:
                        log.info("    %s" % line.strip())
            except CommandFailed as e:
                log.warning("  Could not list namespaces: %s" % str(e))

            log.info("[Step 12] Destroying all namespaces at once...")
            try:
                destroy_output = console.run_command("ndctl destroy-namespace all -f", timeout=120)
                if destroy_output:
                    log.info("  Namespace destruction output:")
                    for line in destroy_output:
                        log.info("    %s" % line.strip())
                log.info("  All namespaces destroyed successfully")

                verify_output = console.run_command("ndctl list -N", timeout=60)
                if not verify_output or len(verify_output) == 0:
                    log.info("  Verified: No namespaces remaining")
                else:
                    log.warning("  Warning: Some namespaces may still exist:")
                    for line in verify_output:
                        log.warning("    %s" % line.strip())
            except CommandFailed as e:
                log.error("  Failed to destroy namespaces: %s" % str(e))

            log.info("[Step 13] Checking system logs for calltraces and crashes after namespace destruction...")
            try:
                calltrace_check = console.run_command("dmesg | grep -i 'call trace\\|calltrace\\|BUG:\\|WARNING:\\|Oops'",
                                                      timeout=60)
                if calltrace_check and len(calltrace_check) > 0:
                    log.error("  CALLTRACE DETECTED in dmesg:")
                    for line in calltrace_check:
                        log.error("    %s" % line.strip())
                    self.fail("Test FAILED: Calltrace detected in system logs after namespace destruction")
                else:
                    log.info("  No calltraces found")
            except CommandFailed:
                log.info("  No calltraces found")

            try:
                crash_check = console.run_command("dmesg | grep -i 'kernel panic\\|segfault\\|general protection fault'",
                                                  timeout=60)
                if crash_check and len(crash_check) > 0:
                    log.error("  CRASH/PANIC DETECTED in dmesg:")
                    for line in crash_check:
                        log.error("    %s" % line.strip())
                    self.fail("Test FAILED: Kernel crash or panic detected in system logs after namespace destruction")
                else:
                    log.info("  No crashes or panics found")
            except CommandFailed:
                log.info("  No crashes or panics found")

            try:
                pmem_messages = console.run_command("dmesg | grep -i 'pmem\\|nvdimm' | tail -20",
                                                    timeout=60)
                if pmem_messages:
                    log.info("  Recent PMEM/NVDIMM messages:")
                    for line in pmem_messages:
                        log.info("    %s" % line.strip())
            except CommandFailed:
                log.info("  No PMEM/NVDIMM messages found")
            log.info("=" * 80)
            log.info("SUCCESS: LPAR booted with 20GB memory, 50GB vpmem, 5 namespaces created and destroyed")
            log.info("  No calltraces or crashes detected")
            log.info("=" * 80)
        except Exception as e:
            log.error("Test failed with error: %s" % str(e))
            raise

    def test_multiple_vpmem_mixed_affinity_with_reboot(self):
        """
        Test: Multiple vpmem volumes with mixed affinity, namespace operations, and reboot
        - 3 vpmem volumes of 8GB (1 with affinity=1, 2 with affinity=0)
        - Create 4 namespaces with mixed alignments (64KB and 2MB)
        - Reboot LPAR
        - Destroy all namespaces
        - Verify no calltraces/crashes
        """
        try:
            log.info("=" * 80)
            log.info("Starting test_lpar_boot_with_multiple_vpmem_affinity")
            log.info("=" * 80)

            log.info("[Step 1] Powering off LPAR...")
            self.cv_HMC.poweroff_lpar()
            time.sleep(10)

            log.info("[Step 2] Backing up current LPAR profile...")
            self.cv_HMC.profile_bckup()

            log.info("[Step 3] Checking LMB size...")
            current_lmb = self.cv_HMC.get_lmb_size()
            log.info("  - Current LMB size: %s MB" % current_lmb[0])

            vpmem_size = "8192"  # 8GB in MB

            if int(vpmem_size) % int(current_lmb[0]) != 0:
                self.fail("vpmem_size (%s MB) must be a multiple of LMB size (%s MB)" %
                          (vpmem_size, current_lmb[0]))

            log.info("[Step 4] Checking for existing vpmem configuration...")
            vpmem_count = self.cv_HMC.vpmem_count()
            if int(vpmem_count[0]) >= 1:
                log.info("  Removing existing vpmem volumes...")
                self.cv_HMC.remove_vpmem()
                log.info("  Existing vpmem volumes removed")
            else:
                log.info("  No existing vpmem volumes found")

            log.info("[Step 5] Configuring 3 vpmem volumes of 8GB each...")

            log.info("  Creating volume 1 with affinity ENABLED (affinity=1)...")
            self.cv_HMC.configure_vpmem("vpmem_vol1", vpmem_size, 1)
            log.info("  Volume 1 created with affinity=1")

            log.info("  Creating volume 2 with affinity DISABLED (affinity=0)...")
            self.cv_HMC.configure_vpmem("vpmem_vol2", vpmem_size, 0)
            log.info("  Volume 2 created with affinity=0")

            log.info("  Creating volume 3 with affinity DISABLED (affinity=0)...")
            self.cv_HMC.configure_vpmem("vpmem_vol3", vpmem_size, 0)
            log.info("  Volume 3 created with affinity=0")

            curr_num_volumes = self.cv_HMC.vpmem_count()
            if int(curr_num_volumes[0]) >= 3:
                log.info("  Successfully configured %s vpmem volumes" % curr_num_volumes[0])
            else:
                self.fail("Failed to configure all 3 vpmem volumes. Only %s configured" % curr_num_volumes[0])

            log.info("[Step 6] Powering off LPAR to apply configuration changes...")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            log.info("  LPAR powered off successfully")

            log.info("[Step 7] Booting LPAR to OS with 3 vpmem volumes...")
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            log.info("  System successfully booted to OS")

            log.info("[Step 8] Verifying vpmem devices...")
            console = self.cv_SYSTEM.console
            console.run_command("uname -a", timeout=60)
            log.info("  Console is working properly")

            self._ensure_ndctl_installed(console)

            try:
                regions = console.run_command("ndctl list -R", timeout=60)
                if regions:
                    log.info("  NVDIMM regions found:")
                    for line in regions:
                        log.info("    %s" % line.strip())

                pmem_check = console.run_command("ls -l /dev/pmem* 2>/dev/null || echo 'Checking...'",
                                                 timeout=30)
                if pmem_check:
                    log.info("  PMEM devices:")
                    for line in pmem_check:
                        log.info("    %s" % line.strip())

            except CommandFailed as e:
                log.warning("  Could not verify vpmem devices: %s" % str(e))

            log.info("[Step 9] Creating 4 namespaces in region 1 with different alignments...")

            try:
                log.info("  Destroying any existing namespaces...")
                console.run_command("ndctl destroy-namespace all -f", timeout=60)
                log.info("  Existing namespaces destroyed")
            except CommandFailed:
                log.info("  No existing namespaces to destroy")

            namespace_configs = [
                {"size": "1552M", "align": "65536", "desc": "64KB alignment"},
                {"size": "1552M", "align": None, "desc": "default (2MB) alignment"},
                {"size": "1552M", "align": "65536", "desc": "64KB alignment"},
                {"size": "1552M", "align": None, "desc": "default (2MB) alignment"}
            ]

            created_namespaces = []
            for i, config in enumerate(namespace_configs):
                try:
                    if config["align"]:
                        cmd = "ndctl create-namespace --mode=dax --region=1 --size=%s --align=%s" % (config["size"], config["align"])
                    else:
                        cmd = "ndctl create-namespace --mode=dax --region=1 --size=%s" % config["size"]

                    log.info("  Creating namespace %d/4 (size: %s, %s)..." % (i+1, config["size"], config["desc"]))
                    output = console.run_command(cmd, timeout=120)

                    if output:
                        log.info("  Namespace %d created successfully:" % (i+1))
                        for line in output:
                            log.info("    %s" % line.strip())
                        created_namespaces.append(i+1)

                except CommandFailed as e:
                    log.error("  Failed to create namespace %d: %s" % (i+1, str(e)))
                    self.fail("Failed to create namespace %d" % (i+1))

            if len(created_namespaces) == 4:
                log.info("  Successfully created all 4 namespaces")
            else:
                self.fail("Only created %d out of 4 namespaces" % len(created_namespaces))

            log.info("  Listing all created namespaces...")
            try:
                ns_list = console.run_command("ndctl list -N", timeout=60)
                if ns_list:
                    log.info("  Created namespaces:")
                    for line in ns_list:
                        log.info("    %s" % line.strip())
            except CommandFailed as e:
                log.warning("  Could not list namespaces: %s" % str(e))

            log.info("[Step 10] Rebooting the LPAR...")
            log.info("  Powering off LPAR...")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            time.sleep(10)

            log.info("  Booting LPAR back to OS...")
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            log.info("  System successfully rebooted to OS")

            console = self.cv_SYSTEM.console
            console.run_command("uname -a", timeout=60)
            log.info("  Console is working after reboot")

            log.info("[Step 11] Destroying all namespaces at once after reboot...")
            try:
                destroy_output = console.run_command("ndctl destroy-namespace all -f", timeout=120)
                if destroy_output:
                    log.info("  Namespace destruction output:")
                    for line in destroy_output:
                        log.info("    %s" % line.strip())
                log.info("  All namespaces destroyed successfully")

                verify_output = console.run_command("ndctl list -N", timeout=60)
                if not verify_output or len(verify_output) == 0:
                    log.info("  Verified: No namespaces remaining")
                else:
                    log.warning("  Warning: Some namespaces may still exist:")
                    for line in verify_output:
                        log.warning("    %s" % line.strip())

            except CommandFailed as e:
                log.error("  Failed to destroy namespaces: %s" % str(e))

            log.info("[Step 12] Checking system logs for calltraces and crashes after namespace destruction...")

            try:
                calltrace_check = console.run_command("dmesg | grep -i 'call trace\\|calltrace\\|BUG:\\|WARNING:\\|Oops'",
                                                      timeout=60)
                if calltrace_check and len(calltrace_check) > 0:
                    log.error("  CALLTRACE DETECTED in dmesg:")
                    for line in calltrace_check:
                        log.error("    %s" % line.strip())
                    self.fail("Test FAILED: Calltrace detected in system logs after namespace destruction")
                else:
                    log.info("  No calltraces found")
            except CommandFailed:
                log.info("  No calltraces found")

            try:
                crash_check = console.run_command("dmesg | grep -i 'kernel panic\\|segfault\\|general protection fault'",
                                                  timeout=60)
                if crash_check and len(crash_check) > 0:
                    log.error("  CRASH/PANIC DETECTED in dmesg:")
                    for line in crash_check:
                        log.error("    %s" % line.strip())
                    self.fail("Test FAILED: Kernel crash or panic detected in system logs after namespace destruction")
                else:
                    log.info("  No crashes or panics found")
            except CommandFailed:
                log.info("  No crashes or panics found")

            log.info("=" * 80)
            log.info("SUCCESS: LPAR booted with 3 vpmem volumes, 4 namespaces created, rebooted, and destroyed")
            log.info("  No calltraces or crashes detected")
            log.info("=" * 80)

        except Exception as e:
            log.error("Test failed with error: %s" % str(e))
            raise

    def tearDown(self):
        """
        Cleanup after test
        """
        log.info("Test completed")

    @classmethod
    def tearDownClass(cls):
        """
        Final cleanup
        """
        log.info("OpTestVpmemBugFixTest completed")


def suite():
    """
    Create test suite with both test cases
    """
    suite = unittest.TestSuite()
    suite.addTest(OpTestVpmemBugFixTest('test_single_vpmem_with_namespace_operations'))
    suite.addTest(OpTestVpmemBugFixTest('test_multiple_vpmem_mixed_affinity_with_reboot'))
    return suite


if __name__ == '__main__':
    unittest.main()
