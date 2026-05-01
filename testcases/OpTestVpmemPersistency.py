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
OpTestVpmemPersistency: Verify data persistency on vpmem device across reboot
------------------------------------------------------------------------------

This test verifies that data written to a vpmem device persists across system reboots.

Test steps:
1. Check for vpmem device availability
2. Create namespace using ndctl
3. Create file system with DAX support
4. Mount the vpmem device with DAX option
5. Create a test file with unique content
6. Reboot the system (power off/on cycle)
7. Remount the vpmem device
8. Verify the test file still exists with correct content

Configuration Parameters (optional):
------------------------------------
The following parameters can be passed via command line to customize the test:

--vpmem-device <path>        : Path to vpmem device (default: /dev/pmem0)
--vpmem-mount-point <path>   : Mount point for vpmem device (default: /pmem0)
--vpmem-namespace <name>     : Namespace name (default: namespace0.0)
--vpmem-region <name>        : Region name (default: region0)

Usage Examples:
--------------
# Run XFS test with default parameters:
./op-test --run testcases.OpTestVpmemPersistency.VpmemPersistencyXfsTest

# Run ext4 test with default parameters:
./op-test --run testcases.OpTestVpmemPersistency.VpmemPersistencyExt4Test

# Run both tests:
./op-test --run-suite vpmem_suite

# Run with custom parameters:
./op-test --run testcases.OpTestVpmemPersistency.VpmemPersistencyXfsTest \
  --vpmem-device /dev/pmem1 \
  --vpmem-mount-point /mnt/pmem1 \
  --vpmem-namespace namespace1.0 \
  --vpmem-region region1
