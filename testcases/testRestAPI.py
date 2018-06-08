#!/usr/bin/python2
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

import time
import subprocess
import commands
import re
import sys
import os

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed


class RestAPI(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.bmc_password = conf.args.bmc_password
        self.rest = conf.system().rest
        self.bmc_type = conf.args.bmc_type
        if "OpenBMC" in self.bmc_type:
            self.curltool = conf.system().rest.curl
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific Rest API Tests")
        self.curltool.log_result()

    def test_bmc_reset(self):
        self.rest.bmc_reset()

    def test_login(self):
        self.rest.login()
        self.rest.logout()
        self.rest.login()

    def test_system_power_cap(self):
        # System power cap enable/disable tests
        self.rest.power_cap_enable()
        PowerCapEnable, PowerCap =self.rest.get_power_cap_settings()
        self.assertEqual(int(PowerCapEnable), 1, "system power cap enable failed")
        self.rest.power_cap_disable()
        PowerCapEnable, PowerCap =self.rest.get_power_cap_settings()
        self.assertEqual(int(PowerCapEnable), 0, "system power cap disable failed")

    def test_occ_active(self):
        # OCC Active state tests using RestAPI
        ids = self.rest.get_occ_ids()
        for id in ids:
            # If system is in runtime OCC should be Active
            if self.system.get_state() in [OpSystemState.PETITBOOT, OpSystemState.PETITBOOT_SHELL,
                                           OpSystemState.BOOTING, OpSystemState.OS]:
                self.assertTrue(self.rest.is_occ_active(id), "OCC%s is not in active state" % id)
            # if system is in standby state OCC should be inactive
            elif self.system.get_state() == OpSystemState.OFF:
                self.assertFalse(self.rest.is_occ_active(id), "OCC%s is still in active state" % id)

    def test_software_enumerate(self):
        self.rest.software_enumerate()
        ids = self.rest.get_list_of_image_ids()
        for id in ids:
            cur_prty = self.rest.get_image_priority(id)
            self.rest.set_image_priority(id, cur_prty)
            next_prty = self.rest.get_image_priority(id)
            self.assertEqual(cur_prty, next_prty, "priority changed after setting")


    def test_field_mode_enable_disable(self):
        # Field mode tests
        self.rest.has_field_mode_set()
        self.rest.set_field_mode("1")
        self.assertTrue(self.rest.has_field_mode_set(), "Field mode enable failed")
        self.rest.set_field_mode("0")
        self.bmc.clear_field_mode()
        self.assertFalse(self.rest.has_field_mode_set(), "Field mode disable failed")

    def test_upload_image(self):
        # Upload image
        self.rest.upload_image(os.path.basename("README.md"))

    def test_inventory(self):
        # FRU Inventory
        self.rest.get_inventory()

    def test_sensors(self):
        # Sensors
        self.rest.sensors()

    def test_obmc_states(self):
        # get BMC State
        self.rest.get_bmc_state()
        # Get Chassis Power State
        self.rest.get_power_state()
        # Get Host State
        self.rest.get_host_state()

    def test_list_sel(self):
        # List SEL records
        self.rest.list_sel()
        # get list of SEL event ID's if any exist
        self.rest.get_sel_ids()

    def test_clear_sel(self):
        # Clear SEL entry by ID- Clear individual SEL Entry
        self.rest.clear_sel_by_id()
        self.rest.get_sel_ids()
        # Clear Complete SEL Repository
        self.rest.clear_sel()
        # Check if SEL has really zero entries or not
        self.assertTrue(self.rest.verify_clear_sel(), "openBMC failed to clear SEL repository")

    def test_obmc_dump(self):
        # List available dumps
        self.rest.list_available_dumps()
        # OpenBMC Dump capture procedure
        # Initiate a dump nd get the dump id
        id = self.rest.create_new_dump()
        # Wait for the dump to finish which can be downloaded
        self.assertTrue(self.rest.wait_for_dump_finish(id), "OpenBMC Dump capture timeout")
        # Download the dump which is ready to offload
        self.rest.download_dump(id)

    def test_set_bootdevs(self):
        # Set bootdev to setup
        self.rest.set_bootdev_to_setup()
        # Get current bootdev
        bootdev = self.rest.get_current_bootdev()
        self.assertEqual(bootdev, "Setup", "Failed to set Setup boot device")
        # Set bootdev to Default
        self.rest.set_bootdev_to_none()
        # Get current bootdev
        bootdev = self.rest.get_current_bootdev()
        self.assertEqual(bootdev, "Regular", "Failed to set Regular boot device")

    def test_get_boot_progress(self):
        # Get boot progress info
        self.rest.get_boot_progress()

    def test_clear_gard_record(self):
        self.rest.clear_gard_records()

    def test_factory_reset_software(self):
        #self.rest.factory_reset_software()
        # Not sure what is the effect of it, enable it caution
        pass

    def test_factory_reset_network(self):
        #self.rest.factory_reset_network()
        # It may clear static N/W, enable it with caution
        pass

    def test_update_root_password(self):
        self.rest.login()
        self.rest.update_root_password(str(self.bmc_password))
        self.rest.login()

    def test_tpm_policy_setting(self):
        self.rest.is_tpm_enabled()
        self.rest.enable_tpm()
        self.assertTrue(self.rest.is_tpm_enabled(), "openBMC failed to enable TPM policy")
        self.rest.disable_tpm()
        self.assertFalse(self.rest.is_tpm_enabled(), "openBMC failed to disable TPM policy")


class RestAPIStandby(RestAPI):
    @classmethod
    def setUpClass(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        super(RestAPIStandby, self).setUpClass()

    @classmethod
    def tearDownClass(self):
        OpTestConfiguration.conf.system().goto_state(OpSystemState.OFF)
        OpTestConfiguration.conf.system().goto_state(OpSystemState.OS)


class RestAPIRuntime(RestAPI):
    @classmethod
    def setUpClass(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        super(RestAPIRuntime, self).setUpClass()

    @classmethod
    def tearDownClass(self):
        OpTestConfiguration.conf.system().goto_state(OpSystemState.OFF)
        OpTestConfiguration.conf.system().goto_state(OpSystemState.OS)

def basic_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(RestAPI)

def standby_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(RestAPIStandby)

def runtime_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(RestAPIRuntime)
