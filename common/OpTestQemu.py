#!/usr/bin/python2
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

# Support testing against Qemu simulator

import sys
import time
import pexpect
import subprocess

from common.Exceptions import CommandFailed

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class QemuConsole():
    def __init__(self, qemu_binary=None, skiboot=None, kernel=None, initramfs=None, logfile=sys.stdout):
        self.qemu_binary = qemu_binary
        self.skiboot = skiboot
        self.kernel = kernel
        self.initramfs = initramfs
        self.state = ConsoleState.DISCONNECTED
        self.logfile = logfile

    def terminate(self):
        if self.state == ConsoleState.CONNECTED:
            print "#Qemu TERMINATE"
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

    def close(self):
        if self.state == ConsoleState.DISCONNECTED:
            return
        print "Qemu close -> TERMINATE"
        self.sol.terminate()
        self.state = ConsoleState.DISCONNECTED

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

        print "#Qemu Console CONNECT"

        cmd = ("%s" % (self.qemu_binary)
               + " -M powernv -m 4G"
               + " -nographic"
               + " -bios %s" % (self.skiboot)
               + " -kernel %s" % (self.kernel)
               + " -initrd %s" % (self.initramfs)
           )
        print cmd
        solChild = pexpect.spawn(cmd,logfile=self.logfile)
        self.state = ConsoleState.CONNECTED
        self.sol = solChild
        return solChild

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.sol.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(1)
            self.connect()
            count += 1
            if count > 120:
                raise "IPMI: not able to get sol console"

        return self.sol

    def run_command(self, command, timeout=60):
        console = self.get_console()
        console.sendline(command)
        console.expect("\n") # from us
        rc = console.expect(["\[console-pexpect\]#$",pexpect.TIMEOUT], timeout)
        output = console.before

        console.sendline("echo $?")
        console.expect("\n") # from us
        rc = console.expect(["\[console-pexpect\]#$",pexpect.TIMEOUT], timeout)
        exitcode = int(console.before)

        if rc == 0:
            res = output
            res = res.splitlines()
            if exitcode != 0:
                raise CommandFailed(command, res, exitcode)
            return res
        else:
            res = console.before
            res = res.split(command)
            return res[-1].splitlines()

class QemuIPMI():
    def __init__(self, console):
        self.console = console

    def ipmi_power_off(self):
        self.console.terminate()

    def ipmi_wait_for_standby_state(self, i_timeout=10):
        self.console.terminate()

    def ipmi_set_boot_to_petitboot(self):
        return 0

    def ipmi_sel_check(self, i_string="Transition to Non-recoverable"):
        pass

class OpTestQemu():
    def __init__(self, qemu_binary=None, skiboot=None, kernel=None, initramfs=None, logfile=sys.stdout):
        self.console = QemuConsole(qemu_binary, skiboot, kernel, initramfs, logfile=logfile)
        self.ipmi = QemuIPMI(self.console)

    def get_host_console(self):
        return self.console

    def get_ipmi(self):
        return self.ipmi

    def power_off(self):
        self.console.terminate()

    def power_on(self):
        self.console.connect()

    def get_rest_api(self):
        return None
