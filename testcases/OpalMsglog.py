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
OPAL log test
-------------

Look for boot and runtime warnings and errors from OPAL (skiboot).

We filter out any "known errors", such as how PRD can do invalid SCOMs but
that it's not an error error.
'''

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
        self.bmc_type = conf.args.bmc_type
        self.conf = conf

    def runTest(self):
        self.setup_test()
        filter_out = [
            # PRD can send invalid SCOMS, skiboot 6.0 logs these as errors
            "XSCOM: read error gcid=.* pcb_addr=0x40031 stat=0x4",
            "XSCOM: Read failed, ret =  -26",
                      ]

        if self.bmc_type in ["qemu"]:
            filter_out.append('SLW: No image found')
            filter_out.append('SLW: Sleep not enabled by HB on this platform')
            filter_out.append('OCC: No HOMER detected, assuming no pstates')
            # A bunch of qemu configurations won't have a pnor
            filter_out.append('FFS: Reading the flash has returned all 0xFF.')
            filter_out.append('Are you reading erased flash?')
            filter_out.append('Is something else using the flash controller?')
            filter_out.append('FLASH: No ffs info; using raw device only')
            filter_out.append('NVRAM: Failed to load')
            filter_out.append("FLASH: Can't load resource id:")
            filter_out.append('CAPP: Error loading ucode lid.')

        if self.bmc_type in ["mambo"]:
            filter_out.append('SBE: Master chip ID not found.')
            filter_out.append('OCC: No HOMER detected, assuming no pstates')
            filter_out.append('OCC: Unassigned OCC Common Area. No sensors found')
            filter_out.append("FLASH: Can't load resource id:")
            filter_out.append("ELOG: Error getting buffer to log error")
            filter_out.append("STB: container NOT VERIFIED, resource_id")
            # We should really fix this one
            filter_out.append("OPAL: Called with bad token 4 ")

        if self.conf.args.flash_kernel:
            # If we've flashed a BOOTKERNEL, then there's no way it'll match
            filter_out.append('STB: BOOTKERNEL verification')

        if self.conf.args.host_pnor or self.bmc_type in ["mambo"]:
            # If we've flashed a full PNOR, we may have to init NVRAM, so don't
            # fail on that
            filter_out.append(
                'NVRAM: Partition at offset .* extends beyond end of nvram')
            filter_out.append(
                'NVRAM: Partition at offset .* has incorrect .* length')
            filter_out.append('NVRAM: Re-initializing')

        try:
            log_entries = self.c.run_command(
                "grep ',[0-4]\]' /sys/firmware/opal/msglog")

            for f in filter_out:
                fre = re.compile(f)
                log_entries = [l for l in log_entries if not fre.search(l)]

            msg = '\n'.join(filter(None, log_entries))
            self.assertTrue(len(log_entries) == 0,
                            "Warnings/Errors in OPAL log:\n%s" % msg)
        except CommandFailed as cf:
            if cf.exitcode is 1 and len(cf.output) is 0:
                # We have no warnings/errors!
                pass
            else:
                raise cf


class Skiroot(OpalMsglog, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console


class Host(OpalMsglog, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
