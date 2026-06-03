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
from common.Exceptions import CommandFailed
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
            print("\n" + "="*80)
            print("OS SYSTEM INFORMATION (via SSH)")
            print("="*80)
            for index, each_cmd in enumerate(list_of_commands, start=0):
                # Check if pty has run_command (SSH) or sendline (console/pexpect)
                if hasattr(pty, 'run_command'):
                    # SSH mode - use run_command
                    try:
                        output = pty.run_command(each_cmd, timeout=10)
                        if output:
                            # Format output nicely
                            print(f"\n[{index+1}] Command: {each_cmd}")
                            print("-" * 80)
                            for line in output:
                                print(f"  {line}")
                    except Exception as e:
                        print(f"\n[{index+1}] Command: {each_cmd}")
                        print("-" * 80)
                        print(f"  ERROR: {e}")
                else:
                    # Console mode - use sendline/expect
                    print(f"\n[{index+1}] Command: {each_cmd}")
                    print("-" * 80)
                    pty.sendline(each_cmd)
                    rc = pty.expect([prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            print("\n" + "="*80 + "\n")
        except CommandFailed as cf:
            raise cf

    def get_HMCconfig(self, pty, prompt,CEC_name,LPAR):
        # Collect config data from HMC
        ################ HMC INFO ####################
        get_HMCconfig_cmds  = self.config_actions["HMC"]["COMMANDS"]
        print("\n" + "="*80)
        print("HMC SYSTEM INFORMATION")
        print("="*80)
        for index, each_cmd in enumerate(get_HMCconfig_cmds, start=0):
            if re.search(r'SYS|LPAR_NAME', each_cmd):
                new_cmd=each_cmd
                # Replace placeholders
                new_cmd = re.sub(r'SYS', CEC_name, new_cmd)
                new_cmd = re.sub(r'LPAR_NAME', LPAR, new_cmd)
                try:
                    output = pty.run_command(new_cmd, timeout=10)
                    if output:
                        print(f"\n[{index+1}] Command: {new_cmd}")
                        print("-" * 80)
                        for line in output:
                            print(f"  {line}")
                except Exception as e:
                    print(f"\n[{index+1}] Command: {new_cmd}")
                    print("-" * 80)
                    print(f"  ERROR: {e}")
            else:
                try:
                    output = pty.run_command(each_cmd, timeout=10)
                    if output:
                        print(f"\n[{index+1}] Command: {each_cmd}")
                        print("-" * 80)
                        for line in output:
                            print(f"  {line}")
                except Exception as e:
                    print(f"\n[{index+1}] Command: {each_cmd}")
                    print("-" * 80)
                    print(f"  ERROR: {e}")
        print("\n" + "="*80 + "\n")
