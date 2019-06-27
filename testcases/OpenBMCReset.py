#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpenBMCReset.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2019
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
OpenBMC reboot and Host stress test
-----------------------------------
This testcase does OpenBMC reboot and Host-BMC interface testing.
 - OpenBMC reboot and Host reboot
 - OpenBMC reboot and Host shutdown
 - OpenBMC reboot and Host-BMC interface test (like flash reading, OCC reset)

'''

import time
import subprocess
import subprocess
import re
import sys

import unittest
import OpTestConfiguration

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpenBMCRebootHostReboot(unittest.TestCase):
    '''
    Reboot BMC and then trigger Host reboot
    '''
    @classmethod
    def setUpClass(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_BMC = self.cv_SYSTEM.bmc
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def number_of_iteration(self):
        return 1

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific reboot tests")
        for i in range(0, self.number_of_iteration()):
            log.info("OpenBMC: BMC reboot - Host reboot iteration {}".format(i))
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            log.info("Sending reboot command to BMC")
            self.cv_BMC.reboot_nowait()
            log.info("Sending reboot command to Host")
            self.c.run_command_ignore_fail("reboot")
            log.info("Waiting for BMC to reach runtime")
            self.cv_REST.wait_for_bmc_runtime()
            log.info("Waiting for Host to reach runtime")
            self.cv_REST.wait_for_runtime()
            log.info("Host ping test")
            self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.CMD_RETRY_BMC)


class OpenBMCRebootHostRebootTorture(OpenBMCRebootHostReboot):
    def number_of_iteration(self):
        return 10


class OpenBMCRebootHostShutdown(unittest.TestCase):
    '''
    Reboot BMC and then trigger Host shutdown
    '''
    @classmethod
    def setUpClass(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_BMC = self.cv_SYSTEM.bmc
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def number_of_iteration(self):
        return 1

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific reboot tests")
        for i in range(0, self.number_of_iteration()):
            log.info("OpenBMC: BMC reboot - Host shutdown iteration {}".format(i))
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            log.info("Sending reboot command to BMC")
            self.cv_BMC.reboot_nowait()
            log.info("Sending shutdown command to Host")
            self.c.run_command_ignore_fail("shutdown")
            log.info("Waiting for BMC to reach runtime")
            self.cv_REST.wait_for_bmc_runtime()
            log.info("Waiting for Host to reach standby state")
            self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.CMD_RETRY_BMC)


class OpenBMCRebootHostShutdownTorture(OpenBMCRebootHostShutdown):
    def number_of_iteration(self):
        return 10


class OpenBMCRebootHostTests(unittest.TestCase):
    '''
    Reboot BMC and then run Host-BMC interface tests
    '''
    @classmethod
    def setUpClass(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_BMC = self.cv_SYSTEM.bmc
        self.cv_REST = self.cv_BMC.get_rest_api()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def number_of_iteration(self):
        return 1

    def runTest(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("OpenBMC specific reboot tests")
        for i in range(0, self.number_of_iteration()):
            log.info("OpenBMC: BMC reboot - Host tests iteration {}".format(i))
            self.cv_REST.wait_for_bmc_runtime()
            self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            self.c.run_command("dmesg -C")

            log.info("Sending reboot command to BMC")
            self.cv_BMC.reboot_nowait()

            log.info("Running opal-prd tests")
            self.c.run_command_ignore_fail(
                "/bin/systemctl restart opal-prd.service")
            self.c.run_command_ignore_fail(
                "/bin/systemctl status opal-prd.service ")

            log.info("Running OCC tests")
            self.c.run_command_ignore_fail(BMC_CONST.OCC_RESET)
            self.c.run_command_ignore_fail(BMC_CONST.OCC_ENABLE)
            self.c.run_command_ignore_fail(BMC_CONST.OCC_DISABLE)
            self.c.run_command_ignore_fail(BMC_CONST.OCC_ENABLE)

            log.info("Running pflash tests")
            self.c.run_command_ignore_fail("pflash --info")
            self.c.run_command_ignore_fail("pflash -P GUARD -r /dev/null")

            log.info("Running IPMI tests")
            self.c.run_command_ignore_fail("ipmitool mc info")

            log.info("Validating dmesg output")
            error = False
            msg = None
            try:
                msg = self.c.run_command("dmesg -r|grep '<[21]>'")
                error = True
            except CommandFailed as cf:
                pass
            self.assertFalse(error,
                             "Critical errors in Kernel log:\n%s" % msg)


class OpenBMCRebootHostTestsTorture(OpenBMCRebootHostTests):
    def number_of_iteration(self):
        return 10
