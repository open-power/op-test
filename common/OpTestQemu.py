#!/usr/bin/env python2
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
import OPexpect
from OpTestUtil import OpTestUtil

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class QemuConsole():
    """
    A 'connection' to the Qemu Console involves *launching* qemu.
    Closing a connection will *terminate* the qemu process.
    """
    def __init__(self, qemu_binary=None, pnor=None, skiboot=None,
            prompt=None, kernel=None, initramfs=None,
            block_setup_term=None, delaybeforesend=None,
            logfile=sys.stdout, hda=None, cdrom=None):
        self.qemu_binary = qemu_binary
        self.pnor = pnor
        self.skiboot = skiboot
        self.kernel = kernel
        self.initramfs = initramfs
        self.hda = hda
        self.state = ConsoleState.DISCONNECTED
        self.logfile = logfile
        self.delaybeforesend = delaybeforesend
        self.system = None
        self.cdrom = cdrom
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        self.block_setup_term = block_setup_term # allows caller specific control of when to block setup_term
        self.setup_term_quiet = 0 # tells setup_term to not throw exceptions, like when system off
        self.setup_term_disable = 0 # flags the object to abandon setup_term operations, like when system off

        # state tracking, reset on boot and state changes
        # console tracking done on System object for the system console
        self.PS1_set = -1
        self.LOGIN_set = -1
        self.SUDO_set = -1

    def set_system(self, system):
        self.system = system

    def set_system_setup_term(self, flag):
        self.system.block_setup_term = flag

    def get_system_setup_term(self):
        return self.system.block_setup_term

    def set_block_setup_term(self, flag):
        self.block_setup_term = flag

    def get_block_setup_term(self):
        return self.block_setup_term

    def enable_setup_term_quiet(self):
        self.setup_term_quiet = 1
        self.setup_term_disable = 0

    def disable_setup_term_quiet(self):
        self.setup_term_quiet = 0
        self.setup_term_disable = 0

    def close(self):
        self.util.clear_state(self)
        try:
            rc_child = self.pty.close()
            exitCode = signalstatus = None
            if self.pty.status != -1: # leaving for debug
              if os.WIFEXITED(self.pty.status):
                exitCode = os.WEXITSTATUS(self.pty.status)
              else:
                signalstatus = os.WTERMSIG(self.pty.status)
            self.state = ConsoleState.DISCONNECTED
        except pexpect.ExceptionPexpect as e:
            self.state = ConsoleState.DISCONNECTED
            raise "Qemu Console: failed to close console"
        except Exception as e:
            self.state = ConsoleState.DISCONNECTED
            pass
        log.debug("Qemu close -> TERMINATE")

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            return self.pty
        else:
            self.util.clear_state(self) # clear when coming in DISCONNECTED

        log.debug("#Qemu Console CONNECT")

        cmd = ("%s" % (self.qemu_binary)
               + " -machine powernv -m 4G"
               + " -nographic -nodefaults"
           )
        if self.pnor:
            cmd = cmd + " -drive file={},format=raw,if=mtd".format(self.pnor)
        if self.skiboot:
            cmd = cmd + " -bios %s" % (self.skiboot)
        if self.kernel:
            cmd = cmd + " -kernel %s" % (self.kernel)
            if self.initramfs is not None:
                cmd = cmd + " -initrd %s" % (self.initramfs)

        if self.hda is not None:
            # Put the disk on the first PHB
            cmd = (cmd
                    + " -drive file={},id=disk01,if=none".format(self.hda)
                    + " -device virtio-blk-pci,drive=disk01,id=virtio01,bus=pcie.0,addr=0"
                )
        if self.cdrom is not None:
            # Put the CDROM on the second PHB
            cmd = (cmd
                    + " -drive file={},id=cdrom01,if=none,media=cdrom".format(self.cdrom)
                    + " -device virtio-blk-pci,drive=cdrom01,id=virtio02,bus=pcie.1,addr=0"
                )
        # typical host ip=10.0.2.2 and typical skiroot 10.0.2.15
        # use skiroot as the source, no sshd in skiroot
        cmd = cmd + " -nic user,model=virtio-net-pci"
        cmd = cmd + " -device ipmi-bmc-sim,id=bmc0 -device isa-ipmi-bt,bmc=bmc0,irq=10"
        cmd = cmd + " -serial none -device isa-serial,chardev=s1 -chardev stdio,id=s1,signal=off"
        print(cmd)
        try:
          self.pty = OPexpect.spawn(cmd,logfile=self.logfile)
        except Exception as e:
          self.state = ConsoleState.DISCONNECTED
          raise CommandFailed('OPexpect.spawn',
                  'OPexpect.spawn encountered a problem: ' + str(e), -1)

        self.state = ConsoleState.CONNECTED
        self.pty.setwinsize(1000,1000)
        if self.delaybeforesend:
          self.pty.delaybeforesend = self.delaybeforesend

        if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
          self.util.setup_term(self.system, self.pty, None, self.system.block_setup_term)

        # Wait a moment for isalive() to read a correct value and then check
        # if the command has already exited. If it has then QEMU has most
        # likely encountered an error and there's no point proceeding.
        time.sleep(0.2)
        if not self.pty.isalive():
            raise CommandFailed(cmd, self.pty.read(), self.pty.status)
        return self.pty

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.util.clear_state(self)
            self.connect()
        else:
            if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
                self.util.setup_term(self.system, self.pty, None, self.system.block_setup_term)

        return self.pty

    def run_command(self, command, timeout=60, retry=0):
        return self.util.run_command(self, command, timeout, retry)

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.util.run_command_ignore_fail(self, command, timeout, retry)

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
        self.console.close()

    def ipmi_wait_for_standby_state(self, i_timeout=10):
        """For Qemu, we just kill the simulator"""
        self.console.close()

    def ipmi_set_boot_to_petitboot(self):
        return 0

    def ipmi_sel_check(self, i_string="Transition to Non-recoverable"):
        pass

    def ipmi_set_no_override(self):
        pass

    def sys_set_bootdev_no_override(self):
        pass

class OpTestQemu():
    def __init__(self, qemu_binary=None, pnor=None, skiboot=None,
                 kernel=None, initramfs=None, cdrom=None,
                 logfile=sys.stdout, hda=None):
        if hda is not None:
            self.qemu_hda_file = tempfile.NamedTemporaryFile(delete=True)
            atexit.register(self.__del__)
        else:
            self.qemu_hda_file = hda
        create_hda = subprocess.check_call(["qemu-img", "create",
                                            "-fqcow2",
                                            self.qemu_hda_file.name,
                                            "10G"])
        self.console = QemuConsole(qemu_binary=qemu_binary, pnor=pnor,
                                   skiboot=skiboot,
                                   kernel=kernel, initramfs=initramfs,
                                   logfile=logfile,
                                   hda=self.qemu_hda_file.name, cdrom=cdrom)
        self.ipmi = QemuIPMI(self.console)
        self.system = None

    def __del__(self):
        self.qemu_hda_file.close()

    def set_system(self, system):
        self.console.system = system

    def get_host_console(self):
        return self.console

    def get_ipmi(self):
        return self.ipmi

    def power_off(self):
        self.console.close()

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

    def has_inband_bootdev(self):
        return False

    def supports_ipmi_dcmi(self):
        return False

    def has_ipmi_sel(self):
        return False
