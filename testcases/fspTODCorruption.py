#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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
FSP TOD Corruption
------------------

Corrupt TOD and check host boot and runtime behaviours
'''

import time
import subprocess
import re
import commands

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestSSH import ConsoleState as SSHConnectionState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class fspTODCorruption():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()

    def get_tod(self):
        log.debug("Running command on FSP: rtim timeofday")
        res = self.cv_FSP.fsp_run_command("rtim timeofday")
        return res

    def set_tod(self):
        time = commands.getoutput('date +"%Y%m%d%H%M%S"')
        log.debug("Setting back the system time using rtim timeofday ")
        cmd = "rtim timeofday %s" % time
        log.debug("Running command on FSP: %s" % cmd)
        self.cv_FSP.fsp_run_command(cmd)
        self.get_tod()

    def tod_force_clock(self):
        res = self.get_tod()
        if "valid" in res:
            log.debug("system time is VALID")
        else:
            raise Exception("System time is invalid,exiting..., "
                            "please set time and rerun")

        log.debug("Running command on FSP: rtim forceClockValue")
        out = self.cv_FSP.fsp_run_command("rtim forceClockValue")
        log.debug(out)
        res = self.get_tod()
        if "INVALID" in res:
            log.debug("system time is INVALID")
        else:
            raise Exception("rtim: forceClockValue interface not forcing "
                            "tod value to invalid")

    def check_hwclock(self):
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_set_hwclock_time("2015-01-01 10:10:10")
        self.cv_HOST.host_read_hwclock()
        self.cv_HOST.host_set_hwclock_time("2016-01-01 20:20:20")
        self.cv_HOST.host_read_hwclock()


class TOD_CORRUPTION(fspTODCorruption, unittest.TestCase):
    '''
    This function tests Boot and runtime behaviour when TOD is corrupted.
    '''
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific TOD Corruption tests")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        state = self.cv_FSP.fsp_run_command("smgr mfgState")
        log.debug(state)
        self.cv_FSP.clear_fsp_errors()
        self.tod_force_clock()
        self.check_hwclock()
        self.tearDown()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.check_hwclock()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.set_tod()
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.check_hwclock()


def suite():
    s = unittest.TestSuite()
    s.addTest(TOD_CORRUPTION())
    return s
