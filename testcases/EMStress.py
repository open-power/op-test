#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

'''
EM Stress tests
---------------
'''

import unittest
import time

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestThread import OpSSHThreadLinearVar1, OpSSHThreadLinearVar2
from common.OpTestSOL import OpSOLMonitorThread
from testcases.OpTestEM import OpTestEM

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class RuntimeEMStress(unittest.TestCase, OpTestEM):
    '''
    Stress test for Energy management/OCC functionalities in FW/OPAL/Linux.
    # tlbie test(IPI stress)
    # CPU Hotplug torture
    # Read frequency loop
    # CPU idle states tests, only one idle state enabled at a time for certain duration
    # CPU Governor change tests
    # OCC Reset reload tests
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.host = conf.host()
        self.torture_time = 780  # 12 hours
        self.bmc_type = conf.args.bmc_type
        self.thread_list = []
        self.tlbie_count = 2
        self.test = "host"

    def runTest(self):

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.console

        self.host.host_check_command("gcc", "cpupower")
        self.host.host_run_command("echo 10 > /proc/sys/kernel/printk")

        # tlbie test(IPI stress)
        # kill any previous existing tlbie_test processes
        self.host.ssh.run_command_ignore_fail("pkill -f /tmp/tlbie_test")
        self.host.copy_test_file_to_host("tlbie_test.c")
        self.host.host_run_command(
            "gcc -pthread -o /tmp/tlbie_test /tmp/tlbie_test.c")
        cmd = "/tmp/tlbie_test &"
        for i in range(self.tlbie_count):
            self.host.host_run_command(cmd)

        # CPU Governor change tests
        torture_time = self.torture_time
        govs = self.get_list_of_governors()[-1].split(" ")
        log.debug(govs)
        cmd_list = []
        for gov in govs:
            if not gov:
                continue
            cmd = "for j in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo %s > $j; done" % gov
            cmd_list.append(cmd)
        num = 1
        thread = OpSSHThreadLinearVar1(
            num, "Thread-%s" % num, cmd_list, 2, torture_time, True)
        thread.start()
        self.thread_list.append(thread)

        # CPU idle states tests, enable only one idle state at a time for certain duration
        torture_time = self.torture_time
        idle_states = self.get_idle_states()
        for i in idle_states:
            self.disable_idle_state(i)
            time.sleep(0.2)
            self.verify_disable_idle_state(i)
        cmd_list = {}
        for i in idle_states:
            cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 0 > $i; done" % i
            cmd_list[cmd] = 1800
            cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 1 > $i; done" % i
            cmd_list[cmd] = 10
        log.debug(cmd_list)

        num = 2
        thread = OpSSHThreadLinearVar2(
            num, "Thread-%s" % num, cmd_list, torture_time, True)
        thread.start()
        self.thread_list.append(thread)

        torture_time = self.torture_time
        # OCC reset reload tests
        cmd_list = {"opal-prd occ reset": 60,
                    "opal-prd --expert-mode htmgt-passthru 4": 10}
        num = 3
        thread = OpSSHThreadLinearVar2(
            num, "Thread-%s" % num, cmd_list, torture_time, True)
        thread.start()
        self.thread_list.append(thread)

        # CPU Hotplug torture
        torture_time = self.torture_time
        num_avail_cores = self.host.host_get_core_count()
        smt_range = ["on", "off"] + list(range(1, self.host.host_get_smt()+1))
        log.debug("Possible smt values: %s" % smt_range)
        cmd_list = []
        for smt in smt_range:
            cmd_list.append("ppc64_cpu --smt=%s" % str(smt))
            for core in range(1, num_avail_cores + 1):
                cmd_list.append("ppc64_cpu --cores-on=%s" % core)
        num = 4
        thread = OpSSHThreadLinearVar1(
            num, "Thread-%s" % num, cmd_list, 5, torture_time, True)
        thread.start()
        self.thread_list.append(thread)

        # Read frequency
        torture_time = self.torture_time
        cmd_list = ['ppc64_cpu --frequency']
        num = 5
        thread = OpSSHThreadLinearVar1(
            num, "Thread-%s" % num, cmd_list, 2, torture_time, True)
        thread.start()
        self.thread_list.append(thread)

        # Monitor for errors
        num = 6
        torture_time = self.torture_time
        thread = OpSOLMonitorThread(num, "Thread-%s" %
                                    num, execution_time=torture_time)
        thread.start()
        self.thread_list.append(thread)

    def tearDown(self):
        # wait for all the threads to finish
        for thread in self.thread_list:
            thread.join()
