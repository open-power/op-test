#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestInterrupt.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2020
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
OpTestInterrupt
---------------
This module contain testcases related to XIVE.
1.Enable kernel logging,basically generate console traffic 
by printing the processes/tasks to the console
2.check Xive is configured properly or not
3.check system reboot with xive=on and xive=off
4.validate interrupts handled by CPU's
'''
import os
import re
import sys
import time
import pexpect
import unittest
import subprocess

import OpTestConfiguration
from common import OpTestHMC, OpTestFSP
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.OpTestConstants import OpTestConstants as BMC_CONST

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestInterrupt(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.c = self.cv_SYSTEM.console
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
    
    def enable_consoletraffic(self):
        '''
        Enable kernel logging, basically generate console traffic by printing the 
        processes/tasks to the console
        '''
        self.c.run_command("echo 10 > /proc/sys/kernel/printk")
        try:
            i = 1
            while i <= 10: 
                self.c.run_command("echo t > /proc/sysrq-trigger", timeout=600)
                i = i+1
        except(KernelOOPS, KernelKdump):
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c.run_command("echo $?")

class XiveTest(OpTestInterrupt):
    '''
    1.This function will check xive is configured properly or not
    2.check for system reboot with Xive=off and on
    '''
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.con.run_command("uname -a")
        result = self.con.run_command("grep -i --color=never xive /boot/config-`uname -r`")
        for line in result:
            temp = ''.join(self.con.run_command("echo %s | cut -d '=' -f 2" % line))
            if temp != 'y':
                self.fail("xive is not configured properly")
        res = self.con.run_command("cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.con.run_command_ignore_fail("sed -i -e 's/xive=.* / /' -e 's/xive=.*/\"/' /etc/default/grub")
            self.con.run_command("sed -i '/GRUB_CMDLINE_LINUX_DEFAULT/s/\"$/ xive=off\"/' /etc/default/grub")
            self.sles_grub_update()
            self.con.run_command("sed -i 's/xive=.*/xive=on\"/' /etc/default/grub")
            self.sles_grub_update()
        elif 'Red Hat' in res[0].strip():
            self.rhel_grub_update('off')
            self.rhel_grub_update('on')
    
    def sles_grub_update(self):
        self.con.run_command("grub2-mkconfig -o /boot/grub2/grub.cfg")
        self.con.run_command("sync;sleep 10")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.con.run_command("cat /proc/cmdline")

    def rhel_grub_update(self, param):
        '''
        This function will pass xive=on and off parameters to command line
        '''
        self.con.run_command("grubby --info=/boot/vmlinuz-`uname -r`")
        self.con.run_command_ignore_fail("grubby --remove-args=xive* --update-kernel=/boot/vmlinuz-`uname -r`")
        self.con.run_command("grubby --args=xive=%s --update-kernel=/boot/vmlinuz-`uname -r`" % param)
        self.con.run_command("sync; sync; sleep 5")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.con.run_command("grubby --info=/boot/vmlinuz-`uname -r`")

    def interrupt_cpu_check(self): 
        '''
        This function will validate interrupts handled by CPU's.
        '''
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        res = self.con.run_command("ip route list | grep default | awk '{print $5}'")
        interrupt = "cat /proc/interrupts | grep %s | head -1" % res[0]
        self.con.run_command(interrupt)
        self.con.run_command("ppc64_cpu --cores-on")
        self.con.run_command("ppc64_cpu --cores-on=1")
        self.con.run_command(interrupt)
        temp = "%s | awk '{print $2}'" % interrupt
        self.con.run_command("ppc64_cpu --smt=off")
        tmp1 = self.con.run_command(temp)
        time.sleep(10)
        tmp2 = self.con.run_command(temp)
        if (tmp1[0] < tmp2[0]):
            log.info("Interrupts are handled by CPU0")
            self.con.run_command("ppc64_cpu --cores-on=all")
            self.con.run_command("ppc64_cpu --smt=on")
            output = self.con.run_command(interrupt)
            cmd = "%s | awk '{print $4}'" % interrupt
            tmp3 = self.con.run_command(cmd)
            smp = "%s | awk '{print $1}'" % interrupt
            result = self.con.run_command(smp)
            log.info("setting smp_affinity_list to CPU2")
            self.con.run_command("echo 2 > /proc/irq/%s/smp_affinity_list" % result[0].lstrip().split(':')[0])
            self.con.run_command(interrupt)
            time.sleep(10)
            tmp4 = self.con.run_command(cmd)
            if (tmp3[0] < tmp4[0]):
                log.info("Interrupts are handled by CPU2")
            else:
                self.fail("Interrupts are not handled by CPU2")
        else:
            self.fail("Interrupts are not handled by CPU")

    def runTest(self):
        self.setup_test()
        self.enable_consoletraffic()
        self.interrupt_cpu_check()
 
