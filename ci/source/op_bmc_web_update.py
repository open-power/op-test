#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_bmc_web_update.py $
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
.. module:: op_bmc_web_update
    :platform: Unix
    :synopsis: This module contains the test functions for enabling BMC and PNOR Firmware components update using BMC Web GUI in OpenPower systems.

.. moduleauthor:: Pavaman Subramaniyam <pavsubra@in.ibm.com>

"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.dirname(os.path.abspath(__file__))
full_path = full_path.split('ci')[0]
sys.path.append(full_path)

import ConfigParser
from common.OpTestSystem import OpTestSystem
from common.OpTestConstants import OpTestConstants as BMC_CONST


def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')),dict(bmcConfig.items('lpar'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, lparCfg = _config_read()
opTestSys = OpTestSystem(bmcCfg['ip'],bmcCfg['username'],
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

    ''' make sure PNOR image exists '''
    pnorImg = testCfg['imagedir'] + testCfg['imagename']
    if not os.path.exists(pnorImg):
        print "PNOR image %s does not exist!. Check config file." % pnorImg
        return 1

    return 0


def bmc_web_pnor_update_hpm():
    """This function does a update of PNOR using the image provided by the user.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_web_pnor_update_hpm(lparCfg['hpmimage'])

def bmc_web_bmc_update_hpm():
    """This function does a update of BMC using the image provided by the user.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_web_bmc_update_hpm(lparCfg['hpmimage'])

def bmc_web_bmcandpnor_update_hpm():
    """This function does a complete update of BMC and PNOR using the image provided by the user.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_web_bmcandpnor_update_hpm(lparCfg['hpmimage'])
