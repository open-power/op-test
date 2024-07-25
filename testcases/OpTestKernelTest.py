#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
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
# Author : Tejas Manhas <Tejas.Manhas@ibm.com>
# Co-Author : Abdul Haleem <abdhalee@linux.vnet.ibm.com>

import json
import OpTestConfiguration
import OpTestLogger
import os
import unittest
from urllib.parse import urlparse
import re
import subprocess
import sys
import time

from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.Exceptions import CommandFailed
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class KernelTest(unittest.TestCase):

    def setUp(self):
        """
        Set up the test environment.
        Initializes test parameters and checks required configurations.
        """
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.repo = self.conf.args.git_repo
        self.repo_reference = self.conf.args.git_repo_reference
        self.branch = self.conf.args.git_branch
        self.home = self.conf.args.git_home
        self.config_path = self.conf.args.git_repoconfigpath
        self.config = self.conf.args.git_repoconfig
        self.good_commit = self.conf.args.good_commit
        self.bad_commit = self.conf.args.bad_commit
        self.bisect_script = self.conf.args.bisect_script
        self.bisect_category = self.conf.args.bisect_category
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        self.linux_path = os.path.join(self.home, "linux")
        self.bisect_flag = self.conf.args.bisect_flag
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.host_distro_name = self.util.distro_name()
        self.console_thread = OpSOLMonitorThread(1, "console")
        # in case bisection see if we need powercycle not for build, but for boot
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console_thread.start()
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")

    def build_kernel(self):
        """
        Build and install the Linux kernel.
        """
        self.config_path = self.conf.args.git_repoconfigpath

        def is_url(path):
            '''
            param path: path to download
            return: boolean True if given path is url False Otherwise
            '''
            valid_schemes = ['http', 'https', 'git', 'ftp']
            if urlparse(path).scheme in valid_schemes:
                return True
            return False

        if self.config_path:
            if is_url(self.config_path):
                self.con.run_command("wget %s -O linux/.config" % self.config_path)
            else:
                self.cv_HOST.copy_test_file_to_host(self.config_path, sourcedir="", dstdir=os.path.join(linux_path, ".config"))
        self.con.run_command("cd linux && make olddefconfig")
        # the below part of the code is needed for only first run and will be decided bisect flag false
        ker_ver = self.con.run_command("make kernelrelease")[-1]
        sha = self.con.run_command("git rev-parse HEAD")
        tcommit = self.con.run_command("export 'TERM=xterm-256color';git show -s --format=%ci")
        tcommit = re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", tcommit[1])
        log.info("Upstream kernel version: %s", ker_ver)
        log.info("Upstream kernel commit-id: %s", sha[-1])
        log.info("Upstream kernel commit-time: %s", tcommit)
        log.debug("Compile the upstream kernel")
        try:
            cpu= self.con.run_command("lscpu | grep '^CPU(s):' | awk '{print $2}'")
            err=self.con.run_command("make -j {} -s vmlinux".format(cpu[-1]), timeout=self.host_cmd_timeout)
            log.info("Kernel build successful")
            return 0,err
        except CommandFailed as e:
            log.error("Kernel build failed: {}".format(e))
            return  4,e
        
    def Store_loc(self, er) :
            """
            To get location of file in which error is introduced
            """
            pattern = r"([\w\d_]+\/(?:(?:[\w\d_]+\/)*[\w\d_]+\b))"
            matches = [match.group(1) for match in re.finditer(pattern,er)]
            return matches
    
    def boot_kernel(self):
        """
        Does kexec boot for Upstream Linux
        """
        self.con.run_command("export TERM=dumb; export NO_COLOR=1; alias ls='ls --color=never'; alias grep='grep --color=never'; git config --global color.ui false; bind 'set enable-bracketed-paste off'")
        self.con.run_command("make olddefconfig")
        base_version = self.con.run_command("uname -r")
        ker_ver = self.con.run_command("make kernelrelease")[-1]
        cpu= self.con.run_command("lscpu | grep '^CPU(s):' | awk '{print $2}'")
        self.con.run_command("make -j {} all -s vmlinux".format(cpu[-1]), timeout = 60000)
        self.con.run_command("make modules_install")
        self.con.run_command("make install")
        if self.host_distro_name in ['rhel', 'Red Hat', 'ubuntu', 'Ubuntu']:
            self.con.run_command('grubby --set-default /boot/vmlinu*-{}'.format(base_version[-1]))
        elif self.host_distro_name in ['sles', 'SLES']:
            self.con.run_command('grub2-set-default /boot/vmlinu*-{}'.format(base_version[-1]))
        else:
            raise self.skipTest("Unsupported OS")
        cmdline = self.con.run_command("cat /proc/cmdline")[-1]
        if self.append_kernel_cmdline:
            cmdline += " %s" % self.append_kernel_cmdline
        try:
            initrd_file = self.con.run_command("ls -l /boot/initr*-%s.img" % ker_ver)[-1].split(" ")[-1]
        except Exception:
            initrd_file = self.con.run_command("ls -l /boot/initr*-%s" % ker_ver)[-1].split(" ")[-1]
        kexec_cmdline = "kexec --initrd %s --command-line=\"%s\" /boot/vmlinu*-%s -l" % (initrd_file, cmdline, ker_ver)
        self.con.run_command("grub2-mkconfig  --output=/boot/grub2/grub.cfg")
        self.con.run_command(kexec_cmdline)
        self.con.run_command("bind 'set enable-bracketed-paste off'")
        self.con.close()
        self.console_thread.console_terminate()
        self.cv_SYSTEM.util.build_prompt()
        self.console_thread.console_terminate()
        time.sleep(15)
        for i in range(5):
            raw_pty = self.util.wait_for(self.cv_SYSTEM.console.get_console, timeout=20)
            time.sleep(10)
            if raw_pty is not None:
                raw_pty.sendline("uname -r")
                break
        try:
            raw_pty.sendline("kexec -e")
        except Exception as e:
            log.info(e)
        rc = raw_pty.expect(["login:", "WARNING: CPU"], timeout=600)
        if rc == 1:
            raw_pty.close()
            self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            dmessage = self.con.run_command("dmesg --color=never")
            log.info(dmessage)
            log.info("WARNING: CPU catched")
            return False
        kernel_version_output = self.con.run_command("uname -r")[-1]
        log.info("Installed upstream kernel version: %s", kernel_version_output[-1])
        if self.conf.args.host_cmd:
            self.con.run_command(self.conf.args.host_cmd,
                                timeout=60)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
        if kernel_version_output != base_version :
            print("Kernel booted fine. Kernel version:", kernel_version_output.strip())
            return True
        else:
            return False


