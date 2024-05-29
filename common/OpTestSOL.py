#!/usr/bin/env python3
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

import time
import threading
import pexpect
import os

import OpTestConfiguration
from .OpTestSystem import OpSystemState

import logging
from logging.handlers import RotatingFileHandler
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpSOLMonitorThread(threading.Thread):
    '''
    This thread just monitors the SOL console for any failures when tests are running
    on other SSH threads
    '''

    def __init__(self, threadID, name, execution_time=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.execution_time = execution_time
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.system.goto_state(OpSystemState.OS)
        logfile = os.path.join(conf.output, "console.log")
        self.sol_logger(logfile)
        self.c = self.system.console.get_console(logger=self.logger)
        self.c_terminate = False

    def run(self):
        log.debug("Starting %s" % self.name)
        if self.execution_time:
            self.timeout_run()
        else:
            self.nontimeout_run()
        log.debug("Exiting %s" % self.name)

    def timeout_run(self):
        execution_time = time.time() + 60 * self.execution_time
        log.debug("Starting %s for new SOL thread" % self.name)
        while True:
            try:
                self.c.expect("\n", timeout=60)
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                self.c.close()
                self.c = self.system.console.get_console()
            if time.time() > execution_time:
                break
        log.debug("Thread exiting after run for desired time")

    def nontimeout_run(self):
        log.debug("Starting %s for new SOL thread" % self.name)
        while True:
            try:
                self.c.expect("\n", timeout=60)
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                self.c.close()
                self.c = self.system.console.get_console()

            if self.c_terminate:
                break
        log.debug("Terminating SOL monitoring thread")

    def console_terminate(self):
        self.c_terminate = True

    def sol_logger(self, logfile):
        '''
        Non fomated console log.
        '''
        self.logger = logging.getLogger("sol-thread")
        self.logger.setLevel(logging.DEBUG)
        file_handler = RotatingFileHandler(
            logfile, maxBytes=2000000, backupCount=10)
        self.logger.addHandler(file_handler)
