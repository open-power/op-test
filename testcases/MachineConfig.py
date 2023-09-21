#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/MachineConfig.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
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
import re
import json

import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common import OpTestInstallUtil
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class MachineConfig(unittest.TestCase):

    def setUp(self):

        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type
        self.machine_config = json.loads(conf.args.machine_config)
        if self.bmc_type == "FSP_PHYP" or self.bmc_type == "EBMC_PHYP":
            self.hmc_user = conf.args.hmc_username
            self.hmc_password = conf.args.hmc_password
            self.hmc_ip = conf.args.hmc_ip
            self.lpar_name = conf.args.lpar_name
            self.system_name = conf.args.system_name
            self.cv_HMC = self.cv_SYSTEM.hmc
            self.lpar_prof = conf.args.lpar_prof
            self.lpar_flag = False
            try:
                self.lpar_list = conf.args.lpar_list
            except AttributeError:
                self.lpar_list = ""
            self.util = OpTestUtil(conf)
        else:
            self.skipTest("Functionality is supported only on LPAR")

    def validate_secureboot_parameter(self, machine_config):
        '''
        Checks the validity of the states, set as parameter in the configuration file.
        Valid states are either 'on' or 'off'.
        Return :
        True  - if secureboot is set to 'on'
        False - if secureboot is set to 'off'
        '''
        sb_valid_states = ['on', 'off']
        secureboot_parameter_state = re.findall(
            "secureboot=[a-z][a-z]+", str(machine_config))[0].split('=')[1]
        if str(secureboot_parameter_state) not in sb_valid_states:
            self.skipTest("%s is not a valid state for secureboot. "
                          "Secureboot valid states can be either set to 'on' or 'off'" % str(secureboot_parameter_state))
        if secureboot_parameter_state == 'on':
            return True
        else:
            return False

    def update_hmc_object(self, target_hmc_ip, target_hmc_username, target_hmc_password,
                          managed_system, lpar_name):
        """
        In case of multi lpar configuration here we are creating multiple objects[In sequence] as per 
        lpar change.
        """
        conf = OpTestConfiguration.conf
        self.cv_HMC = OpTestHMC.OpTestHMC(target_hmc_ip,
                                          target_hmc_username,
                                          target_hmc_password,
                                          managed_system=managed_system,
                                          lpar_name=lpar_name,
                                          lpar_prof=conf.args.lpar_prof
                                          )
        self.cv_HMC.set_system(conf.system())

    def runTest(self):
        if self.lpar_list != "":
            self.lpar_list = self.lpar_list.split(",")
            self.lpar_list.append(self.lpar_name)
            self.lpar_flag = True
            for lpar in self.lpar_list:
                lpar = lpar.strip()
                self.update_hmc_object(
                    self.hmc_ip, self.hmc_user, self.hmc_password, self.system_name, lpar)
                for key in self.machine_config:
                    self.callConfig(key, lpar)
        else:
            for key in self.machine_config:
                self.callConfig(key)

    def callConfig(self, key, lpar=""):

        if lpar != "":
            self.lpar_name = lpar

        status = 0
        if key == "lpar":
            self.sb_enable = None
            config_value = self.machine_config['lpar']
            if 'secureboot' in config_value:
                self.sb_enable = self.validate_secureboot_parameter(
                    self.machine_config)
            status = LparConfig(self.cv_HMC, self.system_name, self.lpar_name, self.lpar_prof,
                                self.machine_config['lpar'], sb_enable=self.sb_enable).LparSetup(self.lpar_flag)
            if status:
                self.fail(status)

        if key == "cec":
            lmb_size = None
            num_hugepages = None
            setup = 0
            if not self.cv_HMC.lpar_vios:
                self.skipTest("Please pass lpar_vios in config file.")
            config_value = self.machine_config['cec']
            valid_size = [128, 256, 1024, 2048, 4096]
            if "lmb" in config_value:
                setup = 1
                lmb_size = re.findall(
                    'lmb=[0-9]+', str(self.machine_config))[0].split('=')[1]
                if int(lmb_size) not in valid_size:
                    self.skipTest("%s is not valid lmb size, "
                                  "valid lmb sizes are 128, 256, 1024, 2048, 4096" % lmb_size)
            if "hugepages" in config_value:
                setup = 1
                num_hugepages = re.findall(
                    'hugepages=[0-9]+', str(self.machine_config))[0].split('=')[1]

            status = CecConfig(self.cv_HMC, self.system_name, self.lpar_name,
                               self.lpar_prof, lmb=lmb_size, hugepages=num_hugepages).CecSetup()
            if status:
                self.fail(status)
            if not setup:
                self.skipTest("Not implemented for other CEC settings")

        if key == "os":
            setup = 0
            sb_enable = None
            hugepage_size = None
            config_value = self.machine_config['os']
            valid_size = ['2M', '1G', '16M', '16G']
            if 'hugepage' in config_value:
                setup = 1
                hugepage_size = re.findall(
                    "hugepage=[0-9]+[A-Z]", str(self.machine_config))[0].split('=')[1]
                if str(hugepage_size) not in valid_size:
                    self.skipTest("%s is not valid hugepage size, "
                                  "valid hugepage sizes are 1G, 2M, 16M, 16G" % hugepage_size)
            if 'secureboot' in config_value:
                setup = 1
                sb_enable = self.validate_secureboot_parameter(
                    self.machine_config)
            status = OsConfig(self.cv_HMC, self.system_name, self.lpar_name, self.lpar_prof,
                              self.machine_config['os'], enable=sb_enable, hugepage=hugepage_size).Ossetup()
            if status:
                self.fail(status)
            if not setup:
                self.skipTest("Not implemented for other OS settings")


