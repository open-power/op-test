#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/MachineConfig.py $
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
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class MachineConfig(unittest.TestCase):


    def setUp(self):

        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.bmc_type = conf.args.bmc_type
        if self.bmc_type == "FSP_PHYP" or self.bmc_type == "EBMC_PHYP" :
            self.hmc_user = conf.args.hmc_username
            self.hmc_password = conf.args.hmc_password
            self.hmc_ip = conf.args.hmc_ip
            self.lpar_name = conf.args.lpar_name
            self.system_name = conf.args.system_name
            self.cv_HMC = self.cv_SYSTEM.hmc
            self.lpar_prof = conf.args.lpar_prof
        else:
            self.skipTest("Functionality is supported only on LPAR")


class LparConfig(MachineConfig):

    '''
    pass lpar_config in config file indicating proc mode, vtpm and vpmem.
    valid values: cpu=shared or cpu=dedicated
                  vtpm=1 or vtpm=0
                  vpmem=0 or vpmem=1
    Ex: lpar_config="cpu=dedicated,vtpm=1,vpmem=1"
    ''' 

    def setUp(self):
        super(LparConfig, self).setUp()
        conf = OpTestConfiguration.conf
        try: self.lpar_config = conf.args.lpar_config
        except AttributeError:
            self.lpar_config = "cpu=shared, vtpm=1, vpmem=1"

    def runTest(self):

        '''
        If cpu=shared is passed in lpar_config lpar proc mode changes to shared mode.
        Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
        Ex:
        sharing_mode=uncap
        min_proc_units=1.0
        max_proc_units=2.0
        desired_proc_units=2.0
        overcommit_ratio=3
        '''

        if "cpu=shared" in self.lpar_config:
            conf = OpTestConfiguration.conf
            try: self.sharing_mode = conf.args.sharing_mode
            except AttributeError:
                self.sharing_mode = "cap"
            try: self.min_proc_units = float(conf.args.min_proc_units)
            except AttributeError:
                self.min_proc_units = 1.0
            try: self.desired_proc_units = float(conf.args.desired_proc_units)
            except AttributeError:
                self.desired_proc_units = 2.0
            try: self.max_proc_units = float(conf.args.max_proc_units)
            except AttributeError:
                self.max_proc_units = 2.0
            try: self.overcommit_ratio = int(conf.args.overcommit_ratio)
            except AttributeError:
                self.overcommit_ratio = 1
            proc_mode = 'shared'
            self.cv_HMC.profile_bckup()
            self.cv_HMC.change_to_shared_mode(self.sharing_mode, self.min_proc_units,
                                              self.desired_proc_units, self.max_proc_units, self.overcommit_ratio)

        '''
        If cpu=dedicated is passed in lpar_config lpar proc mode changes to dedicated mode.
        Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
        Ex:
        sharing_mode=share_idle_procs
        min_proc_units=1
        max_proc_units=2
        desired_proc_units=2
        '''

        if "cpu=dedicated" in self.lpar_config:
            conf = OpTestConfiguration.conf
            try: self.sharing_mode = conf.args.sharing_mode
            except AttributeError:
                self.sharing_mode = "share_idle_procs"
            try: self.min_proc_units = conf.args.min_proc_units
            except AttributeError:
                self.min_proc_units = "1"
            try: self.desired_proc_units = conf.args.desired_proc_units
            except AttributeError:
                self.desired_proc_units = "2"
            try: self.max_proc_units = conf.args.max_proc_units
            except AttributeError:
                self.max_proc_units = "2"
            proc_mode = 'ded'
            self.cv_HMC.profile_bckup()
            self.cv_HMC.change_to_dedicated_mode(self.sharing_mode, self.min_proc_units,
                                                 self.desired_proc_units, self.max_proc_units)


        if "vtpm=1" in self.lpar_config:
            self.vtpm_mode = '1'
            self.cv_HMC.enable_disable_vtpm(self.vtpm_mode)
            vtpm_enabled = self.cv_HMC.vtpm_state()
            if vtpm_enabled[0] == "1":
                log.info("System booted with VTPM enabled")
            else:
                self.fail("Failed to boot with vtpm enabled")

        elif "vtpm=0" in self.lpar_config:
            self.vtpm_mode = '0'
            self.cv_HMC.enable_disable_vtpm(self.vtpm_mode)
            vtpm_enabled = self.cv_HMC.vtpm_state()
            if vtpm_enabled[0] == "0":
                log.info("System booted with VTPM disabled")
            else:
                self.fail("Failed to boot with vtpm disabled")


        if "vpmem=1" in self.lpar_config:
            try: self.pmem_name = conf.args.pmem_name
            except AttributeError:
                self.pmem_name = "vol1"
            try: self.pmem_size = conf.args.pmem_size
            except AttributeError:
                self.pmem_size = "8192"
            curr_num_volumes = self.cv_HMC.vpmem_count()
            if curr_num_volumes[0] >= "1":
                log.info("System already have vpmem volume.")
            else:
                self.cv_HMC.configure_vpmem(self.pmem_name, self.pmem_size)
                curr_num_volumes = self.cv_HMC.vpmem_count()
                if curr_num_volumes[0] >= "1":
                    log.info("Configured vpmem %s of %sMB" % (self.pmem_name, self.pmem_size))
                else:
                    self.fail("Failed to configure pmem")


        self.cv_HMC.poweron_lpar()
        curr_proc_mode = self.cv_HMC.get_proc_mode()
        if proc_mode in curr_proc_mode:
            log.info("System booted with %s mode" % proc_mode)
        else:
            self.fail("Failed to boot in %s mode" % proc_mode)


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


class CecConfig(MachineConfig):

    '''
    This class configures LMB. Pass lmb_size to cec_config in config file.
    Ex: cec_config="lmb=4GB, hugepage=16GB"
    Valid LMB values are "128,256,1024,2048,4096"
    '''

    def setUp(self):
        super(CecConfig, self).setUp()
        conf = OpTestConfiguration.conf
        try: self.cec_config = conf.args.cec_config
        except AttributeError:
            self.cec_config="lmb=256"

    def runTest(self):
        if "lmb=4GB" in self.cec_config or "lmb=4096" in self.cec_config:
            self.lmb_size=4096
        elif "lmb=2GB" in self.cec_config or "lmb=2048" in self.cec_config:
            self.lmb_size=2048
        elif "lmb=1GB" in self.cec_config or "lmb=1024" in self.cec_config:
            self.lmb_size=1024
        elif "lmb=256MB" in self.cec_config or "lmb=256" in self.cec_config:
            self.lmb_size=256
        elif "lmb=128MB" in self.cec_config or "lmb=128" in self.cec_config:
            self.lmb_size=128
        else:
            self.skipTest("Please pass valid LMB size in config file ex: 128,256,1024,2048,4096")
        self.cv_HMC.configure_lmb(self.lmb_size)
        self.cv_HMC.poweroff_system()
        self.cv_HMC.poweron_system()
        current_lmb = self.cv_HMC.get_lmb_size()
        if int(current_lmb[0]) == int(self.lmb_size):
            log.info("System booted with LMB %s" % self.lmb_size)
        else:
            self.fail("Failed to boot with LMB %s" % self.lmb_size)
        if self.cv_HMC.lpar_vios:
            self.cv_HMC.poweron_lpar()
        else:
            log.info("Pass lpar_vios in config file to activate vios and lpar")
