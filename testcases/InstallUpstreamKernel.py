#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

import unittest
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestInstallUtil import InstallUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class InstallUpstreamKernel(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.repo = self.conf.args.git_repo
        self.branch = self.conf.args.git_branch
        self.home = self.conf.args.git_home
        self.config = self.conf.args.git_repoconfig
        self.config_path = self.conf.args.git_repoconfigpath
        self.disk = self.conf.args.host_scratch_disk
        self.patch = self.conf.args.git_patch
        self.use_kexec = self.conf.args.use_kexec
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        if self.config_path:
            self.config = "olddefconfig"
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")
        if self.disk:
            OpIU = InstallUtil()
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            log.debug("Set given disk as default bootable disk")
            OpIU.set_bootable_disk(self.disk)
        self.console_thread = OpSOLMonitorThread(1, "console")

    def runTest(self):
        def is_url(path):
            '''
            param path: path to download
            return: boolean True if given path is url False Otherwise
            '''
            valid_schemes = ['http', 'https', 'git', 'ftp']
            if urlparse(path).scheme in valid_schemes:
                return True
            return False
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console_thread.start()
        try:
            con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            try:
                onlinecpus = int(con.run_command(
                    "lscpu --online -e|wc -l")[-1])
            except Exception:
                onlinecpus = 20
            log.debug("Downloading linux kernel")
            # Compile and install given kernel
            linux_path = os.path.join(self.home, "linux")
            con.run_command("[ -d %s ] || mkdir -p %s" %
                            (self.home, self.home))
            con.run_command("if [ -d %s ];then rm -rf %s;fi" %
                            (linux_path, linux_path), timeout=120)
            con.run_command("cd %s && git clone --depth 1  %s -b %s linux" %
                            (self.home, self.repo, self.branch), timeout=self.host_cmd_timeout)
            con.run_command("cd %s" % linux_path)
            if self.patch:
                patch_file = self.patch.split("/")[-1]
                if is_url(self.patch):
                    con.run_command("wget %s -O %s" % (self.patch, patch_file))
                else:
                    self.cv_HOST.copy_test_file_to_host(
                        self.patch, dstdir=linux_path)
                log.debug("Applying given patch")
                con.run_command("git am %s" %
                                os.path.join(linux_path, patch_file))
            log.debug("Downloading linux kernel config")
            if self.config_path:
                if is_url(self.config_path):
                    con.run_command("wget %s -O .config" % self.config_path)
                else:
                    self.cv_HOST.copy_test_file_to_host(
                        self.config_path, sourcedir="", dstdir=os.path.join(linux_path, ".config"))
            con.run_command("make %s" % self.config)
            log.debug("Compile and install linux kernel")
            con.run_command("make -j %d -s && make modules && make modules_install && make install" %
                            onlinecpus, timeout=self.host_cmd_timeout)
            if not self.use_kexec:
                # FIXME: Handle distributions which do not support grub
                con.run_command(
                    "grub2-mkconfig  --output=/boot/grub2/grub.cfg")
                con.run_command(
                    'grub2-set-default /boot/vmlinu*-`cat include/config/kernel.release 2> /dev/null`')
                log.debug("Rebooting after kernel install...")
                self.console_thread.console_terminate()
                con.close()
                self.cv_SYSTEM.goto_state(OpSystemState.OFF)
                self.cv_SYSTEM.goto_state(OpSystemState.OS)
            else:
                self.console_thread.console_terminate()
                cmdline = con.run_command("cat /proc/cmdline")[-1]
                if self.append_kernel_cmdline:
                    cmdline += " %s" % self.append_kernel_cmdline
                kern_rel_str = con.run_command(
                    "cat %s/include/config/kernel.release" % linux_path)[-1]
                try:
                    initrd_file = con.run_command(
                        "ls -l /boot/initr*-%s.img" % kern_rel_str)[-1].split(" ")[-1]
                except Exception:
                    initrd_file = con.run_command(
                        "ls -l /boot/initr*-%s" % kern_rel_str)[-1].split(" ")[-1]
                kexec_cmdline = "kexec --initrd %s --command-line=\"%s\" /boot/vmlinu*-%s -l" % (
                    initrd_file, cmdline, kern_rel_str)
                # Let's makesure we set the default boot index to current kernel
                # to avoid leaving host in unstable state incase boot failure
                con.run_command(
                    'grub2-set-default /boot/vmlinu*-`uname -r 2> /dev/null`')
                con.run_command(kexec_cmdline)
                con.close()
                raw_pty = self.cv_SYSTEM.console.get_console()
                raw_pty.sendline("reboot")
                raw_pty.expect("login:", timeout=600)
            con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            res = con.run_command("uname -r")
            log.info("Installed upstream kernel version: %s", res[-1])
            if self.conf.args.host_cmd:
                con.run_command(self.conf.args.host_cmd,
                                timeout=self.host_cmd_timeout)
            self.cv_HOST.host_gather_opal_msg_log()
            self.cv_HOST.host_gather_kernel_log()
        finally:
            if self.console_thread.isAlive():
                self.console_thread.console_terminate()