class LparConfig():

    '''
    pass machine_config in config file indicating proc mode, vtpm and vpmem.
    valid values: cpu=shared or cpu=dedicated
                  vtpm=1 or vtpm=0
                  vpmem=0 or vpmem=1
    Ex: machine_config="cpu=dedicated,vtpm=1,vpmem=1"
    '''

    def __init__(self, cv_HMC=None, system_name=None,
                 lpar_name=None, lpar_prof=None, machin_config=None, sb_enable=None):
        self.cv_HMC = cv_HMC
        self.system_name = system_name
        self.lpar_name = lpar_name
        self.lpar_prof = lpar_prof
        self.machine_config = machin_config
        self.hmc_con = self.cv_HMC.ssh
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HMC.poweroff_lpar()
        self.util = OpTestUtil(conf)
        self.sb_enable = sb_enable

    def LparSetup(self, lpar_config=""):
        '''
        If cpu=shared is passed in machine_config lpar proc mode changes to shared mode.
        Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
        Ex:
        sharing_mode=uncap
        min_proc_units=1.0
        max_proc_units=2.0
        desired_proc_units=2.0
        overcommit_ratio=3
        '''
        proc_mode = None
        if "cpu=shared" in self.machine_config:
            conf = OpTestConfiguration.conf
            try:
                self.sharing_mode = conf.args.sharing_mode
            except AttributeError:
                self.sharing_mode = "cap"
            try:
                self.min_proc_units = float(conf.args.min_proc_units)
            except AttributeError:
                self.min_proc_units = 1.0
            try:
                self.desired_proc_units = float(conf.args.desired_proc_units)
            except AttributeError:
                self.desired_proc_units = 2.0
            try:
                self.max_proc_units = float(conf.args.max_proc_units)
            except AttributeError:
                self.max_proc_units = 2.0
            try:
                self.overcommit_ratio = int(conf.args.overcommit_ratio)
            except AttributeError:
                self.overcommit_ratio = 1
            proc_mode = 'shared'
            curr_proc_mode = self.cv_HMC.get_proc_mode()
            if proc_mode in curr_proc_mode and lpar_config == True:
                log.info("System is already booted in shared mode.")
            else:
                self.cv_HMC.profile_bckup()
                self.cv_HMC.change_proc_mode(proc_mode, self.sharing_mode, self.min_proc_units,
                                             self.desired_proc_units, self.max_proc_units, self.overcommit_ratio)

        '''
        If cpu=dedicated is passed in machine_config lpar proc mode changes to dedicated mode.
        Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
        Ex:
        sharing_mode=share_idle_procs
        min_proc_units=1
        max_proc_units=2
        desired_proc_units=2
        '''

        if "cpu=dedicated" in self.machine_config:
            conf = OpTestConfiguration.conf
            try:
                self.sharing_mode = conf.args.sharing_mode
            except AttributeError:
                self.sharing_mode = "share_idle_procs"
            try:
                self.min_proc_units = conf.args.min_proc_units
            except AttributeError:
                self.min_proc_units = "1"
            try:
                self.desired_proc_units = conf.args.desired_proc_units
            except AttributeError:
                self.desired_proc_units = "2"
            try:
                self.max_proc_units = conf.args.max_proc_units
            except AttributeError:
                self.max_proc_units = "2"
            proc_mode = 'ded'
            curr_proc_mode = self.cv_HMC.get_proc_mode()
            if proc_mode in curr_proc_mode:
                log.info("System is already booted in dedicated mode.")
            else:
                self.cv_HMC.profile_bckup()
                self.cv_HMC.change_proc_mode(proc_mode, self.sharing_mode, self.min_proc_units,
                                             self.desired_proc_units, self.max_proc_units)

        if "vtpm=1" in self.machine_config:
            conf = OpTestConfiguration.conf
            vtpm_enabled = self.cv_HMC.vtpm_state()
            if vtpm_enabled[0] == "1":
                log.info("System is already booted with VTPM enabled")
            else:
                proc_compat_mode = self.cv_HMC.get_proc_compat_mode()
                if "POWER10" in proc_compat_mode:
                    self.vtpm_version = 2.0
                    try:
                        self.vtpm_encryption = conf.args.vtpm_encryption
                    except AttributeError:
                        self.vtpm_encryption = "Power10v1"
                elif proc_compat_mode[0] in ["POWER9_base", "POWER9", "POWER8"]:
                    self.vtpm_version = 1.2
                else:
                    log.info("Unknown processor compact mode")
                self.cv_HMC.enable_vtpm(
                    self.vtpm_version, self.vtpm_encryption)
                vtpm_enabled = self.cv_HMC.vtpm_state()
                if vtpm_enabled[0] == "1":
                    log.info("System booted with VTPM enabled")
                else:
                    return "Failed to boot with vtpm enabled"

        elif "vtpm=0" in self.machine_config:
            vtpm_enabled = self.cv_HMC.vtpm_state()
            if vtpm_enabled[0] == "0":
                log.info("System is already booted with VTPM disabled")
            else:
                self.vtpm_mode = '0'
                self.cv_HMC.disable_vtpm()
                vtpm_enabled = self.cv_HMC.vtpm_state()
                if vtpm_enabled[0] == "0":
                    log.info("System booted with VTPM disabled")
                else:
                    return "Failed to boot with vtpm disabled"

        if "vpmem=1" in self.machine_config:
            conf = OpTestConfiguration.conf
            try:
                self.pmem_name = conf.args.pmem_name
            except AttributeError:
                self.pmem_name = "vol1"
            try:
                self.pmem_size = conf.args.pmem_size
            except AttributeError:
                self.pmem_size = "8192"
            if self.cv_HMC.vpmem_count()[0] >= "1":
                self.cv_HMC.remove_vpmem()
            current_lmb = self.cv_HMC.get_lmb_size()
            if int(self.pmem_size) % int(current_lmb[0]) != 0:
                self.fail("pmem_size should be multiple of %s" % current_lmb)
            self.cv_HMC.configure_vpmem(self.pmem_name, self.pmem_size)
            curr_num_volumes = self.cv_HMC.vpmem_count()
            if curr_num_volumes[0] >= "1":
                log.info("Configured vpmem %s of %sMB" %
                         (self.pmem_name, self.pmem_size))
            else:
                return "Failed to configure pmem"

        if "nx_gzip" in self.machine_config:
            conf = OpTestConfiguration.conf
            try:
                self.qos_credits = round(float(conf.args.qos_credits))
            except AttributeError:
                self.qos_credits = 10
            proc_compat_mode = self.cv_HMC.get_proc_compat_mode()
            if "POWER10" in proc_compat_mode:
                self.cv_HMC.configure_gzip_qos(self.qos_credits)
            else:
                log.info("nx_gzip is supported only in Power10 mode")

        """
        If ioslots=drc_name is passed in machine_config lpar profile gets updated with this change
        """

        if "slot=" in self.machine_config:
            ioslot_drc_names = "".join(
                self.machine_config[self.machine_config.index("slot=")+len("slot=")+1:])
            ioslot_drc_names = ",".join(ioslot_drc_names[:ioslot_drc_names.index("=")].split(",")[:-1]) \
                               if "=" in ioslot_drc_names else ioslot_drc_names
            self.cv_HMC.add_ioslot(ioslot_drc_names)

        if self.sb_enable is not None:
            self.cv_HMC.hmc_secureboot_on_off(self.sb_enable)

        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -n %s -f %s" %
                                (self.system_name, self.lpar_name, self.lpar_prof))
        time.sleep(5)
        curr_proc_mode = self.cv_HMC.get_proc_mode()
        if proc_mode:
            if proc_mode in curr_proc_mode:
                log.info("System booted with %s mode" % proc_mode)
            else:
                return "Failed to boot in %s mode" % proc_mode


