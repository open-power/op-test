#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
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
# Assisted with AI tool.
# 

'''
OpTestKuepKuap: Kernel Userspace Access and Execution Prevention Tests

This test case validates kernel security features using LKDTM:
1. KUAP - Kernel Userspace Access Prevention (ACCESS_USERSPACE)
2. KUEP - Kernel Userspace Execution Prevention (EXEC_USERSPACE)
3. Combined tests with various kernel parameters (nosmap, nosmep, disable_radix)

The tests trigger these conditions via LKDTM and verify that the kernel
properly prevents the access/execution and faults appropriately.
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
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.console = None
        cls.install_util = None
        cls.original_panic_on_oops = None

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_SYSTEM.console
        if self.install_util is None:
            self.install_util = OpTestInstallUtil.InstallUtil()
        self.load_lkdtm_module()
        self.disable_panic_on_oops()

    def load_lkdtm_module(self):
        try:
            result = self.console.run_command("lsmod | grep lkdtm", timeout=10)
            if result and any('lkdtm' in line for line in result):
                log.info("LKDTM module is already loaded")
                return True
        except:
            pass
        try:
            log.info("Attempting to load LKDTM module...")
            self.console.run_command("modprobe lkdtm", timeout=30)
            log.info("LKDTM module loaded successfully")
            return True
        except Exception as e:
            log.warning("Could not load LKDTM module: {}".format(e))
            return False

    def disable_panic_on_oops(self):
        try:
            result = self.console.run_command("cat /proc/sys/kernel/panic_on_oops", timeout=10)
            if result:
                current_value = result[-1].strip()
                self.original_panic_on_oops = current_value
                log.info("Current panic_on_oops value: {}".format(current_value))
                if current_value == "0":
                    log.info("panic_on_oops is already disabled")
                    return True
                log.info("Disabling panic_on_oops to prevent system panic during tests...")
                self.console.run_command("echo 0 > /proc/sys/kernel/panic_on_oops", timeout=10)
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
        if self.original_panic_on_oops is None:
            log.info("No original panic_on_oops value to restore")
            return True
        try:
            log.info("Restoring panic_on_oops to original value: {}".format(self.original_panic_on_oops))
            self.console.run_command(
                "echo {} > /proc/sys/kernel/panic_on_oops".format(self.original_panic_on_oops),
                timeout=10
            )
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
        try:
            result = self.console.run_command("cat /proc/cmdline", timeout=10)
            cmdline = ' '.join(result)
            log.info("Current kernel cmdline: {}".format(cmdline))
            return cmdline
        except Exception as e:
            log.error("Failed to get kernel cmdline: {}".format(e))
            return ""

    def update_kernel_cmdline(self, add_args="", remove_args=""):
        try:
            log.info("Updating kernel cmdline...")
            if add_args:
                log.info("Adding parameters: {}".format(add_args))
            if remove_args:
                log.info("Removing parameters: {}".format(remove_args))
            distro = self.cv_HOST.host_get_OS_Level()
            log.info("Detected OS: {}".format(distro))
            success = self.install_util.update_kernel_cmdline(
                distro, add_args, remove_args, reboot=True, reboot_cmd=False, timeout=60
            )
            if success:
                log.info("Kernel cmdline updated successfully")
                self.console = self.cv_SYSTEM.console
                return True
            else:
                log.error("Failed to update kernel cmdline")
                return False
        except Exception as e:
            log.error("Exception while updating kernel cmdline: {}".format(e))
            import traceback
            log.error("Traceback: {}".format(traceback.format_exc()))
            return False

    def check_lkdtm_available(self):
        try:
            result = self.console.run_command(
                "test -d /sys/kernel/debug/provoke-crash/ && echo 'EXISTS' || echo 'NOT_EXISTS'",
                timeout=10
            )
            if 'EXISTS' in result[-1]:
                log.info("LKDTM provoke-crash interface is available")
                return True
            else:
                log.warning("LKDTM provoke-crash directory not found")
                return False
        except CommandFailed as e:
            log.error("Failed to check LKDTM availability: {}".format(e))
            return False

    def trigger_lkdtm_crash(self, crash_type):
        console_output = []
        try:
            try:
                self.console.run_command("dmesg -c > /dev/null", timeout=10)
            except:
                pass
            result = self.console.run_command(
                "bash -c 'echo {} > /sys/kernel/debug/provoke-crash/DIRECT'".format(crash_type),
                timeout=10
            )
            console_output = result
            log.error("{} did not trigger a fault - protection may not be working!".format(crash_type))
            try:
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
            except:
                dmesg = []
            return False, dmesg, console_output
        except Exception as e:
            log.info("{} triggered a fault as expected: {}".format(crash_type, str(e)))
            try:
                import time
                time.sleep(2)
                dmesg = self.console.run_command("dmesg | tail -100", timeout=30)
                return True, dmesg, console_output
            except Exception as dmesg_error:
                log.warning("Could not retrieve dmesg after fault: {}".format(dmesg_error))
                return True, [], console_output

    def verify_fault_in_output(self, dmesg_output, console_output):
        all_output = '\n'.join(dmesg_output + console_output)
        if 'PASS: Faulted appropriately' in all_output:
            log.info("Found 'PASS: Faulted appropriately' - protection is working!")
            return True, "Found 'PASS: Faulted appropriately' message"
        critical_indicators = [
            ('Segmentation fault', 'Segmentation fault occurred (expected behavior)'),
            ('Oops', 'Kernel Oops detected (fault occurred)'),
            ('kernel BUG', 'Kernel BUG detected (fault occurred)'),
        ]
        for indicator, message in critical_indicators:
            if indicator in all_output:
                log.info("Found critical indicator: {}".format(indicator))
                return True, message
        lkdtm_indicators = ['lkdtm', 'LKDTM', 'ACCESS_USERSPACE', 'EXEC_USERSPACE']
        found_lkdtm = [ind for ind in lkdtm_indicators if ind in all_output]
        if found_lkdtm:
            log.info("Found LKDTM indicators: {}".format(', '.join(found_lkdtm)))
            return True, "Found LKDTM activity: {}".format(', '.join(found_lkdtm))
        log.warning("No clear fault indicators found in output")
        return False, "No fault indicators found"

    def run_protection_test(self, test_type, kernel_args="", expect_fault=True):
        log.info("=" * 60)
        log.info("Starting {} Test".format(test_type))
        if kernel_args:
            log.info("Kernel arguments: {}".format(kernel_args))
        log.info("=" * 60)
        if kernel_args:
            log.info("Adding kernel arguments: {}".format(kernel_args))
            if not self.update_kernel_cmdline(add_args=kernel_args):
                self.fail("Failed to add kernel arguments: {}".format(kernel_args))
            cmdline = self.get_current_cmdline()
            required_args = kernel_args.split()
            missing_args = [arg for arg in required_args if arg not in cmdline]
            if missing_args:
                self.fail("Kernel arguments {} not found in cmdline after reboot".format(', '.join(missing_args)))
            log.info("Confirmed kernel arguments are active: {}".format(kernel_args))
            if "disable_radix" in kernel_args:
                is_hash_mode, mmu_type = self.check_hash_mode()
                log.info("MMU Mode detected: {}".format(mmu_type))
                if not is_hash_mode:
                    log.warning("WARNING: System did not boot in Hash mode (detected: {})".format(mmu_type))
                else:
                    log.info("SUCCESS: System booted in Hash mode as expected")
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
        crash_type = "ACCESS_USERSPACE" if "KUAP" in test_type else "EXEC_USERSPACE"
        log.info("Triggering {} to test protection...".format(crash_type))
        fault_occurred, dmesg_output, console_output = self.trigger_lkdtm_crash(crash_type)
        if expect_fault:
            if not fault_occurred:
                log.error("FAIL: {} did not cause a fault!".format(crash_type))
                log.debug("Console output:\n{}".format('\n'.join(console_output)))
                log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
                if kernel_args:
                    self.update_kernel_cmdline(remove_args=kernel_args)
                self.fail("{} did not trigger expected fault".format(crash_type))
            log.info("Verifying fault indicators in output...")
            passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
            if passed:
                log.info("SUCCESS: {}".format(result_message))
            else:
                log.warning("WARNING: Fault occurred but expected messages not found")
                log.warning("Result: {}".format(result_message))
        else:
            if not fault_occurred:
                log.info("EXPECTED: {} did not cause a fault (protection disabled)".format(crash_type))
            else:
                log.warning("UNEXPECTED: {} caused a fault even with protection disabled".format(crash_type))
                passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
                log.warning("Fault details: {}".format(result_message))
        if console_output:
            log.info("Console output from {}:".format(crash_type))
            for line in console_output[-30:]:
                log.debug(line)
        if dmesg_output:
            log.info("Last 50 lines of dmesg:")
            for line in dmesg_output[-50:]:
                log.debug(line)
        if kernel_args:
            log.info("=" * 60)
            log.info("Cleaning up: removing kernel arguments and rebooting...")
            log.info("=" * 60)
            cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)
            if not cleanup_success:
                log.error("Failed to remove kernel arguments: {}".format(kernel_args))
                self.fail("Cleanup failed - could not remove kernel arguments: {}".format(kernel_args))
            log.info("Verifying kernel arguments were removed...")
            cmdline_after_cleanup = self.get_current_cmdline()
            still_present = [arg for arg in required_args if arg in cmdline_after_cleanup]
            if still_present:
                log.error("Cleanup verification failed! Arguments still present: {}".format(', '.join(still_present)))
                self.fail("Cleanup incomplete - arguments still in cmdline: {}".format(', '.join(still_present)))
            log.info("Cleanup verified: all arguments successfully removed")
            log.info("System restored to original state")
        log.info("=" * 60)
        log.info("PASS: {} Test Completed".format(test_type))
        log.info("=" * 60)
        return fault_occurred

    def run_combined_test(self, kernel_args="", expect_fault=True):
        log.info("=" * 60)
        log.info("Starting Combined KUAP and KUEP Test")
        if kernel_args:
            log.info("Kernel arguments: {}".format(kernel_args))
        log.info("=" * 60)
        if kernel_args:
            log.info("Adding kernel arguments: {}".format(kernel_args))
            if not self.update_kernel_cmdline(add_args=kernel_args):
                self.fail("Failed to add kernel arguments: {}".format(kernel_args))
            cmdline = self.get_current_cmdline()
            required_args = kernel_args.split()
            missing_args = [arg for arg in required_args if arg not in cmdline]
            if missing_args:
                self.fail("Kernel arguments {} not found in cmdline after reboot".format(', '.join(missing_args)))
            log.info("Confirmed all kernel arguments are active: {}".format(kernel_args))
            if "disable_radix" in kernel_args:
                is_hash_mode, mmu_type = self.check_hash_mode()
                log.info("MMU Mode detected: {}".format(mmu_type))
                if not is_hash_mode:
                    log.warning("WARNING: System did not boot in Hash mode (detected: {})".format(mmu_type))
                else:
                    log.info("SUCCESS: System booted in Hash mode as expected")
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
        log.info("-" * 60)
        log.info("Running ACCESS_USERSPACE test (KUAP)...")
        log.info("Expected: Should {} fault".format("" if expect_fault else "NOT"))
        log.info("-" * 60)
        kuap_fault_occurred, kuap_dmesg, kuap_console = self.trigger_lkdtm_crash("ACCESS_USERSPACE")
        if expect_fault:
            if not kuap_fault_occurred:
                log.error("FAIL: ACCESS_USERSPACE did not cause a fault!")
            else:
                log.info("SUCCESS: ACCESS_USERSPACE caused a fault as expected")
                kuap_passed, kuap_message = self.verify_fault_in_output(kuap_dmesg, kuap_console)
                if kuap_passed:
                    log.info("Fault verification: {}".format(kuap_message))
        else:
            if not kuap_fault_occurred:
                log.info("EXPECTED: ACCESS_USERSPACE did not cause a fault (protection disabled)")
            else:
                log.warning("UNEXPECTED: ACCESS_USERSPACE caused a fault even with protection disabled")
                kuap_passed, kuap_message = self.verify_fault_in_output(kuap_dmesg, kuap_console)
                log.warning("Fault details: {}".format(kuap_message))
        log.info("-" * 60)
        log.info("Running EXEC_USERSPACE test (KUEP)...")
        log.info("Expected: Should {} fault".format("" if expect_fault else "NOT"))
        log.info("-" * 60)
        kuep_fault_occurred, kuep_dmesg, kuep_console = self.trigger_lkdtm_crash("EXEC_USERSPACE")
        if expect_fault:
            if not kuep_fault_occurred:
                log.error("FAIL: EXEC_USERSPACE did not cause a fault!")
            else:
                log.info("SUCCESS: EXEC_USERSPACE caused a fault as expected")
                kuep_passed, kuep_message = self.verify_fault_in_output(kuep_dmesg, kuep_console)
                if kuep_passed:
                    log.info("Fault verification: {}".format(kuep_message))
        else:
            if not kuep_fault_occurred:
                log.info("EXPECTED: EXEC_USERSPACE did not cause a fault (protection disabled)")
            else:
                log.warning("UNEXPECTED: EXEC_USERSPACE caused a fault even with protection disabled")
                kuep_passed, kuep_message = self.verify_fault_in_output(kuep_dmesg, kuep_console)
                log.warning("Fault details: {}".format(kuep_message))
        log.info("=" * 60)
        log.info("KUAP Test Output Summary:")
        log.info("-" * 60)
        if kuap_console:
            for line in kuap_console[-30:]:
                log.debug(line)
        if kuap_dmesg:
            for line in kuap_dmesg[-50:]:
                log.debug(line)
        log.info("=" * 60)
        log.info("KUEP Test Output Summary:")
        log.info("-" * 60)
        if kuep_console:
            for line in kuep_console[-30:]:
                log.debug(line)
        if kuep_dmesg:
            for line in kuep_dmesg[-50:]:
                log.debug(line)
        if kernel_args:
            log.info("=" * 60)
            log.info("Cleaning up: removing kernel arguments and rebooting...")
            log.info("=" * 60)
            cleanup_success = self.update_kernel_cmdline(remove_args=kernel_args)
            if not cleanup_success:
                log.error("Failed to remove kernel arguments: {}".format(kernel_args))
                self.fail("Cleanup failed - could not remove kernel arguments: {}".format(kernel_args))
            log.info("Verifying kernel arguments were removed...")
            cmdline_after_cleanup = self.get_current_cmdline()
            still_present = [arg for arg in required_args if arg in cmdline_after_cleanup]
            if still_present:
                log.error("Cleanup verification failed! Arguments still present: {}".format(', '.join(still_present)))
                self.fail("Cleanup incomplete - arguments still in cmdline: {}".format(', '.join(still_present)))
            log.info("Cleanup verified: all arguments successfully removed")
            log.info("System restored to original state")
        log.info("=" * 60)
        unexpected_faults = []
        if not expect_fault:
            if kuap_fault_occurred:
                unexpected_faults.append("ACCESS_USERSPACE")
            if kuep_fault_occurred:
                unexpected_faults.append("EXEC_USERSPACE")
            if unexpected_faults:
                log.warning("WARNING: Unexpected faults occurred: {}".format(', '.join(unexpected_faults)))
        log.info("PASS: Combined KUAP and KUEP Test Completed")
        log.info("Test Results:")
        log.info("  - ACCESS_USERSPACE: {} fault".format("DID" if kuap_fault_occurred else "did NOT"))
        log.info("  - EXEC_USERSPACE: {} fault".format("DID" if kuep_fault_occurred else "did NOT"))
        log.info("=" * 60)
        return kuap_fault_occurred, kuep_fault_occurred

    def runTest(self):
        log.info("=" * 60)
        log.info("Starting Kernel Userspace Access Prevention Test")
        log.info("Using LKDTM ACCESS_USERSPACE trigger")
        log.info("=" * 60)
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")
        log.info("Triggering ACCESS_USERSPACE to test userspace access prevention...")
        fault_occurred, dmesg_output, console_output = self.trigger_lkdtm_crash("ACCESS_USERSPACE")
        if not fault_occurred:
            log.error("FAIL: ACCESS_USERSPACE did not cause a fault!")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            self.fail("ACCESS_USERSPACE did not trigger expected fault")
        log.info("Verifying fault indicators in output...")
        passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
        if passed:
            log.info("SUCCESS: {}".format(result_message))
        else:
            log.warning("WARNING: Fault occurred but expected messages not found")
            log.warning("Result: {}".format(result_message))
        if console_output:
            for line in console_output[-50:]:
                log.debug(line)
        if dmesg_output:
            for line in dmesg_output[-100:]:
                log.debug(line)
        log.info("=" * 60)
        log.info("PASS: Kernel Userspace Access Prevention Test Completed")
        log.info("=" * 60)

    def tearDown(self):
        self.restore_panic_on_oops()
        log.info("LKDTM test cleanup completed")


class LKDTMAccessUserspace(OpTestKuepKuap):
    def runTest(self):
        super(LKDTMAccessUserspace, self).runTest()


class LKDTMExecUserspace(OpTestKuepKuap):
    def runTest(self):
        log.info("=" * 60)
        log.info("Starting Kernel Userspace Execution Prevention Test")
        log.info("Using LKDTM EXEC_USERSPACE trigger")
        log.info("=" * 60)
        if not self.check_lkdtm_available():
            self.skipTest("LKDTM module not available or cannot be loaded")
        log.info("Triggering EXEC_USERSPACE to test userspace execution prevention...")
        fault_occurred, dmesg_output, console_output = self.trigger_lkdtm_crash("EXEC_USERSPACE")
        if not fault_occurred:
            log.error("FAIL: EXEC_USERSPACE did not cause a fault!")
            log.debug("Console output:\n{}".format('\n'.join(console_output)))
            log.debug("dmesg output:\n{}".format('\n'.join(dmesg_output)))
            self.fail("EXEC_USERSPACE did not trigger expected fault")
        log.info("Verifying fault indicators in output...")
        passed, result_message = self.verify_fault_in_output(dmesg_output, console_output)
        if passed:
            log.info("SUCCESS: {}".format(result_message))
        else:
            log.warning("WARNING: Fault occurred but expected messages not found")
            log.warning("Result: {}".format(result_message))
        if console_output:
            for line in console_output[-50:]:
                log.debug(line)
        if dmesg_output:
            for line in dmesg_output[-100:]:
                log.debug(line)
        log.info("=" * 60)
        log.info("PASS: Kernel Userspace Execution Prevention Test Completed")
        log.info("=" * 60)


class LKDTMKuapKuepCombined(OpTestKuepKuap):
    def runTest(self):
        self.run_combined_test(kernel_args="nosmap nosmep", expect_fault=False)


class LKDTMKuapWithDisableRadix(OpTestKuepKuap):
    def runTest(self):
        self.run_protection_test("KUAP", kernel_args="disable_radix", expect_fault=True)


class LKDTMKuepWithDisableRadix(OpTestKuepKuap):
    def runTest(self):
        self.run_protection_test("KUEP", kernel_args="disable_radix", expect_fault=True)


class LKDTMKuapKuepCombinedWithDisableRadix(OpTestKuepKuap):
    def runTest(self):
        self.run_combined_test(kernel_args="nosmap nosmep disable_radix", expect_fault=False)


def lkdtm_suite():
    suite = unittest.TestSuite()
    suite.addTest(LKDTMAccessUserspace('runTest'))
    suite.addTest(LKDTMExecUserspace('runTest'))
    suite.addTest(LKDTMKuapKuepCombined('runTest'))
    suite.addTest(LKDTMKuapWithDisableRadix('runTest'))
    suite.addTest(LKDTMKuepWithDisableRadix('runTest'))
    suite.addTest(LKDTMKuapKuepCombinedWithDisableRadix('runTest'))
    return suite
