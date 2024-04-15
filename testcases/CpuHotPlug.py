#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEM.py $
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

'''
CPU Hotplug Testcase
--------------------

This test case is likely to catch bugs either in the kernel or in stop states
we put cores/threads into when we hot unplug them.
'''

# FIXME: Add a smaller version of this test to the normal host test suite
# FIXME: Work out a way to add this to the skiroot test suite.

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class CpuHotPlug(unittest.TestCase):
    '''
    Use the ``ppc64_cpu`` utility to turn SMT on/off and set to each possible
    SMT mode, which is effectively a CPU hotplug operation.
    Then start hotplugging CPU cores by using the ``ppc64_cpu`` utility to
    turn only a specific number of cores on.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        self.num_avail_cores = self.cv_HOST.host_get_core_count()
        smt_range = ["on", "off"] + \
            list(range(1, self.cv_HOST.host_get_smt()+1))
        log.debug("Possible smt values: %s" % smt_range)
        for smt in smt_range:
            self.c.run_command("ppc64_cpu --smt=%s" % str(smt))
            for core in range(1, self.num_avail_cores + 1):
                self.c.run_command("ppc64_cpu --cores-on=%s" % core)

    def tearDown(self):
        self.c.run_command("ppc64_cpu --smt=on")
        self.c.run_command("ppc64_cpu --cores-on=%s" % self.num_avail_cores)
        self.cv_HOST.host_gather_debug_logs()