'''

import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestVpmemPersistency(unittest.TestCase):
    '''
    Test class for vpmem data persistency verification
    '''

    @classmethod
    def setUpClass(cls):
        """
        Set up the test environment
        """
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.util = conf.util
        cls.vpmem_device = getattr(conf.args, 'vpmem_device', None) or "/dev/pmem0"
        cls.mount_point = getattr(conf.args, 'vpmem_mount_point', None) or "/pmem0"
        cls.test_file = "persistency_test_file.txt"
        cls.test_content = "VPMEM_PERSISTENCY_TEST_DATA_{}".format(
            int(time.time())
        )
        cls.namespace_name = getattr(conf.args, 'vpmem_namespace', None) or "namespace0.0"
        cls.region = getattr(conf.args, 'vpmem_region', None) or "region0"
        cls.filesystem_type = "xfs"

    def setUp(self):
        """
        Prepare the system for testing - boot to OS
        """
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_SYSTEM.console

    def install_required_packages(self):
        """
        Install required packages (ndctl and xfsprogs) if not present
        Uses distro-specific package managers:
        - RHEL: yum
        - SLES: zypper
        - Other distros: skip test
        """
        log.info("Installing required packages")
        output = self.console.run_command("grep '^ID=' /etc/os-release", timeout=30)
        distro_name = 'unknown'
        for line in output:
            if 'ID=' in line:
                distro_name = line.split('=')[1].strip().strip('"').strip("'").lower()
                break
        log.info("Detected OS distribution: {}".format(distro_name))
        packages = ['ndctl']
        if self.filesystem_type == 'xfs':
            packages.append('xfsprogs')
        elif self.filesystem_type == 'ext4':
            packages.append('e2fsprogs')

        if distro_name == 'rhel':
            installer = "yum install"
            install_cmd_format = "{} {} -y"
        elif distro_name == 'sles':
            installer = "zypper install"
            install_cmd_format = "{} -y {}"
        else:
            self.skipTest("Unsupported distribution: {}. This test only supports RHEL and SLES.".format(distro_name))
        log.info("Installing packages using: {}".format(installer))
        for pkg in packages:
            cmd = install_cmd_format.format(installer, pkg)
            log.info("Running: {}".format(cmd))
            self.console.run_command(cmd, timeout=600)
            log.info("Package {} installed successfully".format(pkg))
        self.console.run_command("which ndctl", timeout=30)
        log.info("ndctl binary is available")
        if self.filesystem_type == 'xfs':
            self.console.run_command("which mkfs.xfs", timeout=30)
            log.info("mkfs.xfs binary is available")
        elif self.filesystem_type == 'ext4':
            self.console.run_command("which mkfs.ext4", timeout=30)
            log.info("mkfs.ext4 binary is available")
        log.info("All required packages are installed and verified")

    def check_vpmem_device(self):
        """
        Step 1: Check if vpmem device exists in the system
        """
        log.info("Step 1: Checking for vpmem device availability")
        self.install_required_packages()
        output = self.console.run_command("which ndctl", timeout=30)
        log.info("ndctl utility is available")
        output = self.console.run_command("ndctl list -R", timeout=30)
        log.info("Available NVDIMM regions: {}".format(output))
        if not output or output == ['']:
            self.skipTest("No NVDIMM regions found in the system")

    def create_namespace(self):
        """
        Step 2: Create namespace with fsdax mode
        """
        log.info("Step 2: Creating namespace in fsdax mode")
        self.console.run_command(
            "ndctl destroy-namespace {} -f 2>/dev/null || true".format(self.namespace_name),
            timeout=60
        )
        log.info("Attempted to destroy existing namespace")
        cmd = "ndctl create-namespace -m fsdax -r {}".format(self.region)
        output = self.console.run_command(cmd, timeout=120)
        log.info("Namespace created: {}".format(output))
        output = self.console.run_command("ndctl list -N", timeout=30)
        log.info("Available namespaces: {}".format(output))
        time.sleep(5)
        output = self.console.run_command("ls -l /dev/pmem*", timeout=30)
        log.info("PMEM devices: {}".format(output))

    def create_filesystem(self):
        """
        Step 3: Create filesystem with DAX support (XFS or ext4)
        """
        log.info("Step 3: Creating {} filesystem on {}".format(
            self.filesystem_type, self.vpmem_device
        ))
        if self.filesystem_type == "xfs":
            cmd = "mkfs.xfs -f -b size=64k -s size=4k {}".format(self.vpmem_device)
        elif self.filesystem_type == "ext4":
            cmd = "mkfs.ext4 -F -b 65536 {}".format(self.vpmem_device)
        else:
            self.fail("Unsupported filesystem type: {}".format(self.filesystem_type))
        output = self.console.run_command(cmd, timeout=120)
        log.info("Filesystem created: {}".format(output))
        output = self.console.run_command(
            "blkid {}".format(self.vpmem_device),
            timeout=30
        )
        log.info("Filesystem info: {}".format(output))

    def mount_vpmem(self):
        """
        Step 4: Mount vpmem device with DAX option
        """
        log.info("Step 4: Mounting {} to {}".format(
            self.vpmem_device, self.mount_point
        ))
        self.console.run_command(
            "mkdir -p {}".format(self.mount_point),
            timeout=30
        )
        self.console.run_command(
            "umount {} 2>/dev/null || true".format(self.mount_point),
            timeout=30
        )
        cmd = "mount -o dax {} {}".format(self.vpmem_device, self.mount_point)
        output = self.console.run_command(cmd, timeout=60)
        log.info("Mount output: {}".format(output))
        output = self.console.run_command("mount | grep pmem", timeout=30)
        log.info("Mount verification: {}".format(output))
        if self.mount_point not in str(output):
            self.fail("Failed to verify mount point")

    def create_test_file(self):
        """
        Step 5: Create a test file with unique content on vpmem
        """
        log.info("Step 5: Creating test file on vpmem")
        test_file_path = "{}/{}".format(self.mount_point, self.test_file)
        cmd = "echo '{}' > {}".format(self.test_content, test_file_path)
        self.console.run_command(cmd, timeout=30)
        for i in range(10):
            cmd = "echo 'Line {}: {}' >> {}".format(
                i, self.test_content, test_file_path
            )
            self.console.run_command(cmd, timeout=30)
        output = self.console.run_command("cat {}".format(test_file_path), timeout=30)
        log.info("Test file content: {}".format(output))
        output = self.console.run_command(
            "md5sum {}".format(test_file_path),
            timeout=30
        )
        self.original_checksum = output[0].split()[0]
        log.info("Original file checksum: {}".format(self.original_checksum))
        self.console.run_command("sync", timeout=30)
        output = self.console.run_command("ls -lh {}".format(test_file_path), timeout=30)
        log.info("Test file details: {}".format(output))

    def reboot_system(self):
        """
        Step 6: Reboot the system
        """
        log.info("Step 6: Rebooting the system")
        self.console.run_command(
            "umount {} 2>/dev/null || true".format(self.mount_point),
            timeout=30
        )
        log.info("Attempted to unmount vpmem device before reboot")
        log.info("Initiating system shutdown and Activate...")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        time.sleep(10)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.info("System booted successfully")
        self.console = self.cv_SYSTEM.console
        time.sleep(30)

    def verify_data_persistency(self):
        """
        Step 7 & 8: Remount vpmem and verify test file exists with correct content
        """
        log.info("Step 7: Remounting vpmem device after reboot")
        output = self.console.run_command("ls -l /dev/pmem*", timeout=30)
        log.info("PMEM devices after reboot: {}".format(output))
        self.mount_vpmem()
        log.info("Step 8: Verifying test file persistency")
        test_file_path = "{}/{}".format(self.mount_point, self.test_file)
        output = self.console.run_command("ls -lh {}".format(test_file_path), timeout=30)
        log.info("Test file exists after reboot: {}".format(output))
        output = self.console.run_command("cat {}".format(test_file_path), timeout=30)
        log.info("Test file content after reboot: {}".format(output))
        if self.test_content not in str(output):
            self.fail("Test file content does not match original content")
        output = self.console.run_command(
            "md5sum {}".format(test_file_path),
            timeout=30
        )
        new_checksum = output[0].split()[0]
        log.info("New file checksum: {}".format(new_checksum))
        if self.original_checksum != new_checksum:
            self.fail(
                "Checksum mismatch! Original: {}, New: {}".format(
                    self.original_checksum, new_checksum
                )
            )
        log.info("SUCCESS: Data persisted correctly across reboot!")

    def cleanup(self):
        """
        Clean up test artifacts
        """
        log.info("Cleaning up test environment")
        test_file_path = "{}/{}".format(self.mount_point, self.test_file)
        self.console.run_command("rm -f {}".format(test_file_path), timeout=30)
        self.console.run_command(
            "umount {} 2>/dev/null || true".format(self.mount_point),
            timeout=30
        )
        log.info("Cleanup completed")


class VpmemPersistencyTest(OpTestVpmemPersistency, unittest.TestCase):
    '''
    Main test class for vpmem data persistency with configurable filesystem
    Supports both XFS and ext4 filesystems
    '''

    def __init__(self, methodName='runTest', filesystem_type='xfs'):
        """
        Initialize test with specified filesystem type

        Args:
            methodName: Test method name (default: 'runTest')
            filesystem_type: Filesystem type - 'xfs' or 'ext4' (default: 'xfs')
        """
        super(VpmemPersistencyTest, self).__init__(methodName)
        self.filesystem_type = filesystem_type

    def runTest(self):
        """
        Execute the complete vpmem persistency test with reboot
        """
        log.info("Starting vpmem persistency test with {} filesystem".format(
            self.filesystem_type
        ))
        self.check_vpmem_device()
        self.create_namespace()
        self.create_filesystem()
        self.mount_vpmem()
        self.create_test_file()
        self.reboot_system()
        self.verify_data_persistency()
        self.cleanup()
        log.info("Vpmem persistency test with {} completed successfully".format(
            self.filesystem_type
        ))


class VpmemPersistencyXfsTest(VpmemPersistencyTest):
    '''
    Vpmem persistency test with XFS filesystem
    Usage: --run testcases.OpTestVpmemPersistency.VpmemPersistencyXfsTest
    '''
    def __init__(self, methodName='runTest'):
        super(VpmemPersistencyXfsTest, self).__init__(methodName, filesystem_type='xfs')


class VpmemPersistencyExt4Test(VpmemPersistencyTest):
    '''
    Vpmem persistency test with ext4 filesystem
    Usage: --run testcases.OpTestVpmemPersistency.VpmemPersistencyExt4Test
    '''
    def __init__(self, methodName='runTest'):
        super(VpmemPersistencyExt4Test, self).__init__(methodName, filesystem_type='ext4')


def vpmem_suite():
    '''
    Test suite for vpmem persistency tests with reboot
    Tests both XFS and ext4 filesystems

    Usage: --run-suite vpmem_suite
    '''
    suite = unittest.TestSuite()
    suite.addTest(VpmemPersistencyTest('runTest', filesystem_type='xfs'))
    suite.addTest(VpmemPersistencyTest('runTest', filesystem_type='ext4'))
    return suite
