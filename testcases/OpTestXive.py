#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestXive.py $
#
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
# IBM_PROLOG_END_TAG

'''
OpTestXive
------------

This module contain testcases related to XIVE.

1.check for there are no xive related
errors in dmesg log
2.Enable kernel logging, basically generate traffic
3.Enable console traffic by printing the 
processes/tasks to the console
4.check Xive is configured properly or not
5.check system rebbot with xive=on
6.check system reboot with xive=off
7.validate interrupts handled by CPU's
'''
import time
import subprocess
import commands
import re
import sys
import pexpect
import os
import time


from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common import OpTestHMC

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState

class OpTestXive(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.cv_HMC = self.cv_SYSTEM.hmc

    def xive_test(self):
        '''
        This function will check for 
        1.Make sure no errors in dmesg log
        2.Enable kernel logging, basically generate traffic
        3.Enable console traffic by printing the 
        processes/tasks to the console
        '''
    	self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "dmesg -T --level=alert,crit,err,warn | grep -i xive")
        self.cv_HMC.vterm_run_command(self.console, "dmesg -T --level=alert,crit,err,warn | grep -i irq")
        self.cv_HMC.vterm_run_command(self.console, "echo 10 > /proc/sys/kernel/printk")
        i = 1
        while i <= 20: 
        	self.cv_HMC.vterm_run_command(self.console, "echo t > /proc/sysrq-trigger")
		i = i+1
        self.cv_HMC.vterm_run_command(self.console, "echo $?")

class XiveTesting(OpTestXive):
    '''
    1.This function will check xive is configured properly or not
    2.check for system reboot with Xive=off
    3.check for system reboot with Xive=on
    '''
    def setup_test(self):
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "uname -a")
        result = self.cv_HMC.vterm_run_command(self.console, "grep -i --color=never xive /boot/config-`uname -r`")
        print result
        for line in result:
           temp = ''.join(self.cv_HMC.vterm_run_command(self.console, "echo %s | cut -d '=' -f 2" % line))
           if(temp != 'y'):
               self.fail("xive is not configured properly")
        res = self.cv_HMC.vterm_run_command(self.console, "cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.distro = 'SLES'
            self.cv_HMC.vterm_run_command(self.console, "cat /etc/default/grub|grep xive")
            self.cv_HMC.vterm_run_command(self.console, "sed -i '/xive=/c\GRUB_CMDLINE_LINUX_DEFAULT=\"xive=off\"' /etc/default/grub")
            self.cv_HMC.vterm_run_command(self.console, "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.cv_HMC.vterm_run_command(self.console, "cat /etc/default/grub | grep xive")
            self.cv_HMC.vterm_run_command(self.console, "cat /boot/grub2/grub.cfg | grep xive")
            self.cv_HMC.vterm_run_command(self.console, "sync;sleep 10")
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password="passw0rd")
            self.console = self.cv_HMC.get_console()
            self.cv_HMC.vterm_run_command(self.console, "which stty && stty cols 300; which stty && stty rows 30;")
            self.cv_HMC.vterm_run_command(self.console, "cat /proc/cmdline")
            self.cv_HMC.vterm_run_command(self.console,"cat /proc/interrupts | grep -Eai 'xive'")
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=\"xive=off\"/GRUB_CMDLINE_LINUX_DEFAULT=\"xive=on\"/' /etc/default/grub")
            self.cv_HMC.vterm_run_command(self.console, "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.cv_HMC.vterm_run_command(self.console, "cat /etc/default/grub | grep xive")
            self.cv_HMC.vterm_run_command(self.console, "sync;sleep 10")
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password="passw0rd")
            self.console = self.cv_HMC.get_console()
            self.cv_HMC.vterm_run_command(self.console, "which stty && stty cols 300; which stty && stty rows 30;")
            self.cv_HMC.vterm_run_command(self.console, "cat /proc/cmdline")
            self.cv_HMC.vterm_run_command(self.console,"cat /proc/interrupts | grep -Eai 'xive'")
        elif 'Red Hat' in res[0].strip():
            self.distro = 'RHEL'
            self.cv_HMC.vterm_run_command(self.console, "which stty && stty cols 300; which stty && stty rows 30;")
            self.cv_HMC.vterm_run_command(self.console, "grubby --info=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "grubby --remove-args=xive* --update-kernel=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "grubby --info=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "grubby --args=xive=off --update-kernel=/boot/vmlinuz-`uname -r`")
            time.sleep(5)
            self.cv_HMC.vterm_run_command(self.console, "sync; sync;")
            time.sleep(5)
            self.cv_HMC.vterm_run_command(self.console, "grubby --info=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password="passw0rd")
            self.console = self.cv_HMC.get_console()
            self.cv_HMC.vterm_run_command(self.console, "which stty && stty cols 300; which stty && stty rows 30;")
            self.cv_HMC.vterm_run_command(self.console,"cat /proc/interrupts | grep -Eai 'xive'")
            self.cv_HMC.vterm_run_command(self.console, "grubby --info=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "grubby --remove-args=xive* --update-kernel=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "sync;sleep 10")
            self.cv_HMC.vterm_run_command(self.console, "grubby --args=xive=on --update-kernel=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "sleep 5; sync; sleep 5;")
            self.cv_HMC.vterm_run_command(self.console, "grubby --info=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password="passw0rd")
            self.console = self.cv_HMC.get_console()
            self.cv_HMC.vterm_run_command(self.console,"cat /proc/interrupts | grep -Eai 'xive'")

    def xive_cpu_check(self): 
        '''
        This function will validate interrupts handled by CPU's.
        Make sure while running this function xive should be on
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "which stty && stty cols 300; which stty && stty rows 30;")
        res = self.cv_HMC.vterm_run_command(self.console, "ip route list | grep default | awk '{print $5}'")
        self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts") 
        self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
        time.sleep(2)
        self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
        time.sleep(2)
        self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        tmp1 = self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s | awk '{print $2}'" % res[0])
        time.sleep(2)
        tmp2 = self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s | awk '{print $2}'" % res[0])
        if (tmp1[0]<tmp2[0]):
            print "Interrupts are handled by CPU0"
            self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=all")
            self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=on")
            self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
            time.sleep(2)
            self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
            tmp3 = self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s | awk '{print $4}'" % res[0])
            result = self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s | awk '{print $1}' | cut -d ':' -f 1" % res[0])
            print result
            self.cv_HMC.vterm_run_command(self.console, "cd /proc/irq/%s" % result[0])
            self.cv_HMC.vterm_run_command(self.console, "cat smp_affinity_list")
            print "setting smp_affinity_list to CPU2"
            self.cv_HMC.vterm_run_command(self.console, "echo 2 > smp_affinity_list")
            self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s" % res[0])
            tmp4 = self.cv_HMC.vterm_run_command(self.console, "cat /proc/interrupts | grep %s | awk '{print $4}'" % res[0])
            if (tmp3[0]<tmp4[0]):
                print "Interrupts are handled by CPU2"
            else:
                self.fail("Interrupts are not handled by CPU2")
        else:
            self.fail("Interrupts are not handled by CPU")

    def runTest(self):
        self.setup_test()
        self.xive_test()
        self.xive_cpu_check()
 
def crash_suite():
    s = unittest.TestSuite()
    s.addTest(XiveTesting())
    return s
