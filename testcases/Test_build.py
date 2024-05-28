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
import os
import re
import unittest
from urllib.parse import urlparse
import subprocess
import OpTestConfiguration
import OpTestLogger
import configparser
import sys
from testcases import Build_bisector
from testcases import Email_git
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.Exceptions import CommandFailed
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
class Test_build(unittest.TestCase):
    """
    Test case for building kernel and calling Build_bisector.py in case of build failure
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
        self.config = self.conf.args.git_repoconfig
        self.good_commit = self.conf.args.good_commit
        self.bad_commit = self.conf.args.bad_commit
        self.bisect_script = self.conf.args.bisect_script
        self.bisect_category = self.conf.args.bisect_category
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        self.linux_path = os.path.join(self.home, "linux")
        self.bisect_flag = self.conf.args.bisect_flag
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")

    def build_kernel(self):
        """
        Build and install the Linux kernel.
        """
        self.connection.run_command("wget http://ltc-jenkins.aus.stglabs.ibm.com:81/abdul/ioci/kernel_config -o linux/.config")
        self.connection.run_command("cd linux && make olddefconfig")
        try:
            build_command = "make -j && make modules_install"
            err=self.connection.run_command(build_command, timeout=self.host_cmd_timeout)
            log.info("Kernel build successful")
            return 0,err
        except CommandFailed as e:
            log.error("Kernel build failed: {}".format(e))
            return  4,e
        
    def Store_loc ( self, er) :
            """
            To get location of file in which error is introduced
            """
            pattern = r"([\w\d_]+\/(?:(?:[\w\d_]+\/)*[\w\d_]+\b))"
            matches = [match.group(1) for match in re.finditer(pattern,er)]
            return matches
        
    def runTest(self):
        self.connection.run_command("if [ -d {} ]; then rm -rf {}; fi".format(self.home,self.home))
        self.connection.run_command("if [ ! -d {} ]; then mkdir -p {}; fi".format(self.home,self.home))
        self.connection.run_command("cd {}".format(self.home))
        if not self.branch:
            self.branch='master' 
        log.info("CD DONE")
        self.connection.run_command("git clone --depth 1 {} -b {}".format(self.repo, self.branch))
        self.connection.run_command("git clone -b {} {} linux".format( self.branch, self.repo),timeout=3000)
        self.connection.run_command("cd linux")
        commit = self.connection.run_command(" git log -1 --format=%H  | sed -r 's/\x1B\[[0-9:]*[JKsu]//g'")
        self.connection.run_command("cd ..")
        error = self.build_kernel()
        log.info("COMMAND RUN")
        exit_code = error[0]
        errVal = str(error[1])
        log.info("printing the exit code '{}'".format(exit_code))
        entry=[]
        if exit_code != 0:
            entry = self.Store_loc(errVal)[-1]
            badCommit = commit[-1]
            if self.bisect_flag == '1':
                log.info("BUILD_BISECTOR CALLED")
                bisect = Build_bisector.Buil_bisector()
                bisect.setUp()
                res = bisect.runTest()
                log.info("BUILD_BISECTOR END")
                emaili=res[0]
                commiti=res[1]
                log.info("COMMIT REVERT HAS TO BE CHECKED MANUALLY")
            else :  
                emaili=""
                commiti=commit[-1]
        else :  
             emaili=""
             commiti=commit[-1]
        with open('output.json','w') as f:
            json.dump({"exit_code":exit_code,"email":emaili,"commit": commiti,"error":entry,"flag":self.bisect_flag},f)
        if exit_code != 0:
            email = Email_git.Email_git()
            email.setUp()
            email.runTest()
        return exit_code
