#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEEH.py $
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

#  @package OpTestEEH.py
#   This testcase basically tests all OPAL EEH Error injection tests.
#   fenced PHB
#   frozen PE(TODO)

import time
import subprocess
import commands
import re
import sys
import os
import os.path

from pprint import pprint
from difflib import Differ
from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil
from OpTestSensors import OpTestSensors


class OpTestEEH():
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
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP, i_ffdcDir)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                                      i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                                      i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This testcase has below steps
    #         1. Get the list of pci PHB domains
    #         2. Get the root PHB domain where the root file system
    #            is installed(We need to skip this as EEH recovery will
    #            fail on root PHB).
    #         3. Start injecting the fenced PHB errors in a for loop
    #            Only one time basic check whether PHB recovered or not
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_basic_fenced_phb(self):
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb for fenced PHB Testcase"
        pci_domains.remove(root_domain)
        print pci_domains
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty cols 300")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty rows 10")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -D")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        for domain in pci_domains:
            self.prepare_logs()
            cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
            print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
            self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
            # Give some time to EEH PCI Error recovery
            time.sleep(30)
            l_con.sendline("\r\n")
            self.gather_logs()
            self.check_phb_recovery()

    ##
    # @brief  This testcase has below steps
    #         1. Get the list of pci PHB domains
    #         2. Get the root PHB domain where the root file system
    #            is installed(We need to skip this as EEH recovery will
    #            fail on root PHB).
    #         3. Set the MAX EEH Freeze count to 1 so that if we can
    #            test max EEH Recovery capacity within less for loop executions
    #            By default it is 6,
    #         4. Start injecting the fenced PHB errors two times across all PHB domains
    #            except root PHB.( As we set max EEH Freeze count to 1).
    #            So expectation is first time it should recover and second time
    #            EEH should properly remove the device and OS should not crash.
    #
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_max_fenced_phb(self):
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb for fenced PHB Testcase"
        pci_domains.remove(root_domain)
        print pci_domains
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        # Reduce the max EEH freeze count to 1
        cmd = "echo 1 > /sys/kernel/debug/powerpc/eeh_max_freezes"
        self.cv_HOST.host_run_command(cmd)
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty cols 300")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty rows 10")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -D")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        for i in range(0,1):
            for domain in pci_domains:
                self.prepare_logs()
                cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
                print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
                self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
                # Give some time to EEH PCI Error recovery
                time.sleep(30)
                l_con.sendline("\r\n")
                self.gather_logs()
                self.check_phb_recovery()

    ##
    # @brief  This function is used to prepare opal and kernel logs to
    #         a reference point, so that we can compare logs for each EEH
    #         iteration easily
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def prepare_logs(self):
        cmd = "rm -rf /tmp/opal_msglog;touch /sys/firmware/opal/msglog; cp /sys/firmware/opal/msglog /tmp/opal_msglog"
        self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -C")

    ##
    # @brief  This function is used to gather opal and kernel logs
    #         for each EEH iteration instead of full logs
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def gather_logs(self):
        cmd = "diff /sys/firmware/opal/msglog /tmp/opal_msglog"
        self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg")


    ##
    # @brief  This function is used to actually check the PHB recovery
    #         after an EEH Fenced PHB Error Injection.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def check_phb_recovery(self):
        pass
        #TODO
        '''
        As of now only gathering the dmesg and opal logs for
        checking recovery. This function is a todo to check
        the actual PHB EEH recovery.
        '''
