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
---------

This test is to validate kexec commands
'''

import os
import pexpect
import unittest
import OpTestLogger

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
from common.OpTestError import OpTestError
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestKexec(unittest.TestCase):

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

    def get_raw_pty_console(self,cmd):
        """
        This function executes the command in raw_pty console 
        """
        try:
            raw_pty = self.cv_SYSTEM.console.get_console()
            raw_pty.sendline(cmd)
            raw_pty.expect("login:", timeout=600)
            log.info("{} passed(SUCCESS)".format(cmd))
        except CommandFailed:
            log.info("{} failed with exception.".format(cmd))

    def kexec_load_unload(self, arg):
        """
        This function will test the kexec load or unload based on arg
        """
        try:
            if arg is "l":
                self.c.run_command("kexec -l /boot/{} --initrd /boot/{} --append=\"`cat /proc/cmdline`\"".format(self.kernel_image,self.initrd_image))
            elif arg is "u":
                self.c.run_command("kexec -u")
        except CommandFailed:
            kexec_loaded_status = self.c.run_command("cat /sys/kernel/kexec_loaded")
            if kexec_loaded_status[0] == "0":
                log.info("Failed to load kernel image = \"%s\"", self.kernel_image)
            raise OpTestError("kexec -l failed to load kernel")
        
    def kexec_first_load_then_exec(self):
        """
        This function first tests kexec load and then exec(-e) 
        """
        self.kexec_load_unload("l")
        cmd="kexec -e"
        self.get_raw_pty_console(cmd)


    def kexec_force(self):
        """
        This function tests the kexec force(-f)
        """
        cmd="kexec -f /boot/{} --initrd /boot/{} --append=\"`cat /proc/cmdline`\"".format(self.kernel_image,self.initrd_image)
        self.get_raw_pty_console(cmd)

    def kexec_load_and_exec(self):
        """
        This function tests the kexec -l and -e together
        """
        cmd="kexec -l -e /boot/{} --initrd /boot/{} --append=\"`cat /proc/cmdline`\"".format(self.kernel_image,self.initrd_image)
        self.get_raw_pty_console(cmd)

    def kexec_multiboot(self):
        """
        This function tests the kexec multi-boot in loop 
        """
        log.info("Start a loop of %s iterations to run  kexec -l -e together", self.num_of_iterations)
        for i in range(int(self.num_of_iterations)):
            log.info("kexec multiboot test: LOOP=%s", i)
            self.kexec_load_and_exec()

class Kexec_Operations(OpTestKexec):

    def runTest(self):
        self.c.run_command("uname -a")
        self.c.run_command("cat /etc/os-release")
        self.c.run_command("kexec --version")
        self.kexec_load_unload("l")
        self.kexec_load_unload("u")
        self.kexec_first_load_then_exec()
        self.kexec_force()
        self.kexec_load_and_exec()
        self.kexec_multiboot()

def kexec_suite():
    s = unittest.TestSuite()
    s.addTest(Kexec_Operations())

    return s