class RestoreLAPRConfig(MachineConfig):

    '''
    This class boots the lpar with previous profile, this can be called after ChangeToSharedMode or ChangeToDedicatedMode.
    '''

    def setUp(self):
        super(RestoreLAPRConfig, self).setUp()
        conf = OpTestConfiguration.conf

    def runTest(self):
        self.cv_HMC.poweroff_lpar()
        self.cv_HMC.lpar_prof = self.cv_HMC.lpar_prof + "_bck"
        self.cv_HMC.poweron_lpar()


class CecConfig():

    '''
    This class configures LMB. Pass lmb_size to machine_config in config file.
    Ex: machine_config={"cec":"lmb=4096"}
    Valid LMB values are "128,256,1024,2048,4096"

    It also configures 16gb hugepages on CEC. Pass hugepages to machine_config
    in config file
    Ex: machine_config={"cec":"hugepages=4"}
    '''

    def __init__(self, cv_HMC=None, system_name=None,
                 lpar_name=None, lpar_prof=None, lmb=None, hugepages=None):

        self.cv_HMC = cv_HMC
        self.system_name = system_name
        self.lpar_name = lpar_name
        self.lpar_prof = lpar_prof
        self.lmb_size = lmb
        self.num_hugepages = hugepages
        self.setup = 0
        self.cec_dict = {'lmb_cec': None, 'hugepages': None}

    def CecSetup(self):

        self.ValidateCEC_Setup()
        if any(value is not None for value in self.cec_dict.values()):
            self.cv_HMC.poweroff_system()
        if self.cec_dict['lmb_cec'] is not None:
            self.lmb_setup()
        if self.cec_dict['hugepages'] is not None:
            self.hugepage_16gb_setup()
        if self.setup:
            self.cv_HMC.poweron_system()
            self.ValidateCEC_Setup()
            # loading system
            self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -n %s -f %s" %
                                    (self.system_name, self.lpar_name, self.lpar_prof))
            time.sleep(5)

    def ValidateCEC_Setup(self):

        if self.lmb_size:
            current_lmb = self.cv_HMC.get_lmb_size()
            if int(current_lmb[0]) == int(self.lmb_size):
                log.info("System booted with LMB %s" % self.lmb_size)
            else:
                self.cec_dict['lmb_cec'] = self.lmb_size
        if self.num_hugepages:
            self.current_hgpg = self.cv_HMC.get_16gb_hugepage_size()
            if int(self.current_hgpg[0]) != 0:
                log.info("System configured with %s 16gb Hugepage" %
                         self.current_hgpg[0])
                self.cv_HMC.poweroff_lpar()
                self.setting_16gb_hugepage_profile()
            else:
                self.cec_dict['hugepages'] = self.num_hugepages

    def lmb_setup(self):
        # Configure the lmb as per user request
        self.cv_HMC.configure_lmb(self.lmb_size)
        self.setup = 1

    def hugepage_16gb_setup(self):
        # configure the number of 16gb hugepages as per user request
        self.cv_HMC.configure_16gb_hugepage(self.num_hugepages)
        self.setup = 1

    def setting_16gb_hugepage_profile(self):
        self.current_hgpg = self.cv_HMC.get_16gb_hugepage_size()
        attrs = "min_num_huge_pages={0},desired_num_huge_pages={0},max_num_huge_pages={0}" .format(
            int(self.current_hgpg[0]))
        self.cv_HMC.set_lpar_cfg(attrs)


