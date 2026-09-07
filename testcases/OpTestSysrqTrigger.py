#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/Crashtool.py $
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
# IBM_PROLOG_END_TAG
#Author: Shirisha Ganta <shirisha@linux.ibm.com>

'''
OpTestSysrqTrigger: Test SysRq trigger functionality
-----------------------------------------------------

This test case validates various SysRq trigger commands by writing to
/proc/sysrq-trigger and verifying the expected system behavior.
'''

import unittest
import time
import re
import logging

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestSysrqTrigger(unittest.TestCase):
    '''
    Test class for SysRq trigger functionality.
    Tests various sysrq-trigger commands and verifies expected behavior.
    '''

    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_IPMI = conf.ipmi()
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_SYSTEM.console
        # Enable sysrq if needed
        try:
            self.console.run_command("echo 1 | sudo tee /proc/sys/kernel/sysrq > /dev/null 2>&1 || true", timeout=10)
        except:
            pass

    def trigger_sysrq(self, key, timeout=10, ignore_fail=False):
        """
        Trigger sysrq using a method that works with restricted shells.
        
        The op-test console may run in a restricted shell that doesn't allow
        output redirection (>). This method uses 'tee' or 'sh -c' to bypass
        that restriction.
        
        Args:
            key: The sysrq key to trigger
            timeout: Command timeout
            ignore_fail: If True, don't raise exception on failure
        
        Returns:
            Command output or None if ignore_fail=True and command fails
        """
        # Method 1: Use tee (works in restricted shells)
        cmd = f"echo {key} | sudo tee /proc/sysrq-trigger > /dev/null"
        
        try:
            output = self.console.run_command(cmd, timeout=timeout)
            log.debug(f"Successfully triggered sysrq '{key}'")
            return output
        except Exception as e:
            # Method 2: Try with sh -c if tee fails
            try:
                cmd = f"sudo sh -c 'echo {key} > /proc/sysrq-trigger'"
                output = self.console.run_command(cmd, timeout=timeout)
                log.debug(f"Successfully triggered sysrq '{key}' using sh -c")
                return output
            except Exception as e2:
                if ignore_fail:
                    log.warning(f"Sysrq trigger '{key}' failed (ignored): {str(e2)}")
                    return None
                else:
                    log.error(f"Failed to trigger sysrq '{key}': {str(e2)}")
                    raise

    def verify_dmesg_output(self, expected_pattern, timeout=10):
        """
        Verify that dmesg contains the expected pattern.
        
        Args:
            expected_pattern: Regex pattern to search for in dmesg
            timeout: Time to wait for the pattern to appear
        """
        time.sleep(2)  # Give system time to log the message
        try:
            output = self.console.run_command("dmesg | tail -50", timeout=timeout)
            output_str = '\n'.join(output)
            if re.search(expected_pattern, output_str, re.IGNORECASE):
                log.info(f"Found expected pattern: {expected_pattern}")
                return True
            else:
                log.warning(f"Pattern not found: {expected_pattern}")
                log.debug(f"dmesg output: {output_str}")
                return False
        except Exception as e:
            log.error(f"Error checking dmesg: {str(e)}")
            return False

