#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/op_ci_bmc.py $
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
.. module:: op_ci_bmc
    :platform: Unix
    :synopsis: This module contains the test functions for enabling OpenPower
        Continuous Integration on HW and simulation environments.

.. moduleauthor:: Jay Azurin <jmazurin@us.ibm.com>

PNOR image flash steps.
1. check for pflash tool availablity in /tmp directory
2. Get side activated, fail on golden side(make sure doing pnor
   flash when system is in primary side)
3. Do a system ipmi power off
4. Clear SEL logs
5. Transfer PNOR image to BMC busy box(/tmp dir).
6. Flash the pnor image using pflash tool.
7. Bring the system up.
8. Get side activated, fail on golden side
9. Check for any error logs in SEL.
Run some tests after flash.

Note: Assumption is pflash tool available in /tmp directory.

"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.dirname(os.path.abspath(__file__))
full_path = full_path.split('ci')[0]
sys.path.append(full_path)

import ConfigParser
from common.OpTestBMC import OpTestBMC
from common.OpTestSystem import OpTestSystem
from common.OpTestError import OpTestError
from common.OpTestConstants import OpTestConstants as BMC_CONST


def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')),dict(bmcConfig.items('host'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, hostCfg = _config_read()

opTestSys = OpTestSystem(bmc=OpTestBMC(bmcCfg['ip'],bmcCfg['username'],
                                       bmcCfg['password'],testCfg['ffdcdir']),
                         bmcCfg.get('usernameipmi'),
                         bmcCfg.get('passwordipmi'),
                         testCfg['ffdcdir'],
                         hostCfg['hostip'],
                         hostCfg['hostuser'],
                         hostCfg['hostpasswd'])


def test_init():
    """This function validates the test config before running other functions
    """

    ''' create FFDC dir if it does not exist '''
    ffdcDir = testCfg['ffdcdir']
    if not os.path.exists(os.path.dirname(ffdcDir)):
        os.makedirs(os.path.dirname(ffdcDir))

    ''' make sure PNOR image exists '''
    try:
        pnorImg = testCfg['imagedir'] + testCfg['imagename']
        if not os.path.exists(pnorImg):
            print "WARNING: PNOR image %s does not exist!. Check config file." % pnorImg
    except KeyError:
        print "WARNING: No PNOR image specified!"

    return 0


def validate_pflash_tool():
    """This function validates presence of pflash tool, which will be
    used for pnor image flash.

    :return int -- 0: success, OpTestError: error
    """
    return opTestSys.cv_BMC.validate_pflash_tool(BMC_CONST.PFLASH_TOOL_DIR)


def pnor_img_transfer():
    """This function copies the PNOR image to the BMC /tmp dir.

    :returns: int -- the rsync command return code
    """
    return opTestSys.cv_BMC.pnor_img_transfer(testCfg['imagedir'],
                                              testCfg['imagename'])


def pnor_img_flash():
    """This function flashes the PNOR image using pflash tool,
    And this function will work based on the assumption that pflash
    tool available in '/tmp/'.(user need to mount pflash tool in /tmp dir,
    as pflash tool removed from BMC)

    :returns: int -- the pflash command return code
    """
    return opTestSys.cv_BMC.pnor_img_flash(BMC_CONST.PFLASH_TOOL_DIR, testCfg['imagename'])


def outofband_fwandpnor_update_hpm():
    """This function does a complete update of BMC and PNOR using the image provided by the user.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_outofband_fwandpnor_update_hpm(hostCfg['hpmimage'])


def validate_side_activated():
    """This function Verify Primary side activated for both BMC and PNOR
    :returns: int -- 0: success, exception: error
    """
    l_bmc_side, l_pnor_side = opTestSys.cv_IPMI.ipmi_get_side_activated()
    if(l_bmc_side.__contains__(BMC_CONST.PRIMARY_SIDE)):
        print("BMC: Primary side is active")
    else:
        l_msg = "BMC: Primary side is not active"
        print l_msg
        raise OpTestError(l_msg)
    if(l_pnor_side.__contains__(BMC_CONST.PRIMARY_SIDE)):
        print("PNOR: Primary side is active")
    else:
        l_msg = "PNOR: Primary side is not active"
        print l_msg
        raise OpTestError(l_msg)
    return 0
