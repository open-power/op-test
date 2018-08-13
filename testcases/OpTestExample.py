#!/usr/bin/python2
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

import unittest
import logging

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
try:
    import pxssh
except ImportError:
    from pexpect import pxssh

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestExample(unittest.TestCase):
    '''
    This class is a demo to illustrate framework.
    '''
    @classmethod
    def setUpClass(cls):
      conf = OpTestConfiguration.conf
      cls.cv_IPMI = conf.ipmi()
      cls.cv_SYSTEM = conf.system()
      cls.my_connect = None
      cls.my_prompt = None

    def setUp(self, my_connect='ipmi'):
      self.cv_SYSTEM.goto_state(self.my_desired_state)
      if self.my_connect == 'host':
        self.my_console = self.cv_SYSTEM.host().get_ssh_connection()
      else:
        self.my_console = self.cv_SYSTEM.console

    def OPComboTest(self):
      '''Execute commands on target OS
         Key Sort in OPDemoFunc for order of execution
      '''
      xcommand_table = {
        'lsprop'         : 'lsprop /sys/firmware/devicetree/base/ibm,firmware-versions',
        'os-release'     : 'cat /etc/os-release',
        'uname'          : 'uname -a',
      }

      self.OPDemoFunc(xcommand_table)

    def HostVersions(self):
      '''Execute commands on target OS
         Key Sort in OPDemoFunc for order of execution
      '''
      xcommand_table = {
        'linux'          : 'lsprop /sys/firmware/devicetree/base/ibm,firmware-versions/linux',
        'os-release'     : 'cat /etc/os-release',
        'proc-cmdline'   : 'cat /proc/cmdline',
        'version'        : 'cat /proc/version',
      }

      self.OPDemoFunc(xcommand_table)

    def PetitbootVersions(self):
      '''Execute commands on target OS
         Key Sort in OPDemoFunc for order of execution
      '''
      xcommand_table = {
        'cpu-present'        : 'cat /sys/devices/system/cpu/present',
        'eeh'                : 'cat /proc/powerpc/eeh',
        'linux'              : "dmesg -r|grep '<[4321]>'",
        'loc-code'           : 'find /sys/firmware/devicetree/base -name ibm,loc-code',
        'msglog'             : "grep ',[0-4]\]' /sys/firmware/opal/msglog",
        'os-release'         : 'cat /etc/os-release',
        'petitboot'          : 'lsprop /sys/firmware/devicetree/base/ibm,firmware-versions/petitboot',
        'phb'                : "cat /sys/firmware/opal/msglog |  grep 'PHB#' | grep -i  ' C:'",
        'proc-cmdline'       : 'cat /proc/cmdline',
        'slot-label'         : 'find /sys/firmware/devicetree/base -name ibm,slot-label',
      }

      self.OPDemoFunc(xcommand_table)

    def OPMisc(self):
      '''Execute commands on target OS
         Key Sort in OPDemoFunc for order of execution
      '''
      xcommand_table = {
        'nvram-print'    : 'nvram --print-config',
        'nvram-v'        : 'nvram -v',
      }

      self.OPDemoFunc(xcommand_table)

    def OPDemoFunc(self, op_dictionary):
      '''Process a command table
      '''

      xresults = {}

      try:
        for xkey, xcommand in sorted(op_dictionary.items()):
          xresults[xkey] = list(filter(None, self.my_console.run_command(xcommand)))

        for xkey, xvalue in sorted(xresults.items()):
          log.debug('\nCommand Run: "{}"\n{}'.format(op_dictionary[xkey], '\n'.join(xresults[xkey])), extra=xresults)

      except pxssh.ExceptionPxssh as op_pxssh:
        self.fail(str(op_pxssh))
      except CommandFailed as xe:
        my_x = {x:xe.output[x] for x in range(len(xe.output))}
        log.debug('\n******************************\nCommand Failed: \n{}\n******************************'.format('\n'.join(my_x[y] for y,z in my_x.items())), extra=my_x)
        log.debug('\nExitcode {}'.format(xe))
      except Exception as func_e:
        self.fail('OPDemoFunc Exception handler {}'.format(func_e))

class SkirootBasicCheck(OpTestExample, unittest.TestCase):
    '''Class for Skiroot based tests
       This class allows --run testcases.OpTestExample.SkirootBasicCheck
    '''
    def setUp(self):
      self.my_desired_state = OpSystemState.PETITBOOT_SHELL
      super(SkirootBasicCheck, self).setUp()

    def runTest(self):
      self.PetitbootVersions()
      self.OPMisc()
      self.OPComboTest()

class HostBasicCheck(OpTestExample, unittest.TestCase):
    '''Class for Host based tests
       This class allows --run testcases.OpTestExample.HostBasicCheck
    '''
    def setUp(self):
      self.my_connect = 'host'
      self.my_desired_state = OpSystemState.OS
      super(HostBasicCheck, self).setUp()

    def runTest(self):
      self.HostVersions()
      self.OPComboTest()

def skiroot_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite example
       Tests run in order
    '''
    tests = ['PetitbootVersions']
    return unittest.TestSuite(map(SkirootBasicCheck, tests))

def skiroot_full_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite example
       Tests run in order
    '''
    tests = ['PetitbootVersions', 'OPMisc', 'OPComboTest']
    return unittest.TestSuite(map(SkirootBasicCheck, tests))

def host_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite example
       Tests run in order
    '''
    tests = ['HostVersions']
    return unittest.TestSuite(map(HostBasicCheck, tests))

def host_full_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite example
       Tests run in order
    '''
    tests = ['HostVersions', 'PetitbootVersions', 'OPComboTest']
    return unittest.TestSuite(map(HostBasicCheck, tests))