class KernelBuild(KernelTest):
    """
    Does the build for any Linux repo and in case of build failure, calls build bisector 
    from OpTestUtils to give first bad commit and related information along with email template. 
    """

    def setUp(self):
        """
        Does setup for KernelBUild from parent KernelTest
        """
        super(KernelBuild,self).setUp()

    def runTest(self):
        """
        Clones git repo and builds to check for failure and do bisection
        """
        self.con.run_command("if [ -d {} ]; then rm -rf {}; fi".format(self.home,self.home))
        self.con.run_command("if [ ! -d {} ]; then mkdir -p {}; fi".format(self.home,self.home))
        self.con.run_command("cd {}".format(self.home))
        if not self.branch:
            self.branch='master' 
        self.con.run_command("git clone --depth 1 -b {} {} linux".format( self.branch, self.repo),timeout=3000)
        self.con.run_command("cd linux")
        commit = self.con.run_command(" git log -1 --format=%H  | sed -r 's/\x1B\[[0-9:]*[JKsu]//g'")
        self.con.run_command("cd ..")
        error = self.build_kernel()
        exit_code = error[0]
        errVal = str(error[1])
        log.info("printing the exit code '{}'".format(exit_code))
        entry=[]
        err_msg=[]
        if exit_code != 0:
            entry = self.Store_loc(errVal)[-1]
            err_msg= self.util.err_message(error)
            badCommit = commit[-1]
            if self.bisect_flag == '1':
                log.info("STARTING BUILD_BISECTION")
                res = self.util.build_bisector(self.linux_path, self.good_commit, self.repo)
                log.info("BUILD_BISECTION ENDED")
                emaili=res[0]
                commiti=res[1]
                log.info("revert commit check is manual for now")
            else :  
                emaili=""
                commiti=commit[-1]
        else :  
             emaili=""
             commiti=commit[-1]
        with open('output.json','w') as f:
            json.dump({"exit_code":exit_code,"email":emaili,"commit": commiti,"error":entry,"err_msg":err_msg,"flag":self.bisect_flag},f)
        if exit_code != 0:
            self.util.format_email(self.linux_path, self.repo)
    
    def tearDown(self):
        self.console_thread.console_terminate()
        self.con.close()


