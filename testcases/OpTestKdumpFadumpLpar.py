#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestKdumpLparSmt.py $
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

This module can contain testcases related to Kdump and FAadump.

Password less authentication should be setup between kdump machine and dump server

1. ssh-keygen -t rsa
2. cat /root/.ssh/id_rsa.pub | ssh root@<ssh_server_ip> "cat - >> /root/.ssh/authorized_keys"

1. Configure kdump and fadump.
2. Trigger crash.
3. Check for vmcore and dmesg.txt.
4. Run crash tool on the vmcore captured.
5. Repeat Step3 to Step4 for different SMT levels and different dump targets.
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
        self.host_user = conf.args.host_user
        self.host_password = conf.args.host_password
        self.stress_file = "stress-ng-0.09.58"
        self.server_ip = "9.40.192.198"
        self.server_pw = "passw0rd"
        self.net_path = "/var/crash_net"

    def kernel_crash(self):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps

        1. Take backup of files under /var/crash.
        2. Trigger kernel crash: ``echo c > /proc/sysrq-trigger``
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "mkdir -p /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "mv /var/crash/* /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt")
        time.sleep(5)
        self.cv_HMC.vterm_run_command(self.console, "echo 1 > /proc/sys/kernel/sysrq")
        try:
            self.cv_HMC.vterm_run_command(self.console, "echo c > /proc/sysrq-trigger")
        except (KernelOOPS, KernelKdump):
            self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)

    def kernel_crash_hmc(self):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps

        1. Take backup of files under /var/crash.
        2. Trigger kernel crash from HMC
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "mkdir -p /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "mv /var/crash/* /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt")
        time.sleep(5)
        self.cv_HMC.vterm_run_command(self.console, "echo 1 > /proc/sys/kernel/sysrq")
        self.cv_HMC.dumprestart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)

    def kernel_crash_net(self):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps

        1. Create directory given in net_path.
        2. Trigger kernel crash: "echo c > /proc/sysrq-trigger"
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "mkdir -p /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, "mv /var/crash/* /var/crash_bck/")
        self.cv_HMC.vterm_run_command(self.console, 'ssh root@%s "mkdir -p %s"' % (self.server_ip, self.net_path))
        self.cv_HMC.vterm_run_command(self.console, 'ssh root@%s "mv %s/* %s_bck"' % (self.server_ip, self.net_path, self.net_path))
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt")
        time.sleep(5)
        self.cv_HMC.vterm_run_command(self.console, "echo 1 > /proc/sys/kernel/sysrq")
        try:
            self.cv_HMC.vterm_run_command(self.console, "echo c > /proc/sysrq-trigger")
        except (KernelOOPS, KernelKdump):
            self.cv_HMC.wait_login_prompt(self.console, username=self.host_user, password=self.host_password)

    def vmcore_check(self):
        '''
        This function validates the vmcore captured.
        It has below steps.

        1. Check for vmcore and dmesg.txt captured under /var/crash.
        2. Run crash tool on captured vmcore.
        '''
        self.console = self.cv_HMC.get_console()
        time.sleep(40)
        res = self.cv_HMC.vterm_run_command(self.console, 'ls -1 /var/crash')
        path_crash_dir = os.path.join("/var/crash", res[0])
        if self.distro == 'SLES':
            file_list = ['vmcore','dmesg.txt']
            crash_cmd = 'crash vmcore vmlinux* -i file'
        if self.distro == 'RHEL':
            file_list = ['vmcore','vmcore-dmesg.txt']
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

    def vmcore_check_net(self, file_list):
        '''
        This function validates the vmcore captured.
        It has below steps.

        1. Check for vmcore and dmesg.txt captured under /var/crash.
        2. Copy the files from remote machine.
        3. Run crash tool on captured vmcore.
        '''
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, 'scp -r root@%s:/%s/* /var/crash/' % (self.server_ip, self.net_path))
        self.cv_HMC.vterm_run_command(self.console, 'ssh root@%s "rm -rf /%s/*"' % (self.server_ip, self.net_path))
        res = self.cv_HMC.vterm_run_command(self.console, 'ls -1 /var/crash')
        path_crash_dir = os.path.join("/var/crash", res[0])
        if self.distro == 'SLES':
            crash_cmd = 'crash vmcore vmlinux* -i file'
        if self.distro == 'RHEL':
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

    def setup_fadump(self):
        self.console = self.cv_HMC.get_console()
        if self.distro == 'SLES':
            self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\/var\/crash\' /etc/sysconfig/kdump;')
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/KDUMP_FADUMP=\"no\"/KDUMP_FADUMP=\"yes\"/' /etc/sysconfig/kdump;")
            self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
        if self.distro == 'RHEL':
            self.cv_HMC.vterm_run_command(self.console, "grubby --args=\"fadump=on crashkernel=2G-128G:2048M,128G-:8192M\" --update-kernel=/boot/vmlinuz-`uname -r`")
            self.cv_HMC.vterm_run_command(self.console, "sync; sync;")
            time.sleep(5)
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
            self.console = self.cv_HMC.get_console()
        self.cv_HMC.restart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
        self.console = self.cv_HMC.get_console()
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Fadump service is not configured properly"

    def run_workload(self):
        self.console = self.cv_HMC.get_console()
        if self.distro == 'SLES':
            self.cv_HMC.vterm_run_command(self.console, "zypper install -y wget gcc make")
        if self.distro == 'RHEL':
            self.cv_HMC.vterm_run_command(self.console, "yum install -y wget gcc make")
        self.cv_HMC.vterm_run_command(self.console, "wget https://kernel.ubuntu.com/~cking/tarballs/stress-ng/%s.tar.xz" % self.stress_file)
        self.cv_HMC.vterm_run_command(self.console, "tar -xf %s.tar.xz" % self.stress_file)
        self.cv_HMC.vterm_run_command(self.console, "cd %s/" % self.stress_file)
        self.cv_HMC.vterm_run_command(self.console, "make", timeout=600)
        self.cv_HMC.vterm_run_command(self.console, "make install")
        self.cv_HMC.vterm_run_command(self.console, "nohup stress-ng --sequential 0 --timeout 60&")
        time.sleep(600)

    def setup_ssh(self):
        if self.distro == 'SLES':
            self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"ssh:\/\/root:%s@%s\/%s\"\' /etc/sysconfig/kdump;' % (self.server_pw, self.server_ip, self.net_path))
            self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
            self.console = self.cv_HMC.get_console()
        elif self.distro == 'RHEL':
            self.cv_HMC.vterm_run_command(self.console, "cp -f /etc/kdump.conf /etc/kdump.conf_bck")
            self.cv_HMC.vterm_run_command(self.console, "sed -i '/ssh user@my.server.com/c\ssh root@%s' /etc/kdump.conf" % self.server_ip)
            self.cv_HMC.vterm_run_command(self.console, "sed -i '/sshkey \/root\/.ssh\/kdump_id_rsa/c\sshkey \/root\/.ssh\/id_rsa' /etc/kdump.conf")
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf;")
            self.cv_HMC.vterm_run_command(self.console, "sed -i '/path \/var\/crash/c\path %s' /etc/kdump.conf;" % self.net_path)
            self.cv_HMC.vterm_run_command(self.console, "kdumpctl restart")
            self.cv_HMC.vterm_run_command(self.console, "mv -f /etc/kdump.conf_bck /etc/kdump.conf")
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

    def setup_nfs(self):
        if self.distro == 'SLES':
            self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"nfs:\/\/%s\%s\"\' /etc/sysconfig/kdump;' % (self.server_ip, self.net_path))
            self.cv_HMC.vterm_run_command(self.console, "zypper install -y nfs*")
            self.cv_HMC.vterm_run_command(self.console, "service nfs start")
            self.cv_HMC.vterm_run_command(self.console, "mount -t nfs %s:%s /var/crash" % (self.server_ip, self.net_path))
            self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
            self.console = self.cv_HMC.get_console()
        elif self.distro == 'RHEL':
            self.cv_HMC.vterm_run_command(self.console, "cp -f /etc/kdump.conf /etc/kdump.conf_bck")
            self.cv_HMC.vterm_run_command(self.console, "yum -y install nfs-utils")
            self.cv_HMC.vterm_run_command(self.console, "service nfs-server start")
            self.cv_HMC.vterm_run_command(self.console, "echo 'nfs %s:%s' >> /etc/kdump.conf;" % (self.server_ip, self.net_path))
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf;")
            self.cv_HMC.vterm_run_command(self.console, "sed -i '/path \/var\/crash/c\path \/' /etc/kdump.conf;")
            self.cv_HMC.vterm_run_command(self.console, "mount -t nfs %s:%s /var/crash" % (self.server_ip, self.net_path))
            self.cv_HMC.vterm_run_command(self.console, "kdumpctl restart")
            self.cv_HMC.vterm_run_command(self.console, "cat /etc/kdump.conf")
            self.cv_HMC.vterm_run_command(self.console, "mv -f /etc/kdump.conf_bck /etc/kdump.conf")
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

    def setup_ftp(self):
        self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"ftp:\/\/root:%s@%s\/%s\"\' /etc/sysconfig/kdump;' % (self.server_pw, self.server_ip, self.net_path))
        self.cv_HMC.vterm_run_command(self.console, "zypper install -y lftp")
        self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
        self.cv_HMC.restart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
        self.console = self.cv_HMC.get_console()
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

    def setup_sftp(self):
        self.cv_HMC.vterm_run_command(self.console, 'sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"sftp:\/\/root:%s@%s\/%s\"\' /etc/sysconfig/kdump;' % (self.server_pw, self.server_ip, self.net_path))
        self.cv_HMC.vterm_run_command(self.console, "touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
        self.cv_HMC.restart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
        self.console = self.cv_HMC.get_console()
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

class KernelCrash_Kdump(OpTestKernelBase):
    '''
    This function will configure kdump. It has below steps.

    1. Update crashkernel value, rebuild the grub and reboot the machine.
    2. Run ffdc_validation script to check the configurations.
    '''
    def setup_test(self):
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.restart_lpar()
        self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
        self.console = self.cv_HMC.get_console()
        self.cv_HMC.vterm_run_command(self.console, "uname -a")
        res = self.cv_HMC.vterm_run_command(self.console, "cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.distro = 'SLES'
            self.cv_HMC.vterm_run_command(self.console, "zypper install -y crash")
            self.cv_HMC.vterm_run_command(self.console, "zypper install -y kernel-default-debuginfo", timeout=600)
            self.cv_HMC.vterm_run_command(self.console, "sed -i 's/crashkernel=[0-9]\+M/crashkernel=2G-64G:1024M,64G-128G:2048M,128G-:4096M/' /etc/default/grub;")
            self.cv_HMC.vterm_run_command(self.console, "grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.cv_HMC.vterm_run_command(self.console, "sync")
            time.sleep(5)
            self.cv_HMC.restart_lpar()
            self.cv_HMC.wait_login_prompt(self.console, self.host_user, password=self.host_password)
            self.console = self.cv_HMC.get_console()
        elif 'Red Hat' in res[0].strip():
            self.distro = 'RHEL'
            self.cv_HMC.vterm_run_command(self.console, "yum install -y crash")
            self.cv_HMC.vterm_run_command(self.console, "yum install -y kernel-debuginfo")
        else:
            self.skipTest("Currently test is supported only on sles and rhel")
        res = self.cv_HMC.vterm_run_command(self.console, "service kdump status | grep active")
        if 'exited' not in res[0].strip():
            print "Kdump service is not configured properly"

    def runTest(self):
        self.setup_test()
        print "=============== Testing local kdump ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing kdump with smt=off ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=2")
        print "=============== Testing kdump with smt=2 ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=4")
        print "=============== Testing kdump with smt=4 ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        print "=============== Testing kdump with single cpu online ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing kdump with single cpu online and smt=off ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.run_workload()
        print "=============== Testing local kdump with workload ==============="
        self.kernel_crash()
        self.vmcore_check()
        print "=============== Testing kdump with dump trigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing kdump with dump trigger from HMC and smt=off ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=2")
        print "=============== Testing kdump with dump trigger from HMC and smt=2 ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=4")
        print "=============== Testing kdump with dump trigger from HMC and smt=4 ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        print "=============== Testing kdump with single cpu online and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing kdump with single cpu online, smt=off and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.run_workload()
        print "=============== Testing local kdump with workload and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.setup_ssh()
        print "=============== Testing kdump over ssh ==============="
        self.kernel_crash_net()
        if self.distro == 'SLES':
            self.vmcore_check_net(['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check_net(['vmcore.flat','vmcore-dmesg.txt'])
        self.setup_nfs()
        print "=============== Testing kdump over nfs ==============="
        self.kernel_crash_net()
        if self.distro == 'SLES':
            self.vmcore_check_net(['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check_net(['vmcore','vmcore-dmesg.txt'])
        if self.distro == 'SLES':
            self.setup_ftp()
            print "=============== Testing kdump over ftp ==============="
            self.kernel_crash_net()
            self.vmcore_check_net(['vmcore','dmesg.txt'])
            self.setup_sftp()
            print "=============== Testing kdump over sftp ==============="
            self.kernel_crash_net()
            self.vmcore_check_net(['vmcore','dmesg.txt'])
        self.setup_fadump()
        print "=============== Testing local fadump ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing fadump with smt=off ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=2")
        print "=============== Testing fadump with smt=2 ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=4")
        print "=============== Testing fadump with smt=4 ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        print "=============== Testing fadump with single cpu online ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing fadump with single cpu online and smt=off ==============="
        self.kernel_crash()
        self.vmcore_check()
        self.run_workload()
        print "=============== Testing local fadump with workload ==============="
        self.kernel_crash()
        self.vmcore_check()
        print "=============== Testing fadump with dump trigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing fadump with dump trigger from HMC and smt=off ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=2")
        print "=============== Testing fadump with dump trigger from HMC and smt=2 ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=4")
        print "=============== Testing fadump with dump trigger from HMC and smt=4 ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        print "=============== Testing fadump with single cpu online and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --cores-on=1")
        self.cv_HMC.vterm_run_command(self.console, "ppc64_cpu --smt=off")
        print "=============== Testing fadump with single cpu online, smt=off and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.run_workload()
        print "=============== Testing local fadump with workload and dumptrigger from HMC ==============="
        self.kernel_crash_hmc()
        self.vmcore_check()
        self.setup_ssh()
        print "=============== Testing fadump over ssh ==============="
        self.kernel_crash_net()
        if self.distro == 'SLES':
            self.vmcore_check_net(['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check_net(['vmcore.flat','vmcore-dmesg.txt'])
        self.setup_nfs()
        print "=============== Testing fadump over nfs ==============="
        self.kernel_crash_net()
        if self.distro == 'SLES':
            self.vmcore_check_net(['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check_net(['vmcore','vmcore-dmesg.txt'])
        if self.distro == 'SLES':
            self.setup_ftp()
            print "=============== Testing fadump over ftp ==============="
            self.kernel_crash_net()
            self.vmcore_check_net(['vmcore','dmesg.txt'])
            self.setup_sftp()
            print "=============== Testing fadump over sftp ==============="
            self.kernel_crash_net()
            self.vmcore_check_net(['vmcore','dmesg.txt'])

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_Kdump())
    return s
