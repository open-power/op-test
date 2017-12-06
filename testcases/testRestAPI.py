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
        self.rest = conf.system().rest
        self.bmc_type = conf.args.bmc_type
        if "OpenBMC" in self.bmc_type:
            self.curltool = conf.system().rest.curl

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific Rest API Tests")
        self.curltool.log_result()
        # Field mode tests
        self.rest.software_enumerate()
        self.rest.has_field_mode_set()
        self.rest.set_field_mode("1")
        self.assertTrue(self.rest.has_field_mode_set(), "Field mode enable failed")
        self.rest.set_field_mode("0")
        self.bmc.clear_field_mode()
        self.assertFalse(self.rest.has_field_mode_set(), "Field mode disable failed")
        # Upload image
        self.rest.upload_image(os.path.basename("README.md"))
        # FRU Inventory
        self.rest.get_inventory()
        # Sensors
        self.rest.sensors()
        # get BMC State
        self.rest.get_bmc_state()
        # Get Chassis Power State
        self.rest.get_power_state()
        # Get Host State
        self.rest.get_host_state()
        # List SEL records
        self.rest.list_sel()
        # get list of SEL event ID's if any exist
        self.rest.get_sel_ids()
        # Clear SEL entry by ID- Clear individual SEL Entry
        self.rest.clear_sel_by_id()
        self.rest.get_sel_ids()
        # Clear Complete SEL Repository (Not yet implemented)
        self.rest.clear_sel()
        # List available dumps
        self.rest.list_available_dumps()

        # OpenBMC Dump capture procedure
        # Initiate a dump nd get the dump id
        id = self.rest.create_new_dump()
        # Wait for the dump to finish which can be downloaded
        self.assertTrue(self.rest.wait_for_dump_finish(id), "OpenBMC Dump capture timeout")
        # Download the dump which is ready to offload
        self.rest.download_dump(id)
