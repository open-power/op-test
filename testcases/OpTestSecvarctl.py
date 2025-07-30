#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2025
# [+] International Business Machines Corp.
# Author: Krishan Gopal Saraswat <krishang@linux.ibm.com>
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

'''
Secvarctl is to simplify and automate the process of reading, writing,
validating, and generating Secure Boot keys and vaiables such as
PK, KEK, db, dbx, and other secure variables in the OpenPOWER platform.
'''

import unittest
import os
import time
import OpTestConfiguration
import OpTestLogger
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class SecvarctlTest(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.distro_name = self.util.distro_name()
        self.cv_SYSTEM = self.conf.system()
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.secvar_repo = self.conf.args.git_repo
        self.branch = self.conf.args.git_branch
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.home = self.conf.args.git_home
        dep_packages = ['gcc', 'make', 'cmake', 'git', 'libopenssl-devel']
        if self.distro_name == 'rhel':
            self.installer = "dnf install"
        elif self.distro_name == 'sles':
            self.installer = "zypper install"
        for pkg in dep_packages:
            if self.distro_name == 'rhel':
                self.cv_HOST.host_run_command(f"{self.installer} {pkg} -y")
            elif self.distro_name == 'sles':
                self.cv_HOST.host_run_command(f"{self.installer} -y {pkg}")
        try:
            self.secvar_repo = self.conf.args.git_repo
            self.branch = self.conf.args.git_branch
        except AttributeError:
            self.secvar_repo = "https://github.com/open-power/secvarctl"
            self.branch = "main"
            self.home = "/home"

    def build_secvarctl(self):
        try:
            timestamp = int(time.time())
            self.home = os.path.join(self.home, f"secvarctl_{timestamp}")
            # Create new directory with timestamp
            self.connection.run_command(f"mkdir -p {self.home}")
            git_clone_command = "cd {} && git clone --recursive {} -b {}".format(self.home, self.secvar_repo, self.branch)
            # Clone the secvarctl git repository from main branch
            self.connection.run_command(git_clone_command)
            # Log successful git clone
            log.info("secvarctl cloned successfully")

            self.build_path = os.path.join(self.home, "secvarctl")
            self.connection.run_command("cd {} && mkdir -p build && cd build".format(self.build_path))
            self.connection.run_command("cmake ../")
            self.connection.run_command("make")
            self.connection.run_command("cd {} && make check".format(self.build_path))
        except Exception as e:
            # Log any errors that occur
            self.fail("An error occurred : {}".format(str(e)))

    def generate_keys(self):
        try:
            gn_key = "guest_generate_testdata.py"
            self.gen_key_path = os.path.join(self.build_path, "test")
            self.connection.run_command("cd {} && python3 {}".format(self.gen_key_path, gn_key))
        except Exception as e:
            # Log any errors that occur
            self.fail("An error occurred : {}".format(str(e)))

    def run_secvar_test(self):
        try:
            self.connection.run_command("cd {}".format(self.build_path))
            self.connection.run_command("make check")
        except Exception as e:
            # Log any errors that occur
            self.fail("An error occurred : {}".format(str(e)))

    def runTest(self):
        try:
            self.build_secvarctl()
            self.generate_keys()
            self.run_secvar_test()
        except Exception as e:
            # Log any errors that occur
            self.fail("An error occurred : {}".format(str(e)))

    def tearDown(self):
        try:
            # Remove the secvarctl directory and its contents
            if hasattr(self, 'home'):
                self.connection.run_command(f"rm -rf {self.home}")
                log.info(f"Cleaned up secvarctl directory: {self.home}")
        except Exception as e:
            log.error(f"Error during cleanup: {str(e)}")
