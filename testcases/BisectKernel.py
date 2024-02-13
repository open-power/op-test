#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
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

import unittest
import os
from urllib.parse import urlparse
from enum import Enum

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestInstallUtil import InstallUtil
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class Status(Enum):
    """
    Enumeration to maintain bisect status
    """
    FAIL = 1
    SUCCESS = 0

class BisectCategory(Enum):
    """
    Enumeration to maintain the bisect category
    """
    BUILD = "BUILD"
    PERF = "PERF"

class BisectKernel(unittest.TestCase):
    """
    Test case for bisecting the Linux kernel using Git Bisect.

    This test downloads the Linux kernel from a specified repository,
    configures and compiles it, and then uses Git Bisect to find the
    commit that introduced a specific issue.
    """
    def setUp(self):
        """
        Set up the test environment.

        Initializes test parameters and checks required configurations.
        """
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.connection = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.console_thread = OpSOLMonitorThread(1, "console")
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.repo = self.conf.args.git_repo
        self.repo_reference = self.conf.args.git_repo_reference
        self.branch = self.conf.args.git_branch
        self.home = self.conf.args.git_home
        self.config_path = self.conf.args.git_repoconfigpath
        self.config = self.conf.args.git_repoconfig
        self.good_commit = self.conf.args.good_commit
        self.bad_commit = self.conf.args.bad_commit
        self.bisect_script = self.conf.args.bisect_script
        self.bisect_category = self.conf.args.bisect_category
        self.append_kernel_cmdline = self.conf.args.append_kernel_cmdline
        self.linux_path = os.path.join(self.home, "linux")
        # Check and set default values for some parameters
        if self.config_path:
            self.config = "olddefconfig"
        if not self.repo:
            self.fail("Provide git repo of kernel to install")
        if not (self.conf.args.host_ip and self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host ip user details refer, --host-{ip,user,password}")

    @staticmethod
    def is_url(path):
        """
        Check if the given path is a URL.
        """
        valid_schemes = {'http', 'https', 'git', 'ftp'}
        return urlparse(path).scheme in valid_schemes

    def download_kernel(self):
        """
        Download the Linux kernel from the specified repository.
        """
        try:
            # Create the directory if it doesn't exist
            self.connection.run_command("[ -d {} ] || mkdir -p {}".format(self.home, self.home))

            # Remove existing Linux kernel directory if it exists
            self.connection.run_command("if [ -d {} ]; then rm -rf {}; fi".format(self.linux_path, self.linux_path), timeout=600)

            # Clone the Linux kernel repository
            git_clone_command = "cd {} && git clone {} -b {}".format(self.home, self.repo, self.branch)
            if self.repo_reference:
                git_clone_command += " --reference {}".format(self.repo_reference)

            # Clone the linux kernel repository
            self.connection.run_command(git_clone_command, timeout=self.host_cmd_timeout)

            # Change directory to the Linux kernel path
            self.connection.run_command("cd {}".format(self.linux_path))

            # Log successful kernel download
            log.info("Kernel download successful")

        except Exception as e:
            # Log any errors that occur during kernel download
            self.fail("An error occurred during kernel download: {}".format(str(e)))

    def download_kernel_config(self):
        """
        Download the kernel configuration file.
        """
        try:
            if self.config_path:
                if self.is_url(self.config_path):
                    # Download the kernel configuration file from a URL
                    config_file_path = os.path.join(self.linux_path, '.config')
                    self.connection.run_command("wget {} -O {}".format(self.config_path, config_file_path))
                    log.info("Downloaded config file from URL: {} to {}".format(self.config_path, config_file_path))
                else:
                    # Copy the kernel configuration file from the host to the target
                    self.cv_HOST.copy_test_file_to_host(
                        self.config_path, sourcedir="", dstdir=os.path.join(self.linux_path, ".config"))
                    log.info("Copied config file from host: {} to {}".format(self.config_path, self.linux_path))
            else:
                # Log if configuration is not provided
                log.info("Configuration not provided")

        except Exception as e:
            # Log any errors that occur during kernel config download
            self.fail("An error occurred during kernel config download: {}".format(str(e)))

    def bisect_kernel_init(self):
        """
        Start the Git Bisect process for kernel bisecting.
        """
        try:
            # Start the Git Bisect process
            self.connection.run_command("git bisect start")
            log.info("Bisecting kernel: Started Git Bisect process")

            # Mark the known bad commit
            self.connection.run_command("git bisect bad {}".format(self.bad_commit), timeout=self.host_cmd_timeout)
            log.info("Bisecting kernel: Marked known bad commit {}".format(self.bad_commit))

            # Mark the known good commit
            self.connection.run_command("git bisect good {}".format(self.good_commit), timeout=self.host_cmd_timeout)
            log.info("Bisecting kernel: Marked known good commit {}".format(self.good_commit))

        except Exception as e:
            # Log any errors that occur during kernel bisecting
            self.fail("Error during kernel bisecting: {}".format(str(e)))

    def boot_kernel(self):
        """
        Boot the Linux kernel.
        """
        log.info("Booting the kernel")

        # Fetch the current kernel command line
        cmdline = self.connection.run_command("cat /proc/cmdline")[-1]
        log.info("Kernel command line: {}".format(cmdline))

        # Append additional kernel command line if provided
        if self.append_kernel_cmdline:
            cmdline += " {}".format(self.append_kernel_cmdline)

        # Get the kernel release string
        kern_rel_str = self.connection.run_command(
            "cat {}/include/config/kernel.release".format(self.linux_path))[-1]
        log.info("Kernel release string: {}".format(kern_rel_str))

        # Attempt to find the initrd file with the kernel release string
        try:
            initrd_file = self.connection.run_command(
                "ls -l /boot/initr*-{0}.img".format(kern_rel_str))[-1].split(" ")[-1]
            log.info("Initrd file found: {}".format(initrd_file))
        except Exception:
            initrd_file = self.connection.run_command(
                "ls -l /boot/initr*-{0}".format(kern_rel_str))[-1].split(" ")[-1]
            log.info("Initrd file found: {}".format(initrd_file))

        # Build the kexec command line
        kexec_cmdline = "kexec -ls --initrd {0} --command-line=\"{1}\" /boot/vmlinu*-{2}".format(initrd_file, cmdline, kern_rel_str)
        log.info("Kexec starting command line: {}".format(kexec_cmdline))

        try:
            # Run kexec and execute the new kernel
            self.connection.run_command("{} && kexec -e".format(kexec_cmdline))
        except Exception as e:
            # Log any errors that occur during kexec
            log.info("Kexec done! continuing..")

        # Check the kernel version after booting
        self.connection.run_command("uname -r")

    def build_kernel(self, onlinecpus):
        """
        Build and install the Linux kernel.
        """
        try:
            # Build the Linux kernel with the specified number of CPUs
            build_command = "make -j {} -s && make modules_install && make install".format(onlinecpus)
            self.connection.run_command(build_command, timeout=self.host_cmd_timeout)

            # Log successful kernel build
            log.info("Kernel build successful")

            return Status.SUCCESS.value
        except CommandFailed as e:
            # Log the failure and return the failure status
            log.error("Kernel build failed: {}".format(e))
            return Status.FAIL.value

    def reset_state(self):
        """
        Reset the current state to the initial state.
        """
        self.connection.run_command("git add . && git reset --hard HEAD")
        log.info("Resetting the state")

    def mark_commit(self, status):
        """
        Mark the current commit as good, bad, or skip based on the status.
        """
        if status == Status.SUCCESS.value:
            log.info("Marking current commit as good")
            return self.connection.run_command("git bisect good")
        elif status == Status.FAIL.value:
            log.info("Marking current commit as bad")
            return self.connection.run_command("git bisect bad")
        elif status == Status.SKIP.value:
            log.info("Skipping the bisect!")
            return self.connection.run_command("git bisect skip")
        else:
            log.warning("Invalid status: {}".format(status))
            return []

    def run_perf_bisect_script(self):
        """
        Run the performance bisect script and return the result.
        """
        perf_retval = Status.SUCCESS.value

        try:
            perf_retval = int(self.connection.run_command("python3 {}".format(str(self.bisect_script)))[0])
            log.info("Running bisect script. Return value: {}".format(perf_retval))
        except CommandFailed:
            self.fail("Bisect script failed. Return value: {}! Exiting!".format(perf_retval))

        return perf_retval

    def handle_build_bisect(self, build_status):
        """
        Handle the Git Bisect process for build bisecting.
        """
        self.reset_state()
        return self.mark_commit(build_status)

    def handle_perf_bisect(self, build_status):
        """
        Handle the Git Bisect process for performance bisecting.
        """
        if build_status != Status.SUCCESS.value:
            return self.mark_commit(Status.SKIP.value)

        log.info("Booting the kernel using kexec...")
        self.boot_kernel()

        log.info("System rebooted. Starting bisect...")
        self.connection.run_command("cd {}".format(self.linux_path))
        perf_retval = self.run_perf_bisect_script()

        return self.mark_commit(perf_retval)


    def bisect_kernel(self, onlinecpus):
        """
        Handle Git Bisect based on the specified bisect category
        """
        try:
            log.info("Compiling and installing Linux kernel")

            # Change the current directory to the Linux kernel source path
            self.connection.run_command("cd {}".format(self.linux_path))

            # Compile and install the kernel
            self.connection.run_command("make {}".format(self.config))
            res = self.connection.run_command("make kernelrelease")
            log.info("Upstream kernel version: {}".format(res[-1]))

            # Get the build status of the kernel
            build_status = self.build_kernel(onlinecpus)

            git_bisect_out = []

            if self.bisect_category == BisectCategory.BUILD.value:
                git_bisect_out = self.handle_build_bisect(build_status)
            elif self.bisect_category == BisectCategory.PERF.value:
                git_bisect_out = self.handle_perf_bisect(build_status)

            return git_bisect_out

        except Exception as e:
            # Log an error if an exception occurs during kernel build and installation
            self.fail("An error occurred during kernel build and installation: {}".format(str(e)))
            return []

    def runTest(self):
        """
        Run a test that involves iterative kernel builds using Git Bisect.

        This method performs a series of steps, including setting up for kernel testing, 
        and using Git Bisect to identify a commit causing an issue.
        """
        # Start the console thread
        self.console_thread.start()

        try:
            try:
                onlinecpus = int(self.connection.run_command("grep -c '^processor' /proc/cpuinfo")[-1])
                log.info("Online CPUs detected: {}".format(onlinecpus))
            except Exception as e:
                # Handle exception with fallback value for onlinecpus
                onlinecpus = 20
                log.info("Failed to detect online CPUs. Using default value: {} {}".format(onlinecpus, e))

            # Perform necessary setup
            self.download_kernel()
            self.download_kernel_config()
            self.bisect_kernel_init()

            while True:
                # Iterative build and install kernel with Git Bisect
                git_bisect_out = self.bisect_kernel(onlinecpus)
                git_bisect_out_msg = git_bisect_out[0]

                if "first bad" in git_bisect_out_msg:
                    # Identified the commit causing the issue
                    log.info("Issue identified. Caused by: {}".format(git_bisect_out))
                    break
                else:
                    # Git Bisect continues
                    log.info("Git Bisect continues: {}".format(git_bisect_out_msg))

            self.cv_HOST.host_gather_opal_msg_log()
            self.cv_HOST.host_gather_kernel_log()

        finally:
            if self.console_thread.is_alive():
                self.console_thread.console_terminate()
