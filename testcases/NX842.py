#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/NX842.py $
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

import time
import subprocess
import re
import commands
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestIPMI import IPMIConsoleState
from common.Exceptions import CommandFailed


class NX842(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.util = OpTestUtil()
        self.test = "host"
        pass

    def set_up(self):
        if self.test == "skiroot":
            self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.system.sys_get_ipmi_console()
            self.system.host_console_unique_prompt()
        elif self.test == "host":
            self.system.goto_state(OpSystemState.OS)
            kernel = self.host.host_get_kernel_version()
            self.host.host_load_module_based_on_config(
                kernel, "CONFIG_ZRAM", "zram")
            self.c = self.host.get_ssh_connection()
        else:
            raise Exception("Unknow test type")
        return self.c

    def runTest(self):
        c = self.set_up()
        algs = c.run_command("cat /sys/block/zram0/comp_algorithm")
        algs = algs[0].split(' ')
        algs = [s.strip('[]') for s in algs]
        self.assertIn("842", algs, "842 algorithm not supported by zram!")

        c.run_command("echo 1 > /sys/block/zram0/reset")
        c.run_command("echo 842 > /sys/block/zram0/comp_algorithm")

        algs = c.run_command("cat /sys/block/zram0/comp_algorithm")
        algs = algs[0].split(' ')
        self.assertIn("[842]", algs, "842 algorithm not supported by zram!")
        # 20MB should be enough for everyone....
        c.run_command("echo 20971520 > /sys/block/zram0/disksize")
        c.run_command("echo 20971520 > /sys/block/zram0/mem_limit")
        c.run_command("mkfs.ext4 /dev/zram0")
        d = c.run_command("mktemp -d")
        d = d[0]
        c.run_command("mount /dev/zram0 %s" % d)
        c.run_command("dd if=/dev/zero of=%s bs=1024 count=1024" %
                      (d + "/foo"))
        c.run_command("dmesg > %s" % (d + "/dmsg"))
        c.run_command("sync")
        stats = c.run_command("cat /sys/block/zram0/stat")
        stats = stats[0].split()
        # See linux/Documentation/ABI/testing/sysfs-block
        # We use 1 index to match docs
        self.assertGreater(stats[1-1], 1)  # reads
        self.assertGreater(stats[5-1], 1)  # writes
        mod_usage = c.run_command("lsmod|grep nx_compress_powernv")[0].split()
        self.assertGreater(mod_usage[2], 0)  # Should be being used by module
        c.run_command("umount %s" % d)
        c.run_command("echo 1 > /sys/block/zram0/reset")
