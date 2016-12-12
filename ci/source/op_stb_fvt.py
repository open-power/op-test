#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_stb_fvt.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
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
"""
.. module:: op_stb_fvt
    :platform: Unix
    :synopsis: This module contains functional verification test functions
               for Secure and Trusted boot

.. moduleauthor:: Nageswara R Sastry <nasastry@in.ibm.com>


"""
import sys
import os
import unittest

import ConfigParser

# Get path to base directory and append to path to get common modules
full_path = os.path.dirname(os.path.abspath(__file__))
full_path = full_path.split('ci')[0]

sys.path.append(full_path)

def _config_read():
    """ returns bmc system, test config and host options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('host'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, hostCfg = _config_read()

from testcases.OpTestSTB import OpTestSTB
opTestSTB = OpTestSTB(bmcCfg['ip'], bmcCfg['username'],
                      bmcCfg['password'],
                      bmcCfg.get('usernameipmi'),
                      bmcCfg.get('passwordipmi'),
                      testCfg['ffdcdir'], hostCfg['hostip'],
                      hostCfg['hostuser'], hostCfg['hostpasswd'])
def test_init():
    """This function validates the test config before running other functions
    """

    ''' create FFDC dir if it does not exist '''
    ffdcDir = testCfg['ffdcdir']
    if not os.path.exists(os.path.dirname(ffdcDir)):
        os.makedirs(os.path.dirname(ffdcDir))

    return 0


class OpalSTB(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_hw_sb_support(self):
        opTestSTB.hw_sb_support()

    def test_hw_tb_support(self):
        opTestSTB.hw_tb_support()

    def test_secure_boot_mode(self):
        opTestSTB.secure_boot_mode()

    def test_trusted_boot_mode(self):
        opTestSTB.trusted_boot_mode()

    def test_capp_measured(self):
        opTestSTB.capp_measured()

    def test_bootkernel_measured(self):
        opTestSTB.bootkernel_measured()

    def test_capp_verified(self):
        opTestSTB.capp_verified()

    def test_bootkernel_verified(self):
        opTestSTB.bootkernel_verified()

    def test_capp_loaded(self):
        opTestSTB.capp_loaded()

    def test_bootkernel_loaded(self):
        opTestSTB.bootkernel_loaded()

    def test_proc_sb_verify(self):
        opTestSTB.proc_sb_verify()

    def test_proc_tb_verify(self):
        opTestSTB.proc_tb_verify()

    def test_cross_check_hw_opal_sb(self):
        opTestSTB.cross_check_hw_opal_sb()

    def test_cross_check_hw_opal_tb(self):
        opTestSTB.cross_check_hw_opal_tb()

    def test_cross_check_stb(self):
        opTestSTB.cross_check_stb()

if __name__ == '__main__':
    unittest.main()
