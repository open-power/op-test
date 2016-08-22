#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestIPMIReprovision.py $
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

#  @package OpTestIPMIReprovision
#  Reset\Reprovision to default package for OpenPower testing.
#
#  This class will test the functionality of following Reset\Reprovision to default tests.
#  1. NVRAM Partition - IPMI Reprovision.
#  2. GARD Partition - IPMI Reprovision.


import time
import subprocess
import re

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpTestSystem
from OpTestHMIHandling import OpTestHMIHandling


class OpTestIPMIReprovision():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostUser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostIP=None,
                 i_hostUser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_hostIP, i_hostUser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostIP, i_hostUser, i_hostPasswd,i_bmcIP, i_ffdcDir)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostIP,
                 i_hostUser, i_hostPasswd)
        self.util = OpTestUtil()
        self.opTestHMIHandling = OpTestHMIHandling(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostIP,
                 i_hostUser, i_hostPasswd)

    ##
    # @brief This function will cover following test steps
    #        Testcase: NVRAM Partition-IPMI Reprovision
    #        1. Update NVRAM config data with test config data
    #           i.e "nvram --update-config test-name=test-value"

    #        2. Issue an IPMI PNOR Reprovision request command, to reset NVRAM partition to default.
    #        3. Wait for PNOR Reprovision progress to complete(00).
    #        4. Do a Hard reboot(Power OFF/ON) to avoid nvram cache data.
    #        5. Once system booted, check for NVRAM parition whether the test config data
    #           got erased or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_nvram_ipmi_reprovision(self):
        self.cv_HOST.host_run_command("uname -a")
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        print "IPMI_Reprovision: Updating the nvram partition with test cfg data"
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_UPDATE_CONFIG_TEST_DATA)
        self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        print "IPMI_Reprovision: issuing ipmi pnor reprovision request"
        self.cv_SYSTEM.sys_issue_ipmi_pnor_reprovision_request()
        print "IPMI_Reprovision: wait for reprovision to complete"
        self.cv_SYSTEM.sys_wait_for_ipmi_pnor_reprovision_to_complete()
        print "IPMI_Reprovision: gathering the opal message logs"
        self.cv_HOST.host_gather_opal_msg_log()
        print "IPMI_Reprovision: Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == BMC_CONST.FW_SUCCESS:
            print "IPMI_Reprovision: System is in standby/Soft-off state"
        else:
            l_msg = "IPMI_Reprovision: System failed to reach standby/Soft-off state after pnor reprovisioning"
            raise OpTestError(l_msg)

        print "IPMI_Reprovision: Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        l_res = self.cv_HOST.host_run_command(BMC_CONST.NVRAM_PRINT_CFG)
        if l_res.__contains__(BMC_CONST.NVRAM_TEST_DATA):
            l_msg = "NVRAM Partition - IPMI Reprovision not happening, nvram test config data still exists"
            raise OpTestError(l_msg)
        print "NVRAM Partition - IPMI Reprovision is done, cleared the nvram test config data"
        self.cv_HOST.host_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will cover following test steps
    #        Testcase: GARD Partition-IPMI Reprovision
    #        1. Inject core checkstop using existed function from OpTestHMIHandling.py
    #        2. Do a Hard reboot(IPMI Power OFF/ON)
    #        2. Issue an IPMI PNOR Reprovision request command, to reset GUARD partition to default.
    #        3. Wait for IPMI PNOR Reprovision progress to complete(00).
    #        4. Check for GUARD parition whether the existing gard records erased or not.
    #        6. Reboot the system back to see system is booting fine or not.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_gard_ipmi_reprovision(self):
        print "IPMI_Reprovision: Injecting system core checkstop to guard the phyisical cpu"
        self.opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_MALFUNCTION_ALERT)
        print "IPMI_Reprovision: Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == BMC_CONST.FW_SUCCESS:
            print "IPMI_Reprovision: System is in standby/Soft-off state"
        else:
            l_msg = "IPMI_Reprovision: System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        print "IPMI_Reprovision: Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        print "IPMI_Reprovision: issuing ipmi pnor reprovision request"
        self.cv_SYSTEM.sys_issue_ipmi_pnor_reprovision_request()
        print "IPMI_Reprovision: wait for reprovision to complete"
        self.cv_SYSTEM.sys_wait_for_ipmi_pnor_reprovision_to_complete()
        print "IPMI_Reprovision: gathering the opal message logs"
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_get_OS_Level()
        self.cv_HOST.host_clone_skiboot_source(BMC_CONST.CLONE_SKIBOOT_DIR)
        # Compile the necessary tools xscom-utils and gard utility
        self.cv_HOST.host_compile_gard_utility(BMC_CONST.CLONE_SKIBOOT_DIR)
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        l_res = self.cv_SYSTEM.sys_list_gard_records(BMC_CONST.GARD_TOOL_DIR)
        print l_res
        if BMC_CONST.NO_GARD_RECORDS in l_res:
            print "GUARD Partition - IPMI Reprovision is done, cleared HW gard records"
        else:
            l_msg = "IPMI: Reprovision not happening, gard records are not erased"
            raise OpTestError(l_msg)
        print "IPMI_Reprovision: Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == BMC_CONST.FW_SUCCESS:
            print "IPMI_Reprovision: System is in standby/Soft-off state"
        else:
            l_msg = "IPMI_Reprovision: System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        print "IPMI_Reprovision: Performing a IPMI Power ON Operation"
        # Perform a IPMI Power ON Operation
        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

        print "IPMI_Reprovision: gathering the opal message logs"
        self.cv_HOST.host_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS
