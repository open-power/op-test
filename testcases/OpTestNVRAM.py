#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestNVRAM.py $
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
#
#  @package OpTestNVRAM.py
#
#   This testcase will deal with testing nvram partition
#   access functions like getting the list of partitions
#   print/update config data in all the supported partitions
#

import time
import subprocess
import commands
import re
import sys

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestNVRAM():
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
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief  This function tests nvram partition access, print/update
    #         the config data and dumping the partition's data. All
    #         these operations are done on supported partitions in both
    #         host OS and Petitboot.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def test_nvram_configuration(self):
        # Execute these tests in host OS
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        self.cv_HOST.host_run_command("uname -a")
        self.cv_HOST.host_run_command("cat /etc/os-release")
        self.cv_HOST.host_run_command("nvram -v")
        self.cv_HOST.host_run_command("nvram --print-config -p ibm,skiboot")
        self.cv_HOST.host_run_command("nvram --print-config -p common")
        self.cv_HOST.host_run_command("nvram --print-config -p lnx,oops-log")
        self.cv_HOST.host_run_command("nvram --print-config -p wwwwwwwwwwww")
        self.cv_HOST.host_run_command("nvram --print-vpd")
        self.cv_HOST.host_run_command("nvram --print-all-vpd")
        self.cv_HOST.host_run_command("nvram --print-err-log")
        self.cv_HOST.host_run_command("nvram --print-event-scan")
        self.cv_HOST.host_run_command("nvram --partitions")
        self.cv_HOST.host_run_command("nvram --dump common")
        self.cv_HOST.host_run_command("nvram --dump ibm,skiboot")
        self.cv_HOST.host_run_command("nvram --dump lnx,oops-log")
        self.cv_HOST.host_run_command("nvram --dump wwwwwwwwwwww")
        self.cv_HOST.host_run_command("nvram --ascii common")
        self.cv_HOST.host_run_command("nvram --ascii ibm,skiboot")
        self.cv_HOST.host_run_command("nvram --ascii lnx,oops-log")
        self.cv_HOST.host_run_command("nvram --ascii wwwwwwwwwwww")
        try:
            self.test_nvram_update_part_config_in_host("common")
            self.test_nvram_update_part_config_in_host("ibm,skiboot")
            self.test_nvram_update_part_config_in_host("lnx,oops-log")
            self.test_nvram_update_part_config_in_host("wwwwwwwwwwww")
        except OpTestError:
            print "There is a failure in updating one of NVRAM partitions"

        # Execute these tests in petitboot
        self.console = self.cv_SYSTEM.sys_get_ipmi_console()
        try:
            self.cv_SYSTEM.sys_ipmi_boot_system_to_petitboot(self.console)
            self.cv_IPMI.ipmi_host_set_unique_prompt(self.console)
            self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram -v")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-config -p ibm,skiboot")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-config -p common")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-config -p lnx,oops-log")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-config -p wwwwwwwwwwww")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-vpd")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-all-vpd")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-err-log")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --print-event-scan")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --partitions")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump common")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump ibm,skiboot")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump lnx,oops-log")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump wwwwwwwwwwww")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii common")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii ibm,skiboot")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii lnx,oops-log")
            self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii wwwwwwwwwwww")
            try:
                self.test_nvram_update_part_config_in_petitboot("common")
                self.test_nvram_update_part_config_in_petitboot("ibm,skiboot")
                self.test_nvram_update_part_config_in_petitboot("lnx,oops-log")
                self.test_nvram_update_part_config_in_petitboot("wwwwwwwwwwww")
            except OpTestError:
                print "There is a failure in updating one of NVRAM partitions"
        except:
            self.cv_IPMI.ipmi_set_boot_to_disk()
        self.cv_IPMI.ipmi_set_boot_to_disk()

    ##
    # @brief This function tests nvram update/print config functions for partition i_part
    #        these functions will be tested in host OS
    #
    # @param i_part @type string:partition to access i.e common, ibm,skiboot etc
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_nvram_update_part_config_in_host(self, i_part):
        part = i_part
        self.cv_HOST.host_run_command("nvram -p %s --update-config 'test-cfg=test-value'" % part)
        res = self.cv_HOST.host_run_command("nvram -p %s --print-config=test-cfg" % part)
        if "test-value" in res:
            print "Update config to the partition %s works fine" % part
        else:
            msg = "failed to update nvram config into the partition %s" % part
            print msg
            raise OpTestError(msg)

    ##
    # @brief This function tests nvram update/print config functions for partition i_part
    #        these functions will be tested in Petitboot.
    #
    # @param i_part @type string:partition to access i.e common, ibm,skiboot etc
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_nvram_update_part_config_in_petitboot(self, i_part):
        part = i_part
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram -p %s --update-config 'test-cfg=test-value'" % part)
        res_list = self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram -p %s --print-config=test-cfg" % part)
        res = ''.join(res_list)
        if "test-value" in res:
            print "Update config to the partition %s works fine" % part
        else:
            msg = "failed to update nvram config into the partition %s" % part
            print msg
            raise OpTestError(msg)
