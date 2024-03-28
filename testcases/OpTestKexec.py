#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestKexec.py $
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
#

'''
OpTestKexec
-----------
Performs following kexec test (Kexec is a Linux feature that
lets you restart the operating system quickly by loading a
new kernel into memory and switching to it, avoiding a full
computer reboot.)

Test 1: Load and unload kexec kernel
Test 2: First Load and then boot into kexec kernel
Test 3: Load and boot into kexec kernel using force option
Test 4: Single step load and boot into kexec kernel
Test 5: Single step kexec in loop

There is no guarantee that above tests are will be executed in the
same order as they are listed if test are executed using class name.

Note: After a kexec test that involves booting the system using kexec,
it is reset to its previous state before performing the next kexec test.
This is done to avoid performing a kexec on a kernel that was booted using
kexec, except for the kexec in loop test.
'''

import unittest
import OpTestLogger

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestKexec(unittest.TestCase):
    """kexec test class"""

    def populate_kernel_initrd_image(self):
        """
        Determines the kernel and initrd image filenames based on the Linux
        distribution.

        First identifies the distribution using 'get_distro()'. If the
        distribution is unknown, the test is skipped.
        Second identify the kernel version either by the provided
        'linux_src_dir' or the running kernel.

        Based on the Linux distribution and kernel version set the kernel_image
        and initrd_image instance variable
        """

        distro = self.op_test_util.distro_name()

        # Skip the test for unsupported distro
        if distro == "unknown":
            self.skipTest("Unsupported distro")

        # Find kexec kernel version. If user provided the kernel source
        # directory then follow that, else go with currently running kernel.
        k_ver = None
        if self.linux_src_dir:
            try:
                self.cv_HOST.host_run_command("cd " + str(self.linux_src_dir))
                k_ver = self.cv_HOST.host_run_command("make kernelrelease")[0]
            except CommandFailed:
                self.skipTest("No kernel source at " + str(self.linux_src_dir))
        else:
            try:
                k_ver = self.cv_HOST.host_run_command("uname -r")[0]
            except CommandFailed:
                self.skipTest("Unable to find kernel version")

        # Set kernel_image and initrd_image instance variable with
        # corresponding filenames path
        k_ver = str(k_ver)
        if distro == "rhel":
            self.kernel_image = "vmlinuz-" + k_ver
            self.initrd_image = "initramfs-" + k_ver + ".img"
        elif distro == "sles":
            self.kernel_image = "vmlinux-" + k_ver
            self.initrd_image = "initrd-" + k_ver
        elif distro == "ubuntu":
            self.kernel_image = "vmlinux-" + k_ver
            self.initrd_image = "initrd.img-" + k_ver

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.op_test_util = OpTestUtil(conf)
        self.cv_SYSTEM = conf.system()
        self.c = self.cv_SYSTEM.console
        self.cv_HOST = conf.host()
        self.distro = None
        self.num_of_iterations = conf.args.num_of_iterations
        self.kernel_image = conf.args.kernel_image
        self.initrd_image = conf.args.initrd_image
        self.linux_src_dir = conf.args.linux_src_dir
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        # User didn't provide kernel and initrd image so use currently
        # running kernel for kexec kernel.
        if not (self.kernel_image and self.initrd_image):
            self.populate_kernel_initrd_image()

        sb_utilities = OpTestUtil(conf)
        self.kernel_signature = sb_utilities.check_kernel_signature()
        self.os_level_secureboot = sb_utilities.check_os_level_secureboot_state()

    def get_kexec_load_cmd(self, load_opt=True, copy_cmdline=True,
                           syscall_load=False, file_load=False, add_arg=None):
        """
        Generates a kexec command for loading a kernel image with various
        optional arguments.

        Args:
            file_load (bool, optional): If True, includes '-s' to load the
                                        kernel from a file.
            copy_cmdline (bool, optional): If True, includes '--append' with
                                           the current kernel command line.
            add_arg (str, optional): Additional argument to append to the kexec
                                     command.

        Returns:
            str: The generated kexec command for loading a kernel image with
                 optional arguments.
        """

        kexec_cmd = "kexec --initrd=/boot/" + self.initrd_image
        kexec_cmd = kexec_cmd + " /boot/" + self.kernel_image

        if load_opt:
            kexec_cmd = kexec_cmd + " -l"

        if file_load:
            kexec_cmd = kexec_cmd + " -s"

        if syscall_load:
            kexec_cmd = kexec_cmd + " -c"

        if copy_cmdline:
            kexec_cmd = kexec_cmd + " --append=\"`cat /proc/cmdline`\""

        if add_arg is not None:
            kexec_cmd = kexec_cmd + " " + add_arg

        return kexec_cmd

    def get_kexec_unload_cmd(self):
        """
        Generates a kexec command to unload the current kexec kernel image.

        Returns:
            str: The generated kexec command for unloading the current kernel
                 image.
        """

        return "kexec -u"

    def get_kexec_exec_command(self, exec_opt=False):
        """
        Generates a kexec command for either immediate execution or system
        reboot. Reboot command with kexec kernel loaded will lead to clean
        kexec.

        Args:
            exec_opt (bool, optional): If True, generates a kexec command for
                                       immediate execution. If False (default),
                                       generates a kexec command for system
                                       reboot.

        Returns:
            str: The generated kexec command.
        """

        kexec_cmd = None

        if exec_opt:
            kexec_cmd = "kexec -e"
        else:
            kexec_cmd = "reboot"

        return kexec_cmd

    def is_kexec_kernel_loaded(self):
        """
        Checks if a kexec kernel is currently loaded.

        Returns:
            bool: True if a kexec kernel is loaded, False if not loaded, and
                  None if the status cannot be determined.
        """

        try:
            kexec_loaded = self.c.run_command("cat /sys/kernel/kexec_loaded")
            if kexec_loaded[0] == "1":
                return True
        except CommandFailed:
            log.error("Failed to get kexec loaded status.")

        return False

    def execute_kexec_cmd(self, cmd, raw_pty_console=False, sys_reset=True):
        """
        Executes a command using either the standard shell or a raw PTY
        console.

        Args:
            cmd (str): The command to be executed.
            raw_pty_console (bool, optional): If True, uses a raw PTY console
                                              for execution.
            sys_reset(bool, optional): reset the system by rebooting it. If
                                      False close the console connection.

        Returns:
            bool: True if the command runs successfully, False if there's an
                  error.
        """

        try:
            if raw_pty_console:
                raw_pty = self.cv_SYSTEM.console.get_console()
                raw_pty.sendline(cmd)
                raw_pty.expect("login:", timeout=600)

                if sys_reset:
                    # Brings back the system to normal state
                    # by rebooting the system.
                    self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN)
                    self.cv_SYSTEM.goto_state(OpSystemState.OS)
                else:
                    # Re-logging into the test system is required after kexec
                    # into a new kernel. Otherwise, commands run via raw_pty
                    # console won't work properly on the system for the next
                    # test.
                    # Therefore, closing the console if system is not reset so
                    # that the next user can log in before running any command
                    # via raw_pty.
                    self.cv_SYSTEM.console.close()
            else:
                self.c.run_command(cmd)
        except CommandFailed:
            log.error("Failed to run command: %s" % (cmd))
            return False

        return True

    def load_kexec_kernel(self, kexec_load_cmd):
        """
        Loads a kexec kernel using the provided command.

        Args:
            kexec_load_cmd (str): The command to load the kexec kernel.

        Returns:
            bool: True if the kexec kernel is successfully loaded, False if
                  there's an error.

        Note: kexec load status is verified using /sys/kernel/kexec_loaded
              sysfs attribute.
        """

        kexec_cmd_status = self.execute_kexec_cmd(kexec_load_cmd)
        if not kexec_cmd_status:
            return kexec_cmd_status

        kexec_load_status = self.is_kexec_kernel_loaded()
        if not kexec_load_status:
            log.error("/sys/kernel/kexec_loaded expect 1 found 0")

        return kexec_load_status

    def unload_kexec_kernel(self, kexec_unload_cmd):
        """
        Unloads a previously loaded kexec kernel using the provided command.

        Args:
            kexec_unload_cmd (str): The command to unload the kexec kernel.

        Returns:
            bool: True if the kexec kernel is successfully unloaded, False if
            there's an error.

        Note: kexec load status is verified using /sys/kernel/kexec_loaded
              sysfs attribute.
        """

        kexec_cmd_status = self.execute_kexec_cmd(kexec_unload_cmd)

        if not kexec_cmd_status:
            return kexec_cmd_status

        return not self.is_kexec_kernel_loaded()

    def test_load_unload(self):
        """
        Tests loading and unloading of a kexec kernel using kexec command.

        First test kexec load using -l and --append(command line arguments of
        currently running kenrel form /proc/cmdline) option.

        Second test unload of loaded kernel.

        Test passes if both loading and unloading goes fine; otherwise, it
        fails.
        """

        kexec_load_cmd = self.get_kexec_load_cmd()
        ret = self.load_kexec_kernel(kexec_load_cmd)
        self.assertTrue(ret, "Kexec load failed")

        kexec_unload_cmd = self.get_kexec_unload_cmd()
        ret = self.unload_kexec_kernel(kexec_unload_cmd)
        self.assertTrue(ret, "kexec unload failed")

    def test_load_and_exec(self):
        """
        Test kexec functionality by loading and exec into kexec kernel.

        First load the kexec kernel using -l and --append(command line
        arguments of currently running kenrel form /proc/cmdline) option.
        Then exec into kexec kernel.

        Test passes if both the kexec load and the execution into the
        kexec kernel go fine; otherwise, it fails."
        """

        kexec_load_cmd = self.get_kexec_load_cmd()
        ret = self.load_kexec_kernel(kexec_load_cmd)
        self.assertTrue(ret, "Kexec load failed")

        kexec_exec_cmd = self.get_kexec_exec_command(exec_opt=True)
        ret = self.execute_kexec_cmd(kexec_exec_cmd, raw_pty_console=True)
        self.assertTrue(ret, "kexec exec failed: " + kexec_exec_cmd)

    def test_file_load_and_exec(self):
        """
        Test kexec functionality by loading with kexec-file-syscall and exec
        into kexec kernel.

        First load the kexec kernel using -s, -l and --append(command line
        arguments of currently running kenrel form /proc/cmdline) option.
        Then exec into kexec kernel.

        Test passes if both the kexec load and the execution into the
        kexec kernel go fine; otherwise, it fails."
        """

        kexec_load_cmd = self.get_kexec_load_cmd(file_load=True)
        ret = self.load_kexec_kernel(kexec_load_cmd)
        self.assertTrue(ret, "Kexec load failed")

        kexec_exec_cmd = self.get_kexec_exec_command(exec_opt=True)
        ret = self.execute_kexec_cmd(kexec_exec_cmd, raw_pty_console=True)
        self.assertTrue(ret, "kexec exec failed: " + kexec_exec_cmd)

    def test_syscall_load_and_exec(self):
        """
        Test kexec functionality by loading with kexec-syscall and exec
        into kexec kernel.

        First load the kexec kernel using -c, -l and --append(command line
        arguments of currently running kenrel form /proc/cmdline) option.
        Then exec into kexec kernel.

        Test passes if both the kexec load and the execution into the
        kexec kernel go fine; otherwise, it fails."
        """

        kexec_load_cmd = self.get_kexec_load_cmd(syscall_load=True)
        ret = self.load_kexec_kernel(kexec_load_cmd)
        if self.os_level_secureboot:
            self.assertFalse(ret, "Kexec load pass, with -c option")
        else:
            self.assertTrue(ret, "Kexec load failed, with -c option")

        kexec_exec_cmd = self.get_kexec_exec_command(exec_opt=True)
        if self.os_level_secureboot:
            ret = self.execute_kexec_cmd(kexec_exec_cmd)
            self.assertFalse(ret, "Kexec exec pass, with -c option")
        else:
            ret = self.execute_kexec_cmd(kexec_exec_cmd, raw_pty_console=True)
            self.assertTrue(ret, "Kexec exec failed, with -c option")

    def test_kexec_force(self):
        """
        Test kexec load and exec into kexec kernel using --force (-f) option.

        Test passes if kexec kerne boots fine; otherwise, it fails."
        """

        kexec_force_cmd = self.get_kexec_load_cmd(add_arg="-f")
        ret = self.execute_kexec_cmd(kexec_force_cmd, raw_pty_console=True)
        self.assertTrue(ret, kexec_force_cmd + "failed")

    def test_kexec_single_step(self):
        """
        Test kexec loading and exec into kexec kernel in a single step.

        The kexec command used here doesn't use -l and -e option.

        Test passes if kexec kernel boots fine; otherwise, it fails."
        """

        kexec_cmd = self.get_kexec_load_cmd(load_opt=False)
        ret = self.execute_kexec_cmd(kexec_cmd, raw_pty_console=True)
        self.assertTrue(ret, kexec_cmd + "failed")

    def test_kexec_in_loop(self):
        """
        Perform kexec in loop.

        Loop count is configured using num_of_iterations configuration option.

        Test passes if kexec kernel boots fine for all iteration; otherwise,
        it fails.
        """

        kexec_load_cmd = self.get_kexec_load_cmd(load_opt=False)
        log.info("Kexec loop count: %s " % str(self.num_of_iterations))

        for i in range(1, int(self.num_of_iterations)+1):
            ret = self.execute_kexec_cmd(kexec_load_cmd, raw_pty_console=True,
                                         sys_reset=False)
            self.assertTrue(ret, "kexec failed, at iteration cnt: " + str(i))
            log.info("Completed kexec iteration cnt %s." % str(i))


def kexec_suite():
    """kexec test suite"""

    suite = unittest.TestSuite()
    suite.addTest(OpTestKexec('test_load_unload'))
    suite.addTest(OpTestKexec('test_load_and_exec'))
    suite.addTest(OpTestKexec('test_kexec_force'))
    suite.addTest(OpTestKexec('test_kexec_single_step'))
    suite.addTest(OpTestKexec('test_file_load_and_exec'))
    suite.addTest(OpTestKexec('test_syscall_load_and_exec'))
    suite.addTest(OpTestKexec('test_kexec_in_loop'))
    return suite
