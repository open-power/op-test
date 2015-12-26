#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_ci_fvt.py $
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
.. module:: op_ci_fvt
    :platform: Unix
    :synopsis: This module contains functional verification test functions
               for OPAL firmware. Corresponding source files for new OPAL
               features will be adding in common directory

.. moduleauthor:: Pridhiviraj Paidipeddi <ppaidipe@in.ibm.com>


"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.abspath(os.path.dirname(sys.argv[0])).split('ci')[0]
sys.path.append(full_path)

import ConfigParser
from common.OpTestSensors import OpTestSensors
from common.OpTestSwitchEndianSyscall import OpTestSwitchEndianSyscall


def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    print configFile
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('lpar'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, lparCfg = _config_read()
opTestSensors = OpTestSensors(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg['usernameipmi'],
                              bmcCfg['passwordipmi'],
                              testCfg['ffdcdir'], lparCfg['lparip'],
                              lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestSwitchEndianSyscall = OpTestSwitchEndianSyscall(bmcCfg['ip'],
                                                      bmcCfg['username'],
                                                      bmcCfg['password'],
                                                      bmcCfg['usernameipmi'],
                                                      bmcCfg['passwordipmi'],
                                                      testCfg['ffdcdir'],
                                                      lparCfg['lparip'],
                                                      lparCfg['lparuser'],
                                                      lparCfg['lparpasswd'])


def test_init():
    """This function validates the test config before running other functions
    """

    ''' create FFDC dir if it does not exist '''
    ffdcDir = testCfg['ffdcdir']
    if not os.path.exists(os.path.dirname(ffdcDir)):
        os.makedirs(os.path.dirname(ffdcDir))

    return 0


def test_sensors():
    """This function tests the hwmon driver for hardware monitoring sensors
    using sensors utility
    returns: int 0-success, raises exception-error
    """
    return opTestSensors.test_hwmon_driver()


def test_switch_endian_syscall():
    """This function executes the switch_endian() sys call test which is
    implemented in /linux/tools/testing/selftests/powerpc/switch_endian
    git  repository
    returns: int 0: success, 1: error
    """
    return opTestSwitchEndianSyscall.testSwitchEndianSysCall()
