#!/usr/bin/env python3
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

'''
OpTestResourceGroup
--------------------
Tests the full lifecycle of a Resource Group (RG) on a PowerVM managed system
via HMC privileged commands:

  1. create_rg   - Create RG2 with procs=4, affinity_priority=128
  2. list_rg     - Verify RG2 appears in lshwres output
  3. modify_rg   - Change affinity_priority to 64
  4. assign_lpar - Assign the LPAR to RG2
  5. remove_lpar - Remove the LPAR from RG2
  6. delete_rg   - Delete RG2 and verify it is gone

Prerequisites in machine.conf:
  hmc_ip             = <HMC IP>
  hmc_username       = <non-root HMC user, e.g. hscpe>
  hmc_password       = <password>
  hmc_root_password  = passw0rd
  system_name        = <managed system, e.g. ltcden14>
  lpar_name          = <LPAR name>
'''

import unittest
import OpTestConfiguration
import OpTestLogger
from common.OpTestError import OpTestError

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

RG_NAME = "RG2"
RG_GID  = 2
RG_PROCS = 4
RG_AFFINITY = 128


class OpTestResourceGroup(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.lpar_name = conf.args.lpar_name
        self.system_name = conf.args.system_name
        # Ensure any leftover RG from a previous failed run is cleaned up
        self._cleanup_rg(ignore_errors=True)

    # ------------------------------------------------------------------ #
    #  Individual test methods                                             #
    # ------------------------------------------------------------------ #

    def test_1_create_rg(self):
        '''Create resource group RG2 with procs=4, affinity_priority=128'''
        log.info("Creating resource group '%s' (gid=%s, procs=%s, "
                 "affinity_priority=%s)" % (RG_NAME, RG_GID, RG_PROCS, RG_AFFINITY))
        self.cv_HMC.create_resource_group(RG_NAME, gid=RG_GID,
                                          procs=RG_PROCS,
                                          affinity_priority=RG_AFFINITY)
        self.assertTrue(self._rg_exists(),
                        "RG '%s' not found after creation" % RG_NAME)
        log.info("PASS: resource group '%s' created successfully" % RG_NAME)

    def test_2_list_rg(self):
        '''Verify RG2 is visible in lshwres output'''
        log.info("Listing resource groups on %s" % self.system_name)
        output = self.cv_HMC.list_resource_groups()
        log.info("lshwres output: %s" % output)
        self.assertTrue(self._rg_exists(),
                        "RG '%s' not found in list_resource_groups()" % RG_NAME)
        log.info("PASS: resource group '%s' listed correctly" % RG_NAME)

    def test_3_modify_rg(self):
        '''Modify affinity_priority of RG2 from 128 to 64'''
        log.info("Modifying resource group '%s': affinity_priority=64" % RG_NAME)
        self.cv_HMC.modify_resource_group(RG_NAME, affinity_priority=64)
        log.info("PASS: resource group '%s' modified successfully" % RG_NAME)

    def test_4_assign_lpar(self):
        '''Assign LPAR to RG2'''
        log.info("Assigning LPAR '%s' to resource group '%s'" % (
            self.lpar_name, RG_NAME))
        self.cv_HMC.assign_lpar_to_resource_group(RG_NAME)
        log.info("PASS: LPAR '%s' assigned to '%s'" % (self.lpar_name, RG_NAME))

    def test_5_remove_lpar(self):
        '''Remove LPAR from RG2'''
        log.info("Removing LPAR '%s' from resource group '%s'" % (
            self.lpar_name, RG_NAME))
        self.cv_HMC.remove_lpar_from_resource_group(RG_NAME)
        log.info("PASS: LPAR '%s' removed from '%s'" % (self.lpar_name, RG_NAME))

    def test_6_delete_rg(self):
        '''Delete RG2 and verify it is gone'''
        log.info("Deleting resource group '%s'" % RG_NAME)
        self.cv_HMC.delete_resource_group(RG_NAME)
        self.assertFalse(self._rg_exists(),
                         "RG '%s' still present after deletion" % RG_NAME)
        log.info("PASS: resource group '%s' deleted successfully" % RG_NAME)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _rg_exists(self):
        '''Return True if RG_NAME appears in lshwres output'''
        output = self.cv_HMC.list_resource_groups()
        return any(RG_NAME in line for line in output)

    def _cleanup_rg(self, ignore_errors=False):
        '''Best-effort delete of RG_NAME (used in setUp for idempotency)'''
        try:
            if self._rg_exists():
                log.info("Cleaning up leftover resource group '%s'" % RG_NAME)
                self.cv_HMC.delete_resource_group(RG_NAME)
        except Exception as e:
            if not ignore_errors:
                raise
            log.warning("Ignoring cleanup error: %s" % e)

    def tearDown(self):
        '''Best-effort cleanup so the managed system is left in a clean state'''
        self._cleanup_rg(ignore_errors=True)
