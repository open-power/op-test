#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/Crashtool.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2025
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
#Author: Shirisha Ganta <shirisha@linux.ibm.com>

import unittest
import os
import OpTestConfiguration
import OpTestLogger

from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class CrashToolInteractiveTest(unittest.TestCase):
    """
    Detects and validates the latest crash dump (vmcore) under /var/crash/

    Identifies appropriate debug symbols (vmlinux) based on the OS (e.g., RHEL or SLES)

    Launches crash vmlinux vmcore in interactive mode on the console

    Executes a sequence of commands (log, bt, ps, etc.) in a single session

    Verifies command output and exits cleanly from the crash shell
    """

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.op_test_util = OpTestUtil(conf)
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.console = self.cv_SYSTEM.console.get_console()
        self.distro = self.op_test_util.distro_name()
        self.version = self.op_test_util.get_distro_version().split(".")[0]
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        try:
            self.crash_commands = conf.args.crash_commands
        except AttributeError:
            self.crash_commands = "log,bt,ps,runq,kmem -i,kmem -o,kmem -h,vm,sys,mod"
        self.commands = [cmd.strip() for cmd in self.crash_commands.split(",")]

    def run_crash_command(self, cmd, timeout=180):
        """
        1.Sends a command to the running crash session
        2.Waits for the crash> prompt again
        3.Captures and returns command output, stripping echo
        4.If timeout or error occurs, raises an exception unless the prompt is found
        """
        self.console.sendline(cmd)
        try:
            self.console.expect_exact("crash>", timeout=180)
            full_output = self.console.before.strip()
            lines = full_output.splitlines()
            if lines and lines[0].strip() == cmd:
                lines = lines[1:]
            output = "\n".join(lines).strip()
            return output
        except Exception as e:
            if "crash>" in self.console.before:
                full_output = self.console.before.strip()
                lines = full_output.splitlines()
                if lines and lines[0].strip() == cmd:
                    lines = lines[1:]
                return "\n".join(lines).strip()
            else:
                raise Exception(
                    f"Crash command '{cmd}' timed out or failed") from e

    def verify_packages(self):
        """
        Verifies that required debug packages are installed based on distro.
        Raises OpTestError if any package is missing.
        """
        # Determine which packages to check
        if self.distro.lower() == "sles":
            required_pkgs = ["kernel-default-debuginfo",
                             "kernel-default-debugsource", "crash"]
        elif self.distro.lower() == "rhel":
            required_pkgs = ["kernel-debuginfo",
                             "kernel-debuginfo-common-ppc64le", "crash"]

        # Check each package
        for pkg in required_pkgs:
            cmd = f"rpm -q {pkg}"
            output = self.cv_HOST.host_run_command(cmd)
            if any(x in output[0] for x in ["not installed", "is not installed", "package {} is not installed".format(pkg)]):
                raise OpTestError(f"Required package '{pkg}' is not installed")

        log.info(
            f"All required debug packages for {self.distro} are installed.")

    def runTest(self):
        """
        1.Gets kernel version (uname -r)
        2.Finds latest crash directory (e.g., /var/crash/2025-06-03-07-08/)
        3.Validates vmcore file type and size
        4.Detects OS type/version and constructs appropriate vmlinux path
        5.Launches crash interactively
        6.Runs commands (stored in self.commands)
        7.Exits crash cleanly
        """
        self.verify_packages()
        kernel_version = self.cv_HOST.host_run_command("uname -r")[0].strip()
        cmd = "ls -1td /var/crash/*/ | head -n 1 | xargs basename"
        crash_dir = self.cv_HOST.host_run_command(cmd)[0].strip()
        vmcore_path = f"/var/crash/{crash_dir}/vmcore"
        file_info = self.cv_HOST.host_run_command(f"file {vmcore_path}")
        size_check = self.cv_HOST.host_run_command(f"stat -c %s {vmcore_path}")
        vmcore_size = int(size_check[0].strip())

        if "vmcore" not in file_info[0] or vmcore_size < 100000:
            self.fail("Invalid or corrupted vmcore")
        if self.distro == "rhel":
            vmlinux = f"/usr/lib/debug/lib/modules/{kernel_version}/vmlinux"
        elif (self.distro == "sles") and self.version == "16":
            vmlinux = f"/boot/vmlinux-{kernel_version}"
            debug_info = f"/usr/lib/debug/usr/lib/modules/{kernel_version}/vmlinux.debug"
            vmlinux = f"{vmlinux} {debug_info}"

        elif self.distro == "sles":
            vmlinux = f"/boot/vmlinux-{kernel_version}"

        crash_cmd = f"crash {vmlinux} {vmcore_path}"
        self.console.sendline(crash_cmd)
        try:
            self.console.expect_exact("crash>", timeout=300)
        except Exception as e:
            if "crash>" not in self.console.before:
                raise Exception(
                    "Crash tool failed to launch or kernel panic detected") from e

        # Set scroll off to avoid pager issues
        self.run_crash_command("set scroll off")

        # Run each command and capture output
        for cmd in self.commands:
            log.info("------------Output for cmd %s --------------" % (cmd))
            self.run_crash_command(cmd)

        # Exit crash session
        self.console.sendline("exit")
        self.console.expect("#", timeout=30)
