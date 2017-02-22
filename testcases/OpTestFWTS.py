#!/usr/bin/python
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

# This test runs FWTS and munges the JSON report output into
# python unittest.TestCase objects, so we get the individual
# failure/successes into the TestResult output (e.g. junit XML)

import time
import subprocess
import re
import sys
import os

import OpTestConfiguration
import unittest
from common.OpTestSystem import OpSystemState

import json

class FWTSVersion(unittest.TestCase):
    MAJOR = 0
    MINOR = 0
    def version_check(self):
        return (self.MAJOR == 17 and self.MINOR >=1) or self.MAJOR > 17
    def runTest(self):
        self.assertTrue(self.version_check(),
                        'FWTS must be at least Version 17.01'
        )

class FWTSTest(unittest.TestCase):
    SUBTEST_RESULT = []
    def runTest(self):
        if self.SUBTEST_RESULT.get('log_text') == 'dtc reports warnings from device tree:Warning (reg_format): "reg" property in /ibm,opal/flash@0 has invalid length (8 bytes) (#address-cells == 0, #size-cells == 0)\n':
            self.skipTest('/ibm,opal/flash@0 known warning')

        # Some FWTS verions barfed (incorrectly) on missing nodes
        # in the device tree. If we spot this, skip the test
        # this work-around should be removed when the FWTS version readily
        # available from the archives no longer has this problem
        if not (self.SUBTEST_RESULT.get('failure_label') == 'None'):
            if re.match('Property of "(status|manufacturer-id|part-number|serial-number)" for "/sys/firmware/devicetree/base/memory-buffer' , self.SUBTEST_RESULT.get('log_text')):
                self.skipTest("FWTS bug: Incorrect Missing '(status|manufacturer-id|part-number|serial-number)' property in memory-buffer/dimm");

        self.assertEqual(self.SUBTEST_RESULT.get('failure_label'), 'None', self.SUBTEST_RESULT)

class OpTestFWTS(unittest.TestSuite):
    def add_fwts_results(self):
        host = self.host
        fwtsjson = host.host_run_command('fwts -q -r stdout --log-type=json')
        r = json.loads(fwtsjson[2:], encoding='latin-1')
        tests = []
        for fwts in r['fwts']:
            for k in fwts:
                if k == "tests":
                    tests = fwts[k]

        for test_container in tests:
            for tr in test_container:
                js_suite = test_container[tr][0]
                js_subtests = test_container[tr][1]
                suite = unittest.TestSuite()

                for sts in js_subtests:
                    if sts == "subtests":
                        for subtest in js_subtests[sts]:
                            for st_info in subtest['subtest']:
                                if not st_info.get('subtest_results'):
                                    continue
                                for st_result in st_info.get('subtest_results'):
                                    t = FWTSTest()
                                    t.SUBTEST_RESULT = st_result
                                    suite.addTest(t)
                self.real_fwts_suite.addTest(suite)

    def run(self, result):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.system = conf.system()

        self.system.goto_state(OpSystemState.OS)

        self.real_fwts_suite = unittest.TestSuite()

        host = self.host
        fwts_version = host.host_run_command('fwts --version')
        # We want to ensure we're at least at version 17.01
        # which means we need to parse this:
        # fwts, Version V17.01.00, 2017-01-19 04:20:38
        v = re.search("fwts, Version V(\d+)\.(\d+)", fwts_version)
        major , minor = v.group(1) , v.group(2)

        checkver = FWTSVersion()
        checkver.MAJOR = major
        checkver.MINOR = minor
        self.real_fwts_suite.addTest(checkver)

        if checkver.version_check():
            self.add_fwts_results()

        self.real_fwts_suite.run(result)
