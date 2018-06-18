#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPrdDriver.py $
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

# @package OpTestPrdDriver
#  PRD driver package for OpenPower testing.
#
#  This class will test the functionality of following.
#  PRD (Processor Runtime Diagnostic) enables the support for handing certain RAS events by the userspace application.
#  For testing out this feature, we require the userspace xscom-utils, part of the 'skiboot' tree.
#  skiboot tree is cloning in /tmp directory.
#  Using the xscom utility, we need to inject errors through FIR (Fault Isolation Register)
#  and observe them getting cleared if PRD handles them successfully.
#  0x01020013 IPOLL mask register
#  0x02010840 PBA Local Fault isolation register
#  0x02010843 PBA Local fault isolation mask register

import time
import subprocess
import re
import sys
import os
import random


from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed


class ErrorToInject():
    def __init__(self, desc, FIR, FIMR, ERROR):
        self.desc = desc
        self.FIR = FIR
        self.FIMR = FIMR
        self.ERROR = ERROR
    def __str__(self):
        return self.desc

class OpTestPrdDriver(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    ##
    # @brief This is a common function for all the PRD test cases. This will be executed before
    #        any test case starts. Basically this provides below requirements.
    #        1. Validates all required host commands
    #        2. It will clone skiboot source repository
    #        3. Compile the necessary tools -xscom-utils(getscom and putscom)
    #        4. Get the list Of Chips.
    #           Ex: ['00000000', '00000001', '00000010']
    #        5. generate a random chip.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def prd_init(self):
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Getting list of processor chip Id's(executing getscom -l to get chip id's)
        l_res = self.cv_HOST.host_run_command("PATH=/usr/local/sbin:$PATH getscom -l")
        l_chips = []
        for line in l_res:
            matchObj = re.search("(\d{8}).*processor", line)
            if matchObj:
                l_chips.append(matchObj.group(1))
        print l_chips, len(l_chips)
        self.assertNotEqual(len(l_chips), 0, "Getscom failed to list processor chip id's")
        l_chips.sort()
        print l_chips # ['00000000', '00000001', '00000010']
        self.random_chip = random.choice(l_chips)

    ##
    # @brief This function injects some core FIR errors and verifies whether opal-prd clears the errors.
    #        and also this function injects errors on random chip.
    #
    # @param FIR @type str: Local Fault Isolation register
    # @param FIMR @type str: Local Fault Isolation mask register
    # @param ERROR @type int: Core FIR error, this error will be written to FIR.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def prd_test_core_fir(self, FIR, FIMR, ERROR):
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        chip_id = "0x" + self.random_chip
        print chip_id
        print "OPAL-PRD: Injecting error 0x%x on FIR: %s" % (ERROR, FIR)
        # Read Local Fault Isolation register
        l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip_id, FIR)
        l_res = console.run_command(l_cmd)

        # Reading Local Fault Isolation mask register
        l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip_id, FIMR)
        l_res = console.run_command(l_cmd)
        #print l_res

        # Changing the FIMR value to un-masked value.
        LEN = 16
        l_len = len(l_res[-1])
        l_val = hex(int(("0x" + "0"*(LEN - l_len) + l_res[-1]), 16)& (ERROR ^ 0xffffffffffffffff))

        # Writing the same value to Local Fault Isolation mask register again
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (chip_id, FIMR, l_val)
        l_res = console.run_command(l_cmd)

        # Inject a core error on FIR
        l_cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (chip_id, FIR, hex(ERROR))
        l_res = console.run_command(l_cmd)

        time.sleep(5)
        tries = 30
        for i in range(1, tries):
            time.sleep(1)
            # Read Local Fault Isolation register again
            l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip_id, FIR)
            l_res = console.run_command(l_cmd)
            if l_res[-1] == BMC_CONST.FAULT_ISOLATION_REGISTER_CONTENT:
                print "Opal-prd handles core hardware error"
                break
            else:
                l_msg = "Opal-prd not yet cleared hardware error, (%d/%d)" %(i,tries)

        # Check FIR got cleared by opal-prd
        self.assertEqual(l_res[-1], BMC_CONST.FAULT_ISOLATION_REGISTER_CONTENT,
                        "Opal-prd not clearing hardware errors in runtime")

        # Reading the Local Fault Isolation Mask Register again
        l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip_id, FIMR)
        l_res = console.run_command(l_cmd)
        #print l_res

        # check for IPOLL mask register value to see opal-prd cleared the value
        l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip_id, self.IPOLL_MASK_REGISTER)
        l_res = console.run_command(l_cmd)
        print l_res
        self.assertEqual(l_res[-1], self.IPOLL_MASK_REGISTER_CONTENT,
            "Opal-prd is not clearing the IPOLL MASK REGISTER after injecting core FIR error")
        print "Opal-prd cleared the IPOLL MASK REGISTER"
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function performs below steps
    #        1. Initially connecting to host and ipmi consoles for execution.
    #        2. check for IPOLL mask register value to see whether opal-prd is running or not
    #           if it is 0-->opal-prd is running-->continue
    #           else start opal-prd service again
    #        3. call test_prd_for_fir() function for each core FIR error and this function
    #           can be used for any number of errors, like it is a generic function
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" in self.bmc_type:
            self.skipTest("OpenPower specific")
        # In P9 FSP systems we need to enable this test
        self.prd_init()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
	self.cv_SYSTEM.host_console_unique_prompt()

        cpu = self.cv_HOST.host_get_proc_gen()
        faults_to_inject = []

        if cpu not in ["POWER8", "POWER8E", "POWER9"]:
            self.skipTest("Unknown CPU type %s" % cpu)

        if cpu in ["POWER8", "POWER8E"]:
            self.IPOLL_MASK_REGISTER = "0x01020013"
            self.IPOLL_MASK_REGISTER_CONTENT = "0000000000000000"
            PBA_FAULT_ISOLATION_REGISTER = "0x02010840"
            PBA_FAULT_ISOLATION_MASK_REGISTER = "0x02010843"
            PBAFIR_OCI_APAR_ERR = 0x8000000000000000
            PBAFIR_PB_CE_FW  = 0x0400000000000000
            PBAFIR_PB_RDDATATO_FW = 0x2000000000000000
            PBAFIR_PB_RDADRERR_FW = 0x6000000000000000
            faults_to_inject = [
                ErrorToInject("PRD: Test for PBAFIR_OCI_APAR_ERR-->OCI Address Parity Error",
                              PBA_FAULT_ISOLATION_REGISTER,
                              PBA_FAULT_ISOLATION_MASK_REGISTER,
                              PBAFIR_OCI_APAR_ERR),
                ErrorToInject("PRD: Test for PBAFIR_PB_CE_FW-->PB Read Data CE Error for Forwarded Request",
                              PBA_FAULT_ISOLATION_REGISTER,
                              PBA_FAULT_ISOLATION_MASK_REGISTER,
                              PBAFIR_PB_CE_FW),
                ErrorToInject("PRD: Test for PBAFIR_PB_RDDATATO_FW-->PB Read Data Timeout for Forwarded Request",
                              PBA_FAULT_ISOLATION_REGISTER,
                              PBA_FAULT_ISOLATION_MASK_REGISTER,
                              PBAFIR_PB_RDDATATO_FW),
                ErrorToInject("PRD: Test for PBAFIR_PB_RDADRERR_FW-->PB CRESP Addr Error Received for Forwarded Read Request",
                              PBA_FAULT_ISOLATION_REGISTER,
                              PBA_FAULT_ISOLATION_MASK_REGISTER,
                              PBAFIR_PB_RDADRERR_FW),
            ]
        if cpu in ["POWER9"]:
            self.IPOLL_MASK_REGISTER = "0xF0033" #TP.TPCHIP.PIB.PCBMS.COMP.INTR_COMP.HOST_MASK_REG
            self.IPOLL_MASK_REGISTER_CONTENT = "a400000000000000"

        l_con.run_command("stty cols 300")
        l_con.run_command("stty rows 30")

        try:
            l_con.run_command("opal-prd --pnor /dev/mtd0 --debug --stdio")
        except CommandFailed as cf:
            print "opal-prd failed to activate %s" % str(cf)

        # check for IPOLL mask register value to check opal-prd is running or not
        l_cmd = "PATH=/usr/local/sbin:$PATH getscom -c 0x0 %s" % self.IPOLL_MASK_REGISTER
        l_res = l_con.run_command(l_cmd)
        if l_res[-1] == self.IPOLL_MASK_REGISTER_CONTENT:
            print "Opal-prd is running"
        else:
            l_con.run_command("service opal-prd start")
            l_res = l_con.run_command(l_cmd)
            self.assertEqual(l_res[-1], self.IPOLL_MASK_REGISTER_CONTENT,
                    "IPOLL MASK REGISTER is not getting cleared by opal-prd")
            print "Opal-prd is running"

        # Test for PBA FIR with different core errors
        for e in faults_to_inject:
            print "PRD Test: %s" % str(e)
            self.prd_test_core_fir(e.FIR, e.FIMR, e.ERROR)

        pass
