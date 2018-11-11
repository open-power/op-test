#!/usr/bin/env python3
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

'''
Test OpenBMC REST API
---------------------

Tests a bunch of functionality only available through OpenBMC REST API

Generally takes about 10 minutes to run rest-api suite

.. note::

   The OpenBMC REST API is not a long term nor stable API.
   It's just as likely that OpenBMC changes their API as anything.
'''

import os

import unittest

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.Exceptions import HTTPCheck

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class RestAPI(unittest.TestCase):
    '''
    RestAPI Class - Execution order independent
    --run-suite rest-api
    --run testcases.testRestAPI.Runtime
    --run testcases.testRestAPI.HostOff
    or run the individual tests
    '''
    @classmethod
    def setUpClass(cls):
        cls.conf = OpTestConfiguration.conf
        if "OpenBMC" not in cls.conf.args.bmc_type:
            raise unittest.SkipTest("OpenBMC specific Rest API Tests")
        cls.cv_SYSTEM = cls.conf.system()
        cls.cv_BMC = cls.conf.bmc()
        cls.rest = cls.conf.system().rest
        try:
            if cls.desired == OpSystemState.OFF:
                cls.cv_SYSTEM.goto_state(OpSystemState.OFF)
            else:
                cls.cv_SYSTEM.goto_state(OpSystemState.OS)
        except Exception as e:
            log.debug("Unable to find cls.desired, probably a test code problem")
            cls.cv_SYSTEM.goto_state(OpSystemState.OS)


