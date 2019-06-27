#!/usr/bin/env python3
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

'''
OPAL sysfs Tests
----------------

This pokes a few bits of functionality accessible through sysfs that OPAL
provides.

It includes:

- System powercaps, i.e. `/sys/firmware/opal/powercap/`
- Power Shift Ratio, i.e. `/sys/firmware/opal/psr`
- Sensor Groups, i.e. `/sys/firmware/opal/sensor_groups/`
- The OPAL symbol map, i.e. `/sys/firmware/opal/symbol_map`
- Exporting of random bits of memory, i.e. `/sys/firmware/opal/exports/`
'''

import time
import random
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

POWERCAP_CURRENT = "/sys/firmware/opal/powercap/system-powercap/powercap-current"
POWERCAP_MAX = "/sys/firmware/opal/powercap/system-powercap/powercap-max"
POWERCAP_MIN = "/sys/firmware/opal/powercap/system-powercap/powercap-min"
OPAL_PSR = "/sys/firmware/opal/psr"
OPAL_SENSOR_GROUPS = "/sys/firmware/opal/sensor_groups/"
OPAL_SYMBOL_MAP = "/sys/firmware/opal/symbol_map"
OPAL_EXPORTS = "/sys/firmware/opal/exports/"


class OpalSysfsTests():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type

    def get_proc_gen(self):
        try:
            if self.cpu:
                pass
        except AttributeError:
            cmd = "grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"
            self.cpu = ''.join(self.c.run_command(cmd))
        return self.cpu

    def set_psr_value(self, entry, psr_val):
        self.c.run_command("echo %s > %s/%s" % (psr_val, str(OPAL_PSR), entry))
        for i in range(21):
            value = self.c.run_command("cat %s/%s" % (str(OPAL_PSR), entry))
            if int(value[-1]) == int(psr_val):
                break
            time.sleep(1)
        self.assertTrue((int(value[-1]) == int(psr_val)),
                        "OPAL failed to set psr value")

    def get_power_cap(self):
        return int(self.c.run_command("cat %s" % str(POWERCAP_CURRENT))[-1])

    def set_power_cap(self, value):
        valid_powercap_values = [self.get_power_cap(), value]
        self.c.run_command("echo %s > %s" % (value, str(POWERCAP_CURRENT)))
        for i in range(21):
            cur_powercap = self.get_power_cap()
            self.assertIn(cur_powercap, valid_powercap_values,
                          "Retrieved powercap was not either the previous one "
                          "({}) or the one we're trying to set ({}). Got {}, "
                          "expected in {}".format(
                              valid_powercap_values[0],
                              value,
                              cur_powercap,
                              repr(valid_powercap_values)))
            if int(cur_powercap) == int(value):
                break
            time.sleep(2)
        self.assertEqual(int(cur_powercap), int(value),
                         "OPAL failed to set power cap value. "
                         "Got {} when trying to set {}.".format(
                             cur_powercap, value))

    def test_opal_powercap(self):
        self.setup_test()
        self.get_proc_gen()
        if self.cpu not in ["POWER9"]:
            return
        cur_powercap = int(self.c.run_command("cat %s" %
                                              str(POWERCAP_CURRENT))[-1])
        max_powercap = int(self.c.run_command(
            "cat %s" % str(POWERCAP_MAX))[-1])
        min_powercap = int(self.c.run_command(
            "cat %s" % str(POWERCAP_MIN))[-1])

        log.debug("Powercap cur:{} max:{} min:{}".format(
            cur_powercap, max_powercap, min_powercap))

        self.set_power_cap(max_powercap)
        self.set_power_cap(min_powercap)
        self.set_power_cap(cur_powercap)
        self.set_power_cap(max_powercap)

        for i in range(3):
            value = random.randint(min_powercap, max_powercap)
            self.set_power_cap(value)
        # Set back to cur_powercap
        self.set_power_cap(cur_powercap)

    def test_opal_psr(self):
        self.setup_test()
        self.get_proc_gen()
        if self.cpu not in ["POWER9"]:
            return
        list = self.c.run_command("ls --color=never -1 %s" % str(OPAL_PSR))
        for entry in list:
            value = self.c.run_command("cat %s/%s" % (str(OPAL_PSR), entry))
            self.assertTrue(
                (0 <= int(value[-1]) <= 100), "Out-of-range psr value")
            self.set_psr_value(entry, 50)
            self.set_psr_value(entry, 25)
            self.set_psr_value(entry, 100)

    def test_opal_sensor_groups(self):
        self.setup_test()
        self.get_proc_gen()
        log.debug(repr(self.cpu))
        if self.cpu not in ["POWER9"]:
            return
        list = self.c.run_command(
            "ls --color=never -1 %s" % str(OPAL_SENSOR_GROUPS))
        for entry in list:
            self.c.run_command("ls --color=never /%s/%s/clear" %
                               (OPAL_SENSOR_GROUPS, entry))
            if self.test == "skiroot":
                self.c.run_command("echo 1 > /%s/%s/clear" %
                                   (OPAL_SENSOR_GROUPS, entry))
                continue
            # clearing min/max for hwmon sensors
            self.c.run_command("sensors")
            self.c.run_command("ppc64_cpu --frequency")
            self.c.run_command("sensors")
            self.c.run_command("echo 1 > /%s/%s/clear" %
                               (OPAL_SENSOR_GROUPS, entry))
            self.c.run_command("ppc64_cpu --frequency")
            self.c.run_command("sensors")
            self.c.run_command("echo 1 > /%s/%s/clear" %
                               (OPAL_SENSOR_GROUPS, entry))

    def test_opal_symbol_map(self):
        self.setup_test()
        self.c.run_command("ls --color=never -1 %s" % str(OPAL_SYMBOL_MAP))
        # It may fail due to timeout
        self.c.run_command("grep opal_ %s" % str(OPAL_SYMBOL_MAP), 120)

    def test_opal_exports(self):
        self.setup_test()
        # Not all kernel's won't create exports sysfs
        self.c.run_command_ignore_fail(
            "ls --color=never -1 %s" % str(OPAL_EXPORTS))


class Skiroot(OpalSysfsTests, unittest.TestCase):
    def setup_test(self):
        self.test = 'skiroot'
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console


class Host(OpalSysfsTests, unittest.TestCase):
    def setup_test(self):
        self.test = 'host'
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
