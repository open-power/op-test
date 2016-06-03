#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_firmware_component_update.py $
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
.. module:: op_firmware_component_update
    :platform: Unix
    :synopsis: This module contains the test functions for enabling BMC and PNOR Firmware components update in OpenPower systems.

.. moduleauthor:: Pavaman Subramaniyam <pavsubra@linux.vnet.ibm.com>


"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.abspath(os.path.dirname(sys.argv[0])).split('ci')[0]
sys.path.append(full_path)

import ConfigParser
from common.OpTestSystem import OpTestSystem
from common.OpTestHost import OpTestHost
from common.OpTestConstants import OpTestConstants as BMC_CONST

def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('host'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, hostCfg = _config_read()
opTestSys = OpTestSystem(bmcCfg['ip'],bmcCfg['username'],
                         bmcCfg['password'],
                         bmcCfg.get('usernameipmi'),
                         bmcCfg.get('passwordipmi'),
                         testCfg['ffdcdir'],
                         hostCfg['hostip'],hostCfg['hostuser'],hostCfg['hostpasswd'])


def validate_host():
    """This function Validates the host and waits for host to connect
    :returns: int -- 0: success, 1: error
    """
    opTestSys.sys_bmc_validate_host()

    return 0

def outofband_fw_update_hpm():
    """This function Update the BMC fw image using hpm file
    :returns: int -- 0: success, 1: error
    """
    opTestSys.sys_bmc_outofband_fw_update_hpm(hostCfg['hpmimage'])

    return 0

def outofband_pnor_update_hpm():
    """This function Update the BMC pnor image using hpm file
    :returns: int -- 0: success, 1: error
    """
    opTestSys.sys_bmc_outofband_pnor_update_hpm(hostCfg['hpmimage'])

    return 0

def inband_fw_update_hpm():
    """This function Update the BMC fw using hpm file using HOST
    :returns: int -- 0: success, 1: error
    """
    opTestSys.sys_bmc_inband_fw_update_hpm(hostCfg['hpmimage'])

    return 0

def inband_pnor_update_hpm():
    """This function Update the BMC pnor using hpm file using HOST
    :returns: int -- 0: success, 1: error
    """
    opTestSys.sys_bmc_inband_pnor_update_hpm(hostCfg['hpmimage'])

    return 0

