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
import os
import os.path

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

class OpTestNVRAM(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()

class HostNVRAM(OpTestNVRAM):
    ##
    # @brief  This function tests nvram partition access, print/update
    #         the config data and dumping the partition's data. All
    #         these operations are done on supported partitions in both
    #         host OS and Petitboot.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
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
            self.nvram_update_part_config_in_host("common")
            self.nvram_update_part_config_in_host("ibm,skiboot")
            # The following 2 are disabled due to possible nvram binary
            # bug.
#            self.nvram_update_part_config_in_host("lnx,oops-log")
#            self.nvram_update_part_config_in_host("wwwwwwwwwwww")
        except OpTestError:
            print "There is a failure in updating one of NVRAM partitions"

    ##
    # @brief This function tests nvram update/print config functions for partition i_part
    #        these functions will be tested in host OS
    #
    # @param i_part @type string:partition to access i.e common, ibm,skiboot etc
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def nvram_update_part_config_in_host(self, i_part):
        part = i_part
        self.cv_HOST.host_run_command("nvram -p %s --update-config 'test-cfg=test-value'" % part)
        res = self.cv_HOST.host_run_command("nvram -p %s --print-config=test-cfg" % part)
        if "test-value" in res:
            print "Update config to the partition %s works fine" % part
        else:
            msg = "failed to update nvram config into the partition %s" % part
            print msg
            raise OpTestError(msg)

class SkirootNVRAM(OpTestNVRAM):
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        # Execute these tests in petitboot
        self.console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_set_unique_prompt()
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
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump common|head")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump ibm,skiboot|head")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump lnx,oops-log|head")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --dump wwwwwwwwwwww|head")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii common|head -c512; echo")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii ibm,skiboot|head -c512; echo")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii lnx,oops-log|head -c512; echo")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("nvram --ascii wwwwwwwwwwww|head -c512; echo")
        try:
            self.nvram_update_part_config_in_petitboot("common")
            self.nvram_update_part_config_in_petitboot("ibm,skiboot")
            # below two are Disabled due to nvram off-by-one bug
            #self.nvram_update_part_config_in_petitboot("lnx,oops-log")
            #self.nvram_update_part_config_in_petitboot("wwwwwwwwwwww")
        except OpTestError:
            print "There is a failure in updating one of NVRAM partitions"

    ##
    # @brief This function tests nvram update/print config functions for partition i_part
    #        these functions will be tested in Petitboot.
    #
    # @param i_part @type string:partition to access i.e common, ibm,skiboot etc
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def nvram_update_part_config_in_petitboot(self, i_part):
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