class OsConfig():
    '''
    This Class assign  huge page in the system   based on MMU either Radix or hash and validate
    MMU is Radix : 2M or 1 GB Huge page
    MMU HASH :  16M or 16GB
    pass hgpgsize to machine_config in config file
    '''

    def __init__(self, cv_HMC=None, system_name=None,
                 lpar_name=None, lpar_prof=None, machine_config=None, hugepage=None, enable=None):
        self.cv_HMC = cv_HMC
        self.system_name = system_name
        self.lpar_name = lpar_name
        self.lpar_prof = lpar_prof
        self.machine_config = machine_config
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.c = self.cv_HMC.get_host_console()
        self.hmc_con = self.cv_HMC.ssh
        self.mmulist = self.c.run_command("tail /proc/cpuinfo | grep MMU")
        self.mmu = str(self.mmulist[0]).split(':')[1].strip()
        self.obj = OpTestInstallUtil.InstallUtil()
        self.os_level = self.cv_HOST.host_get_OS_Level()
        self.size_hgpg = hugepage
        self.enable = enable
        self.util = OpTestUtil(conf)

    def Ossetup(self):
        if self.size_hgpg:
            self.OsHugepageSetup()
        if self.enable is not None:
            if not self.util.os_secureboot_enable(enable=self.enable):
                return "secure boot os setting failed"

    def OsHugepageSetup(self):

        filename_part1 = "cat /sys/kernel/mm/hugepages/hugepages-"
        filename_part2 = "kB/nr_hugepages"
        if self.size_hgpg == "16G":
            self.num_hgpg = self.cv_HMC.get_16gb_hugepage_size()
            self.no_hgpg = int(self.num_hgpg[0])
            if self.no_hgpg != 0:
                self.configure_os_16gb_hugepage()
                con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
                assign_hp = con.run_command("%s%s%s" % (
                    filename_part1, "16777216", filename_part2))[0]
            else:
                return "16gb hugepages are not configured in CEC"
        else:
            exist_cfg = self.cv_HMC.get_lpar_cfg()
            self.des_mem = int(exist_cfg.get('desired_mem'))
            self.percentile = int(self.des_mem * 0.1)
            if 'Radix' in self.mmu:
                if self.size_hgpg == "16M":
                    self.fail("16M is not supported in Radix")
                elif self.size_hgpg == "2M":
                    self.no_hgpg = int(self.percentile / 2)
                elif self.size_hgpg == "1G":
                    self.no_hgpg = int(self.percentile / 1024)

            elif 'Hash' in self.mmu and self.size_hgpg == "16M":
                self.no_hgpg = int(self.percentile / 16)
            self.obj.update_kernel_cmdline(self.os_level,
                                           "hugepagesz=%s hugepages=%s" % (
                                               self.size_hgpg, self.no_hgpg),
                                           "",
                                           reboot=True,
                                           reboot_cmd=True)
            con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            if self.size_hgpg == "2M":
                assign_hp = con.run_command("%s%s%s" % (
                    filename_part1, "2048", filename_part2))[0]
            elif self.size_hgpg == "1G":
                assign_hp = con.run_command("%s%s%s" % (
                    filename_part1, "1048576", filename_part2))[0]
            elif self.size_hgpg == "16M":
                assign_hp = con.run_command("%s%s%s" % (
                    filename_part1, "16384", filename_part2))[0]
        if str(self.no_hgpg) != assign_hp:
            msg = "Expected %s: But found %s" % (self.no_hgpg, assign_hp)
            return msg
        else:
            log.info("%s Hugepage validation successful!" % self.size_hgpg)

    def configure_os_16gb_hugepage(self):
        if 'Radix' in self.mmu:
            self.obj.update_kernel_cmdline(self.os_level,
                                           "default_hugepagesz=16G hugepagesz=16G hugepages=%s disable_radix=1" % int(
                                               self.num_hgpg[0]),
                                           "",
                                           reboot=True,
                                           reboot_cmd=True)

        elif 'Hash' in self.mmu:
            self.obj.update_kernel_cmdline(self.os_level,
                                           "default_hugepagesz=16G hugepagesz=16G hugepages=%s" % int(
                                               self.num_hgpg[0]),
                                           "",
                                           reboot=True,
                                           reboot_cmd=True)
