#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

import OpTestSystem
from OpTestUtil import OpTestUtil
from Exceptions import CommandFailed, SSHSessionDisconnected
import re
import sys
import os
import time
import pexpect

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

try:
    from common import OPexpect
except ImportError:
    import OPexpect

sudo_responses = ["not in the sudoers",
                  "incorrect password"]


class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1


def set_system_to_UNKNOWN_BAD(system):
    s = system.get_state()
    system.set_state(OpTestSystem.OpSystemState.UNKNOWN_BAD)
    return s


class OpTestSSH():
    def __init__(self, host, username, password, logfile=sys.stdout, port=22,
                 prompt=None, check_ssh_keys=False, known_hosts_file=None,
                 block_setup_term=None, delaybeforesend=None, use_parent_logger=True):
        self.state = ConsoleState.DISCONNECTED
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.logfile = logfile
        self.check_ssh_keys = check_ssh_keys
        self.known_hosts_file = known_hosts_file
        self.delaybeforesend = delaybeforesend
        self.system = None
        # OpTestUtil instance is NOT conf's
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        # allows caller specific control of when to block setup_term
        self.block_setup_term = block_setup_term
        # tells setup_term to not throw exceptions, like when system off
        self.setup_term_quiet = 0
        # flags the object to abandon setup_term operations, like when system off
        self.setup_term_disable = 0

        # ssh state tracking, reset on boot and state changes
        # ssh port 2200 console tracking not done on SSH object, its done on System object for the system console
        self.PS1_set = -1
        self.LOGIN_set = -1
        self.SUDO_set = -1
        self.use_parent_logger = use_parent_logger

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
        if self.state == ConsoleState.DISCONNECTED:
            return
        try:
            self.pty.send("\r")
            self.pty.send('~.')
            close_rc = self.pty.expect(
                [pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            log.debug("CLOSE Expect Buffer ID={}".format(hex(id(self.pty))))
            rc_child = self.pty.close()
            exitCode = signalstatus = None
            if self.pty.status != -1:  # leaving here for debug
                if os.WIFEXITED(self.pty.status):
                    exitCode = os.WEXITSTATUS(self.pty.status)
                else:
                    signalstatus = os.WTERMSIG(self.pty.status)
            self.state = ConsoleState.DISCONNECTED
        except pexpect.ExceptionPexpect as e:
            self.state = ConsoleState.DISCONNECTED
            raise "SSH Console: failed to close ssh console"
        except Exception as e:
            self.state = ConsoleState.DISCONNECTED
            pass

    def connect(self, logger=None):
        if self.state == ConsoleState.CONNECTED:
            rc_child = self.close()
            self.state = ConsoleState.DISCONNECTED
        else:
            self.util.clear_state(self)  # clear when coming in DISCONNECTED

        cmd = ("sshpass -p %s " % (self.password)
               + " ssh"
               + " -p %s" % str(self.port)
               + " -l %s %s" % (self.username, self.host)
               + " -o PubkeyAuthentication=no -o afstokenpassing=no"
               )

        if not self.check_ssh_keys:
            cmd = (cmd
                   + " -q"
                   + " -o 'UserKnownHostsFile=/dev/null' "
                   + " -o 'StrictHostKeyChecking=no'"
                   )
        elif self.known_hosts_file:
            cmd = (cmd + " -o UserKnownHostsFile=" + self.known_hosts_file)

        # For multi threades SSH sessions use individual logger and file handlers per session.
        if logger:
            self.log = logger
        elif self.use_parent_logger:
            self.log = log
        else:
            self.log = OpTestLogger.optest_logger_glob.get_custom_logger(
                __name__)

        self.log.debug(cmd)

        try:
            self.pty = OPexpect.spawn(cmd,
                                      logfile=self.logfile,
                                      failure_callback=set_system_to_UNKNOWN_BAD,
                                      failure_callback_data=self.system)
        except Exception as e:
            self.state = ConsoleState.DISCONNECTED
            raise CommandFailed("OPexepct.spawn encountered a problem", e, -1)

        self.state = ConsoleState.CONNECTED
        # set for bash, otherwise it takes the 24x80 default
        self.pty.setwinsize(1000, 1000)
        if self.delaybeforesend:
            self.pty.delaybeforesend = self.delaybeforesend
        self.pty.logfile_read = OpTestLogger.FileLikeLogger(self.log)
        # delay here in case messages like afstokenpassing unsupported show up which mess up setup_term
        time.sleep(2)
        self.check_set_term()
        log.debug("CONNECT starts Expect Buffer ID={}".format(hex(id(self.pty))))
        return self.pty

    def check_set_term(self):
        if self.block_setup_term is not None:
            setup_term_flag = self.block_setup_term  # caller control
        else:
            setup_term_flag = self.system.block_setup_term  # system defined control
        if self.port == 2200:
            if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
                self.util.setup_term(self.system, self.pty,
                                     None, setup_term_flag)
        else:
            if self.SUDO_set != 1 or self.LOGIN_set != 1 or self.PS1_set != 1:
                self.util.setup_term(self.system, self.pty,
                                     self, setup_term_flag)

    def get_console(self, logger=None):
        if self.state == ConsoleState.DISCONNECTED:
            self.connect(logger)
            if self.pty.isalive():
                # connect() will have already setup term
                return self.pty

        count = 0
        while (not self.pty.isalive()):
            self.log.info('# Reconnecting')
            if (count > 0):
                time.sleep(1)
            self.connect()
            count += 1
            if count > 120:
                raise "SSH: not able to get console"

        self.check_set_term()

        return self.pty

    def run_command(self, command, timeout=60, retry=0):
        return self.util.run_command(self, command, timeout, retry)

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.util.run_command_ignore_fail(self, command, timeout, retry)
