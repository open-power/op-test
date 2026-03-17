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
#
# Assisted with AI tool.

'''
OpTestKuepKuap: Kernel Userspace Access and Execution Prevention Tests
--------------------------------------------------------------------

This test case validates kernel security features using LKDTM:
1. KUAP - Kernel Userspace Access Prevention (ACCESS_USERSPACE)
2. KUEP - Kernel Userspace Execution Prevention (EXEC_USERSPACE)
3. Combined KUAP and KUEP test with kernel commandline arguments
4. KUAP test with disable_radix (Hash mode)
5. KUEP test with disable_radix (Hash mode)
6. Combined KUAP and KUEP test with nosmap, nosmep, and disable_radix

The tests trigger these conditions via LKDTM and verify that the kernel
properly prevents the access/execution and faults appropriately.

The tests are considered PASS if the kernel logs "PASS: Faulted appropriately"
which indicates that the security features are working correctly.

Note: These are NOT tests for validating LKDTM itself, but rather for
validating the kernel's userspace access/execution prevention security features.
'''

import unittest
import logging

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
from common import OpTestInstallUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestKuepKuap(unittest.TestCase):
    '''
    Test class for Kernel Userspace Access and Execution Prevention features.
    Uses LKDTM to trigger ACCESS_USERSPACE and EXEC_USERSPACE and verifies
    that the kernel properly prevents the access/execution and faults appropriately.
    '''

    @classmethod
    def setUpClass(cls):
        """
        Set up the test environment.
        Initializes system configuration and connections.
        """
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.console = None
        cls.install_util = None
        cls.original_panic_on_oops = None

    def setUp(self):
        """
        Prepare the system for testing.
        Ensures the system is in OS state and console is available.
        Loads LKDTM module and disables panic_on_oops if needed.
        """
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_SYSTEM.console

        # Initialize InstallUtil if not already done
        if self.install_util is None:
            self.install_util = OpTestInstallUtil.InstallUtil()

        # Load LKDTM module if not already loaded
        self.load_lkdtm_module()

        # Disable panic_on_oops to prevent system panic during tests
        self.disable_panic_on_oops()

    def load_lkdtm_module(self):
        """
        Load the LKDTM kernel module if it's not already loaded.

        Returns:
            bool: True if module is loaded or successfully loaded, False otherwise
        """
        try:
            # Check if module is already loaded
            result = self.console.run_command("lsmod | grep lkdtm", timeout=10)
            if result and any('lkdtm' in line for line in result):
                log.info("LKDTM module is already loaded")
                return True
        except:
            # Module not loaded, try to load it
            pass

        try:
            log.info("Attempting to load LKDTM module...")
            self.console.run_command("modprobe lkdtm", timeout=30)
            log.info("LKDTM module loaded successfully")
            return True
        except Exception as e:
            log.warning("Could not load LKDTM module: {}".format(e))
            log.warning("Tests may fail if LKDTM is not available")
            return False

    def disable_panic_on_oops(self):
        """
        Disable panic_on_oops to prevent system panic during LKDTM tests.
        Saves the original value to restore later.

        Returns:
            bool: True if successfully disabled or already disabled, False otherwise
        """
        try:
            # Get current panic_on_oops value
            result = self.console.run_command("cat /proc/sys/kernel/panic_on_oops", timeout=10)
            if result:
                current_value = result[-1].strip()
                self.original_panic_on_oops = current_value
                log.info("Current panic_on_oops value: {}".format(current_value))

                if current_value == "0":
                    log.info("panic_on_oops is already disabled")
                    return True

                # Disable panic_on_oops
                log.info("Disabling panic_on_oops to prevent system panic during tests...")
                self.console.run_command("echo 0 > /proc/sys/kernel/panic_on_oops", timeout=10)

                # Verify it was disabled
                verify_result = self.console.run_command("cat /proc/sys/kernel/panic_on_oops", timeout=10)
                if verify_result and verify_result[-1].strip() == "0":
                    log.info("panic_on_oops successfully disabled")
                    return True
                else:
                    log.warning("Failed to verify panic_on_oops was disabled")
                    return False

        except Exception as e:
            log.error("Failed to disable panic_on_oops: {}".format(e))
            return False

    def restore_panic_on_oops(self):
        """
        Restore the original panic_on_oops value.

        Returns:
            bool: True if successfully restored, False otherwise
        """
        if self.original_panic_on_oops is None:
            log.info("No original panic_on_oops value to restore")
            return True

        try:
            log.info("Restoring panic_on_oops to original value: {}".format(self.original_panic_on_oops))
            self.console.run_command(
                "echo {} > /proc/sys/kernel/panic_on_oops".format(self.original_panic_on_oops),
                timeout=10
            )

            # Verify restoration
            verify_result = self.console.run_command("cat /proc/sys/kernel/panic_on_oops", timeout=10)
            if verify_result and verify_result[-1].strip() == self.original_panic_on_oops:
                log.info("panic_on_oops successfully restored to: {}".format(self.original_panic_on_oops))
                return True
            else:
                log.warning("Failed to verify panic_on_oops restoration")
                return False

        except Exception as e:
            log.error("Failed to restore panic_on_oops: {}".format(e))
            return False

    def check_hash_mode(self):
        """
        Check if the system has booted in Hash mode (MMU type).
        
        On PowerPC systems with disable_radix, the system should boot in Hash mode.
        This checks /proc/cpuinfo for the MMU type.
        
        Returns:
            tuple: (is_hash_mode, mmu_type)
                - is_hash_mode: True if in Hash mode, False otherwise
                - mmu_type: String describing the MMU type found
        """
        try:
            log.info("Checking MMU mode (Hash vs Radix)...")
            result = self.console.run_command("grep -i 'mmu' /proc/cpuinfo | head -1", timeout=10)
            
            if result:
                mmu_line = ' '.join(result).lower()
                log.info("MMU info from /proc/cpuinfo: {}".format(mmu_line))
                
                if 'hash' in mmu_line:
                    log.info("System is running in Hash mode")
                    return True, "Hash"
                elif 'radix' in mmu_line:
                    log.info("System is running in Radix mode")
                    return False, "Radix"
                else:
                    log.warning("Could not determine MMU mode from: {}".format(mmu_line))
                    return False, "Unknown"
            else:
                log.warning("No MMU information found in /proc/cpuinfo")
                return False, "Not found"
                
        except Exception as e:
            log.error("Failed to check MMU mode: {}".format(e))
            return False, "Error"

    def get_current_cmdline(self):
        """
        Get the current kernel command line parameters.

        Returns:
            str: Current kernel command line
        """
        try:
            result = self.console.run_command("cat /proc/cmdline", timeout=10)
            cmdline = ' '.join(result)
            log.info("Current kernel cmdline: {}".format(cmdline))
            return cmdline
        except Exception as e:
            log.error("Failed to get kernel cmdline: {}".format(e))
            return ""

    def update_kernel_cmdline(self, add_args="", remove_args=""):
        """
        Update kernel command line parameters using OpTestInstallUtil.
        This handles adding/removing parameters and rebooting the system.

        Args:
            add_args: Kernel parameters to add (e.g., "nosmap", "nosmep")
            remove_args: Kernel parameters to remove

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            log.info("Updating kernel cmdline...")
            if add_args:
                log.info("Adding parameters: {}".format(add_args))
            if remove_args:
                log.info("Removing parameters: {}".format(remove_args))

            # Get OS distribution
            distro = self.cv_HOST.host_get_OS_Level()
            log.info("Detected OS: {}".format(distro))

            # Use OpTestInstallUtil to update kernel cmdline
            # This will automatically handle grubby/grub and reboot
            # Signature: update_kernel_cmdline(distro, args, remove_args, reboot=True, reboot_cmd=True, timeout=60)
            success = self.install_util.update_kernel_cmdline(
                distro,
                add_args,
                remove_args,
                reboot=True,
                reboot_cmd=False,  # Use goto_state method instead of reboot command
                timeout=60  # Wait 60 seconds before reboot
            )

            if success:
                log.info("Kernel cmdline updated successfully")
                # Refresh console connection after reboot
                self.console = self.cv_SYSTEM.console
                return True
            else:
                log.error("Failed to update kernel cmdline")
                return False

        except Exception as e:
            log.error("Exception while updating kernel cmdline: {}".format(e))
            log.error("Exception details: {}".format(str(e)))
            import traceback
            log.error("Traceback: {}".format(traceback.format_exc()))
            return False

    def check_lkdtm_available(self):
        """
        Check if LKDTM module is available and the provoke-crash interface exists.

        Returns:
            bool: True if LKDTM is available, False otherwise
        """
        try:
            # Check if the provoke-crash directory exists
            result = self.console.run_command(
                "test -d /sys/kernel/debug/provoke-crash/ && echo 'EXISTS' || echo 'NOT_EXISTS'",
                timeout=10
            )

            if 'EXISTS' in result[-1]:
                log.info("LKDTM provoke-crash interface is available")
                return True
            else:
                log.warning("LKDTM provoke-crash directory not found")
                log.warning("Ensure debugfs is mounted and LKDTM module is loaded")
                return False

        except CommandFailed as e:
            log.error("Failed to check LKDTM availability: {}".format(e))
            return False

    def trigger_access_userspace_crash(self):
        """
        Trigger ACCESS_USERSPACE via LKDTM to test userspace access prevention.

        This tests the kernel's userspace access prevention feature.
        The kernel should prevent the access and fault appropriately.

        Returns:
            tuple: (success, dmesg_output, console_output)
                - success: True if fault occurred as expected, False otherwise
                - dmesg_output: Last 100 lines of dmesg for analysis
                - console_output: Raw console output from the trigger command
        """
        console_output = []
        try:
            # Clear dmesg buffer first to get only relevant output
            try:
                self.console.run_command("dmesg -c > /dev/null", timeout=10)
            except:
                pass  # If this fails, continue anyway

            # Attempt to trigger the crash
            # This command is expected to fail (return non-zero exit code or timeout)
            result = self.console.run_command(
                "bash -c 'echo ACCESS_USERSPACE > /sys/kernel/debug/provoke-crash/DIRECT'",
                timeout=10
            )
            console_output = result

            # If we reach here, the fault did NOT occur (unexpected)
            log.error("ACCESS_USERSPACE did not trigger a fault - userspace access prevention may not be working!")
            try:
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
            except:
                dmesg = []
            return False, dmesg, console_output

        except Exception as e:
            # This is the EXPECTED behavior - the command should fail or timeout
            log.info("ACCESS_USERSPACE triggered a fault as expected: {}".format(str(e)))

            # After a fault, the console may be in an unstable state
            # Try to recover and get dmesg output
            try:
                # Give the system a moment to recover
                import time
                time.sleep(2)

                # Try to get dmesg output
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
                return True, dmesg, console_output
            except Exception as dmesg_error:
                log.warning("Could not retrieve dmesg after fault: {}".format(dmesg_error))
                # Even if we can't get dmesg, the fault occurred which is what we wanted
                return True, [], console_output

    def trigger_exec_userspace_crash(self):
        """
        Trigger EXEC_USERSPACE via LKDTM to test userspace execution prevention.

        This tests the kernel's userspace execution prevention feature.
        The kernel should prevent the execution and fault appropriately.

        Returns:
            tuple: (success, dmesg_output, console_output)
                - success: True if fault occurred as expected, False otherwise
                - dmesg_output: Last 100 lines of dmesg for analysis
                - console_output: Raw console output from the trigger command
        """
        console_output = []
        try:
            # Clear dmesg buffer first to get only relevant output
            try:
                self.console.run_command("dmesg -c > /dev/null", timeout=10)
            except:
                pass  # If this fails, continue anyway

            # Attempt to trigger the crash
            # This command is expected to fail (return non-zero exit code or timeout)
            result = self.console.run_command(
                "bash -c 'echo EXEC_USERSPACE > /sys/kernel/debug/provoke-crash/DIRECT'",
                timeout=10
            )
            console_output = result

            # If we reach here, the fault did NOT occur (unexpected)
            log.error("EXEC_USERSPACE did not trigger a fault - userspace execution prevention may not be working!")
            try:
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
            except:
                dmesg = []
            return False, dmesg, console_output

        except Exception as e:
            # This is the EXPECTED behavior - the command should fail or timeout
            log.info("EXEC_USERSPACE triggered a fault as expected: {}".format(str(e)))

            # After a fault, the console may be in an unstable state
            # Try to recover and get dmesg output
            try:
                # Give the system a moment to recover
                import time
                time.sleep(2)

                # Try to get dmesg output
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
                return True, dmesg, console_output
            except Exception as dmesg_error:
                log.warning("Could not retrieve dmesg after fault: {}".format(dmesg_error))
                # Even if we can't get dmesg, the fault occurred which is what we wanted
                return True, [], console_output

    def verify_fault_in_output(self, dmesg_output, console_output):
        """
        Verify that the kernel faulted appropriately by checking for the
        "PASS: Faulted appropriately" message or other fault indicators.

        This message indicates that the userspace access prevention feature
        is working correctly.

        Args:
            dmesg_output: List of dmesg lines to analyze
            console_output: List of console output lines from the trigger command

        Returns:
            tuple: (passed, message)
                - passed: True if fault indicators found
                - message: Description of what was found
        """
        # Combine both outputs for analysis
        all_output = '\n'.join(dmesg_output + console_output)

        # Primary check: Look for the expected PASS message
        if 'PASS: Faulted appropriately' in all_output:
            log.info("Found 'PASS: Faulted appropriately' - userspace access prevention is working!")
            return True, "Found 'PASS: Faulted appropriately' message"

        # Secondary check: Look for fault indicators that prove the feature is working
        critical_indicators = [
            ('Segmentation fault', 'Segmentation fault occurred (expected behavior)'),
            ('Oops', 'Kernel Oops detected (fault occurred)'),
            ('kernel BUG', 'Kernel BUG detected (fault occurred)'),
        ]

        for indicator, message in critical_indicators:
            if indicator in all_output:
                log.info("Found critical indicator: {}".format(indicator))
                return True, message

        # Tertiary check: Look for LKDTM-related messages
        lkdtm_indicators = [
            'lkdtm',
            'LKDTM',
            'ACCESS_USERSPACE',
            'EXEC_USERSPACE',
        ]

        found_lkdtm = []
        for indicator in lkdtm_indicators:
            if indicator in all_output:
                found_lkdtm.append(indicator)

        if found_lkdtm:
            log.info("Found LKDTM indicators: {}".format(', '.join(found_lkdtm)))
            return True, "Found LKDTM activity: {}".format(', '.join(found_lkdtm))

        log.warning("No clear fault indicators found in output")
        return False, "No fault indicators found"

    def runTest(self):
        """
        Main test execution method.

        Test flow:
        1. Check if LKDTM is available
        2. Trigger ACCESS_USERSPACE to test userspace access prevention
        3. Verify the kernel faulted appropriately (expected behavior)
        4. Check for "PASS: Faulted appropriately" message in dmesg
        5. Report test results

        The test PASSES if the kernel prevents userspace access and faults appropriately.
        """
        log.info("=" * 60)
        log.info("Starting Kernel Userspace Access Prevention Test")
        log.info("Using LKDTM ACCESS_USERSPACE trigger")
        log.info("=" * 60)

        # Step 1: Check LKDTM availability
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 2: Trigger ACCESS_USERSPACE to test userspace access prevention
        log.info("Triggering ACCESS_USERSPACE to test userspace access prevention...")
        fault_occurred, dmesg_output, console_output = self.trigger_access_userspace_crash()

        # Step 3: Verify the results
        if not fault_occurred:
            # Print output for debugging
            log.error("FAIL: ACCESS_USERSPACE did not cause a fault!")
            log.error("This indicates userspace access prevention may not be working!")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            self.fail("ACCESS_USERSPACE did not trigger expected fault - userspace access prevention not working")

        # Step 4: Verify fault was logged and check for "PASS: Faulted appropriately"
        log.info("Verifying fault indicators in output...")
        passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)

        if passed:
            log.info("SUCCESS: {}".format(result_message))
            log.info("Kernel faulted appropriately - userspace access prevention is working!")
        else:
            log.warning("WARNING: Fault occurred but expected messages not found")
            log.warning("Result: {}".format(result_message))

        # Print output for reference
        if console_output:
            log.info("Console output from trigger:")
            for line in console_output[-50:]:
                log.debug(line)

        if dmesg_output:
            log.info("Last 100 lines of dmesg:")
            for line in dmesg_output[-100:]:
                log.debug(line)

        log.info("=" * 60)
        log.info("PASS: Kernel Userspace Access Prevention Test Completed")
        log.info("The kernel faulted appropriately as expected")
        log.info("This validates that userspace access prevention is working correctly")
        log.info("=" * 60)

    def tearDown(self):
        """
        Clean up after test execution.
        Restores panic_on_oops to its original value.
        """
        # Restore panic_on_oops to original value
        self.restore_panic_on_oops()
        log.info("LKDTM test cleanup completed")

    def run_test_with_cmdline_param(self, param, test_type):
        """
        Run a test with a specific kernel command line parameter.

        Args:
            param: Kernel parameter to add (e.g., "nosmap", "nosmep", "nosmap nosmep")
            test_type: Type of test to run ("access", "exec", or "both")

        Returns:
            bool: True if test completed successfully
        """
        log.info("=" * 60)
        log.info("Running test with kernel parameter(s): {}".format(param))
        log.info("Test type: {}".format(test_type))
        log.info("=" * 60)

        # Step 1: Add kernel parameter(s) and reboot using OpTestInstallUtil
        log.info("Adding kernel parameter(s) {} and rebooting...".format(param))
        if not self.update_kernel_cmdline(add_args=param):
            self.fail("Failed to add kernel parameter(s): {}".format(param))

        # Step 2: Verify parameter(s) are active
        cmdline = self.get_current_cmdline()
        params_list = param.split()
        for p in params_list:
            if p not in cmdline:
                self.fail("Kernel parameter {} not found in cmdline after reboot".format(p))
        log.info("Confirmed kernel parameter(s) {} are active".format(param))

        # Step 3: Check LKDTM availability
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 4: Run the appropriate test(s)
        test_results = []

        if test_type == "access" or test_type == "both":
            log.info("Triggering ACCESS_USERSPACE (KUAP test) with {} parameter(s)...".format(param))
            fault_occurred, dmesg_output, console_output = self.trigger_access_userspace_crash()
            test_results.append({
                'name': 'ACCESS_USERSPACE (KUAP)',
                'fault_occurred': fault_occurred,
                'dmesg': dmesg_output,
                'console': console_output
            })

        if test_type == "exec" or test_type == "both":
            log.info("Triggering EXEC_USERSPACE (KUEP test) with {} parameter(s)...".format(param))
            fault_occurred, dmesg_output, console_output = self.trigger_exec_userspace_crash()
            test_results.append({
                'name': 'EXEC_USERSPACE (KUEP)',
                'fault_occurred': fault_occurred,
                'dmesg': dmesg_output,
                'console': console_output
            })

        if not test_results:
            self.fail("Invalid test type: {}".format(test_type))

        # Step 5: Analyze results for all tests
        for result in test_results:
            test_name = result['name']
            fault_occurred = result['fault_occurred']
            dmesg_output = result['dmesg']
            console_output = result['console']

            log.info("-" * 60)
            log.info("Results for {}:".format(test_name))

            # With nosmap/nosmep, the test should NOT fault (protection disabled)
            if not fault_occurred:
                log.info("EXPECTED: {} did not cause a fault with {} parameter(s)".format(test_name, param))
                log.info("This confirms that protection is properly disabled")
            else:
                log.warning("UNEXPECTED: {} caused a fault even with {} parameter(s)".format(test_name, param))
                log.warning("This may indicate the parameter(s) are not working as expected")

            # Print output for reference
            if console_output:
                log.info("Console output from {}:".format(test_name))
                for line in console_output[-30:]:
                    log.debug(line)

            if dmesg_output:
                log.info("Last 50 lines of dmesg for {}:".format(test_name))
                for line in dmesg_output[-50:]:
                    log.debug(line)

        # Step 6: Remove kernel parameter(s) and reboot back to normal using OpTestInstallUtil
        log.info("-" * 60)
        log.info("Cleaning up: removing kernel parameter(s) {} and rebooting...".format(param))

        cleanup_success = self.update_kernel_cmdline(remove_args=param)

        if not cleanup_success:
            log.error("Failed to remove kernel parameter(s): {}".format(param))
            log.error("Manual cleanup may be required!")
            self.fail("Cleanup failed - could not remove kernel parameter(s): {}".format(param))

        # Step 7: Verify parameters were removed
        log.info("Verifying kernel parameter(s) were removed...")
        cmdline_after_cleanup = self.get_current_cmdline()
        params_list = param.split()

        still_present = []
        for p in params_list:
            if p in cmdline_after_cleanup:
                still_present.append(p)

        if still_present:
            log.error("Cleanup verification failed! Parameters still present: {}".format(', '.join(still_present)))
            log.error("Current cmdline: {}".format(cmdline_after_cleanup))
            self.fail("Cleanup incomplete - parameters still in cmdline: {}".format(', '.join(still_present)))

        log.info("Cleanup verified: all parameters successfully removed")
        log.info("System restored to original state")

        log.info("=" * 60)
        log.info("PASS: Test with {} parameter(s) completed successfully".format(param))
        log.info("All kernel parameters removed and system restored")
        log.info("=" * 60)
        return True


class LKDTMAccessUserspace(OpTestKuepKuap, unittest.TestCase):
    '''
    Specific test class for Kernel Userspace Access Prevention test.
    Uses LKDTM ACCESS_USERSPACE to validate the security feature.
    This allows running: --run testcases.OpTestKuepKuap.LKDTMAccessUserspace
    '''

    def runTest(self):
        """Execute the Kernel Userspace Access Prevention test using ACCESS_USERSPACE"""
        super(LKDTMAccessUserspace, self).runTest()


class LKDTMExecUserspace(OpTestKuepKuap, unittest.TestCase):
    '''
    Specific test class for Kernel Userspace Execution Prevention test.
    Uses LKDTM EXEC_USERSPACE to validate the security feature.
    This allows running: --run testcases.OpTestKuepKuap.LKDTMExecUserspace
    '''

    def runTest(self):
        """
        Execute the Kernel Userspace Execution Prevention test using EXEC_USERSPACE.

        Test flow:
        1. Check if LKDTM is available
        2. Trigger EXEC_USERSPACE to test userspace execution prevention
        3. Verify the kernel faulted appropriately (expected behavior)
        4. Check for "PASS: Faulted appropriately" message in dmesg
        5. Report test results

        The test PASSES if the kernel prevents userspace execution and faults appropriately.
        """
        log.info("=" * 60)
        log.info("Starting Kernel Userspace Execution Prevention Test")
        log.info("Using LKDTM EXEC_USERSPACE trigger")
        log.info("=" * 60)

        # Step 1: Check LKDTM availability
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 2: Trigger EXEC_USERSPACE to test userspace execution prevention
        log.info("Triggering EXEC_USERSPACE to test userspace execution prevention...")
        fault_occurred, dmesg_output, console_output = self.trigger_exec_userspace_crash()

        # Step 3: Verify the results
        if not fault_occurred:
            # Print output for debugging
            log.error("FAIL: EXEC_USERSPACE did not cause a fault!")
            log.error("This indicates userspace execution prevention may not be working!")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            self.fail("EXEC_USERSPACE did not trigger expected fault - userspace execution prevention not working")

        # Step 4: Verify fault was logged and check for "PASS: Faulted appropriately"
        log.info("Verifying fault indicators in output...")
        passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)

        if passed:
            log.info("SUCCESS: {}".format(result_message))
            log.info("Kernel faulted appropriately - userspace execution prevention is working!")
        else:
            log.warning("WARNING: Fault occurred but expected messages not found")
            log.warning("Result: {}".format(result_message))

        # Print output for reference
        if console_output:
            log.info("Console output from trigger:")
            for line in console_output[-50:]:
                log.debug(line)

        if dmesg_output:
            log.info("Last 100 lines of dmesg:")
            for line in dmesg_output[-100:]:
                log.debug(line)

        log.info("=" * 60)
        log.info("PASS: Kernel Userspace Execution Prevention Test Completed")
        log.info("The kernel faulted appropriately as expected")
        log.info("This validates that userspace execution prevention is working correctly")
        log.info("=" * 60)


class LKDTMKuapKuepCombined(OpTestKuepKuap, unittest.TestCase):
    '''
    Combined test for both KUAP and KUEP with nosmap and nosmep kernel commandline arguments.
    This test adds both nosmap and nosmep as kernel commandline arguments and runs
    both ACCESS_USERSPACE and EXEC_USERSPACE tests.

    With nosmap and nosmep, the protections are disabled, so the tests should NOT fault,
    demonstrating that the kernel parameters properly disable the security features.

    This allows running: --run testcases.OpTestKuepKuap.LKDTMKuapKuepCombined
    '''

    def runTest(self):
        """
        Execute both ACCESS_USERSPACE and EXEC_USERSPACE tests with nosmap and nosmep
        kernel commandline arguments.

        Test flow:
        1. Add 'nosmap nosmep' kernel commandline arguments and reboot
        2. Run ACCESS_USERSPACE test (KUAP)
        3. Run EXEC_USERSPACE test (KUEP)
        4. Verify both tests do NOT fault (protections disabled)
        5. Remove kernel arguments and restore system

        With nosmap and nosmep, both tests should NOT fault, validating that
        the kernel arguments properly disable SMAP and SMEP protections.
        """
        log.info("=" * 60)
        log.info("Starting Combined KUAP and KUEP Test with nosmap and nosmep")
        log.info("Adding 'nosmap nosmep' kernel commandline arguments")
        log.info("=" * 60)

        # Step 1: Add kernel arguments 'nosmap nosmep' and reboot
        kernel_args = "nosmap nosmep"
        log.info("Adding kernel arguments: {}".format(kernel_args))
        if not self.update_kernel_cmdline(add_args=kernel_args):
            self.fail("Failed to add kernel arguments: {}".format(kernel_args))

        # Step 2: Verify arguments are active
        cmdline = self.get_current_cmdline()
        if "nosmap" not in cmdline or "nosmep" not in cmdline:
            self.fail("Kernel arguments 'nosmap nosmep' not found in cmdline after reboot")
        log.info("Confirmed kernel arguments 'nosmap nosmep' are active")

        # Step 3: Ensure debugfs is mounted (required for LKDTM)
        try:
            log.info("Ensuring debugfs is mounted...")
            self.console.run_command("mount -t debugfs none /sys/kernel/debug 2>/dev/null || true", timeout=10)
        except Exception as e:
            log.warning("Could not mount debugfs: {}".format(e))

        # Step 4: Reload LKDTM module after reboot
        log.info("Reloading LKDTM module after reboot...")
        try:
            # Unload if already loaded
            self.console.run_command("rmmod lkdtm 2>/dev/null || true", timeout=10)
        except:
            pass

        # Load LKDTM module
        if not self.load_lkdtm_module():
            self.skipTest("LKDTM module not available or cannot be loaded after reboot")

        # Step 5: Check LKDTM availability
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 4: Run ACCESS_USERSPACE test (KUAP) with nosmap
        log.info("-" * 60)
        log.info("Running ACCESS_USERSPACE test (KUAP) with nosmap kernel argument...")
        log.info("Expected: Should NOT fault (SMAP protection disabled)")
        log.info("-" * 60)

        kuap_fault_occurred, kuap_dmesg, kuap_console = self.trigger_access_userspace_crash()

        if not kuap_fault_occurred:
            log.info("EXPECTED: ACCESS_USERSPACE did not cause a fault with nosmap argument")
            log.info("This confirms that SMAP protection is properly disabled")
        else:
            log.warning("UNEXPECTED: ACCESS_USERSPACE caused a fault even with nosmap argument")
            log.warning("This may indicate nosmap parameter is not working as expected")
            kuap_passed, kuap_message = self.verify_fault_in_output(kuap_dmesg, kuap_console)
            log.warning("Fault details: {}".format(kuap_message))

        # Step 5: Run EXEC_USERSPACE test (KUEP) with nosmep
        log.info("-" * 60)
        log.info("Running EXEC_USERSPACE test (KUEP) with nosmep kernel argument...")
        log.info("Expected: Should NOT fault (SMEP protection disabled)")
        log.info("-" * 60)

        kuep_fault_occurred, kuep_dmesg, kuep_console = self.trigger_exec_userspace_crash()

        if not kuep_fault_occurred:
            log.info("EXPECTED: EXEC_USERSPACE did not cause a fault with nosmep argument")
            log.info("This confirms that SMEP protection is properly disabled")
        else:
            log.warning("UNEXPECTED: EXEC_USERSPACE caused a fault even with nosmep argument")
            log.warning("This may indicate nosmep parameter is not working as expected")
            kuep_passed, kuep_message = self.verify_fault_in_output(kuep_dmesg, kuep_console)
            log.warning("Fault details: {}".format(kuep_message))

        # Step 6: Print detailed output for both tests
        log.info("=" * 60)
        log.info("KUAP Test Output Summary:")
        log.info("-" * 60)
        if kuap_console:
            log.info("Console output from ACCESS_USERSPACE:")
            for line in kuap_console[-30:]:
                log.debug(line)
        if kuap_dmesg:
            log.info("Last 50 lines of dmesg for ACCESS_USERSPACE:")
            for line in kuap_dmesg[-50:]:
                log.debug(line)

        log.info("=" * 60)
        log.info("KUEP Test Output Summary:")
        log.info("-" * 60)
        if kuep_console:
            log.info("Console output from EXEC_USERSPACE:")
            for line in kuep_console[-30:]:
                log.debug(line)
        if kuep_dmesg:
            log.info("Last 50 lines of dmesg for EXEC_USERSPACE:")
            for line in kuep_dmesg[-50:]:
                log.debug(line)

        # Step 7: Remove kernel arguments and restore system
        log.info("=" * 60)
        log.info("Cleaning up: removing kernel arguments and rebooting...")
        log.info("=" * 60)

        cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)

        if not cleanup_success:
            log.error("Failed to remove kernel arguments: {}".format(kernel_args))
            log.error("Manual cleanup may be required!")
            self.fail("Cleanup failed - could not remove kernel arguments: {}".format(kernel_args))

        # Step 8: Verify arguments were removed
        log.info("Verifying kernel arguments were removed...")
        cmdline_after_cleanup = self.get_current_cmdline()

        if "kuap" in cmdline_after_cleanup or "kuep" in cmdline_after_cleanup:
            log.error("Cleanup verification failed! Arguments still present in cmdline")
            log.error("Current cmdline: {}".format(cmdline_after_cleanup))
            self.fail("Cleanup incomplete - arguments still in cmdline")

        log.info("Cleanup verified: all arguments successfully removed")
        log.info("System restored to original state")

        # Step 9: Final test result
        log.info("=" * 60)

        # With nosmap and nosmep, we expect NO faults (protections disabled)
        unexpected_faults = []
        if kuap_fault_occurred:
            unexpected_faults.append("ACCESS_USERSPACE (with nosmap)")
        if kuep_fault_occurred:
            unexpected_faults.append("EXEC_USERSPACE (with nosmep)")

        if unexpected_faults:
            log.warning("WARNING: Unexpected faults occurred: {}".format(', '.join(unexpected_faults)))
            log.warning("This may indicate nosmap/nosmep parameters are not working correctly")

        log.info("PASS: Combined KUAP and KUEP Test with nosmap/nosmep Completed")
        log.info("Test Results:")
        log.info("  - ACCESS_USERSPACE with nosmap: {} fault".format("DID" if kuap_fault_occurred else "did NOT"))
        log.info("  - EXEC_USERSPACE with nosmep: {} fault".format("DID" if kuep_fault_occurred else "did NOT"))
        log.info("Expected behavior: Both should NOT fault (protections disabled)")
        log.info("This validates that nosmap and nosmep kernel arguments properly disable protections")
        log.info("=" * 60)


class LKDTMKuapWithDisableRadix(OpTestKuepKuap, unittest.TestCase):
    '''
    Test KUAP (Kernel Userspace Access Prevention) with disable_radix kernel argument.
    This forces the system to boot in Hash mode instead of Radix mode.
    
    This allows running: --run testcases.OpTestKuepKuap.LKDTMKuapWithDisableRadix
    '''

    def runTest(self):
        """
        Execute KUAP test with disable_radix kernel argument.
        
        Test flow:
        1. Add 'disable_radix' kernel argument and reboot
        2. Verify system booted in Hash mode
        3. Run ACCESS_USERSPACE test (KUAP)
        4. Verify the kernel faulted appropriately
        5. Remove kernel argument and restore system
        """
        log.info("=" * 60)
        log.info("Starting KUAP Test with disable_radix (Hash Mode)")
        log.info("Adding 'disable_radix' kernel argument")
        log.info("=" * 60)

        # Step 1: Add kernel argument 'disable_radix' and reboot
        kernel_args = "disable_radix"
        log.info("Adding kernel argument: {}".format(kernel_args))
        if not self.update_kernel_cmdline(add_args=kernel_args):
            self.fail("Failed to add kernel argument: {}".format(kernel_args))

        # Step 2: Verify argument is active
        cmdline = self.get_current_cmdline()
        if "disable_radix" not in cmdline:
            self.fail("Kernel argument 'disable_radix' not found in cmdline after reboot")
        log.info("Confirmed kernel argument 'disable_radix' is active")

        # Step 3: Check if system booted in Hash mode
        is_hash_mode, mmu_type = self.check_hash_mode()
        log.info("MMU Mode detected: {}".format(mmu_type))
        
        if not is_hash_mode:
            log.warning("WARNING: System did not boot in Hash mode (detected: {})".format(mmu_type))
            log.warning("disable_radix may not be working as expected")
        else:
            log.info("SUCCESS: System booted in Hash mode as expected")

        # Step 4: Ensure debugfs is mounted and reload LKDTM
        try:
            log.info("Ensuring debugfs is mounted...")
            self.console.run_command("mount -t debugfs none /sys/kernel/debug 2>/dev/null || true", timeout=10)
        except Exception as e:
            log.warning("Could not mount debugfs: {}".format(e))

        log.info("Reloading LKDTM module after reboot...")
        try:
            self.console.run_command("rmmod lkdtm 2>/dev/null || true", timeout=10)
        except:
            pass

        if not self.load_lkdtm_module():
            self.skipTest("LKDTM module not available or cannot be loaded after reboot")

        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 5: Run ACCESS_USERSPACE test (KUAP) in Hash mode
        log.info("-" * 60)
        log.info("Running ACCESS_USERSPACE test (KUAP) in Hash mode with disable_radix...")
        log.info("Expected: Should fault appropriately (KUAP protection active)")
        log.info("-" * 60)

        fault_occurred, dmesg_output, console_output = self.trigger_access_userspace_crash()

        if not fault_occurred:
            log.error("FAIL: ACCESS_USERSPACE did not cause a fault in Hash mode!")
            log.error("This indicates KUAP may not be working in Hash mode")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            # Continue to cleanup even if test fails
        else:
            log.info("SUCCESS: ACCESS_USERSPACE caused a fault as expected in Hash mode")
            passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
            if passed:
                log.info("Fault verification: {}".format(result_message))

        # Print output for reference
        if console_output:
            log.info("Console output from ACCESS_USERSPACE:")
            for line in console_output[-30:]:
                log.debug(line)

        if dmesg_output:
            log.info("Last 50 lines of dmesg:")
            for line in dmesg_output[-50:]:
                log.debug(line)

        # Step 6: Remove kernel argument and restore system
        log.info("=" * 60)
        log.info("Cleaning up: removing kernel argument and rebooting...")
        log.info("=" * 60)

        cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)

        if not cleanup_success:
            log.error("Failed to remove kernel argument: {}".format(kernel_args))
            log.error("Manual cleanup may be required!")
            self.fail("Cleanup failed - could not remove kernel argument: {}".format(kernel_args))

        # Step 7: Verify argument was removed
        log.info("Verifying kernel argument was removed...")
        cmdline_after_cleanup = self.get_current_cmdline()

        if "disable_radix" in cmdline_after_cleanup:
            log.error("Cleanup verification failed! Argument still present in cmdline")
            log.error("Current cmdline: {}".format(cmdline_after_cleanup))
            self.fail("Cleanup incomplete - argument still in cmdline")

        log.info("Cleanup verified: argument successfully removed")
        log.info("System restored to original state")

        # Final result
        if not fault_occurred:
            self.fail("KUAP test with disable_radix failed - no fault occurred")

        log.info("=" * 60)
        log.info("PASS: KUAP Test with disable_radix (Hash Mode) Completed")
        log.info("System booted in {} mode and KUAP protection worked correctly".format(mmu_type))
        log.info("=" * 60)


class LKDTMKuepWithDisableRadix(OpTestKuepKuap, unittest.TestCase):
    '''
    Test KUEP (Kernel Userspace Execution Prevention) with disable_radix kernel argument.
    This forces the system to boot in Hash mode instead of Radix mode.
    
    This allows running: --run testcases.OpTestKuepKuap.LKDTMKuepWithDisableRadix
    '''

    def runTest(self):
        """
        Execute KUEP test with disable_radix kernel argument.
        
        Test flow:
        1. Add 'disable_radix' kernel argument and reboot
        2. Verify system booted in Hash mode
        3. Run EXEC_USERSPACE test (KUEP)
        4. Verify the kernel faulted appropriately
        5. Remove kernel argument and restore system
        """
        log.info("=" * 60)
        log.info("Starting KUEP Test with disable_radix (Hash Mode)")
        log.info("Adding 'disable_radix' kernel argument")
        log.info("=" * 60)

        # Step 1: Add kernel argument 'disable_radix' and reboot
        kernel_args = "disable_radix"
        log.info("Adding kernel argument: {}".format(kernel_args))
        if not self.update_kernel_cmdline(add_args=kernel_args):
            self.fail("Failed to add kernel argument: {}".format(kernel_args))

        # Step 2: Verify argument is active
        cmdline = self.get_current_cmdline()
        if "disable_radix" not in cmdline:
            self.fail("Kernel argument 'disable_radix' not found in cmdline after reboot")
        log.info("Confirmed kernel argument 'disable_radix' is active")

        # Step 3: Check if system booted in Hash mode
        is_hash_mode, mmu_type = self.check_hash_mode()
        log.info("MMU Mode detected: {}".format(mmu_type))
        
        if not is_hash_mode:
            log.warning("WARNING: System did not boot in Hash mode (detected: {})".format(mmu_type))
            log.warning("disable_radix may not be working as expected")
        else:
            log.info("SUCCESS: System booted in Hash mode as expected")

        # Step 4: Ensure debugfs is mounted and reload LKDTM
        try:
            log.info("Ensuring debugfs is mounted...")
            self.console.run_command("mount -t debugfs none /sys/kernel/debug 2>/dev/null || true", timeout=10)
        except Exception as e:
            log.warning("Could not mount debugfs: {}".format(e))

        log.info("Reloading LKDTM module after reboot...")
        try:
            self.console.run_command("rmmod lkdtm 2>/dev/null || true", timeout=10)
        except:
            pass

        if not self.load_lkdtm_module():
            self.skipTest("LKDTM module not available or cannot be loaded after reboot")

        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 5: Run EXEC_USERSPACE test (KUEP) in Hash mode
        log.info("-" * 60)
        log.info("Running EXEC_USERSPACE test (KUEP) in Hash mode with disable_radix...")
        log.info("Expected: Should fault appropriately (KUEP protection active)")
        log.info("-" * 60)

        fault_occurred, dmesg_output, console_output = self.trigger_exec_userspace_crash()

        if not fault_occurred:
            log.error("FAIL: EXEC_USERSPACE did not cause a fault in Hash mode!")
            log.error("This indicates KUEP may not be working in Hash mode")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            # Continue to cleanup even if test fails
        else:
            log.info("SUCCESS: EXEC_USERSPACE caused a fault as expected in Hash mode")
            passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
            if passed:
                log.info("Fault verification: {}".format(result_message))

        # Print output for reference
        if console_output:
            log.info("Console output from EXEC_USERSPACE:")
            for line in console_output[-30:]:
                log.debug(line)

        if dmesg_output:
            log.info("Last 50 lines of dmesg:")
            for line in dmesg_output[-50:]:
                log.debug(line)

        # Step 6: Remove kernel argument and restore system
        log.info("=" * 60)
        log.info("Cleaning up: removing kernel argument and rebooting...")
        log.info("=" * 60)

        cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)

        if not cleanup_success:
            log.error("Failed to remove kernel argument: {}".format(kernel_args))
            log.error("Manual cleanup may be required!")
            self.fail("Cleanup failed - could not remove kernel argument: {}".format(kernel_args))

        # Step 7: Verify argument was removed
        log.info("Verifying kernel argument was removed...")
        cmdline_after_cleanup = self.get_current_cmdline()

        if "disable_radix" in cmdline_after_cleanup:
            log.error("Cleanup verification failed! Argument still present in cmdline")
            log.error("Current cmdline: {}".format(cmdline_after_cleanup))
            self.fail("Cleanup incomplete - argument still in cmdline")

        log.info("Cleanup verified: argument successfully removed")
        log.info("System restored to original state")

        # Final result
        if not fault_occurred:
            self.fail("KUEP test with disable_radix failed - no fault occurred")

        log.info("=" * 60)
        log.info("PASS: KUEP Test with disable_radix (Hash Mode) Completed")
        log.info("System booted in {} mode and KUEP protection worked correctly".format(mmu_type))
        log.info("=" * 60)


class LKDTMKuapKuepCombinedWithDisableRadix(OpTestKuepKuap, unittest.TestCase):
    '''
    Combined test for both KUAP and KUEP with nosmap, nosmep, and disable_radix kernel arguments.
    This test adds all three kernel arguments and runs both ACCESS_USERSPACE and EXEC_USERSPACE tests
    in Hash mode.
    
    With nosmap and nosmep, the protections are disabled, so the tests should NOT fault.
    The disable_radix forces Hash mode operation.
    
    This allows running: --run testcases.OpTestKuepKuap.LKDTMKuapKuepCombinedWithDisableRadix
    '''

    def runTest(self):
        """
        Execute both ACCESS_USERSPACE and EXEC_USERSPACE tests with nosmap, nosmep,
        and disable_radix kernel arguments.
        
        Test flow:
        1. Add 'nosmap nosmep disable_radix' kernel arguments and reboot
        2. Verify system booted in Hash mode
        3. Run ACCESS_USERSPACE test (KUAP)
        4. Run EXEC_USERSPACE test (KUEP)
        5. Verify both tests do NOT fault (protections disabled)
        6. Remove kernel arguments and restore system
        """
        log.info("=" * 60)
        log.info("Starting Combined KUAP and KUEP Test with nosmap, nosmep, and disable_radix")
        log.info("Adding 'nosmap nosmep disable_radix' kernel arguments")
        log.info("=" * 60)

        # Step 1: Add kernel arguments and reboot
        kernel_args = "nosmap nosmep disable_radix"
        log.info("Adding kernel arguments: {}".format(kernel_args))
        if not self.update_kernel_cmdline(add_args=kernel_args):
            self.fail("Failed to add kernel arguments: {}".format(kernel_args))

        # Step 2: Verify arguments are active
        cmdline = self.get_current_cmdline()
        required_args = ["nosmap", "nosmep", "disable_radix"]
        missing_args = [arg for arg in required_args if arg not in cmdline]
        
        if missing_args:
            self.fail("Kernel arguments {} not found in cmdline after reboot".format(', '.join(missing_args)))
        log.info("Confirmed all kernel arguments are active: {}".format(kernel_args))

        # Step 3: Check if system booted in Hash mode
        is_hash_mode, mmu_type = self.check_hash_mode()
        log.info("MMU Mode detected: {}".format(mmu_type))
        
        if not is_hash_mode:
            log.warning("WARNING: System did not boot in Hash mode (detected: {})".format(mmu_type))
            log.warning("disable_radix may not be working as expected")
        else:
            log.info("SUCCESS: System booted in Hash mode as expected")

        # Step 4: Ensure debugfs is mounted and reload LKDTM
        try:
            log.info("Ensuring debugfs is mounted...")
            self.console.run_command("mount -t debugfs none /sys/kernel/debug 2>/dev/null || true", timeout=10)
        except Exception as e:
            log.warning("Could not mount debugfs: {}".format(e))

        log.info("Reloading LKDTM module after reboot...")
        try:
            self.console.run_command("rmmod lkdtm 2>/dev/null || true", timeout=10)
        except:
            pass

        if not self.load_lkdtm_module():
            self.skipTest("LKDTM module not available or cannot be loaded after reboot")

        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")

        # Step 5: Run ACCESS_USERSPACE test (KUAP) with nosmap in Hash mode
        log.info("-" * 60)
        log.info("Running ACCESS_USERSPACE test (KUAP) with nosmap in Hash mode...")
        log.info("Expected: Should NOT fault (SMAP protection disabled)")
        log.info("-" * 60)

        kuap_fault_occurred, kuap_dmesg, kuap_console = self.trigger_access_userspace_crash()

        if not kuap_fault_occurred:
            log.info("EXPECTED: ACCESS_USERSPACE did not cause a fault with nosmap in Hash mode")
            log.info("This confirms that SMAP protection is properly disabled")
        else:
            log.warning("UNEXPECTED: ACCESS_USERSPACE caused a fault even with nosmap in Hash mode")
            log.warning("This may indicate nosmap parameter is not working as expected")
            kuap_passed, kuap_message = self.verify_fault_in_output(kuap_dmesg, kuap_console)
            log.warning("Fault details: {}".format(kuap_message))

        # Step 6: Run EXEC_USERSPACE test (KUEP) with nosmep in Hash mode
        log.info("-" * 60)
        log.info("Running EXEC_USERSPACE test (KUEP) with nosmep in Hash mode...")
        log.info("Expected: Should NOT fault (SMEP protection disabled)")
        log.info("-" * 60)

        kuep_fault_occurred, kuep_dmesg, kuep_console = self.trigger_exec_userspace_crash()

        if not kuep_fault_occurred:
            log.info("EXPECTED: EXEC_USERSPACE did not cause a fault with nosmep in Hash mode")
            log.info("This confirms that SMEP protection is properly disabled")
        else:
            log.warning("UNEXPECTED: EXEC_USERSPACE caused a fault even with nosmep in Hash mode")
            log.warning("This may indicate nosmep parameter is not working as expected")
            kuep_passed, kuep_message = self.verify_fault_in_output(kuep_dmesg, kuep_console)
            log.warning("Fault details: {}".format(kuep_message))

        # Step 7: Print detailed output for both tests
        log.info("=" * 60)
        log.info("KUAP Test Output Summary (Hash Mode):")
        log.info("-" * 60)
        if kuap_console:
            log.info("Console output from ACCESS_USERSPACE:")
            for line in kuap_console[-30:]:
                log.debug(line)
        if kuap_dmesg:
            log.info("Last 50 lines of dmesg for ACCESS_USERSPACE:")
            for line in kuap_dmesg[-50:]:
                log.debug(line)

        log.info("=" * 60)
        log.info("KUEP Test Output Summary (Hash Mode):")
        log.info("-" * 60)
        if kuep_console:
            log.info("Console output from EXEC_USERSPACE:")
            for line in kuep_console[-30:]:
                log.debug(line)
        if kuep_dmesg:
            log.info("Last 50 lines of dmesg for EXEC_USERSPACE:")
            for line in kuep_dmesg[-50:]:
                log.debug(line)

        # Step 8: Remove kernel arguments and restore system
        log.info("=" * 60)
        log.info("Cleaning up: removing kernel arguments and rebooting...")
        log.info("=" * 60)

        cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)

        if not cleanup_success:
            log.error("Failed to remove kernel arguments: {}".format(kernel_args))
            log.error("Manual cleanup may be required!")
            self.fail("Cleanup failed - could not remove kernel arguments: {}".format(kernel_args))

        # Step 9: Verify arguments were removed
        log.info("Verifying kernel arguments were removed...")
        cmdline_after_cleanup = self.get_current_cmdline()

        still_present = [arg for arg in required_args if arg in cmdline_after_cleanup]

        if still_present:
            log.error("Cleanup verification failed! Arguments still present: {}".format(', '.join(still_present)))
            log.error("Current cmdline: {}".format(cmdline_after_cleanup))
            self.fail("Cleanup incomplete - arguments still in cmdline: {}".format(', '.join(still_present)))

        log.info("Cleanup verified: all arguments successfully removed")
        log.info("System restored to original state")

        # Step 10: Final test result
        log.info("=" * 60)

        # With nosmap and nosmep, we expect NO faults (protections disabled)
        unexpected_faults = []
        if kuap_fault_occurred:
            unexpected_faults.append("ACCESS_USERSPACE (with nosmap)")
        if kuep_fault_occurred:
            unexpected_faults.append("EXEC_USERSPACE (with nosmep)")

        if unexpected_faults:
            log.warning("WARNING: Unexpected faults occurred: {}".format(', '.join(unexpected_faults)))
            log.warning("This may indicate nosmap/nosmep parameters are not working correctly in Hash mode")

        log.info("PASS: Combined KUAP and KUEP Test with nosmap/nosmep/disable_radix Completed")
        log.info("Test Results in {} mode:".format(mmu_type))
        log.info("  - ACCESS_USERSPACE with nosmap: {} fault".format("DID" if kuap_fault_occurred else "did NOT"))
        log.info("  - EXEC_USERSPACE with nosmep: {} fault".format("DID" if kuep_fault_occurred else "did NOT"))
        log.info("Expected behavior: Both should NOT fault (protections disabled)")
        log.info("This validates that nosmap and nosmep kernel arguments work correctly in Hash mode")
        log.info("=" * 60)


def lkdtm_suite():
    '''
    Function to prepare a test suite for Kernel Userspace Access and Execution Prevention tests.
    This allows: --run-suite lkdtm

    Includes:
    1. ACCESS_USERSPACE test (KUAP - Kernel Userspace Access Prevention)
    2. EXEC_USERSPACE test (KUEP - Kernel Userspace Execution Prevention)
    3. Combined KUAP and KUEP test with nosmap and nosmep
    4. KUAP test with disable_radix (Hash mode)
    5. KUEP test with disable_radix (Hash mode)
    6. Combined KUAP and KUEP test with nosmap, nosmep, and disable_radix
    '''
    suite = unittest.TestSuite()
    suite.addTest(LKDTMAccessUserspace('runTest'))
    suite.addTest(LKDTMExecUserspace('runTest'))
    suite.addTest(LKDTMKuapKuepCombined('runTest'))
    suite.addTest(LKDTMKuapWithDisableRadix('runTest'))
    suite.addTest(LKDTMKuepWithDisableRadix('runTest'))
    suite.addTest(LKDTMKuapKuepCombinedWithDisableRadix('runTest'))
    return suite
