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
# DeviceTreeValidation
# In this testcase we can validate different DT nodes and properties
# of different OPAL subcomponents. And also we can validate the DT
# of skiroot against host.
#

import unittest
import re
import struct

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

MAX_PSTATES = 256
CPUIDLE_STATE_MAX = 10


class DeviceTreeValidation(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def get_proc_gen(self):
        self.cpu = ''.join(self.c.run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/ .*//;'"))

        if self.cpu not in ["POWER8", "POWER8E", "POWER9"]:
            self.skipTest("Unknown CPU type %s" % cpu)

    # Checks for monotonocity/strictly increase/decrease of values
    def strictly_increasing(self, L):
        return all(x<y for x, y in zip(L, L[1:]))

    def strictly_decreasing(self, L):
        return all(x>y for x, y in zip(L, L[1:]))

    def non_increasing(self, L):
        return all(x>=y for x, y in zip(L, L[1:]))

    def non_decreasing(self, L):
        return all(x<=y for x, y in zip(L, L[1:]))

    # two's complement of integers
    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
            val = val - (1 << bits)        # compute negative value
        return val                         # return positive value as is

    #32 bit BE to LE Conversion
    def swap32(self, i):
        return struct.unpack("<I", struct.pack(">I", i))[0]

    # 64 bit BE to LE Conversion
    def swap64(self, i):
        return struct.unpack("<Q", struct.pack(">Q", i))[0]

    def dt_prop_read_str_arr(self, prop):
        res = self.c.run_command("lsprop /proc/device-tree/%s" % prop)
        if "bytes total" in "".join(res):
            res = res[1:-1]
        else:
            res = res[1:]
        list = []
        for line in res:
            line = re.sub("\(.*\)", "", line)
            list = list + line.strip("\t\r\n ").split(" ")
        return list

    def dt_prop_read_u32_arr(self, prop):
        res = self.c.run_command("hexdump -v -e \'1/4 \"%%08x\" \"\\n\"\'  /proc/device-tree/%s" % prop)
        list = []
        for line in res:
            val = ("{:08x}".format(self.swap32(int(line, 16))))
            list.append(val)
        return list

    def dt_prop_read_u64_arr(self, prop):
        res = self.c.run_command("hexdump -v -e \'2/4 \"%%08x\" \"\\n\"\'  /proc/device-tree/%s" % prop)
        list = []
        for line in res:
            val = ("{:016x}".format(self.swap64(int(line, 16))))
            list.append(val)
        return list

    def validate_idle_state_properties(self):
        idle_state_names = self.dt_prop_read_str_arr("ibm,opal/power-mgt/ibm,cpu-idle-state-names")
        idle_state_flags = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,cpu-idle-state-flags")
        idle_state_latencies_ns = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,cpu-idle-state-latencies-ns")
        idle_state_residency_ns = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,cpu-idle-state-residency-ns")
        if self.cpu in ["POWER8", "POWER8E"]:
            has_stop_inst = False
            control_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-pmicr"
            mask_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-pmicr-mask"
        elif "POWER9" in self.cpu:
            has_stop_inst = True
            control_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-psscr"
            mask_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-psscr-mask"
        idle_states_control_array = self.dt_prop_read_u64_arr(control_prop)
        idle_states_mask_array = self.dt_prop_read_u64_arr(mask_prop)

        print "\n \
               List of idle states: %s\n \
               Idle state flags: %s\n \
               Idle state latencies ns: %s\n \
               Idle state residency ns: %s\n \
               Idle state control property: %s\n \
               Idle state mask property: %s\n " % \
               (idle_state_names, idle_state_flags, idle_state_latencies_ns, \
               idle_state_residency_ns, idle_states_control_array, idle_states_mask_array)

        # Validate ibm,cpu-idle-state-flags property
        self.assertGreater(len(idle_state_flags), 0, "No idle states found in DT")
        self.assertGreater(CPUIDLE_STATE_MAX, len(idle_state_flags), "More idle states found in DT than the expected")

        # Validate names, latencies and residency properties
        self.assertEqual(len(idle_state_flags), len(idle_state_names), "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_state_latencies_ns), "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_state_residency_ns), "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_states_control_array), "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_states_mask_array), "Array size mismatch")

        # Validate residency and latency counters are in increasing order
        self.assertTrue(self.strictly_increasing(idle_state_residency_ns), "Non monotonicity observed for residency values")
        self.assertTrue(self.strictly_increasing(idle_state_latencies_ns), "Non monotonicity observed for latency values")
        self.non_decreasing(idle_state_residency_ns)
        self.non_decreasing(idle_state_latencies_ns)

    def vaildate_pstate_properties(self):
        pstate_ids = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-ids")
        pstate_min = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-min")
        pstate_max = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-max")
        pstate_nominal = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-nominal")
        pstate_turbo = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-turbo")
        pstate_frequencies = self.dt_prop_read_u32_arr("ibm,opal/power-mgt/ibm,pstate-frequencies-mhz")
        nr_pstates = abs(self.twos_comp(int(pstate_max[0], 16), 32) - self.twos_comp(int(pstate_min[0], 16), 32)) + 1

        print "\n \
                List of pstate_ids: %s\n \
                Minimum pstate: %s\n \
                Maximum pstate: %s\n \
                Nominal pstate: %s\n \
                Turbo pstate: %s\n \
                Pstate frequencies: %s\n \
                Number of pstates: %s\n" % (pstate_ids, pstate_min, pstate_max, pstate_nominal, \
                pstate_turbo, pstate_frequencies, nr_pstates)

        if (nr_pstates <= 1 or nr_pstates > 128):
            if self.cpu in ["POWER8", "POWER8E"]:
                self.assertTrue(False, "pstates range %s is not valid" % nr_pstates)
            elif "POWER9" in self.cpu:
                self.assertTrue(False, "More than 128 pstates found in pstate table" % nr_pstates)

        self.assertEqual(nr_pstates, len(pstate_ids),
                         "Wrong number of pstates, Expected %s, found %s" % (nr_pstates, len(pstate_ids)))

        if self.cpu in ["POWER8", "POWER8E"]:
            id_list = []
            for id in pstate_ids:
                id_list.append(self.twos_comp(int(id, 16), 32))
            self.assertTrue(self.strictly_decreasing(id_list), "Non monotonocity observed for pstate ids")
        elif "POWER9" in self.cpu:
            self.assertTrue(self.strictly_increasing(pstate_ids), "Non monotonocity observed for pstate ids")

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
        self.c.run_command("stty cols 300; stty rows 30;")
        self.get_proc_gen()
        self.validate_idle_state_properties()
        self.vaildate_pstate_properties()

        # Validate ibm,opal node DT content at skiroot against host
        # We can extend for other nodes as well, which are suspicieous.
        node = "/proc/device-tree/ibm,opal/"
        props = self.c.run_command("find %s -type f" % node)
        prop_val_pair_skiroot = {}
        for prop in props:
            prop_val_pair_skiroot[prop] = "".join(self.c.run_command("lsprop %s" % prop)[2:])

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()
        props = self.c.run_command("find %s -type f" % node)
        prop_val_pair_host = {}
        for prop in props:
            prop_val_pair_host[prop] = "".join(self.c.run_command("lsprop %s" % prop)[1:])

        failures = []
        for prop in prop_val_pair_skiroot:
            if prop in prop_val_pair_host:
                if prop_val_pair_skiroot[prop] in prop_val_pair_host[prop]:
                    print "Property %s has same values in both host and skiroot" % prop
                else:
                    failures.append("Value mismatch in skiroot %s and host %s for the property %s" \
                                    % (prop_val_pair_skiroot[prop], prop_val_pair_host[prop], prop))
            else:
                failures.append("Property %s is not existed in host OS" % prop)
        if failures:
            self.assertTrue(False, "DT Property values pair vaildation failed")
