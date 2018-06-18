#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestPNOR.py $
#
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
# IBM_PROLOG_END_TAG
#
#  @package OpTestPNOR.py
#
#   This testcase will deal with testing access to the host pnor
#   from petitboot through the pflash program
#

import time
import subprocess
import commands
import re
import sys
import os
import os.path

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.Exceptions import CommandFailed

class OpTestPNOR():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.util = OpTestUtil()

    def pflashErase(self, offset, length):
        self.c.run_command("pflash -e -f -a %d -s %d" % (offset,length))

    def pflashErasePartition(self, partition):
        self.c.run_command("pflash -e -f -P %s" % (partition))

    def pflashRead(self, filename, offset, length):
        self.c.run_command("pflash -r %s -a %d -s %d" % (filename,offset,length))

    def pflashReadPartition(self, filename, partition):
        self.c.run_command("pflash -r %s -P %s" % (filename,partition))

    def pflashWrite(self, filename, offset, length):
        self.c.run_command("pflash -f -p %s -a %d -s %d" % (filename,offset,length))

    def pflashWritePartition(self, filename, partition):
        self.c.run_command("pflash -f -p %s -P %s" % (filename,partition))

    def pflashGetPartition(self, partition):
        d = self.c.run_command("pflash --info")
        for line in d:
            s = re.search(partition, line)
            if s:
                m = re.match(r'ID=\d+\s+\S+\s+((0[xX])?[0-9a-fA-F]+)..(0[xX])?[0-9a-fA-F]+\s+\(actual=((0[xX])?[0-9a-fA-F]+)\)\s(\[)?([A-Za-z-]+)?(\])?.*', line)
                if not m:
                    continue
                offset = int(m.group(1), 16)
                length = int(m.group(4), 16)
                ret = {'offset': offset,
                       'length': length
                       }
                flags = m.group(7)
                if flags:
                    ret['flags'] = [x for x in list(flags) if x != '-']
                return ret

    def comparePartitionFile(self, filename, partition):
        self.c.run_command("pflash -r /tmp/tmp -P %s" % (partition))
        try:
            self.c.run_command("diff /tmp/tmp %s" % (filename))
        except CommandFailed as cf:
            self.assertEqual(cf.output, "0")

    def runTestReadEraseWriteNVRAM(self):
        # Read NVRAM to file /tmp/nvram
        self.pflashReadPartition("/tmp/nvram", "NVRAM")
        nvramInfo = self.pflashGetPartition("NVRAM")
        # Erase the NVRAM partition
        self.pflashErase(nvramInfo['offset'], nvramInfo['length'])
        # Read the (hopefully) erased NVRAM
        self.pflashReadPartition("/tmp/null", "NVRAM")
        # Write back to the NVRAM partition
        self.pflashWrite("/tmp/nvram", nvramInfo['offset'], nvramInfo['length'])
        # Compare /tmp/nvram to rewritten nvram contents
        self.comparePartitionFile("/tmp/nvram", "NVRAM")
        # Check /tmp/null all "erased"
        d = self.c.run_command("cat /tmp/null | tr -d \"\xff\" | wc -c")
        self.assertEqual(d[0], "0")

    def runTestReadWritePAYLOAD(self):
        payloadInfo = self.pflashGetPartition("PAYLOAD")
        print repr(payloadInfo)
        # Read PAYLOAD to file /tmp/payload
        self.pflashReadPartition("/tmp/payload", "PAYLOAD")
        # Write /tmp/payload to PAYLOAD
        try:
            self.pflashWrite("/tmp/payload", payloadInfo['offset'], payloadInfo['length'])
        except CommandFailed as cf:
            print repr(cf)
            if not ('R' in payloadInfo['flags'] and cf.exitcode in [8]):
                raise cf
        # Check the same
        self.comparePartitionFile("/tmp/payload", "PAYLOAD")
        # Try using the pflash -P option as well
        try:
            self.pflashWritePartition("/tmp/payload", "PAYLOAD")
        except CommandFailed as cf:
            if not ('R' in payloadInfo['flags'] and cf.exitcode in [8]):
                raise cf
        # Check the same
        self.comparePartitionFile("/tmp/payload", "PAYLOAD")

    def runTestWriteTOC(self):
        tocInfo = self.pflashGetPartition("part")
        # Read the toc so we can write it back later
        self.pflashRead("/tmp/toc", tocInfo['offset'], tocInfo['length'])
        # Write all zeros to the toc (Because why not :D)
        self.c.run_command("dd if=/dev/zero of=/tmp/zeros bs=1 count=%s" % (tocInfo['length']))
        self.pflashWrite("/tmp/zeros", tocInfo['offset'], tocInfo['length'])
        # Read and compare
        self.pflashRead("/tmp/tmp", tocInfo['offset'], tocInfo['length'])
        try:
            self.c.run_command("diff /tmp/tmp /tmp/zeros")
        except CommandFailed as cf:
            # This is not an error -> expected for vPNOR
            print "Failed to zero TOC"
        # Better write the toc back now
        self.pflashWrite("/tmp/toc", tocInfo['offset'], tocInfo['length'])

    def runTest(self):
        self.setup_test()
        if not self.system.has_mtd_pnor_access():
            self.skipTest("Host doesn't have MTD PNOR access")

        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")

        # Read Erase Write NVRAM
        self.runTestReadEraseWriteNVRAM()
        # Read and then reWrite PAYLOAD
        self.runTestReadWritePAYLOAD()
        # Try write to the TOC
        self.runTestWriteTOC()

class Skiroot(OpTestPNOR, unittest.TestCase):
    def setup_test(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.system.sys_get_ipmi_console()
        self.system.host_console_unique_prompt()

class Host(OpTestPNOR, unittest.TestCase):
    def setup_test(self):
        self.system.goto_state(OpSystemState.OS)
        self.c = self.system.host().get_ssh_connection()
