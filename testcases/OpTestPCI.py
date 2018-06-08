#!/usr/bin/python2
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

#  @package OpTestPCI.py
#   This testcase basically will test and gather PCI subsystem Info
#   Tools used are lspci and lsusb
#   any pci related tests will be added in this package

import time
import subprocess
import commands
import re
import sys
import os
import os.path

import unittest

import OpTestConfiguration
from distutils.version import LooseVersion
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed


class TestPCI():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.pci_good_data_file = conf.lspci_file()
        self.bmc_type = conf.args.bmc_type

    def pcie_link_errors(self):
        total_entries = link_down_entries = timeout_entries = []
        try:
            link_down_entries = self.c.run_command("grep ',[432]\].*PHB#.* Link down' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if link_down_entries:
            total_entries = total_entries + link_down_entries
        try:
            timeout_entries = self.c.run_command("grep ',[432]\].*Timeout waiting for' /sys/firmware/opal/msglog")
        except CommandFailed as cf:
            pass
        if timeout_entries:
            total_entries = total_entries + timeout_entries
        msg = '\n'.join(filter(None, total_entries))
        self.assertTrue( len(total_entries) == 0, "pcie link down/timeout Errors in OPAL log:\n%s" % msg)


    def get_list_of_pci_devices(self):
        cmd = "ls /sys/bus/pci/devices/ | awk {'print $1'}"
        res = self.c.run_command(cmd)
        return res

    def get_driver(self, pe):
        cmd = "lspci -ks %s" % pe
        output = self.c.run_command(cmd, timeout=120)
        if output:
            for line in output:
                if 'Kernel driver in use:' in line:
                    return (line.rsplit(":")[1]).strip(" ")
        return None

    def get_list_of_slots(self):
        cmd = "ls /sys/bus/pci/slots/ -1"
        res = self.c.run_command(cmd)
        return res

    def get_root_pe_address(self):
        cmd = "df -h /boot | awk 'END {print $1}'"
        res = self.c.run_command(cmd)
        boot_disk = ''.join(res).split("/dev/")[1]
        boot_disk = boot_disk.replace("\r\n", "")
        cmd  = "ls -l /dev/disk/by-path/ | grep %s | awk '{print $(NF-2)}'" % boot_disk
        res = self.c.run_command(cmd)
        root_pe = res[0].split("-")[1]
        return  root_pe

    def gather_errors(self):
        # Gather all errors from kernel and opal logs
        try:
            self.c.run_command("dmesg -r|grep '<[4321]>'")
        except CommandFailed:
            pass
        try:
            self.c.run_command("grep ',[0-4]\]' /sys/firmware/opal/msglog")
        except CommandFailed:
            pass


    def check_pci_devices(self):
        c = self.c
        l_res = c.run_command("lspci -mm -n")
        # We munge the result back to what we'd get
        # from "ssh user@host lspci -mm -n > host-lspci.txt" so that the diff
        # is simple to do
        self.pci_data_hostos = '\n'.join(l_res) + '\n'
        diff_process = subprocess.Popen(['diff', "-u", self.pci_good_data_file , "-"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_hostos)
        r = diff_process.wait()
        self.assertEqual(r, 0, "Stored and detected PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

    # Compare host "lspci -mm -n" output to known good
    def runTest(self):
        self.setup_test()
        c = self.c

        list_pci_devices_commands = ["lspci -mm -n",
                                     "lspci -m",
                                     "lspci -t",
                                     "lspci -n",
                                     "lspci -nn",
                                     "cat /proc/bus/pci/devices",
                                     "ls /sys/bus/pci/devices/ -l",
                                     "lspci -vvxxx",
                                     ]
        for cmd in list_pci_devices_commands:
            c.run_command(cmd, timeout=300)

        list_usb_devices_commands = ["lsusb",
                                     "lsusb -t",
                                     "lsusb -v",
                                     ]
        for cmd in list_usb_devices_commands:
            c.run_command(cmd)

        # Test we don't EEH on reading all config space
        c.run_command("hexdump -C /sys/bus/pci/devices/*/config", timeout=600)

        if not self.pci_good_data_file:
            self.skipTest("No good pci data provided")
        self.check_pci_devices()


class TestPCISkiroot(TestPCI, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class TestPCIHost(TestPCI, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()

class PcieLinkErrorsHost(TestPCIHost, unittest.TestCase):

    def runTest(self):
        self.setup_test()
        self.pcie_link_errors()

class PcieLinkErrorsSkiroot(TestPCISkiroot, unittest.TestCase):

    def runTest(self):
        self.setup_test()
        self.pcie_link_errors()

class TestPciSkirootReboot(TestPCI, unittest.TestCase):

    def set_up(self):
        self.test = "skiroot_reboot"

    def runTest(self):
        self.set_up()
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        if "skiroot_reboot" in self.test:
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        elif "distro_reboot" in self.test:
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_res = c.run_command("lspci -mm -n")
        self.pci_data_hardboot = '\n'.join(l_res) + '\n'
        with open("pci_file_hardboot", 'w') as file:
            for line in self.pci_data_hardboot:
                file.write(line)
        file.close()
        # reboot from petitboot kernel
        c.sol.sendline("reboot")
        self.cv_SYSTEM.wait_for_petitboot()
        self.cv_SYSTEM.set_state(OpSystemState.PETITBOOT)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_SYSTEM.host_console_unique_prompt()
        l_res = c.run_command("lspci -mm -n")
        self.pci_data_softreboot = '\n'.join(l_res) + '\n'
        diff_process = subprocess.Popen(['diff', "-u", "pci_file_hardboot", "-"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_softreboot)
        r = diff_process.wait()
        self.assertEqual(r, 0, "Hard and Soft reboot PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

class TestPciOSReboot(TestPciSkirootReboot, unittest.TestCase):

    def set_up(self):
        self.test = "distro_reboot"

class TestPciSkirootvsOS(TestPCI, unittest.TestCase):

    def runTest(self):
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.cv_SYSTEM.host_console_unique_prompt()
        l_res = c.run_command("lspci -mm -n")
        self.pci_data_skiroot = '\n'.join(l_res) + '\n'
        with open("pci_file_skiroot", 'w') as file:
            for line in self.pci_data_skiroot:
                file.write(line)
        file.close()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_res = c.run_command("lspci -mm -n")
        self.pci_data_hostos = '\n'.join(l_res) + '\n'
        diff_process = subprocess.Popen(['diff', "-u", "pci_file_skiroot", "-"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diff_stdout, diff_stderr = diff_process.communicate(self.pci_data_hostos)
        r = diff_process.wait()
        self.assertEqual(r, 0, "Skiroot and Host OS PCI devices differ:\n%s%s" % (diff_stdout, diff_stderr))

class TestPciDriverBindHost(TestPCIHost, unittest.TestCase):

    def set_up(self):
        self.test = "host"

    def test_bind(self):
        self.set_up()
        if "skiroot" in self.test:
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.cv_SYSTEM.sys_get_ipmi_console()
            self.cv_SYSTEM.host_console_unique_prompt()
            root_pe = "xxxx"
        else:
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.c = self.cv_SYSTEM.sys_get_ipmi_console()
            self.cv_SYSTEM.host_console_login()
            self.cv_SYSTEM.host_console_unique_prompt()
            root_pe = self.get_root_pe_address()
            self.c.run_command("dmesg -D")
        list = self.get_list_of_pci_devices()
        failure_list = {}
        for slot in list:
            rc = 0
            driver = self.get_driver(slot)
            if root_pe in slot:
                continue
            if driver is None:
                continue
            index = "%s_%s" % (driver, slot)
            cmd = "echo -n %s > /sys/bus/pci/drivers/%s/unbind" % (slot, driver)
            try:
                self.c.run_command(cmd)
            except CommandFailed as cf:
                msg = "Driver unbind operation failed for driver %s, slot %s" % (slot, driver)
                failure[index] = msg
            time.sleep(5)
            cmd = 'ls /sys/bus/pci/drivers/%s' % driver
            self.c.run_command(cmd)
            path = "/sys/bus/pci/drivers/%s/%s" % (driver, slot)
            try:
                self.c.run_command("test -d %s" % path)
                rc = 1
            except CommandFailed as cf:
                pass
            cmd = "echo -n %s > /sys/bus/pci/drivers/%s/bind" % (slot, driver)
            try:
                self.c.run_command(cmd)
            except CommandFailed as cf:
                msg = "Driver bind operation failed for driver %s, slot %s" % (slot, driver)
                failure_list[index] = msg
            time.sleep(5)
            cmd = 'ls /sys/bus/pci/drivers/%s' % driver
            self.c.run_command(cmd)
            try:
                self.c.run_command("test -d %s" % path)
            except CommandFailed as cf:
                rc = 2
            self.gather_errors()

            if rc == 1:
                msg = "%s not unbound for driver %s" % (slot, driver)
                failure_list[index] = msg

            if rc == 2:
                msg = "%s not bound back for driver %s" % (slot, driver)
                failure_list[index] = msg
        self.assertEqual(failure_list, {}, "Driver bind/unbind failures %s" % failure_list)


class TestPciDriverBindSkiroot(TestPciDriverBindHost, unittest.TestCase):

    def set_up(self):
        self.test = "skiroot"

class TestPciHotplugHost(TestPCI, unittest.TestCase):

    def runTest(self):
        # Currently this feature enabled for fsp systems
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific PCI Hotplug tests")
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        c = self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        res = self.c.run_command("uname -r")[-1].split("-")[0]
        if LooseVersion(res) < LooseVersion("4.10.0"):
            self.skipTest("This kernel does not support hotplug %s" % res)
        self.cv_HOST.host_load_module("pnv_php")
        device_list = self.get_list_of_pci_devices()
        root_pe = self.get_root_pe_address()
        slot_list = self.get_list_of_slots()
        self.c.run_command("dmesg -D")
        print device_list, slot_list
        pair = {} # Pair of device vs slot location code
        for device in device_list:
            cmd = "lspci -k -s %s -vmm" % device
            res = self.c.run_command(cmd)
            for line in res:
                #if "PhySlot:\t" in line:
                obj = re.match('PhySlot:\t(.*)', line)
                if obj:
                    pair[device] = obj.group(1)
        print pair
        failure_list = {}
        for device, phy_slot in pair.iteritems():
            if root_pe in device:
                continue
            index = "%s_%s" % (device, phy_slot)
            path = "/sys/bus/pci/slots/%s/power" % phy_slot
            try:
                self.c.run_command("test -f %s" % path)
            except CommandFailed as cf:
                print "Slot %s does not support hotplug" % phy_slot
                continue # slot does not support hotplug
            try:
                self.c.run_command("echo 0 > %s" % path)
            except CommandFailed as cf:
                msg = "PCI device/slot power off operation failed"
                failure_list[index] = msg
            time.sleep(5)
            cmd = "lspci -k -s %s" % device
            res = self.c.run_command(cmd)
            if device in "\n".join(res):
                msg = "PCI device failed to remove after power off operation"
                failure_list[index] = msg
            try:
                self.c.run_command("echo 1 > %s" % path)
            except CommandFailed as cf:
                msg = "PCI device/slot power on operation failed"
                failure_list[index] = msg
            res = self.c.run_command(cmd)
            if device not in "\n".join(res):
                msg = "PCI device failed to attach back after power on operation"
                failure_list[index] = msg
            self.gather_errors()
        self.assertEqual(failure_list, {}, "PCI Hotplug failures %s" % failure_list)


def suite():
    s = unittest.TestSuite()
    s.addTest(TestPCIHost())
    s.addTest(PcieLinkErrorsHost())
    s.addTest(TestPCISkiroot())
    s.addTest(PcieLinkErrorsSkiroot())
    s.addTest(TestPciSkirootvsOS())
    s.addTest(TestPciSkirootReboot())
    s.addTest(TestPciOSReboot())
    return s

