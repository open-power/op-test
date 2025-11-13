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
    
    def get_config(self, pty,prompt,CEC_name,LPAR,action_name):
        # Collect config data based on action_name
        get_config_cmds  = self.config_actions[action_name]["COMMANDS"]
        for index, each_cmd in enumerate(get_config_cmds, start=0):
             if re.search(r'SYS|LPAR_NAME', each_cmd):
                new_cmd=each_cmd
                # Replace placeholders
                new_cmd = re.sub(r'SYS', CEC_name, new_cmd)
                new_cmd = re.sub(r'LPAR_NAME', LPAR, new_cmd)
                try:
                    if action_name in ['HMC', 'IO']:
                        output = pty.run_command(new_cmd)
                    else:
                        pty.sendline(new_cmd)
                        rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
                except Exception as e:
                   print('command failed due to system error')
             else:
                try:
                    if action_name == 'HMC':
                        output = pty.run_command(each_cmd)
                    else:
                        pty.sendline(each_cmd)
                        rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
                except Exception as e:
                    print('command failed due to system error')
