#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDlpar.py $
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

'''
OpTestLparFreq
---------------
'''

import unittest
import time
import OpTestConfiguration
from common import OpTestHMC
from common.OpTestSystem import OpSystemState


class OpTestLparFreq(unittest.TestCase):

    failed_test = []

    def check_mode(self, mode):
        output = self.console.run_command("ppc64_cpu --frequency")
        output_mode = output[0].split("Power Savings Mode: ")
        if output_mode[1] != mode:
            self.failed_test.append(mode)
        else:
            print("Change to %s powersave mode is successful" % mode)

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

    def get_freq(self):
        output = self.console.run_command("ppc64_cpu --frequency")
        return output[-2].split()[1]

    def powersaveMode_test(self):

        # This test sets Powersave mode to different available modes and
        # checks whether the mode is changed accordingly in OS.

        self.cv_HMC.run_command("lspwrmgmt -m %s -r sys" % self.system_name)
        self.console.run_command("ppc64_cpu --frequency")
        power_saver_modes = self.cv_HMC.run_command("lspwrmgmt -m %s -r sys -F supported_power_saver_mode_types"
                                                    % self.system_name)
        self.powersave_modes_list = power_saver_modes[0].strip("\"").split(',')
        self.powersave_check_list = ['Static', 'Dynamic, Favor Performance', 'Maximum Performance mode']
        for i in range(3):
            self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                                    (self.system_name, self.powersave_modes_list[i]))
            time.sleep(5)
            self.check_mode(self.powersave_check_list[i])

    def ModeFreq_test(self):

        # This test sets Powersave mode to different available modes and
        # checks whether the frequency chages accordingly.

        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                                (self.system_name, self.powersave_modes_list[0]))
        time.sleep(5)
        static_freq = self.get_freq()
        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                                (self.system_name, self.powersave_modes_list[2]))
        time.sleep(5)
        max_perf_freq = self.get_freq()
        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                                (self.system_name, self.powersave_modes_list[1]))
        time.sleep(5)
        dynamic_freq = self.get_freq()
        print("Average Frequency with Static Powersave mode=%s, Dynamic Performance mode=%s, Maximum Performance mode=%s"
              % (static_freq, dynamic_freq, max_perf_freq))
        if dynamic_freq < static_freq:
            print("Dynamic Performance mode frequency is less than Static Powersave mode frequency")
            self.failed_test.append("Static Powersave mode frequency check failed")
        if max_perf_freq < dynamic_freq:
            print("Maximum Performance mode frequency is less than Dynamic Performance mode frequency")
            self.failed_test.append("Maximum Performance mode frequency check failed")

    def Lpar_shutdown_freq_test(self):

        # This test Set Powersave mode to "Staic Power Saver" mode when lpar is deactivated
        # and check if the frequency is set properly when the lpar boots up

        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o shutdown -n %s" %
                                (self.system_name, self.lpar_name))
        time.sleep(60)
        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" %
                                (self.system_name, self.powersave_modes_list[0]))
        self.cv_HMC.run_command("chsysstate -r lpar -m %s -o on -b norm -n %s" %
                                (self.system_name, self.lpar_name))
        time.sleep(120)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.check_mode(self.powersave_check_list[0])

    def Lpar_Dynamic_freq_test(self):

        # This test Set Powersave mode to "Dynamic Performance Mode" mode and
        # check if frequency is set based on system utilisation.
        # ebizzy url must be defined in ~/.op-test-framework.conf

        self.cv_HMC.run_command("chpwrmgmt -m %s -r sys -o enable -t %s" % (self.system_name, self.powersave_modes_list[1]))
        time.sleep(5)
        freq_before = self.get_freq()
        self.console.run_command("cd /root")
        self.console.run_command("wget %s" % self.url)
        self.console.run_command("tar -xf ebizzy*.tar.gz")
        self.console.run_command("cd /root/ebizzy*/")
        self.console.run_command("./configure")
        self.console.run_command("make")
        self.console.run_command("./ebizzy &")
        freq_after = self.get_freq()
        if freq_before == freq_after:
            self.failed_test.append("Check for frequency change in Dynamic Performance Mode failed")
        else:
            print("In Dynamic Performance Mode LPAR frequency is set based on system utilisation")
        print("System frequency before running workload is %s" % freq_before)
        print("System frequency after running workload is %s" % freq_after)

    def runTest(self):
        self.powersaveMode_test()
        self.ModeFreq_test()
        self.Lpar_shutdown_freq_test()
        self.Lpar_Dynamic_freq_test()
        if self.failed_test:
            self.fail("%s tests failed" % self.failed_test)
