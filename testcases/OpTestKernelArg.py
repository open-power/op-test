#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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


import unittest

import OpTestConfiguration
from common import OpTestInstallUtil


class OpTestKernelArg(unittest.TestCase):
    '''
    KernelArgTest
    -------------

    Test will add/remove kernel commandline argument based on the user input
    from --add-kernel-args/--remove-kernel-args and reboots the system to get
    it reflected

    Example: ./op-test --add-kernel-args "hugepagesz=1G default_hugepagesz=1G hugepages=5" \
             --remove-kernel-args "disable_radix" <other args..>
    '''

    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.kernel_add_args = self.conf.args.add_kernel_args
        self.kernel_remove_args = self.conf.args.remove_kernel_args
        if not (self.kernel_add_args or self.kernel_remove_args):
            self.fail("Provide either --add-kernel-args and "
                      "--remove-kernel-args option")

    def runTest(self):
        obj = OpTestInstallUtil.InstallUtil()
        if not obj.update_kernel_cmdline(self.kernel_add_args,
                                         self.kernel_remove_args):
            self.fail("KernelArgTest failed to update kernel args")