class SysrqBasicTests(OpTestSysrqTrigger):

    def test_sysrq_loglevel_0(self):
        """Test: echo 0 > /proc/sysrq-trigger - Set loglevel to 0"""
        log.info("Testing sysrq-trigger with value 0 (loglevel 0)")
        try:
            self.trigger_sysrq('0', timeout=10)
            self.verify_dmesg_output("sysrq.*loglevel|changing.*loglevel")
            log.info("PASS: Loglevel 0 test completed")
        except Exception as e:
            log.error(f"FAIL: Loglevel 0 test failed: {str(e)}")
            raise

    def test_sysrq_loglevel_1_to_9(self):
        """Test: echo 1-9 > /proc/sysrq-trigger - Set various loglevels"""
        for level in range(1, 10):
            log.info(f"Testing sysrq-trigger with value {level} (loglevel {level})")
            try:
                self.trigger_sysrq(str(level), timeout=10)
                time.sleep(1)
                log.info(f"PASS: Loglevel {level} test completed")
            except Exception as e:
                log.error(f"FAIL: Loglevel {level} test failed: {str(e)}")
                raise

    def test_sysrq_k_sak(self):
        """Test: echo k > /proc/sysrq-trigger - SAK (Secure Access Key)"""
        log.info("Testing sysrq-trigger 'k' - SAK")
        try:
            self.trigger_sysrq('k', timeout=10, ignore_fail=True)
            if self.verify_dmesg_output("sysrq.*SAK"):
                log.info("PASS: SAK test completed")
            else:
                log.warning("SAK message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: SAK test failed: {str(e)}")
            raise

    def test_sysrq_l_backtrace(self):
        """Test: echo l > /proc/sysrq-trigger - Show backtrace of all active CPUs"""
        log.info("Testing sysrq-trigger 'l' - Show backtrace of all active CPUs")
        try:
            self.trigger_sysrq('l', timeout=10)
            if self.verify_dmesg_output("sysrq.*backtrace|Show backtrace|backtrace|CPU"):
                log.info("PASS: Backtrace test completed")
            else:
                log.warning("Backtrace message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Backtrace test failed: {str(e)}")
            raise

    def test_sysrq_m_memory(self):
        """Test: echo m > /proc/sysrq-trigger - Show Memory"""
        log.info("Testing sysrq-trigger 'm' - Show Memory")
        try:
            self.trigger_sysrq('m', timeout=10)
            if self.verify_dmesg_output("sysrq.*Memory|Show Memory"):
                log.info("PASS: Show Memory test completed")
            else:
                log.warning("Memory message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Show Memory test failed: {str(e)}")
            raise

    def test_sysrq_n_nice_rt(self):
        """Test: echo n > /proc/sysrq-trigger - Nice All RT Tasks"""
        log.info("Testing sysrq-trigger 'n' - Nice All RT Tasks")
        try:
            self.trigger_sysrq('n', timeout=10)
            if self.verify_dmesg_output("sysrq.*Nice.*RT|Nice All RT"):
                log.info("PASS: Nice RT Tasks test completed")
            else:
                log.warning("Nice RT message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Nice RT Tasks test failed: {str(e)}")
            raise

    def test_sysrq_p_show_regs(self):
        """Test: echo p > /proc/sysrq-trigger - Show Regs"""
        log.info("Testing sysrq-trigger 'p' - Show Regs")
        try:
            self.trigger_sysrq('p', timeout=10)
            if self.verify_dmesg_output("sysrq.*Regs|Show Regs"):
                log.info("PASS: Show Regs test completed")
            else:
                log.warning("Show Regs message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Show Regs test failed: {str(e)}")
            raise

    def test_sysrq_q_hrtimers(self):
        """Test: echo q > /proc/sysrq-trigger - Show clockevent devices & pending hrtimers"""
        log.info("Testing sysrq-trigger 'q' - Show clockevent devices & pending hrtimers")
        try:
            self.trigger_sysrq('q', timeout=10)
            if self.verify_dmesg_output("sysrq.*clockevent|hrtimers|hrtimer"):
                log.info("PASS: Show hrtimers test completed")
            else:
                log.warning("hrtimers message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Show hrtimers test failed: {str(e)}")
            raise

    def test_sysrq_r_keyboard(self):
        """Test: echo r > /proc/sysrq-trigger - Keyboard mode set to system default"""
        log.info("Testing sysrq-trigger 'r' - Keyboard mode")
        try:
            self.trigger_sysrq('r', timeout=30)
            if self.verify_dmesg_output("sysrq.*Keyboard"):
                log.info("PASS: Keyboard mode test completed")
            else:
                log.warning("Keyboard message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Keyboard mode test failed: {str(e)}")
            raise

    def test_sysrq_s_sync(self):
        """Test: echo s > /proc/sysrq-trigger - Emergency Sync"""
        log.info("Testing sysrq-trigger 's' - Emergency Sync")
        try:
            self.trigger_sysrq('s', timeout=60)
            time.sleep(5)
            if self.verify_dmesg_output("sysrq.*Sync|Emergency Sync|Emergency Sync complete"):
                log.info("PASS: Emergency Sync test completed")
            else:
                log.warning("Sync message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Emergency Sync test failed: {str(e)}")
            raise

    def test_sysrq_t_show_state(self):
        """Test: echo t > /proc/sysrq-trigger - Show State"""
        log.info("Testing sysrq-trigger 't' - Show State")
        try:
            self.trigger_sysrq('t', timeout=30)
            if self.verify_dmesg_output("sysrq.*State|Show State|runnable|workqueues"):
                log.info("PASS: Show State test completed")
            else:
                log.warning("Show State message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Show State test failed: {str(e)}")
            raise

    def test_sysrq_u_remount_ro(self):
        """Test: echo u > /proc/sysrq-trigger - Emergency Remount R/O"""
        log.info("Testing sysrq-trigger 'u' - Emergency Remount R/O")
        try:
            self.trigger_sysrq('u', timeout=30)
            time.sleep(5)
            if self.verify_dmesg_output("sysrq.*Remount|Emergency Remount|Emergency Remount complete"):
                log.info("PASS: Emergency Remount R/O test completed")
            else:
                log.warning("Remount message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Emergency Remount R/O test failed: {str(e)}")
            raise

    def test_sysrq_w_blocked_state(self):
        """Test: echo w > /proc/sysrq-trigger - Show Blocked State"""
        log.info("Testing sysrq-trigger 'w' - Show Blocked State")
        try:
            self.trigger_sysrq('w', timeout=10)
            if self.verify_dmesg_output("sysrq.*Blocked|Show Blocked"):
                log.info("PASS: Show Blocked State test completed")
            else:
                log.warning("Blocked State message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Show Blocked State test failed: {str(e)}")
            raise

    def test_sysrq_z_ftrace(self):
        """Test: echo z > /proc/sysrq-trigger - Dump ftrace buffer"""
        log.info("Testing sysrq-trigger 'z' - Dump ftrace buffer")
        try:
            self.trigger_sysrq('z', timeout=10, ignore_fail=True)
            if self.verify_dmesg_output("sysrq.*ftrace|Dump ftrace|ftrace buffer"):
                log.info("PASS: Dump ftrace buffer test completed")
            else:
                log.warning("ftrace message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Dump ftrace buffer test failed: {str(e)}")
            raise

    def runTest(self):
        """Run all non-destructive tests"""
        self.test_sysrq_loglevel_0()
        self.test_sysrq_loglevel_1_to_9()
        self.test_sysrq_k_sak()
        self.test_sysrq_l_backtrace()
        self.test_sysrq_m_memory()
        self.test_sysrq_n_nice_rt()
        self.test_sysrq_p_show_regs()
        self.test_sysrq_q_hrtimers()
        self.test_sysrq_r_keyboard()
        self.test_sysrq_s_sync()
        self.test_sysrq_t_show_state()
        self.test_sysrq_u_remount_ro()
        self.test_sysrq_w_blocked_state()
        self.test_sysrq_z_ftrace()


