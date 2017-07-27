#!/usr/bin/python
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
        self.rest = conf.system().rest
        self.bmc_type = conf.args.bmc_type
        self.curltool = conf.system().rest.curl

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific Rest API Tests")
        self.curltool.log_result()
        # FRU Inventory
        self.rest.get_inventory()
        # Sensors
        self.rest.sensors()
        # get BMC State
        self.rest.get_bmc_state()
        # Get Chassis Power State
        self.rest.get_power_state()
        # List SEL records
        self.rest.list_sel()
        # get list of SEL event ID's if any exist
        self.rest.get_sel_ids()
        # Clear SEL entry by ID- Clear individual SEL Entry
        self.rest.clear_sel_by_id()
        self.rest.get_sel_ids()
        # Clear Complete SEL Repository (Not yet implemented)
        self.rest.clear_sel()
