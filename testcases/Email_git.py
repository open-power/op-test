#Email_git.py: to make boot of the repo and test it through exit code

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
import json
# import requests
import os
import uuid
from datetime import datetime
import re
import unittest
import os
from urllib.parse import urlparse
from enum import Enum
import subprocess
import OpTestConfiguration
import OpTestLogger
import configparser
import sys
from testcases import BisectKernel
from testcases import Test_build
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestInstallUtil import InstallUtil
from common.Exceptions import CommandFailed
# from testcases import Boot
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
class Email_git(unittest.TestCase):
    """
    Test case for bisecting the Linux kernel using Git Bisect.
    This test downloads the Linux kernel from a specified repository,
    configures and compiles it, and then uses Git Bisect to find the
    commit that introduced a specific issue.
    """
    def setUp(self):
        """
        Set up the test environment.
        Initializes test parameters and checks required configurations.
        """
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.console_thread = OpSOLMonitorThread(1, "console")
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.repo = self.conf.args.git_repo
        self.repo_reference = self.conf.args.git_repo_reference
        self.branch = self.conf.args.git_branch
        self.home = self.conf.args.git_home
        # self.config_path = self.conf.args.git_repoconfigpatih
        self.config = self.conf.args.git_repoconfig
        self.good_commit = self.conf.args.good_commit
        self.bad_commit = self.conf.args.bad_commit
        self.bisect_script = self.conf.args.bisect_script
        self.bisect_category = self.conf.args.bisect_category
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        self.linux_path = os.path.join(self.home, "linux")
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")
    def get_commit_message(self,commit_sha):
        try:
            self.connection.run_command(" if [ '$(pwd)' != {} ]; then cd {} || exit 1 ; fi ".format(self.linux_path,self.linux_path))
            
            commit_message = self.connection.run_command("git log -n 1 --pretty=format:%s {} | sed -r 's/\x1B\[[0-9:]*[JKsu]//g'".format(commit_sha))
            print(commit_message)
        except subprocess.CalledProcessError:
            commit_message = None
        print(commit_message[0].strip())
        return commit_message[0].strip()
    def runTest(self):
    # def generate_email_template(machine_type, gcc_version, commit, error_message):
        machine_type = self.connection.run_command("uname -m")
        gcc_version = self.connection.run_command("gcc --version")[0]
        kernel_version = self.connection.run_command("uname -r")
        try:
            with open("output.json", "r") as file:
                data = json.load(file)
                error_message = data.get("error", "")
                commit = str(data.get("commit", ""))[:7]
        except FileNotFoundError:
            print("Error: output.json not found.")
            error_message = ""
            commit = ""
 
        fix_description = self.get_commit_message(commit)
        # self.repo = "https://git.kernel.org/pub/scm/linux/kernel/git/netdev/net.git"

        if "https://git.kernel.org/pub/scm/linux/kernel/git/netdev/net.git" in self.repo:
            linux = "netdev/net"
        elif "https://git.kernel.org/pub/scm/linux/kernel/git/netdev/net-next.git" in self.repo:
            linux = "netdev/net-next"
        elif "https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git" in self.repo or "git://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git" in self.repo:
            linux = "scsi/scsi-queue"
        elif "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git" in self.repo:
            linux = "mainline/master"
        elif "https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git" in self.repo:
            linux = "linux-next/master"
        else:
            linux = "linux"

        subject = "[{}][bisected {}][PPC {}] build fail with error: {}".format(linux,commit, machine_type, error_message)
        
        body = """
        Greetings,

        Today's next kernel fails to build with gcc {} on {} machine.

        Kernel build fail at error: {}

        Kernel Version: {}
        Machine Type: {}
        gcc: {}
        Commit: {}

        kernel builds fine when the bad commit ({})  is reverted
        {} - {}

        -- 
        Regards
        PPC KBOT
        """.format(gcc_version, machine_type, error_message,kernel_version, machine_type, gcc_version, commit,commit, commit, fix_description)
        print(subject)
        print(body)
        
        with open("email.json","w") as email:
             json.dump({"subject":subject,"body":body},email)
        # return subject, body
    
