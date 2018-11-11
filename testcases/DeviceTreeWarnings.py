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
# DeviceTreeWarnings
# This test read the device tree from /proc/device-tree using dtc
# and fails if there are any device tree warnings or errors present.
#

'''
DeviceTreeWarnings
------------------

Check for any warnings from tools such as ``dtc`` in our device tree.
'''

import unittest
import re

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed


class DeviceTreeWarnings():
    '''
    Look at the warnings from ``dtc``, filtering out any known issues.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        filter_out = [
            # As of skiboot 6.0.1 on POWER9 we produce the following warnings:
            'dts: Warning \(reg_format\): "reg" property in '
            '(/ibm,opal/flash@0) has invalid length',

            'dts: Warning \(unit_address_vs_reg\): Node /imc-counters/nx '
            'has a reg or ranges property, but no unit name',

            "dts: Warning \((pci_device_reg|pci_device_bus_num|"
            "simple_bus_reg)\): Failed prerequisite 'reg_format'",
        ]
        log_entries = self.c.run_command(
            "dtc -I fs /proc/device-tree -O dts -o dts")
        for f in filter_out:
            fre = re.compile(f)
            log_entries = [l for l in log_entries if not fre.search(l)]

        msg = '\n'.join([_f for _f in log_entries if _f])
        self.assertTrue(len(log_entries) == 0,
                        "Warnings/Errors in Device Tree:\n{}".format(msg))


class Skiroot(DeviceTreeWarnings, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console


class Host(DeviceTreeWarnings, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.cv_HOST.host_check_command("dtc")
