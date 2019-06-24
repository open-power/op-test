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
import os

from common.Exceptions import CommandFailed
import OPexpect
from OpTestUtil import OpTestUtil
import OpTestConfiguration

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
            logfile=sys.stdout, disks=None, cdrom=None):
        self.qemu_binary = qemu_binary
        self.pnor = pnor
        self.skiboot = skiboot
        self.kernel = kernel
        self.initramfs = initramfs
        self.disks = disks
        self.state = ConsoleState.DISCONNECTED
        self.logfile = logfile
        self.delaybeforesend = delaybeforesend
        self.system = None
        self.cdrom = cdrom
        # OpTestUtil instance is NOT conf's
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        self.block_setup_term = block_setup_term # allows caller specific control of when to block setup_term
        self.setup_term_quiet = 0 # tells setup_term to not throw exceptions, like when system off
        self.setup_term_disable = 0 # flags the object to abandon setup_term operations, like when system off
        self.mac_str = '52:54:00:22:34:56'

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

    # Because this makes sense for the console
    def update_disks(self, disks):
        self.disks = disks

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
            skibootdir = os.path.dirname(self.skiboot)
            skibootfile = os.path.basename(self.skiboot)
            if skibootfile:
                cmd = cmd + " -bios %s" % (skibootfile)
            if skibootdir:
                cmd = cmd + " -L %s" % (skibootdir)
        if self.kernel:
            cmd = cmd + " -kernel %s" % (self.kernel)
            if self.initramfs is not None:
                cmd = cmd + " -initrd %s" % (self.initramfs)

        # So in the powernv QEMU model we have 3 PHBs with one slot free each.
        # We can add a pcie bridge to each of these, and each bridge has 31
        # slots.. if you see where I'm going..
        cmd = (cmd
                + " -device pcie-pci-bridge,id=pcie.3,bus=pcie.0,addr=0x0"
                + " -device pcie-pci-bridge,id=pcie.4,bus=pcie.1,addr=0x0"
                + " -device pcie-pci-bridge,id=pcie.5,bus=pcie.2,addr=0x0"
            )

        # Put the NIC in slot 2 of the second PHB (1st is reserved for later)
        cmd = (cmd
                + " -netdev user,id=u1 -device e1000e,netdev=u1,mac={},bus=pcie.4,addr=2"
                .format(self.mac_str)
                )
        prefilled_slots = 1

        if self.cdrom is not None:
            # Put the CDROM in slot 3 of the second PHB
            cmd = (cmd
                    + " -drive file={},id=cdrom01,if=none,media=cdrom".format(self.cdrom)
                    + " -device virtio-blk-pci,drive=cdrom01,id=virtio02,bus=pcie.4,addr=3"
                )
            prefilled_slots += 1

        bridges = []
        bridges.append({'bus': 3, 'n_devices': 0, 'bridged' : False})
        bridges.append({'bus': 4, 'n_devices': prefilled_slots, 'bridged' : False})
        bridges.append({'bus': 5, 'n_devices': 0, 'bridged' : False})

        # For any amount of disks we have, start finding spots for them in the PHBs
        if self.disks:
            diskid = 0
            bid = 0
            for disk in self.disks:
                bridge = bridges[bid]
                if bridge['n_devices'] >= 30:
                    # This bridge is full
                    if bid == len(bridges) - 1:
                        # All bridges full, find one to extend
                        if [x for  x in bridges if x['bridged'] == False] == []:
                            # We messed up and filled up all our slots
                            raise OpTestError("Oops! We ran out of slots!")
                        for i in range(0, bid):
                            if not bridges[i]['bridged']:
                                # We can add a bridge here
                                parent = bridges[i]['bus']
                                new = bridges[-1]['bus'] + 1
                                print("Adding new bridge {} on bridge {}".format(new, parent))
                                bridges.append({'bus': new, 'n_devices' : 0, 'bridged' : False})
                                cmd = cmd + " -device pcie-pci-bridge,id=pcie.{},bus=pcie.{},addr=0x1".format(new, parent)
                                bid = bid + 1
                                bridges[i]['bridged'] = True
                                bridge = bridges[bid]
                                break
                    else:
                        # Just move to the next one, subsequent bridge should
                        # always have slots
                        bid = bid + 1
                        bridge = bridges[bid]
                        if bridge['n_devices'] >= 30:
                            raise OpTestError("Lost track of our PCI bridges!")

                # Got a bridge, let's go!
                # Valid bridge slots are 1..31, but keep 1 free for more bridges
                addr = 2 + bridge['n_devices']
                print("Adding disk {} on bus {} at address {}".format(diskid, bridge['bus'], addr))
                cmd = cmd + " -drive file={},id=disk{},if=none".format(disk.name, diskid)
                cmd = cmd + " -device virtio-blk-pci,drive=disk{},id=virtio{},bus=pcie.{},addr={}".format(diskid, diskid, bridge['bus'], hex(addr))
                diskid += 1
                bridge['n_devices'] += 1

        # typical host ip=10.0.2.2 and typical skiroot 10.0.2.15
        # use skiroot as the source, no sshd in skiroot

        fru_path = os.path.join(OpTestConfiguration.conf.basedir, "test_binaries", "qemu_fru")
        cmd = cmd + " -device ipmi-bmc-sim,id=bmc0,frudatafile=" + fru_path + " -device isa-ipmi-bt,bmc=bmc0,irq=10"
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

    def ipmi_sel_elist(self, dump=False):
        pass

    def ipmi_set_no_override(self):
        pass

    def sys_set_bootdev_no_override(self):
        pass

