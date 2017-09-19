#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/SbePassThrough.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
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

# @package SbePassThrough
#  Test case for SBE passthrough
#

import re
import random


from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class SbePassThrough(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def setup_init(self):
        self.DOORBELL_REG = "D0063"
        self.os_level = self.cv_HOST.host_get_OS_Level()
        self.chips = self.cv_HOST.host_get_list_of_chips()

    def setup_opalprd_logs(self):
        if "Ubuntu" in self.os_level:
            self.syslog = "/var/log/syslog"
        elif "redhat" in self.os_level:
            self.syslog = "/var/log/messages"
        cmd = "cat %s |grep 'opal-prd' > /tmp/opal_prd_log" % self.syslog
        self.c.run_command(cmd)

    def is_sbe_interrupt_processed(self):
        cmd = "grep 'opal-prd' %s | diff - /tmp/opal_prd_log" % self.syslog
        for i in range(31):
            self.data = " ".join(self.c.run_command_ignore_fail(cmd))
            if "SBEIO:<< process_sbe_msg" in self.data:
                print "OPAL Processed the SBE interrupt and called HBRT accordingly"
                return True
            time.sleep(2)
        else:
            return False

    def is_sel_sent_to_bmc(self):
        if "IPMI:sel: <<process_esel" in self.data:
            print "HBRT/Host Commited error log and sent to BMC/FSP"
            return True
        return False

    def runTest(self):
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        # Clear any pre-existing SEL or eSEL's
        self.cv_SYSTEM.sys_sdr_clear()
        self.c.run_command("dmesg -D")
        self.cpu = ''.join(self.c.run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/ .*//;'"))

        if self.cpu not in ["POWER9"]:
            self.skipTest("SBE Passthrough Test not supported on %s" % self.cpu)

        # Make sure opal-prd daemon runs before test starts
        self.c.run_command("service opal-prd start")
        self.setup_init()
        for i in range(0, 11):
            for chip in self.chips:
                self.setup_opalprd_logs()
                cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip, self.DOORBELL_REG)
                self.c.run_command(cmd)
                value = "0x0800000000000000"
                cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (chip, self.DOORBELL_REG, value)
                self.c.run_command(cmd)
                self.assertTrue(self.is_sbe_interrupt_processed(), "OPAL Failed to process the SBE Interrupt")
                self.assertTrue(self.is_sel_sent_to_bmc(), "HBRT/Host failed to send the eSEL to MC/SP")
                print self.cv_SYSTEM.sys_get_sel_list() # Verify the eSEL from BMC side as well.
