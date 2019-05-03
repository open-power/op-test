#!/usr/bin/env python2
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

'''
PCI Slot/Location Codes
-----------------------

This test will use the device tree to determine if the pciex is
a root/switch fabric with one or more switch devices.

Slot labels and loc codes are retrieved and if missing or empty
the test will identify for investigation.  Not all test results
reporting missing or empty slot labels or loc codes are problems,
it is the system owner to make that determination.

'''

import unittest
import re
import os

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class PciDT(unittest.TestCase):
    '''
    PciDT Class
    --run testcases.PciSlotLocCodes
    '''
    @classmethod
    def setUpClass(cls):
        cls.conf = OpTestConfiguration.conf
        if cls.conf.args.bmc_type in ['qemu', 'mambo']:
            raise unittest.SkipTest("QEMU/Mambo running so skipping tests")
        cls.cv_SYSTEM = cls.conf.system()
        try:
            if cls.desired == OpSystemState.OS:
                cls.c = cls.cv_SYSTEM.cv_HOST.get_ssh_connection()
                cls.cv_SYSTEM.goto_state(OpSystemState.OS)
            else:
                cls.c = cls.cv_SYSTEM.console
                cls.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        except Exception as e:
            log.debug("Unable to find cls.desired, probably a test code problem")
            cls.c = cls.cv_SYSTEM.console
            cls.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    def dump_lspci(self, lspci_dict):
        for key, value in lspci_dict.iteritems():
            log.debug("Dumping lspci value={} key={} ".format(value, key))

    def build_lspci(self, lspci_dict={}):
        bus_dirs = self.c.run_command("find /sys/bus/pci/devices -type l")
        # first build a dict with device info
        # of_base=0000:00:00.0
        # pciex_spec=/pciex@600c3c0000000/pci@0
        # of_key=/proc/device-tree/pciex@600c3c0000000/pci@0
        for directory in sorted(bus_dirs):
            try:
                of_base = os.path.basename(directory)
                of_node_path = directory + "/of_node"
                cmd = "ls -l %s | awk '{print $11}'" % of_node_path
                # goal is to pull off the pciex to build key for dict lookup
                # ../../../firmware/devicetree/base/pciex@600c3c0000000/pci@0
                # /proc/device-tree/pciex@600c3c0000000/pci@0
                of_output = self.c.run_command(cmd)
                pciex_spec = re.sub("^(.*base)", "", of_output[0])
                of_key = "/proc/device-tree" + pciex_spec
                lspci_dict[of_key] = of_base
            except Exception as e:
                log.debug("of_base skipping directory={} Exception={}"
                    .format(directory, e))
        return lspci_dict

    def build_lspci_names(self, lspci_dict):
        self.dump_lspci(lspci_dict) # just logging
        lspci_names = self.c.run_command("lspci -nn")
        lspci_names_dict = {}
        # 0006:00:00.0 Bridge [0680]: IBM Device [1014:04ea] (rev 01)
        for key, value in lspci_dict.iteritems():
            for i in range(len(lspci_names)):
                if value in lspci_names[i]:
                    lspci_names_dict[key] = lspci_names[i]
        return lspci_names_dict

    def build_slot_loc_tables(self):
        '''
        Builds a dictionary to track slots and loc codes and their
        values.
        '''
        node_dirs = self.c.run_command("find /proc/device-tree/ -type d "
                       "| grep -i pciex | grep -i pci@")
        output_dict = {}
        self.slot_failures = 0
        self.loccode_failures = 0
        for directory in sorted(node_dirs):
            matchObj = re.match(".*/pci@\d{1,}$", directory, re.M)
            tracking_dict = {}
            try:
                r = self.c.run_command("find {} -type d".format(directory))
                # empty=1, missing=2
                if len(r) == 1 and matchObj:
                    tracking_dict['slot-label-status'] = 0
                    tracking_dict['loc-code-status'] = 0
                    try:
                        check_list = ["npu"]
                        pciObj = re.search("/(pciex@[0-9a-fA-F]+)/", directory)
                        compat_node = "/proc/device-tree/{}/compatible".format(pciObj.group(1))
                        compat_output = self.c.run_command("cat {}".format(compat_node))
                        matching = [xs for xs in check_list if any(xs in xa for xa in compat_output)]
                        if len(matching) == 0:
                            log.debug("Non-NPU compat_output={} for {}"
                                .format(compat_output, compat_node))
                            res = self.c.run_command("cat {}/ibm,slot-label"
                                .format(directory))
                            if res[0] == "":
                                tracking_dict['slot-label-status'] = 1
                                value = ""
                                self.slot_failures += 1
                            else:
                                value = res[0].rstrip('\x00')
                            tracking_dict['slot-label'] = value
                        else:
                            log.debug("NPU compat_output={} for {}"
                                .format(compat_output, compat_node))
                    except CommandFailed as cf:
                        tracking_dict['slot-label-status'] = 2
                        tracking_dict['slot-label'] = None
                        self.slot_failures += 1
                    try:
                        res = self.c.run_command("cat {}/ibm,loc-code"
                            .format(directory))
                        if res[0] == "":
                            tracking_dict['loc-code-status'] = 1
                            value = ""
                            self.loccode_failures += 1
                        else:
                            value = res[0].rstrip('\x00')
                        tracking_dict['loc-code'] = value
                    except CommandFailed as cf:
                        tracking_dict['loc-code-status'] = 2
                        tracking_dict['loc-code'] = None
                        self.loccode_failures += 1
                    output_dict[directory] = tracking_dict
            except CommandFailed as cf:
                log.debug("Unable to query for pciex info, Exception={}"
                    .format(cf))
        return output_dict

    def doit(self):
        '''
        Performs the building of an lspci like lookup that will
        be used to output helpful information when failures occur
        as well as logging both good and not so good results
        to the debug log for analysis.
        '''
        # build a dictionary of devices, helpfulness in display
        lspci_dict = self.build_lspci()
        # map the devices to names, helpfulness in display
        lspci_mappings = self.build_lspci_names(lspci_dict)
        # build the slot and loc code tables
        output_dict = self.build_slot_loc_tables()
        # package up failures to report
        output_list = []
        count = 1
        for key in output_dict:
            if output_dict[key].get('slot-label-status') != 0 \
               and output_dict[key].get('loc-code-status') != 0:
                    output_list.append("<----------------------"
                        "Investigate #{}---------------------->"
                        .format(count))
                    count += 1
                    output_list.append("PCI Path={}".format(key))
                    output_list.append("{}".format(lspci_mappings[key]))
                    output_list.append("ibm,slot-label={}"
                        .format(output_dict[key].get('slot-label')))
                    output_list.append("ibm,loc-code={}"
                        .format(output_dict[key].get('loc-code')))
                    log.debug("Investigate - PCI Root Path={}".format(key))
                    log.debug("Investigate - {}"
                        .format(lspci_mappings[key]))
                    log.debug("Investigate - lspci={}"
                        .format(lspci_dict.get(key)))
                    log.debug("Investigate - ibm,slot-label={}"
                        .format(output_dict[key].get('slot-label')))
                    log.debug("Investigate - ibm,loc-code={}"
                        .format(output_dict[key].get('loc-code')))
            else:
                # this path just for logging
                log.debug("PCI Root Path={}".format(key))
                log.debug("{}"
                    .format(lspci_mappings[key]))
                log.debug("lspci={}"
                    .format(lspci_dict.get(key)))
                log.debug("ibm,slot-label={}"
                    .format(output_dict[key].get('slot-label')))
                log.debug("ibm,loc-code={}"
                    .format(output_dict[key].get('loc-code')))

        if len(output_list):
            failed_list = '\n'.join(filter(None, output_list))
            self.assertTrue(False, "PCI Root: Slot Label "
                "or Loc Code Failures:\nBased on Platform "
                "Slot Labels may not be present\n{}"
                .format(failed_list))

class SkirootDT(PciDT):
    '''
    SkirootDT Class performs PCI DT checks in skiroot
    --run testcases.PciSlotLocCodes.SkirootDT
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.PETITBOOT_SHELL
        super(SkirootDT, cls).setUpClass()

    def runTest(self):
        self.doit()

class HostDT(PciDT):
    '''
    HostDT Class performs PCI DT checks in the Host OS
    --run testcases.PciSlotLocCodes.HostDT
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OS
        super(HostDT, cls).setUpClass()

    def runTest(self):
        self.doit()

