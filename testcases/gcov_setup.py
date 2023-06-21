#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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
import tempfile
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Gcov(unittest.TestCase):
    '''
    Install the distro src  kernel and gcov is enabled and booted with
    newly installed kernel
    '''
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.util = OpTestUtil(OpTestConfiguration.conf)


    def runTest(self):
        '''
        Running the gcov test
        '''
        log.info("OS: %s" %self.util.distro_name())
        log.info("\nInstalling the ditro src...")
        src_path = self.util.get_distro_src('kernel', '/root', "-bp")
        out = self.cv_HOST.host_run_command(f"ls {src_path}")
        for line in out:
            if line.startswith("linux-"):
                src_path = os.path.join(src_path, line)
                break
        log.info("\n\nsource path = %s" %src_path)
        log.info("\nadding gcov_param....")
        self.kernel_config(src_path)
        log.info("Building the new kernel...")
        self.build_and_boot(src_path)
        log.info("rebooting the lpar after building the src with kernel parameters")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def kernel_config(self, dest_path):
        """
        Add the gcov related kernel config parameter
        """
        if dest_path is None:
            log.error("Please provide a valid path")
            return ""
        k_version = "".join(self.cv_HOST.host_run_command("uname -r"))
        boot_conf_file = f"/boot/config-{k_version}"
        src_conf_file = f"{dest_path}/.config"
        log.info(f"copying {boot_conf_file} {src_conf_file}")
        self.cv_HOST.host_run_command(f"cp {boot_conf_file} {src_conf_file}")
        log.info("\n\n Adding the kernel_config_parameter....")
        self.add_gcov_param(src_conf_file)

    def add_gcov_param(self, conf_file):
        """
        Adding the gcov kernel parameter to enable it.
        """
        k_config_params = ["CONFIG_GCOV_KERNEL=y", "CONFIG_ARCH_HAS_GCOV_PROFILE_ALL=y", "CONFIG_DRM_AMDGPU=m", "CONFIG_DRM_AMDGPU_USERPTR=m"]
        k_config_params.extend(["CONFIG_GCOV_PROFILE_ALL=y", "CONFIG_GCOV_PROFILE_FTRACE=y", "CONFIG_DEBUG_INFO_BTF=m", "CONFIG_DRM_NOUVEAU=m"])
        k_config_params.extend(["CONFIG_DRM_NOUVEAU_BACKLIGHT=m", "CONFIG_HWMON=m", "CONFIG_DRM_RADEON=m", "CONFIG_DRM_RADEON_USERPTR=m", "CONFIG_FB_RADEON=m"])
        k_config_params.extend(["CONFIG_DRM_I2C_CH7006=m", "CONFIG_DRM_I2C_SIL164=m", "CONFIG_VIRTIO=m", "CONFIG_VIRTIO_FS=m", "CONFIG_HW_RANDOM_VIRTIO=m"])
        k_config_params.extend(["CONFIG_DRM_VIRTIO_GPU=m", "CONFIG_SND_VIRTIO=m", "CONFIG_DRM_QXL=m", "CONFIG_VGA_ARB=m", "CONFIG_VGA_CONSOLE=y"])
        k_config_params.extend(["CONFIG_INFINIBAND=m", "CONFIG_INFINIBAND_VIRT_DMA=m", "CONFIG_HID=m", "CONFIG_DRM_FBDEV_EMULATION=m", "CONFIG_DRM_KMS_HELPER=m"])
        k_config_params.extend(["CONFIG_DRM_VKMS=m", "CONFIG_DRM_BOCHS=m", "CONFIG_DRM_CIRRUS_QEMU=m", "CONFIG_FB_MATROX=m", "CONFIG_FB_MATROX_G=m"])
        k_config_params.extend(["CONFIG_DRM_AST=m"])
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
        if err_param:
            self.fail("few param did not got updated: %s" %err_param)

    def build_and_boot(self, config_path):
        """
        building and booting the newly installed kernel
        """
        self.cv_HOST.host_run_command(f"cd {config_path}")
        self.cv_HOST.host_run_command("make olddefconfig")
        cmd = f"make -j $nproc && make -j $nproc modules_install && make install"
        self.cv_HOST.host_run_command(cmd)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
