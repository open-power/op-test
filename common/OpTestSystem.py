#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestSystem.py $
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

## @package OpTestSystem
#  System package for OpenPower testing.
#
#  This class encapsulates all interfaces and classes required to do end to end
#  automated flashing and testing of OpenPower systems.

from OpTestBMC import OpTestBMC
from OpTestIPMI import OpTestIPMI


class OpTestSystem():

    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi,i_bmcPasswdIpmi,i_ffdcDir=None):
        self.cv_BMC = OpTestBMC(i_bmcIP,i_bmcUser,i_bmcPasswd,i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP,i_bmcUserIpmi,i_bmcPasswdIpmi,
                                  i_ffdcDir)

    ############################################################################
    # System Interfaces
    ############################################################################

    ## Clear all SDR's in the System
    #  @return int -- 0: success, 1: error
    #
    def sys_sdr_clear(self):
        return self.cv_IPMI.ipmi_sdr_clear()

    ## Power on the system
    #  @return int -- 0: success, 1: error
    #
    def sys_power_on(self):
        return self.cv_IPMI.ipmi_power_on()

    ## Power off the system
    #  @return int -- 0: success, 1: error
    #
    def sys_power_off(self):
        return self.cv_IPMI.ipmi_power_off()

    ## Wait for boot to end based on serial over lan output data
    #  @return int -- 0: success, 1: error
    #
    def sys_ipl_wait_for_working_state(self,i_timeout=10):
        return self.cv_IPMI.ipl_wait_for_working_state(i_timeout)

    ## Check for error during IPL that would result in test case failure
    #  @return int -- 0: success, 1: error
    #
    def sys_sel_check(self,i_string):
        return self.cv_IPMI.ipmi_sel_check(i_string)

    ############################################################################
    # BMC Interfaces
    ############################################################################

    ## Reboot the BMC
    #  @return int -- 0: success, 1: error
    #
    def bmc_reboot(self):
        return self.cv_BMC.reboot()

    ## Update the BMC PNOR
    #  @param i_imageDir PNOR image directory
    #  @param i_imageName PNOR image name
    #  @return int -- 0: success, 1: error
    #
    def bmc_update(self,i_imageDir,i_imageName):
        rc = self.cv_BMC.pnor_img_transfer(i_imageDir,i_imageName)
        if rc == 0:
            rc = self.cv_BMC.pnor_img_flash(i_imageName)
        return rc

    ############################################################################
    # OS Interfaces
    ############################################################################