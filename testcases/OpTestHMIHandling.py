#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestHMIHandling.py $
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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestLpar import OpTestLpar
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestHMIHandling():
    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_lparip, i_lparuser, i_lparPasswd)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_lparip,
                 i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This is a common function for all the hmi test cases. This will be executed before
    #        any test case starts. Basically this provides below requirements.
    #        1. Validates all required lpar commands
    #        2. It will clone skiboot source repository
    #        3. Compile the necessary tools xscom-utils and gard utility to test HMI.
    #        4. Get the list Of Chips and cores in the form of dictionary.
    #           Ex: [['00000000', ['4', '5', '6', 'c', 'd', 'e']], ['00000001', ['4', '5', '6', 'c', 'd', 'e']], ['00000010', ['4', '5', '6', 'c', 'd', 'e']]]
    #        5. In-order to inject HMI errors on cpu's, cpu should be running,
    #           so disabling the sleep states 1 and 2 of all CPU's.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_init(self):
        # Get OS level
        self.cv_LPAR.lpar_get_OS_Level()

        # Check whether git and gcc commands are available on lpar
        self.cv_LPAR.lpar_check_command("git")
        self.cv_LPAR.lpar_check_command("gcc")

        # It will clone skiboot source repository
        l_dir = "/tmp/skiboot"
        self.cv_LPAR.lpar_clone_skiboot_source(l_dir)
        # Compile the necessary tools xscom-utils and gard utility
        self.cv_LPAR.lpar_compile_xscom_utilities(l_dir)
        self.cv_LPAR.lpar_compile_gard_utility(l_dir)

        # Getting list of processor chip Id's(executing getscom -l to get chip id's)
        l_res = self.cv_LPAR.lpar_run_command("cd %s/external/xscom-utils/; ./getscom -l" % l_dir)
        l_res = l_res.splitlines()
        l_chips = []
        for line in l_res:
            matchObj = re.search("(\d{8}).*processor", line)
            if matchObj:
                l_chips.append(matchObj.group(1))
        if not l_chips:
            l_msg = "Getscom failed to list processor chip id's"
            raise OpTestError(l_msg)
        l_chips.sort()
        print l_chips # ['00000000', '00000001', '00000010']

        # Currently getting the list of active core id's with respect to each chip is by using opal msg log
        # TODO: Need to identify best way to get list of cores(If Opal msg log is empty)
        l_cmd = "cat /sys/firmware/opal/msglog | grep -i CHIP"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        l_cores = {}
        self.l_dic = []
        l_res = l_res.splitlines()
        for line in l_res:
            matchObj = re.search("Chip (\d{1,2}) Core ([a-z0-9])", line)
            if matchObj:
                if l_cores.has_key(int(matchObj.group(1))):
                    (l_cores[int(matchObj.group(1))]).append(matchObj.group(2))
                else:
                    l_cores[int(matchObj.group(1))] = list(matchObj.group(2))
        if not l_cores:
            l_msg = "Failed in getting core id's information from OPAL msg log"
            raise OpTestError(l_msg)

        print l_cores # {0: ['4', '5', '6', 'c', 'd', 'e'], 1: ['4', '5', '6', 'c', 'd', 'e'], 10: ['4', '5', '6', 'c', 'd', 'e']}
        l_cores = sorted(l_cores.iteritems())
        print l_cores
        i=0
        for tup in l_cores:
            new_list = [l_chips[i], tup[1]]
            self.l_dic.append(new_list)
            i+=1
        print self.l_dic
        # self.l_dic is a list of chip id's, core id's . and is of below format 
        # [['00000000', ['4', '5', '6', 'c', 'd', 'e']], ['00000001', ['4', '5', '6', 'c', 'd', 'e']], ['00000010', ['4', '5', '6', 'c', 'd', 'e']]]

        self.l_dir = l_dir
        # In-order to inject HMI errors on cpu's, cpu should be running, so disabling the sleep states 1 and 2 of all CPU's
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE2)
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE1)
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE0)
        self.cv_LPAR.lpar_run_command(BMC_CONST.DISABLE_CPU_SLEEP_STATE1)
        self.cv_LPAR.lpar_run_command(BMC_CONST.DISABLE_CPU_SLEEP_STATE2)
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE2)
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE1)
        self.cv_LPAR.lpar_run_command(BMC_CONST.GET_CPU_SLEEP_STATE0)

    ##
    # @brief This function is mainly used to clear hardware gard entries.
    #        It will perform below steps
    #           1. Reboot the system(Power off/on)
    #           2. Clear any Hardware gard entries
    #           3. Again reboot the system, to make use of garded Hardware.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def clearGardEntries(self):
        # Power off and on the system.
        self.cv_IPMI.ipmi_power_off()
        self.cv_IPMI.ipmi_power_on()
        if int(self.cv_SYSTEM.sys_ipl_wait_for_working_state()):
            l_msg = "System failed to boot host OS"
            raise OpTestError(l_msg)
        time.sleep(BMC_CONST.LPAR_BRINGUP_TIME)

        # Clearing gard entries after lpar comes up
        self.cv_LPAR.lpar_get_OS_Level()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_lpar_login(l_con)
        self.cv_IPMI.ipmi_lpar_set_unique_prompt(l_con)
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("uname -a")
        l_dir = "/tmp/skiboot"
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("cd %s/external/gard/;" % l_dir)
        l_cmd = "./gard list; echo $?"
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
        l_cmd = "./gard clear all; echo $?"
        l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
        if int(l_res[-1]):
            l_msg = "Clearing gard entries through gard tool is failed"
            raise OpTestError(l_msg)
        l_cmd = "./gard list; echo $?"
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)

        # Rebooting the system again to make use of garded hardware
        self.cv_IPMI.ipmi_power_off()
        self.cv_IPMI.ipmi_power_on()
        if int(self.cv_SYSTEM.sys_ipl_wait_for_working_state()):
            l_msg = "System failed to boot host OS"
            raise OpTestError(l_msg)
        time.sleep(BMC_CONST.LPAR_BRINGUP_TIME)
        self.cv_LPAR.lpar_get_OS_Level()
        self.cv_SYSTEM.sys_ipmi_close_console(l_con)

    ##
    # @brief This function executes HMI test case based on the i_test value, Before test starts
    #        disabling kdump service to make sure system reboots, after injecting non-recoverable errors.
    #
    # @param i_test @type int: this is the type of test case want to execute
    #                          BMC_CONST.HMI_PROC_RECV_DONE: Processor recovery done
    #                          BMC_CONST.HMI_PROC_RECV_ERROR_MASKED: proc_recv_error_masked
    #                          BMC_CONST.HMI_MALFUNCTION_ALERT: malfunction_alert
    #                          BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR: hypervisor resource error
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def testHMIHandling(self, i_test):
        l_test = i_test
        self.test_init()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_lpar_login(l_con)
        self.cv_IPMI.ipmi_lpar_set_unique_prompt(l_con)
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("cat /etc/os-release")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("service kdump status")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("service kdump stop")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("service kdump status")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("cd %s/external/xscom-utils/;" % self.l_dir)
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("lscpu")
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg -D")
        if l_test == BMC_CONST.HMI_PROC_RECV_DONE:
            self.test_proc_recv_done()
        elif l_test == BMC_CONST.HMI_PROC_RECV_ERROR_MASKED:
            self.test_proc_recv_error_masked()
        elif l_test == BMC_CONST.HMI_MALFUNCTION_ALERT:
            self.test_malfunction_allert()
        elif l_test == BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR:
            self.test_hyp_resource_err()
        elif l_test == BMC_CONST.TOD_ERRORS:
            # TOD Error recovery works on systems having more than one chip TOD
            # Skip this test on single chip systems(as recovery fails on 1S systems)
            if len(self.l_dic) == 1:
                l_msg = "This is a single chip system, TOD Error recovery won't work"
                print l_msg
                return BMC_CONST.FW_SUCCESS
            elif len(self.l_dic) > 1:
                self.test_tod_errors(BMC_CONST.PSS_HAMMING_DISTANCE)
                self.test_tod_errors(BMC_CONST.INTERNAL_PATH_OR_PARITY_ERROR)
                self.test_tod_errors(BMC_CONST.TOD_DATA_PARITY_ERROR)
                self.test_tod_errors(BMC_CONST.TOD_SYNC_CHECK_ERROR)
                self.test_tod_errors(BMC_CONST.FSM_STATE_PARITY_ERROR)
                self.test_tod_errors(BMC_CONST.MASTER_PATH_CONTROL_REGISTER)
                self.test_tod_errors(BMC_CONST.PORT_0_PRIMARY_CONFIGURATION_REGISTER)
                self.test_tod_errors(BMC_CONST.PORT_1_PRIMARY_CONFIGURATION_REGISTER)
                self.test_tod_errors(BMC_CONST.PORT_0_SECONDARY_CONFIGURATION_REGISTER)
                self.test_tod_errors(BMC_CONST.PORT_1_SECONDARY_CONFIGURATION_REGISTER)
                self.test_tod_errors(BMC_CONST.SLAVE_PATH_CONTROL_REGISTER)
                self.test_tod_errors(BMC_CONST.INTERNAL_PATH_CONTROL_REGISTER)
                self.test_tod_errors(BMC_CONST.PR_SC_MS_SL_CONTROL_REGISTER)
            else:
                l_msg = "Getting Chip information failed"
                raise OpTestError(l_msg)
        elif l_test == BMC_CONST.TFMR_ERRORS:
            self.testTFMR_Errors(BMC_CONST.TB_PARITY_ERROR)
            self.testTFMR_Errors(BMC_CONST.TFMR_PARITY_ERROR)
            self.testTFMR_Errors(BMC_CONST.TFMR_HDEC_PARITY_ERROR)
            self.testTFMR_Errors(BMC_CONST.TFMR_DEC_PARITY_ERROR)
            self.testTFMR_Errors(BMC_CONST.TFMR_PURR_PARITY_ERROR)
            self.testTFMR_Errors(BMC_CONST.TFMR_SPURR_PARITY_ERROR)
        else:
            l_msg = "Please provide valid test case"
            raise OpTestError(l_msg)
        self.cv_SYSTEM.sys_ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to test HMI: processor recovery done
    #        and also this function injecting error on all the cpus one by one and 
    #        verify whether cpu is recovered or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_proc_recv_done(self):
        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = "1%s013100" % l_core
                l_cmd = "./putscom -c %s %s 0000000000100000; echo $?" % (l_chip, l_reg)

                self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg -C")
                time.sleep(10)
                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
                time.sleep(10)
                if l_res[-1] == "0":
                    print "Injected thread hang recoverable error"
                else:
                    if any("Kernel panic - not syncing" in line for line in l_res):
                        l_msg = "Processor recovery failed: Kernel got panic"
                    elif any("Petitboot" in line for line in l_res):
                        l_msg = "System reached petitboot:Processor recovery failed"
                    elif any("ISTEP" in line for line in l_res):
                        l_msg = "System started booting: Processor recovery failed"
                    else:
                        l_msg = "Failed to inject thread hang recoverable error"
                    print l_msg
                    raise OpTestError(l_msg)

                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg")
                if any("Processor Recovery done" in line for line in l_res) and \
                any("Harmless Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
                    print "Processor recovery done"
                else:
                    l_msg = "HMI handling failed to log message: for proc_recv_done"
                    raise OpTestError(l_msg)
                time.sleep(BMC_CONST.HMI_TEST_CASE_SLEEP_TIME)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to test HMI: proc_recv_error_masked
    #        Processor went through recovery for an error which is actually masked for reporting
    #        this function also injecting the error on all the cpu's one-by-one.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_proc_recv_error_masked(self):
        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = "1%s013100" % l_core
                l_cmd = "./putscom -c %s %s 0000000000080000; echo $?" % (l_chip, l_reg)
                self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg -C")
                time.sleep(10)
                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
                time.sleep(10)
                if l_res[-1] == "0":
                    print "Injected thread hang recoverable error"
                else:
                    if any("Kernel panic - not syncing" in line for line in l_res):
                        l_msg = "Processor recovery failed: Kernel got panic"
                    elif any("Petitboot" in line for line in l_res):
                        l_msg = "System reached petitboot:Processor recovery failed"
                    elif any("ISTEP" in line for line in l_res):
                        l_msg = "System started booting: Processor recovery failed"
                    else:
                        l_msg = "Failed to inject thread hang recoverable error"
                    print l_msg
                    raise OpTestError(l_msg)

                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg")
                if any("Processor Recovery done" in line for line in l_res) and \
                any("Harmless Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
                    print "Processor recovery done"
                else:
                    l_msg = "HMI handling failed to log message"
                    raise OpTestError(l_msg)
                time.sleep(BMC_CONST.HMI_TEST_CASE_SLEEP_TIME)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to test hmi malfunction alert:Core checkstop
    #        A processor core in the system has to be checkstopped (failed recovery).
    #        Injecting core checkstop on random core of random chip
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_malfunction_allert(self):
        # Get random pair of chip vs cores
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        # Get random core number
        l_core = random.choice(l_pair[1])

        l_reg = "1%s013100" % l_core
        l_cmd = "./putscom -c %s %s 1000000000000000" % (l_chip, l_reg)

        l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
        if any("Kernel panic - not syncing" in line for line in l_res):
            print "Malfunction alert: kernel got panic"
        elif any("login:" in line for line in l_res):
            print "System booted to host OS without any kernel panic message"
        elif any("Petitboot" in line for line in l_res):
            print "System reached petitboot without any kernel panic message"
        elif any("ISTEP" in line for line in l_res):
            print "System started booting without any kernel panic message"
        else:
            l_msg = "HMI: Malfunction alert failed"
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to test HMI: Hypervisor resource error
    #        Injecting Hypervisor resource error on random core of random chip
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_hyp_resource_err(self):
        # Get random pair of chip vs cores
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        # Get random core number
        l_core = random.choice(l_pair[1])

        l_reg = "1%s013100" % l_core
        l_cmd = "./putscom -c %s %s 0000000000008000" % (l_chip, l_reg)

        l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
        if any("Kernel panic - not syncing" in line for line in l_res) and \
        any("Hypervisor Resource error - core check stop" in line for line in l_res):
            print "Hypervisor resource error: kernel got panic"
        elif any("login:" in line for line in l_res):
            print "System booted to host OS without any kernel panic message"
        elif any("Petitboot" in line for line in l_res):
            print "System reached petitboot without any kernel panic message"
        elif any("ISTEP" in line for line in l_res):
            print "System started booting without any kernel panic message"
        else:
            l_msg = "HMI: Hypervisor resource error failed"
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS

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
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def testTFMR_Errors(self, i_error):
        l_error = i_error
        for l_pair in self.l_dic:
            l_chip = l_pair[0]
            for l_core in l_pair[1]:
                l_reg = "1%s013281" % l_core
                l_cmd = "./putscom -c %s %s %s;echo $?" % (l_chip, l_reg, l_error)
                self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg -C")
                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
                time.sleep(10)
                if l_res[-1] == "0":
                    print "Injected TFMR error %s" % l_error
                else:
                    if any("Kernel panic - not syncing" in line for line in l_res):
                        l_msg = "TFMR error injection: Kernel got panic"
                    elif any("Petitboot" in line for line in l_res):
                        l_msg = "System reached petitboot:TFMR error injection recovery failed"
                    elif any("ISTEP" in line for line in l_res):
                        l_msg = "System started booting: TFMR error injection recovery failed"
                    else:
                        l_msg = "Failed to inject TFMR error %s " % l_error
                        print l_msg
                        raise OpTestError(l_msg)

                l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg")
                if any("Timer facility experienced an error" in line for line in l_res) and \
                    any("Severe Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
                    print "Timer facility experienced an error and got recovered"
                else:
                    l_msg = "HMI handling failed to log message"
                    raise OpTestError(l_msg)
                time.sleep(BMC_CONST.HMI_TEST_CASE_SLEEP_TIME)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function tests chip TOD related error injections and check
    #        the corresponding error got recovered. And this error injection
    #        happening on a random chip. This tod errors should test on systems
    #        having more than one processor socket(chip). On single chip system
    #        TOD error recovery won't work.
    #
    # @param i_error @type string: this is the type of error want to inject
    #                       These errors represented in common/OpTestConstants.py file.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_tod_errors(self, i_error):
        l_error = i_error
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        l_chip = l_pair[0]
        l_cmd = "./putscom -c %s %s %s;echo $?" % (l_chip, BMC_CONST.TOD_ERROR_REG, l_error)
        self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg -C")
        l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console(l_cmd)
        time.sleep(10)
        # As of now putscom command to TOD register will fail with return code -1.
        # putscom indirectly call getscom to read the value again.
        # But getscom to TOD error reg there is no access
        # TOD Error reg has only WO access and there is no read access
        if l_res[-1] == "1":
            print "Injected TOD error %s" % l_error
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
                l_msg = "TOD: PSS Hamming distance error injection failed"
                raise OpTestError(l_msg)
        l_res = self.cv_IPMI.run_lpar_cmd_on_ipmi_console("dmesg")
        if any("Timer facility experienced an error" in line for line in l_res) and \
            any("Severe Hypervisor Maintenance interrupt [Recovered]" in line for line in l_res):
            print "Timer facility experienced an error and got recovered"
        else:
            l_msg = "HMI handling failed to log message"
            raise OpTestError(l_msg)
        time.sleep(BMC_CONST.HMI_TEST_CASE_SLEEP_TIME)
        return BMC_CONST.FW_SUCCESS
