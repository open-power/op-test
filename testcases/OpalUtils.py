#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpalUtils.py $
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

# @package OpalUtils
#  Test different OPAL Utilities
#  getscom, putscom, gard, pflash
#

import re
import random


from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class OpalUtils(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def utils_init(self):
        self.cv_HOST.host_get_OS_Level()
        chips = self.cv_HOST.host_get_list_of_chips()
        cores = self.cv_HOST.host_get_cores()
        print cores
        i=0
        for tup in cores:
            new_list = [chips[i], tup[1]]
            self.l_dic.append(new_list)
            i+=1
        print self.l_dic

    def disable_cpu_sleepstates(self):
        if self.cpu in ["POWER8", "POWER8E"]:
            self.c.run_command(BMC_CONST.DISABLE_CPU_SLEEP_STATE1)
            self.c.run_command(BMC_CONST.DISABLE_CPU_SLEEP_STATE2)

        if self.cpu in ["POWER9"]:
            pass
            # TODO: Disable stop states here in P9

    def scom_read_operation(self):
        if self.cpu in ["POWER8", "POWER8E"]:
            self.IPOLL_MASK_REGISTER = "0x01020013"

        if self.cpu in ["POWER9"]:
            self.IPOLL_MASK_REGISTER = "0xF0033"

        cmd = "PATH=/usr/local/sbin:$PATH getscom -c 0x0 %s" % self.IPOLL_MASK_REGISTER
        try:
            self.c.run_command(cmd)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("SCOM read operation failed")

    def scom_write_opearation(self):
        # Get random pair of chip vs cores
        l_pair = random.choice(self.l_dic)
        # Get random chip id
        chip = l_pair[0]
        # Get random core number
        core = random.choice(l_pair[1])

        value = "0004080000000000"
        if self.cpu in ["POWER8", "POWER8E"]:
            self.TFMR_PURR_REGISTER = "1%s013281" % core

        if self.cpu in ["POWER9"]:
            self.DOORBELL_REG = "D0063"
            value = "0x0800000000000000"
            cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (chip, self.DOORBELL_REG, value)
            self.c.run_command(cmd)
            return

        cmd = "PATH=/usr/local/sbin:$PATH putscom -c %s %s %s" % (chip, self.TFMR_PURR_REGISTER, value)
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("SCOM write operation failed")

        cmd = "PATH=/usr/local/sbin:$PATH getscom -c %s %s" % (chip, self.TFMR_PURR_REGISTER)
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("SCOM read operation failed")

    def list_gard_records(self):
        cmd = "PATH=/usr/local/sbin:$PATH opal-gard list all"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("List gard records operation failed")

    def clear_gard_records(self):
        cmd = "PATH=/usr/local/sbin:$PATH opal-gard clear all"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("Clear gard records operation failed")

    def flash_info(self):
        cmd = "PATH=/usr/local/sbin:$PATH pflash --info"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("pflash info operation failed")

    def flash_read_part(self):
        cmd = "PATH=/usr/local/sbin:$PATH pflash -r /dev/stdout -P VERSION"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("pflash read PART operation failed")

    def flash_read_guard_part(self):
        cmd = "PATH=/usr/local/sbin:$PATH pflash -r /mnt/gard.bin -P GUARD"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("pflash read GUARD PART operation failed")

    def flash_erase_guard_part(self):
        cmd = "PATH=/usr/local/sbin:$PATH pflash -P GUARD -e -f"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("pflash erase GUARD operation failed")

    def flash_program_guard_part(self):
        cmd = "PATH=/usr/local/sbin:$PATH pflash -p /mnt/gard.bin -P GUARD -e -f"
        try:
            res = self.c.run_command(cmd,timeout=120)
        except CommandFailed as cf:
            print str(cf)
            raise Exception("pflash programme GUARD operation failed")


    ##
    # @brief This testcase performs below steps
    #        1. SCOM Read operation
    #        2. SCOM Write operation
    #        3. List Gard records operation
    #        4. Clear Gard records operation
    #        5. pflash info operation
    #        6. pflash read part operation
    #
    def runTest(self):
        self.l_dic = []
        self.utils_init()
        self.c = self.cv_SYSTEM.console

        self.c.run_command("dmesg -D")
        self.cpu = self.cv_HOST.host_get_proc_gen()

        if self.cpu not in ["POWER8", "POWER8E", "POWER9"]:
            self.skipTest("Unknown CPU type %s" % self.cpu)

        self.disable_cpu_sleepstates()
        self.scom_read_operation()
        self.scom_write_opearation()
        self.list_gard_records()
        self.clear_gard_records()
        self.flash_info()
        self.flash_read_part()
        self.list_gard_records()
        self.flash_read_guard_part()
        self.flash_erase_guard_part()
        self.flash_program_guard_part()
        pass
