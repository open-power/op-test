#!/usr/bin/env python3
# encoding=utf8
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/SerialConsole.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2019
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

'''
SerialConsole
-------------

Get a serial console and use it like an IPMI one.
We use a shell command to connect to it, so you can easily point op-test
at a serial concentrator over SSH.
'''

import time
import os
import pexpect
import sys

from .OpTestConstants import OpTestConstants as BMC_CONST
from .OpTestError import OpTestError
from .OpTestUtil import OpTestUtil
from . import OpTestSystem
from .Exceptions import CommandFailed
from . import OPexpect

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class SerialConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

def set_system_to_UNKNOWN_BAD(system):
    s = system.get_state()
    system.set_state(OpTestSystem.OpSystemState.UNKNOWN_BAD)
    return s

class SerialConsole():
    def __init__(self, console_command=None, logfile=sys.stdout, prompt=None,
                 block_setup_term=None, delaybeforesend=None):
        self.console_command = console_command
        self.logfile = logfile
        self.delaybeforesend = delaybeforesend
        self.state = SerialConsoleState.DISCONNECTED
        # OpTestUtil instance is NOT conf's
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        self.delaybeforesend = delaybeforesend
        # allows caller specific control of when to block setup_term
        self.block_setup_term = block_setup_term
        # tells setup_term to not throw exceptions, like when system off
        self.setup_term_quiet = 0
        # flags the object to abandon setup_term operations, like when system off
        self.setup_term_disable = 0

        # FUTURE - System Console currently tracked in System Object
        # state tracking, reset on boot and state changes
        self.PS1_set = -1
        self.LOGIN_set = -1
        self.SUDO_set = -1

    def set_system(self, system):
        self.system = system

    def set_system_setup_term(self, flag):
        self.system.block_setup_term = flag

    def get_system_setup_term(self):
        return self.system.block_setup_term

    def set_block_setup_term(self, flag):
        self.block_setup_term = flag

    def get_block_setup_term(self):
        return self.block_setup_term

    def enable_setup_term_quiet(self):
        self.setup_term_quiet = 1
        self.setup_term_disable = 0

    def disable_setup_term_quiet(self):
        self.setup_term_quiet = 0
        self.setup_term_disable = 0

    def close(self):
        self.util.clear_state(self)
        if self.state == SerialConsoleState.DISCONNECTED:
            return
        try:
            # Hopefully we don't need to do this....
            #self.pty.send("\r")
            #self.pty.send('~.')
            #close_rc = self.pty.expect(
            #    ['Connection to.*closed', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            #log.debug("CLOSE Expect Buffer ID={}".format(hex(id(self.pty))))
            rc_child = self.pty.close()
            self.state = SerialConsoleState.DISCONNECTED
            exitCode = signalstatus = None
            if self.pty.status != -1:  # leaving for future debug
                if os.WIFEXITED(self.pty.status):
                    exitCode = os.WEXITSTATUS(self.pty.status)
                else:
                    signalstatus = os.WTERMSIG(self.pty.status)
        except pexpect.ExceptionPexpect:
            self.state = SerialConsoleState.DISCONNECTED
            raise OpTestError("Failed to close serial console")
        except Exception:
            self.state = SerialConsoleState.DISCONNECTED
            pass

    def connect(self, logger=None):
        if self.state == SerialConsoleState.CONNECTED:
            rc_child = self.close()
        else:
            self.util.clear_state(self)

        try:
            self.pty = OPexpect.spawn(self.console_command,
                                      logfile=self.logfile,
                                      failure_callback=set_system_to_UNKNOWN_BAD,
                                      failure_callback_data=self.system)
        except Exception:
            self.state = SerialConsoleState.DISCONNECTED
            raise CommandFailed(
                'OPexpect.spawn', "OPexpect.spawn encountered a problem, command was '{}'".format(cmd), -1)

        log.debug("#Serial Console CONNECT")
        self.state = SerialConsoleState.CONNECTED
        self.pty.setwinsize(1000, 1000)

        if logger:
            self.pty.logfile_read = OpTestLogger.FileLikeLogger(logger)
        else:
            self.pty.logfile_read = OpTestLogger.FileLikeLogger(log)

        if self.delaybeforesend:
            self.pty.delaybeforesend = self.delaybeforesend
        time.sleep(0.2)
        log.debug("CONNECT starts Expect Buffer ID={}".format(
            hex(id(self.pty))))
        return self.pty

    def get_console(self, logger=None):
        if self.state == SerialConsoleState.DISCONNECTED:
            self.connect(logger)

        count = 0
        while (not self.pty.isalive()):
            log.warning('# Reconnecting')
            if (count > 0):
                time.sleep(BMC_CONST.IPMI_SOL_ACTIVATE_TIME)
            self.connect()
            count += 1
            if count > 120:
                raise("not able to get serial console")
        if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
            self.util.setup_term(self.system, self.pty,
                                 None, self.system.block_setup_term)

        return self.pty

    def run_command(self, command, timeout=60, retry=0):
        return self.util.run_command(self, command, timeout, retry)

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.util.run_command_ignore_fail(self, command, timeout, retry)
