#!/usr/bin/env python3
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

'''
SbePassThrough
--------------

Test case for SBE passthrough
'''


import unittest
import time

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class SbePassThrough(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def setup_init(self):
        self.c.run_command("dmesg -D")
        self.cpu = ''.join(self.c.run_command(
            "grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))

        if self.cpu not in ["POWER9"]:
            self.skipTest(
                "SBE passthrough test not supported on %s" % self.cpu)

        if self.cpu == "POWER9":
            self.DOORBELL_REG = "D0063"
        self.os_level = self.cv_HOST.host_get_OS_Level()
        self.chips = self.cv_HOST.host_get_list_of_chips()

    def setup_opalprd_logs(self):
        self.prd_log_cmd = "journalctl -t opal-prd -p 7"
        self.c.run_command("%s  > /tmp/opal_prd_log" % self.prd_log_cmd)

    def is_sbe_interrupt_processed(self):
        cmd = "%s | diff -a /tmp/opal_prd_log -" % self.prd_log_cmd
        for i in range(31):
            self.data = " ".join(self.c.run_command_ignore_fail(cmd))
            if "SBEIO:<< process_sbe_msg" in self.data:
                log.debug(
                    "OPAL Processed the SBE interrupt and called HBRT accordingly")
                return True
            time.sleep(2)
        else:
            return False

    def is_sel_sent_to_bmc(self):
        if "IPMI:sel: <<process_esel" in self.data:
            log.debug("HBRT/Host Commited error log and sent to BMC/FSP")
            return True
        return False

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.console
        # Clear any pre-existing SEL or eSEL's
        self.cv_SYSTEM.sys_sdr_clear()
        self.c.run_command("dmesg -D")

        # Make sure opal-prd daemon runs before test starts
        try:
            start_res = self.c.run_command("service opal-prd start")
            log.debug("start_res={}".format(start_res))
            pid_res = self.c.run_command("pidof opal-prd")
            log.debug("pid_res={}".format(pid_res))
        except Exception as e:
            log.debug("Unable to start opal-prd.service or keep opal-prd running,"
                      " unable to run test, Exception={}".format(e))
            self.assertTrue(False, "Unable to start opal-prd.service or keep "
                            "opal-prd running, unable to run test, raise a bug {}".format(e))
        self.setup_init()
        for i in range(0, 2):
            for chip in self.chips:
                self.setup_opalprd_logs()
                cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (
                    chip, self.DOORBELL_REG)
                self.c.run_command(cmd)
                value = "0x0800000000000000"
                cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (
                    chip, self.DOORBELL_REG, value)
                self.c.run_command(cmd)
                self.assertTrue(self.is_sbe_interrupt_processed(),
                                "OPAL Failed to process the SBE Interrupt")
                self.assertTrue(self.is_sel_sent_to_bmc(),
                                "HBRT/Host failed to send the eSEL to MC/SP")
                log.debug(self.cv_SYSTEM.sys_get_sel_list())
                sels = " ".join(self.c.run_command("ipmitool sel list"))
                if 'SEL has no entries' in sels:
                    self.assertTrue(False, "SP/MC is failed to log eSEL")
                elif "OEM record df | 040020" in sels:
                    log.debug("SEL is properly committed and logged by SP/MC")
