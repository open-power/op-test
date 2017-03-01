#!/usr/bin/python
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

#  @package OpTestEEH.py
#   This testcase basically tests all OPAL EEH Error injection tests.
#   fenced PHB
#   frozen PE

import time
import subprocess
import commands
import re
import sys
import os

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

class EEHRecoveryFailed(Exception):
    def __init__(self, thing, dev, log=None):
        self.thing = thing
        self.dev = dev
        self.log = log
    def __str__(self):
        return "%s %s recovery failed: %s" % (self.thing, self.dev, self.log)

class OpTestEEH(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()
    ##
    # @brief  This function is used to prepare opal and kernel logs to
    #         a reference point, so that we can compare logs for each EEH
    #         iteration easily
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def prepare_logs(self):
        cmd = "rm -rf /tmp/opal_msglog;touch /sys/firmware/opal/msglog; cp /sys/firmware/opal/msglog /tmp/opal_msglog"
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        c.run_command(cmd)
        c.run_command("dmesg -C")

    ##
    # @brief  This function is used to gather opal and kernel logs
    #         for each EEH iteration instead of full logs
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def gather_logs(self):
        cmd = "diff /sys/firmware/opal/msglog /tmp/opal_msglog"
        c = self.cv_SYSTEM.sys_get_ipmi_console()
        c.run_command(cmd)
        c.run_command("dmesg")


    ##
    # @brief  This function is used to actually check the PHB recovery
    #         after an EEH Fenced PHB Error Injection.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def check_eeh_phb_recovery(self, i_domain):
        domain = i_domain.split("PCI")[1]
        list = self.get_list_of_pci_devices()
        for device in list:
            if domain in device:
                return True
        return False


    ##
    # @brief  This function is used to get list of PCI devices
    #         available at that instant of time.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def get_list_of_pci_devices(self):
        cmd = "ls /sys/bus/pci/devices"
        res = self.cv_SYSTEM.sys_get_ipmi_console().run_command(cmd)
        return res

        ##
    # @brief   Get dictionary of pe vs config addr
    #          Ex: {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}
    #
    # @returns pe_dic @type dictionary:
    #
    def get_dic_of_pe_vs_addr(self):
        pe_dic = {}
        # Get list of PE's
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        res = console.run_command("ls /sys/bus/pci/devices/ | awk {'print $1'}")
        for pe in res:
            if not pe:
                continue
            cmd = "cat /sys/bus/pci/devices/%s/eeh_pe_config_addr" % pe
            addr = console.run_command(cmd)
            pe_dic[pe] = ((addr[0]).split("x"))[1]
        return pe_dic


    ##
    # @brief   Inject error and check for recovery, finally gather logs
    #
    # @returns True-->If PE is recover
    #          False-->If PE is failed to recover.
    #
    def run_pe_4(self, addr, e, f, phb, pe, con):
        self.prepare_logs()
        count_old = self.check_eeh_slot_resets()
        rc = self.inject_error(addr, e, f, phb, pe)
        if rc != 0:
            print "Skipping verification as command failed"
            return
        # Give some time to EEH PCI Error recovery
        time.sleep(60)
        count = self.check_eeh_slot_resets()
        if int(count) > int(count_old):
            print "PE Slot reset happenned successfully on pe: %s" % pe
        else:
            print "PE Slot reset not happened on pe: %s" % pe
        self.gather_logs()
        if not self.check_eeh_pe_recovery(pe):
            msg = "PE %s recovery failed" % pe
            print msg
            # Don't exit here, continue to test with other adapters
            #raise OpTestError(msg)
            return False
        else:
            print "PE %s recovery success" % pe
        return True


    ##
    # @brief   Inject error
    #           addr: PE address
    #           e   : 0->32 bit errors
    #               : 1->64 bit errors
    #           f   : Function
    #                   0 : MMIO read
    #                   4 : CFG read
    #                   6 : MMIO write
    #                   10: CFG write
    #           phb : PHB Index
    #           pe  : PE BDF address
    #
    # @returns command return code @type integer
    #
    def inject_error(self, addr, e, f, phb, pe):
        cmd = "echo %s:%s:%s:0:0 > /sys/kernel/debug/powerpc/PCI%s/err_injct && lspci -ns %s; echo $?" % (addr, e, f, phb, pe)
        res = self.cv_SYSTEM.sys_get_ipmi_console().run_command(cmd)
        return int(res[-1])


    ##
    # @brief   Check for EEH Slot Reset count
    #          cat /proc/powerpc/eeh | tail -n 1
    #          eeh_slot_resets=10
    #
    # @returns output @type string: EEH Slot reset count
    #
    def check_eeh_slot_resets(self):
        cmd = "cat /proc/powerpc/eeh | tail -n 1"
        count = self.cv_SYSTEM.sys_get_ipmi_console().run_command(cmd)
        output = (count[-1].split("="))[1]
        return output


    ##
    # @brief   return True if PE is available in the system
    #           else return False. Which will be useful for
    #           checking the PE after injecting the EEH error
    #
    # @returns True/False @type boolean
    #
    def check_eeh_pe_recovery(self, pe):
        list = self.get_list_of_pci_devices()
        for device in list:
            if pe in device:
                return True
        return False


class OpTestEEHbasic_fenced_phb(OpTestEEH):
    ##
    # @brief  This testcase has below steps
    #         1. Get the list of pci PHB domains
    #         2. Get the root PHB domain where the root file system
    #            is installed(We need to skip this as EEH recovery will
    #            fail on root PHB).
    #         3. Start injecting the fenced PHB errors in a for loop
    #            Only one time basic check whether PHB recovered or not
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()

        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb %s for fenced PHB Testcase" % root_domain
        pci_domains.remove(root_domain)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con.run_command("stty cols 300")
        l_con.run_command("stty rows 10")
        l_con.run_command("dmesg -D")
        l_con.run_command("uname -a")
        l_con.run_command("cat /etc/os-release")
        for domain in pci_domains:
            self.prepare_logs()
            cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
            print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
            l_con.run_command(cmd)
            # Give some time to EEH PCI Error recovery
            time.sleep(30)
            self.gather_logs()
            if not self.check_eeh_phb_recovery(domain):
                raise EEHRecoveryFailed("PHB domain", domain)
            else:
                print "PHB %s recovery successful" % domain

class OpTestEEHmax_fenced_phb(OpTestEEH):
    ##
    # @brief  This testcase has below steps
    #         1. Get the list of pci PHB domains
    #         2. Get the root PHB domain where the root file system
    #            is installed(We need to skip this as EEH recovery will
    #            fail on root PHB).
    #         3. Set the MAX EEH Freeze count to 1 so that we can
    #            test max EEH Recovery capacity within less for loop executions
    #            By default it is 6,
    #         4. Start injecting the fenced PHB errors two times across all PHB domains
    #            except root PHB.( As we set max EEH Freeze count to 1).
    #            So expectation is first time it should recover and second time
    #            EEH should properly remove the device and OS should not crash.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb %s for fenced PHB Testcase" % root_domain
        pci_domains.remove(root_domain)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        # Set the max EEH freeze count to 1
        cmd = "echo 1 > /sys/kernel/debug/powerpc/eeh_max_freezes"
        self.cv_HOST.host_run_command(cmd)
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con.run_command("stty cols 300")
        l_con.run_command("stty rows 10")
        l_con.run_command("dmesg -D")
        l_con.run_command("uname -a")
        l_con.run_command("cat /etc/os-release")
        for i in range(0,2):
            for domain in pci_domains:
                self.prepare_logs()
                cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
                print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
                l_con.run_command(cmd)
                # Give some time to EEH PCI Error recovery
                time.sleep(30)
                self.gather_logs()
                if i == 0:
                    if not self.check_eeh_phb_recovery(domain):
                        raise EEHRecoveryFailed("PHB domain", domain)
                    else:
                        print "PHB %s recovery successful" % domain
                else:
                    if self.check_eeh_phb_recovery(domain):
                        raise EEHRecoveryFailed("PHB domain", domain)
                    else:
                        print "PHB domain %s removed successfully" % domain

class OpTestEEHbasic_frozen_pe(OpTestEEH):
    ##
    # @brief  This testcase has below steps
    #         1. Get the list of pci PHB domains
    #         2. Get the root PHB domain where the root file system
    #            is installed(We need to skip this as EEH recovery will
    #            fail on root PHB).
    #         3. get dictionary of pe vs config addr
    #            Ex: {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}
    #         4.Prepare below command & Start inject frozenPE errors on all PE's
    #           echo "PE_number:<0,1>:<function>:0:0" > /sys/kernel/debug/powerpc/PCIxxxx/err_injct
    #         5. Gather necssary logs(dmesg & OPAL) and check the device(PE) got
    #            recovered or not.
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb %s for frozen PE Testcase" % root_domain
        pci_domains.remove(root_domain)
        pe_dic = self.get_dic_of_pe_vs_addr()
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con.run_command("stty cols 300")
        l_con.run_command("stty rows 10")
        l_con.run_command("dmesg -D")
        l_con.run_command("uname -a")
        l_con.run_command("cat /etc/os-release")
        print "==============================Testing frozen PE error injection==============================="

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
        for e in ERROR:
            for pe, addr in pe_dic.iteritems():
                phb = (pe.split(":"))[0]
                # Skip the PE's under root PHB
                if any(phb in s for s in pci_domains):
                    for f in func:
                        print "==========================Running error injection on pe %s func %s======================" % (pe, f)
                        self.run_pe_4(addr, e, f, phb, pe, l_con)



def suite():
    s = unittest.TestSuite()
    s.addTest(OpTestEEHbasic_fenced_phb())
    s.addTest(OpTestEEHmax_fenced_phb())
    s.addTest(OpTestEEHbasic_frozen_pe())
    return s
