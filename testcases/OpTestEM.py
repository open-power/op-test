#!/usr/bin/python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestEM.py $
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

#  @package OpTestEM
#  Energy Management package for OpenPower testing.
#
#  This class will test the functionality of following drivers
#  1. powernv cpuidle driver
#  2. powernv cpufreq driver

import time
import subprocess
import re
import random
import decimal

import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
from common.OpTestIPMI import IPMIConsoleState


class OpTestEM():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.util = OpTestUtil()
        self.ppc64cpu_freq_re = re.compile(r"([a-z]+):\s+([\d.]+)")

    def set_up(self):
        if self.test == "skiroot":
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.cv_SYSTEM.sys_get_ipmi_console()
            self.cv_SYSTEM.host_console_unique_prompt()
            if self.c.state == IPMIConsoleState.DISCONNECTED:
                self.c = self.cv_SYSTEM.sys_get_ipmi_console()
                self.cv_SYSTEM.host_console_unique_prompt()
            # if sol console drops in b/w
            elif not self.c.sol.isalive():
                print "Console is not active"
                self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        elif self.test == "host":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.c = self.cv_HOST.get_ssh_connection()
        else:
            raise Exception("Unknow test type")
        return self.c

    def tear_down(self):
        if self.test == "skiroot":
            self.c.close()
        elif self.test == "host":
            self.c.terminate()

    def get_first_available_cpu(self):
        cmd = "cat /sys/devices/system/cpu/present | cut -d'-' -f1"
        res = self.c.run_command(cmd)
        return res[0]

    ##
    # @brief sets the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency of cpu to be set
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def set_cpu_freq(self, i_freq):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo %s > $i; done" % i_freq
        self.c.run_command(l_cmd)

    ##
    # @brief verify the cpu frequency with i_freq value
    #
    # @param i_freq @type str: this is the frequency to be verified with cpu frequency
    def verify_cpu_freq(self, i_freq, and_measure=True):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.c.run_command(l_cmd)
        if not cur_freq[0] == i_freq:
            # (According to Vaidy) it may take milliseconds to have the
            # request for a frequency change to come into effect.
            # So, if we happen to be *really* quick checking the result,
            # we may have checked before it has taken effect. So, we
            # sleep for a (short) amount of time and retry.
            time.sleep(0.2)
            cur_freq = self.c.run_command(l_cmd)

        self.assertEqual(cur_freq[0], i_freq,
                         "CPU frequency not changed to %s" % i_freq)
        if not and_measure:
            return
        frequency_output = self.c.run_command("ppc64_cpu --frequency")
        freq = {}
        for f in frequency_output:
            m = re.match(self.ppc64cpu_freq_re, f)
            if m:
                freq[m.group(1)] = int(decimal.Decimal(m.group(2)) * 1000000)
        # Frequencies are in KHz
        print repr(freq)
        self.assertAlmostEqual(freq["min"], freq["max"], delta=(freq["avg"]/100),
                               msg="ppc64_cpu measured CPU Frequency differs between min/max when frequency set explicitly")
        self.assertAlmostEqual(freq["avg"], freq["max"], delta=(freq["avg"]/100),
                               msg="ppc64_cpu measured CPU Frequency differs between avg/max when frequency set explicitly")

        delta = int(i_freq) / (100)
        print "Set %d, Measured %d, Allowed Delta %d" % (int(i_freq),freq["avg"],delta)

        self.assertAlmostEqual(freq["avg"], int(i_freq), delta=delta,
                               msg="Set and measured CPU frequency differ too greatly")


    ##
    # @brief sets the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be set for all cpu's
    def set_cpu_gov(self, i_gov):
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo %s > $i; done" % i_gov
        self.c.run_command(l_cmd)

    ##
    # @brief verify the cpu governer with i_gov governer
    #
    # @param i_gov @type str: this is the governer to be verified with cpu governer
    def verify_cpu_gov(self, i_gov):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        cur_gov = self.c.run_command(l_cmd)
        self.assertEqual(cur_gov[0], i_gov, "CPU governor not changed to %s" % i_gov)

    ##
    # @brief enable cpu idle state i_idle
    #
    # @param i_idle @type str: this is the cpu idle state to be enabled
    def enable_idle_state(self, i_idle):
        if self.test == "host":
            l_cmd = "cpupower idle-set -e %s" % i_idle
        elif self.test == "skiroot":
            l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 0 > $i; done" % i_idle
        self.c.run_command(l_cmd)

    ##
    # @brief disable cpu idle state i_idle
    #
    # @param i_idle @type str: this is the cpu idle state to be disabled
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def disable_idle_state(self, i_idle):
        if self.test == "host":
            l_cmd = "cpupower idle-set -d %s" % i_idle
        elif self.test == "skiroot":
            l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 1 > $i; done" % i_idle
        self.c.run_command(l_cmd)

    ##
    # @brief verify whether cpu idle state i_idle enabled
    #
    # @param i_idle @type str: this is the cpu idle state to be verified for enable
    def verify_enable_idle_state(self, i_idle):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.c.run_command(l_cmd)
        self.assertEqual(cur_value[0], "0", "CPU state%s not enabled" % i_idle)

    ##
    # @brief verify whether cpu idle state i_idle disabled
    #
    # @param i_idle @type str: this is the cpu idle state to be verified for disable
    def verify_disable_idle_state(self, i_idle):
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.c.run_command(l_cmd)
        self.assertEqual(cur_value[0], "1", "CPU state%s not disabled" % i_idle)


