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
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestLPM(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.console = self.cv_SYSTEM.console
        self.cv_HOST = conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.src_mg_sys = self.cv_HMC.mg_system
        self.dest_mg_sys = self.cv_HMC.tgt_mg_system
        self.oslevel = None

    def check_pkg_installation(self):
        pkg_found = True
        pkg_notfound= []
        self.oslevel = self.cv_HOST.host_get_OS_Level()
        lpm_pkg_list = ["src", "rsct.core", "rsct.core.utils", "rsct.basic", "rsct.opt.storagerm", "DynamicRM"]
        for pkg in lpm_pkg_list:
            pkg_status = self.cv_HOST.host_check_pkg_installed(self.oslevel, pkg)
            if not pkg_status:
                pkg_found = False
                pkg_notfound.append(pkg)
        if pkg_found:
            return True
        raise OpTestError("Install the required packages : %s" % pkg_notfound)

    def lpm_setup(self):
        try:
            self.cv_HOST.host_run_command("systemctl status firewalld.service")
            self.firewall_status = True
            '''
            Systemctl returns 3 if the service is in stopped state, Hence it is a false failure,
            handling the same with exception with exitcode. 
            '''
        except CommandFailed as cf:
            if cf.exitcode == 3:
                self.firewall_status = False
        if self.firewall_status:
             self.cv_HOST.host_run_command("systemctl stop firewalld.service")
        rc = self.cv_HOST.host_run_command("lssrc -a | grep 'rsct \| rsct_rm'")
        if "inoperative" in str(rc):
            self.cv_HOST.host_run_command("startsrc -g rsct_rm; startsrc -g rsct")
            rc = self.cv_HOST.host_run_command("lssrc -a")
            if "inoperative" in str(rc):
                raise OpTestError("LPM cannot continue as some of rsct services are not active")

    def lpar_migrate_test(self):
        self.check_pkg_installation()
        self.lpm_setup()
        if not self.cv_HMC.migrate_lpar(self.src_mg_sys, self.dest_mg_sys):
            raise OpTestError("Lpar Migration failed")
        log.debug("Wait for 5 minutes before migrating lpar back") 
        time.sleep(300) #delay of 5 mins after migration.
        log.debug("Migrating lpar back to original managed system")
        if not self.cv_HMC.migrate_lpar(self.dest_mg_sys,  self.src_mg_sys):
            raise OpTestError("Migrating lpar back failed")

    def runTest(self):
        self.lpar_migrate_test()

    def tearDown(self):
        if self.firewall_status:
            self.cv_HOST.host_run_command("systemctl start firewalld.service")

def LPM_suite():
    s = unittest.TestSuite()
    s.addTest(OpTestLPM())
    return s
