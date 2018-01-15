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

class KernelLog():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()
        if "skiroot" in self.test:
            cmd = "dmesg -r|grep '<[4321]>'"
        elif "host" in self.test:
            cmd = "dmesg --color=never -T --level=alert,crit,err,warn"
        else:
            raise Exception("Unknow test type")

        log_entries = self.c.run_command_ignore_fail(cmd)
        filter_out = ["Unable to open file.* /etc/keys/x509",
                    "This architecture does not have kernel memory protection.",
                    "aacraid.* Comm Interface type3 enabled",
                    "mpt3sas_cm0.* MSI-X vectors supported",
                    "i40e.*PCI-Express bandwidth available for this device may be insu",
                    "i40e.*Please move the device to a different PCI-e link with more",
                    "systemd.*Dependency failed for pNFS block layout mapping daemon.",
                    "NFSD.* Using .* as the NFSv4 state recovery directory",
                    "ipmi_si.* Unable to find any System Interface",
                    "mpt3sas.*invalid short VPD tag 00 at offset 1"]

        for f in filter_out:
            fre = re.compile(f)
            log_entries = [l for l in log_entries if not fre.search(l)]

        msg = '\n'.join(filter(None, log_entries))
        self.assertTrue( len(log_entries) == 0, "Warnings/Errors in Kernel log:\n%s" % msg)

class Skiroot(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "skiroot"
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()

class Host(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "host"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.host().get_ssh_connection()
