#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
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
#

'''
OpTestLPM
---------

This test is to preform and validate basic Live Partition Mobility(LPM)  migration
from source to destination managed system
'''

import unittest
import time
import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestLPM(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.console = self.cv_SYSTEM.console
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.src_mg_sys = self.cv_HMC.mg_system
        self.dest_mg_sys = self.cv_HMC.tgt_mg_system

    def lpar_migrate_test(self):
        if not self.cv_HMC.migrate_lpar(self.src_mg_sys, self.dest_mg_sys):
            raise OpTestError("Lpar Migration failed")
        log.debug("Wait for 5 minutes before migrating lpar back") 
        time.sleep(300) #delay of 5 mins after migration.
        log.debug("Migrating lpar back to original managed system")
        if not self.cv_HMC.migrate_lpar(self.dest_mg_sys,  self.src_mg_sys):
            raise OpTestError("Migrating lpar back failed")

    def runTest(self):
        self.lpar_migrate_test()
