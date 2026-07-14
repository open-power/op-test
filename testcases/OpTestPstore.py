#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPstore.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2020
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
OpTestPstore
------------

This module can contain testcases related to Pstore.
1. Trigger crash.
2. Check new files are created or not under /sys/fs/pstore
'''

import time
import subprocess
import re
import sys
import pexpect
import os
import time


from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestSOL import OpSOLMonitorThread
from common import OpTestHMC, OpTestFSP

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.Exceptions import KernelOOPS, KernelKdump, KernelPanic, KernelFADUMP

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestPstore(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.con = self.cv_SYSTEM.console
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
    
    def kernel_crash(self):
        try:
            self.con.run_command( "echo c > /proc/sysrq-trigger")
        except (KernelOOPS, KernelKdump, KernelPanic, KernelFADUMP):
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            
    def pstore_file_check(self):
        #This function will validate new files are created
        #or not under /sys/fs/pstore after crash
        time_init = self.con.run_command( "date +%s")
        result = self.con.run_command( 'ls -1 /sys/fs/pstore')
        l = []
        for line in result:
            files_list =  "".join(re.findall("[a-zA-Z]",line))
            l.append(files_list)
        for i in result:
            self.con.run_command( "cd /sys/fs/pstore")
            time_created = self.con.run_command( "stat -c%%Z %s" % i)
            if (time_init > time_created):
                print("New file %s is created" % i)
            else:
                print("New file %s is not created" % i)

            
class Pstore(OpTestPstore):

    def setup_test(self):
        self.con.run_command( "which stty && stty cols 300; which stty && stty rows 30")
        self.con.run_command( "uname -a")
        res = self.con.run_command( "cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.distro = 'SLES'
            self.con.run_command( "sed -i -e 's/crashkernel=.* / /' -e 's/crashkernel=.*/\"/' /etc/default/grub")
            self.con.run_command( "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.con.run_command( "sync; sync; sleep 5")
            self.con.run_command( "sed -i '/GRUB_CMDLINE_LINUX_DEFAULT/s/\"$/ crashkernel=2G-4G:512M,4G-64G:1024M,64G-128G:2048M,128G-:4096M\"/' /etc/default/grub")
            self.con.run_command( "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.con.run_command( "sync; sync; sleep 5")
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        elif 'Red Hat Enterprise Linux' in res[0].strip():
            self.distro = 'RHEL'
        else:
            self.skipTest("Currently test is supported only on sles and rhel")
        res = self.con.run_command( "systemctl status kdump.service | grep active")
        if 'exited' not in res[0].strip():
            print("Kdump service is not configured properly")

    def runTest(self):
        self.setup_test()
        print("=================== Testing Kdump=======================")
        self.kernel_crash()
        self.pstore_file_check()
        print("=================Kdump Disable==========================")
        self.con.run_command("service kdump stop")
        self.con.run_command("echo 10 > /proc/sys/kernel/panic")
        self.kernel_crash()
        self.pstore_file_check()
