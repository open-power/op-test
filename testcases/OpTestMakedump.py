#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestMakedump.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2021
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
1. Trigger crash
2. Check for Vmcore captured or not
3. Run makedump on the vmcore captured
'''
import os
import time
import unittest

import OpTestConfiguration
from common import OpTestInstallUtil
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import KernelOOPS, KernelKdump


import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestMakedump(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.c = self.cv_SYSTEM.console

    def kernel_crash(self):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps
        1. Take backup of files under /var/crash.
        2. Trigger kernel crash: ``echo c > /proc/sysrq-trigger``
        '''
        self.c.run_command("mkdir -p /var/crash_bkp/")
        if len(self.c.run_command("ls -1 /var/crash")) != 0:
            self.c.run_command("mv /var/crash/* /var/crash_bkp/")
            self.c.run_command("sync")
            time.sleep(5)
        else:
            log.info("/var/crash/ directory is empty")
        self.c.run_command("echo 1 > /proc/sys/kernel/sysrq")
        try:
            self.c.run_command("echo c > /proc/sysrq-trigger")
        except (KernelOOPS, KernelKdump):
            self.cv_SYSTEM.goto_state(OpSystemState.OS)

class Makedump(OpTestMakedump):
    '''
    this function will test the vmcore is captured or not
    and run the makedump
    '''
    def makedump_check(self):
        res = self.c.run_command("ls -1 /var/crash/")
        crash_dir = self.c.run_command("cd /var/crash/%s" % res[0])
        res = self.c.run_command("ls")
        if 'vmcore' not in res[0]:
            self.fail("vmcore is not saved")
        else:
            log.info("vmcore is saved")
        self.c.run_command("makedumpfile -v")
        self.c.run_command("makedumpfile --split -d 31 -l vmcore dump3 dump4")
        self.c.run_command("makedumpfile --reassemble dump3 dump4 dump5")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile -b 8 -d 31 -l vmcore dump2")
        self.c.run_command("makedumpfile -f -d 31 -l vmcore dump6")
        self.c.run_command("makedumpfile --dump-dmesg vmcore log")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile --cyclic-buffer 1024 vmcore dump10")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile --split --splitblock-size 1024 vmcore dump12 dump13 dump14")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile --work-dir /tmp vmcore dump20")
        self.c.run_command("makedumpfile --non-mmap vmcore dump22")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile -D -d 31 -l vmcore dump1")
        self.c.run_command(" makedumpfile -D -d 31 -l vmcore dump41 --num-threads 8")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile -d 31 -c vmcore dump42")
        self.c.run_command("makedumpfile -d 31 -p vmcore dump43")
        self.c.run_command("rm -rf dump*")
        self.c.run_command("makedumpfile -d 31 -e vmcore --work-dir /tmp dump44")
        self.c.run_command("makedumpfile -d 31 -c vmcore dump51 --message-level 21")
    def runTest(self):
        self.kernel_crash()
        self.makedump_check()
