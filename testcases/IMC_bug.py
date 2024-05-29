#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/IMC_bug.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2019
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
# This test is to find IMC bug, when we try to cat files in IMC path.  

import unittest
import OpTestConfiguration

class ImcDebugfs(unittest.TestCase):
   def setUp(self):
       conf = OpTestConfiguration.conf
       self.cv_IPMI = conf.ipmi()
       self.cv_SYSTEM = conf.system()
       self.cv_HOST = conf.host()
       self.cv_BMC = conf.bmc()
       self.platform = conf.platform()
       self.bmc_type = conf.args.bmc_type
       self.util = self.cv_SYSTEM.util
       self.c = self.cv_SYSTEM.console

class Imc(ImcDebugfs):
   def fsbug(self):
       self.c.run_command("cat /sys/kernel/debug/powerpc/imc/*")

   def runTest(self):
       self.fsbug()

def crash_suite():
   s = unittest.TestSuite()
   s.addTest(Imc())
   return s
