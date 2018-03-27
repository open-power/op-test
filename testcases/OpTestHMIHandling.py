#!/usr/bin/python2
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

# @package OpTestHMIHandling
#  HMI Handling package for OpenPower testing.
#
#  This class will test the functionality of following.
#  1. HMI Non-recoverable errors - Core checkstop and Hypervisor resource error
#  2. HMI Recoverable errors- proc_recv_done, proc_recv_error_masked and proc_recv_again
#  3. TFMR error injections
#  4. chip TOD error injections

import time
import subprocess
import re
import sys
import os
import random
import pexpect

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.OpTestIPMI import IPMIConsoleState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

class OpTestHMIHandling(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_FSP = conf.bmc()
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type
        self.util = OpTestUtil()

    def ipmi_monitor_sol_ipl(self, console, timeout):
        # Error injection causing the SOL console to terminate immediately.
        # So Let's re-connect the console
        console.close()
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        try:
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        except:
            self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            self.cv_SYSTEM.set_state(OpSystemState.OS)
        console.close()
        print "System booted fine to host OS..."
        return BMC_CONST.FW_SUCCESS

    def verify_proc_recovery(self, l_res):
        if any("Processor Recovery done" in line for line in l_res) and \
            any("Harmless Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
            print "Processor recovery done"
            return
        else:
            raise Exception("HMI handling failed to log message: for proc_recv_done")

    def verify_timer_facility_recovery(self, l_res):
        if any("Timer facility experienced an error" in line for line in l_res) and \
            any("Severe Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
            print "Timer facility experienced an error and got recovered"
            return
        else:
            raise Exception("HMI handling failed to log message")

    def init_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.proc_gen = self.cv_HOST.host_get_proc_gen()

        l_chips = self.cv_HOST.host_get_list_of_chips() # ['00000000', '00000001', '00000010']
        if not l_chips:
            raise Exception("Getscom failed to list processor chip ids")

        l_cores = self.cv_HOST.host_get_cores()
        if not l_cores:
            raise Exception("Failed to get list of core id's")

        print l_cores # {0: ['4', '5', '6', 'c', 'd', 'e'], 1: ['4', '5', '6', 'c', 'd', 'e'], 10: ['4', '5', '6', 'c', 'd', 'e']}
        # Remove master core where injecting core checkstop leads to IPL expected failures
        # after 2 failures system will starts boot in Golden side of PNOR
        l_cores[0][1].pop(0)
        print l_cores
        self.l_dic = []
        i=0
        for tup in l_cores:
            new_list = [l_chips[i], tup[1]]
            self.l_dic.append(new_list)
            i+=1
        print self.l_dic
        # self.l_dic is a list of chip id's, core id's . and is of below format 
        # [['00000000', ['4', '5', '6', 'c', 'd', 'e']], ['00000001', ['4', '5', '6', 'c', 'd', 'e']], ['00000010', ['4', '5', '6', 'c', 'd', 'e']]]

        # In-order to inject HMI errors on cpu's, cpu should be running, so disabling the sleep states 1 and 2 of all CPU's
        self.disable_cpu_idle_states()

        # Disable kdump to check behaviour of IPL caused due to kernel panic after injection of core/system checkstop
        self.disable_kdump_service()


    def disable_kdump_service(self):
        l_oslevel = self.cv_HOST.host_get_OS_Level()
        try:
            if "Ubuntu" in l_oslevel:
                self.cv_HOST.host_run_command("service kdump-tools stop")
            else:
                self.cv_HOST.host_run_command("service kdump stop")
        except CommandFailed as cf:
            if cf.exitcode == 5:
                # kdump may not be enabled, so it's not a failure to stop it
                pass

    # Disable all CPU idle states except snooze state
    def disable_cpu_idle_states(self):
        states = self.cv_HOST.host_run_command("find /sys/devices/system/cpu/cpu*/cpuidle/state* -type d | cut -d'/' -f8 | sort -u | sed -e 's/^state//'")
        for state in states:
            if state is "0":
                self.cv_HOST.host_run_command("cpupower idle-set -e 0")
                continue
            self.cv_HOST.host_run_command("cpupower idle-set -d %s" % state)

    def form_scom_addr(self, addr, core):
        if self.proc_gen in ["POWER8", "POWER8E"]:
            val = addr[0]+str(core)+addr[2:]
        elif self.proc_gen in ["POWER9"]:
            val = hex(eval("0x%s | (((%s & 0x1f) + 0x20) << 24)" % (addr, int(core, 16))))
            print val
        return val

    def clearGardEntries(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        if "FSP" in self.bmc_type:
            res = self.cv_FSP.fspc.run_command("gard --clr all")
            self.assertIn("Success in clearing Gard Data", res,
                "Failed to clear GARD entries")
            print self.cv_FSP.fspc.run_command("gard --gc cpu")
        else:
            g = self.cv_HOST.host_run_command("PATH=/usr/local/sbin:$PATH opal-gard list all")
            if "No GARD entries to display" not in g:
                self.cv_HOST.host_run_command("PATH=/usr/local/sbin:$PATH opal-gard clear all")
                cleared_gard = self.cv_HOST.host_run_command("PATH=/usr/local/sbin:$PATH opal-gard list")
                self.assertIn("No GARD entries to display", cleared_gard,
                              "Failed to clear GARD entries")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    ##
    # @brief This function executes HMI test case based on the i_test value, Before test starts
    #        disabling kdump service to make sure system reboots, after injecting non-recoverable errors.
    #
    # @param i_test @type int: this is the type of test case want to execute
    #                          BMC_CONST.HMI_PROC_RECV_DONE: Processor recovery done
    #                          BMC_CONST.HMI_PROC_RECV_ERROR_MASKED: proc_recv_error_masked
    #                          BMC_CONST.HMI_MALFUNCTION_ALERT: malfunction_alert
    #                          BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR: hypervisor resource error
    def _testHMIHandling(self, i_test):
        l_test = i_test
        self.init_test()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con.run_command("uname -a")
        l_con.run_command("cat /etc/os-release")
        l_con.run_command("lscpu")
        l_con.run_command("dmesg -D")
        if l_test == BMC_CONST.HMI_PROC_RECV_DONE:
            self._test_proc_recv_done()
        elif l_test == BMC_CONST.HMI_PROC_RECV_ERROR_MASKED:
            self._test_proc_recv_error_masked()
        elif l_test == BMC_CONST.HMI_MALFUNCTION_ALERT:
            self._test_malfunction_allert()
        elif l_test == BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR:
            self._test_hyp_resource_err()
        elif l_test == BMC_CONST.TOD_ERRORS:
            # TOD Error recovery works on systems having more than one chip TOD
            # Skip this test on single chip systems(as recovery fails on 1S systems)
            if len(self.l_dic) == 1:
                l_msg = "This is a single chip system, TOD Error recovery won't work"
                print l_msg
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
        else:
            raise Exception("Please provide valid test case")
        self.cv_HOST.ssh.state = SSHConnectionState.DISCONNECTED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to test HMI: processor recovery done
    #        and also this function injecting error on all the cpus one by one and 
    #        verify whether cpu is recovered or not.
    def _test_proc_recv_done(self):
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
                console = self.cv_SYSTEM.sys_get_ipmi_console()
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd,timeout=120)
                except CommandFailed as cf:
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

    ##
    # @brief This function is used to test HMI: proc_recv_error_masked
    #        Processor went through recovery for an error which is actually masked for reporting
    #        this function also injecting the error on all the cpu's one-by-one.
    def _test_proc_recv_error_masked(self):
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
                l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s 0000000000080000" % (l_chip, l_reg)
                console = self.cv_SYSTEM.sys_get_ipmi_console()
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd, timeout=120)
                except CommandFailed as cf:
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

    ##
    # @brief This function is used to test hmi malfunction alert:Core checkstop
    #        A processor core in the system has to be checkstopped (failed recovery).
    #        Injecting core checkstop on random core of random chip
    def _test_malfunction_allert(self):
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
        #l_res = self.cv_SYSTEM.sys_get_ipmi_console().run_command(l_cmd, timeout=600)
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        console.sol.sendline(l_cmd)
        self.ipmi_monitor_sol_ipl(console, timeout=600)

    ##
    # @brief This function is used to test HMI: Hypervisor resource error
    #        Injecting Hypervisor resource error on random core of random chip
    def _test_hyp_resource_err(self):
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

        console = self.cv_SYSTEM.sys_get_ipmi_console()
        console.sol.sendline(l_cmd)
        self.ipmi_monitor_sol_ipl(console, timeout=600)

    ##
    # @brief This function tests timer facility related error injections and check
    #        the corresponding error got recovered. And this process is repeated
    #        for all the active cores in all the chips.
    #
    # @param i_error @type string: this is the type of error want to inject
    #                          BMC_CONST.TB_PARITY_ERROR
    #                          BMC_CONST.TFMR_PARITY_ERROR
    #                          BMC_CONST.TFMR_HDEC_PARITY_ERROR
    #                          BMC_CONST.TFMR_DEC_PARITY_ERROR
    #                          BMC_CONST.TFMR_PURR_PARITY_ERROR
    #                          BMC_CONST.TFMR_SPURR_PARITY_ERROR
    def _testTFMR_Errors(self, i_error):
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
                console = self.cv_SYSTEM.sys_get_ipmi_console()
                console.run_command("dmesg -C")
                try:
                    l_res = console.run_command(l_cmd, timeout=120)
                except CommandFailed as cf:
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

    ##
    # @brief This function tests chip TOD related error injections and check
    #        the corresponding error got recovered. And this error injection
    #        happening on a random chip. This tod errors should test on systems
    #        having more than one processor socket(chip). On single chip system
    #        TOD error recovery won't work.
    #
    # @param i_error @type string: this is the type of error want to inject
    #                       These errors represented in common/OpTestConstants.py file.
    def _test_tod_errors(self, i_error):
        l_error = i_error
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (l_chip, BMC_CONST.TOD_ERROR_REG, l_error)
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        console.run_command("dmesg -C")

        # As of now putscom command to TOD register will fail with return code -1.
        # putscom indirectly call getscom to read the value again.
        # But getscom to TOD error reg there is no access
        # TOD Error reg has only WO access and there is no read access
        try:
            l_res = console.run_command(l_cmd, timeout=120)
        except CommandFailed as cf:
            if cf.exitcode == 1:
                pass
            else:
                if any("Kernel panic - not syncing" in line for line in l_res):
                    print "TOD ERROR Injection-kernel got panic"
                elif any("login:" in line for line in l_res):
                    print "System booted to host OS without any kernel panic message"
                elif any("Petitboot" in line for line in l_res):
                    print "System reached petitboot without any kernel panic message"
                elif any("ISTEP" in line for line in l_res):
                    print "System started booting without any kernel panic message"
                else:
                    raise Exception("TOD: PSS Hamming distance error injection failed %s", str(c))
        time.sleep(0.2)
        l_res = console.run_command("dmesg")
        self.verify_timer_facility_recovery(l_res)
        return

    ##
    # @brief This function enables a single core
    def host_enable_single_core(self):
        self.cv_HOST.host_enable_single_core()

class HMI_TFMR_ERRORS(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.TFMR_ERRORS)

class TOD_ERRORS(OpTestHMIHandling):
    def runTest(self):
        self._testHMIHandling(BMC_CONST.TOD_ERRORS)

class SingleCoreTOD_ERRORS(OpTestHMIHandling):
    def runTest(self):
        self.host_enable_single_core()
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

class HypervisorResourceError(OpTestHMIHandling):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        super(HypervisorResourceError, self).setUp()

    def runTest(self):
        self._testHMIHandling(BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR)

class ClearGard(OpTestHMIHandling):
    def runTest(self):
        self.clearGardEntries()

def unrecoverable_suite():
    s = unittest.TestSuite()
    s.addTest(MalfunctionAlert())
    s.addTest(HypervisorResourceError())
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
