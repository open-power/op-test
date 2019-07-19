#!/usr/bin/env python3
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

'''
gcov
----

A "Test Case" for extracting GCOV code coverage data from skiboot. The real
use of this test case and code is to help construct code coverage reports
for skiboot.
'''

import os
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed
from common import OpTestInstallUtil

import socket

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

NR_GCOV_DUMPS = 0

class gcov():
    '''
    Base "test case" for extracting skiboot GCOV code coverage data from the
    host (use the Skiroot and Host TestCases for running this code).

    This requires a GCOV build of skiboot.

    We (rather convolutedly) do a HTTP POST operation (through shell!) back to
    the `op-test` process as since we may be running in skiroot, we don't have
    all the nice usual ways of transferring files around. The good news is that
    implementing a simple HTTP POST request in shell isn't that hard.
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.gcov_dir = conf.logdir

    def runTest(self):
        self.setup_test()
        try:
            exports = self.c.run_command(
                "ls -1 --color=never /sys/firmware/opal/exports/")
        except CommandFailed as cf:
            log.debug("exports cf.output={}".format(cf.output))
            exports = "EMPTY"
        if 'gcov' not in exports:
            self.skipTest("Not a GCOV build")

        l = self.c.run_command("wc -c /sys/firmware/opal/exports/gcov")
        iutil = OpTestInstallUtil.InstallUtil()
        try:
            my_ip = iutil.get_server_ip()
            log.debug("my_ip={}".format(my_ip))
        except Exception as e:
            log.debug("get_server_ip Exception={}".format(e))
            self.fail(
                "Unable to get the IP from Petitboot or Host, check that the IP's are configured")
        if not my_ip:
            self.fail(
                "We failed to get the IP from Petitboot or Host, check that the IP's are configured")

        HOST, PORT = "0.0.0.0", 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            port = s.getsockname()[1]
            s.listen(1)
            print(("# TCP Listening on %s" % port))

            insanity = "cat /sys/firmware/opal/exports/gcov "
            insanity += "| nc {} {}\n".format(my_ip, port)
            self.c.get_console().send(insanity)
            conn, addr = s.accept()
            with conn:
                print('Connected by ', addr)

                global NR_GCOV_DUMPS
                NR_GCOV_DUMPS = NR_GCOV_DUMPS + 1
                filename = os.path.join(
                    self.gcov_dir, 'gcov-saved-{}'.format(NR_GCOV_DUMPS))
                with open(filename, 'wb') as f:
                    size = int(l[0].split()[0])
                    while size:
                        data = conn.recv(4096)
                        size = size - len(data)
                        if not data: break
                        f.write(data)
            self.c.get_console().expect('#')
        self.c.run_command('echo Hello')


class Skiroot(gcov, unittest.TestCase):
    '''
    Extract GCOV code coverage in skiroot environment.
    '''

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console


class Host(gcov, unittest.TestCase):
    '''
    Extract GCOV code coverage from a host OS.
    '''

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
