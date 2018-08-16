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
#
# Test PCI Slot location codes both in OPAL message log and in Device Tree.
#
# 1. PciSlotLocCodesOPAL - This tests whether OPAL properly set both slot label and location codes.
#
# Good PCI slot table:
# ====================
# [   10.359828138,7] PCI Summary:
# [   10.359835972,5] PHB#0000:00:00.0 [ROOT] 1014 04c1 R:00 C:060400 B:01..01 SLOT=UIO Slot1
# [   10.363504748,5] PHB#0000:01:00.0 [EP  ] 15b3 1019 R:00 C:020700 (       network) LOC_CODE=UIO Slot1
# [   10.368471297,5] PHB#0000:01:00.1 [EP  ] 15b3 1019 R:00 C:020700 (       network) LOC_CODE=UIO Slot1
# [   10.372721504,5] PHB#0001:00:00.0 [ROOT] 1014 04c1 R:00 C:060400 B:01..09 SLOT=PLX
# [   10.376981242,5] PHB#0001:01:00.0 [SWUP] 10b5 8725 R:ca C:060400 B:02..09 SLOT=PLX up
# [   10.380540103,5] PHB#0001:02:01.0 [SWDN] 10b5 8725 R:ca C:060400 B:03..03 SLOT=UIO Slot2
# [   10.384791723,5] PHB#0001:03:00.0 [EP  ] 1000 00c9 R:01 C:010700 (           sas) LOC_CODE=UIO Slot2
# [   10.389761894,5] PHB#0001:02:08.0 [SWDN] 10b5 8725 R:ca C:060400 B:04..08 SLOT=PLX switch
# [   10.394022995,5] PHB#0001:02:09.0 [SWDN] 10b5 8725 R:ca C:060400 B:09..09 SLOT=Onboard LAN
# [   10.398281380,5] PHB#0001:09:00.0 [EP  ] 8086 1589 R:02 C:020000 (      ethernet) LOC_CODE=Onboard LAN
# [   10.402542938,5] PHB#0001:09:00.1 [EP  ] 8086 1589 R:02 C:020000 (      ethernet) LOC_CODE=Onboard LAN
# [   10.407510738,5] PHB#0001:09:00.2 [EP  ] 8086 1589 R:02 C:020000 (      ethernet) LOC_CODE=Onboard LAN
# [   10.412478618,5] PHB#0001:09:00.3 [EP  ] 8086 1589 R:02 C:020000 (      ethernet) LOC_CODE=Onboard LAN
# [   10.417445128,5] PHB#0001:01:00.1 [EP  ] 10b5 87d0 R:ca C:088000 (system-peripheral) LOC_CODE=PLX
# [   10.421708888,5] PHB#0001:01:00.2 [EP  ] 10b5 87d0 R:ca C:088000 (system-peripheral) LOC_CODE=PLX
# [   10.425970709,5] PHB#0001:01:00.3 [EP  ] 10b5 87d0 R:ca C:088000 (system-peripheral) LOC_CODE=PLX
# [   10.430936444,5] PHB#0001:01:00.4 [EP  ] 10b5 87d0 R:ca C:088000 (system-peripheral) LOC_CODE=PLX
#
# a. For a PCI slot there should be a slot label
# Ex: SLOT=UIO Slot1, SLOT=PLX switch, SLOT=Onboard LAN etc.
#
# b. For a PCI device there should be a location code to be set.
# Ex: LOC_CODE=UIO Slot1, LOC_CODE=Onboard LAN, LOC_CODE=PLX
#
# This test lists, list of failure slots which doesn't have slot label and also list of devices
# which doesn't have location code.
#
# Improper PCI slot table:
# ========================
# [   56.456989963,5] PHB#0000:00:00.0 [ROOT] 1014 04c1 R:00 C:060400 B:01..01 ^M
# [   57.016141753,5] PHB#0000:01:00.0 [EP  ] 15b3 1019 R:00 C:020700 (       network) ^M
# [   57.260082412,5] PHB#0000:01:00.1 [EP  ] 15b3 1019 R:00 C:020700 (       network) ^M
# [   57.479170283,5] PHB#0001:00:00.0 [ROOT] 1014 04c1 R:00 C:060400 B:01..09 ^M
# [   58.067505884,5] PHB#0001:01:00.0 [SWUP] 10b5 8725 R:ca C:060400 B:02..09 ^M
# [   58.309033124,5] PHB#0001:02:01.0 [SWDN] 10b5 8725 R:ca C:060400 B:03..03 SLOT=S000103 ^M
# [   59.016127095,5] PHB#0001:03:00.0 [EP  ] 1000 00c9 R:01 C:010700 (           sas) LOC_CODE=S000103^M
# [   59.139096517,5] PHB#0001:02:08.0 [SWDN] 10b5 8725 R:ca C:060400 B:04..08 ^M
#
# 2. PciSlotLocCodesDeviceTree
# This test looks into the device tree under pciex DT node for list of slots and pci devices(End points)
# And lists the failure of slots which doesn't have ibm,slot-label and also lists failure of
# pci devices which doesn't have the ibm,loc-code property.
#
# Example failure output:
# SLOT Label failures:/proc/device-tree/pciex@600c3c0500000/pci@0
#                     /proc/device-tree/pciex@600c3c0400000/pci@0
#                     /proc/device-tree/pciex@600c3c0400000/pci@0/pci@0
#                     /proc/device-tree/pciex@600c3c0300000/pci@0
#                     /proc/device-tree/pciex@600c3c0200000/pci@0
#                     /proc/device-tree/pciex@600c3c0100000/pci@0
#
# LOC_CODE failures:/proc/device-tree/pciex@600c3c0500000/pci@0/usb-xhci@0
#                   /proc/device-tree/pciex@600c3c0400000/pci@0/pci@0/vga@0
#                   /proc/device-tree/pciex@600c3c0300000/pci@0/sas@0
#                   /proc/device-tree/pciex@600c3c0200000/pci@0/sas@0
#                   /proc/device-tree/pciex@600c3c0100000/pci@0/system-peripheral@0,2
#                   /proc/device-tree/pciex@600c3c0100000/pci@0/system-peripheral@0,3
#                   /proc/device-tree/pciex@600c3c0100000/pci@0/system-peripheral@0,1
#                   /proc/device-tree/pciex@600c3c0100000/pci@0/system-peripheral@0,4
#                   /proc/device-tree/pciex@600c3c0000000/pci@0/network@0
#                   /proc/device-tree/pciex@600c3c0000000/pci@0/network@0,1
#

