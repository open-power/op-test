#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPCI.py $
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

#  @package OpTestPCI.py
#   This testcase basically will test and gather PCI subsystem Info
#   Tools used are lspci and lsusb
#   any pci related tests will be added in this package

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


class OpTestPCI():
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
                 i_hostuser=None, i_hostPasswd=None, i_hostLspci=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP, i_ffdcDir)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                                      i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                                      i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()
        self.lspci_file = i_hostLspci

    ##
    # @brief  This function will get the PCI and USB susbsytem Info
    #         And also this test compares known good data of
    #         "lspci -mm -n" which is stored in testcases/data directory
    #         with the current lspci data.
    #         User need to specify the corresponding file name into
    #         machines xml like lspci.txt which contains "lspci -mm -n"
    #         command output in a working good state of system.
    #         tools used are lspci and lsusb
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_host_pci_devices_info(self):
        if self.lspci_file == "empty.txt":
            print "Skipping the pci devices comparision as missing the lspci data file name in machines xml"
            return BMC_CONST.FW_SUCCESS
        filename = os.path.join(os.path.dirname(__file__).split('testcases')[0], self.lspci_file)
        if not os.path.isfile(filename):
            raise OpTestError("lspci file %s not found in top level directory" % filename)
        with open(filename, 'r') as f:
            self.pci_good_data = f.read().replace('\n', '')
        print self.pci_good_data
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.test_skiroot_pci_devices()
        self.test_host_pci_devices()

    ##
    # @brief  This function will get the "lspci -mm -n" output from the petitboot
    #         and compares it with known good lspci data
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_skiroot_pci_devices(self):
        cmd = "lspci -mm -n"
        self.console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.sys_ipmi_boot_system_to_petitboot(self.console)
        self.cv_IPMI.ipmi_host_set_unique_prompt(self.console)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        res = self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        self.cv_SYSTEM.sys_ipmi_close_console(self.console)
        self.pci_data_petitboot = ''.join(res[1:])
        print self.pci_data_petitboot
        if self.pci_good_data == self.pci_data_petitboot:
            print "All the pci devices are detected at petitboot"
        else:
            result = list(Differ().compare(self.pci_good_data, self.pci_data_petitboot))
            pprint(result)
            raise OpTestError("There is a mismatch b/w known good output and tested petitboot lspci output")

    ##
    # @brief  This function will get the "lspci -mm -n" output from the host OS
    #         and compares it with known good lspci data
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_host_pci_devices(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.cv_SYSTEM.sys_hard_reboot()
        self.cv_HOST.host_check_command("lspci")
        self.cv_HOST.host_check_command("lsusb")
        self.cv_HOST.host_list_pci_devices()
        self.cv_HOST.host_get_pci_verbose_info()
        self.cv_HOST.host_list_usb_devices()
        l_res = self.cv_HOST.host_run_command("lspci -mm -n")
        self.pci_data_hostos = l_res.replace("\r\n", "")
        if self.pci_good_data == self.pci_data_hostos:
            print "All the pci devices are detected by firmware"
        else:
            print self.pci_data_hostos
            result = list(Differ().compare(self.pci_good_data, self.pci_data_hostos))
            pprint(result)
            raise OpTestError("There is a mismatch b/w known good output and tested host lspci output")
