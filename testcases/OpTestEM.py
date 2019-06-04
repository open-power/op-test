#!/usr/bin/env python3
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

'''
OpTestEM
--------

Energy Management package for OpenPower testing.

This class will test the functionality of following drivers:

1. powernv cpuidle driver
2. powernv cpufreq driver
'''

import time
import subprocess
import re
import random
import decimal

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
from common.OpTestIPMI import IPMIConsoleState
import common.OpTestQemu as OpTestQemu
from testcases.DeviceTreeValidation import DeviceTreeValidation

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestEM():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.ppc64cpu_freq_re = re.compile(r"([a-z]+):\s+([\d.]+)")
        self.c = None  # use this for tearDown

    def set_up(self):
        self.c = None  # clear this, we may not get back from goto and tearDown relies on
        if self.test == "skiroot":
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c = self.cv_SYSTEM.console
        elif self.test == "host":
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            self.c = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        else:
            raise Exception("Unknown test type")
        return self.c

    def tearDown(self):
        if self.c == None:  # unable to proceed
            return

        cpu_num = self.get_first_available_cpu()
        # Check cpufreq driver enabled
        cpufreq = False
        try:
            self.c.run_command(
                "ls --color=never /sys/devices/system/cpu/cpu%s/cpufreq/" % cpu_num)
            cpufreq = True
        except CommandFailed:
            pass
        # return back to sane cpu governor
        if cpufreq:
            self.set_cpu_gov("powersave")

        # Check cpuidle driver enabled
        cpuidle = False
        try:
            self.c.run_command(
                "ls --color=never /sys/devices/system/cpu/cpu%s/cpuidle/" % cpu_num)
            cpuidle = True
        except CommandFailed:
            pass

        if not cpuidle:
            return
        # and then re-enable all idle states
        idle_states = self.get_idle_states()
        for i in idle_states:
            self.enable_idle_state(i)

    def get_idle_states(self):
        return self.c.run_command("find /sys/devices/system/cpu/cpu*/cpuidle/state* -type d | cut -d'/' -f8 | sort -u | sed -e 's/^state//'")

    def get_first_available_cpu(self):
        cmd = "cat /sys/devices/system/cpu/present | cut -d'-' -f1"
        try:
            res = self.c.run_command(cmd)
            return res[0]
        except Exception as e:
            raise e

    def get_list_of_cpu_freq(self):
        '''
        Get available cpu scaling frequencies
        '''
        l_res = self.c.run_command(
            "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies")
        freq_list = l_res[0].split(' ')[:-1]  # remove empty entry at end
        log.debug(freq_list)
        return freq_list

    def set_cpu_freq(self, i_freq):
        '''
        Run a command on the host to set CPU frequency on all CPUs.
        '''
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo %s > $i; done" % i_freq
        self.c.run_command(l_cmd)

    def verify_cpu_freq(self, i_freq, and_measure=True):
        '''
        Verify the CPU frequency is set to the value we ask for. If `and_measure` is True,
        we use `ppc64_cpu --frequency` to verify it rather than just checking sysfs.

        When measuring CPU frequency, we allow a bit of error in measurement.
        '''
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
        log.debug(repr(freq))
        delta = int(i_freq) / (100)
        log.debug("# Set %d, Measured %d, Allowed Delta %d" %
                  (int(i_freq), freq["avg"], delta))
        self.assertAlmostEqual(freq["min"], freq["max"], delta=(freq["avg"]/100),
                               msg="ppc64_cpu measured CPU Frequency differs between min/max when frequency set explicitly")
        self.assertAlmostEqual(freq["avg"], freq["max"], delta=(freq["avg"]/100),
                               msg="ppc64_cpu measured CPU Frequency differs between avg/max when frequency set explicitly")

        self.assertAlmostEqual(freq["avg"], int(i_freq), delta=delta,
                               msg="Set and measured CPU frequency differ too greatly")

    def verify_cpu_freq_almost(self, i_freq):
        '''
        This function verifies CPU frequency against a single or list of frequency's provided
        '''
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq"
        cur_freq = self.c.run_command(l_cmd)

        if not type(i_freq) is list:
            if not cur_freq[0] == i_freq:
                time.sleep(0.2)
                cur_freq = self.c.run_command(l_cmd)

            if int(cur_freq[0]) == int(i_freq):
                return

        achieved = False
        if not type(i_freq) is list:
            freq_list = [i_freq]
        else:
            freq_list = i_freq

        for freq in freq_list:
            delta = int(freq) / (100)
            try:
                self.assertAlmostEqual(int(cur_freq[0]), int(freq), delta=delta,
                                       msg="CPU frequency not changed to %s" % i_freq)
                achieved = True
                break
            except AssertionError:
                pass

        self.assertTrue(
            achieved, "CPU failed to achieve any one of the frequency in %s" % freq_list)

    def set_cpu_gov(self, i_gov):
        '''
        Sets the CPU governor for all CPUs.
        '''
        l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo %s > $i; done" % i_gov
        self.c.run_command(l_cmd)

    def verify_cpu_gov(self, i_gov):
        '''
        Verifies the CPU governor (on CPU0) matches, just by looking at sysfs.
        '''
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        cur_gov = self.c.run_command(l_cmd)
        self.assertEqual(cur_gov[0], i_gov,
                         "CPU governor not changed to %s" % i_gov)

    def enable_idle_state(self, i_idle):
        '''
        Enable a CPU idle state on all CPUs. Will use `cpupower` or poke at sysfs directly,
        depending on if `cpupower` is available.
        '''
        sysfs_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 0 > $i; done" % i_idle
        if self.test == "host":
            l_cmd = "cpupower idle-set -e %s" % i_idle
        elif self.test == "skiroot":
            l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 0 > $i; done" % i_idle
        try:
            self.c.run_command(l_cmd)
        except CommandFailed:
            self.c.run_command(sysfs_cmd)

    def disable_idle_state(self, i_idle):
        '''
        Disable a CPU idle state on all CPUs using sysfs or `cpupower`.
        '''
        sysfs_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 1 > $i; done" % i_idle
        if self.test == "host":
            l_cmd = "cpupower idle-set -d %s" % i_idle
        elif self.test == "skiroot":
            l_cmd = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state%s/disable; do echo 1 > $i; done" % i_idle
        try:
            self.c.run_command(l_cmd)
        except CommandFailed:
            self.c.run_command(sysfs_cmd)

    def verify_enable_idle_state(self, i_idle):
        '''
        Verify CPU idle state (on CPU0) is enabled (by reading sysfs).
        '''
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.c.run_command(l_cmd)
        self.assertEqual(cur_value[0], "0", "CPU state%s not enabled" % i_idle)

    def verify_disable_idle_state(self, i_idle):
        '''
        Verify CPU idle state (on CPU0) is *disabled* (by reading sysfs).
        '''
        l_cmd = "cat /sys/devices/system/cpu/cpu0/cpuidle/state%s/disable" % i_idle
        cur_value = self.c.run_command(l_cmd)
        self.assertEqual(cur_value[0], "1",
                         "CPU state%s not disabled" % i_idle)

    def get_pstate_limits(self):
        '''
        Get each of the pstate limits: pstate_min, pstate_max, pstate_nom (all from sysfs).
        '''
        cpu_num = self.get_first_available_cpu()

        # Check cpufreq driver enabled
        self.c.run_command(
            "ls --color=never /sys/devices/system/cpu/cpu%s/cpufreq/" % cpu_num)
        pstate_min = self.c.run_command(
            "cat /sys/devices/system/cpu/cpu%s/cpufreq/cpuinfo_min_freq" % cpu_num)[0]
        pstate_max = self.c.run_command(
            "cat /sys/devices/system/cpu/cpu%s/cpufreq/cpuinfo_max_freq" % cpu_num)[0]
        pstate_nom = self.c.run_command(
            "cat /sys/devices/system/cpu/cpu%s/cpufreq/cpuinfo_nominal_freq" % cpu_num)[0]
        return pstate_min, pstate_max, pstate_nom

    def get_list_of_governors(self):
        '''
        Get list of supported CPU governors
        '''
        cmd = "cat /sys/devices/system/cpu/cpu%s/cpufreq/scaling_available_governors" % self.get_first_available_cpu()
        res = self.c.run_command(cmd)
        return res


