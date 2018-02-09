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
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState

module_logger = logging.getLogger(OpTestLogger.optest_logger_glob.parent_logger+'.{}'.format(__name__))

class HelloWorld(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.my_logger = logging.getLogger(OpTestLogger.optest_logger_glob.parent_logger+'.{}'.format(__name__))
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.my_logger.info('setUp info call in HelloWorld class')
        self.my_logger.debug('setUp debug call in HelloWorld class')

    def runTest(self):
        module_logger.info('HelloWorld runTest info call')
        module_logger.debug('HelloWorld runTest debug call')
        self.assertEqual("Hello World", "Hello World")