class Runtime(RestAPI, unittest.TestCase):
    '''
    Runtime Class performs tests with Host On
    HostOff Class will turn the Host Off
    --run testcases.testRestAPI.Runtime
    --run testcases.testRestAPI.HostOff
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OS
        super(Runtime, cls).setUpClass()

    def test_tpm_policy_setting(self):
        '''
        REST TPM Policy Settings
        --run testcases.testRestAPI.Runtime.test_tpm_policy_setting
        --run testcases.testRestAPI.HostOff.test_tpm_policy_setting
        '''
        status = self.rest.is_tpm_enabled()
        log.debug("TPM Enabled Starts={}".format(status))
        self.rest.enable_tpm()
        self.assertTrue(self.rest.is_tpm_enabled(),
                        "OpenBMC failed to enable TPM policy")
        self.rest.disable_tpm()
        self.assertFalse(self.rest.is_tpm_enabled(),
                         "OpenBMC failed to disable TPM policy")

    def test_system_power_cap(self):
        '''
        REST System Power Cap
        --run testcases.testRestAPI.Runtime.test_system_power_cap
        --run testcases.testRestAPI.HostOff.test_system_power_cap
        '''
        # System power cap enable/disable tests
        self.rest.power_cap_enable()
        PowerCapEnable, PowerCap = self.rest.get_power_cap_settings()
        log.debug("SHOULD BE ENABLED PowerCapEnable={} PowerCap={}".format(
            PowerCapEnable, PowerCap))
        self.assertEqual(int(PowerCapEnable), 1,
                         "System Power Cap Enable Failed")
        self.rest.power_cap_disable()
        PowerCapEnable, PowerCap = self.rest.get_power_cap_settings()
        log.debug("SHOULD BE DISABLED PowerCapEnable={} PowerCap={}".format(
            PowerCapEnable, PowerCap))
        self.assertEqual(int(PowerCapEnable), 0,
                         "System Power Cap Disable Failed")

    def test_occ_active(self):
        '''
        REST OCC Active
        --run testcases.testRestAPI.Runtime.test_occ_active
        --run testcases.testRestAPI.HostOff.test_occ_active
        '''
        # OCC Active state tests using RestAPI
        ids = self.rest.get_occ_ids()
        log.debug("OCC IDs: {}".format(ids))
        for id in ids:
            log.debug("OpSystemState={}".format(self.cv_SYSTEM.get_state()))
            # If system is in runtime OCC should be Active
            if self.cv_SYSTEM.get_state() in [OpSystemState.PETITBOOT, OpSystemState.PETITBOOT_SHELL,
                                              OpSystemState.BOOTING, OpSystemState.OS]:
                self.assertTrue(self.rest.is_occ_active(
                    id), "OCC%s is not in active state" % id)
            # if system is in standby state OCC should be inactive
            elif self.cv_SYSTEM.get_state() == OpSystemState.OFF:
                self.assertFalse(self.rest.is_occ_active(
                    id), "OCC%s is still in active state" % id)

    def test_software_enumerate(self):
        '''
        REST Software Enumerate
        --run testcases.testRestAPI.Runtime.test_software_enumerate
        --run testcases.testRestAPI.HostOff.test_software_enumerate
        '''
        self.rest.software_enumerate()
        ids = self.rest.get_list_of_image_ids()
        log.debug("Software Enumerate IDs: {}".format(ids))
        for id in ids:
            log.debug("Looking at Image Data Info ID={}".format(id))
            start_priority = self.rest.get_image_priority(id)
            log.debug("Image ID={} Starting Priority={}".format(
                id, start_priority))
            self.rest.set_image_priority(id, start_priority)
            updated_priority = self.rest.get_image_priority(id)
            log.debug("Image ID={} Updated Priority={}".format(
                id, updated_priority))
            self.assertEqual(start_priority, updated_priority,
                             "Image Priority Change did not happen as expected")

    def test_image_lists(self):
        '''
        REST Image Interfaces
        --run testcases.testRestAPI.Runtime.test_image_lists
        --run testcases.testRestAPI.HostOff.test_image_lists
        '''
        ids = self.rest.get_list_of_image_ids()
        log.debug("Image IDs: {}".format(ids))
        for id in ids:
            status = self.rest.is_image_already_active(id)
            log.debug("Image ID={} Active={}".format(id, status))
        host_images = self.rest.host_image_ids()
        log.debug("Host Images: {}".format(host_images))
        bmc_images = self.rest.bmc_image_ids()
        for id in bmc_images:
            status = self.rest.validate_functional_bootside(id)
            log.debug(
                "Image ID={} Functional Boot Side Validation: {}".format(id, status))
            if status:
                try:
                    activation_status = self.rest.image_ready_for_activation(
                        id, timeout=1)
                    log.debug("Activation Status: {}".format(
                        activation_status))
                except HTTPCheck as e:
                    # expected since the image is active, we just testing API
                    # xyz.openbmc_project.Software.Activation.Activations.Active
                    log.debug(
                        "HTTPCheck Exception={} e.message={}".format(e, e.message))
        log.debug("BMC Images: {}".format(bmc_images))

    def test_field_mode_enable_disable(self):
        '''
        REST Field Mode Enable and Disable
        --run testcases.testRestAPI.Runtime.test_field_mode_enable_disable
        --run testcases.testRestAPI.HostOff.test_field_mode_enable_disable
        '''
        # Field mode tests
        self.rest.has_field_mode_set()
        self.rest.set_field_mode("1")
        self.assertTrue(self.rest.has_field_mode_set(),
                        "Field Mode Enable Failed")
        self.rest.set_field_mode("0")
        # clear_field_mode will reboot the BMC
        self.cv_BMC.clear_field_mode()
        self.assertFalse(self.rest.has_field_mode_set(),
                         "Field Mode Disable Failed")

    def test_upload_image(self):
        '''
        REST Upload Image
        --run testcases.testRestAPI.Runtime.test_upload_image
        --run testcases.testRestAPI.HostOff.test_upload_image
        '''
        # Upload image
        try:
            self.rest.upload_image(os.path.basename("README.md"), minutes=None)
        except Exception as e:
            # upload_image only works for verified images
            # so this is expected to fail, but we test the API
            log.debug("Upload Image Exception={} Message={}".format(e, e.message))
            check_list = ["Version already exists",
                          "failed to be extracted",
                          "we timed out trying"]
            matching = [xs for xs in check_list if xs in e.message]
            if not len(matching):
                self.assertTrue(False, "Unexpected failure on upload_image")

    def test_inventory(self):
        '''
        REST Get Inventory
        --run testcases.testRestAPI.Runtime.test_inventory
        --run testcases.testRestAPI.HostOff.test_inventory
        '''
        # FRU Inventory
        r = self.rest.get_inventory()
        log.debug("Inventory: {}".format(r))
        # r = dictionary of dictionaries

    def test_sensors(self):
        '''
        REST Sensors
        --run testcases.testRestAPI.Runtime.test_sensors
        --run testcases.testRestAPI.HostOff.test_sensors
        '''
        # Sensors
        r = self.rest.sensors()
        log.debug("Sensors: {}".format(r))
        # r = dictionary of dictionaries

    def test_obmc_states(self):
        '''
        REST OBMC States
        --run testcases.testRestAPI.Runtime.test_obmc_states
        --run testcases.testRestAPI.HostOff.test_obmc_states
        '''
        # get BMC State
        r = self.rest.get_bmc_state()
        # r=xyz.openbmc_project.State.BMC.BMCState.Ready
        # Get Chassis Power State
        r = self.rest.get_power_state()
        # r=xyz.openbmc_project.State.Host.HostState.Running
        # Get Host State
        r = self.rest.get_host_state()
        # r=xyz.openbmc_project.State.Host.HostState.Running

    def test_list_sel(self):
        '''
        REST List SELs
        --run testcases.testRestAPI.Runtime.test_list_sel
        --run testcases.testRestAPI.HostOff.test_list_sel
        '''
        # List SEL records
        json_data = self.rest.list_sel()
        log.debug("List SEL: {}".format(json_data))
        # get list of SEL event ID's if any exist
        id_list, dict_list = self.rest.get_sel_ids()
        log.debug("SEL ID List: {} SEL DICT List: {}".format(id_list, dict_list))

    def test_dump_sels(self):
        '''
        REST Dump SELs
        --run testcases.testRestAPI.Runtime.test_dump_sels
        --run testcases.testRestAPI.HostOff.test_dump_sels
        '''
        # Dump SEL records
        # Dump list of SEL event ID's if any exist
        id_list, dict_list = self.rest.get_sel_ids(dump=True)
        log.debug("SEL ID List: {} SEL DICT List: {}".format(id_list, dict_list))

    def test_clear_sel(self):
        '''
        REST Clear SELs
        --run testcases.testRestAPI.Runtime.test_clear_sel
        --run testcases.testRestAPI.HostOff.test_clear_sel
        '''
        # Clear SEL entry by ID
        self.rest.clear_sel_by_id()
        id_list, dict_list = self.rest.get_sel_ids()
        log.debug("SEL ID List: {}\nSEL DICT List: {}\n".format(
            id_list, dict_list))
        # Clear Complete SEL Repository
        self.rest.clear_sel()
        # Check if SEL has really zero entries or not
        self.assertTrue(self.rest.verify_clear_sel(),
                        "openBMC failed to clear SEL repository")

    def test_obmc_delete_dumps(self):
        '''
        REST OBMC Delete ALL Dumps
        --run testcases.testRestAPI.Runtime.test_obmc_delete_dumps
        --run testcases.testRestAPI.HostOff.test_obmc_delete_dumps
        '''
        # Delete all the dumps
        r = self.rest.delete_all_dumps()
        log.debug("Deleted all dumps")

    def test_obmc_create_dump(self):
        '''
        REST OBMC Create Dump
        --run testcases.testRestAPI.Runtime.test_obmc_create_dump
        --run testcases.testRestAPI.HostOff.test_obmc_create_dump
        '''
        # Create a dump
        dump_id = self.rest.create_new_dump()
        log.debug("Created new dump ID={}".format(dump_id))

    def test_obmc_download_dumps(self):
        '''
        REST OBMC Download ALL Dumps
        --run testcases.testRestAPI.Runtime.test_obmc_download_dumps
        --run testcases.testRestAPI.HostOff.test_obmc_download_dumps
        '''
        # List available dumps
        dump_ids = self.rest.get_dump_ids()
        log.debug("Available Dumps to Download: {}".format(dump_ids))
        for id in dump_ids:
            dump_id = id
            log.debug("Downloading Dump ID: {}".format(dump_id))
            self.rest.download_dump(id)
        if not len(dump_ids):
            log.debug("No Available dumps to download")

    def test_obmc_dump(self):
        '''
        REST OBMC List, Create and Download a Dump
        --run testcases.testRestAPI.Runtime.test_obmc_dump
        --run testcases.testRestAPI.HostOff.test_obmc_dump
        '''
        # List available dumps
        r = self.rest.list_available_dumps()
        log.debug("Available Dumps: {}".format(r.json().get('data')))
        # OpenBMC Dump capture procedure
        # Initiate a dump nd get the dump id
        id = self.rest.create_new_dump()
        # Wait for the dump to finish which can be downloaded
        self.assertTrue(self.rest.wait_for_dump_finish(
            id, counter=30), "OpenBMC Dump capture timeout")
        # Download the dump which is ready to offload
        self.rest.download_dump(id)

    def test_set_bootdevs(self):
        '''
        REST Set Boot Device to Setup then Regular,
        this leaves the boot device as we found it
        --run testcases.testRestAPI.Runtime.test_set_bootdevs
        --run testcases.testRestAPI.HostOff.test_set_bootdevs
        '''
        # Check current bootdev
        start_bootdev = self.rest.get_current_bootdev()
        log.debug("Boot Device Starts={}".format(start_bootdev))
        # Set bootdev to setup
        self.rest.set_bootdev_to_setup()
        # Get current bootdev
        bootdev = self.rest.get_current_bootdev()
        self.assertEqual(bootdev, "Setup", "Failed to set Setup boot device")
        # Set bootdev to Default
        self.rest.set_bootdev_to_none()
        # Get current bootdev
        bootdev = self.rest.get_current_bootdev()
        self.assertEqual(bootdev, "Regular",
                         "Failed to set Regular boot device")
        # Put the bootdev back how we found it
        if bootdev != start_bootdev:
            if start_bootdev == "Setup":
                self.rest.set_bootdev_to_setup()
            else:
                self.rest.set_bootdev_to_none()
        # Check bootdev
        bootdev = self.rest.get_current_bootdev()
        log.debug("Boot Device Ends={}".format(bootdev))

    def test_get_boot_progress(self):
        '''
        REST Get Boot Progress
        --run testcases.testRestAPI.Runtime.test_get_boot_progress
        --run testcases.testRestAPI.HostOff.test_get_boot_progress
        '''
        # Get boot progress info
        r = self.rest.get_boot_progress()
        log.debug("Boot Progress={}".format(r))

    def test_clear_gard_record(self):
        '''
        REST Clear ALL Gard Records
        --run testcases.testRestAPI.Runtime.test_clear_gard_record
        --run testcases.testRestAPI.HostOff.test_clear_gard_record
        '''
        self.rest.clear_gard_records()

    def test_factory_reset_software(self):
        '''
        REST Factory Reset Software
        USE AT YOUR OWN RISK
        --run testcases.testRestAPI.Runtime.test_factory_reset_software
        --run testcases.testRestAPI.HostOff.test_factory_reset_software
        '''
        # self.rest.factory_reset_software()
        # Not sure what the effect is, enable with caution
        pass

    def test_factory_reset_network(self):
        '''
        REST Factory Reset Network
        USE AT YOUR OWN RISK
        --run testcases.testRestAPI.Runtime.test_factory_reset_network
        --run testcases.testRestAPI.HostOff.test_factory_reset_network
        '''
        # self.rest.factory_reset_network()
        # It may clear static N/W, enable with caution
        pass

    def test_update_root_password(self):
        '''
        REST Update Root Password
        Caution if OpTestConfiguration bmc_password is modified
        util_bmc_server does automatic login with stored credentials
        --run testcases.testRestAPI.Runtime.test_update_root_password
        --run testcases.testRestAPI.HostOff.test_update_root_password
        '''
        self.rest.update_root_password(str(self.conf.args.bmc_password))


class HostOff(Runtime):
    '''
    Runtime Class performs tests with Host On
    HostOff Class will turn the Host Off
    --run testcases.testRestAPI.Runtime
    --run testcases.testRestAPI.HostOff
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OFF
        super(Runtime, cls).setUpClass()


