#!/usr/bin/env python3
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

'''
Petitboot MMU
----------

This test verifies that the petitboot kernel has booted with the expected MMU mode
for the processor. This means hash for P8 and radix for P9 onwards.
'''

import unittest

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class PetitbootMMU(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console

        log.debug("Scraping /proc/cpuinfo for CPU and MMU info")
        cpu = self.c.run_command(
            "awk '$1 == \"cpu\" {print $3}' /proc/cpuinfo | uniq")[0].strip(',')
        mmu = self.c.run_command(
            "awk '$1 == \"MMU\" {print $3}' /proc/cpuinfo")[0]
        log.debug("Got CPU '{}' and MMU '{}'".format(cpu, mmu))

        if cpu == 'POWER8':
            self.assertEqual(
                mmu, 'Hash', 'Expect hash MMU on Power8, found {}'.format(mmu))
        elif cpu == 'POWER9':
            self.assertEqual(
                mmu, 'Radix', 'Expect radix MMU on Power9, found {}'.format(mmu))
        else:
            self.skipTest(
                "Unknown CPU '{}', please update testcase to support this CPU")