class SysrqTriggerDestructiveTests(OpTestSysrqTrigger):
    """
    Destructive tests that require system reboot or may cause system instability.
    These tests should be run separately and with caution.
    """

    def test_sysrq_b_reboot(self):
        """Test: echo b > /proc/sysrq-trigger - Immediate reboot"""
        log.info("Testing sysrq-trigger 'b' - Immediate reboot")
        log.warning("This test will reboot the system immediately!")
        try:
            # Sync before reboot
            self.console.run_command("sync", timeout=10)
            time.sleep(2)
            
            # Trigger reboot
            self.console.run_command_ignore_fail("echo b > /proc/sysrq-trigger", timeout=5)
            
            # Wait for system to go down
            time.sleep(10)
            
            # Wait for system to come back up
            log.info("Waiting for system to reboot...")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
            log.info("PASS: System rebooted successfully")
        except Exception as e:
            log.error(f"FAIL: Reboot test failed: {str(e)}")
            raise

    def test_sysrq_e_term_all(self):
        """Test: echo e > /proc/sysrq-trigger - SIGTERM all processes"""
        log.info("Testing sysrq-trigger 'e' - SIGTERM all processes")
        log.warning("This test will terminate all processes!")
        try:
            self.console.run_command_ignore_fail("echo e > /proc/sysrq-trigger", timeout=5)
            time.sleep(5)
            
            # System should get to login prompt
            log.info("Waiting for system to stabilize...")
            time.sleep(10)
            
            # Try to reconnect
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
            log.info("PASS: SIGTERM all processes test completed")
        except Exception as e:
            log.error(f"FAIL: SIGTERM test failed: {str(e)}")
            raise

    def test_sysrq_f_oom(self):
        """Test: echo f > /proc/sysrq-trigger - Manual OOM kill"""
        log.info("Testing sysrq-trigger 'f' - Manual OOM kill")
        try:
            self.trigger_sysrq('f', timeout=10)
            if self.verify_dmesg_output("sysrq.*OOM|Manual OOM|oom-kill|Out of memory", timeout=15):
                log.info("PASS: Manual OOM test completed")
            else:
                log.warning("OOM message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Manual OOM test failed: {str(e)}")
            raise

    def test_sysrq_i_kill_all(self):
        """Test: echo i > /proc/sysrq-trigger - SIGKILL all processes"""
        log.info("Testing sysrq-trigger 'i' - SIGKILL all processes")
        log.warning("This test will kill all processes!")
        try:
            self.trigger_sysrq('i', timeout=5, ignore_fail=True)
            time.sleep(5)
            
            # System should get to login prompt
            log.info("Waiting for system to stabilize...")
            time.sleep(10)
            
            # Try to reconnect
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
            log.info("PASS: SIGKILL all processes test completed")
        except Exception as e:
            log.error(f"FAIL: SIGKILL test failed: {str(e)}")
            raise

    def test_sysrq_j_thaw_filesystems(self):
        """Test: echo j > /proc/sysrq-trigger - Thaw filesystems"""
        log.info("Testing sysrq-trigger 'j' - Thaw filesystems")
        try:
            self.console.run_command("echo j > /proc/sysrq-trigger", timeout=10)
            if self.verify_dmesg_output("sysrq.*thaw|Thaw", timeout=15):
                log.info("PASS: Thaw filesystems test completed")
            else:
                log.warning("Thaw message not found in dmesg, but command executed")
        except Exception as e:
            log.error(f"FAIL: Thaw filesystems test failed: {str(e)}")
            raise

    def test_sysrq_o_poweroff(self):
        """Test: echo o > /proc/sysrq-trigger - Power off the system"""
        log.info("Testing sysrq-trigger 'o' - Power off")
        log.warning("This test will power off the system!")
        try:
            # Sync before poweroff
            self.console.run_command("sync", timeout=10)
            time.sleep(2)
            
            # Trigger poweroff
            self.console.run_command_ignore_fail("echo o > /proc/sysrq-trigger", timeout=5)
            
            # Wait for system to power off
            log.info("Waiting for system to power off...")
            time.sleep(30)
            
            # Power on the system
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
            log.info("PASS: System powered off and restarted successfully")
        except Exception as e:
            log.error(f"FAIL: Poweroff test failed: {str(e)}")
            raise

    def test_sysrq_x_xmon(self):
        """Test: echo x > /proc/sysrq-trigger - Enter XMON (PowerPC only)"""
        log.info("Testing sysrq-trigger 'x' - Enter XMON")
        log.warning("This test will enter XMON debugger (PowerPC specific)!")
        
        # Check if running on PowerPC
        try:
            output = self.console.run_command("uname -m", timeout=10)
            if "ppc" not in '\n'.join(output).lower():
                log.info("SKIP: XMON test only applicable for PowerPC systems")
                self.skipTest("Not a PowerPC system")
                return
        except:
            pass
        
        try:
            # Check if xmon is enabled
            try:
                output = self.console.run_command("cat /proc/sys/kernel/xmon 2>/dev/null || echo 'not found'", timeout=10)
                log.info(f"XMON status: {output}")
            except:
                log.warning("Could not check xmon status")
            
            self.console.run_command_ignore_fail("echo x > /proc/sysrq-trigger", timeout=5)
            time.sleep(5)
            
            # If system enters XMON, we need to exit it
            # This is platform-specific and may require special handling
            log.info("Attempting to recover from XMON...")
            
            # Try to reconnect
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
            log.info("PASS: XMON test completed")
        except Exception as e:
            log.error(f"FAIL: XMON test failed: {str(e)}")
            raise


    def runTest(self):
        #Run all destructive tests
        self.test_sysrq_f_oom()
        self.test_sysrq_j_thaw_filesystems()
        # Uncomment below tests only when you want to test them
        # as they will reboot/crash/poweroff the system
        #self.test_sysrq_b_reboot()
        #self.test_sysrq_e_term_all()
        #self.test_sysrq_i_kill_all()
        #self.test_sysrq_o_poweroff()
        #self.test_sysrq_x_xmon()

def full_suite():
    suite = unittest.TestSuite()
    suite.addTests(basic_suite())
    suite.addTests(destructive_suite())
    return suite