class HostBounces(RestAPI, unittest.TestCase):
    '''
    Performs Reboots and Power On/Off variety
    Purpose is to exercise the REST API's
    --run testcases.testRestAPI.HostBounces
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OFF
        super(HostBounces, cls).setUpClass()

    def test_power_on(self):
        '''
        REST Power On
        --run testcases.testRestAPI.HostBounces.test_power_on
        '''
        self.rest.power_on()
        self.rest.wait_for_runtime()

    def test_soft_reboot(self):
        '''
        REST Soft Reboot
        --run testcases.testRestAPI.HostBounces.test_soft_reboot
        '''
        self.rest.power_on()
        self.rest.wait_for_runtime()
        self.rest.soft_reboot()
        self.rest.wait_for_standby()
        self.rest.wait_for_runtime()

    def test_hard_reboot(self):
        '''
        REST Hard Reboot
        --run testcases.testRestAPI.HostBounces.test_hard_reboot
        '''
        self.rest.power_on()
        self.rest.wait_for_runtime()
        self.rest.hard_reboot()
        self.rest.wait_for_standby()
        self.rest.wait_for_runtime()

    def test_power_soft(self):
        '''
        REST Power Soft Off
        --run testcases.testRestAPI.HostBounces.test_power_soft
        '''
        self.rest.power_on()
        self.rest.wait_for_runtime()
        self.rest.power_soft()
        self.rest.wait_for_standby()

    def test_power_off(self):
        '''
        REST Power Off
        --run testcases.testRestAPI.HostBounces.test_power_off
        '''
        self.rest.power_on()
        self.rest.wait_for_runtime()
        self.rest.power_off()
        self.rest.wait_for_standby()


def host_off_suite():
    # run with Host powered OFF
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(HostOff))
    return s


def runtime_suite():
    # run with Host powered ON
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(Runtime))
    return s
