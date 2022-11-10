#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEnergyd $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2022
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
OpTestLparFreq
---------------
'''

import unittest
import time
import OpTestConfiguration
import OpTestLogger

from common import OpTestHMC
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestEnergyd(unittest.TestCase):

    failed_test = []

    def check_powersave_mode(self, mode):
        output = self.console.run_command("ppc64_cpu --frequency")
        output_mode = output[0].split("Power and Performance Mode: ")
        if output_mode[1] != mode:
            self.failed_test.append(mode)
        else:
            log.info("Change to %s powersave mode is successful" % mode)


    def set_powersave_mode(self, mode):
        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                               (self.system_name, mode))

    def get_online_core_count(self):
        cores_online = ((self.console.run_command("ppc64_cpu --cores-on"))[0].split())[5]
        return(cores_online)

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.console = self.cv_SYSTEM.console
        self.hmc_user = conf.args.hmc_username
        self.hmc_password = conf.args.hmc_password
        self.hmc_ip = conf.args.hmc_ip
        self.lpar_name = conf.args.lpar_name
        self.system_name = conf.args.system_name
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.energyd_url = conf.args.energyd_url


    def energyd_service_test(self):

        # This test install pseries-energy package.
        # Starts energyd service and checks if it is active.

        if 'Dedicated' != (self.console.run_command("lparstat -i | grep Type")[0].split())[2]:
            self.skipTest("Test is supported only in dedicated mode")
        self.total_cores = ((self.console.run_command("ppc64_cpu --cores-present"))[0].split())[5]
        if int(self.total_cores) < 3:
            self.skipTest("Test need lpar with atleast 3 cores.")
        self.console.run_command("rpm -ivh %s --force" % self.energyd_url)
        self.console.run_command("service energyd start")
        if "running" not in (self.console.run_command("service energyd status | grep active"))[1]:
            self.fail("Service check failed")

    def energyd_function_test(self):

        # This test verifies functionality of energyd service.
        # Verifies if the number of online cores reduces to 2 when service is active in powersave mode.

        self.set_powersave_mode("power_saving")
        self.check_powersave_mode('Power Saving')
        time.sleep(5)
        self.console.run_command("service energyd stop")
        time.sleep(60)
        cores_online = self.get_online_core_count()
        if self.total_cores != cores_online:
            self.failed_test.append("All cores are not online even when energyd is not active.")
        self.console.run_command("service energyd start")
        time.sleep(60)
        cores_online = self.get_online_core_count()
        if int(cores_online) > 2:
            self.failed_test.append("More than 2 cores are online even when energyd is active.")
        self.console.run_command("service energyd stop")
        cores_online = self.get_online_core_count()
        if self.total_cores != cores_online:
            self.failed_test.append("All cores are not online even when energyd is not active.")
        self.console.run_command("service energyd start")

    def energyd_powersave_test(self):

        # This test verifies that all cores are online in max performance mode even if service is active.

        self.set_powersave_mode("max_perf")
        cores_online = self.get_online_core_count()
        time.sleep(60)
        if self.total_cores != cores_online:
            self.failed_test.append("All cores are not online even with maximum performance mode.")
        self.set_powersave_mode("power_saving")
        time.sleep(60)
        cores_online = self.get_online_core_count()
        if int(cores_online) > 2:
            self.failed_test.append("More than 2 cores are online in powersave mode even when energyd is active.")

    def runTest(self):
        self.energyd_service_test()
        self.energyd_function_test()
        self.energyd_powersave_test()

        if self.failed_test:
            self.fail("%s tests failed" % self.failed_test)