class slw_info(OpTestEM, unittest.TestCase):
    '''
    This test just gathers the host CPU SLW info.
    '''

    def setUp(self):
        self.test = "host"
        super(slw_info, self).setUp()

    def runTest(self):
        self.c = self.set_up()
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")

        proc_gen = self.cv_HOST.host_get_proc_gen()
        if proc_gen in ["POWER8", "POWER8E"]:
            self.c.run_command(
                "hexdump -c /proc/device-tree/ibm,enabled-idle-states")
        try:
            if proc_gen in ["POWER8", "POWER8E"]:
                self.c.run_command(
                    "cat /sys/firmware/opal/msglog | grep -i slw")
            elif proc_gen in ["POWER9"]:
                self.c.run_command(
                    "cat /sys/firmware/opal/msglog | grep -i stop")
        except CommandFailed as cf:
            pass  # we may have no slw entries in msglog


class cpu_freq_states_host(OpTestEM, unittest.TestCase):
    '''
    This test will cover following test steps:

    1. Check the cpupower utility is available in host.
    2. Get available cpu scaling frequencies
    3. Set the userspace governer for all cpu's
    4. test the cpufreq driver by set/verify cpu frequency

    '''

    def setUp(self):
        self.test = "host"
        super(cpu_freq_states_host, self).setUp()

    NR_FREQUENCIES_SET = 100
    NR_FREQUENCIES_VERIFIED = 10

    def runTest(self):
        self.c = self.set_up()

        if isinstance(self.c, OpTestQemu.QemuConsole):
            raise self.skipTest(
                "OpTestSystem running QEMU frequency checks not applicable")

        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")

        cpu_num = self.get_first_available_cpu()

        # Check cpufreq driver enabled
        self.c.run_command(
            "ls --color=never /sys/devices/system/cpu/cpu%s/cpufreq/" % cpu_num)

        # Get available cpu scaling frequencies
        freq_list = self.get_list_of_cpu_freq()
        log.debug(freq_list)

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
        pass


