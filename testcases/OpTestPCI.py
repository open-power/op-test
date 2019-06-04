#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPCI.py $
#
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
#
# IBM_PROLOG_END_TAG

'''
OpTestPCI: PCI checks
-------------------------------

Perform various PCI validations and checks

--run-suite BasicPCI (includes skiroot_suite and host_suite)
--run-suite pci-regression

Sample naming conventions below, see each test method for
the applicable options per method.

--run testcases.OpTestPCI.PCISkiroot.pcie_link_errors
      ^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^ ^^^^^^^^^^^^^^^^
          module name      subclass    test method

--run testcases.OpTestPCI.PCIHost.pcie_link_errors
      ^^^^^^^^^^^^^^^^^^^ ^^^^^^^ ^^^^^^^^^^^^^^^^
          module name     subclass   test method

'''

import unittest
import logging
import pexpect
import time
import re
import difflib
from distutils.version import LooseVersion

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed, UnexpectedCase

log = OpTestLogger.optest_logger_glob.get_logger(__name__)
skiroot_done = 0
host_done = 0
skiroot_lspci = None
host_lspci = None
reset_console = 0


class OpClassPCI(unittest.TestCase):
    '''
    Main Parent class

    We cannot guarantee a soft boot entry, so need to force to PS or OS
    '''

    @classmethod
    def setUpClass(cls, desired=None, power_cycle=0):
        '''
        Main setUpClass, this is shared across all subclasses.
        This is called once when the subclass is instantiated.
        '''
        if desired is None:
            cls.desired = OpSystemState.PETITBOOT_SHELL
        else:
            cls.desired = desired
        cls.power_cycle = power_cycle
        cls.conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = cls.conf.system()
        cls.cv_HOST = cls.conf.host()
        cls.my_connect = None
        if cls.power_cycle == 1:
            cls.cv_SYSTEM.goto_state(OpSystemState.OFF)
            cls.power_cycle = 0
        try:
            if cls.desired == OpSystemState.OS:
                # set bootdev for reboot cases
                cls.cv_SYSTEM.sys_set_bootdev_no_override()
                cls.cv_SYSTEM.goto_state(OpSystemState.OS)
                cls.c = cls.cv_SYSTEM.host().get_ssh_connection()
            else:
                cls.cv_SYSTEM.sys_set_bootdev_setup()
                cls.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
                cls.c = cls.cv_SYSTEM.console
            cls.pty = cls.cv_SYSTEM.console.get_console()
        except Exception as e:
            log.debug("Unable to find cls.desired, probably a test code problem")
            cls.cv_SYSTEM.goto_state(OpSystemState.OS)

    @classmethod
    def tearDownClass(cls):
        '''
        Main tearDownClass, this is shared across all subclasses.
        This is called once when the subclass is taken down.
        '''
        global skiroot_done
        global host_done
        global skiroot_lspci
        global host_lspci
        global reset_console
        if reset_console == 1:
            cls.refresh_console()

    @classmethod
    def set_console(cls):
        '''
        This method allows setting the shared class console to the real
        console when needed, i.e. driver_bind tests which unbind the
        ethernet drivers.
        '''
        cls.c = cls.cv_SYSTEM.console

    @classmethod
    def refresh_console(cls):
        '''
        This method is used to set the shared class console back to the proper
        object (this gets set to the real console when we unbind the ethernet)
        in the driver_bind test as an example.
        '''
        # this done after a reboot
        global reset_console
        if cls.cv_SYSTEM.get_state() == OpSystemState.PETITBOOT_SHELL:
            cls.c = cls.cv_SYSTEM.console
        else:
            cls.c = cls.cv_SYSTEM.host().get_ssh_connection()
        reset_console = 0

    def setUp(self):
        '''
        All variables common to a subclass need to be defined here since
        this method gets called before each subclass test
        '''
        pass

    def tearDown(self):
        '''
        This is done at the end of each subclass test.
        '''
        global reset_console
        if reset_console == 1:
            self.refresh_console()

    def get_lspci(self):
        '''
        Usually used internally, can be run for query of system

        Case A --run testcases.OpTestPCI.PCISkiroot.get_lspci
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.get_lspci
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.get_lspci
        Case D --run testcases.OpTestPCI.PCIHost.get_lspci
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.get_lspci
        Case F --run testcases.OpTestPCI.PCIHostHardboot.get_lspci
        '''
        lspci_data = self.c.run_command("lspci -mm -n")
        return lspci_data

    def check_commands(self):
        '''
        Checks for general capability to run commands

        Case A --run testcases.OpTestPCI.PCISkiroot.check_commands
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.check_commands
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.check_commands
        Case D --run testcases.OpTestPCI.PCIHost.check_commands
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.check_commands
        Case F --run testcases.OpTestPCI.PCIHostHardboot.check_commands

        '''
        list_pci_devices_commands = ["lspci -mm -n",
                                     "lspci -m",
                                     "lspci -t",
                                     "lspci -n",
                                     "lspci -nn",
                                     "cat /proc/bus/pci/devices",
                                     "ls --color=never /sys/bus/pci/devices/ -l",
                                     "lspci -vvxxx",
                                     ]
        for cmd in list_pci_devices_commands:
            self.c.run_command(cmd, timeout=300)

        list_usb_devices_commands = ["lsusb",
                                     "lsusb -t",
                                     "lsusb -v",
                                     ]
        for cmd in list_usb_devices_commands:
            self.c.run_command(cmd)

        # Test that we do not EEH on reading all config space
        self.c.run_command(
            "hexdump -C /sys/bus/pci/devices/*/config", timeout=600)

    def get_lspci_file(self):
        '''
        Usually used internally, can be run for query of system

        Case A --run testcases.OpTestPCI.PCISkiroot.get_lspci_file
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.get_lspci_file
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.get_lspci_file
        Case D --run testcases.OpTestPCI.PCIHost.get_lspci_file
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.get_lspci_file
        Case F --run testcases.OpTestPCI.PCIHostHardboot.get_lspci_file
        '''
        if self.conf.lspci_file():
            with open(self.conf.lspci_file(), 'r') as f:
                file_content = f.read().splitlines()
            log.debug("file_content={}".format(file_content))
            return file_content

    def _diff_my_devices(self,
                         listA=None,
                         listA_name=None,
                         listB=None,
                         listB_name=None):
        '''
        Performs unified diff of two lists
        '''
        unified_output = difflib.unified_diff(
            filter(None, listA),
            filter(None, listB),
            fromfile=listA_name,
            tofile=listB_name,
            lineterm="")
        unified_list = list(unified_output)
        log.debug("unified_list={}".format(unified_list))
        return unified_list

    def compare_boot_devices(self):
        '''
        This is best leveraged in the suite pci-regression,
        where both the skiroot/host softboot and the
        skiroot/host hardboot get done in the same wave,
        so that the global variables carry over to compare.

        If both skiroot and host lspci completed, will
        compare lspci results.

        If you want to compare against an input file, use
        compare_live_devices.

        Case A --run testcases.OpTestPCI.PCISkiroot.compare_boot_devices
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.compare_boot_devices
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.compare_boot_devices
        Case D --run testcases.OpTestPCI.PCIHost.compare_boot_devices
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.compare_boot_devices
        Case F --run testcases.OpTestPCI.PCIHostHardboot.compare_boot_devices
        '''
        global skiroot_done
        global host_done
        global skiroot_lspci
        global host_lspci
        lspci_output = self.get_lspci()
        if self.cv_SYSTEM.get_state() == OpSystemState.PETITBOOT_SHELL:
            skiroot_lspci = lspci_output
            skiroot_done = 1
        else:
            host_lspci = lspci_output
            host_done = 1
        if host_done and skiroot_done:
            compare_results = self._diff_my_devices(listA=skiroot_lspci,
                                                    listA_name="skiroot_lspci",
                                                    listB=host_lspci,
                                                    listB_name="host_lspci")
            if len(compare_results):
                self.assertEqual(len(compare_results), 0,
                                 "skiroot_lspci and host_lspci devices differ:\n{}"
                                 .format(self.conf.lspci_file(), ('\n'.join(i for i in compare_results))))
            # refresh so next pair can be matched up, i.e. soft or hard
            skiroot_done = 0
            host_done = 0
            skiroot_lspci = None
            host_lspci = None

    def compare_live_devices(self):
        '''
        Compares the live system lspci against an input file, host-lspci
        provided either in conf file or via command line.

        "ssh user@host lspci -mm -n > host-lspci.txt"

        --host-lspci host-lspci.txt on command line
                         or
        host_lspci=host-lspci.txt in conf file

        Case A --run testcases.OpTestPCI.PCISkiroot.compare_live_devices
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.compare_live_devices
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.compare_live_devices
        Case D --run testcases.OpTestPCI.PCIHost.compare_live_devices
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.compare_live_devices
        Case F --run testcases.OpTestPCI.PCIHostHardboot.compare_live_devices
        '''
        active_lspci = self.get_lspci()
        file_lspci = self.get_lspci_file()
        if file_lspci:
            compare_results = self._diff_my_devices(listA=file_lspci,
                                                    listA_name=self.conf.lspci_file(),
                                                    listB=active_lspci,
                                                    listB_name="Live System")
            log.debug("compare_results={}".format(compare_results))
            if len(compare_results):
                self.assertEqual(len(compare_results), 0,
                                 "Stored ({}) and Active PCI devices differ:\n{}"
                                 .format(self.conf.lspci_file(), ('\n'.join(i for i in compare_results))))

    def pcie_link_errors(self):
        '''
        Checks for link errors

        Case A --run testcases.OpTestPCI.PCISkiroot.pcie_link_errors
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.pcie_link_errors
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.pcie_link_errors
        Case D --run testcases.OpTestPCI.PCIHost.pcie_link_errors
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.pcie_link_errors
        Case F --run testcases.OpTestPCI.PCIHostHardboot.pcie_link_errors

        '''
        total_entries = link_down_entries = timeout_entries = []
        try:
            link_down_entries = self.c.run_command(
                "grep ',[432]\].*PHB#.* Link down' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if link_down_entries:
            log.debug("link_down_entries={}".format(link_down_entries))
            total_entries = total_entries + link_down_entries
            log.debug(
                "total_entries with link_down_entries={}".format(total_entries))
        try:
            timeout_entries = self.c.run_command(
                "grep ',[432]\].*Timeout waiting for' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if timeout_entries:
            log.debug("timeout_entries={}".format(timeout_entries))
            total_entries = total_entries + timeout_entries
            log.debug(
                "total_entries with timeout_entries={}".format(total_entries))
        platform = self.c.run_command("cat /proc/device-tree/compatible")

        filter_out = [
            'PHB#00(00|30|33|34)\[(0|8):(0|4|3)\]: LINK: Timeout waiting for link up',
            'Timeout waiting for downstream link',
        ]

        log.debug("STARTING total_entries={}".format(total_entries))
        if re.search(r'p9dsu', platform[0]):
            # No presence detect on some p9dsu slots :/
            for f in filter_out:
                fre = re.compile(f)
                total_entries = [l for l in total_entries if not fre.search(l)]
            log.debug("P9DSU FILTERED OUT total_entries={}".format(total_entries))

        msg = '\n'.join(filter(None, total_entries))
        log.debug("total_entries={}".format(total_entries))
        self.assertTrue(len(total_entries) == 0,
                        "pcie link down/timeout Errors in OPAL log:\n{}".format(msg))

    def _get_list_of_pci_devices(self):
        cmd = "ls --color=never /sys/bus/pci/devices/ | awk {'print $1'}"
        res = self.c.run_command(cmd)
        return res

    def _get_driver(self, pe):
        cmd = "lspci -ks {}".format(pe)
        output = self.c.run_command(cmd, timeout=120)
        if output:
            for line in output:
                if 'Kernel driver in use:' in line:
                    return (line.rsplit(":")[1]).strip(" ")
        return None

    def _get_list_of_slots(self):
        cmd = "ls --color=never /sys/bus/pci/slots/ -1"
        res = self.c.run_command(cmd)
        return res

    def _get_root_pe_address(self):
        cmd = "df -h /boot | awk 'END {print $1}'"
        res = self.c.run_command(cmd)
        boot_disk = ''.join(res).split("/dev/")[1]
        boot_disk = boot_disk.replace("\r\n", "")
        awk_string = "awk '{print $(NF-2)}'"
        pre_cmd = "ls --color=never -l /dev/disk/by-path/ | grep {} | ".format(
            boot_disk)
        cmd = pre_cmd + awk_string
        res = self.c.run_command(cmd)
        root_pe = res[0].split("-")[1]
        return root_pe

    def _gather_errors(self):
        # Gather all errors from kernel and opal logs
        try:
            self.c.run_command("dmesg -r|grep '<[4321]>'")
        except CommandFailed:
            pass
        try:
            self.c.run_command("grep ',[0-4]\]' /sys/firmware/opal/msglog")
        except CommandFailed:
            pass

    def driver_bind(self):
        '''
        Unbind and then bind the devices

        Case A --run testcases.OpTestPCI.PCISkiroot.driver_bind
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.driver_bind
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.driver_bind
        Case D --run testcases.OpTestPCI.PCIHost.driver_bind
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.driver_bind
        Case F --run testcases.OpTestPCI.PCIHostHardboot.driver_bind

        Special note on unbinding shared bmc ethernet ports, caution.
        '''
        # since we will be unbinding ethernet drivers, override the console
        global reset_console
        reset_console = 1
        self.set_console()
        if self.cv_SYSTEM.get_state() == OpSystemState.PETITBOOT_SHELL:
            root_pe = "xxxx"
        else:
            root_pe = self._get_root_pe_address()
            self.c.run_command("dmesg -D")
        list = self._get_list_of_pci_devices()
        failure_list = {}
        for slot in list:
            rc = 0
            driver = self._get_driver(slot)
            if root_pe in slot:
                continue
            if driver is None:
                continue
            index = "{}_{}".format(driver, slot)
            cmd = "echo -n {} > /sys/bus/pci/drivers/{}/unbind".format(
                slot, driver)
            log.debug("unbind driver={} slot={} cmd={}".format(
                driver, slot, cmd))
            try:
                self.c.run_command(cmd)
            except CommandFailed as cf:
                msg = "Driver unbind operation failed for driver {}, slot {}".format(
                    slot, driver)
                failure_list[index] = msg
            time.sleep(5)
            cmd = 'ls --color=never /sys/bus/pci/drivers/{}'.format(driver)
            self.c.run_command(cmd)
            path = "/sys/bus/pci/drivers/{}/{}".format(driver, slot)
            try:
                self.c.run_command("test -d {}".format(path))
                rc = 1
            except CommandFailed as cf:
                pass
            cmd = "echo -n {} > /sys/bus/pci/drivers/{}/bind".format(
                slot, driver)
            log.debug("bind driver={} slot={} cmd={}".format(driver, slot, cmd))
            try:
                self.c.run_command(cmd)
            except CommandFailed as cf:
                msg = "Driver bind operation failed for driver {}, slot {}".format(
                    slot, driver)
                failure_list[index] = msg
            time.sleep(5)
            cmd = 'ls --color=never /sys/bus/pci/drivers/{}'.format(driver)
            self.c.run_command(cmd)
            try:
                self.c.run_command("test -d {}".format(path))
            except CommandFailed as cf:
                rc = 2

            self._gather_errors()

            if rc == 1:
                msg = "{} not unbound for driver {}".format(slot, driver)
                failure_list[index] = msg

            if rc == 2:
                msg = "{} not bound back for driver {}".format(slot, driver)
                failure_list[index] = msg
        self.assertEqual(failure_list, {},
                         "Driver bind/unbind failures {}".format(failure_list))

    def hot_plug_host(self):
        '''
        NEEDS TESTING
        Case A --run testcases.OpTestPCI.PCIHost.hot_plug_host
        Case B --run testcases.OpTestPCI.PCIHostSoftboot.hot_plug_host
        Case C --run testcases.OpTestPCI.PCIHostHardboot.hot_plug_host
        '''
        # Currently this feature enabled only for fsp systems
        if "FSP" not in self.conf.args.bmc_type:
            log.debug(
                "Skipping test, currently only OPAL FSP Platform supported for hot_plug_host")
            self.skipTest(
                "Skipping test, currently only OPAL FSP Platform supported for hot_plug_host")
        res = self.c.run_command("uname -r")[-1].split("-")[0]
        if LooseVersion(res) < LooseVersion("4.10.0"):
            log.debug(
                "Skipping test, Kernel does not support hotplug {}".format(res))
            self.skipTest(
                "Skipping test, Kernel does not support hotplug={}".format(res))
        self.cv_HOST.host_load_module("pnv_php")
        device_list = self._get_list_of_pci_devices()
        root_pe = self._get_root_pe_address()
        slot_list = self._get_list_of_slots()
        self.c.run_command("dmesg -D")
        pair = {}  # Pair of device vs slot location code
        for device in device_list:
            cmd = "lspci -k -s {} -vmm".format(device)
            res = self.c.run_command(cmd)
            for line in res:
                # if "PhySlot:\t" in line:
                obj = re.match('PhySlot:\t(.*)', line)
                if obj:
                    pair[device] = obj.group(1)
        failure_list = {}
        for device, phy_slot in pair.iteritems():
            if root_pe in device:
                continue
            index = "{}_{}".format(device, phy_slot)
            path = "/sys/bus/pci/slots/{}/power".format(phy_slot)
            try:
                self.c.run_command("test -f {}".format(path))
            except CommandFailed as cf:
                log.debug("Slot {} does not support hotplug".format(phy_slot))
                continue  # slot does not support hotplug
            try:
                self.c.run_command("echo 0 > {}".format(path))
            except CommandFailed as cf:
                msg = "PCI device/slot power off operation failed"
                failure_list[index] = msg
            time.sleep(5)
            cmd = "lspci -k -s {}".format(device)
            res = self.c.run_command(cmd)
            if device in "\n".join(res):
                msg = "PCI device failed to remove after power off operation"
                failure_list[index] = msg
            try:
                self.c.run_command("echo 1 > {}".format(path))
            except CommandFailed as cf:
                msg = "PCI device/slot power on operation failed"
                failure_list[index] = msg
            res = self.c.run_command(cmd)
            if device not in "\n".join(res):
                msg = "PCI device failed to attach back after power on operation"
                failure_list[index] = msg
            self._gather_errors()
        self.assertEqual(failure_list, {},
                         "PCI Hotplug failures {}".format(failure_list))

    def pci_link_check(self):
        '''
        PCI link checks

        Case A --run testcases.OpTestPCI.PCISkiroot.pci_link_check
        Case B --run testcases.OpTestPCI.PCISkirootSoftboot.pci_link_check
        Case C --run testcases.OpTestPCI.PCISkirootHardboot.pci_link_check
        Case D --run testcases.OpTestPCI.PCIHost.pci_link_check
        Case E --run testcases.OpTestPCI.PCIHostSoftboot.pci_link_check
        Case F --run testcases.OpTestPCI.PCIHostHardboot.pci_link_check
        '''
        lspci_output = self.c.run_command("lspci")

        # List of devices that won't be checked
        blacklist = [
            "Broadcom Limited NetXtreme BCM5719 Gigabit Ethernet PCIe (rev 01)"]

        # Populating device id list
        device_ids = []
        for line in lspci_output:
            if line:
                line = line.strip().split(' ')
                device_ids.append(line[0])

        class Device:
            def __init__(self, device_info):
                self.domain = ""
                self.primary = ""
                self.slotfunc = ""
                self.name = ""
                self.secondary = ""
                self.capability = ""
                self.capspeed = 0
                self.capwidth = 0
                self.staspeed = 0
                self.stawidth = 0

                # 0000:00:00.0 PCI bridge: IBM Device 03dc
                id_components = device_info[0].split(":")
                self.domain = id_components[0]
                self.primary = id_components[1]
                self.slotfunc = id_components[2].split()[0]
                self.name = id_components[-1].strip()

                for line in device_info[1:]:
                    if line:
                        line = line.strip()
                        if "Bus:" in line:
                            line = line.split("secondary=")
                            self.secondary = line[1][:2]
                        if "Express (v" in line:
                            self.capability = "Endpoint"
                            if "Root Port" in line:
                                self.capability = "Root"
                            if "Upstream" in line:
                                self.capability = "Upstream"
                            if "Downstream" in line:
                                self.capability = "Downstream"
                        if "LnkCap:" in line:
                            # LnkCap:   Port #0, Speed 8GT/s, Width x16, ASPM L0s, Exit Latency L0s unlimited, L1 unlimited
                            line = line.split("GT/s, Width x")
                            self.capspeed = float(line[0].split()[-1])
                            self.capwidth = float(line[1].split(",")[0])
                        if "LnkSta:" in line:
                            # LnkSta:   Speed 8GT/s, Width x8, TrErr- Train- SlotClk+ DLActive+ BWMgmt- ABWMgmt+
                            line = line.split("GT/s, Width x")
                            self.staspeed = float(line[0].split()[-1])
                            self.stawidth = float(line[1].split(",")[0])

            def get_details(self):
                msg = ("{}, capability={}, secondary={} \n"
                       .format(self.get_id(), self.capability, self.secondary))
                msg += ("capspeed={}, capwidth={}, staspeed={}, stawidth={}"
                        .format(self.capspeed, self.capwidth, self.staspeed, self.stawidth))
                return msg

            def get_id(self):
                return "{}:{}:{}".format(self.domain, self.primary, self.slotfunc)

        # Checking if two devices are linked together
        def devicesLinked(upstream, downstream):
            if upstream.domain == downstream.domain:
                if upstream.secondary == downstream.primary:
                    if upstream.capability == "Root":
                        if downstream.capability == "Upstream":
                            return True
                        if downstream.capability == "Endpoint":
                            return True
                    if upstream.capability == "Downstream":
                        if downstream.capability == "Endpoint":
                            return True
            return False

        # Checking if LnkSta matches LnkCap - speed
        def optimalSpeed(upstream, downstream):
            if upstream.capspeed > downstream.capspeed:
                optimal_speed = downstream.capspeed
            else:
                optimal_speed = upstream.capspeed
            if optimal_speed > upstream.staspeed:
                return False
            return True

        # Checking if LnkSta matches LnkCap - width
        def optimalWidth(upstream, downstream):
            if upstream.capwidth > downstream.capwidth:
                optimal_width = downstream.capwidth
            else:
                optimal_width = upstream.capwidth
            if optimal_width > upstream.stawidth:
                return False
            return True

        device_list = []

        # Filling device objects' details
        for device in device_ids:
            device_info = self.c.run_command("lspci -s {} -vv".format(device))
            device_list.append(Device(device_info))

        checked_devices = []
        suboptimal_links = ""
        blacklist_links = ""

        # Returns a string containing details of the suboptimal link
        def subLinkInfo(upstream, downstream):
            msg = "\nSuboptimal link between {} and {} - ".format(
                upstream.get_id(), downstream.get_id())
            if not optimalSpeed(upstream, downstream):
                if upstream.capspeed > downstream.capspeed:
                    optimal_speed = downstream.capspeed
                else:
                    optimal_speed = upstream.capspeed
                actual_speed = upstream.staspeed
                msg += "Link speed capability is {}GT/s but status was {}GT/s. ".format(
                    optimal_speed, actual_speed)
            if not optimalWidth(upstream, downstream):
                if upstream.capwidth > downstream.capwidth:
                    optimal_width = downstream.capwidth
                else:
                    optimal_width = upstream.capwidth
                actual_width = upstream.stawidth
                msg += "Link width capability is x{} but status was x{}. ".format(
                    optimal_width, actual_width)
            return msg

        # Searching through devices to check for links and testing to see if they're optimal
        for device in device_list:
            if device not in checked_devices:
                checked_devices.append(device)
                for endpoint in device_list:
                    if endpoint not in checked_devices:
                        if devicesLinked(device, endpoint):
                            checked_devices.append(endpoint)
                            log.debug("checking link between {} and {}".format(
                                device.get_id(), endpoint.get_id()))
                            log.debug(device.get_details())
                            log.debug(endpoint.get_details())
                            if endpoint.name in blacklist:
                                no_check_msg = ("Link between {} and {} not checked as {} is in the list of blacklisted devices"
                                                .format(device.get_id(), endpoint.get_id(), endpoint.get_id()))
                                log.info(no_check_msg)
                                blacklist_links += "{}\n".format(no_check_msg)
                            else:
                                if(not optimalSpeed(device, endpoint)) or (not optimalWidth(device, endpoint)):
                                    suboptimal_links += subLinkInfo(
                                        device, endpoint)
                            log.debug("")

        log.debug("Finished testing links")

        log.debug("blacklist_links={}".format(blacklist_links))
        log.debug("suboptimal_links={}".format(suboptimal_links))
        # Assert suboptimal list is empty
        self.assertEqual(len(suboptimal_links), 0, suboptimal_links)


class PCISkirootSoftboot(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''
    @classmethod
    def setUpClass(cls):
        super(PCISkirootSoftboot, cls).setUpClass()
        cls.pty.sendline("reboot")
        cls.cv_SYSTEM.set_state(OpSystemState.IPLing)
        # clear the states since we rebooted outside the state machine
        cls.cv_SYSTEM.util.clear_state(cls.cv_SYSTEM)
        cls.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

    @classmethod
    def tearDownClass(cls):
        super(PCISkirootSoftboot, cls).tearDownClass()

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCISkirootSoftboot, self).setUp()


class PCISkirootHardboot(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''
    @classmethod
    def setUpClass(cls):
        super(PCISkirootHardboot, cls).setUpClass(power_cycle=1)

    @classmethod
    def tearDownClass(cls):
        super(PCISkirootHardboot, cls).tearDownClass()

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCISkirootHardboot, self).setUp()


class PCISkiroot(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCISkiroot, self).setUp()


class PCIHostSoftboot(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''
    @classmethod
    def setUpClass(cls):
        super(PCIHostSoftboot, cls).setUpClass(desired=OpSystemState.OS)
        cls.pty.sendline("reboot")
        cls.cv_SYSTEM.set_state(OpSystemState.BOOTING)
        # clear the states since we rebooted outside the state machine
        cls.cv_SYSTEM.util.clear_state(cls.cv_SYSTEM)
        cls.cv_SYSTEM.goto_state(OpSystemState.OS)

    @classmethod
    def tearDownClass(cls):
        super(PCIHostSoftboot, cls).tearDownClass()

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCIHostSoftboot, self).setUp()


class PCIHostHardboot(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''
    @classmethod
    def setUpClass(cls):
        super(PCIHostHardboot, cls).setUpClass(
            desired=OpSystemState.OS, power_cycle=1)

    @classmethod
    def tearDownClass(cls):
        super(PCIHostHardboot, cls).tearDownClass()

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCIHostHardboot, self).setUp()


class PCIHost(OpClassPCI, unittest.TestCase):
    '''
    Class allows to run parent classes with unique setup
    '''
    @classmethod
    def setUpClass(cls):
        super(PCIHost, cls).setUpClass(desired=OpSystemState.OS)

    def setUp(self):
        # this left as placeholder for per test setUp
        super(PCIHost, self).setUp()


def skiroot_softboot_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite pci-regression
    --run testcases.OpTestPCI.skiroot_softboot_suite
    '''
    tests = ['pcie_link_errors', 'compare_live_devices',
             'pci_link_check', 'compare_boot_devices']
    return unittest.TestSuite(map(PCISkirootSoftboot, tests))


def skiroot_hardboot_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite pci-regression
    --run testcases.OpTestPCI.skiroot_hardboot_suite
    '''
    tests = ['pcie_link_errors', 'compare_live_devices',
             'pci_link_check', 'compare_boot_devices']
    return unittest.TestSuite(map(PCISkirootHardboot, tests))


def skiroot_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite BasicPCI
    --run testcases.OpTestPCI.skiroot_suite

    This suite does not care on soft vs hard boot
    '''
    tests = ['pcie_link_errors', 'compare_live_devices']
    return unittest.TestSuite(map(PCISkiroot, tests))


def skiroot_full_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run testcases.OpTestPCI.skiroot_full_suite

    This suite does not care on soft vs hard boot
    '''
    tests = ['pcie_link_errors', 'compare_live_devices',
             'pci_link_check', 'driver_bind']
    return unittest.TestSuite(map(PCISkiroot, tests))


def host_softboot_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite pci-regression
    --run testcases.OpTestPCI.host_softboot_suite
    '''
    tests = ['pcie_link_errors', 'compare_live_devices', 'pci_link_check',
             'compare_boot_devices', 'driver_bind', 'hot_plug_host']
    return unittest.TestSuite(map(PCIHostSoftboot, tests))


def host_hardboot_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite pci-regression
    --run testcases.OpTestPCI.host_hardboot_suite
    '''
    tests = ['pcie_link_errors', 'compare_live_devices', 'pci_link_check',
             'compare_boot_devices', 'driver_bind', 'hot_plug_host']
    return unittest.TestSuite(map(PCIHostHardboot, tests))


def host_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run-suite BasicPCI
    --run testcases.OpTestPCI.host_suite

    This suite does not care on soft vs hard boot
    '''
    tests = ['pcie_link_errors', 'compare_live_devices']
    return unittest.TestSuite(map(PCIHost, tests))


def host_full_suite():
    '''
    Function used to prepare a test suite (see op-test)
    --run testcases.OpTestPCI.host_full_suite

    This suite does not care on soft vs hard boot
    '''
    tests = ['pcie_link_errors', 'compare_live_devices',
             'pci_link_check', 'driver_bind', 'hot_plug_host']
    return unittest.TestSuite(map(PCIHost, tests))
