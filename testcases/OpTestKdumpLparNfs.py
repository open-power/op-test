#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestKernel.py $
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
OpTestKdump
------------

This module contains testcases related to Kdump.

Please install crash and kernel-default-debuginfo packages on the target machine where kdump is tested.
Password less authentication should be set between kdump machine and nfs server
Nfs server should have NFS path

1. ssh-keygen -t rsa
2. cat /root/.ssh/id_rsa.pub | ssh root@<ssh_server_ip> "cat - >> /root/.ssh/authorized_keys"

1. Configure kdump.
2. Trigger crash.
3. Check for vmcore and dmesg.txt.
4. Run crash tool on the vmcore captured.
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
from common.Exceptions import KernelOOPS, KernelKdump

class OpTestKernelBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.host_password = conf.args.host_password
        self.server_ip = "x.x.x.x"
        self.nfs_path = "/home/mnt/testarea/nfs"

    def kernel_crash(self):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps

        1. Create directory given in nfs path.
        2. Trigger kernel crash: ``echo c > /proc/sysrq-trigger``
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "mkdir -p /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "mv /var/crash/* /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, 'ssh root@%s "mkdir -p %s_bck"' % (self.server_ip, self.nfs_path))
        self.cv_HMC.vterm_run_command(self.console, 'ssh root@%s "mv %s/* %s_bck"' % (self.server_ip, self.nfs_path, self.nfs_path))
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt")
        time.sleep(5)
        self.cv_HMC.vterm_run_command(self.console, "echo 1 > /proc/sys/kernel/sysrq")
        try:
            self.cv_HMC.vterm_run_command(self.console, "echo c > /proc/sysrq-trigger")
        except (KernelOOPS, KernelKdump):
            self.cv_HMC.wait_login_prompt(self.console, username="root", password=self.host_password)

    def vmcore_check(self):
        '''
        This function validates the vmcore captured.
        It has below steps.

        1. Check for vmcore and dmesg.txt captured under /var/crash.
        2. Run crash tool on captured vmcore.
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, 'scp -r root@%s:%s/* /var/crash/' % (self.server_ip, self.nfs_path), timeout=600)
        res = self.cv_HMC.vterm_run_command(self.console, 'ls -1 /var/crash')
        path_crash_dir = os.path.join("/var/crash", res[0])
        if self.distro == 'SLES':
            file_list = ['vmcore','dmesg.txt']
            crash_cmd = 'crash vmcore vmlinux* -i file'
        if self.distro == 'RHEL':
            file_list = ['vmcore.flat','vmcore-dmesg.txt']
            crash_cmd = 'crash /usr/lib/debug/lib/modules/`uname -r`/vmlinux vmcore -i file'
        res = self.cv_HMC.vterm_run_command(self.console, 'ls -1 %s' % path_crash_dir)
        for files in file_list:
            if files not in res:
                self.fail(" %s is not saved " % files)
            else:
                print(" %s is saved " % files)
        self.cv_HMC.vterm_run_command(self.console, "cd %s" % path_crash_dir)
        self.cv_HMC.vterm_run_command(self.console, 'echo -e "bt\\nbt -a\\nalias\\nascii\\nfiles\\nmount\\nps\\nq" > file')
        self.cv_HMC.vterm_run_command(self.console, crash_cmd, timeout=600)
        self.cv_HMC.vterm_run_command(self.console, "rm -rf /var/crash/*")
        print ("========== Please note that all the dumps under /var/crash are moved to /var/crash_bck ===========")

class KernelCrash_Kdump(OpTestKernelBase):
    '''
    This function will configure kdump. It has below steps.

    1. Update crashkernel value, rebuild the grub and reboot the machine.
    2. Configure kdump over nfs.
    '''

    def setup_test(self):
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.restart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, username="root", password=self.host_password)
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "uname -a")
        res = self.cv_HMC.vterm_run_command(self.console, "cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.distro = 'SLES'
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/crashkernel=[0-9]\+M/crashkernel=2G-64G:1024M,64G-128G:2048M,128G-:4096M/' /etc/default/grub")
            self.cv_HMC.vterm_run_command(self.console, "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password=self.host_password)
            self.console = self.cv_HMC.get_console()
            self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"nfs:\/\/%s\%s\"\' /etc/sysconfig/kdump;' % (self.server_ip, self.nfs_path))
            self.cv_HMC.vterm_run_command(self.console, "zypper install -y nfs*")
            self.cv_HMC.vterm_run_command(self.console, "service nfs start")
            self.cv_HMC.vterm_run_command(self.console, "mount -t nfs %s:%s /var/crash" % (self.server_ip, self.nfs_path))
            self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, username="root", password=self.host_password)
            self.console = self.cv_HMC.get_console()
        elif 'Red Hat' in res[0].strip():
            self.distro = 'RHEL'
            self.cv_HMC.vterm_run_command(self.console, "cp /etc/kdump.conf /etc/kdump.conf_bck")
            self.cv_HMC.vterm_run_command(self.console, "yum -y install nfs-utils")
            self.cv_HMC.vterm_run_command(self.console, "service nfs-server start")
            self.cv_HMC.vterm_run_command(self.console, "echo 'nfs %s:%s' >> /etc/kdump.conf;" % (self.server_ip, self.nfs_path))
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf;")
            self.cv_HMC.vterm_run_command(self.console, "mount -t nfs %s:%s /var/crash" % (self.server_ip, self.nfs_path))
            self.cv_HMC.vterm_run_command(self.console, "kdumpctl restart")
            self.cv_HMC.vterm_run_command(self.console, "rm -rf /etc/kdump.conf")
            self.cv_HMC.vterm_run_command(self.console, "mv /etc/kdump.conf_bck /etc/kdump.conf")
        else:
            self.skipTest("Currently test is supported only on sles and rhel")
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

    def runTest(self):
        self.setup_test()
        self.kernel_crash()
        self.vmcore_check()

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_Kdump())
    return s
