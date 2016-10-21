#!/usr/bin/python
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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestPrdDriver():
    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                 i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

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
    def testPrdDriver(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.test_init()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cd %s/external/xscom-utils/;" % BMC_CONST.CLONE_SKIBOOT_DIR)

        # check for IPOLL mask register value to check opal-prd is running or not
        l_cmd = "./getscom -c 0x0 %s" % BMC_CONST.IPOLL_MASK_REGISTER
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
        if l_res[-1] == BMC_CONST.IPOLL_MASK_REGISTER_CONTENT:
            print "Opal-prd is running"
        else:
            self.cv_IPMI.run_host_cmd_on_ipmi_console("service opal-prd start")
            l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
            if l_res[-1] == BMC_CONST.IPOLL_MASK_REGISTER_CONTENT:
                print "Opal-prd is running"
            else:
                l_msg = "IPOLL MASK REGISTER is not getting cleared by opal-prd"
                raise OpTestError(l_msg)

        # test for PBA FIR with different core errors
        # 1.PBAFIR_OCI_APAR_ERR-->OCI Address Parity Error
        print "PRD: Test for PBAFIR_OCI_APAR_ERR-->OCI Address Parity Error"
        self.test_prd_for_fir(BMC_CONST.PBA_FAULT_ISOLATION_REGISTER,
                              BMC_CONST.PBA_FAULT_ISOLATION_MASK_REGISTER,
                              BMC_CONST.PBAFIR_OCI_APAR_ERR)
        # 2.PBAFIR_PB_CE_FW-->PB Read Data CE Error for Forwarded Request
        print "PRD: Test for PBAFIR_PB_CE_FW-->PB Read Data CE Error for Forwarded Request"
        self.test_prd_for_fir(BMC_CONST.PBA_FAULT_ISOLATION_REGISTER,
                              BMC_CONST.PBA_FAULT_ISOLATION_MASK_REGISTER,
                              BMC_CONST.PBAFIR_PB_CE_FW)
        # 3.PBAFIR_PB_RDDATATO_FW-->PB Read Data Timeout for Forwarded Request
        print "PRD: Test for PBAFIR_PB_RDDATATO_FW-->PB Read Data Timeout for Forwarded Request"
        self.test_prd_for_fir(BMC_CONST.PBA_FAULT_ISOLATION_REGISTER,
                              BMC_CONST.PBA_FAULT_ISOLATION_MASK_REGISTER,
                              BMC_CONST.PBAFIR_PB_RDDATATO_FW)
        # 4.PBAFIR_PB_RDADRERR_FW-->PB CRESP Addr Error Received for Forwarded Read Request
        print "PRD: Test for PBAFIR_PB_RDADRERR_FW-->PB CRESP Addr Error Received for Forwarded Read Request"
        self.test_prd_for_fir(BMC_CONST.PBA_FAULT_ISOLATION_REGISTER,
                              BMC_CONST.PBA_FAULT_ISOLATION_MASK_REGISTER,
                              BMC_CONST.PBAFIR_PB_RDADRERR_FW)
        return BMC_CONST.FW_SUCCESS

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
    def test_prd_for_fir(self, FIR, FIMR, ERROR):
        chip_id = "0x" + self.random_chip
        print chip_id
        print "OPAL-PRD: Injecting error 0x%x on FIR: %s" % (ERROR, FIR)
        # Read Local Fault Isolation register
        l_cmd = "./getscom -c %s %s" % (chip_id, FIR)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)

        # Reading Local Fault Isolation mask register
        l_cmd = "./getscom -c %s %s" % (chip_id, FIMR)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
        print l_res

        # Changing the FIMR value to un-masked value.
        LEN = 16
        l_len = len(l_res[-1])
        l_val = hex(int(("0x" + "0"*(LEN - l_len) + l_res[-1]), 16)& (ERROR ^ 0xffffffffffffffff))

        # Writing the same value to Local Fault Isolation mask register again
        l_cmd = "./putscom -c %s %s %s" % (chip_id, BMC_CONST.PBA_FAULT_ISOLATION_MASK_REGISTER, l_val)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)

        # Inject a core error on FIR
        l_cmd = "./putscom -c %s %s %s" % (chip_id, FIR, hex(ERROR))
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)

        time.sleep(30)

        # Read Local Fault Isolation register again
        l_cmd = "./getscom -c %s %s" % (chip_id, FIR)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
        print l_res

        # Check FIR got cleared by opal-prd
        if l_res[-1] == BMC_CONST.FAULT_ISOLATION_REGISTER_CONTENT:
            print "Opal-prd handles core hardware error"
        else:
            l_msg = "Opal-prd not clearing hardware errors in runtime"
            print l_msg
            raise OpTestError(l_msg)

        # Reading the Local Fault Isolation Mask Register again
        l_cmd = "./getscom -c %s %s" % (chip_id, FIMR)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
        print l_res

        # check for IPOLL mask register value to see opal-prd cleared the value
        l_cmd = "./getscom -c %s %s" % (chip_id, BMC_CONST.IPOLL_MASK_REGISTER)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(l_cmd)
        if l_res[-1] == BMC_CONST.IPOLL_MASK_REGISTER_CONTENT:
            print "Opal-prd cleared the IPOLL MASK REGISTER"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Opal-prd is not clearing the IPOLL MASK REGISTER after injecting core FIR error"
            print l_msg
            raise OpTestError(l_msg)

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
    def test_init(self):
        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Check whether git and gcc commands are available on host
        self.cv_HOST.host_check_command("git")
        self.cv_HOST.host_check_command("gcc")

        # It will clone skiboot source repository 
        self.cv_HOST.host_clone_skiboot_source(BMC_CONST.CLONE_SKIBOOT_DIR)

        # Compile the necessary tools xscom-utils and gard utility
        self.cv_HOST.host_compile_xscom_utilities(BMC_CONST.CLONE_SKIBOOT_DIR)

        # Getting list of processor chip Id's(executing getscom -l to get chip id's)
        l_res = self.cv_HOST.host_run_command("cd %s/external/xscom-utils/; ./getscom -l" % BMC_CONST.CLONE_SKIBOOT_DIR)
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
        self.random_chip = random.choice(l_chips)

        # Below will be useful for debug purposes to compare chip information
        l_res = self.cv_HOST.host_read_msglog_core()
        print l_res
