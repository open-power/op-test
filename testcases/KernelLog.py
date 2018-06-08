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

class KernelLog():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def runTest(self):
        self.setup_test()

        log_entries = []
        # Depending on where we're running, we may need to do all sorts of
        # things to get a sane dmesg output. Urgh.
        try:
            log_entries = self.c.run_command("dmesg --color=never -T --level=alert,crit,err,warn")
        except CommandFailed:
            try:
                log_entries = self.c.run_command("dmesg -T --level=alert,crit,err,warn")
            except CommandFailed:
                log_entries = self.c.run_command("dmesg -r|grep '<[4321]>'")

        filter_out = ["Unable to open file.* /etc/keys/x509",
                      "OF: reserved mem: not enough space all defined regions.",
                      "Could not find start_pfn for node 25.",
                      "nvidia: loading out-of-tree module taints kernel",
                      "nvidia: module license 'NVIDIA' taints kernel.",
                      "Disabling lock debugging due to kernel taint",
                      "NVRM: loading NVIDIA UNIX ppc64le Kernel Module",
                      "This architecture does not have kernel memory protection.",
                      "aacraid.* Comm Interface type3 enabled",
                      "mpt3sas_cm.* MSI-X vectors supported",
                      "i40e.*PCI-Express bandwidth available for this device may be insu",
                      "i40e.*Please move the device to a different PCI-e link with more",
                      "systemd.*Dependency failed for pNFS block layout mapping daemon.",
                      "NFSD.* Using .* as the NFSv4 state recovery directory",
                      "ipmi_si.* Unable to find any System Interface",
                      "mpt3sas.*invalid short VPD tag 00 at offset 1",
                      "synth uevent.*failed to send uevent",
                      "vio: uevent: failed to send synthetic uevent",
                      "pstore: decompression failed: -5",
                      "NCQ Send/Recv Log not supported",
                      # Nouveau not supporting our GPUs is expected, not OPAL bug.
                      "nouveau .* unknown chipset",
                      "nouveau: probe of .* failed with error -12",
                      # The below xive message should go away when https://github.com/open-power/skiboot/issues/171 is resolved
                      "xive: Interrupt.*type mismatch, Linux says Level, FW says Edge",
                      # This is why we can't have nice things.
                      "systemd-journald.*File.*corrupted or uncleanly shut down, renaming and replacing.",
                      # Not having memory on all NUMA nodes isn't *necessarily* fatal or a problem
                      "Could not find start_pfn for node",
                      # PNOR tests open a r/w window on a RO partition, currently fails like this
                      "mtd.*opal_flash_async_op\(op=1\) failed \(rc -6\)"
        ]

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
