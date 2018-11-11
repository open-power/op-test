#!/usr/bin/env python2
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
OpTestModel: A Model test case
------------------------------

This test case is to illustrate a few best practices for leveraging
the OpCheck helpers to perform some system wide health checks.

'''

import unittest
import time

import OpTestConfiguration
from common.OpTestConstants import OpConstants as OpSystemState
import common.OpTestUtil as Util

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpModel(unittest.TestCase):
    '''
    OpModel is an illustration of how to use the OpCheck class and
    use a standard methodology for setting up classes to be shared
    within a module.
    '''
    @classmethod
    def setUpClass(cls):
        cls.conf = OpTestConfiguration.conf
        if cls.conf.args.bmc_type in ['qemu', 'mambo']:
            raise unittest.SkipTest("QEMU/Mambo running so skipping tests")
        cls.opcheck = Util.OpCheck(cls=cls) # OpCheck helper for standard setup

    @classmethod
    def tearDownClass(cls):
        cls.opcheck.check_up(stage="stop") # performs standard checks POST Class

    def lsprop_check(self, stage=None, diff_dict=None):
        fn_label = "lspropfw" # fn_label should match what to compare it to
        command = "lsprop /sys/firmware/devicetree/base/ibm,firmware-versions"
        dict_stage = {} # we need new object each time
        diff_dict[stage] = Util.dump_me(self=self,
                                    term_obj=self.c,
                                    conf=self.conf,
                                    dict_stage=dict_stage,
                                    stage=stage,
                                    fn_label=fn_label,
                                    command=command)

    def lspci_check(self, stage=None, diff_dict=None):
        fn_label = "pci" # fn_label should match what to compare it to
        command = "lspci"
        dict_stage = {} # we need new object each time
        diff_dict[stage] = Util.dump_me(self=self,
                                    term_obj=self.c,
                                    conf=self.conf,
                                    dict_stage=dict_stage,
                                    stage=stage,
                                    fn_label=fn_label,
                                    command=command)

    def uptime_check(self, stage=None, diff_dict=None):
        fn_label = "timeup" # fn_label should match what to compare it to
        command = "uptime"
        dict_stage = {} # we need new object each time
        diff_dict[stage] = Util.dump_me(self=self,
                                    term_obj=self.c,
                                    conf=self.conf,
                                    dict_stage=dict_stage,
                                    stage=stage,
                                    fn_label=fn_label,
                                    command=command)

    def df_check(self, stage=None, diff_dict=None):
        fn_label = "df" # fn_label should match what to compare it to
        command = "df -h"
        dict_stage = {} # we need new object each time
        diff_dict[stage] = Util.dump_me(self=self,
                                    term_obj=self.c,
                                    conf=self.conf,
                                    dict_stage=dict_stage,
                                    stage=stage,
                                    fn_label=fn_label,
                                    command=command)

    def setUp(self):
        '''
        Demonstrate setUp which happens before each test_*
        This is to capture state information to compare with post-test
        Typically these may be checks that should remain static.
        '''
        self.diff_dict = {} # we create the dict here, fresh each setUp
        stage = "start"
        self.lsprop_check(stage=stage, diff_dict=self.diff_dict)
        self.lspci_check(stage=stage, diff_dict=self.diff_dict)

    def tearDown(self):
        '''
        Demonstrate tearDown which happens after each test_*
        This is to catch any problems that happened during the test
        Typically these may be checks that should remain static.
        '''
        stage = "stop"
        self.lsprop_check(stage=stage, diff_dict=self.diff_dict)
        self.lspci_check(stage=stage, diff_dict=self.diff_dict)

        self.status = Util.diff_files(diff_dict=self.diff_dict)
        self.assertFalse(self.status, "We've got diff problems!")

class HostOS(OpModel, unittest.TestCase):
    '''
    Model Class to illustrate leveraging the setUpClass
    and OpCheck Class.

    This model allows unittest fixtures to inherit
    common tests which only differ by where they are
    executed, e.g. HostOS or in Skiroot.

    The methods below need to start with test_ for
    unittest to leverage the loading of the methods
    and the automatic calling of setUp/tearDown per test.
    '''
    @classmethod
    def setUpClass(cls):
        log.debug("HostOS setUpClass setting cls.desired=OS")
        cls.desired = OpSystemState.OS
        super(HostOS, cls).setUpClass()

    def test_A(self):
        '''
        Example test_A to show how to use the capturing
        of data to be used after the test to compare
        '''
        diff_dict = {}
        stage = "test_A_start"
        self.df_check(stage=stage, diff_dict=diff_dict)
        time.sleep(5)
        stage = "test_A_stop"
        self.df_check(stage=stage, diff_dict=diff_dict)
        self.status = Util.diff_files(diff_dict=diff_dict)
        self.assertFalse(self.status, "Something changed !")

    def test_B(self):
        '''
        Example test_B to show how to use the capturing
        of data to be used after the test to compare
        '''
        diff_dict = {}
        stage = "test_B_start"
        self.uptime_check(stage=stage, diff_dict=diff_dict)
        time.sleep(5)
        stage = "test_B_stop"
        self.uptime_check(stage=stage, diff_dict=diff_dict)
        self.status = Util.diff_files(diff_dict=diff_dict,
                         logdir=self.conf.logdir)
        self.assertTrue(self.status,
            "We should have had a diff problem! Times should not match")

class PetitbootShell(HostOS):
    '''
    Model Class to illustrate leveraging the setUpClass
    and OpCheck Class.

    This model allows unittest fixtures to inherit
    common tests which only differ by where they are
    executed, e.g. HostOS or in Skiroot.
    '''
    @classmethod
    def setUpClass(cls):
        log.debug("Petitboot setUpClass setting cls.desired=PS")
        cls.desired = OpSystemState.PETITBOOT_SHELL
        super(HostOS, cls).setUpClass()

def host_model_suite():
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(HostOS))
    return s

def skiroot_model_suite():
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(PetitbootShell))
    return s
