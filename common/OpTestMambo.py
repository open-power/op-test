#!/usr/bin/env python2
#
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

'''
Support testing against Mambo simulator
'''

import sys
import time
import pexpect
import subprocess
import os

from common.Exceptions import CommandFailed, ParameterCheck
import OPexpect
from OpTestUtil import OpTestUtil

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class MamboConsole():
    '''
    A 'connection' to the Mambo Console involves *launching* Mambo.
    Closing a connection will *terminate* the Mambo process.
    '''
    def __init__(self, mambo_binary=None,
            mambo_initial_run_script=None,
            mambo_autorun=None,
            skiboot=None,
            prompt=None,
            kernel=None,
            initramfs=None,
            block_setup_term=None,
            delaybeforesend=None,
            logfile=sys.stdout):
        self.mambo_binary = mambo_binary
        self.mambo_initial_run_script = mambo_initial_run_script
        self.mambo_autorun = mambo_autorun
        self.skiboot = skiboot
        self.kernel = kernel
        self.initramfs = initramfs
        self.state = ConsoleState.DISCONNECTED
        self.logfile = logfile
        self.delaybeforesend = delaybeforesend
        self.system = None
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        self.block_setup_term = block_setup_term # allows caller specific control of when to block setup_term
        self.setup_term_quiet = 0 # tells setup_term to not throw exceptions, like when system off
        self.setup_term_disable = 0 # flags the object to abandon setup_term operations, like when system off

        # state tracking, reset on boot and state changes
        # console tracking done on System object for the system console
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
        try:
            rc_child = self.pty.close()
            exitCode = signalstatus = None
            if self.pty.status != -1: # leaving for debug
              if os.WIFEXITED(self.pty.status):
                exitCode = os.WEXITSTATUS(self.pty.status)
              else:
                signalstatus = os.WTERMSIG(self.pty.status)
            self.state = ConsoleState.DISCONNECTED
        except pexpect.ExceptionPexpect as e:
            self.state = ConsoleState.DISCONNECTED
            raise "Mambo Console: failed to close console"
        except Exception as e:
            self.state = ConsoleState.DISCONNECTED
            pass
        log.debug("Mambo close -> TERMINATE")

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            return self.pty
        else:
            self.util.clear_state(self) # clear when coming in DISCONNECTED

        log.debug("#Mambo Console CONNECT")

        if not os.access(self.mambo_initial_run_script, os.R_OK|os.W_OK):
            raise ParameterCheck(message="Check that the file exists with"
                " R/W permissions mambo-initial-run-script={}"
                .format(self.mambo_initial_run_script))

        cmd = ("%s" % (self.mambo_binary)
               + " -e"
               + " -f {}".format(self.mambo_initial_run_script)
           )

        spawn_env = {}
        if self.skiboot:
            spawn_env['SKIBOOT'] = self.skiboot
        if self.kernel:
            spawn_env['SKIBOOT_ZIMAGE'] = self.kernel
        if self.initramfs:
            if not os.access(self.initramfs, os.R_OK|os.W_OK):
                raise ParameterCheck(message="Check that the file exists with"
                    " R/W permissions flash-initramfs={}"
                    .format(self.initramfs))
            spawn_env['SKIBOOT_INITRD'] = self.initramfs
        if self.mambo_autorun:
            spawn_env['SKIBOOT_AUTORUN'] = str(self.mambo_autorun)
        log.debug("OpTestMambo cmd={} mambo spawn_env={}".format(cmd, spawn_env))
        try:
          self.pty = OPexpect.spawn(cmd,
              logfile=self.logfile,
              env=spawn_env)
        except Exception as e:
          self.state = ConsoleState.DISCONNECTED
          raise CommandFailed('OPexpect.spawn',
                  'OPexpect.spawn encountered a problem: ' + str(e), -1)

        self.state = ConsoleState.CONNECTED
        self.pty.setwinsize(1000,1000)
        if self.delaybeforesend:
          self.pty.delaybeforesend = self.delaybeforesend

        if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
          self.util.setup_term(self.system, self.pty, None, self.system.block_setup_term)

        time.sleep(0.2)
        if not self.pty.isalive():
            raise CommandFailed(cmd, self.pty.read(), self.pty.status)
        return self.pty

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.util.clear_state(self)
            self.connect()
        else:
            if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
                self.util.setup_term(self.system, self.pty, None, self.system.block_setup_term)

        return self.pty

    def run_command(self, command, timeout=60, retry=0):
        return self.util.run_command(self, command, timeout, retry)

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.util.run_command_ignore_fail(self, command, timeout, retry)

    def mambo_run_command(self, command, timeout=60, retry=0):
        return self.util.mambo_run_command(self, command, timeout, retry)

    def mambo_exit(self):
        return self.util.mambo_exit(self)

    def mambo_enter(self):
        return self.util.mambo_enter(self)

class MamboIPMI():
    '''
    Mambo has fairly limited IPMI capability.
    '''
    def __init__(self, console):
        self.console = console

    def ipmi_power_off(self):
        """For Mambo, this just kills the simulator"""
        self.console.close()

    def ipmi_wait_for_standby_state(self, i_timeout=10):
        """For Mambo, we just kill the simulator"""
        self.console.close()

    def ipmi_set_boot_to_petitboot(self):
        return 0

    def ipmi_sel_check(self, i_string="Transition to Non-recoverable"):
        pass

    def ipmi_sel_elist(self, dump=False):
        pass

    def ipmi_set_no_override(self):
        pass

    def sys_set_bootdev_no_override(self):
        pass

class OpTestMambo():
    def __init__(self, mambo_binary=None,
                 mambo_initial_run_script=None,
                 mambo_autorun=None,
                 skiboot=None,
                 kernel=None,
                 initramfs=None,
                 prompt=None,
                 block_setup_term=None,
                 delaybeforesend=None,
                 logfile=sys.stdout):
        self.console = MamboConsole(mambo_binary=mambo_binary,
            mambo_initial_run_script=mambo_initial_run_script,
            mambo_autorun=mambo_autorun,
            skiboot=skiboot,
            kernel=kernel,
            initramfs=initramfs,
            logfile=logfile)
        self.ipmi = MamboIPMI(self.console)
        self.system = None

    def set_system(self, system):
        self.console.system = system

    def get_host_console(self):
        return self.console

    def run_command(self, command, timeout=10, retry=0):
        # mambo only supports system console object, not this bmc object
        return None # at least return something and have the testcase handle

    def get_ipmi(self):
        return self.ipmi

    def power_off(self):
        self.console.close()

    def power_on(self):
        self.console.connect()

    def get_rest_api(self):
        return None

    def has_os_boot_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_inband_bootdev(self):
        return False

    def supports_ipmi_dcmi(self):
        return False

    def has_ipmi_sel(self):
        return False
