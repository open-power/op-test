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

import unittest
import re

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

class OpalMsglog():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        filter_out = [
            # PRD can send invalid SCOMS, skiboot 6.0 logs these as errors
            "XSCOM: read error gcid=.* pcb_addr=0x40031 stat=0x4",
            "XSCOM: Read failed, ret =  -26",
                      ]

        try:
            log_entries = self.c.run_command("grep ',[0-4]\]' /sys/firmware/opal/msglog")

            for f in filter_out:
                fre = re.compile(f)
                log_entries = [l for l in log_entries if not fre.search(l)]

            msg = '\n'.join(filter(None, log_entries))
            self.assertTrue( len(log_entries) == 0, "Warnings/Errors in OPAL log:\n%s" % msg)
        except CommandFailed as cf:
            if cf.exitcode is 1 and len(cf.output) is 0:
                pass
            else:
                raise cf

class Skiroot(OpalMsglog, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class Host(OpalMsglog, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()
