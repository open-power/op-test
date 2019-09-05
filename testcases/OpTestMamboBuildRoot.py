#!/usr/bin/env python3
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
Test for Mambo Sim with BuildRoot Env
Usage:
Sample config looks like:
$ cat mambo.cfg
[op-test]
bmc_type=mambo
mambo_binary=./mambo/p9/systemsim-p9-release/run/p9/run_cmdline
flash_skiboot=./mambo/p9/skiboot/skiboot.lid
flash_kernel=./mambo/linux/vmlinux
flash_initramfs=./mambo/mamboinit.img
host_user=root
host_password=

$ ./op-test -c mambo.cfg --run testcases.OpTestMamboBuildRoot.OpTestMamboBuildRoot

Note:
for mambo/power-simulator binary/package can be obtained from
ftp://public.dhe.ibm.com/software/server/powerfuncsim/
mamboinit.img is a image obtained from compiling https://github.com/open-power/buildroot
skiboot.lid is obtained by compiling https://github.com/open-power/skiboot
checkout readme of respective respositories for how to compile.
'''

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
import common.OpTestMambo as OpTestMambo

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestMamboBuildRoot(unittest.TestCase):
    '''
    Mambo Build Root test
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.host = conf.host()
        self.system.goto_state(OpSystemState.OS)
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

        uname_output = self.c.run_command('uname -a')
        log.debug("uname = {}".format(uname_output))
        cpuinfo_output = self.c.run_command('cat /proc/cpuinfo')
        log.debug("cpuinfo = {}".format(cpuinfo_output))
        int_output = self.c.run_command('cat /proc/interrupts')
        log.debug("interrupts = {}".format(int_output))
