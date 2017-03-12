#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpalErrorLog.py $
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

#  @package OpalErrorLog
#  Currently runs only in FSP platforms
#

import time
import subprocess
import re

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class OpalErrorLog(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()


    ##
    # @brief This function tests OpalErrorLog component
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL Error log tests")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        # Check status of opal_errd daemon before running the test
        if not self.cv_HOST.host_get_status_of_opal_errd_daemon():
            self.cv_HOST.host_stop_opal_errd_daemon()
            self.cv_HOST.host_start_opal_errd_daemon()
        self.assertTrue(self.cv_HOST.host_get_status_of_opal_errd_daemon(),
                "opal_errd daemon is failed to start")

        # Clear previous existing logs in Host and FSP before start of the test
        self.cv_FSP.clear_errorlogs_in_fsp()
        self.cv_HOST.host_clear_error_logs()
        count = 100
        # Start Generating the error logs from FSP.
        print "FSP: Start generating the error logs from FSP."
        for i in range(count+1):
            print "=====================================Iteration: %d=====================================" % i
            self.cv_FSP.generate_error_log_from_fsp()
            self.cv_HOST.host_list_all_errorlogs()
            self.cv_HOST.host_list_all_service_action_logs()

        res = self.cv_HOST.host_get_number_of_errorlogs()
        transfer_complete = False
        tries = 60
        for j in range(tries+1):
            res = self.cv_HOST.host_get_number_of_errorlogs()
            if res >= count:
                transfer_complete = True
                break
            time.sleep(1)
            print "Waiting for transfer of error logs to Host: (%d\%d)" % (j, tries)
        self.assertTrue(transfer_complete, "Failed to transfer all error logs to Host in a minute")
        self.cv_FSP.clear_errorlogs_in_fsp()
        print "OpalErrorLog test executed successfully"
