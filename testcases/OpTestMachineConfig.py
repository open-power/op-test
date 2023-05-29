#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestMachineConfig.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
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


import os
import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common import OpTestInstallUtil
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestMachineConfig(unittest.TestCase):


    def setUp(self):

        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        if self.bmc_type == "FSP_PHYP" or self.bmc_type == "EBMC_PHYP" :
            self.hmc_user = conf.args.hmc_username
            self.hmc_password = conf.args.hmc_password
            self.hmc_ip = conf.args.hmc_ip
            self.lpar_name = conf.args.lpar_name
            self.system_name = conf.args.system_name
            self.cv_HMC = self.cv_SYSTEM.hmc
            self.lpar_prof = conf.args.lpar_prof
            self.c = self.cv_HMC.get_host_console()
            self.hmc_con = self.cv_HMC.ssh
            self.size_hgpg = conf.args.size_hgpg
            self.mmulist = self.c.run_command("tail /proc/cpuinfo | grep MMU")
            self.mmu = str(self.mmulist[0]).split(':')[1].strip()
        else:
            self.cancel("Functionality is supported only on LPAR")

class HugepageOsConfig(OpTestMachineConfig):

    '''
    This class checkf for whether the MMU is Radix or Hash.
    If MMU is Radix then depending upon the user input it
    will create 2M or 1G Hugepages.
    If MMU is Hash then upon user input it will create
    16M Hugepages
    And also validates the Hugepages created
    '''

    def setUp(self):
        super(HugepageOsConfig, self).setUp()
        self.obj = OpTestInstallUtil.InstallUtil()
        self.os_level = self.cv_HOST.host_get_OS_Level()

    def runTest(self):
        if self.size_hgpg not in ("16M", "2M", "1G"):
            self.fail("Provided Hugepage is not supported")
        exist_cfg = self.cv_HMC.get_lpar_cfg()
        self.des_mem = int(exist_cfg.get('desired_mem'))
        self.percentile = int(self.des_mem * 0.1)
        if 'Radix' in self.mmu:
            if self.size_hgpg == "16M":
                self.fail("16M is not supported in Radix")
            elif self.size_hgpg == "2M":
                self.no_hp = int(self.percentile / int(self.size_hgpg.rstrip('M')))
            elif self.size_hgpg == "1G":
                self.no_hp = int(self.percentile / (int(self.size_hgpg.rstrip('G')) * 1024))

            self.obj.update_kernel_cmdline(self.os_level,
                                           "hugepagesz=%s hugepages=%s" % (
                                           self.size_hgpg, self.no_hp),
                                           "",
                                           reboot=True,
                                           reboot_cmd=True)
        elif 'Hash' in self.mmu and self.size_hgpg == "16M":
            self.no_hp = int(self.percentile / int(self.size_hgpg.rstrip('M')))
            self.obj.update_kernel_cmdline(self.os_level,
                                           "hugepagesz=%s hugepages=%s" % (
                                            self.size_hgpg, self.no_hp),
                                            "",
                                            reboot=True,
                                            reboot_cmd=True)
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        filename_part1 = "cat /sys/kernel/mm/hugepages/hugepages-"
        filename_part2 = "kB/nr_hugepages"
        if self.size_hgpg == "2M":
            assign_hp = con.run_command("%s%s%s" % (filename_part1,"2048",filename_part2))[0]
        elif self.size_hgpg == "1G":
            assign_hp = con.run_command("%s%s%s" % (filename_part1,"1048576",filename_part2))[0]
        elif self.size_hgpg == "16M":
            assign_hp = con.run_command("%s%s%s" % (filename_part1,"16777216",filename_part2))[0]
        if str(self.no_hp) != assign_hp:
            msg = "Expected %s: But found %s" % (self.no_hp, assign_hp)
            self.fail(msg)
        else:
            log.info("%s Hugepage validation successful!" % self.size_hgpg)
