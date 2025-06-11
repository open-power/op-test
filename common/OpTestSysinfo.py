#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestUtil.py $
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

import OpTestConfiguration
import time
import pexpect
import yaml
import re
from common.OpTestSSH import OpTestSSH
import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
config_file = "./CONFIG.YAML"

class OpTestSysinfo():

    def __init__(self):
        with open(config_file, "r") as file:
            self.config_actions = yaml.safe_load(file)
            list_of_commands = self.config_actions["LINUX"]["COMMANDS"]
            get_HMCconfig_cmds  = self.config_actions["HMC"]["COMMANDS"]

    def get_OSconfig(self, pty, prompt):
        # Collect config related data from the OS
        try:
            list_of_commands = self.config_actions["LINUX"]["COMMANDS"]
            print("########### OS Sysinfo ########")
            for index, each_cmd in enumerate(list_of_commands, start=0):
                pty.sendline(each_cmd)
                rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        except CommandFailed as cf:
            raise cf

    def get_HMCconfig(self, pty, prompt,CEC_name):
        # Collect config data from HMC
        ################ HMC INFO ####################
        get_HMCconfig_cmds  = self.config_actions["HMC"]["COMMANDS"]
        for index, each_cmd in enumerate(get_HMCconfig_cmds, start=0):
             if re.search('SYS', each_cmd):
                 new_cmd=re.sub('SYS',CEC_name,each_cmd)
                 try:
                   output = pty.run_command(new_cmd)
                 except Exception as e: 
                   print('command failed due to system error')
             else:
                try:
                    output = pty.run_command(each_cmd)
                except Exception as e:
                          print('command failed due to system error')

