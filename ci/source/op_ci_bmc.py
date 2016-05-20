#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_ci_bmc.py $
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
2. Do a system ipmi power off
3. Clear SEL logs
4. Transfer PNOR image to BMC busy box(/tmp dir).
5. Flash the pnor image using pflash tool.
6. Bring the system up.
7. Check for any error logs in SEL.
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
from common.OpTestSystem import OpTestSystem
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

opTestSys = OpTestSystem(bmcCfg['ip'],bmcCfg['username'],
                         bmcCfg['password'],
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

def bmc_reboot():
    """This function issues the reboot command on the BMC console.  It then
    pings the BMC until it responds, which presumably means that it is done
    rebooting.  It returns the number of failed pings.  The caller should make
    returned value is greater than 1

    :returns: int -- the number of ping failures while waiting for the BMC to
        reboot - TODO

    """
    opTestSys.sys_bmc_reboot()

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


def ipmi_sdr_clear():
    """This function clears the sensor data

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_sdr_clear()


def ipmi_power_off():
    """This function sends the chassis power off ipmitool command.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_power_off()


def ipmi_power_on():
    """This function sends the chassis power on ipmitool command.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_power_on()


def ipmi_warm_reset():
    """ This function sends the warm reset ipmitool command

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_warm_reset()


def ipmi_power_soft():
    """ This function sends the chassis power soft ipmitool command

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_power_soft()


def ipmi_sol_capture():
    """Spawns the sol logger expect script as a background process. In order to
    properly kill the process the caller should call the ipmitool sol
    deactivate command, i.e.: ipmitool_cmd_run('sol deactivate'). The sol.log
    file file is placed in the FFDC directory.

    :returns: subprocess child object
    """
    return opTestSys.sys_sol_capture()


def ipl_wait_for_working_state(timeout=10):
    """This function starts the sol capture and waits for the IPL to end. The
    marker for IPL completion is the Host Status sensor which reflects the ACPI
    power state of the system.  When it reads S0/G0: working it means that the
    petitboot is has began loading.  The overall timeout for the IPL is defined
    in the test configuration options.

    :param timeout: The number of minutes to wait for IPL to complete, i.e. How
        long to poll the ACPI sensor for working state before giving up.
    :type timeout: int.
    :returns: int -- 0: success, 1: error
    """

    return opTestSys.sys_ipl_wait_for_working_state()


def ipmi_sel_check():
    """This function dumps the sel log and looks for specific hostboot error
    log string.

    :returns: int -- 0: success, 1: error
    """
    selDesc = 'Transition to Non-recoverable'
    return opTestSys.sys_sel_check(selDesc)

def validate_host():
    """This function validate that the OS/partition can be pinged.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_power_on_validate_host()


def outofband_fwandpnor_update_hpm():
    """This function does a complete update of BMC and PNOR using the image provided by the user.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_outofband_fwandpnor_update_hpm(hostCfg['hpmimage'])
