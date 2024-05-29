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
# DeviceTreeValidation
# In this testcase we can validate different DT nodes and properties
# of different OPAL subcomponents. And also we can validate the DT
# of skiroot against host.
#

'''
DeviceTreeValidation
--------------------

Check a bunch of device tree properties and structure for validity,
and compare device tree in host and skiroot environments.
'''

import unittest
import re
import struct
import difflib

import OpTestConfiguration
from common.Exceptions import CommandFailed
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
import common.OpTestQemu as OpTestQemu
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

MAX_PSTATES = 256
CPUIDLE_STATE_MAX = 10

# We use some globals to keep state between IPLs
# Which means we can save an IPL in running full test suite
prop_val_pair_skiroot = {}
prop_val_pair_host = {}


class DeviceTreeValidation(unittest.TestCase):
    DO_FULL_TEST = 0

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type
        self.node = "/proc/device-tree/ibm,opal/"

    # Checks for monotonocity/strictly increase/decrease of values
    def strictly_increasing(self, L):
        return all(x < y for x, y in zip(L, L[1:]))

    def strictly_decreasing(self, L):
        return all(x > y for x, y in zip(L, L[1:]))

    def non_increasing(self, L):
        return all(x >= y for x, y in zip(L, L[1:]))

    def non_decreasing(self, L):
        return all(x <= y for x, y in zip(L, L[1:]))

    # two's complement of integers
    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        # if sign bit is set e.g., 8bit: 128-255
        if (val & (1 << (bits - 1))) != 0:
            # compute negative value
            val = val - (1 << bits)
        # return positive value as is
        return val

    # 32 bit BE to LE Conversion
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
        res = self.c.run_command("hexdump -v -e \'1/4 \"%%08x\" \"\\n\"\'  "
                                 "/proc/device-tree/%s" % prop)
        list = []
        for line in res:
            val = ("{:08x}".format(self.swap32(int(line, 16))))
            list.append(val)
        return list

    def dt_prop_read_u64_arr(self, prop):
        res = self.c.run_command("hexdump -v -e \'2/4 \"%%08x\" \"\\n\"\'  "
                                 "/proc/device-tree/%s" % prop)
        list = []
        for line in res:
            val = ("{:016x}".format(self.swap64(int(line, 16))))
            list.append(val)
        return list

    def validate_idle_state_properties(self):
        idle_state_names = self.dt_prop_read_str_arr(
            "ibm,opal/power-mgt/ibm,cpu-idle-state-names")
        idle_state_flags = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,cpu-idle-state-flags")
        idle_state_latencies_ns = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,cpu-idle-state-latencies-ns")
        idle_state_residency_ns = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,cpu-idle-state-residency-ns")
        if self.cv_HOST.host_get_proc_gen(console=1) in ["POWER8", "POWER8E"]:
            has_stop_inst = False
            control_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-pmicr"
            mask_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-pmicr-mask"
        elif self.cv_HOST.host_get_proc_gen(console=1) in ["POWER9", "POWER9P"]:
            has_stop_inst = True
            control_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-psscr"
            mask_prop = "ibm,opal/power-mgt/ibm,cpu-idle-state-psscr-mask"
        idle_states_control_array = self.dt_prop_read_u64_arr(control_prop)
        idle_states_mask_array = self.dt_prop_read_u64_arr(mask_prop)

        log.debug("\n \
               List of idle states: %s\n \
               Idle state flags: %s\n \
               Idle state latencies ns: %s\n \
               Idle state residency ns: %s\n \
               Idle state control property: %s\n \
               Idle state mask property: %s\n " %
                  (idle_state_names, idle_state_flags, idle_state_latencies_ns,
                   idle_state_residency_ns, idle_states_control_array,
                   idle_states_mask_array))

        # Validate ibm,cpu-idle-state-flags property
        self.assertGreater(len(idle_state_flags), 0,
                           "No idle states found in DT")
        self.assertGreater(CPUIDLE_STATE_MAX, len(idle_state_flags),
                           "More idle states found in DT than the expected")

        # Validate names, latencies and residency properties
        self.assertEqual(len(idle_state_flags), len(idle_state_names),
                         "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_state_latencies_ns),
                         "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_state_residency_ns),
                         "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_states_control_array),
                         "Array size mismatch")
        self.assertEqual(len(idle_state_flags), len(idle_states_mask_array),
                         "Array size mismatch")

        # Validate residency and latency counters are in increasing order
        self.assertTrue(self.strictly_increasing(idle_state_residency_ns),
                        "Non monotonicity observed for residency values")
        self.assertTrue(self.strictly_increasing(idle_state_latencies_ns),
                        "Non monotonicity observed for latency values")
        self.non_decreasing(idle_state_residency_ns)
        self.non_decreasing(idle_state_latencies_ns)

    def validate_pstate_properties(self):
        pstate_ids = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-ids")
        pstate_min = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-min")
        pstate_max = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-max")
        pstate_nominal = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-nominal")
        pstate_turbo = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-turbo")
        pstate_frequencies = self.dt_prop_read_u32_arr(
            "ibm,opal/power-mgt/ibm,pstate-frequencies-mhz")
        nr_pstates = abs(self.twos_comp(int(pstate_max[0], 16), 32) -
                         self.twos_comp(int(pstate_min[0], 16), 32)) + 1

        log.debug("\n \
                List of pstate_ids: {}\n \
                Minimum pstate: {}\n \
                Maximum pstate: {}\n \
                Nominal pstate: {}\n \
                Turbo pstate: {}\n \
                Pstate frequencies: {}\n \
                Number of pstates: {}\n".format(pstate_ids,
                                                pstate_min,
                                                pstate_max,
                                                pstate_nominal,
                                                pstate_turbo,
                                                pstate_frequencies,
                                                nr_pstates))

        if (nr_pstates <= 1 or nr_pstates > 128):
            if self.cv_HOST.host_get_proc_gen(console=1) in ["POWER8", "POWER8E"]:
                self.assertTrue(False, "pstates range {} is not valid".format(
                    nr_pstates))
            elif self.cv_HOST.host_get_proc_gen(console=1) in ["POWER9", "POWER9P"]:
                self.assertTrue(False, "More than 128 pstates found {}"
                                "in pstate table".format(nr_pstates))

        self.assertEqual(nr_pstates, len(pstate_ids),
                         "Wrong number of pstates, "
                         "Expected %s, found %s".format())

        if self.cv_HOST.host_get_proc_gen(console=1) in ["POWER8", "POWER8E"]:
            id_list = []
            for id in pstate_ids:
                id_list.append(self.twos_comp(int(id, 16), 32))
            self.assertTrue(self.strictly_decreasing(id_list),
                            "Non monotonocity observed for pstate ids")
        elif self.cv_HOST.host_get_proc_gen(console=1) in ["POWER9", "POWER9P"]:
            self.assertTrue(self.strictly_increasing(pstate_ids),
                            "Non monotonocity observed for pstate ids")

    def validate_firmware_version(self):
        fw_node = "/proc/device-tree/ibm,firmware-versions/"
        # Validate firmware version properties
        if self.bmc_type not in ['OpenBMC', 'SMC', 'AMI']:
            self.skipTest(
                "ibm,firmware-versions DT node not available on this system")

        if self.cv_HOST.host_get_proc_gen() not in ["POWER8", "POWER8E"]:
            try:
                self.c.run_command("ls --color=never %s/version" % fw_node)
                version = self.dt_prop_read_str_arr(
                    "ibm,firmware-versions/version")
                if not version:
                    raise OpTestError("DT: Firmware version property is empty")
            except CommandFailed:
                raise OpTestError("DT: Firmware version property is missing")

        props = self.c.run_command("find %s -type f" % fw_node)
        for prop in props:
            val = self.c.run_command("lsprop %s" % prop)
            if not val:
                raise OpTestError(
                    "DT: Firmware component (%s) is empty" % prop)

    def check_dt_matches(self):
        # allows the ability to filter for debug
        # skip the parent(s) in the hierarchy
        # leave as None to get checked
        # setting to anything other than None will ignore
        ignore_dict = {"/proc/device-tree/ibm,opal/": None,
                       "/proc/device-tree/ibm,opal/sensor-groups": None,
                       "/proc/device-tree/ibm,opal/sensors": None,
                       "/proc/device-tree/ibm,opal/power-mgt": None,
                       "/proc/device-tree/ibm,opal/fw-features": None,
                       }
        if len(prop_val_pair_skiroot) and len(prop_val_pair_host):
            unified_failed_props = missing_prop_in_skiroot = \
                missing_prop_in_host = matched_prop_in_host = 0
            host_props = unified_diff_passed = \
                skipped_props = skiroot_props = 0
            unified_failures = []
            missing_in_host = []
            missing_in_skiroot = []
            matched_in_host = []
            skiroot_check = all(elem in prop_val_pair_host
                                for elem in prop_val_pair_skiroot)
            host_check = all(elem in prop_val_pair_skiroot
                             for elem in prop_val_pair_host)
            for prop in prop_val_pair_host:
                host_props += 1
                if prop not in prop_val_pair_skiroot:
                    # these failures will show up in the host_check
                    # log the specifics
                    missing_prop_in_skiroot += 1
                    missing_in_skiroot.append(["DT Node \"{}\" found in host"
                                               " but does NOT exist in skiroot".format(prop)])
                    log.debug("DT Node \"{}\" found in host"
                              " but does NOT exist in skiroot".format(prop))
            for prop in prop_val_pair_skiroot:
                skiroot_props += 1
                if prop in prop_val_pair_host:
                    check1_len = len(prop_val_pair_skiroot[prop])
                    check2_len = len(prop_val_pair_host[prop])
                    # we need the debug to figure out why things fail
                    for elem in prop_val_pair_skiroot[prop]:
                        log.debug("skiroot elem={}".format(elem))
                    for elem in prop_val_pair_host[prop]:
                        log.debug("host elem={}".format(elem))
                    check1_skiroot = all(elem in prop_val_pair_host[prop]
                                         for elem in prop_val_pair_skiroot[prop])
                    check2_skiroot = all(elem in prop_val_pair_skiroot[prop]
                                         for elem in prop_val_pair_host[prop])
                    # if cross check good and same length (just in case
                    # duplicate list items) trying to catch any mods)
                    # if order of list content differs, the unified diff
                    # always flags as difference even though
                    # the elements match (just in a different order)
                    if check1_skiroot and check2_skiroot \
                            and (check1_len == check2_len):
                        matched_prop_in_host += 1
                        matched_in_host.append(["Skiroot DT Node \"{}\" found"
                                                " in skiroot and exists in host".format(prop)])
                        log.debug("DT Node \"{}\" is the same in both"
                                  " skiroot and host".format(prop))
                        continue
                    log.debug("Skiroot DT Node \"{}\" appears "
                              "to differ from the Host, ^^^ compare the debug output ^^^"
                              .format(prop))
                    log.debug("skiroot_len={} host_len={}"
                              .format(check1_len, check2_len))
                    log.debug("skiroot_cross_check_to_host={} host_cross_check_to_skiroot={}"
                              .format(check1_skiroot, check2_skiroot))
                    if ignore_dict.get(str(prop)) != None:
                        skipped_props += 1
                        continue
                    unified_output = difflib.unified_diff(
                        [_f for _f in prop_val_pair_skiroot[prop] if _f],
                        [_f for _f in prop_val_pair_host[prop] if _f],
                        fromfile="skiroot",
                        tofile="host",
                        lineterm="")
                    unified_list = list(unified_output)
                    if len(unified_list):
                        unified_failed_props += 1
                        unified_failures.append(["<----------> Diff Failure #{}: \"{}\""
                                                 .format(unified_failed_props, prop)])
                        unified_failures.append(unified_list)
                    else:  # diff is OK, should not get here
                        # good cases should have been filtered above
                        unified_diff_passed += 1
                        log.debug("Unexpected case unified_diff passed={}"
                                  .format(prop))
                else:
                    # these failures will show up in the skiroot_check
                    # log the specifics
                    missing_prop_in_host += 1
                    missing_in_host.append(["DT Node \"{}\" does not"
                                            " exist in the host OS".format(prop)])
            if unified_failed_props \
                    or (skiroot_props != host_props) \
                    or not skiroot_check \
                    or not host_check:
                for i in unified_failures:
                    line_num = 1
                    for j in i:
                        log.debug("Failure Line #{} {}".format(line_num,
                                                               "".join(j)))
                        line_num += 1
                self.assertTrue(False, "DT Diff failures detected Total={}"
                                "\nSUMMARY:\n{}\n"
                                "Missing (found in skiroot not in host):\n{}\n"
                                "Missing (found in host not in skiroot):\n{}\n"
                                "Skipped Nodes (usually 0 or 1, the parent) = {}\n"
                                "Cross Check matched (skiroot to host) = {}\n"
                                "Skiroot Nodes = {}\n"
                                "Host Nodes = {}\n"
                                "Skiroot Nodes matched host Nodes = {}\n"
                                "Host Nodes matched skiroot Nodes = {}\n"
                                "Failures:{}\n"
                                .format(
                                    unified_failed_props,
                                    ('\n'.join(i for f in unified_failures for i in f)),
                                    (None if len(missing_in_host) == 0
                                     else ('\n'.join(i for f in missing_in_host for i in f))),
                                    (None if len(missing_in_skiroot) == 0
                                     else ('\n'.join(i for f in missing_in_skiroot for i in f))),
                                    skipped_props,
                                    matched_prop_in_host,
                                    skiroot_props,
                                    host_props,
                                    skiroot_check,
                                    host_check,
                                    unified_failed_props,
                                ))
            else:
                log.debug("DT Diff success")

    def runTest(self):
        self.skipTest("Not meant to be run directly. "
                      "Run skiroot/host variants")