import unittest
import re

import OpTestConfiguration
from collections import OrderedDict
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class PciSlotLocCodesOPAL():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()


    def runTest(self):
        self.setup_test()
        self.log_entries = self.c.run_command_ignore_fail("cat /sys/firmware/opal/msglog |  grep 'PHB#' | grep -i  ' C:'")
        failed_eplist = []
        failed_slotlist = []
        match_list = ["[EP  ]", "[LGCY]", "[PCID]", "[ETOX]" ]

        for entry in self.log_entries:
            if entry == '':
                continue

            matchObj = re.match(r"(.*) PHB#(.*) \[(.*)", entry)
            if matchObj:
                bdfn = matchObj.group(2)
            else:
                log.debug(entry)
                bdfn = entry

            ep_present = False
            # Check for a end point PCI device, it should have LOC_CODE label
            for string in match_list:
                if string in entry:
                    ep_present = True
                    if "LOC_CODE" in entry:
                        log.debug("Location code found for entry %s" % bdfn)
                    else:
                        failed_eplist.append(bdfn)
                    break
            else:
                ep_present = False

            if ep_present:
                continue

            # If it is a pcie slot check for SLOT entry
            if "SLOT" in entry:
                log.debug("Entry %s has the slot label" % bdfn)
            else:
                failed_slotlist.append(bdfn)

        log.debug(failed_eplist, failed_slotlist)
        if (len(failed_slotlist) == 0) and (len(failed_eplist) == 0):
            return
        failed_eplist = '\n'.join(filter(None, failed_eplist))
        failed_slotlist = '\n'.join(filter(None, failed_slotlist))
        message = "SLOT Label failures: %s\n LOC_CODE failures:%s\n" % (failed_slotlist, failed_eplist)
        self.assertTrue(False, message)

class PciSlotLocCodesDeviceTree():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        node_dirs = self.c.run_command("find /proc/device-tree/ -type d | grep -i pciex | grep -i pci@")
        log.debug(node_dirs)
        slot_list = []
        device_list = []
        for directory in node_dirs:
            matchObj = re.match(".*/pci@\d{1,}$", directory, re.M)
            if matchObj:
                log.debug("entry %s is a slot" % directory)
                slot_list.append(directory)
            else:
                log.debug("entry %s is a device" % directory)
                device_list.append(directory)

        failed_slot_list = []
        empty_slot_label_list = []
        for slot in slot_list:
            try:
                res = self.c.run_command("cat %s/ibm,slot-label" % slot)
                present = True
            except CommandFailed as cf:
                present = False
                failed_slot_list.append(slot)
            # Check for empty slot label
            if present:
                if res[0] == "":
                    empty_slot_label_list.append(slot)
        log.warning(failed_slot_list)

        failed_loc_code_list = []
        empty_loc_code_list = []
        for device in device_list:
            try:
                res = self.c.run_command("cat %s/ibm,loc-code" % device)
                present = True
            except CommandFailed as cf:
                present = False
                failed_loc_code_list.append(device)
            # Check for empty location code
            if present:
                if res[0] == "":
                    empty_loc_code_list.append(device)

        log.warning(failed_loc_code_list)

        if len(empty_slot_label_list) != 0:
            empty_slot_label_list = '\n'.join(filter(None, empty_slot_label_list))
            log.error("List of slot labels with empty string : %s" % empty_slot_label_list)

        if len(empty_loc_code_list) != 0:
            empty_loc_code_list = '\n'.join(filter(None, empty_loc_code_list))
            log.error("List of devices with empty location code : %s " % empty_loc_code_list)

        if (len(failed_slot_list) == 0) and (len(failed_loc_code_list) == 0):
            return
        failed_slot_list = '\n'.join(filter(None, failed_slot_list))
        failed_loc_code_list = '\n'.join(filter(None, failed_loc_code_list))
        message = "SLOT Label failures: %s\n LOC_CODE failures:%s\n" % (failed_slot_list, failed_loc_code_list)
        self.assertTrue(False, message)

class Skiroot(PciSlotLocCodesOPAL, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console

class Host(PciSlotLocCodesOPAL, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

class SkirootDT(PciSlotLocCodesDeviceTree, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console

class HostDT(PciSlotLocCodesDeviceTree, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
