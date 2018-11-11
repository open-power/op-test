#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEEH.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2016
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
OpTestEEH
---------

This testcase basically tests all OPAL EEH Error injection tests.

- fenced PHB
- frozen PE
'''

import time
import subprocess
import subprocess
import re
import sys
import os

import unittest

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

EEH_HIT = 0
EEH_MISS = 1


class EEHRecoveryFailed(Exception):
    '''
    EEH Recovery failed on thing for reason.
    '''

    def __init__(self, thing, dev, log=None):
        self.thing = thing
        self.dev = dev
        self.log = log

    def __str__(self):
        return "%s %s recovery failed: Log=%s" % (self.thing, self.dev, self.log)


class EEHRemoveFailed(Exception):
    '''
    EEH Remove failed on thing for reason.
    '''

    def __init__(self, thing, dev, log=None):
        self.thing = thing
        self.dev = dev
        self.log = log

    def __str__(self):
        return "%s %s remove failed: Log=%s" % (self.thing, self.dev, self.log)


class EEHLocCodeFailed(Exception):
    '''
    Failed to log location code along with failure.
    '''

    def __init__(self, thing, dev, log=None):
        self.thing = thing
        self.dev = dev
        self.log = log

    def __str__(self):
        return "%s %s location code failure: Log=%s" % (self.thing, self.dev, self.log)


class OpTestEEH(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_HOST = conf.host()
        cls.cv_IPMI = conf.ipmi()
        cls.cv_SYSTEM = conf.system()
        # By default test will run on all PHBs/PE's, if one want to skip certain ones mention in this format.
        # ['PCI0001', 'PCI0002', 'PCI0003', 'PCI0004', 'PCI0005', 'PCI0030', 'PCI0031', 'PCI0032']
        cls.skip_phbs = []
        cls.skip_pes = []  # ['0002:00:00.0']

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.set_con_log_lev_crit()
        self.cv_HOST.host_gather_opal_msg_log(console=1)
        self.cv_HOST.host_gather_kernel_log(console=1)
        self.cv_SYSTEM.console.run_command("dmesg -D")
        self.cv_SYSTEM.console.run_command("uname -a")
        self.cv_SYSTEM.console.run_command("cat /etc/os-release")

    def get_test_pci_domains(self):
        root_domain = self.cv_HOST.host_get_root_phb(console=1)
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains(console=1)
        log.debug(
            "Skipping the root phb %s for both fenced/frozen EEH Testcases" % root_domain)
        pci_domains.remove(root_domain)
        if len(self.skip_phbs) != 0:
            log.debug("Skipping the known phbs %s from user" % self.skip_phbs)
            pci_domains = [
                domain for domain in pci_domains if domain not in self.skip_phbs]
        return pci_domains

    def prepare_logs(self):
        '''
        This function is used to prepare opal and kernel logs to
        a reference point, so that we can compare logs for each EEH
        iteration easily.

        Basically, we throw logs in a temp file and diff them afterwards.
        '''
        cmd = "cat /sys/firmware/opal/msglog|grep ',[0-4]\]' > /tmp/opal_msglog"
        self.cv_SYSTEM.console.run_command_ignore_fail(cmd)
        self.cv_SYSTEM.console.run_command("dmesg -C")

    def gather_logs(self):
        '''
        This function is used to gather opal and kernel logs
        for each EEH iteration instead of full logs.

        This should make it easier to debug problems as you'll have
        the specific log messages that occured for each test.
        '''
        cmd = "grep ',[0-4]\]' /sys/firmware/opal/msglog | diff - /tmp/opal_msglog"
        self.cv_SYSTEM.console.run_command_ignore_fail(cmd)
        self.cv_SYSTEM.console.run_command("dmesg")

    def check_eeh_phb_recovery(self, i_domain):
        '''
        This function is used to actually check the PHB recovery
        after an EEH Fenced PHB Error Injection.

        We scrape the kernel log for the correct strings.
        '''
        cmd = "dmesg  | grep -i 'EEH: Notify device driver to resume'; echo $?"
        tries = 60
        for i in range(1, tries+1):
            res = self.cv_SYSTEM.console.run_command(cmd)
            if int(res[-1]):
                log.debug("Waiting for PHB %s EEH Completion: (%d/%d)" %
                          (i_domain, i, tries))
                time.sleep(1)
            else:
                break
        else:
            self.gather_logs()
            raise EEHRecoveryFailed("EEH recovery failed", i_domain)

        tries = 30
        domain = i_domain.split("PCI")[1]
        for j in range(1, tries+1):
            list = self.get_list_of_pci_devices()
            for device in list:
                if domain in device:
                    return True
            time.sleep(0.2)
        else:
            return False

    def get_list_of_pci_devices(self):
        '''
        This function is used to get list of PCI devices
        available at that instant of time.
        '''
        cmd = "ls /sys/bus/pci/devices"
        res = self.cv_SYSTEM.console.run_command(cmd)
        return res

    def get_dic_of_pe_vs_addr(self):
        '''
        Get dictionary of pe vs config addr.
        e.g.

        ::

          {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}

        '''
        pe_dic = {}
        # Get list of PE's
        console = self.cv_SYSTEM.console
        res = console.run_command(
            "ls /sys/bus/pci/devices/ | awk {'print $1'}")
        if len(self.skip_pes) != 0:
            log.debug("Skipping the known PE's %s from user" % self.skip_pes)
        for pe in res:
            if not pe or pe in self.skip_pes:
                continue
            cmd = "cat /sys/bus/pci/devices/%s/eeh_pe_config_addr" % pe
            addr = console.run_command(cmd)
            pe_dic[pe] = ((addr[0]).split("x"))[1]
        return pe_dic

    def run_pe_4(self, addr, e, f, phb, pe, con):
        '''
        Inject error and check for recovery, finally gather logs.

        Returns True if PE recovers, False if failed to recover.
        '''
        self.prepare_logs()
        try:
            self.inject_error(addr, e, f, phb, pe)
        except CommandFailed as cf:
            if cf.exitcode != 0:
                log.debug("Skipping verification as command failed")
                return EEH_MISS
        if not self.check_eeh_hit():
            return EEH_MISS
        else:
            log.debug("PE %s EEH hit success" % pe)
            return EEH_HIT

    def inject_error(self, addr, e, f, phb, pe):
        '''
        Inject error:

        addr
          PE address
        e
          0
            32 bit errors
          1
            64 bit errors
        f (Function)
          0
            MMIO read
          4
            CFG read
          6
            MMIO write
          10
            CFG write
        phb
          PHB Index
        pe
          PE BDF address
        '''
        cmd = "echo %s:%s:%s:0:0 > /sys/kernel/debug/powerpc/PCI%s/err_injct && lspci -ns %s" % (
            addr, e, f, phb, pe)
        res = self.cv_SYSTEM.console.run_command(cmd)

    def check_eeh_slot_resets(self):
        '''
        Check for EEH Slot Reset count. i.e. ::

          $ cat /proc/powerpc/eeh | tail -n 1
          eeh_slot_resets=10

        Returns integer (in above example '10').
        '''
        cmd = "cat /proc/powerpc/eeh | tail -n 1"
        count = self.cv_SYSTEM.console.run_command(cmd)
        output = (count[0].split("="))[1]
        return output

    def check_eeh_pe_recovery(self, pe):
        '''
        return True if PE is available in the system
        else return False. Which will be useful for
        checking the PE after injecting the EEH error
        '''
        cmd = "dmesg  | grep -i 'EEH: Notify device driver to resume'; echo $?"
        tries = 60
        for i in range(1, tries+1):
            res = self.cv_SYSTEM.console.run_command(cmd)
            if int(res[-1]):
                log.debug("Waiting for PE %s EEH Completion: (%d/%d)" %
                          (pe, i, tries))
                time.sleep(1)
            else:
                break
        else:
            self.gather_logs()
            raise EEHRecoveryFailed("EEH recovery failed", pe)

        tries = 30
        for j in range(1, tries+1):
            list = self.get_list_of_pci_devices()
            for device in list:
                if pe in device:
                    return True
            time.sleep(1)
        else:
            return False

    def check_eeh_hit(self):
        c = self.cv_SYSTEM.console
        tries = 10
        for i in range(1, tries+1):
            try:
                res = c.run_command("dmesg | grep 'EEH: Frozen'")
            except CommandFailed as cf:
                continue
            return True
            time.sleep(1)
        else:
            return False

    def check_eeh_removed(self):
        tries = 60
        c = self.cv_SYSTEM.console
        for i in range(1, tries+1):
            try:
                res = c.run_command("dmesg | grep 'permanently disabled'")
            except CommandFailed as cf:
                continue
            return True
            time.sleep(1)
        else:
            return False

    def set_con_log_lev_crit(self):
        '''
        EEH verbose is enabled in P9. Until we have a capable of setting console log level in runtime,
        or EEH verbose is disabled in P9, we need to disable the console logging to make tests run.
        (But at the cost of one additional IPL execution overhead)

        TODO: Remove this once we have a way of disabling console log level in runtime without
        having an additional IPL.

        '''
        self.cpu = self.cv_HOST.host_get_proc_gen(console=1)
        if self.cpu in ["POWER8", "POWER8E"]:
            return
        try:
            level = "".join(self.cv_SYSTEM.console.run_command(
                "nvram -p ibm,skiboot --print-config=log-level-driver"))
        except CommandFailed:
            level = "5"
        if level == "2":
            return
        self.cv_SYSTEM.console.run_command(
            "nvram -p ibm,skiboot --update-config log-level-driver=2")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def verify_location_code_logging(self, pe):
        tries = 60
        c = self.cv_SYSTEM.console
        for i in range(1, tries+1):
            try:
                res = c.run_command(
                    "dmesg | grep -i --color=never 'EEH: PE location:'")
                found = True
            except CommandFailed as cf:
                continue
            if found:
                break
            time.sleep(1)
        else:
            raise EEHLocCodeFailed(
                "PE ", pe, "Kernel failed to log the location codes for a PCI EEH error")

        matchObj = re.match(
            "(.*) EEH: PE location: (.*), PHB.*", res[-1], re.I)
        if matchObj:
            loc_code = matchObj.group(2)
            if loc_code == 'N/A':
                log.warning(
                    "FW/Kernel failed to log the pcie slot/device location code")


class OpTestEEHbasic_fenced_phb(OpTestEEH):
    '''
    This testcase has below steps:

    1. Get the list of pci PHB domains
    2. Get the root PHB domain where the root file system
       is installed(We need to skip this as EEH recovery will
       fail on root PHB).
    3. Start injecting the fenced PHB errors in a for loop
       Only one time basic check whether PHB recovered or not
    '''

    def runTest(self):
        pci_domains = self.get_test_pci_domains()
        for domain in pci_domains:
            self.prepare_logs()
            cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
            log.debug(
                "=================Injecting the fenced PHB error on PHB: %s=================" % domain)
            self.cv_SYSTEM.console.run_command_ignore_fail(cmd)
            # Give some time to EEH PCI Error recovery
            if self.check_eeh_phb_recovery(domain):
                log.debug("PHB %s recovery successful" % domain)
            else:
                self.gather_logs()
                raise EEHRecoveryFailed("PHB domain", domain)
            self.gather_logs()


class OpTestEEHmax_fenced_phb(OpTestEEH):
    '''
    This testcase has below steps:

    1. Get the list of pci PHB domains
    2. Get the root PHB domain where the root file system
       is installed(We need to skip this as EEH recovery will
       fail on root PHB).
    3. Set the MAX EEH Freeze count to 1 so that we can
       test max EEH Recovery capacity within less for loop executions
       By default it is 6,
    4. Start injecting the fenced PHB errors two times across all PHB domains
       except root PHB.( As we set max EEH Freeze count to 1).
       So expectation is first time it should recover and second time
       EEH should properly remove the device and OS should not crash.
    '''

    def runTest(self):
        pci_domains = self.get_test_pci_domains()
        # Set the max EEH freeze count to 1
        cmd = "echo 1 > /sys/kernel/debug/powerpc/eeh_max_freezes"
        self.cv_SYSTEM.console.run_command(cmd)
        for i in range(0, 2):
            for domain in pci_domains:
                self.prepare_logs()
                cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
                log.debug(
                    "=================Injecting the fenced PHB error on PHB: %s=================" % domain)
                self.cv_SYSTEM.console.run_command_ignore_fail(cmd)
                # Give some time to EEH PCI Error recovery
                if i == 0:
                    if self.check_eeh_phb_recovery(domain):
                        log.debug("PHB %s recovery successful" % domain)
                    else:
                        self.gather_logs()
                        raise EEHRecoveryFailed("PHB domain", domain)
                else:
                    if self.check_eeh_removed():
                        log.debug(
                            "PHB domain %s removed successfully" % domain)
                    else:
                        self.gather_logs()
                        raise EEHRemoveFailed("PHB domain", domain)
                self.gather_logs()


class OpTestEEHbasic_frozen_pe(OpTestEEH):
    '''
    This testcase has below steps

    1. Get the list of pci PHB domains
    2. Get the root PHB domain where the root file system
       is installed(We need to skip this as EEH recovery will
       fail on root PHB).
    3. get dictionary of pe vs config addr.

       Ex: ::

         {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}

    4. Prepare below command & Start inject frozenPE errors on all PE's ::

        echo "PE_number:<0,1>:<function>:0:0" > /sys/kernel/debug/powerpc/PCIxxxx/err_injct

    5. Gather necssary logs(dmesg & OPAL) and check the device(PE) got
       recovered or not.
    '''

    def runTest(self):
        pci_domains = self.get_test_pci_domains()
        pe_dic = self.get_dic_of_pe_vs_addr()
        log.debug(
            "==================Testing frozen PE error injection=====================")

        # Frequently used function
        # 0 : MMIO read
        # 4 : CFG read
        # 6 : MMIO write
        # 10: CFG write
        func = [0, 4, 6, 10]
        ERROR = [0, 1]
        # "pe_no:0:function:address:mask" - 32-bit PCI errors
        # "pe_no:1:function:address:mask" - 64-bit PCI errors

        # Ex: echo "PE_number:<0,1>:<function>:0:0" > /sys/kernel/debug/powerpc/PCIxxxx/err_injct
        # echo 2:0:4:0:0 > /sys/kernel/debug/powerpc/PCI0001/err_injct && lspci -ns 0001:0c:00.0; echo $?
        # Inject error on every PE
        for pe, addr in list(pe_dic.items()):
            count = 0
            recover = True
            for e in ERROR:
                phb = (pe.split(":"))[0]
                if count > 5 or not recover:
                    break
                # Skip the PE's under root PHB
                if any(phb in s for s in pci_domains):
                    for f in func:
                        log.debug(
                            "===================Running error injection on pe %s func %s===================" % (pe, f))
                        rc = 1
                        rc = self.run_pe_4(
                            addr, e, f, phb, pe, self.cv_SYSTEM.console)
                        if rc == EEH_MISS:
                            continue
                        count += 1
                        if count < 6:  # Upto five times check for recovery
                            try:
                                ret = self.check_eeh_pe_recovery(pe)
                                self.gather_logs()
                            except EEHRecoveryFailed:
                                log.error(
                                    "EEH_FAIL: PE %s recovery failed after %d EEH error" % (pe, count))
                                recover = False
                                break
                            if not ret:
                                log.error(
                                    "EEH_FAIL: PE %s recovery failed after %d EEH error" % (pe, count))
                                recover = False
                                break
                            log.debug(
                                "PE %s recovered after %d EEH error" % (pe, count))
                        elif count == 6:  # sixth time check for removal
                            if not self.check_eeh_removed():
                                log.error(
                                    "EEH_FAIL: PE %s remove failed after 6th EEH hit" % pe)
                            else:
                                log.debug(
                                    "PE %s removed successfully after 6th EEH hit" % pe)
                        self.check_eeh_slot_resets()
                        self.verify_location_code_logging(pe)


class OpTestEEHmax_frozen_pe(OpTestEEH):
    '''
    This testcase has below steps

    1. Get the list of pci PHB domains
    2. Get the root PHB domain where the root file system
       is installed(We need to skip this as EEH recovery will
       fail on root PHB).
    3. get dictionary of pe vs config addr. Ex: ::

         {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}

    4. Prepare below command & Start inject frozenPE errors on all PE's ::

        echo "PE_number:<0,1>:<function>:0:0" > /sys/kernel/debug/powerpc/PCIxxxx/err_injct

    5. Gather necssary logs(dmesg & OPAL) and check the device(PE) got
       recovered or not.
    '''

    def runTest(self):
        pci_domains = self.get_test_pci_domains()
        # Set the max EEH freeze count to 1
        cmd = "echo 1 > /sys/kernel/debug/powerpc/eeh_max_freezes"
        self.cv_SYSTEM.console.run_command(cmd)
        pe_dic = self.get_dic_of_pe_vs_addr()
        log.debug(
            "======================Testing frozen PE error injection===========================")

        # Frequently used function
        # 0 : MMIO read
        # 4 : CFG read
        # 6 : MMIO write
        # 10: CFG write
        func = [0, 4, 6, 10]
        ERROR = [0, 1]
        # "pe_no:0:function:address:mask" - 32-bit PCI errors
        # "pe_no:1:function:address:mask" - 64-bit PCI errors

        # Ex: echo "PE_number:<0,1>:<function>:0:0" > /sys/kernel/debug/powerpc/PCIxxxx/err_injct
        # echo 2:0:4:0:0 > /sys/kernel/debug/powerpc/PCI0001/err_injct && lspci -ns 0001:0c:00.0; echo $?
        # Inject error on every PE
        for pe, addr in list(pe_dic.items()):
            count = 0
            recover = True
            for e in ERROR:
                if count > 1 or not recover:
                    break
                phb = (pe.split(":"))[0]
                # Skip the PE's under root PHB
                if any(phb in s for s in pci_domains):
                    for f in func:
                        log.debug(
                            "=====================Running error injection on pe %s func %s====================" % (pe, f))
                        rc = 1
                        rc = self.run_pe_4(
                            addr, e, f, phb, pe, self.cv_SYSTEM.console)
                        if rc == EEH_MISS:
                            continue
                        count += 1
                        if count == 1:  # First time check for recovery
                            try:
                                ret = self.check_eeh_pe_recovery(pe)
                                self.gather_logs()
                            except EEHRecoveryFailed:
                                log.error(
                                    "EEH_FAIL: PE %s recovery failed after first EEH error" % pe)
                                recover = False
                                break
                            if not ret:
                                log.error(
                                    "EEH_FAIL: PE %s recovery failed after first EEH error" % pe)
                                recover = False
                                break
                            else:
                                log.debug(
                                    "PE % recovered after first EEH error" % pe)
                        elif count == 2:  # Second time check for removal
                            if not self.check_eeh_removed():
                                log.error("EEH_FAIL: PE %s remove failed" % pe)
                            else:
                                log.debug("PE %s removed successfully" % pe)
                        self.check_eeh_slot_resets()
                        self.verify_location_code_logging(pe)


def suite():
    s = unittest.TestSuite()
    s.addTest(OpTestEEHbasic_fenced_phb())
    s.addTest(OpTestEEHmax_fenced_phb())
    s.addTest(OpTestEEHbasic_frozen_pe())
    s.addTest(OpTestEEHmax_frozen_pe())
    return s
