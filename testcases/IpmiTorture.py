#!/usr/bin/python2
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

import unittest
import time
import threading

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST

class OobIpmiThread(threading.Thread):
    def __init__(self, threadID, name, cmd, execution_time):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.cmd = cmd
        self.execution_time = execution_time
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()

    def run(self):
        print "Starting " + self.name
        self.oob_ipmi_thread(self.name, self.cmd, self.execution_time)
        print "Exiting " + self.name

    def oob_ipmi_thread(self, threadName, cmd, t):
        execution_time = time.time() + 60*t
        print "Starting %s for oob-ipmi %s" % (threadName, cmd)
        while True:
            try:
                self.cv_IPMI.ipmitool.run(cmd, logcmd=False)
            except:
                pass
            if time.time() > execution_time:
                break
            time.sleep(2)


class InbandIpmiThread(threading.Thread):
    def __init__(self, threadID, name, ipmi_method, cmd, execution_time):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.ipmi_method = ipmi_method
        self.cmd = cmd
        self.execution_time = execution_time
        conf = OpTestConfiguration.conf
        self.host = conf.host()

    def run(self):
        print "Starting " + self.name
        self.inband_ipmi_thread(self.name, self.cmd, self.execution_time)
        print "Exiting " + self.name

    def inband_ipmi_thread(self, threadName, cmd, t):
        execution_time = time.time() + 60*t
        self.c = self.host.get_ssh_connection()
        print "Starting %s for inband-ipmi %s" % (threadName, cmd)
        while True:
            try:
                self.c.run_command(self.ipmi_method + cmd)
            except:
                pass
            if time.time() > execution_time:
                break
            time.sleep(2)

class SolConsoleThread(threading.Thread):
    def __init__(self, threadID, name, test, execution_time):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.test = test
        self.execution_time = execution_time
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()

    def run(self):
        print "Starting " + self.name
        self.sol_console_thread(self.name, self.execution_time)
        print "Exiting " + self.name

    def sol_console_thread(self, threadName, t):
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        # Enable kernel logging(printk) to console
        self.c.run_command("echo 10 > /proc/sys/kernel/printk")
        execution_time = time.time() + 60*self.execution_time
        i = 0
        while True:
            print "Iteration %s, SOL open/close" % i
            try:
                self.c.get_console()
                # Execute any host command(for console IO) if system is in runtime
                if "runtime" in self.test:
                    try:
                        self.c.run_command("ipmitool power status")
                        # Enable console traffic by printing the processes/tasks to the console
                        self.c.run_command("echo t > /proc/sysrq-trigger")
                    except:
                        pass
                self.c.close()
            except:
                pass
            time.sleep(3)
            i += 1
            if time.time() > execution_time:
                break

class IpmiInterfaceTorture(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.torture_time = 2400
        self.bmc_type = conf.args.bmc_type

    def runTest(self):
        self.setup_test()
        self.thread_list = []
        # OOB IPMI Torture
        torture_time = self.torture_time
        cmd_list = ["sdr list", "fru print", "sel list", "sensor list","power status"]
        for j in range(1,3):
            for idx, cmd in enumerate(cmd_list):
                num = j*(idx + 1)
                thread = OobIpmiThread(num, "Thread-%s" % num, cmd, torture_time)
                thread.start()
                self.thread_list.append(thread)

        if "skiroot" in self.test:
            return

        if self.test == "standby":
            return

        # In-band IPMI Torture (Open Interface)
        cmd_list = ["sdr list", "fru print", "sel list", "sensor list","power status"]
        for j in range(1,3):
            for idx, cmd in enumerate(cmd_list):
                num = j*(idx + 1)
                thread = InbandIpmiThread(num, "Thread-%s" % num, BMC_CONST.IPMITOOL_OPEN, cmd, torture_time)
                thread.start()
                self.thread_list.append(thread)

        if "FSP" in self.bmc_type:
            return

        # In-band IPMI Torture (USB Interface)
        cmd_list = ["sdr list", "fru print", "sel list", "sensor list","power status"]
        for idx, cmd in enumerate(cmd_list):
            thread = InbandIpmiThread(idx, "Thread-%s" % idx, BMC_CONST.IPMITOOL_USB, cmd, torture_time)
            thread.start()
            self.thread_list.append(thread)

    def tearDown(self):
        # wait for all the threads to finish
        for thread in self.thread_list:
            thread.join()

class ConsoleIpmiTorture(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.torture_time = 2400

    def ipmi_interface_torture(self):
        # OOB IPMI Torture
        torture_time = self.torture_time
        self.thread_list = []
        cmd_list = ["sdr list", "fru print", "sel list", "sensor list","power status"]
        for j in range(1,3):
            for idx, cmd in enumerate(cmd_list):
                num = j*(idx + 1)
                thread = OobIpmiThread(num, "Thread-%s" % num, cmd, torture_time)
                thread.start()
                self.thread_list.append(thread)

        if self.test == "standby":
            return

        if "skiroot" in self.test:
            return

        return # Don't enable below inband ipmi torture, console and ssh sessions make the o/p clutter
        # In-band IPMI Torture
        cmd_list = ["sdr list", "fru print", "sel list", "sensor list","power status"]
        for j in range(1,3):
            for idx, cmd in enumerate(cmd_list):
                num = j*(idx + 1)
                thread = InbandIpmiThread(num, "Thread-%s" % num, BMC_CONST.IPMITOOL_OPEN, cmd, torture_time)
                thread.start()
                self.thread_list.append(thread)

    def console_torture(self):
        thread = SolConsoleThread(1, "SOL-Thread", self.test, self.torture_time)
        thread.start()
        self.thread_list.append(thread)

    def runTest(self):
        self.setup_test()
        self.ipmi_interface_torture()
        self.console_torture()

    def tearDown(self):
        # Wait for all the thread to finish
        for thread in self.thread_list:
            thread.join()

class SkirootConsoleTorture(ConsoleIpmiTorture):
    def setup_test(self):
        self.test = "skiroot_runtime"
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_unique_prompt()


class SkirootIpmiTorture(IpmiInterfaceTorture):
    def setup_test(self):
        self.test = "skiroot_runtime"
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()

class RuntimeConsoleTorture(ConsoleIpmiTorture):
    def setup_test(self):
	self.test = "runtime"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()

class StandbyConsoleTorture(ConsoleIpmiTorture):
    def setup_test(self):
	self.test = "standby"
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()

class RuntimeIpmiInterfaceTorture(IpmiInterfaceTorture):
    def setup_test(self):
        self.test = "runtime"
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()

class StandbyIpmiInterfaceTorture(IpmiInterfaceTorture):
    def setup_test(self):
        self.test = "standby"
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.c = self.cv_SYSTEM.sys_get_ipmi_console()
