#!/usr/bin/env python2
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

'''
Kernel Log
----------

Check the Linux kernel log in skiroot and the OS for warnings and errors,
filtering for known benign problems (or problems that are just a Linux issue
rather than a firmware issue).

'''

import unittest
import re

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class KernelLog():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type

    def runTest(self):
        self.setup_test()

        log_entries = []
        # Depending on where we're running, we may need to do all sorts of
        # things to get a sane dmesg output. Urgh.
        try:
            log_entries = self.c.run_command(
                "dmesg --color=never -T --level=alert,crit,err,warn")
        except CommandFailed:
            try:
                log_entries = self.c.run_command(
                    "dmesg -T --level=alert,crit,err,warn")
            except CommandFailed:
                try:
                    log_entries = self.c.run_command(
                        "dmesg -r|grep '<[4321]>'")
                except CommandFailed as cf:
                    # An exit code of 1 and no output can mean success.
                    # as it means we're not successfully grepping out anything
                    if cf.exitcode == 1 and len(cf.output) == 0:
                        pass

        filter_out = ["Unable to open file.* /etc/keys/x509",
                      "OF: reserved mem: not enough space all defined regions.",
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
                      "pstore: decompression failed",
                      "NCQ Send/Recv Log not supported",
                      "output lines suppressed due to ratelimiting",
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
                      "mtd.*opal_flash_async_op\(op=1\) failed \(rc -6\)",
                      # New warning, but aparrently harmless
                      "Cannot allocate SWIOTLB buffer",
                      # Ignore a quirk that we hit on (at least some) Tuletas,
                      "TI XIO2000a quirk detected; secondary bus fast back-to-back transfers disabled",
                      # SCSI is Fun, and for some reason likes being very severe about discovering disks,
                      "sd .* \[sd.*\] Assuming drive cache: write through",
                      # SCSI is fun. Progress as dots
                      " \.$",
                      # SCSI is fun, of course this is critically important event
                      "s[dr] .* Power-on or device reset occurred",
                      ".?ready$",
                      # Mellanox!
                      "mlx4_en.* Port \d+: Using \d+ [TR]X rings",
                      "mlx4_en.* Port \d+: Initializing port",
                      "mlx4_core.*Old device ETS support detected",
                      "mlx4_core.*Consider upgrading device FW.",
                      ]

        if self.bmc_type in ['qemu']:
            # Qemu doesn't (yet) have pstate support, so ignore errors there.
            filter_out.append('powernv-cpufreq: ibm,pstate-min node not found')
            filter_out.append('nvram: Failed to find or create lnx,oops-log')
            filter_out.append('nvram: Failed to initialize oops partition!')
            # some weird disk setups
            filter_out.append('vdb.*start.*is beyond EOD')
            # urandom_read fun
            filter_out.append('urandom_read: \d+ callbacks suppressed')

        if self.bmc_type in ['mambo']:
            # We have a couple of things showing up in Mambo runs.
            # We should probably fix this, but ignore for now.
            #
            # First, no pstates:
            filter_out.append('powernv-cpufreq: ibm,pstate-min node not found')
            # Strange IMC failure
            filter_out.append('IMC PMU nest_mcs01_imc Register failed')
            # urandom_read fun
            filter_out.append('urandom_read: \d+ callbacks suppressed')

        for f in filter_out:
            fre = re.compile(f)
            log_entries = [l for l in log_entries if not fre.search(l)]

        msg = '\n'.join(filter(None, log_entries))
        self.assertTrue(len(log_entries) == 0,
                        "Warnings/Errors in Kernel log:\n%s" % msg)


class Skiroot(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "skiroot"
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console


class Host(KernelLog, unittest.TestCase):
    def setup_test(self):
        self.test = "host"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_HOST.get_ssh_connection()
