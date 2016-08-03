#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/op_fwts_fvt.py $
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
.. module:: op_fwts_fvt
    :platform: Unix
    :synopsis: This module contains functional verification test functions
               for Firmware Test Suite(FWTS). Corresponding source files for new FWTS
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
from testcases.OpTestFWTS import OpTestFWTS


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

opTestFWTS = OpTestFWTS(bmcCfg['ip'], bmcCfg['username'],
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


def test_system_reboot():
    """This function reboots the system to OS, to start FWTS tests from stable point
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_system_reboot()


def test_pre_init():
    """This function tests initial setup for FWTS to work i.e checking ipmitool,
    packages, Loading necessary modules.
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_init()


def test_bmc_info():
    """This function tests FWTS bmc_info test
    BMC Info
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_bmc_info()


def test_prd_info():
    """This function tests FWTS prd_info test
    OPAL Processor Recovery Diagnostics Info
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_prd_info()


def test_oops():
    """This function tests FWTS oops test
    Scan kernel log for Oopses.
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_oops()


def test_olog():
    """This function tests FWTS olog test
    Run OLOG scan and analysis checks(opal msg log).
        returns: int 0-success, raises exception-error
    """
    return opTestFWTS.test_olog()
