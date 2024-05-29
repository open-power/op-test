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
packages and HTX package(for extended cases) 
have to be setup on the system and the
profiles of the LPAR must be defined.
In addition to it, few variables as mentioned below
must be defined in ~/.op-test-framework.conf
cpu_resource - max number of CPU
mem_resource - max memory in MB
lpar2_name - name of destination lpar for move operation
loop_num - number of times to run loop
'''
import unittest
from os import path 
import OpTestConfiguration
import OpTestLogger
from random import randint
from common.OpTestSOL import OpSOLMonitorThread
log = OpTestLogger.optest_logger_glob.get_logger(__name__)
class OpTestDlpar(unittest.TestCase):
   def setUp(self):
      conf = OpTestConfiguration.conf
      self.cv_SYSTEM = conf.system()
      self.console = self.cv_SYSTEM.console
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
      self.loop_num = conf.args.loop_num
      self.console_thread = OpSOLMonitorThread(1, "console")
      self.console_thread.start()
      self.extended = {'loop':0,'wkld':0,'smt':0}
   def AddRemove(self,res_type,res_option,operation,res_num):
      #Generate a random number of CPU or memory to add or remove
      res_num = int(res_num)
      if (res_type == "proc"):
          #for x in range(res_num):
          res_num = randint(1,res_num)
          log.debug("Random number of resource generated for CPU is %s"%res_num)
      if (res_type == "mem"):
          res_mem = int(res_num/1024)
          #for x in range(res_mem):
          res_num = (randint(1,res_mem))*1024
          log.debug("Random number of memory generated for MEM is %s"%res_num)
      if(self.extended['loop'] != 1):
          log.debug("Loop is not on")
          self.loop_num = 1
      else:
          log.debug("Loop is on repeat %s %s times" %(operation,self.loop_num))
      count=0
      while (count < int(self.loop_num)):
          log.debug("Iteration %s"%count)
          if(self.extended['smt'] == 1):
              log.debug("smt is on, executing the script")
              self.console.run_command("nohup ./smt_script &")
          if(self.extended['wkld'] == 1):
              log.debug("Starting workload..")
              self.console.run_command("htxscreen -f mdt.all")
              self.extended['wkld'] = 0
          log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type, self.system_name, self.lpar_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type, self.system_name, self.lpar_name))
          log.debug("time chhwres -r %s -m %s -o %s -p %s %s %s"
                     %(res_type,self.system_name,operation,self.lpar_name,
                     res_option,res_num))
          self.cv_HMC.run_command_ignore_fail("time chhwres -r %s -m %s -o %s -p %s %s %s"
                     %(res_type,self.system_name,operation,self.lpar_name,
                     res_option,res_num))
          log.debug("time lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                     %(res_type,self.system_name,self.lpar_name))
          count=count+1
   def Move(self,res_type,res_option,res_num):
      if(self.extended['loop'] != 1):
          log.debug("Loop is not on")
          self.loop_num = 1
      else:
          log.debug("Loop is on repeat %s times" %self.loop_num)
      count=0
      while (count < int(self.loop_num)):
          log.debug("Iteration %s"%count)
          if(self.extended['smt'] == 1):
              log.debug("smt is on, executing the script")
              self.console.run_command("nohup ./smt_script &")
          if(self.extended['wkld'] == 1):
              log.debug("Starting workload..")
              self.console.run_command("htxscreen -f mdt.all")
              self.extended['wkld'] = 0
          log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         %(res_type,self.system_name,self.lpar_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         %(res_type,self.system_name,self.lpar_name))
          log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         %(res_type,self.system_name,self.lpar2_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         %(res_type,self.system_name,self.lpar2_name))
          log.debug("time chhwres -r %s -m %s -o m -p %s -t %s %s %s"
                         % (res_type,self.system_name,self.lpar_name,self.lpar2_name,res_option,res_num))
          self.cv_HMC.run_command_ignore_fail("time chhwres -r %s -m %s -o m -p %s -t %s %s %s"
                         % (res_type,self.system_name,self.lpar_name,self.lpar2_name,res_option,res_num))
          log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         % (res_type,self.system_name,self.lpar_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         % (res_type,self.system_name,self.lpar_name))
          log.debug("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         % (res_type,self.system_name,self.lpar2_name))
          self.cv_HMC.run_command("lshwres -r %s -m %s --level lpar --filter lpar_names=%s"
                         % (res_type,self.system_name,self.lpar2_name))
          count = count+1
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
class DlparCPUExtended(OpTestDlpar,unittest.TestCase):
   '''Class for DLPAR CPU Extended Tests
      This class allows --run testcases.OpTestDlpar.DlparCPUExtended
   '''
   def setUp(self):
      super(DlparCPUExtended, self).setUp()
   def runTest(self):
      if(path.exists("smt_script") != 1):
          self.console.run_command('echo -e "ppc64_cpu --smt=off\nsleep 10s\nppc64_cpu --smt=on\nfor i in `seq 1 5000`;\ndo\nppc64_cpu --smt\nppc64_cpu --smt=2\nsleep 10s\nppc64_cpu --smt\nppc64_cpu --smt=3\nsleep 10s \nppc64_cpu --smt\nppc64_cpu --smt=4\nsleep 10s \nppc64_cpu --smt\ndone\" > smt_script')
          self.console.run_command("chmod +x ./smt_script")
      log.debug("CPU_LOOP_IDLE Executing..")
      log.debug("#########################")
      self.extended['loop']= 1 
      log.debug("CPU add in a loop")
      log.debug("=================")
      self.AddRemove("proc","--procs","a",self.cpu_resource)
      log.debug("CPU remove in a loop")
      log.debug("=================")
      self.AddRemove("proc","--procs","r",self.cpu_resource)
      log.debug("CPU move in a loop")
      log.debug("=================")
      self.Move("proc","--procs",self.cpu_resource)
      log.debug("CPU_LOOP_IDLE Complete") 
      log.debug("CPU_SMT Executing..")
      log.debug("#########################")
      self.extended['loop']=0
      self.extended['smt']=1
      log.debug("CPU add and SMT") 
      log.debug("=================")
      self.AddRemove("proc","--procs","a",self.cpu_resource)
      log.debug("CPU remove and SMT")  
      log.debug("=================")
      self.AddRemove("proc","--procs","r",self.cpu_resource)
      log.debug("CPU move and SMT")  
      log.debug("=================")
      self.Move("proc","--procs",self.cpu_resource)
      log.debug("CPU_SMT Complete")
      log.debug("CPU_WKLD Executing..")
      log.debug("#########################")
      self.extended['smt']=0
      self.extended['wkld']=1
      log.debug("CPU add and WKLD")
      log.debug("=================")
      self.AddRemove("proc","--procs","a",self.cpu_resource)
      log.debug("CPU remove and WKLD")
      log.debug("=================")
      self.AddRemove("proc","--procs","r",self.cpu_resource)
      log.debug("CPU move and WKLD")
      log.debug("=================")
      self.Move("proc","--procs",self.cpu_resource)
      log.debug("CPU_WKLD Complete")
      log.debug("CPU_WKLD Complete..")
      log.debug("CPU_WKLD_LOOP Executing..")
      log.debug("#########################")
      self.extended['wkld']=1
      self.extended['loop']=1
      log.debug("CPU add loop and WKLD")
      log.debug("=================")
      self.AddRemove("proc","--procs","a",self.cpu_resource)
      log.debug("CPU remove loop and WKLD")
      log.debug("=================")
      self.AddRemove("proc","--procs","r",self.cpu_resource)
      log.debug("CPU move loop and WKLD")
      log.debug("=================")
      self.Move("proc","--procs",self.cpu_resource)
      log.debug("CPU_WKLD_LOOP Complete")
      if(path.exists(smt_script) != 1):
          log.debug("Deleting smt script")
          self.console.run_command("rm ./smt_script")

class DlparMemExtended(OpTestDlpar, unittest.TestCase):
    '''Class for DLPAR Mem Extended Tests
       This class allows --run testcases.OpTestDlpar.DlparMemExtended
    '''

    def setUp(self):
        super(DlparMemExtended, self).setUp()

    def runTest(self):
        if (path.exists("smt_script") != 1):
            self.console.run_command(
                'echo -e "ppc64_cpu --smt=off\nsleep 10s\nppc64_cpu --smt=on\nfor i in `seq 1 5000`;\ndo\nppc64_cpu --smt\nppc64_cpu --smt=2\nsleep 10s\nppc64_cpu --smt\nppc64_cpu --smt=3\nsleep 10s \nppc64_cpu --smt\nppc64_cpu --smt=4\nsleep 10s \nppc64_cpu --smt\ndone\" > smt_script')
            self.console.run_command("chmod +x ./smt_script")
        log.debug("Mem_LOOP_IDLE Executing..")
        log.debug("#########################")
        self.extended['loop'] = 1
        log.debug("Mem add in a loop")
        log.debug("=================")
        self.AddRemove("mem", "-q", "a", self.mem_resource)
        log.debug("Mem remove in a loop")
        log.debug("=================")
        self.AddRemove("mem", "-q", "r", self.mem_resource)
        log.debug("Mem move in a loop")
        log.debug("=================")
        self.Move("mem", "-q", self.mem_resource)
        log.debug("Mem_LOOP_IDLE Complete")
        log.debug("Mem_SMT Executing..")
        log.debug("#########################")
        self.extended['loop'] = 0
        self.extended['smt'] = 1
        log.debug("Mem add and SMT")
        log.debug("=================")
        self.AddRemove("mem", "-q", "a", self.mem_resource)
        log.debug("Mem remove and SMT")
        log.debug("=================")
        self.AddRemove("mem", "-q", "r", self.mem_resource)
        log.debug("Mem move and SMT")
        log.debug("=================")
        self.Move("mem", "-q", self.mem_resource)
        log.debug("Mem_SMT Complete")
        log.debug("Mem_WKLD Executing..")
        log.debug("#########################")
        self.extended['smt'] = 0
        self.extended['wkld'] = 1
        log.debug("Mem add and WKLD")
        log.debug("=================")
        self.AddRemove("mem", "-q", "a", self.mem_resource)
        log.debug("Mem remove and WKLD")
        log.debug("=================")
        self.AddRemove("mem", "-q", "r", self.mem_resource)
        log.debug("Mem move and WKLD")
        log.debug("=================")
        self.Move("mem", "-q", self.mem_resource)
        log.debug("Mem_WKLD Complete")
        log.debug("Mem_WKLD Complete..")
        log.debug("Mem_WKLD_LOOP Executing..")
        log.debug("#########################")
        self.extended['wkld'] = 1
        self.extended['loop'] = 1
        log.debug("Mem add loop and WKLD")
        log.debug("=================")
        self.AddRemove("mem", "-q", "a", self.mem_resource)
        log.debug("Mem remove loop and WKLD")
        log.debug("=================")
        self.AddRemove("mem", "-q", "r", self.mem_resource)
        log.debug("Mem move loop and WKLD")
        log.debug("=================")
        self.Move("mem", "-q", self.mem_resource)
        log.debug("Mem_WKLD_LOOP Complete")
        if (path.exists(smt_script) != 1):
            log.debug("Deleting smt script")
            self.console.run_command("rm ./smt_script")

def tearDown(self):
    self.console_thread.console_terminate()
#reboot machine & delete script smt_script
global conf
