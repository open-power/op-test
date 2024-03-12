#build_bisector.py : run the bisector script after taking good commit and bad commit.

#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
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
import os
import uuid
from datetime import datetime
import re
import unittest
import os
from urllib.parse import urlparse
from enum import Enum
import subprocess
import smtplib
from email.mime.text import MIMEText
import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestInstallUtil import InstallUtil
from common.Exceptions import CommandFailed
import test_binaries
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
class Buil_bisector(unittest.TestCase):
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
        self.config_path = self.conf.args.git_repoconfigpath
        self.config = self.conf.args.git_repoconfig
        self.good_commit = self.conf.args.good_commit
        self.bad_commit = self.conf.args.bad_commit
        self.bisect_script = self.conf.args.bisect_script
        self.bisect_category = self.conf.args.bisect_category
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        self.linux_path = os.path.join(self.home, "linux")
        if self.config_path:
            self.config = "olddefconfig"
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")
    def get_email(self, commit_id):
        try :
            self.connection.run_command("git config --global color.ui true")
            result = self.connection.run_command("git show --format=%ce {} | sed -r 's/\x1B\[[0-9:]*[JKsu]//g'".format(commit_id))
            print("result",result,"result")
            email = result[0]
            print("email: ",email)

            return email
        except subprocess.CalledProcessError as e:
            print("ERROR",e)
            return None    
    def runTest(self):
        self.connection.run_command(" if [ '$(pwd)' != {} ]; then cd {} || exit 1 ; fi ".format(self.linux_path,self.linux_path))
        shallow = self.connection.run_command("git rev-parse --is-shallow-repository")
        print(type(shallow[-1]))
        if shallow[-1] == True or shallow[-1] == 'true':
            self.connection.run_command("git fetch --unshallow",timeout=3000)
        makefile_path = os.path.join(self.conf.basedir, "make.sh")
        self.cv_HOST.copy_test_file_to_host(makefile_path, dstdir=self.linux_path)
        self.connection.run_command("git bisect start")
        self.connection.run_command("git bisect good {} ".format(self.good_commit))
        self.connection.run_command(" git bisect bad ")
        self.connection.run_command("chmod +x ./make.sh ")
        commit =  self.connection.run_command(" git bisect run ./make.sh")
        log.info(commit)
        badCommit = [word for word in commit if word.endswith("is the first bad commit")]
        badCommit= badCommit[0].split()[0]
        log.info("BISECT")
        log.info(badCommit)
        email = self.get_email(badCommit)
        subject = f"Author of Commit {badCommit}"
        body = f"The above commit is causing build errors"
        self.connection.run_command("git bisect reset")
        log.info("email  ")
        log.info(email)  
        return email , badCommit
             
        
        