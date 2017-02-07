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

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestEEH():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, host=self.cv_HOST)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                                      i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                                      i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

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
    def test_basic_fenced_phb(self):
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb %s for fenced PHB Testcase" % root_domain
        pci_domains.remove(root_domain)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty cols 300")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty rows 10")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -D")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        for domain in pci_domains:
            self.prepare_logs()
            cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
            print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
            self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
            # Give some time to EEH PCI Error recovery
            time.sleep(30)
            l_con.sendline("\r\n")
            self.gather_logs()
            if not self.check_eeh_phb_recovery(domain):
                msg = "PHB domain %s recovery failed" % domain
                raise OpTestError(msg)
            else:
                print "PHB %s recovery successful" % domain

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
    def test_max_fenced_phb(self):
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
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty cols 300")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty rows 10")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -D")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
        for i in range(0,2):
            for domain in pci_domains:
                self.prepare_logs()
                cmd = "echo 0x8000000000000000 > /sys/kernel/debug/powerpc/%s/err_injct_outbound; lspci;" % domain
                print "=================Injecting the fenced PHB error on PHB: %s=================" % domain
                self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
                # Give some time to EEH PCI Error recovery
                time.sleep(30)
                l_con.sendline("\r\n")
                l_con.sendline("\r\n")
                self.gather_logs()
                if i == 0:
                    if not self.check_eeh_phb_recovery(domain):
                        msg = "PHB domain %s recovery failed" % domain
                        raise OpTestError(msg)
                    else:
                        print "PHB %s recovery successful" % domain
                else:
                    if self.check_eeh_phb_recovery(domain):
                        msg = "PHB domain %s not removed from the system" % domain
                        raise OpTestError(msg)
                    else:
                        print "PHB domain %s removed successfully" % domain

    ##
    # @brief  This function is used to prepare opal and kernel logs to
    #         a reference point, so that we can compare logs for each EEH
    #         iteration easily
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def prepare_logs(self):
        cmd = "rm -rf /tmp/opal_msglog;touch /sys/firmware/opal/msglog; cp /sys/firmware/opal/msglog /tmp/opal_msglog"
        self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -C")

    ##
    # @brief  This function is used to gather opal and kernel logs
    #         for each EEH iteration instead of full logs
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def gather_logs(self):
        cmd = "diff /sys/firmware/opal/msglog /tmp/opal_msglog"
        self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg")


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
        res = self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
        return res


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
    def test_basic_frozen_pe(self):
        root_domain = self.cv_HOST.host_get_root_phb()
        pci_domains = self.cv_HOST.host_get_list_of_pci_domains()
        print "Skipping the root phb %s for frozen PE Testcase" % root_domain
        pci_domains.remove(root_domain)
        pe_dic = self.get_dic_of_pe_vs_addr()
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty cols 300")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("stty rows 10")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("dmesg -D")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console("cat /etc/os-release")
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


    ##
    # @brief   Get dictionary of pe vs config addr
    #          Ex: {'0001:0c:00.2': '2', '0001:0b:00.0': 'fb', '0001:0c:00.0': '2'}
    #
    # @returns pe_dic @type dictionary:
    #
    def get_dic_of_pe_vs_addr(self):
        pe_dic = {}
        # Get list of PE's
        res = self.cv_HOST.host_run_command("ls /sys/bus/pci/devices/ | awk {'print $1'}")
        res = res.splitlines()
        for pe in res:
            if not pe:
                continue
            cmd = "cat /sys/bus/pci/devices/%s/eeh_pe_config_addr" % pe
            addr = self.cv_HOST.host_run_command(cmd)
            addr = addr.splitlines()
            pe_dic[pe] = ((addr[1]).split("x"))[1]
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
        con.sendline("\r\n")
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
        res = self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
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
        count = self.cv_IPMI.run_host_cmd_on_ipmi_console(cmd)
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