class slw_info(OpTestEM, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(slw_info, self).setUp()

    # @brief This function just gathers the host CPU SLW info
    def runTest(self):
        self.c = self.set_up()
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")

        proc_gen = self.cv_HOST.host_get_proc_gen()
        if proc_gen in ["POWER8", "POWER8E"]:
            self.c.run_command("hexdump -c /proc/device-tree/ibm,enabled-idle-states")
        try:
            if proc_gen in ["POWER8", "POWER8E"]:
                self.c.run_command("cat /sys/firmware/opal/msglog | grep -i slw")
            elif proc_gen in ["POWER9"]:
                self.c.run_command("cat /sys/firmware/opal/msglog | grep -i stop")
        except CommandFailed as cf:
            pass # we may have no slw entries in msglog
        self.tear_down()


class cpu_freq_states_host(OpTestEM, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(cpu_freq_states_host, self).setUp()

    NR_FREQUENCIES_SET = 100
    NR_FREQUENCIES_VERIFIED = 10
    # @brief This function will cover following test steps
    #        2. Check the cpupower utility is available in host.
    #        3. Get available cpu scaling frequencies
    #        4. Set the userspace governer for all cpu's
    #        5. test the cpufreq driver by set/verify cpu frequency
    def runTest(self):
        self.c = self.set_up()
        self.c.run_command("stty cols 300;stty rows 30")
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")

        cpu_num = self.get_first_available_cpu()

        # Check cpufreq driver enabled
        self.c.run_command("ls /sys/devices/system/cpu/cpu%s/cpufreq/" % cpu_num)

        # Get available cpu scaling frequencies
        l_res = self.c.run_command("cat /sys/devices/system/cpu/cpu%s/cpufreq/scaling_available_frequencies" % cpu_num)
        print l_res
        freq_list = l_res[0].split(' ')[:-1] # remove empty entry at end
        print freq_list

        # Set the cpu governer to userspace
        self.set_cpu_gov("userspace")
        self.verify_cpu_gov("userspace")
        for i_freq in freq_list:
            self.set_cpu_freq(i_freq)
            self.verify_cpu_freq(i_freq, False)
        for i in range(1, self.NR_FREQUENCIES_VERIFIED):
            i_freq = random.choice(freq_list)
            self.set_cpu_freq(i_freq)
            self.verify_cpu_freq(i_freq, True)
        self.tear_down()
        pass

class cpu_freq_states_skiroot(cpu_freq_states_host):
    def setUp(self):
        self.test = "skiroot"
        super(cpu_freq_states_host, self).setUp()

class cpu_idle_states_host(OpTestEM, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(cpu_idle_states_host, self).setUp()

    ##
    # @brief This function will cover following test steps
    #        1. It will get the OS and kernel versions.
    #        2. Check the cpupower utility is available in host.
    #        3. Set the userspace governer for all cpu's
    #        4. test the cpuidle driver by enable/disable/verify the idle states
    def runTest(self):
        self.c = self.set_up()
        self.c.run_command("stty cols 300;stty rows 30")
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        cpu_num = self.get_first_available_cpu()

        # Check cpuidle driver enabled
        try:
            self.c.run_command("ls /sys/devices/system/cpu/cpu%s/cpuidle/" % cpu_num)
        except CommandFailed:
            self.assertTrue(False, "cpuidle driver is not enabled in kernel")

        # TODO: Check the runtime idle states = expected idle states!
        idle_states = self.c.run_command("find /sys/devices/system/cpu/cpu*/cpuidle/state* -type d | cut -d'/' -f8 | sort -u | sed -e 's/^state//'")
        print repr(idle_states)
        # currently p8 cpu has 3 states
        for i in idle_states:
            self.enable_idle_state(i)
            self.verify_enable_idle_state(i)
        for i in idle_states:
            self.disable_idle_state(i)
            self.verify_disable_idle_state(i)
        # and reset back to enabling idle.
        for i in idle_states:
            self.enable_idle_state(i)
            self.verify_enable_idle_state(i)

        self.tear_down()
        pass

class cpu_idle_states_skiroot(cpu_idle_states_host):
    def setUp(self):
        self.test = "skiroot"
        super(cpu_idle_states_host, self).setUp()


def host_suite():
    s = unittest.TestSuite()
    s.addTest(slw_info())
    s.addTest(cpu_freq_states_host())
    s.addTest(cpu_idle_states_host())
    return s

def skiroot_suite():
    s = unittest.TestSuite()
    s.addTest(cpu_freq_states_skiroot())
    s.addTest(cpu_idle_states_skiroot())
    return s
