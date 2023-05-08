#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/LparConfig.py $
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

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class LparConfig(unittest.TestCase):


    def setUp(self):

        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
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
            log.info("Functionality is supported only on LPAR")

    def verify_profile(self, proc_mode):

    '''
    This function verifies if lpar is in shared mode or dedicated mode, takes mode as argument.
    '''

        curr_proc_mode = self.cv_HMC.run_command("lshwres -r proc -m %s --level lpar --filter lpar_names=%s -F curr_proc_mode" %
                                                (self.system_name, self.lpar_name))
        if proc_mode in curr_proc_mode:
            log.info("System booted with %s mode" % proc_mode)
        else:
            self.fail("Failed to boot in %s mode" % proc_mode)

    def shudown_lpar(self):
        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o shutdown -n %s" %
                               (self.system_name, self.lpar_name))
        time.sleep(30)

    def poweron_lpar(self):
        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -n %s -f %s" %
                               (self.system_name, self.lpar_name, self.lpar_prof))
        time.sleep(30)

class ChangeToSharedMode(LparConfig):

    '''
    This class takes backup of current profile to default_profile_bck.
    changes lpar profile to shared mode.
    Shutdown the lpar.
    Activates the lpar in shared mode.
    Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
    Ex:
        sharing_mode=uncap
        min_proc_units=1.0
        max_proc_units=2.0
        desired_proc_units=2.0
    '''

    def setUp(self):
        super(ChangeToSharedMode, self).setUp()
        conf = OpTestConfiguration.conf
        try: self.sharing_mode = conf.args.sharing_mode
        except AttributeError:
            self.sharing_mode = "cap"
        try: self.min_proc_units = conf.args.min_proc_units
        except AttributeError:
            self.min_proc_units = "1.0"
        try: self.desired_proc_units = conf.args.desired_proc_units
        except AttributeError:
            self.desired_proc_units = "2.0"
        try: self.max_proc_units = conf.args.max_proc_units
        except AttributeError:
            self.max_proc_units = "2.0"

    def runTest(self):
        self.cv_HMC.run_command("mksyscfg -r prof -m %s -o save -p %s -n %s_bck --force" %
                               (self.system_name, self.lpar_name, self.lpar_prof))
        self.cv_HMC.set_lpar_cfg("proc_mode=shared,sharing_mode=%s,min_proc_units=%s,max_proc_units=%s,desired_proc_units=%s" %
                                (self.sharing_mode, self.min_proc_units, self.max_proc_units, self.desired_proc_units))
        self.shudown_lpar()
        self.poweron_lpar()
        self.verify_profile('shared') 

class ChangeToDedicatedMode(LparConfig):

    '''
    This class takes backup of current profile to default_profile_bck.
    changes lpar profile to dedicated mode.
    Shutdown the lpar.
    Activates the lpar in dedicated mode.
    Pass sharing_mode, min_proc_units, max_proc_units and desired_proc_units in config file.
    '''

    def setUp(self):
        super(ChangeToDedicatedMode, self).setUp()
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

    def runTest(self):
        self.cv_HMC.run_command("mksyscfg -r prof -m %s -o save -p %s -n %s_bck --force" %
                               (self.system_name, self.lpar_name, self.lpar_prof))
        self.cv_HMC.set_lpar_cfg("proc_mode=ded,sharing_mode=%s,min_procs=%s,max_procs=%s,desired_procs=%s" %
                                (self.sharing_mode, self.min_proc_units, self.max_proc_units, self.desired_proc_units))
        self.shudown_lpar()
        self.poweron_lpar()
        self.verify_profile('ded')


class EnableVtpm(LparConfig):

    '''
    This class enables vtpm on the lpar.
    '''

    def setUp(self):
        super(EnableVtpm, self).setUp()
        conf = OpTestConfiguration.conf

    def runTest(self):
        self.shudown_lpar()
        self.cv_HMC.run_command("chsyscfg -r lpar -m %s -i \"name=%s, vtpm_enabled=1\"" %
                               (self.system_name, self.lpar_name))
        time.sleep(10)
        vtpm_enabled = self.cv_HMC.run_command("lssyscfg -m %s -r lpar --filter lpar_names=%s -F vtpm_enabled" %
                                              (self.system_name, self.lpar_name))
        if vtpm_enabled[0] == "1":
            log.info("System booted with VTPM enabled")
        else:
            self.fail("Failed to boot with vtpm enabled")
        self.poweron_lpar()

class ConfigurePmem(LparConfig):

    '''
    This class creates vpmem volume of specified size if lpar doesnot have any vpmem volume.
    '''

    def setUp(self):
        super(ConfigurePmem, self).setUp()
        conf = OpTestConfiguration.conf
        try: self.pmem_name = conf.args.pmem_name
        except AttributeError:
            self.pmem_name = "vol1"
        try: self.pmem_size = conf.args.pmem_size
        except AttributeError:
            self.pmem_size = "8192"

    def vpmem_count(self):
        return self.cv_HMC.run_command("lshwres -r pmem -m %s --level lpar --filter lpar_names=%s -F curr_num_volumes" %
                                      (self.system_name, self.lpar_name))

    def runTest(self):
        curr_num_volumes = self.vpmem_count()
        if curr_num_volumes[0] >= "1":
            self.skipTest("System already have vpmem volume.")
        self.shudown_lpar()
        self.cv_HMC.run_command("chhwres -r pmem -m %s -o a --rsubtype volume --volume %s --device dram -p %s -a size=%s,affinity=1" %
                               (self.system_name, self.pmem_name, self.lpar_name, self.pmem_size))
        curr_num_volumes = self.vpmem_count()
        if curr_num_volumes[0] >= "1":
            log.info("Configured vpmem %s of %sMB" % (self.pmem_name, self.pmem_size))
        else:
            self.fail("Failed to configure pmem")
        self.poweron_lpar()

class RestoreConfig(LparConfig):

    '''
    This class boots the lpar with previous profile, this can be called after ChangeToSharedMode or ChangeToDedicatedMode.
    '''

    def setUp(self):
        super(RestoreConfig, self).setUp()
        conf = OpTestConfiguration.conf

    def runTest(self):
        self.shudown_lpar()
        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -n %s -f %s_bck" %
                               (self.system_name, self.lpar_name, self.lpar_prof))
        time.sleep(30)
        self.cv_HMC.run_command("mksyscfg -r prof -m %s -o save -p %s -n %s --force" %
                               (self.system_name, self.lpar_name, self.lpar_prof))
        time.sleep(30)
        self.shudown_lpar()
        self.poweron_lpar()
        self.cv_HMC.run_command("rmsyscfg -r prof -m %s -n %s_bck -p %s" %
                               (self.system_name, self.lpar_prof, self.lpar_name))
        time.sleep(30)
