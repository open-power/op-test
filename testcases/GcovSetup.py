#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2023
# [+] International Business Machines Corp.
# Author: Naresh Bannoth <nbannoth@linux.vnet.ibm.com>
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

'''
gcov
----

A "Test Case" for extracting GCOV code coverage data for linux kernel.
Installs the kernel source and build the kernel with gcov enabled.
'''

import os
import unittest
import time
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class GcovBuild(unittest.TestCase):
    '''
    Install the distro src  kernel and gcov is enabled and booted with
    newly installed kernel
    '''
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.host_cmd_timeout = self.conf.args.host_cmd_timeout
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.util = OpTestUtil(OpTestConfiguration.conf)


    def runTest(self):
        '''
        Running the gcov test
        '''
        self.distro_name = self.util.distro_name()
        log.info("OS: %s" %self.distro_name)
        if self.distro_name == 'rhel':
            self.installer = "yum install"
        elif self.distro_name == 'sles':
            self.installer = "zypper install"
        dep_packages = ["rpm-build", "gcc*", "perl*", "tiny*"]
        log.info(f"\nInstalling following dependency packages\n {dep_packages}")
        for pkg in dep_packages:
            if self.distro_name == 'rhel':
                dep_packages.append("yum-utils")
                self.cv_HOST.host_run_command(f"{self.installer} {pkg} -y")
            elif self.distro_name == 'sles':
                self.cv_HOST.host_run_command(f"{self.installer} -y {pkg}")
        log.info("\nInstalling the ditro src...")
        if self.distro_name == 'rhel':
            src_path = self.util.get_distro_src('kernel', '/root', "-bp")
        elif self.distro_name == 'sles':
            src_path = self.util.get_distro_src('kernel-default', '/root', "-bp", "linux")
        src_path_base = src_path
        out = self.cv_HOST.host_run_command(f"ls {src_path}")
        for line in out:
            if line.startswith("linux-"):
                src_path = os.path.join(src_path, line)
                break
        log.info("\n\nsource path = %s" %src_path)
        self.cv_HOST.host_run_command('mkdir -p /root/kernel')
        self.cv_HOST.host_run_command('mv %s /root/kernel/linux' %src_path)
        self.cv_HOST.host_run_command('rm -rf %s' %src_path_base)
        src_path = '/root/kernel/linux'
        log.info("\nadding gcov_param....")
        self.kernel_config(src_path)
        log.info("Building the new kernel...")
        self.build_and_boot(src_path)
        log.info("rebooting the lpar after building the src with kernel parameters")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        time.sleep(10)
        self.validate_gcov_enablement(src_path)

    def kernel_config(self, dest_path):
        """
        Add the gcov related kernel config parameter
        """
        if dest_path is None:
            log.error("Please provide a valid path")
            return ""
        boot_conf_file = self.cv_HOST.host_run_command(f"ls /boot/ | grep -i config-")[0]
        boot_conf_file = f"/boot/{boot_conf_file}"
        src_conf_file = f"{dest_path}/.config"
        log.info(f"copying {boot_conf_file} {src_conf_file}")
        self.cv_HOST.host_run_command(f"cp {boot_conf_file} {src_conf_file}")
        log.info("\n\n Adding the kernel_config_parameter....")
        self.add_gcov_param(src_conf_file)

    def add_gcov_param(self, conf_file):
        """
        Adding the gcov kernel parameter to enable it.
        """
        k_config_params = ["CONFIG_GCOV_KERNEL=y", "CONFIG_ARCH_HAS_GCOV_PROFILE_ALL=y", "CONFIG_GCOV_PROFILE_ALL=y", "CONFIG_GCOV_PROFILE_FTRACE=y"]
        err_param = []
        for param in k_config_params:
            log.info("\n working on param  %s" %param)
            unset_param = param
            if param.split("=")[-1] == "y":
                new_param = param[:-1] + "m"
            else:
                new_param = param[:-1] + "y"

            out = int("".join(self.cv_HOST.host_run_command(f"grep -n ^{param} {conf_file} | wc -l")))
            new_out = int("".join(self.cv_HOST.host_run_command(f"grep -n ^{new_param} {conf_file} | wc -l")))
            if param.split("=")[-1] == "m":
                new_unset_param = unset_param.split("=")[0]
                unset_out = int("".join(self.cv_HOST.host_run_command(f"grep -n '{new_unset_param} is not set' {conf_file} | wc -l")))
                if unset_out == 1:
                    continue

            if param.split("=")[-1] == "m":
                param = f"#{param}"
            if out == 1:
                if param.split("=")[-1] == "m":
                    log.info("param found but needs to unset....\n unsetting the param")
                    self.cv_HOST.host_run_command(f"sed -i 's/^{unset_param}/{param}/g' {conf_file}")
                else:
                    log.info("%s parameter already available with same value, So skipping to change it" %param)
                    continue
            elif new_out == 1:
                log.info("%s parameter exists with opposit valuue , changing it" %param)
                self.cv_HOST.host_run_command(f"sed -i 's/^{new_param}/{param}/g' {conf_file}")
            else:
                log.info("%s parameter does not exists, so appending" %param)
                self.cv_HOST.host_run_command(f"echo {param} >> {conf_file}")

            out_check = int("".join(self.cv_HOST.host_run_command(f"grep -n ^{param} {conf_file} | wc -l")))
            if out_check == 1:
                log.info("%s  param added/changed successfully" %param)
            else:
                log.info("param failed to change {param}")
                err_param.append(param)
            log.info("\n\n\n")
        if self.distro_name == 'sles':
            self.cv_HOST.host_run_command(f"sed -i 's/^.*CONFIG_SYSTEM_TRUSTED_KEYS/#&/g' {conf_file}")
        if err_param:
            self.fail("few param did not got updated: %s" %err_param)

    def build_and_boot(self, config_path):
        """
        building and booting the newly installed kernel
        """
        try:
            onlinecpus = int(self.cv_HOST.host_run_command("lscpu --online -e|wc -l")[-1])
        except Exception:
            onlinecpus = 20

        self.cv_HOST.host_run_command(f"cd {config_path}")
        self.cv_HOST.host_run_command("make olddefconfig")
        try:
            self.cv_HOST.host_run_command("make -j %s" %onlinecpus , timeout=self.host_cmd_timeout)
            cmd = f"make -j modules_install && make install"
            if not self.cv_HOST.host_run_command(cmd):
                self.fail("module installation failed")
        except Exception:
            self.fail("compile and build of gcov kernel failed")

    def validate_gcov_enablement(self, gcov_src_path):
        """
        validating whether gcov enabled or not after build and boot with gcov kernel parameter
        """
        sys_path = "/sys/kernel/debug/gcov/"
        log.info("\n validating gcov enablement after boot....\n")
        if self.cv_HOST.host_run_command(f"ls -d {sys_path}"):
            log.info("\ngcov_dir exists\n\n checking for kernel_src...\n\n")
            fin_path = os.path.join(sys_path, gcov_src_path)
            if self.cv_HOST.host_run_command(f"ls -d {fin_path}"):
                log.info("Successfully enabled the gcov flags")
            else:
                self.fail("gcov flag enabled but src files not exists")
        else:
            log.info("gcov dir not found....\nfailed to enable gcov_flag")
