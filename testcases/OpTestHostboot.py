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

'''
OpTestHostboot: Hostboot checks
-------------------------------

Perform various hostboot validations and checks
'''

from builtins import map
import unittest
import logging
import pexpect
import time
import string

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestHostboot(unittest.TestCase):
    '''
    OpTestHostboot class
    '''
    @classmethod
    def setUpClass(cls):
      conf = OpTestConfiguration.conf
      cls.cv_SYSTEM = conf.system()
      cls.my_connect = None
      cls.good_watermark = 10
      cls.threshold_attempts = 4

    def setUp(self, my_connect='ipmi'):
      if self.my_connect == 'host':
        self.my_console = self.cv_SYSTEM.host().get_ssh_connection()
      else:
        self.my_console = self.cv_SYSTEM.console
      # enable the console to be acquired non-obtrusively
      # console will not attempt to get prompts setup, etc
      # unblock to allow setup_term during get_console
      self.block_setup_term = 0
      self.cv_SYSTEM.console.enable_setup_term_quiet()
      self.pty = self.cv_SYSTEM.console.get_console()
      self.cv_SYSTEM.console.disable_setup_term_quiet()

    def SniffTest(self):
      '''Perform sniff test for platform errors
      '''
      self.snippet_list = []
      self.snippet_count = 1
      log.debug("System Power Off")
      self.cv_SYSTEM.sys_power_off()
      self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
      time.sleep(30)
      log.debug("System Power On")
      self.cv_SYSTEM.sys_power_on()
      count = self.threshold_attempts
      counter = 0
      error = False
      while count != 0:
          try:
              rc = self.pty.expect([pexpect.TIMEOUT, pexpect.EOF, "Error reported by"],
                       timeout=30)
              if rc == 2:
                  combo_io = self.pty.before + self.pty.after
                  self.snippet_list.append("Snippet #{}".format(self.snippet_count))
                  self.snippet_list += combo_io.replace("\r\r\n","\n").splitlines()
                  self.snippet_count += 1
                  error = True
                  count -= 1
          except Exception as e:
              log.debug("Something happened looking for Error,"
                  " Exception={}".format(e))
              count -= 1
          if error:
              error = False
              self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
              log.debug("RESETTING \"Error reported by\", Powering Off System")
              self.cv_SYSTEM.sys_power_off()
              log.debug("RESETTING \"Error reported by\", Powering On System")
              self.cv_SYSTEM.sys_power_on()
          else:
              if counter > self.good_watermark:
                  break
              else:
                  counter += 1
      if count == 0:
          return False
      else:
          return True

    def HostChecks(self):
      '''Sniff test the boot for any platform errors
      '''
      log.debug("Running HostChecks")
      success = self.SniffTest()
      if success:
          self.cv_SYSTEM.goto_state(OpSystemState.OS)
      else:
          self.assertTrue(False, "We reached the limit on how many"
              " errors detected during boot: \"{}\"\n"
              .format(self.threshold_attempts,
              ('\n'.join(f for f in self.snippet_list))))

    def PetitbootChecks(self):
      '''Sniff test the boot for any platform errors
      '''
      log.debug("Running PetitbootChecks")
      success = self.SniffTest()
      if success:
          self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
      else:
          self.assertTrue(False, "We reached the limit on how many"
              " errors detected during boot: \"{}\"\n"
              .format(self.threshold_attempts,
              ('\n'.join(f for f in self.snippet_list))))

class SkirootBasicCheck(OpTestHostboot, unittest.TestCase):
    '''Class for Skiroot based tests
       This class allows --run testcases.OpTestHostboot.SkirootBasicCheck
    '''
    def setUp(self):
      super(SkirootBasicCheck, self).setUp()

    def runTest(self):
      self.PetitbootChecks()

class HostBasicCheck(OpTestHostboot, unittest.TestCase):
    '''Class for Host based tests
       This class allows --run testcases.OpTestHostboot.HostBasicCheck
    '''
    def setUp(self):
      self.my_connect = 'host'
      super(HostBasicCheck, self).setUp()

    def runTest(self):
      self.HostChecks()

def skiroot_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite hostboot
       Tests run in order
    '''
    tests = ['PetitbootChecks']
    return unittest.TestSuite(list(map(SkirootBasicCheck, tests)))

def skiroot_full_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite hostboot
       Tests run in order
    '''
    tests = ['PetitbootChecks']
    return unittest.TestSuite(list(map(SkirootBasicCheck, tests)))

def host_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite hostboot
       Tests run in order
    '''
    tests = ['HostChecks']
    return unittest.TestSuite(list(map(HostBasicCheck, tests)))

def host_full_suite():
    '''Function used to prepare a test suite (see op-test)
       This allows --run-suite hostboot
       Tests run in order
    '''
    tests = ['HostChecks']
    return unittest.TestSuite(list(map(HostBasicCheck, tests)))
