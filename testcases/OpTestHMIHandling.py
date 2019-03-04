#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestHMIHandling.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
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

'''
OpTestHMIHandling
-----------------

HMI Handling package for OpenPower testing.

This class will test the functionality of following.

1. HMI Non-recoverable errors - Core checkstop and Hypervisor resource error
2. HMI Recoverable errors- proc_recv_done, proc_recv_error_masked and proc_recv_again
3. TFMR error injections
4. chip TOD error injections
'''

import time
import subprocess
import re
import sys
import os
import random
import pexpect
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.OpTestIPMI import IPMIConsoleState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed, UnknownStateTransition, PlatformError, HostbootShutdown, StoppingSystem

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestHMIHandling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_HOST = conf.host()
        cls.cv_IPMI = conf.ipmi()
        cls.cv_FSP = conf.bmc()
        cls.cv_SYSTEM = conf.system()
        cls.bmc_type = conf.args.bmc_type
        cls.util = conf.util

    def setUp(self):
        if self.cv_SYSTEM.get_state() == OpSystemState.UNKNOWN_BAD:
          self.clear_stop()

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.clearGardEntries()
        self.cv_HOST.host_enable_all_cores(console=1)
        self.cpu = ''.join(self.cv_HOST.host_run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'", console=1))
        if self.cpu in ["POWER9"]:
            self.revision = ''.join(self.cv_HOST.host_run_command("grep '^revision' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/ (.*)//;'", console=1))
            if not self.revision in ["2.2", "2.3"]:
                log.debug("Skipping, HMIHandling NOT supported on CPU={} Revision={}"
                           .format(self.cpu, self.revision))
                raise unittest.SkipTest("HMIHandling not supported on CPU={} Revision={}"
                                         .format(self.cpu, self.revision))
        else:
            log.debug("Skipping, HMIHandling NOT supported on CPU={} Revision={}"
                        .format(self.cpu, self.revision))
            raise unittest.SkipTest("HMIHandling not supported on CPU={} Revision={}"
                                     .format(self.cpu, self.revision))
        log.debug("Setting up to run HMIHandling on CPU={} Revision={}".format(self.cpu, self.revision))

    def clear_stop(self):
        self.cv_SYSTEM.stop = 0
        self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        for i in range(3):
          try:
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.clearGardEntries()
            break
          except (UnknownStateTransition, PlatformError, HostbootShutdown, StoppingSystem) as e:
            log.debug("\n\n\nOpTestSystem OpTestHMIHandling clear_stop counter i={} (i=0 or i=1 can be seen recovering from failed test) Exception={}\n\n\n".format(i, e))
            self.cv_SYSTEM.stop = 0
            self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
        else:
          self.assertTrue(False, "OpTestHMIHandling failed to recover from previous OpSystemState.UNKNOWN_BAD")

    def handle_panic(self):
        rc = self.cv_SYSTEM.console.pty.expect_no_fail(["Kernel panic - not syncing: Unrecoverable HMI exception", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
        if rc == 0:
            rc = self.cv_SYSTEM.console.pty.expect_no_fail(["ISTEP", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
            if rc == 0:
                self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                self.cv_SYSTEM.goto_state(OpSystemState.OS)
            else:
                self.assertTrue(False, "OpTestHMIHandling: System failing to reboot after topology recovery failure")
        else:
          self.assertTrue(False, "OpTestHMIHandling: No panic after topology recovery failure")

    def handle_OpalTI(self):
        rc = self.cv_SYSTEM.console.pty.expect_no_fail(["ISTEP", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
        if rc == 0:
            self.cv_SYSTEM.set_state(OpSystemState.IPLing)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        else:
            self.assertTrue(False, "System failed to reboot after OPAL TI")

    def handle_ipl(self):
        rc = self.cv_SYSTEM.console.pty.expect(["ISTEP", "istep", pexpect.TIMEOUT, pexpect.EOF], timeout=180)
        log.debug("before={}".format(self.cv_SYSTEM.console.pty.before))
        log.debug("after={}".format(self.cv_SYSTEM.console.pty.after))
        if rc in [0,1]:
          for i in range(3):
            try:
              self.cv_SYSTEM.set_state(OpSystemState.IPLing)
              self.cv_SYSTEM.goto_state(OpSystemState.OS)
              break
            except (UnknownStateTransition, PlatformError, HostbootShutdown, StoppingSystem) as e:
              log.debug("\n\n\nOpTestSystem OpTestHMIHandling handle_ipl counter i={} (i=0 or i=1 are common test results) Exception={}\n\n\n".format(i, e))
              self.cv_SYSTEM.stop = 0
          else:
            self.clear_stop() # set the machine to recover for whatever comes next
            self.assertTrue(False, "OpTestHMIHandling failed to normally recover after Error Injection")
        else:
          self.clear_stop() # set the machine to recover for whatever comes next
          self.assertTrue(False, "OpTestHMIHandling failed to get ISTEP/istep after Error Injection")

    def verify_proc_recovery(self, l_res):
        if any("Processor Recovery done" in line for line in l_res) and \
            any("Harmless Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
            log.debug("Processor recovery done")
            return
        else:
            raise Exception("HMI handling failed to log message: for proc_recv_done")

    def verify_timer_facility_recovery(self, l_res):
        if any("Timer facility experienced an error" in line for line in l_res) and \
            any("Severe Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
            log.debug("Timer facility experienced an error and got recovered")
            return
        else:
            raise Exception("HMI handling failed to log message")

    def init_test(self):
        self.proc_gen = self.cv_HOST.host_get_proc_gen(console=1)

        l_chips = self.cv_HOST.host_get_list_of_chips(console=1) # ['00000000', '00000001', '00000010']
        if not l_chips:
            raise Exception("Getscom failed to list processor chip ids")

        l_cores = self.cv_HOST.host_get_cores(console=1)
        if not l_cores:
            raise Exception("Failed to get list of core id's")

        log.debug(l_cores) # {0: ['4', '5', '6', 'c', 'd', 'e'], 1: ['4', '5', '6', 'c', 'd', 'e'], 10: ['4', '5', '6', 'c', 'd', 'e']}
        # Remove master core where injecting core checkstop leads to IPL expected failures
        # after 2 failures system will starts boot in Golden side of PNOR
        l_cores[0][1].pop(0)
        log.debug(l_cores)
        self.l_dic = []
        i=0
        for tup in l_cores:
            new_list = [l_chips[i], tup[1]]
            self.l_dic.append(new_list)
            i+=1
        log.debug(self.l_dic)
        # self.l_dic is a list of chip id's, core id's . and is of below format 
        # [['00000000', ['4', '5', '6', 'c', 'd', 'e']], ['00000001', ['4', '5', '6', 'c', 'd', 'e']], ['00000010', ['4', '5', '6', 'c', 'd', 'e']]]

        # In-order to inject HMI errors on cpu's, cpu should be running, so disabling the sleep states 1 and 2 of all CPU's
        self.disable_cpu_idle_states()

        # Disable kdump to check behaviour of IPL caused due to kernel panic after injection of core/system checkstop
        self.disable_kdump_service()


    def disable_kdump_service(self):
        l_oslevel = self.cv_HOST.host_get_OS_Level(console=1)
        try:
            if "Ubuntu" in l_oslevel:
                self.cv_HOST.host_run_command("service kdump-tools stop", console=1)
            else:
                self.cv_HOST.host_run_command("service kdump stop", console=1)
        except CommandFailed as cf:
            if cf.exitcode == 5:
                # kdump may not be enabled, so it's not a failure to stop it
                pass

    def enable_idle_state(self, i_idle):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 0 > $i; done" % i_idle
        self.cv_HOST.host_run_command(l_cmd, console=1)

    def disable_idle_state(self, i_idle):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 1 > $i; done" % i_idle
        self.cv_HOST.host_run_command(l_cmd, console=1)

    # Disable all CPU idle states except snooze state
    def disable_cpu_idle_states(self):
        states = self.cv_HOST.host_run_command("find /sys/devices/system/cpu/cpu*/cpuidle/state* -type d | cut -d'/' -f8 | sort -u | sed -e 's/^state//'", console=1)
        for state in states:
            if state is "0":
                try:
                    self.cv_HOST.host_run_command("cpupower idle-set -e 0", console=1)
                except CommandFailed:
                    self.enable_idle_state("0")
                continue
            try:
                self.cv_HOST.host_run_command("cpupower idle-set -d %s" % state, console=1)
            except CommandFailed:
                self.disable_idle_state(state)

    def form_scom_addr(self, addr, core):
        if self.proc_gen in ["POWER8", "POWER8E"]:
            val = addr[0]+str(core)+addr[2:]
        elif self.proc_gen in ["POWER9"]:
            val = hex(eval("0x%s | (((%s & 0x1f) + 0x20) << 24)" % (addr, int(core, 16))))
            log.debug(val)
        return val

    def is_node_present(self, node):
        ''' Check if specified device tree is present or not.'''
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        l_cmd = "ls %s" % node
        try:
            self.cv_HOST.host_run_command(l_cmd, console=1)
        except CommandFailed as cf:
            '''Node is not present '''
            return 0

        return 1

    def get_OpalSwXstop(self):
        self.proc_gen = self.cv_HOST.host_get_proc_gen(console=1)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        try:
            o = self.cv_HOST.host_run_command("nvram -p ibm,skiboot --print-config=opal-sw-xstop", console=1)
            '''
            On a fresh system this isn't set. The command will exit with
            exitcode = 255.
            On power8 we treat this as enabled
            On power9 we treat this as disable.
            '''
        except CommandFailed as cf:
            if cf.exitcode == 255:
                if self.proc_gen in ["POWER8", "POWER8E"]:
                    return "enable"
                elif self.proc_gen in ["POWER9"]:
                    return "disable"
            else:
                self.assertTrue(False, "get_OpalSwXstop() failed to query nvram.")
        return o

    def set_OpalSwXstop(self, val):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        o = self.get_OpalSwXstop()
        if val in o:
            return

        l_cmd = "nvram -p ibm,skiboot --update-config opal-sw-xstop=%s" % val
        self.cv_HOST.host_run_command(l_cmd, console=1)
        o = self.get_OpalSwXstop()
        if val in o:
            pass
        else:
            l_msg = "Failed to set opal-sw-xstop config to %s" % val
            self.assertTrue(False, l_msg)

    def clearGardEntries(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        expect_prompt = self.cv_SYSTEM.util.build_prompt()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        if "FSP" in self.bmc_type:
            # maybe add gard --dg to first check if None to skip power cycle ?
            res = self.cv_FSP.fspc.run_command("gard --clr all")
            self.assertIn("Success in clearing Gard Data", res,
                "Failed to clear GARD entries")
            log.debug(self.cv_FSP.fspc.run_command("gard --gc cpu"))
        else:
            my_term = self.cv_SYSTEM.console
            my_pty = my_term.get_console()
            my_term.run_command("date") # just need to run to get console setup
            cmd_list_all = "PATH=/usr/local/sbin:$PATH opal-gard list all"
            my_pty.sendline(cmd_list_all)
            rc = my_pty.expect([expect_prompt, "Clear the entire GUARD", pexpect.TIMEOUT, pexpect.EOF], timeout=60)
            log.debug("rc={}".format(rc))
            log.debug("list before={}".format(my_pty.before))
            log.debug("list after={}".format(my_pty.after))
            if rc == 0:
                output = []
                output += my_pty.before.replace("\r\r\n","\n").splitlines()
                try:
                    del output[:1] # remove command from the list
                except Exception as e:
                    pass # nothing there
                log.debug("LIST output={}".format(output))
                if "No GARD entries to display" in output:
                    log.debug("No GARD, so keep on")
                    return # all good so keep on
                else:
                    log.debug("GOT GARD to clear")
                    cmd_clear_all = "PATH=/usr/local/sbin:$PATH opal-gard clear all"
                    my_pty.sendline(cmd_clear_all)
                    rc = my_pty.expect([expect_prompt, "Clear the entire GUARD", pexpect.TIMEOUT, pexpect.EOF], timeout=60)
                    log.debug("GARD Clear rc={}".format(rc))
                    log.debug("GARD Clear before={}".format(my_pty.before))
                    log.debug("GARD Clear after={}".format(my_pty.after))
                    if rc == 0:
                        output = []
                        output += my_pty.before.replace("\r\r\n","\n").splitlines()
                        try:
                            del output[:1] # remove command from the list
                        except Exception as e:
                            pass # nothing there
                        log.debug("GARD Clear output={}".format(output))
                    if rc == 1:
                        my_pty.sendline("y")
                        rc = my_pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=60)
                        log.debug("GARD Clear Y rc={}".format(rc))
                        log.debug("GARD Clear Y before={}".format(my_pty.before))
                        log.debug("GARD Clear Y after={}".format(my_pty.after))
                        if rc != 0:
                            self.assertTrue(False, "We failed to clear the GARD, review the debug log.")
                        else:
                            log.debug("GARD CLEAR Y completed.")
            if rc in [1]:
                my_pty.sendline("y")
                rc = my_pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=60)
                log.debug("LIST rc={}".format(rc))
                log.debug("LIST before={}".format(my_pty.before))
                log.debug("LIST after={}".format(my_pty.after))
                if rc != 0:
                    self.assertTrue(False, "We tried to clear the GARD, but did not get the prompt back")
                else:
                    log.debug("GARD LIST Clear Y completed.")
            elif rc in [2,3]: # we timed out, so we got something other than what we expected
                self.assertTrue(False, "We timed out or EOF from trying to clear the GARD, review the debug log.")

            cmd_list_all = "PATH=/usr/local/sbin:$PATH opal-gard list all"
            my_pty.sendline(cmd_list_all)
            rc = my_pty.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=60)
            log.debug("FINAL GARD LIST rc={}".format(rc))
            log.debug("FINAL before={}".format(my_pty.before))
            log.debug("FINAL after={}".format(my_pty.after))
            if rc == 0:
                output = []
                output += my_pty.before.replace("\r\r\n","\n").splitlines()
                try:
                   del output[:1] # remove command from the list
                except Exception as e:
                   pass # nothing there
                log.debug("FINAL output={}".format(output))
                if "No GARD entries to display" not in output:
                    self.assertTrue(False, "We failed to get the prompt back from trying to clear the GARD entries")
                else: # we had something to clear and confirmed we cleared, but now we reboot
                    log.debug("ALL confirmed clear GARD")

        log.debug("We must have had GARD cleared, so we are going to Power OFF, then boot to OS")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def _testHMIHandling(self, i_test):
        '''
        This function executes HMI test case based on the i_test value, Before test starts
        disabling kdump service to make sure system reboots, after injecting non-recoverable errors.

        i_test (type int): this is the type of test case want to execute

        BMC_CONST.HMI_PROC_RECV_DONE
          Processor recovery done
        BMC_CONST.HMI_PROC_RECV_ERROR_MASKED
          proc_recv_error_masked
        BMC_CONST.HMI_MALFUNCTION_ALERT
          malfunction_alert
        BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR
          hypervisor resource error
        '''
        l_test = i_test
        self.init_test()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        l_con = self.cv_SYSTEM.console
        l_con.run_command("uname -a")
        l_con.run_command("cat /etc/os-release")
        l_con.run_command("lscpu") # bug https://bugs.launchpad.net/ubuntu/+source/util-linux/+bug/1732865
        l_con.run_command("dmesg -D")
        if l_test == BMC_CONST.HMI_PROC_RECV_DONE:
            self._test_proc_recv_done()
        elif l_test == BMC_CONST.HMI_PROC_RECV_ERROR_MASKED:
            self._test_proc_recv_error_masked()
        elif l_test == BMC_CONST.HMI_MALFUNCTION_ALERT:
            self._test_malfunction_alert()
        elif l_test == BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR:
            self._test_hyp_resource_err()
        elif l_test == BMC_CONST.TOD_ERRORS:
            # TOD Error recovery works on systems having more than one chip TOD
            # Skip this test on single chip systems(as recovery fails on 1S systems)
            if len(self.l_dic) == 1:
                l_msg = "This is a single chip system, TOD Error recovery won't work"
                log.debug(l_msg)
                return BMC_CONST.FW_SUCCESS
            elif len(self.l_dic) > 1:
                self._test_tod_errors(BMC_CONST.PSS_HAMMING_DISTANCE)
                self._test_tod_errors(BMC_CONST.INTERNAL_PATH_OR_PARITY_ERROR)
                self._test_tod_errors(BMC_CONST.TOD_DATA_PARITY_ERROR)
                self._test_tod_errors(BMC_CONST.TOD_SYNC_CHECK_ERROR)
                self._test_tod_errors(BMC_CONST.FSM_STATE_PARITY_ERROR)
                self._test_tod_errors(BMC_CONST.MASTER_PATH_CONTROL_REGISTER)
                self._test_tod_errors(BMC_CONST.PORT_0_PRIMARY_CONFIGURATION_REGISTER)
                self._test_tod_errors(BMC_CONST.PORT_1_PRIMARY_CONFIGURATION_REGISTER)
                self._test_tod_errors(BMC_CONST.PORT_0_SECONDARY_CONFIGURATION_REGISTER)
                self._test_tod_errors(BMC_CONST.PORT_1_SECONDARY_CONFIGURATION_REGISTER)
                self._test_tod_errors(BMC_CONST.SLAVE_PATH_CONTROL_REGISTER)
                self._test_tod_errors(BMC_CONST.INTERNAL_PATH_CONTROL_REGISTER)
                self._test_tod_errors(BMC_CONST.PR_SC_MS_SL_CONTROL_REGISTER)
            else:
                raise Exception("Getting Chip information failed")
        elif l_test == BMC_CONST.TFMR_ERRORS:
            self._testTFMR_Errors(BMC_CONST.TB_PARITY_ERROR)
            self._testTFMR_Errors(BMC_CONST.TFMR_PARITY_ERROR)
            self._testTFMR_Errors(BMC_CONST.TFMR_HDEC_PARITY_ERROR)
            self._testTFMR_Errors(BMC_CONST.TFMR_DEC_PARITY_ERROR)
            self._testTFMR_Errors(BMC_CONST.TFMR_PURR_PARITY_ERROR)
            self._testTFMR_Errors(BMC_CONST.TFMR_SPURR_PARITY_ERROR)
        elif l_test == BMC_CONST.HMI_TOD_TOPOLOGY_FAILOVER:
            self._test_tod_topology_failover()
        else:
            raise Exception("Please provide valid test case")
        l_con.run_command("dmesg -C")

    def _test_proc_recv_done(self):
        '''
        This function is used to test HMI: processor recovery done
        and also this function injecting error on all the cpus one by one and
        verify whether cpu is recovered or not.
        '''
        if self.proc_gen in ["POWER9"]:
            scom_addr = "20010A40"
        elif self.proc_gen in ["POWER8", "POWER8E"]:
            scom_addr = "10013100"
        else:
            return

        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = self.form_scom_addr(scom_addr, l_core)
                l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s 0000000000100000" % (l_chip, l_reg)
                # recoverable errors may not succeed all the time and
                # ssh may terminate due to soft/hard lockups so use console
                console = self.cv_SYSTEM.console
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd,timeout=20)
                except CommandFailed as cf:
                    l_res = cf.output
                    if cf.exitcode == 1:
                        pass
                    else:
                        if any("Kernel panic - not syncing" in line for line in l_res):
                            raise Exception("Processor recovery failed: Kernel got panic")
                        elif any("Petitboot" in line for line in l_res):
                            raise Exception("System reached petitboot:Processor recovery failed")
                        elif any("ISTEP" in line for line in l_res):
                            raise Exception("System started booting: Processor recovery failed")
                        else:
                            raise Exception("Failed to inject thread hang recoverable error %s", str(cf))
                time.sleep(0.2)
                l_res = console.run_command("dmesg")
                self.verify_proc_recovery(l_res)
        return

    def _test_proc_recv_error_masked(self):
        '''
        This function is used to test HMI: proc_recv_error_masked
        Processor went through recovery for an error which is actually masked for reporting
        this function also injecting the error on all the cpu's one-by-one.
        '''
        if self.proc_gen in ["POWER8", "POWER8E"]:
            scom_addr = "10013100"
        else:
            return

        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = self.form_scom_addr(scom_addr, l_core)
                l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s 0000000000080000" % (l_chip, l_reg)
                # recoverable errors may not succeed all the time and
                # ssh may terminate due to soft/hard lockups so use console
                console = self.cv_SYSTEM.console
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd, timeout=20)
                except CommandFailed as cf:
                    l_res = cf.output
                    if cf.exitcode == 1:
                        pass
                    else:
                        if any("Kernel panic - not syncing" in line for line in l_res):
                            raise Exception("Processor recovery failed: Kernel got panic")
                        elif any("Petitboot" in line for line in l_res):
                            raise Exception("System reached petitboot:Processor recovery failed")
                        elif any("ISTEP" in line for line in l_res):
                            raise Exception("System started booting: Processor recovery failed")
                        else:
                            raise Exception("Failed to inject thread hang recoverable error %s", str(cf))
                time.sleep(0.2)
                l_res = console.run_command("dmesg")
                self.verify_proc_recovery(l_res)
        return

    def _test_malfunction_alert(self):
        '''
        This function is used to test hmi malfunction alert:Core checkstop
        A processor core in the system has to be checkstopped (failed recovery).
        Injecting core checkstop on random core of random chip
        '''
        if self.proc_gen in ["POWER9"]:
            scom_addr = "20010A40"
        elif self.proc_gen in ["POWER8", "POWER8E"]:
            scom_addr = "10013100"
        else:
            return

        # Get random pair of chip vs cores
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        # Get random core number
        l_core = random.choice(l_pair[1])

        l_reg = self.form_scom_addr(scom_addr, l_core)
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s 1000000000000000" % (l_chip, l_reg)

        # Core checkstop will lead to system IPL, so we will wait for certain time for IPL
        # to finish
        # recoverable errors may not succeed all the time and
        # ssh may terminate due to soft/hard lockups so use console
        console = self.cv_SYSTEM.console
        res = console.run_command("uname -a") # perform any command to make sure console is logged in

        # now can send raw pexpect commands which assume log in
        console.pty.sendline(l_cmd)
        self.handle_ipl()

    def _test_tod_topology_failover(self):
        '''
        This function is used to test error path for hmi TOD topology failover.
        On HMI recovery failure TOD/TB goes in invalid state and stops running.
        In this case kernel should either
        a) panic followed by clean reboot. (For opal-sw-xstop=disable)
            OR
        b) cause OPAL TI by triggering sw checkstop to OCC. (For
           opal-sw-xstop=enable)

        In both cases we should not see any hangs at Linux OS level.
        To simulate error condition inject TOD topology failover on all the
        chips until we see HMI failure.
        '''
        scom_addr = "0x40000"
        l_error = "0x4000000000000000"
        l_test_mode = "TI"

        g = self.get_OpalSwXstop()
        if "disable" in g:
            l_test_mode="panic"

        console = self.cv_SYSTEM.console
        l_cmd = ""
        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            l_cmd_str = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s; " % (l_chip, scom_addr, l_error)
            l_cmd = l_cmd + l_cmd_str

        console.pty.sendline(l_cmd)
        if l_test_mode == "panic":
            self.handle_panic()
        else:
            self.handle_OpalTI()

        return

    def _test_hyp_resource_err(self):
        '''
        This function is used to test HMI: Hypervisor resource error
        Injecting Hypervisor resource error on random core of random chip
        '''
        if self.proc_gen in ["POWER9"]:
            scom_addr = "20010A40"
        elif self.proc_gen in ["POWER8", "POWER8E"]:
            scom_addr = "10013100"
        else:
            return

        # Get random pair of chip vs cores
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        # Get random core number
        l_core = random.choice(l_pair[1])

        l_reg = self.form_scom_addr(scom_addr, l_core)
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s 0000000000008000" % (l_chip, l_reg)

        console = self.cv_SYSTEM.console
        res = console.run_command("uname -a") # perform any command to make sure console is logged in

        # now can send raw pexpect commands which assume log in
        console.pty.sendline(l_cmd)
        self.handle_ipl()

    def _testTFMR_Errors(self, i_error):
        '''
        This function tests timer facility related error injections and check
        the corresponding error got recovered. And this process is repeated
        for all the active cores in all the chips.

        `i_error` string: this is the type of error want to inject

        - BMC_CONST.TB_PARITY_ERROR
        - BMC_CONST.TFMR_PARITY_ERROR
        - BMC_CONST.TFMR_HDEC_PARITY_ERROR
        - BMC_CONST.TFMR_DEC_PARITY_ERROR
        - BMC_CONST.TFMR_PURR_PARITY_ERROR
        - BMC_CONST.TFMR_SPURR_PARITY_ERROR
        '''
        if self.proc_gen in ["POWER9"]:
            scom_addr = "20010A84"
        elif self.proc_gen in ["POWER8", "POWER8E"]:
            scom_addr = "10013281"
        else:
            return

        l_error = i_error
        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = self.form_scom_addr(scom_addr, l_core)
                l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (l_chip, l_reg, l_error)
                # recoverable errors may not succeed all the time and
                # ssh may terminate due to soft/hard lockups so use console
                console = self.cv_SYSTEM.console
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd, timeout=20)
                except CommandFailed as cf:
                    l_res = cf.output
                    if cf.exitcode == 1:
                        pass
                    else:
                        if any("Kernel panic - not syncing" in line for line in l_res):
                            l_msg = "TFMR error injection: Kernel got panic"
                        elif any("Petitboot" in line for line in l_res):
                            l_msg = "System reached petitboot:TFMR error injection recovery failed"
                        elif any("ISTEP" in line for line in l_res):
                            l_msg = "System started booting: TFMR error injection recovery failed"
                        else:
                            raise Exception("Failed to inject TFMR error %s " % str(cf))

                time.sleep(0.2)
                l_res = console.run_command("dmesg")
                self.verify_timer_facility_recovery(l_res)
        return

    def _test_tod_errors(self, i_error):
        '''
        This function tests chip TOD related error injections and check
        the corresponding error got recovered. And this error injection
        happening on a random chip. This tod errors should test on systems
        having more than one processor socket(chip). On single chip system
        TOD error recovery won't work.

        @param i_error @type string: this is the type of error want to inject
                               These errors represented in common/OpTestConstants.py file.
        '''
        l_error = i_error
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (l_chip, BMC_CONST.TOD_ERROR_REG, l_error)
        console = self.cv_SYSTEM.console
        console.run_command("dmesg -C")

        # As of now putscom command to TOD register will fail with return code -1.
        # putscom indirectly call getscom to read the value again.
        # But getscom to TOD error reg there is no access
        # TOD Error reg has only WO access and there is no read access
        try:
            l_res = console.run_command(l_cmd, timeout=20)
        except CommandFailed as cf:
            l_res = cf.output
            if cf.exitcode == 1:
                pass
            else:
                if any("Kernel panic - not syncing" in line for line in l_res):
                    log.debug("TOD ERROR Injection-kernel got panic")
                elif any("login:" in line for line in l_res):
                    log.debug("System booted to host OS without any kernel panic message")
                elif any("Petitboot" in line for line in l_res):
                    log.debug("System reached petitboot without any kernel panic message")
                elif any("ISTEP" in line for line in l_res):
                    log.debug("System started booting without any kernel panic message")
                else:
                    raise Exception("TOD: PSS Hamming distance error injection failed %s", str(cf))
        time.sleep(0.2)
        l_res = console.run_command("dmesg")
        self.verify_timer_facility_recovery(l_res)
        return

class HMI_TFMR_ERRORS(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.TFMR_ERRORS)

class TOD_ERRORS(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.TOD_ERRORS)

class SingleCoreTOD_ERRORS(OpTestHMIHandling):
    def setUp(self):
        super(SingleCoreTOD_ERRORS, self).setUp()
        self.cv_HOST.host_enable_single_core(console=1)

    def runTest(self):
        self._testHMIHandling(BMC_CONST.TOD_ERRORS)

class PROC_RECOV_DONE(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.HMI_PROC_RECV_DONE)

class PROC_RECV_ERROR_MASKED(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.HMI_PROC_RECV_ERROR_MASKED)

class MalfunctionAlert(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.HMI_MALFUNCTION_ALERT)
        self.clearGardEntries()

class TodTopologyFailoverPanic(OpTestHMIHandling):
    def runTest(self):
        self.set_OpalSwXstop("disable")
        self._testHMIHandling(BMC_CONST.HMI_TOD_TOPOLOGY_FAILOVER)

class TodTopologyFailoverOpalTI(OpTestHMIHandling):
    def runTest(self):
        rc = self.is_node_present("/proc/device-tree/ibm,sw-checkstop-fir")
        if rc == 1:
            self.set_OpalSwXstop("enable")
            self._testHMIHandling(BMC_CONST.HMI_TOD_TOPOLOGY_FAILOVER)
        else:
            self.skipTest("OPAL TI not supported on this system.")

class HypervisorResourceError(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR)
        self.clearGardEntries()

class ClearGard(OpTestHMIHandling):
    def runTest(self):
        self.clearGardEntries()

def unrecoverable_suite():
    s = unittest.TestSuite()
    s.addTest(MalfunctionAlert())
    s.addTest(HypervisorResourceError())
    s.addTest(TodTopologyFailoverPanic())
    s.addTest(TodTopologyFailoverOpalTI())
    s.addTest(ClearGard())
    return s

def suite():
    s = unittest.TestSuite()
    s.addTest(HMI_TFMR_ERRORS())
    s.addTest(PROC_RECOV_DONE())
    s.addTest(PROC_RECV_ERROR_MASKED())
    s.addTest(TOD_ERRORS())
    return s

def experimental_suite():
    s = unittest.TestSuite()
    s.addTest(TOD_ERRORS())
    s.addTest(SingleCoreTOD_ERRORS())
    return s