class cpu_freq_states_skiroot(cpu_freq_states_host):
    def setUp(self):
        self.test = "skiroot"
        super(cpu_freq_states_host, self).setUp()


class cpu_freq_gov_host(OpTestEM, DeviceTreeValidation, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(cpu_freq_gov_host, self).setUp()

    def runTest(self):
        self.c = self.set_up()

        if isinstance(self.c, OpTestQemu.QemuConsole):
            raise self.skipTest(
                "OpTestSystem running QEMU frequency governor checks not applicable")

        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        pstate_min, pstate_max, pstate_nom = self.get_pstate_limits()
        log.debug("Pstate min:{} max:{} nom:{}".format(
            pstate_min, pstate_max, pstate_nom))

        turbo = self.dt_prop_read_u32_arr(
            "/ibm,opal/power-mgt/ibm,pstate-turbo")[0]
        ultra_turbo = self.dt_prop_read_u32_arr(
            "/ibm,opal/power-mgt/ibm,pstate-ultra-turbo")[0]

        cpu_num = self.get_first_available_cpu()

        if turbo == ultra_turbo:
            log.debug("No WoF frequencies")
            freq_list = [pstate_max]
        else:
            # Add boost frequencies
            l_res = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu%s/cpufreq/scaling_boost_frequencies" % cpu_num)
            freq_list = l_res[0].split(' ')[:-1]  # remove empty entry at end
            # Add turbo frequency
            l_res = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu%s/cpufreq/scaling_available_frequencies" % cpu_num)
            fre_list = l_res[0].split(' ')[:-1]
            freq_list.append(max(fre_list))

        # performance(Pstate_max),
        # ondemand(Workload based),
        # userspace(User request),
        # powersave(Pstate_min)
        self.set_cpu_gov("performance")
        self.verify_cpu_gov("performance")
        self.verify_cpu_freq_almost(freq_list)
        log.debug(
            "CPU successfully achieved one of the boost or turbo freuency when performance governor set")
        self.set_cpu_gov("powersave")
        self.verify_cpu_gov("powersave")
        self.verify_cpu_freq_almost(pstate_min)
        self.set_cpu_gov("performance")


class cpu_freq_gov_skiroot(cpu_freq_gov_host):
    def setUp(self):
        self.test = "skiroot"
        super(cpu_freq_gov_host, self).setUp()


class cpu_boost_freqs_host(OpTestEM, DeviceTreeValidation, unittest.TestCase):
    def setUp(self):
        self.test = "host"
        super(cpu_boost_freqs_host, self).setUp()

    def runTest(self):
        self.c = self.set_up()
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        pstate_min, pstate_max, pstate_nom = self.get_pstate_limits()

        cpu_num = self.get_first_available_cpu()

        # Check cpufreq driver enabled
        self.c.run_command(
            "ls --color=never /sys/devices/system/cpu/cpu%s/cpufreq/" % cpu_num)

        turbo = self.dt_prop_read_u32_arr(
            "/ibm,opal/power-mgt/ibm,pstate-turbo")[0]
        ultra_turbo = self.dt_prop_read_u32_arr(
            "/ibm,opal/power-mgt/ibm,pstate-ultra-turbo")[0]

        if turbo == ultra_turbo:
            self.skipTest("No WoF frequencies available to test")

        # In P9 check for stop5
        proc_gen = self.cv_HOST.host_get_proc_gen()
        if proc_gen in ["POWER9"]:
            try:
                self.c.run_command(
                    "grep stop5 /sys/devices/system/cpu/cpu%s/cpuidle/state*/name" % cpu_num)
            except CommandFailed:
                self.skipTest("Stop5 not available. WOF is not supported")

        # Enable all idle states
        idle_states = self.get_idle_states()
        for i in idle_states:
            self.enable_idle_state(i)

        # Get available cpu boost frequencies
        try:
            l_res = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu%s/cpufreq/scaling_boost_frequencies" % cpu_num)
        except CommandFailed:
            self.assertTrue(
                False, "No scaling_boost_frequencies file got created")

        freq_list = l_res[0].split(' ')[:-1]  # remove empty entry at end
        log.debug("Boost frequencies: {}".format(freq_list))

        # Boost frequencies will achieve only when cpufreq governor is performance
        self.set_cpu_gov("performance")
        self.verify_cpu_gov("performance")

        achieved_freq = ""
        # Run the workload only on one active core so it should achieve one of boost frequencies
        res = self.c.run_command_ignore_fail(
            "perf  stat timeout  10 yes > /dev/null")
        for line in res:
            if "cycles" in line and "GHz" in line:
                achieved_freq = int(decimal.Decimal(line.split()[3]) * 1000000)
                break

        if not achieved_freq:
            self.assertTrue(False, "Failed to get CPU achieved frequency")

        achieved = False
        for freq in freq_list:
            delta = int(freq) / (100)
            try:
                self.assertAlmostEqual(int(freq), achieved_freq, delta=delta,
                                       msg="Set and measured CPU frequency differ too greatly")
                achieved = True
                break
            except AssertionError:
                pass

        self.assertTrue(
            achieved, "CPU failed to achieve any one of the frequency in boost frequenies(WoF) range")
        log.debug("CPU successfully achieved one of the boost freuency")
        log.debug("Achieved freq: %d, near by WoF freq: %d" %
                  (int(achieved_freq), int(freq)))


class cpu_idle_states_host(OpTestEM, unittest.TestCase):
    '''
    This test will cover following test steps:

    1. It will get the OS and kernel versions.
    2. Check the cpupower utility is available in host.
    3. Set the userspace governer for all cpu's
    4. test the cpuidle driver by enable/disable/verify the idle states
    '''

    def setUp(self):
        self.test = "host"
        super(cpu_idle_states_host, self).setUp()

    def runTest(self):
        self.c = self.set_up()

        if isinstance(self.c, OpTestQemu.QemuConsole):
            raise self.skipTest(
                "OpTestSystem running QEMU cpu idle state checks not applicable")

        try:
            self.c.run_command("taskset")
        except CommandFailed as cf:
            if 'not found' in ''.join(cf.output):
                self.skipTest("Taskset command not found")

        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        cpu_num = self.get_first_available_cpu()

        # Check cpuidle driver enabled
        try:
            self.c.run_command(
                "ls --color=never /sys/devices/system/cpu/cpu%s/cpuidle/" % cpu_num)
        except CommandFailed:
            kernel_cmdline = self.c.run_command_ignore_fail(
                "cat /proc/cmdline")
            skiboot_err = self.c.run_command_ignore_fail(
                "egrep -i '[54321]\].*(slw|stop)' /sys/firmware/opal/msglog")
            kernel_err = self.c.run_command_ignore_fail("dmesg|grep idle")
            dt_err = self.c.run_command_ignore_fail(
                "lsprop /proc/device-tree/ibm,opal/power-mgt")
            self.assertTrue(False, "cpuidle driver is not enabled in kernel\n"
                            "skiboot:{}\n"
                            "kernel cmdline:{}\nkernel:{}\n"
                            "DT:{}".format(
                                '\n'.join(skiboot_err),
                                '\n'.join(kernel_cmdline),
                                '\n'.join(kernel_err),
                                '\n'.join(dt_err)))

        nrcpus = self.c.run_command("grep -c 'processor.*: ' /proc/cpuinfo")
        nrcpus = int(nrcpus[0])
        self.assertGreater(nrcpus, 0, "You can't have 0 CPUs")

        # Copy /dev/urandom into temptext.txt
        self.c.run_command(
            "dd if=/dev/urandom bs=1024 count=30000 2> /dev/null 1> temptext.txt")

        # Setting workloads. Skiroot does not have the -c option for taskset.
        # This means it must use the CPU affinity which will limit at cpu63 as
        # printf '%x' $(( 1 << 64 )) becomes 0
        workload = """for cpu in {0..%d};do taskset -c $cpu sha1sum temptext.txt & done; wait""" % (
            nrcpus - 1)
        if self.test == "skiroot":
            if nrcpus > 60:
                nrcpus = 60
            workload = """for cpu in `seq 0 1 %d`;do taskset 0x`printf '%%x' $(( 1 << $cpu ))` sha1sum temptext.txt & done; wait""" % (
                nrcpus - 1)

        # TODO: Check the expected idle states (/proc/device-tree/ibm,opal/power-mgt)
        # in runtime idle states (idle_state_names)
        idle_states = self.get_idle_states()
        log.debug("Discovered idle states: {}".format(repr(idle_states)))
        names = self.c.run_command(
            "cat /sys/devices/system/cpu/cpu0/cpuidle/state*/name")
        names = [[a] for a in names]
        idle_state_names = {}
        for i in range(len(idle_states)):
            idle_state_names[idle_states[i]] = names[i]

        # We first disable everything
        for i in idle_states:
            self.disable_idle_state(i)
            self.verify_disable_idle_state(i)

        # With all idle disabled, gather current usage and total time spent in idle
        # state (as a baseline)
        before_usage = {}
        before_time = {}
        for i in idle_states:
            before_usage[i] = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu*/cpuidle/state%s/usage" % (i))
            before_usage[i] = [int(a) for a in before_usage[i]]
            before_time[i] = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu*/cpuidle/state%s/time" % (i))
            before_time[i] = [int(a) for a in before_time[i]]

        # Enable one idle state, check residency, disable and repeat.
        after_usage = {}
        after_time = {}
        for i in idle_states:
            success = 0
            total = 0
            self.enable_idle_state(i)
            self.verify_enable_idle_state(i)

            self.c.run_command(workload)

            after_usage[i] = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu*/cpuidle/state%s/usage" % i)
            after_usage[i] = [int(a) for a in after_usage[i]]
            after_time[i] = self.c.run_command(
                "cat /sys/devices/system/cpu/cpu*/cpuidle/state%s/time" % i)
            after_time[i] = [int(a) for a in after_time[i]]
            for c in range(nrcpus):
                log.debug("# CPU %d entered idle state %s %u times" % (
                    c, idle_state_names[i], after_usage[i][c] - before_usage[i][c]))
                log.debug("# CPU %d entered idle state %s for %u microseconds" % (
                    c, idle_state_names[i], after_time[i][c] - before_time[i][c]))
                if after_usage[i][c] > before_usage[i][c]:
                    success += 0.5
                if after_time[i][c] > before_time[i][c]:
                    success += 0.5
                total += 1
            log.debug("CPUs entered idle state %s for %d/%d of the times" %
                      (idle_state_names[i], success, total))
            self.assertGreater(success/total, 0.95, "CPUs entered idle state %s for %d/%d of the times" %
                               (idle_state_names[i], success, total))
            self.disable_idle_state(i)

        # Remove added temptext.txt file. Idle states are re-enabled during tearDown
        self.c.run_command("rm temptext.txt")
        pass


class cpu_idle_states_skiroot(cpu_idle_states_host):
    def setUp(self):
        self.test = "skiroot"
        super(cpu_idle_states_host, self).setUp()


def host_suite():
    s = unittest.TestSuite()
    s.addTest(slw_info())
    s.addTest(cpu_freq_states_host())
    s.addTest(cpu_freq_gov_host())
    s.addTest(cpu_boost_freqs_host())
    s.addTest(cpu_idle_states_host())
    return s


def skiroot_suite():
    s = unittest.TestSuite()
    s.addTest(cpu_freq_states_skiroot())
    s.addTest(cpu_freq_gov_skiroot())
    s.addTest(cpu_idle_states_skiroot())
    return s
