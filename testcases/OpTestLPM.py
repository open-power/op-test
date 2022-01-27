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


    @staticmethod
    def errMsg(vios_name, mg_system):
        raise OpTestError("Mover Service Partition (MSP) for VIOS %s" \
        " (in managed system %s) not enabled" % (vios_name, mg_system))

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.console = self.cv_SYSTEM.console
        self.cv_HOST = conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.src_mg_sys = self.cv_HMC.mg_system
        self.dest_mg_sys = self.cv_HMC.tgt_mg_system
        self.oslevel = None
        self.slot_num = None
        self.options = None
        if conf.args.lpar_vios and 'remote_lpar_vios' in conf.args:
            self.src_lpar_vios = self.cv_HMC.lpar_vios.split(",")
            self.dest_lpar_vios = conf.args.remote_lpar_vios.split(",")
            for vios_name in self.src_lpar_vios:
                if not self.cv_HMC.is_msp_enabled(self.src_mg_sys, vios_name):
                    self.errMsg(vios_name, self.src_mg_sys)
            for vios_name in self.dest_lpar_vios:
                if not self.cv_HMC.is_msp_enabled(self.dest_mg_sys, vios_name):
                    self.errMsg(vios_name, self.dest_mg_sys)
        if 'slot_num' in conf.args:
            self.slot_num = conf.args.slot_num
        if self.slot_num:
            self.bandwidth = conf.args.bandwidth
            self.options = conf.args.options
            self.adapters = conf.args.adapters.split(",")
            self.target_adapters = conf.args.target_adapters.split(",")
            self.ports = conf.args.ports.split(",")
            self.target_ports = conf.args.target_ports.split(",")
            self.vios_id = []
            for vios_name in self.src_lpar_vios:
                self.vios_id.append(self.cv_HMC.get_lpar_id(self.src_mg_sys, vios_name))
            self.target_vios_id = []
            for vios_name in self.dest_lpar_vios:
                self.target_vios_id.append(self.cv_HMC.get_lpar_id(self.dest_mg_sys, vios_name))
            self.adapter_id = []
            for adapter in self.adapters:
                self.adapter_id.append(self.cv_HMC.get_adapter_id(self.src_mg_sys, adapter))
            self.target_adapter_id = []
            for adapter in self.target_adapters:
                self.target_adapter_id.append(self.cv_HMC.get_adapter_id(self.dest_mg_sys, adapter))

    def check_pkg_installation(self):
        pkg_found = True
        pkg_notfound = []
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

    def vnic_options(self, remote=''):
        '''
        Form the vnic_mappings param based on the adapters' details
        provided.
        '''
        if int(self.slot_num) < 3 or int(self.slot_num) > 2999:
            return ""
        if remote:
            cmd = []
            for index in range(0, len(self.adapters)):
                l_cmd = []
                for param in [self.slot_num, 'ded', self.src_lpar_vios[index],
                              self.vios_id[index], self.adapter_id[index],
                              self.ports[index], self.bandwidth,
                              self.target_adapter_id[index],
                              self.target_ports[index]]:
                    l_cmd.append(param)
                cmd.append("/".join(l_cmd))
        else:
            cmd = []
            for index in range(0, len(self.adapters)):
                l_cmd = []
                for param in [self.slot_num, 'ded',
                              self.dest_lpar_vios[index],
                              self.target_vios_id[index],
                              self.target_adapter_id[index],
                              self.target_ports[index], self.bandwidth,
                              self.adapter_id[index], self.ports[index]]:
                    l_cmd.append(param)
                cmd.append("/".join(l_cmd))

        return " -i \"vnic_mappings=%s\" " % ",".join(cmd)

    def lpar_migrate_test(self):
        self.check_pkg_installation()
        self.lpm_setup()
        cmd = ''
        if self.slot_num:
            cmd = self.vnic_options()
        if not self.cv_HMC.migrate_lpar(self.src_mg_sys, self.dest_mg_sys, self.options, cmd):
            raise OpTestError("Lpar Migration failed")
        log.debug("Wait for 5 minutes before migrating lpar back")
        time.sleep(300)  # delay of 5 mins after migration.
        if self.slot_num:
            cmd = self.vnic_options('remote')
        log.debug("Migrating lpar back to original managed system")
        if not self.cv_HMC.migrate_lpar(self.dest_mg_sys,  self.src_mg_sys, self.options, cmd):
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
