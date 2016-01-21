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

import time
import subprocess

from OpTestBMC import OpTestBMC
from OpTestIPMI import OpTestIPMI
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestLpar import OpTestLpar
from OpTestUtil import OpTestUtil
from OpTestWeb import OpTestWeb

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
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi,i_bmcPasswdIpmi,i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP,i_bmcUser,i_bmcPasswd,i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP,i_bmcUserIpmi,i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd)
        self.cv_WEB = OpTestWeb(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi)
        self.util = OpTestUtil()

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
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            print ("Retry clearing SDR")
            try:
                rc = self.cv_IPMI.ipmi_sdr_clear()
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
    # @brief Power cycle the system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_power_cycle(self):
        try:
            rc = self.cv_IPMI.ipmi_power_cycle()
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


    ##
    # @brief Reboot the BMC
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_reboot(self):
        try:
            rc = self.cv_BMC.reboot()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Validates the partition and waits for partition to connect
    #        important to perform before all inband communications
    #
    # @return BMC_CONST.FW_SUCCESS raises OpTestError when failed
    #
    def sys_bmc_validate_lpar(self):
        # Check to see if lpar credentials are present
        if(self.cv_LPAR.ip == None):
            l_msg = "Partition credentials not provided"
            print l_msg
            raise OpTestError(l_msg)

        # Check if partition is active
        try:
            self.util.PingFunc(self.cv_LPAR.ip)
        except OpTestError as e:
            print("Trying to recover partition")
            try:
                self.cv_IPMI.ipmi_power_off()
                self.cv_IPMI.ipmi_power_on()
                self.util.PingFunc(self.cv_LPAR.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            except OpTestError as e:
                return BMC_CONST.FW_FAILED

        print 'Partition is pinging'
        return BMC_CONST.FW_SUCCESS


    ###########################################################################
    # CODE-UPDATE INTERFACES
    ###########################################################################

    ##
    # @brief Update the BMC fw image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_outofband_fw_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
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
    def sys_bmc_outofband_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_power_on()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Update the BMC fw and pnor image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_outofband_fwandpnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image,BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE)
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
    def sys_bmc_inband_fw_update_hpm(self,i_image):

        try:
            self.sys_bmc_validate_lpar()
            self.cv_IPMI.ipmi_cold_reset()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_LPAR.lpar_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_cold_reset()
            # TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
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
    def sys_bmc_inband_pnor_update_hpm(self,i_image):

        try:
            self.sys_bmc_validate_lpar()
            self.cv_IPMI.ipmi_cold_reset()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_LPAR.lpar_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_cold_reset()
            # TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC fw and pnor using hpm file using LPAR
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_fwandpnor_update_hpm(self,i_image):

        try:
            self.sys_bmc_validate_lpar()
            self.cv_IPMI.ipmi_cold_reset()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_LPAR.lpar_code_update(i_image, BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_cold_reset()
            # TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the PNOR image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_WEB.web_update_hpm(i_image,BMC_CONST.UPDATE_PNOR)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_bmc_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_WEB.web_update_hpm(i_image,BMC_CONST.UPDATE_BMC)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC and PNOR image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_bmcandpnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_WEB.web_update_hpm(i_image, BMC_CONST.UPDATE_BMCANDPNOR)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ###########################################################################
    # Energy Scale
    ###########################################################################

    ##
    # @brief Sets power limit of BMC
    #
    # @param i_powerlimit @type int: power limit to be set at BMC
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_power_limit(self, i_powerlimit):
        try:
            self.cv_IPMI.ipmi_power_status()
            self.cv_IPMI.ipmi_set_power_limit(i_powerlimit)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Gets the Power Limit
    #
    # @return l_powerlimit @type int: current power limit on bmc
    #         or BMC_CONST.FW_FAILED
    #
    def sys_get_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_get_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Activates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_activate_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_activate_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Dectivates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_deactivate_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_deactivate_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Enable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    def sys_enable_all_occ_sensor(self):
        try:
            return self.cv_IPMI.ipmi_enable_all_occ_sensor()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Disable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    def sys_disable_all_occ_sensor(self):
        try:
            return self.cv_IPMI.ipmi_disenable_all_occ_sensor()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc CPU sensors
    # example (CPU Core Func 1|0x0|discrete|0x8080|na|na|na|na|na|na)
    #         (CPU Core Temp 1|42.000|degrees C|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return CPU sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_cpu_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_CPU)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc Processor sensors
    # example (Mem Proc0 Pwr|0.000|Watts|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return Processor sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_processor_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_PROCESSOR)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc Fan sensors
    # example(Fan 1 |9000.000|RPM|ok|0.000|0.000|0.000|16500.000|16500.000|16500.000)
    #
    # @return Fan sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_fan_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_FAN)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc DIMM sensors
    # example(DIMM Func 0|0x0|discrete|0x4080|na|na|na|na|na|na)
    #        (DIMM Temp 0|27.000|degrees C|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return Fan sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_dimm_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_DIMM)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read All BMC sensors
    #
    # @return BMC sensor readings if successful or
    #         return BMC_CONST.FW_FAILED
    def read_sensor_list(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_SENSOR_LIST)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc power levels
    # example (Instantaneous power reading:                   297 Watts
    #          Minimum during sampling period:                284 Watts
    #          Maximum during sampling period:                317 Watts
    #          Average power reading over sample period:      297 Watts
    #          IPMI timestamp:                           Tue Nov 24 09:46:03 2015
    #          Sampling period:                          00010000 Milliseconds
    #          Power reading state is:                   activated)
    #
    # @return Power reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_power_level(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_GET_POWER)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc temperature levels of CPU and baseboard
    # example (Entity ID Entity Instance              Temp. Readings
    #         (CPU temperature sensors(41h)             0       +28 C)
    #         (Baseboard temperature sensors(42h)       0       +22 C)
    #
    # @return Operating temperature readings if successful or
    #         return BMC_CONST.FW_FAILED
    def read_temperature_level(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_GET_TEMP)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read OCC status
    #
    # @return OCC status if successful or
    #         return BMC_CONST.FW_FAILED
    def read_occ_status(self):
        try:
            return self.cv_IPMI.ipmi_get_occ_status()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED



##########################################################
#
#  Warning! Don't use these function for any other purpose.
#  Currently used for creating a mount point on BMC
#
##########################################################
    ##
    # @brief Executes a command onto the BMC
    #
    # @param i_cmd @type string: command to be executed onto the bmc console
    #
    # @return output generated by executing the command or BMC_CONST.FW_FAILED
    #
    def sys_execute_cmd_onto_bmc(self, i_cmd):
        try:
            return self.cv_BMC.sys_execute_cmd_onto_bmc(i_cmd)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