class OpTestQemu():
    def __init__(self, conf=None, qemu_binary=None, pnor=None, skiboot=None,
                 kernel=None, initramfs=None, cdrom=None,
                 logfile=sys.stdout):
        self.disks = []
        # need the conf object to properly bind opened object
        # we need to be able to cleanup/close the temp file in signal handler
        self.conf = conf
        if self.conf.args.qemu_scratch_disk and self.conf.args.qemu_scratch_disk.strip():
            try:
                # starts as name string
                log.debug("OpTestQemu opening file={}"
                    .format(self.conf.args.qemu_scratch_disk))
                self.conf.args.qemu_scratch_disk = \
                    open(self.conf.args.qemu_scratch_disk, 'wb')
                # now is a file-like object
            except Exception as e:
                log.error("OpTestQemu encountered a problem "
                          "opening file={} Exception={}"
                    .format(self.conf.args.qemu_scratch_disk, e))
        else:
            # update with new object to close in cleanup
            self.conf.args.qemu_scratch_disk = \
                tempfile.NamedTemporaryFile(delete=True)
            # now a file-like object
            try:
                create_hda = subprocess.check_call(["qemu-img", "create",
                                                    "-fqcow2",
                                                    self.conf.args.qemu_scratch_disk.name,
                                                    "10G"])
            except Exception as e:
                log.error("OpTestQemu encountered a problem with qemu-img,"
                          " check that you have qemu-utils installed first"
                          " and then retry.")
                raise e

        self.disks.append(self.conf.args.qemu_scratch_disk)
        atexit.register(self.__del__)
        self.console = QemuConsole(qemu_binary=qemu_binary,
                                   pnor=pnor,
                                   skiboot=skiboot,
                                   kernel=kernel,
                                   initramfs=initramfs,
                                   logfile=logfile,
                                   disks=self.disks, cdrom=cdrom)
        self.ipmi = QemuIPMI(self.console)
        self.system = None

    def __del__(self):
        for fd in self.disks:
            log.debug("OpTestQemu cleaning up qemu_scratch_disk={}"
                .format(self.conf.args.qemu_scratch_disk))
            try:
                fd.close()
            except Exception as e:
                log.error("OpTestQemu cleanup, ignoring Exception={}"
                    .format(e))
        self.disks = []

    def set_system(self, system):
        self.console.system = system

    def get_host_console(self):
        return self.console

    def run_command(self, command, timeout=10, retry=0):
        # qemu only supports system console object, not this bmc object
        return None # at least return something and have the testcase handle

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

    def add_temporary_disk(self, size):
        self.console.close()

        fd = tempfile.NamedTemporaryFile(delete=True)
        self.disks.append(fd)
        create_hda = subprocess.check_call(["qemu-img", "create",
                                            "-fqcow2", fd.name, size])
        self.console.update_disks(self.disks)
