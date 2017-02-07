#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/op_occ_fvt.py $
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
.. module:: op_occ_fvt
    :platform: Unix
    :synopsis: This module contains functional verification test functions
               for OCC and HBRT firmware. Corresponding source files for these
               features will be adding in testcases directory

.. moduleauthor:: Pridhiviraj Paidipeddi <ppaidipe@linux.vnet.ibm.com>


"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.dirname(os.path.abspath(__file__))
full_path = full_path.split('ci')[0]

sys.path.append(full_path)
import ConfigParser

from common.OpTestConstants import OpTestConstants as BMC_CONST
from testcases.OpTestEnergyScale import OpTestEnergyScale
from testcases.OpTestOCC import OpTestOCC
from testcases.OpTestEM import OpTestEM


def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    print configFile
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('host'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, hostCfg = _config_read()
opTestEnergyScale = OpTestEnergyScale(bmcCfg['ip'], bmcCfg['username'],
                                      bmcCfg['password'],
                                      bmcCfg.get('usernameipmi'),
                                      bmcCfg.get('passwordipmi'),
                                      testCfg['ffdcdir'],
                                      testCfg['platformname'],
                                      hostCfg['hostip'],
                                      hostCfg['hostuser'],
                                      hostCfg['hostpasswd'])

opTestOCC = OpTestOCC(bmcCfg['ip'], bmcCfg['username'],
                      bmcCfg['password'],
                      bmcCfg.get('usernameipmi'),
                      bmcCfg.get('passwordipmi'),
                      testCfg['ffdcdir'], hostCfg['hostip'],
                      hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestEM = OpTestEM(bmcCfg['ip'], bmcCfg['username'],
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


def test_energy_scale_at_standby_state():
    """This function tests the platform energy scale tests at standby state
    returns: int 0-success, raises exception-error
    """
    return opTestEnergyScale.test_energy_scale_at_standby_state()


def test_energy_scale_at_runtime_state():
    """This function tests the platform energy scale tests at runtime
    returns: int 0-success, raises exception-error
    """
    return opTestEnergyScale.test_energy_scale_at_runtime_state()


def test_dcmi_at_standby_and_runtime_states():
    """This function tests the dcmi commands at both standby and runtime state
    returns: int 0-success, raises exception-error
    """
    return opTestEnergyScale.test_dcmi_at_standby_and_runtime_states()


def test_occ_reset_functionality():
    """This function tests OCC Reset functionality using opal-prd tool.
    returns: int 0-success, raises exception-error
    """
    return opTestOCC.test_occ_reset_functionality()


def test_occ_reset_n_times():
    """This function tests OCC Reset(n>3) functionality using opal-prd tool.
    returns: int 0-success, raises exception-error
    """
    return opTestOCC.test_occ_reset_n_times()


def test_occ_enable_disable_functionality():
    """This function tests the OCC Enable/Disable functionality using opal-prd tool.
    returns: int 0-success, raises exception-error
    """
    return opTestOCC.test_occ_enable_disable_functionality()


def test_cpu_freq_states():
    """This function tests the CPU Frequency states by changing and verifying those frequencies
    returns: int 0-success, raises exception-error
    """
    return opTestEM.test_cpu_freq_states()


def test_cpu_idle_states():
    """This function tests the CPU idle states by enable and disabling them.
    returns: int 0-success, raises exception-error
    """
    return opTestEM.test_cpu_idle_states()

import os
import unittest
import xmlrunner

import ConfigParser
from common.OpTestSystem import OpTestSystem
from common.OpTestError import OpTestError
from common.OpTestConstants import OpTestConstants as BMC_CONST

class OpalOCCTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_slw_info(self):
        opTestEM.test_slw_info()

    def test_cpu_idle_states(self):
        opTestEM.test_cpu_idle_states()

    def test_cpu_freq_states(self):
        opTestEM.test_cpu_freq_states()

    def test_energy_scale_at_standby_state(self):
        opTestEnergyScale.test_energy_scale_at_standby_state()

    def test_energy_scale_at_runtime_state(self):
        opTestEnergyScale.test_energy_scale_at_runtime_state()

    def test_dcmi_at_standby_and_runtime_states(self):
        opTestEnergyScale.test_dcmi_at_standby_and_runtime_states()

    def test_occ_reset_functionality(self):
        opTestOCC.test_occ_reset_functionality()

    def test_occ_reset_n_times(self):
        opTestOCC.test_occ_reset_n_times()

    def test_occ_enable_disable_functionality(self):
        opTestOCC.test_occ_enable_disable_functionality()

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='%s/test-reports' % full_path))
