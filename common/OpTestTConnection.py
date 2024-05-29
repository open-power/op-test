#!/usr/bin/env python3
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

# @package OpTestTConnection
#  TConnection-API to telnet connection
#  This library of tconnection can use in cases if any platform has
#  telnet connection to their SP/MC.(i.e EX: FSP uses tenet connection)

# ruscur: Some notes on Python 3 conversion.
# There's a lot of yucky string/byte conversion in here: telnetlib needs
# everything to be bytes (which is fair enough since it's telnet), but
# we don't want the callers of this library to have to do the conversions
# constantly themselves, so in this file we should expect to be given
# strings and to return strings - even though that makes things harder.

import telnetlib


class NoLoginPrompt(Exception):
    def __init__(self, output):
        self.output = output

    def __str__(self):
        return "No login prompt found, instead got: {}".format(repr(self.output))


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
        # These have to be bytes(), but we can't just convert it because the strings
        # need an explicit encoding, which they don't have. (sigh)
        self.host_name = bytes(host_name.encode('ascii'))
        self.user_name = bytes(user_name.encode('ascii'))
        self.password = bytes(password.encode('ascii'))
        self.prompt = bytes(prompt.encode('ascii'))
        self.tn = None

    ##
    # @brief login to telnet connection of SP/MC
    #
    def login(self):
        self.tn = telnetlib.Telnet(self.host_name)
        self.tn.read_until(b'login: ')
        self.tn.write(self.user_name + b'\n')
        self.tn.read_until(b'assword: ')
        self.tn.write(self.password + b'\n')
        ret = self.tn.read_until(self.prompt)
        if self.prompt not in ret:
            raise NoLoginPrompt(ret)

    ##
    # @brief run the given command on telnet connection
    # @param command @type string: command to run
    #
    def run_command(self, command):
        command = bytes(command.encode('ascii'))
        self.tn.write(command + b'\n')
        response = self.tn.read_until(self.prompt)
        return self._send_only_result(command, response)

    def issue_forget(self, command):
        command = bytes(command.encode('ascii'))
        self.tn.write(command + b'\n')
        response = self.tn.read_very_eager()
        return self._send_only_result(command, response)

    def _send_only_result(self, command, response):
        output = response.splitlines()
        if command in output[0]:
            output.pop(0)
        output.pop()
        output = [element.lstrip().decode('utf-8') for element in output]
        response = '\n'.join(output)
        response = response.strip()
        return ''.join(response)
