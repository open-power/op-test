#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestLparFreq $
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
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestLparFreq(unittest.TestCase):

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
        self.url = conf.args.url


    def get_cpu_freq(self):
        output = self.console.run_command("ppc64_cpu --frequency")
        return output[-1].split()[2]


    def powersaveMode_test(self):

        # This test sets Powersave mode to different available modes and
        # checks whether the mode is changed accordingly in OS.

        self.cv_HMC.run_command("lspwrmgmt -m %s -r sys" % self.system_name)
        power_saver_modes = self.cv_HMC.run_command("lspwrmgmt -m %s -r sys -F supported_power_saver_mode_types"
                                                    % self.system_name)
        self.powersave_modes_list = power_saver_modes[0].strip("\"").split(',')
        self.powersave_check_list = ['Static', 'Power Saving', 'Maximum Performance']
        for i in range(3):
            self.set_powersave_mode(self.powersave_modes_list[i])
            time.sleep(5)
            self.check_powersave_mode(self.powersave_check_list[i])


    def ModeFreq_test(self):

        # This test sets Powersave mode to different available modes and
        # checks whether the frequency chages accordingly.
        # Verifies if Average frequency matches with Platform reported frequency.
        # Verifies if frequency is maximum in maximum Performance mode and least in powersave mode.

        powersave_freq_list = []
        for i in range(3):
            self.set_powersave_mode(self.powersave_modes_list[i])
            time.sleep(5)
            powersave_freq_list.append(self.get_cpu_freq())
        for i in range(3):
            log.info("Average Frequency in %s mode = %s" %
                     (self.powersave_modes_list[i], powersave_freq_list[i]))
        powersave_plat_freq_list = []
        output = self.console.run_command("ppc64_cpu --frequency")
        for i in range(3, 6):
            powersave_plat_freq_list.append(output[i].split()[2])
        log.info("Platform reported frequency for [ powersave, max, static ] = %s" %
                 powersave_plat_freq_list)
        j = [2, 0, 1]
        for i in range(3):
            if round(float(powersave_freq_list[i]), 1) != round(float(powersave_plat_freq_list[j[i]]), 1):
                log.info("Static mode frequency test failed")
                self.failed_test.append("%s mode frequency test failed" % self.powersave_modes_list[i])
            else:
                log.info("Average frequency matches with Platform reported frequency for %s mode" %
                         self.powersave_modes_list[i])
        if powersave_freq_list[0] < powersave_freq_list[1]:
            log.info("Static mode frequency is less than Powersave mode frequency")
            self.failed_test.append("Frequency is not least with Powersave mode.")
        if powersave_freq_list[2] < powersave_freq_list[0]:
            log.info("Maximum Performance mode frequency is less than Static mode frequency.")
            self.failed_test.append("Frequency is not maximum with maximum Performance mode.")


    def Lpar_shutdown_freq_test(self):

        # This test Set Powersave mode to "Staic Power Saver" mode when lpar is deactivated
        # and check if the frequency is set properly when the lpar boots up

        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o shutdown -n %s" %
                                (self.system_name, self.lpar_name))
        time.sleep(60)
        self.set_powersave_mode(self.powersave_modes_list[0])
        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -b norm -n %s" %
                                (self.system_name, self.lpar_name))
        time.sleep(120)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.check_powersave_mode(self.powersave_check_list[0])


    def Lpar_freq_test_workload(self):

        # This test sets Powersave mode to different powersave modes and verifies frequency with
        # ebizzy workload.
        # ebizzy url must be defined in ~/.op-test-framework.conf

        res = self.console.run_command("cat /etc/os-release")
        if 'Red Hat' in res[0] or 'Red Hat' in res[1]:
            self.console.run_command("yum -y install wget make gcc")
        elif 'SLES' in res[0] or 'SLES' in res[1]:
            self.console.run_command("zypper install -y wget make gcc")
        if not self.url:
            raise self.skipTest("Provide ebizzy url in op-test-framework.conf")
        try:
            self.console.run_command("wget %s -P /tmp" % self.url)
        except CommandFailed:
            self.fail("Failed to download ebizzy tar")
        self.console.run_command("tar -xf /tmp/ebizzy*.tar.gz -C /tmp")
        self.console.run_command("cd /tmp/ebizzy*/")
        try:
            self.console.run_command("./configure; make")
        except CommandFailed:
            self.fail("Failed to compile ebizzy")
        for i in range(3):
            self.set_powersave_mode(self.powersave_modes_list[i])
            time.sleep(5)
            freq_before = self.get_cpu_freq()
            self.console.run_command("./ebizzy -S 60&")
            time.sleep(10)
            freq_after = self.get_cpu_freq()
            self.console.run_command("pkill ebizzy; ps -ef|grep ebizzy")
            if round(float(freq_before), 1) != round(float(freq_after), 1):
                self.failed_test.append("Check for frequency change with workload failed")
            else:
                log.info("Frequency check with workload is as expected")
            log.info("System frequency before running workload is %s for %s mode" %
                    (freq_before, self.powersave_modes_list[i]))
            log.info("System frequency after running workload is %s for %s mode" %
                    (freq_after, self.powersave_modes_list[i]))


    def Lpar_freq_test_smt(self):

        #This test verifies frequency with different SMT modes in all powersave modes.

        for i in range(3):
             self.set_powersave_mode(self.powersave_modes_list[i])
             time.sleep(5)
             freq_before = self.get_cpu_freq()
             for j in [2, 4, 1]:
                 self.console.run_command("ppc64_cpu --smt=%s" % j)
                 freq_after = self.get_cpu_freq()
                 if round(float(freq_before), 1) != round(float(freq_after), 1):
                     self.failed_test.append("Check for frequency with smt=%s mode failed in %s powersave mode" %
                                            (j, self.powersave_modes_list[i]))
                 else:
                     log.info("Frequency check with smt=%s is working as expected in %s powersave mode" %
                             (j, self.powersave_modes_list[i]))


    def runTest(self):
        self.powersaveMode_test()
        self.ModeFreq_test()
        self.Lpar_shutdown_freq_test()
        self.Lpar_freq_test_workload()
        self.Lpar_freq_test_smt()
        if self.failed_test:
            self.fail("%s tests failed" % self.failed_test)
