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
# Below is the procedure for FW Upgrade through Out-of-band method.
# 1. Get the current PNOR level before upgrade
# 2. Clear SEL logs
# 3. Get current working side-->make sure do fw update on primary side(other wise backup golden
#    image will be overwritten).
# 4. Do ipmi power off.
# 5. Issue BMC cold reset to bring BMC to stable point
# 6. Preserve Network settings of BMC
# 7. Do a code update for both BMC and PNOR firmwares using hpm image method
# 8. Bring the system up(Power ON)
# 9. Wait for working state of system
# 10. Check for any Non-recoverable errors in SEL logs
# 11. Get PNOR level again after FW Upgrade.
#
# TODO: Gather BMC FW Version info before and after FW upgrade, currently we are getting PNOR version only.

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
from common.OpTestHost import OpTestHost
from common.OpTestIPMI import OpTestIPMI
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
                         bmcCfg['usernameipmi'],
                         bmcCfg['passwordipmi'],
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

    ''' make sure hpm image exists '''
    hpmimage = hostCfg['hpmimage']
    if not os.path.exists(hpmimage):
        print "FW HPM image %s does not exist!. Check config file." % hpmimage
        return 1

    return 0

def get_PNOR_level():
    """This function gets the pnor level of the bmc
    :returns: int -- 0: success, 1: error
    """
    l_rc = opTestSys.cv_IPMI.ipmi_get_PNOR_level()
    print l_rc
    return 0

def ipmi_sdr_clear():
    """This function clears the sel log data

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_sdr_clear()

def get_side_activated():
    """This function Verify Primary side activated for both BMC and PNOR
    :returns: int -- 0: success, 1: error
    """
    rc = opTestSys.cv_IPMI.ipmi_get_side_activated()
    if(rc.__contains__(BMC_CONST.PRIMARY_SIDE)):
        print("Primary side is active")
    else:
        l_msg = "Primary side is not active"
        raise OpTestError(l_msg)
    return 0

def ipmi_power_off():
    """This function sends the chassis power off ipmitool command.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_power_off()

def cold_reset():
    """This function Performs a cold reset onto the host
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
    opTestSys.cv_IPMI.ipmi_code_update(hostCfg['hpmimage'],str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))

    return 0

def validate_host():
    """This function validate that the Host OS can be pinged.

    :returns: int -- 0: success, 1: error
    """
    return opTestSys.sys_bmc_power_on_validate_host()

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