class DeviceTreeValidationSkiroot(DeviceTreeValidation):
    def runTest(self):
        # goto PS before running any commands
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        if self.cv_HOST.host_get_proc_gen(console=1) not in ["POWER8", "POWER8E",
                                                             "POWER9", "POWER9P"]:
            self.skipTest("Unknown CPU type {}".format(
                self.cv_HOST.host_get_proc_gen(console=1)))

        system_state = self.cv_SYSTEM.get_state()
        self.c = self.cv_SYSTEM.console
        if isinstance(self.c, OpTestQemu.QemuConsole):
            raise self.skipTest("OpTestSystem running QEMU so comparing "
                                "Skiroot to Host is not applicable")
        self.cv_HOST.host_get_proc_gen(console=1)
        self.validate_idle_state_properties()
        self.validate_pstate_properties()
        self.validate_firmware_version()

        # Validate ibm,opal node DT content at skiroot against host
        # We can extend for other nodes as well, which are suspicieous.
        props = self.c.run_command("find %s -type d" % self.node)
        for prop in props:
            # Not all distros consistently output lsprop (-R) so make it consistent
            # Otherwise we get mismatches which get flagged as failures
            # https://github.com/ibm-power-utilities/powerpc-utils
            prop_val_pair_skiroot[prop] = self.c.run_command(
                "lsprop -R %s" % prop)

        self.check_dt_matches()


class DeviceTreeValidationHost(DeviceTreeValidation):
    def runTest(self):
        # goto OS before running any commands
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        if self.cv_HOST.host_get_proc_gen(console=1) not in ["POWER8", "POWER8E",
                                                             "POWER9", "POWER9P"]:
            self.skipTest("Unknown CPU type {}".format(
                self.cv_HOST.host_get_proc_gen(console=1)))

        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.cv_HOST.host_get_proc_gen(console=1)
        self.validate_idle_state_properties()
        self.validate_pstate_properties()
        self.validate_firmware_version()

        props = self.c.run_command("find %s -type d" % self.node)
        for prop in props:
            # Not all distros consistently output lsprop (-R) so make it consistent
            # Otherwise we get mismatches which get flagged as failures
            # https://github.com/ibm-power-utilities/powerpc-utils
            prop_val_pair_host[prop] = self.c.run_command(
                "lsprop -R %s" % prop)

        self.check_dt_matches()
