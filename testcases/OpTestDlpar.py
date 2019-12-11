#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDlpar.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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
'''
OpTestDlpar
------------
This module contain testcases related to DLPAR.
The prerequisite is that the necessary DLPAR
packages have to be setup on the system and the
profiles of the LPAR must be defined.
In addition to it, few variables as mentioned below
must be defined in ~/.op-test-framework.conf
'''
import unittest
import logging
import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC, OpTestFSP
from common import OpTestHMC
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
class OpTestDlpar(unittest.TestCase):
   def setUp(self):
      conf = OpTestConfiguration.conf
      self.cv_SYSTEM = conf.system()
      conf = OpTestConfiguration.conf
      self.hmc_user = conf.args.hmc_username
      self.hmc_password = conf.args.hmc_password
      self.hmc_ip = conf.args.hmc_ip
      self.lpar_name = conf.args.lpar_name
      self.system_name = conf.args.system_name
      self.cv_HMC = self.cv_SYSTEM.hmc
      # The following variables needs to be defined in
      # ~/.op-test-framework.conf
      self.cpu_resource = conf.args.cpu_resource
      self.mem_resource = conf.args.mem_resource
      self.lpar2_name = conf.args.lpar2_name

   def AddRemove(self,res_type,res_option,operation,res_num):
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                 %(res_type, self.system_name, self.lpar_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                 %(res_type, self.system_name, self.lpar_name))
      log.debug("chhwres -r %s -m %s -o %s -p %s %s %s"
                 %(res_type,self.system_name,operation,self.lpar_name,
                 res_option,res_num))
      self.cv_HMC.run_command("chhwres -r %s -m %s -o %s -p %s %s %s"
                 %(res_type,self.system_name,operation,self.lpar_name,
                 res_option,res_num))
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                 %(res_type,self.system_name,self.lpar_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                 %(res_type,self.system_name,self.lpar_name))

   def Move(self,res_type,res_option,res_num):
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar_name))
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar2_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar2_name))
      log.debug("chhwres -r %s -m %s -o m -p %s -t %s %s %s"
                     % (res_type,self.system_name,self.lpar_name,self.lpar2_name,res_option,res_num))
      self.cv_HMC.run_command("chhwres -r %s -m %s -o m -p %s -t %s %s %s"
                     % (res_type,self.system_name,self.lpar_name,self.lpar2_name,res_option,res_num))
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     % (res_type,self.system_name,self.lpar_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     % (res_type,self.system_name,self.lpar_name))
      log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     % (res_type,self.system_name,self.lpar2_name))
      self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     % (res_type,self.system_name,self.lpar2_name))

class DlparCPUBasic(OpTestDlpar,unittest.TestCase):
   '''Class for DLPAR CPU Basic Tests
      This class allows --run testcases.OpTestDlpar.DlparCPUBasic
   '''
   def setUp(self):
      super(DlparCPUBasic, self).setUp()
   def runTest(self):
      self.AddRemove("proc","--procs","a",self.cpu_resource)
      self.AddRemove("proc","--procs","r",self.cpu_resource)
      self.Move("proc","--procs",self.cpu_resource)

class DlparMemBasic(OpTestDlpar,unittest.TestCase):
   '''Class for DLPAR Memory Basic Tests
      This class allows --run testcases.OpTestDlpar.DlparMemBasic
   '''
   def setUp(self):
      super(DlparMemBasic, self).setUp()
   def runTest(self):
      self.AddRemove("mem","-q","a",self.mem_resource)
      self.AddRemove("mem","-q","r",self.mem_resource)
      self.Move("mem","-q",self.mem_resource)
global conf

