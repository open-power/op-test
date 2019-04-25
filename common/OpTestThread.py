#!/usr/bin/python2
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
#

'''
Multithreaded library
---------------------
This adds a new multithreaded library with having different
variants of thread based SSH/SOL session runs, each thread logs
to a different log file.
'''
from __future__ import absolute_import

import random
import unittest
import time
import threading
import pexpect

import OpTestConfiguration
from .OpTestSystem import OpSystemState
from .OpTestConstants import OpTestConstants as BMC_CONST
from .Exceptions import CommandFailed
from .OpTestIPMI import IPMIConsoleState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpSSHThreadLinearVar1(threading.Thread):
    '''
    Runs a list of commands in a loop with equal sleep times in linear order
    '''
    def __init__(self, threadID, name, cmd_list, sleep_time, execution_time, ignore_fail=False):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.cmd_list = cmd_list
        self.sleep_time = sleep_time
        self.execution_time = execution_time
        self.ignore_fail = ignore_fail
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.c = self.host.get_new_ssh_connection(name)

    def run(self):
        log.debug("Starting %s" % self.name)
        self.inband_child_thread(self.name, self.cmd_list, self.sleep_time, self.execution_time, self.ignore_fail)
        log.debug("Exiting %s" % self.name)

    def inband_child_thread(self, threadName, cmd_list, sleep_time, torture_time, ignore_fail):
        execution_time = time.time() + 60*torture_time,
        log.debug("Starting %s for new SSH thread %s" % (threadName, cmd_list))
        while True:
            for cmd in cmd_list:
                if ignore_fail:
                    try:
                        self.c.run_command(cmd)
                    except CommandFailed as cf:
                        pass
                else:
                    self.c.run_command(cmd)
                time.sleep(sleep_time)
            if time.time() > execution_time:
                break
        log.debug("Thread exiting after run for desired time")

class OpSSHThreadLinearVar2(threading.Thread):
    '''
    Runs a dictionary of command(command, sleep time) pairs with each having individual sleep times
    '''
    def __init__(self, threadID, name, cmd_dic, execution_time, ignore_fail=False):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.cmd_dic = cmd_dic
        self.execution_time = execution_time
        self.ignore_fail = ignore_fail
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.c = self.host.get_new_ssh_connection(name)

    def run(self):
        log.debug("Starting %s" % self.name)
        self.inband_child_thread(self.name, self.cmd_dic, self.execution_time, self.ignore_fail)
        log.debug("Exiting %s" % self.name)

    def inband_child_thread(self, threadName, cmd_dic, torture_time, ignore_fail):
        execution_time = time.time() + 60*torture_time,
        log.debug("Starting %s for new SSH thread %s" % (threadName, cmd_dic))
        while True:
            for cmd, tm in cmd_dic.items():
                if ignore_fail:
                    try:
                        self.c.run_command(cmd)
                    except CommandFailed as cf:
                        pass
                else:
                    self.c.run_command(cmd)
                time.sleep(tm)
            if time.time() > execution_time:
                break
        log.debug("Thread exiting after run for desired time")

class OpSSHThreadRandom(threading.Thread):
    '''
    Runs a random command from a list of commands in a loop with equal sleep times
    '''
    def __init__(self, threadID, name, cmd_list, sleep_time, execution_time, ignore_fail=False):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.cmd_list = cmd_list
        self.sleep_time = sleep_time
        self.execution_time = execution_time
        self.ignore_fail = ignore_fail
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.c = self.host.get_new_ssh_connection(name)

    def run(self):
        log.debug("Starting %s" % self.name)
        self.inband_child_thread(self.name, self.cmd_list, self.sleep_time, self.execution_time, self.ignore_fail)
        log.debug("Exiting %s" % self.name)

    def inband_child_thread(self, threadName, cmd_list, sleep_time, torture_time, ignore_fail):
        execution_time = time.time() + 60*torture_time,
        log.debug("Starting %s for new SSH thread %s" % (threadName, cmd_list))
        while True:
            cmd = random.choice(cmd_list)
            if ignore_fail:
                try:
                    self.c.run_command(cmd)
                except CommandFailed as cf:
                    pass
            else:
                self.c.run_command(cmd)
            if time.time() > execution_time:
                break
            time.sleep(sleep_time)
        log.debug("Thread exiting after run for desired time")


