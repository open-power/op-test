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

"""
Support testing against Qemu simulator
"""

import atexit
import sys
import time
import pexpect
import subprocess
import tempfile

from common.Exceptions import CommandFailed
from common import OPexpect

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class QemuConsole():
    """
    A 'connection' to the Qemu Console involves *launching* qemu.
    Terminating a connection will *terminate* the qemu process.
    """
    def __init__(self, qemu_binary=None, skiboot=None, kernel=None, initramfs=None, logfile=sys.stdout, hda=None, ubuntu_cdrom=None):
        self.qemu_binary = qemu_binary
        self.skiboot = skiboot
        self.kernel = kernel
        self.initramfs = initramfs
        self.hda = hda
        self.state = ConsoleState.DISCONNECTED
        self.logfile = logfile
        self.ubuntu_cdrom = ubuntu_cdrom

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
           )
        if self.initramfs is not None:
            cmd = cmd + " -initrd %s" % (self.initramfs)
        if self.hda is not None:
            cmd = cmd + " -hda %s" % (self.hda)
        if self.ubuntu_cdrom is not None:
            cmd = cmd + " -cdrom %s" % (self.ubuntu_cdrom)
        cmd = cmd + " -netdev user,id=u1 -device e1000,netdev=u1"
        cmd = cmd + " -device ipmi-bmc-sim,id=bmc0 -device isa-ipmi-bt,bmc=bmc0,irq=10"
        print cmd
        solChild = OPexpect.spawn(cmd,logfile=self.logfile)
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
            res = output.replace("\r\r\n", "\n")
            print repr(res)
            res = res.splitlines()
            if exitcode != 0:
                raise CommandFailed(command, res, exitcode)
            return res
        else:
            res = console.before
            res = res.split(command)
            return res[-1].splitlines()

    # This command just runs and returns the ouput & ignores the failure
    def run_command_ignore_fail(self, command, timeout=60):
        try:
            output = self.run_command(command, timeout)
        except CommandFailed as cf:
            output = cf.output
        return output

class QemuIPMI():
    """
    Qemu has fairly limited IPMI capability, and we probably need to
    extend the capability checks so that more of the IPMI test suite
    gets skipped.

    """
    def __init__(self, console):
        self.console = console

    def ipmi_power_off(self):
        """For Qemu, this just kills the simulator"""
        self.console.terminate()

    def ipmi_wait_for_standby_state(self, i_timeout=10):
        """For Qemu, we just kill the simulator"""
        self.console.terminate()

    def ipmi_set_boot_to_petitboot(self):
        return 0

    def ipmi_sel_check(self, i_string="Transition to Non-recoverable"):
        pass

    def sys_set_bootdev_no_override(self):
        pass

class OpTestQemu():
    def __init__(self, qemu_binary=None, skiboot=None, kernel=None, initramfs=None, ubuntu_cdrom=None, logfile=sys.stdout):
        self.qemu_hda_file = tempfile.NamedTemporaryFile(delete=True)
        atexit.register(self.__del__)
        create_hda = subprocess.check_call(["qemu-img", "create",
                                            "-fqcow2",
                                            self.qemu_hda_file.name,
                                            "10G"])
        self.console = QemuConsole(qemu_binary, skiboot, kernel, initramfs, logfile=logfile, hda=self.qemu_hda_file.name, ubuntu_cdrom=ubuntu_cdrom)
        self.ipmi = QemuIPMI(self.console)

    def __del__(self):
        self.qemu_hda_file.close()

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

    def has_os_boot_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False
