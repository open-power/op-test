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
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestConnection import OpTestConnection

class OpTestSystem():

    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    # @param i_lpartype The type of lpar example aix or linux
    # @param i_lparid ID of the lpar. Default set to 1
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi,i_bmcPasswdIpmi,i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None, i_lpartype=None, i_lparid = "1"):
        self.cv_BMC = OpTestBMC(i_bmcIP,i_bmcUser,i_bmcPasswd,i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP,i_bmcUserIpmi,i_bmcPasswdIpmi,
                                  i_ffdcDir, i_lparip, i_lparuser, i_lparPasswd,
                                  i_lpartype, i_lparid)

    ############################################################################
    # System Interfaces
    ############################################################################

    ##
    # @brief Clear all SDR's in the System
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_sdr_clear(self):
        try:
            rc =  self.cv_IPMI.ipmi_sdr_clear()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Power on the system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_power_on(self):
        try:
            rc = self.cv_IPMI.ipmi_power_on()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Power soft the system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_power_soft(self):
        try:
            rc = self.cv_IPMI.ipmi_power_soft()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Power off the system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_power_off(self):
        try:
            rc = self.cv_IPMI.ipmi_power_off()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Warm reset on the bmc system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_warm_reset(self):
        try:
            rc = self.cv_IPMI.ipmi_warm_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Wait for boot to end based on serial over lan output data
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_ipl_wait_for_working_state(self,i_timeout=10):
        try:
            rc = self.cv_IPMI.ipl_wait_for_working_state(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Check for error during IPL that would result in test case failure
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_sel_check(self,i_string):
        try:
            rc = self.cv_IPMI.ipmi_sel_check(i_string)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ############################################################################
    # BMC Interfaces
    ############################################################################

    ##
    # @brief Reboot the BMC
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def bmc_reboot(self):
        try:
            rc = self.cv_BMC.reboot()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Update the BMC fw image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def bmc_outofband_fw_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_power_on()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC pnor image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def bmc_outofband_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_power_on()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS



    ##
    # @brief Update the BMC fw using hpm file using LPAR
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def bmc_inband_fw_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_inband_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS



    ##
    # @brief Update the BMC pnor using hpm file using LPAR
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def bmc_inband_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_inband_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS



    ###########################################################################
    # OS Interfaces
    ###########################################################################
