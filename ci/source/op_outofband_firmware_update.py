#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_outofband_firmware_update.py $
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
.. module:: op_outofband_firmware_update
    :platform: Linux
    :synopsis: This module contains the test functions for enabling Firmware update of BMC and PNOR over IPMI in OpenPower systems.

.. moduleauthor:: Pavaman Subramaniyam <pavsubra@linux.vnet.ibm.com>


"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.abspath(os.path.dirname(sys.argv[0])).split('ci')[0]
sys.path.append(full_path)

import ConfigParser
from common.OpTestSystem import OpTestSystem
from common.OpTestLpar import OpTestLpar
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST

def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('lpar'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, lparCfg = _config_read()
opTestSys = OpTestSystem(bmcCfg['ip'],bmcCfg['username'],
                         bmcCfg['password'],
                         bmcCfg['usernameipmi'],
                         bmcCfg['passwordipmi'],
                         testCfg['ffdcdir'])


def get_PNOR_level():
    """This function gets the pnor level of the bmc
    :returns: int -- 0: success, 1: error
    """
    l_rc = opTestSys.cv_IPMI.ipmi_get_PNOR_level()
    print l_rc
    return 0

def get_side_activated():
    """This function Verify Primary side activated for both BMC and PNOR
    :returns: int -- 0: success, 1: error
    """
    rc = opTestSys.cv_IPMI.ipmi_get_side_activated()
    if(rc.__contains__(BMC_CONST.PRIMARY_SIDE)):
        print("Primary side is active")
    else:
        print("Primary side is not active")

    return 0

def cold_reset():
    """This function Performs a cold reset onto the lpar
    :returns: int -- 0: success, 1: error
    """
    return opTestSys.cv_IPMI.ipmi_cold_reset()

    return 0

def preserve_network_setting():
    """This function Executes a command on the os of the bmc to protect network setting
    :returns: int -- 0: success, 1: error
    """
    return opTestSys.cv_IPMI.ipmi_preserve_network_setting()

def code_update():
    """This function Flashes component 1 Firmware image of hpm file using ipmitool
    :returns: int -- 0: success, 1: error
    """
    opTestSys.cv_IPMI.ipmi_code_update(lparCfg['hpmimage'],str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))

    return 0

