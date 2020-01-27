#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestKdump.py $
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
This module contain testcases related to Kdump.
TODO: Add fadump, ubuntu and LPAR support.
'''
import os
import time
import pexpect
import unittest
import OpTestConfiguration
from common import OpTestHMC, OpTestFSP
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import KernelOOPS, KernelKdump
import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestKernelKdump(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.console = self.cv_SYSTEM.console
        self.stress_file = "stress-ng-0.09.58"
        self.server_ip = "x.x.x.x"
        self.server_pw = "xxxx"
        self.net_path = "/var/crash_net"
    
    def kernel_crash(self, crash_type, dump_place):
        '''
        This function will test the kdump followed by system
        reboot. it has below steps

        1. Remove files under /var/crash.
        2. Trigger kernel crash: ``echo c > /proc/sysrq-trigger``
        '''
        self.console.run_command("rm -rf /var/crash/*")
        if dump_place == "net":
            self.console.run_command('ssh root@%s "mkdir -p %s"' % (self.server_ip, self.net_path))
            self.console.run_command('ssh root@%s "rm -rf %s/*"' % (self.server_ip, self.net_path))
        self.console.run_command("ppc64_cpu --smt")
        time.sleep(5)
        self.console.run_command("echo 1 > /proc/sys/kernel/sysrq")
        if crash_type == "manual":
            self.console.pty.sendline("echo c > /proc/sysrq-trigger")
            done = False
            rc = -1
            while not done:
                try:
                    rc = self.console.pty.expect(['ISTEP', "kdump: saving vmcore complete"], timeout=300)
                except KernelOOPS:
                    self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                except KernelKdump:
                    log.info("Kdump kernel started booting, waiting for dump to finish")
                if rc == 0:
                    self.cv_SYSTEM.set_state(OpSystemState.IPLing)
                    done = True
                if rc == 1:
                    log.info("Kdump finished collecting vmcore")
                    done = True
        if crash_type == "hmc":
            self.dumprestart_lpar()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def vmcore_check(self, dump_place, file_list=[]):
        '''
        This function validates the vmcore captured.
        It has below steps.

        1. Check for vmcore and dmesg.txt captured under /var/crash.
        2. Run crash tool on captured vmcore.
        '''
        time.sleep(5)
        if dump_place == "net":
            self.console.run_command('scp -r root@%s:/%s/* /var/crash/' % (self.server_ip, self.net_path), timeout=600)
            self.console.run_command('ssh root@%s "rm -rf /%s/*"' % (self.server_ip, self.net_path))
        res = self.console.run_command('ls -1 /var/crash')
        path_crash_dir = os.path.join("/var/crash", res[0])
        if dump_place == "local":
            if self.distro == 'SLES':
                file_list = ['vmcore','dmesg.txt']
            if self.distro == 'RHEL':
                file_list = ['vmcore','vmcore-dmesg.txt']
        if self.distro == 'SLES':
            crash_cmd = 'crash vmcore vmlinux* -i file'
        if self.distro == 'RHEL':
            crash_cmd = 'crash /usr/lib/debug/lib/modules/`uname -r`/vmlinux %s -i file' % file_list[0]
        res = self.console.run_command('ls -1 %s' % path_crash_dir)
        for files in file_list:
            if files not in res:
                self.fail(" %s is not saved " % files)
            else:
                log.info(" %s is saved " % files)
        self.console.run_command("cd %s" % path_crash_dir)
        self.console.run_command('echo -e "bt\\nbt -a\\nalias\\nascii\\nfiles\\nmount\\nps\\nq" > file')
        self.console.run_command(crash_cmd, timeout=600)
        time.sleep(5)
        self.console.run_command("rm -rf /var/crash/*")

    def run_workload(self):
        if self.distro == 'SLES':
            self.console.run_command("zypper install -y wget gcc make")
        if self.distro == 'RHEL':
            self.console.run_command("yum install -y wget gcc make")
        self.console.run_command("cd /root")
        self.console.run_command("wget https://kernel.ubuntu.com/~cking/tarballs/stress-ng/%s.tar.xz" % self.stress_file)
        self.console.run_command("tar -xf %s.tar.xz" % self.stress_file)
        self.console.run_command("cd %s/" % self.stress_file)
        self.console.run_command("make", timeout=600)
        self.console.run_command("make install")
        self.console.run_command("nohup stress-ng --sequential 0 --timeout 60&", timeout=600)
        time.sleep(10)

    def setup_ssh(self):
        if self.distro == 'SLES':
            self.console.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"ssh:\/\/root:%s@%s\/%s\"\' /etc/sysconfig/kdump;' % (self.server_pw, self.server_ip, self.net_path))
            self.console.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
            time.sleep(5)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        elif self.distro == 'RHEL':
            self.console.run_command("cp -f /etc/kdump.conf /etc/kdump.conf_bck")
            self.console.run_command("sed -i '/ssh user@my.server.com/c\ssh root@%s' /etc/kdump.conf" % self.server_ip)
            self.console.run_command("sed -i '/sshkey \/root\/.ssh\/kdump_id_rsa/c\sshkey \/root\/.ssh\/id_rsa' /etc/kdump.conf")
            self.console.run_command("sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf;")
            self.console.run_command("sed -i '/path \/var\/crash/c\path %s' /etc/kdump.conf;" % self.net_path)
            self.console.run_command("cd /root; kdumpctl restart", timeout=600)
            self.console.run_command("mv -f /etc/kdump.conf_bck /etc/kdump.conf")
        res = self.console.run_command("service kdump status | grep active")
        if 'exited' not in res[0].strip():
            log.info("Kdump service is not configured properly")

    def setup_nfs(self):
        if self.distro == 'SLES':
            self.console.run_command('sed -i \'/^KDUMP_SAVEDIR=/c\KDUMP_SAVEDIR=\"nfs:\/\/%s\%s\"\' /etc/sysconfig/kdump;' % (self.server_ip, self.net_path))
            self.console.run_command("zypper install -y nfs*")
            self.console.run_command("service nfs start")
            self.console.run_command("mount -t nfs %s:%s /var/crash" % (self.server_ip, self.net_path))
            self.console.run_command("touch /etc/sysconfig/kdump; systemctl restart kdump.service; sync", timeout=600)
            time.sleep(5)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
        elif self.distro == 'RHEL':
            self.console.run_command("cp -f /etc/kdump.conf /etc/kdump.conf_bck")
            self.console.run_command("yum -y install nfs-utils")
            self.console.run_command("service nfs-server start")
            self.console.run_command("echo 'nfs %s:%s' >> /etc/kdump.conf;" % (self.server_ip, self.net_path))
            self.console.run_command("sed -i 's/-l --message-level/-l -F --message-level/' /etc/kdump.conf;")
            self.console.run_command("sed -i '/path \/var\/crash/c\path \/' /etc/kdump.conf;")
            self.console.run_command("mount -t nfs %s:%s /var/crash" % (self.server_ip, self.net_path))
            self.console.run_command("cd /root; kdumpctl restart", timeout=600)
            self.console.run_command("mv -f /etc/kdump.conf_bck /etc/kdump.conf")
        res = self.console.run_command("service kdump status | grep active")
        if 'exited' not in res[0].strip():
            log.info("Kdump service is not configured properly")

class KernelCrash_Kdump(OpTestKernelKdump):
    '''
    This function will configure kdump. It has below steps.

    1. Update crashkernel value, rebuild the grub and reboot the machine.
    2. Install debuginfo packages.
    3. Check for kdump service status.
    '''
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console.run_command("uname -a")
        self.console.run_command("cat /etc/os-release")
        res = self.console.run_command("cat /etc/os-release | grep NAME | head -1")
        if 'SLES' in res[0].strip():
            self.distro = 'SLES'
            self.console.run_command("zypper install -y crash")
            self.console.run_command("zypper install -y kernel-default-debuginfo", timeout=600)
            self.console.run_command("sed -i 's/crashkernel=[0-9]\+M/crashkernel=2G-64G:1024M,64G-128G:2048M,128G-:4096M/' /etc/default/grub;")
            self.console.run_command("grub2-mkconfig -o /boot/grub2/grub.cfg")
            self.console.run_command("sync")
            time.sleep(5)
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.console.run_command("cat /proc/cmdline")
        elif 'Red Hat' in res[0].strip():
            self.distro = 'RHEL'
            self.console.run_command("yum install -y crash")
            self.console.run_command("yum install -y kernel-debuginfo")
        else:
            self.skipTest("Currently test is supported only on sles and rhel")
        res = self.console.run_command("service kdump status | grep active")
        if 'exited' not in res[0].strip():
            log.info("Kdump service is not configured properly")

    def runTest(self):
        self.setup_test()
        log.info("=============== Testing local kdump ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.console.run_command("ppc64_cpu --smt=off")
        log.info("=============== Testing kdump with smt=off ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.console.run_command("ppc64_cpu --smt=2")
        log.info("=============== Testing kdump with smt=2 ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.console.run_command("ppc64_cpu --smt=4")
        log.info("=============== Testing kdump with smt=4 ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.console.run_command("ppc64_cpu --cores-on=1")
        log.info("=============== Testing kdump with single cpu online ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.console.run_command("ppc64_cpu --cores-on=1")
        self.console.run_command("ppc64_cpu --smt=off")
        log.info("=============== Testing kdump with single cpu online and smt=off ===============")
        self.kernel_crash("manual", "local")
        self.vmcore_check("local")
        self.setup_ssh()
        log.info("=============== Testing kdump over ssh ===============")
        self.kernel_crash("manual", "net")
        if self.distro == 'SLES':
            self.vmcore_check("net", ['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check("net", ['vmcore.flat','vmcore-dmesg.txt'])
        self.setup_nfs()
        log.info("=============== Testing fadump over nfs ===============")
        self.kernel_crash("manual", "net")
        if self.distro == 'SLES':
            self.vmcore_check("net", ['vmcore','dmesg.txt'])
        if self.distro == 'RHEL':
            self.vmcore_check("net", ['vmcore','vmcore-dmesg.txt'])

def crash_suite():
    s = unittest.TestSuite()
    s.addTest(KernelCrash_Kdump())
    return s
