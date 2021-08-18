#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDlpar.py $
#
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
# IBM_PROLOG_END_TAG
'''
OpTestHugepage
------------
Test does the following sequentially

1. Get the configured hugepages from LPAR profile
2. Update the LPAR grub with hugepage kernel commandline parameters
3. Power off the LPAR and managed system
4. Configure sample hugepages through ASM
5. Power on the managed system
6. Update the LPAR profile with incremented hugepages
7. Power on the LPAR with the profile
8. Verify if 16G hugepages are configured properly at OS level
9. Revert LPAR profile config and kernel parameters 

Pre-requisite:
LPAR must be set to normal boot
VIOS must be provided for whole system restart, if applicable
Profile of the LPAR must be provided
Other LPARs must be shutdown as a precaution
'''
import unittest
import time
import OpTestConfiguration
import OpTestLogger
from common import OpTestInstallUtil
from common.OpTestSystem import OpSystemState
LOG = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestHugepage(unittest.TestCase):
    """
    Class OpTestHugepage: Configure and boot with 16G hugepage
    """
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.cv_FSP = self.cv_SYSTEM.bmc

    def setupHugepage(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        exist_cfg = self.cv_HMC.get_lpar_cfg()
        self.des_hp = int(exist_cfg.get('desired_num_huge_pages', 0))
        self.min_hp = int(exist_cfg.get('min_num_huge_pages', 0))
        self.max_hp = int(exist_cfg.get('max_num_huge_pages', 0))
        self.os_level = self.cv_SYSTEM.cv_HOST.host_get_OS_Level()
        self.obj = OpTestInstallUtil.InstallUtil()
        self.obj.update_kernel_cmdline(self.os_level,
                                       "default_hugepagesz=16G hugepagesz=16G hugepages=%s" % str(
                                           self.des_hp + 2),
                                       "",
                                       reboot=True,
                                       reboot_cmd=True)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_HMC.poweroff_system()
        self.cv_FSP.cv_ASM.configure_hugepages(self.des_hp + 5)

    def validateHugepage(self):
        self.cv_HMC.poweron_system()
        attrs = "min_num_huge_pages=%s,desired_num_huge_pages=%s,max_num_huge_pages=%s" % (
            self.min_hp + 1, self.des_hp + 2, self.max_hp + 3)
        self.cv_HMC.set_lpar_cfg(attrs)
        # Same console can no longer connect after whole system reboot
        # Hence closing it here
        self.cv_SYSTEM.console.close()
        # Wait couple of minutes to make VIOS up after system comes up
        time.sleep(120)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        no_hp = con.run_command(
            "cat /sys/kernel/mm/hugepages/hugepages-16777216kB/nr_hugepages")[0]
        if str(self.des_hp + 2) != no_hp:
            msg = "Expected %s: But found %s" % (self.des_hp + 2, no_hp)
            self.fail(msg)
        else:
            LOG.info("16G Hugepage validation successful!")

    def cleanup(self):
        attrs = "min_num_huge_pages=%s,desired_num_huge_pages=%s,max_num_huge_pages=%s" % (
            self.min_hp, self.des_hp, self.max_hp)
        self.cv_HMC.set_lpar_cfg(attrs)
        self.obj.update_kernel_cmdline(self.os_level,
                                       "",
                                       "default_hugepagesz=16G hugepagesz=16G hugepages=%s" % str(
                                           self.des_hp + 2),
                                       reboot=True,
                                       reboot_cmd=True)


class Hugepage16GTest(OpTestHugepage, unittest.TestCase):
    '''
    Configure, Test and cleanup 16G hugepages
    '''

    def setUp(self):
        super(Hugepage16GTest, self).setUp()

    def runTest(self):
        self.setupHugepage()
        self.validateHugepage()

    def tearDown(self):
        self.cleanup()


def hugepage_suite():
    suite = unittest.TestSuite()
    suite.addTest(Hugepage16GTest())

    return suite
