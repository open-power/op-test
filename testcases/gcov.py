#!/usr/bin/python2
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
# DeviceTreeWarnings
# This test read the device tree from /proc/device-tree using dtc
# and fails if there are any device tree warnings or errors present.
#

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed
from common import OpTestInstallUtil

class gcov():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        exports = self.c.run_command("ls -1 --color=never /sys/firmware/opal/exports/")
        if 'gcov' not in exports:
            self.skip("Not a GCOV build")

        l = self.c.run_command("wc -c /sys/firmware/opal/exports/gcov")
        iutil = OpTestInstallUtil.InstallUtil()
        my_ip = iutil.get_server_ip()
        if not my_ip:
            self.fail("unable to get the ip from host")
        port = iutil.start_server(my_ip)

        url = 'http://%s:%s/upload' % (my_ip, port)
        insanity = "(echo 'POST /upload/gcov HTTP/1.1'; \n"
        insanity += "echo 'Host: %s:%d';\n" % (my_ip, port)
        insanity += "echo 'Content-length: %s';\n" % (l[0])
        insanity += "echo 'Origin: http://%s:%d'; \n" % (my_ip, port)
        boundary = "OhGoodnessWhyDoIHaveToDoThis"
        insanity += "echo 'Content-Type: multipart/form-data; boundary=%s';\n" % boundary
        insanity += "echo; echo '--%s'; \n" % boundary
        insanity += "echo 'Content-Disposition: form-data; name=\"file\"; filename=\"gcov\"'; \n"
        insanity += "echo 'Content-Type: application/octet-stream'; echo; \n"
        insanity += "cat /sys/firmware/opal/exports/gcov; \n"
        insanity += "echo; echo '--%s--';\n" % boundary
        insanity += ") | nc %s %d" % (my_ip, port)
        self.c.run_command(insanity)

        with open('gcov-saved', 'wb') as f:
            f.write(iutil.get_uploaded_file('gcov'))



class Skiroot(gcov, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class Host(gcov, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
