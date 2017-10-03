#!/usr/bin/python2
# encoding=utf8
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestTConnection.py $
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

## @package OpTestTConnection
#  TConnection-API to telnet connection
#  This library of tconnection can use in cases if any platform has 
#  telnet connection to their SP/MC.(i.e EX: FSP uses tenet connection)

import telnetlib

class TConnection():

    ##
    # @brief Initialize this object
    #
    # @param host_name @type string: IP Address of the SP/MC
    # @param user_name @type string: Userid to log into the SP/MC
    # @param password @type string: Password of the userid to log into the SP/MC
    # @param prompt @type string: $ or # type of prompt
    #
    def __init__(self, host_name, user_name, password, prompt):
        self.host_name = host_name
        self.user_name = user_name
        self.password = password
        self.prompt = prompt
        self.tn = None

    ##
    # @brief login to telnet connection of SP/MC
    #
    def login(self):
        self.tn = telnetlib.Telnet(self.host_name)
        self.tn.read_until('login: ')
        self.tn.write(self.user_name + '\n')
        self.tn.read_until('assword: ')
        self.tn.write(self.password + '\n')
        ret=self.tn.read_until(self.prompt)
        assert self.prompt in ret

    ##
    # @brief run the given command on telnet connection
    # @param command @type string: command to run
    #
    def run_command(self, command):
        self.tn.write(command + '\n')
        response = self.tn.read_until(self.prompt)
        return self._send_only_result(command, response)

    def issue_forget(self,command):
        self.tn.write(command + '\n')
        response = self.tn.read_very_eager()
        return self._send_only_result(command, response)

    def _send_only_result(self, command, response):
        output = response.splitlines()
        if command in output[0]:
            output.pop(0)
        output.pop()
        output = [ element.lstrip()+'\n' for element in output]
        response = ''.join(output)
        response = response.strip()
        return ''.join(response)
