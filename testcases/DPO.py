#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDPO.py $
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

#  @package DPO.py
#       Delayed Power off testcase is to test OS graceful shutdown request
#       to be notified from OPAL and OS should process the request.
#       We will use "ipmitool power soft" command to issue DPO.

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import pexpect
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class Base(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util


class DPOSkiroot(Base):

    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()
        self.host = "Skiroot"

    ##
    # @brief This will test DPO feature in skiroot and Host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        self.setup_test()
        self.c.run_command("uname -a")
        if self.host == "Host":
            self.cv_SYSTEM.load_ipmi_drivers(True)
        self.c.sol.sendline("ipmitool power soft")
        try:
            rc = self.c.sol.expect_exact(["reboot: Power down",
                                          "Power down",
                                          "Invalid command",
                                          "Unspecified error"
                                      ], timeout=120)
            self.assertIn(rc, [0, 1], "Failed to power down")
        except pexpect.TIMEOUT:
            raise OpTestError("Soft power off not happening")
        rc = self.cv_SYSTEM.sys_wait_for_standby_state()
        print rc
        self.cv_SYSTEM.set_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

class DPOHost(DPOSkiroot):
    def setup_test(self):
        self.host = "Host"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