class KernelBoot(KernelTest):

    def setUp(self):
        """
        Does setup for KernelBoot from parent KernelTest
        """
        super(KernelBoot,self).setUp()

    def runTest(self):
        """
        Clones git repo and boots the kernel to check for failure and do bisection
        """
        self.con.run_command("if [ -d {} ]; then rm -rf {}; fi".format(self.home,self.home))
        self.con.run_command("if [ ! -d {} ]; then mkdir -p {}; fi".format(self.home,self.home))
        self.con.run_command("cd {}".format(self.home))
        if not self.branch:
            self.branch='master'
        self.con.run_command("git clone --depth 1 -b {} {} linux".format( self.branch, self.repo),timeout=3000)
        self.con.run_command("cd linux")
        commit = self.con.run_command(" git log -1 --format=%H  | sed -r 's/\x1B\[[0-9:]*[JKsu]//g'")
        self.con.run_command("cd ..")
        error = self.build_kernel()
        exit_code = error[0]
        if exit_code != 0:
            return "Build Failure in boot, check build bisection Aborting"
        log.info("BOOOT STARTING")
        boot = False
        try :
            boot = self.boot_kernel()
        except Exception as e:
            log.info("EXCEPTION")
        if not boot and self.bisect_flag == '1':
            log.info("BISECTION STARTING")
            subprocess.run(f"if [ -d {self.linux_path} ]; then rm -rf {self.linux_path}; fi", shell=True, check=True)
            subprocess.run(f"if [ ! -d {self.linux_path} ]; then mkdir -p {self.linux_path}; fi", shell=True, check=True)
            subprocess.run(f"cd {self.home}", shell=True, check=True)
            subprocess.run("git config --global http.postBuffer 1048576000", shell=True, check=True)
            subprocess.run(f"git clone -b {self.branch} {self.repo} {self.linux_path}" , shell=True, check=True,timeout=1800)
            subprocess.run(f"cd {self.linux_path}",shell=True,check=True)
            try:
                subprocess.run("git bisect start", shell=True, check=True,cwd=self.linux_path)
                subprocess.run("git bisect bad", shell=True, check=True,cwd=self.linux_path)
                folder_type=re.split(r'[\/\\.]',str(self.repo))[-2]
                if folder_type == 'linux-next':
                    subprocess.run("git fetch --tags" , shell=True, check=True)
                    good_tag=subprocess.run("git tag -l 'v[0-9]*' | sort -V | tail -n 1", shell=True, check=True)
                    subprocess.run(f"git bisect good {good_tag}", shell=True, check=True,cwd=self.linux_path)
                else:
                    subprocess.run("pwd")
                    subprocess.run(f"git bisect good {self.good_commit}", shell=True, check=True,cwd=self.linux_path)
                while True:
                    print("ENTERED LOOP BISECT")
                    subprocess.run("git bisect next", shell=True, check=True, cwd=self.linux_path)
                    commit_to_test = subprocess.check_output("git rev-parse HEAD", shell=True, cwd=self.linux_path).decode().strip()
                    log.info("commit to test is")
                    log.info(commit_to_test)
                    self.con.run_command(" if [ '$(pwd)' != {} ]; then cd {} || exit 1 ; fi ; bind 'set enable-bracketed-paste off'".format(self.linux_path,self.linux_path))
                    self.con.run_command("git checkout {}; git checkout {};".format(self.branch,commit_to_test))
                    result = self.boot_kernel()
                    if result == True:
                        subprocess.run("git bisect good", shell=True, check=True,cwd=self.linux_path)
                    else:
                        subprocess.run("git bisect bad", shell=True, check=True,cwd=self.linux_path)
            except subprocess.CalledProcessError as e:
                log.info("Error:", e)
            finally:
                bisect_log = subprocess.run("git bisect log", shell=True, check=True,cwd=self.linux_path)
                log.info(bisect_log)
                subprocess.run("git bisect reset", shell=True, check=True,cwd=self.linux_path)
        elif self.bisect_flag != '1':
            log.info("BOOT FAILURE, NO BISECTION")
        else:
            log.info("NO BISECTION NEEDED, NOT BOOT FAILURE")

    def tearDown(self):
        self.console_thread.console_terminate()
        self.con.close()
