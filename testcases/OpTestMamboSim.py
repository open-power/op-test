#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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
# POWER9 Functional Simulator User Guide
# http://public.dhe.ibm.com/software/server/powerfuncsim/p9/docs/P9funcsim_ug_v1.0_pub.pdf
#
# POWER9 Functional Simulator Command Reference Guide
# http://public.dhe.ibm.com/software/server/powerfuncsim/p9/docs/P9funcsim_cr_v1.0_pub.pdf

'''
Mambo Sim
---------
Tests that illustrate the use cases and provides comments on special handling
needed to switch context between the target OS and the Mambo simulator.

Debug logging is done to output both examples of command run and to
provide pertinent information regarding the state of the mambo config.

'''

import unittest
import time
import pexpect

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
import common.OpTestMambo as OpTestMambo

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestMamboSim(unittest.TestCase):
    '''
    Provide an illustrative example of class methods to run
    both target OS commands as well as switching to the
    Mambo Simulator and running mambo commands and then switching back
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.host = conf.host()
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.prompt = self.system.util.build_prompt()
        self.c = self.system.console
        self.pty = self.c.get_console()
        if not isinstance(self.c, OpTestMambo.MamboConsole):
            raise unittest.SkipTest(
                "Must be running Mambo to perform this test")

    def runTest(self):
        # need to first perform run_command initially
        # which sets up the pexpect prompt for subsequent run_command(s)

        # mambo echos twice so turn off
        # this stays persistent even after switching context
        # from target OS to mambo and back
        self.c.run_command('stty -echo')

        target_OS_command_1 = "lsprop /sys/firmware/devicetree/base/ibm,opal/firmware"
        lsprop_output = self.c.run_command(target_OS_command_1)
        log.debug("target OS command 1 '{}'".format(target_OS_command_1))
        for i in lsprop_output:
            log.debug("lsprop output = {}".format(i))

        # exit target OS and enter mambo
        self.c.mambo_enter()

        # mambo command
        mambo_command_1 = "mysim of print"
        mambo_output = self.c.mambo_run_command(mambo_command_1)
        log.debug("mambo command 1 '{}'".format(mambo_command_1))
        for i in mambo_output:
            log.debug("mysim of print output = {}".format(i))

        # return to target OS
        self.c.mambo_exit()
        # need to sync pexpect buffer from mambo_exit
        # extra character appears and depending on commands
        # run in mambo caller may or may not want to sync
        # e.g. if mambo commands were queued and results need parsed
        self.pty.sendline()  # sync up pexpect buffer
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)

        lsprop_output = self.c.run_command(
            'lsprop /sys/firmware/devicetree/base/ibm,opal/firmware')
        cmdline_output = self.c.run_command('cat /proc/cmdline')

        # exit target OS and enter mambo
        self.c.mambo_enter()

        mambo_command_2 = "ls --color=never -l /"
        mambo_command_3 = "nvram --partitions"
        mambo_command_4 = "cat /proc/powerpc/eeh"
        mambo_command_5 = "cat /proc/cmdline"
        mambo_command_6 = "cat /sys/devices/system/cpu/present"
        mambo_command_7 = "cat /proc/version"
        # mysim command 2
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_2))

        # mysim command 3
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_3))

        # mysim command 4
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_4))

        # mysim command 5
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_5))

        # mysim command 6
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_6))

        # mysim command 7
        self.c.mambo_run_command(
            "mysim console create input in string \"{}\"".format(mambo_command_7))

        # return to target OS
        self.c.mambo_exit()

        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 2 '{}'".format(mambo_command_2))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 2 before=\"{}\"".format(i))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 3 '{}'".format(mambo_command_3))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 3 before=\"{}\"".format(i))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 4 '{}'".format(mambo_command_4))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 4 before=\"{}\"".format(i))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 5 '{}'".format(mambo_command_5))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 5 before=\"{}\"".format(i))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 6 '{}'".format(mambo_command_6))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 6 before=\"{}\"".format(i))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        log.debug("mambo command 7 '{}'".format(mambo_command_7))
        for i in self.pty.before.replace("\r\r\n", "\n").splitlines():
            log.debug("mambo command 7 before=\"{}\"".format(i))

        # exit target OS and enter mambo
        self.c.mambo_enter()

        # mysim command 8
        self.c.mambo_run_command(
            "mysim console create input in string \"echo 'hello world command 8'\"")

        # mambo commands
        version_list = self.c.mambo_run_command("version list")
        log.debug("version list={}".format(version_list))
        define_list = self.c.mambo_run_command(
            "define list")  # list machines available
        log.debug("define list ={}".format(define_list))
        # all active configuration objects and machines
        display_configures = self.c.mambo_run_command("display configures")
        log.debug("display configures={}".format(display_configures))

        # return to target OS
        # queued_echo_output will NOT contain the command 8 echo of 'hello world command 8'
        # when returning to the target OS the pexpect buffer is awaiting retrieval, "expecting"
        queued_echo_output = self.c.mambo_exit()
        log.debug("mambo_exit command 8 queued_echo_output={}".format(
            queued_echo_output))
        rc = self.pty.expect(
            [self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        # now retrieve the echo output which sat awaiting
        log.debug("delayed queued_echo_output=\"{}\"".format(self.pty.before))

        osrelease = self.c.run_command('ls --color=never -al /etc/os-release')
        for i in osrelease:
            log.debug("osrelease={}".format(i))
