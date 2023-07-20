#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/Lcov.py
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
# [+] International Business Machines Corp.
# Author: Naresh Bannoth <nbannoth@linux.vnet.ibm.com>
#
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

'''
Lcov setup Testcase
--------------------

This test case is to setup Lcov and gather the gcov code coverage data
'''

import unittest
import os
import time
import tempfile
import OpTestConfiguration
from common.OpTestUtil import OpTestUtil

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class LcovSetup(unittest.TestCase):
    '''
    Gather the gcov ran data using lcov tool
    '''

    def setUp(self):
        '''
        get the configuration details
        '''
        conf = OpTestConfiguration.conf
        self.host_cmd_timeout = conf.args.host_cmd_timeout
        self.cv_HOST = conf.host()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.distro = self.util.distro_name()
        self.k_version = "".join(self.cv_HOST.host_run_command("uname -r"))

    def runTest(self):
        '''
        Test for installing the lcov
        '''
        log.info("distro_name=%s" %self.distro)
        if self.distro == 'rhel':
            cmd = "yum install"
        elif self.distro == 'sles':
            cmd = "zypper install"
        dep_packages = ['perl*', 'tiny*']
        log.info("installing the dependency packages")
        for pkg in dep_packages:
            self.c.run_command(cmd + " " + pkg + " -y")
        time.sleep(5)
        log.info("changing dir to /home")
        self.c.run_command("cd /home/")
        url = 'git clone https://github.com/linux-test-project/lcov.git'
        self.c.run_command(url)
        log.info("changing dir to /lcov")
        self.c.run_command("cd lcov")
        self.c.run_command("pwd")
        self.c.run_command("make install")


class LcovCounterZero(LcovSetup):
    '''
    make the lcov counter to zero before gathering the data
    '''
    def runTest(self):
        '''
        Running the test for Zeroing the lcov
        '''
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        log.info("Zeroing the lcov")
        self.c.run_command("echo 1 > /sys/kernel/debug/gcov/reset")
        self.c.run_command("lcov --zerocounters")


class LcovGatherData(LcovSetup):
    '''
    collect all gcov data and create an html file
    '''
    def runTest(self):
        '''
        Running the test
        '''
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.k_version = "".join(self.cv_HOST.host_run_command("uname -r"))
        src_path = f'/root/kernel-{self.k_version}*/linux-{self.k_version}*'
        self.cv_HOST.host_run_command(f"cd {src_path}")
        src_path = "".join(self.cv_HOST.host_run_command("pwd"))
        temp_dir = tempfile.mkdtemp(prefix="Lcov_result_")
        gcov_path = '/sys/kernel/debug/gcov'
        gcov_src = src_path[1:]
        gcov_src_path = os.path.join(gcov_path, gcov_src)
        info_file_path = '/home/test.info'
        self.cv_HOST.host_run_command(f"touch /home/test.info")
        info_cmd = f'lcov -o {info_file_path} -c -f -d {gcov_src_path} -b  {src_path} --keep-going' 
        self.c.run_command(info_cmd, timeout=self.host_cmd_timeout)
        html_cmd = f'genhtml -o {temp_dir} {info_file_path}'
        self.c.run_command(html_cmd, timeout=self.host_cmd_timeout)
        curr_dir = os.getcwd()
        log.info(f"\n\ncurrent_dir={curr_dir}, \ncreating dir here now")
        self.cv_HOST.host_run_command("mkdir -p Lcov-result")
        lcov_result_dir = os.path.join(curr_dir, "Lcov-result")
        log.info(f"copying html files to this paths at source : {lcov_result_dir}")
        self.cv_HOST.copy_files_from_host(lcov_result_dir, "%s/*" %temp_dir)
        log.info("\ncopying done.....")

