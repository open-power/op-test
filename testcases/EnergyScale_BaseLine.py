#!/usr/bin/python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

# This test is somewhat re-implementing the EnergyScale_BaseLine plugin for DVT
# except it's not perfect, and don't bet that it is the same as it's only
# based on a log of a test run rather than the source code for that test.

import time
import subprocess
import re
import sys
import os
import random

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class EnergyScale_BaseLine(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.host = conf.host()
        self.bmc = conf.bmc()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.system.goto_state(OpSystemState.OS)

    def get_occ_reset_count(self):
        c = self.host.get_ssh_connection()
        r = c.run_command("/tmp/occtoolp9 -I")
        r = [l for l in r if "resetCount" in l]
        reset_count = [l.split("resetCount:")[1].split(' ')[0] for l in r]
        reset_count = [int(l) for l in reset_count]
        print repr(reset_count)
        # Reset count is [HTMGT, OCC0, OCC1] counts
        # We want to only care about occ0 as it seems that's what happens
        count = reset_count[1] # occ0 reset count
        return count

    def runTest(self):
        self.host.copy_test_file_to_host("occtoolp9")
        c = self.host.get_ssh_connection()
        print "# Clear OCC RESET Counter"
        c.run_command("opal-prd --expert-mode htmgt-passthru 4")
        self.assertEqual(self.get_occ_reset_count(), 0, "OCC Reset Count != 0")
        print "# Validate IPLed to OCC ACTIVE"
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Disabled/Observation"
        c.run_command("opal-prd --expert-mode htmgt-passthru 9 2")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Enabled/Active"
        c.run_command("opal-prd --expert-mode htmgt-passthru 9 3")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Characterization"
        c.run_command("opal-prd --expert-mode htmgt-passthru 9 5")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Enabled/Active"
        c.run_command("opal-prd --expert-mode htmgt-passthru 9 3")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Reset Counter=0"
        self.assertEqual(self.get_occ_reset_count(), 0, "OCC Reset Count != 0")
        print "# Validate OCC Reset"
        c.run_command("opal-prd occ reset")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Reset Counter=1"
        self.assertEqual(self.get_occ_reset_count(), 1, "OCC Reset Count != 1")
        print "# Clear OCC RESET Counter"
        c.run_command("opal-prd --expert-mode htmgt-passthru 4")
        c.run_command("/tmp/occtoolp9 -p")
        print "# Validate OCC Reset Counter=0"
        self.assertEqual(self.get_occ_reset_count(), 0, "OCC Reset Count != 0")
        print "# Process any errors OCC is Reporting"
        c.run_command("opal-prd occ process-error")
