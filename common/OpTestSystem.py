#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestSystem.py $
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
from OpTestHost import OpTestHost
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
    # @param i_hostIP The IP address of the Host
    # @param i_hostuser The userid to log into the Host
    # @param i_hostPasswd The password of the userid to log into the host with
    #
    def __init__(self,
                 i_bmcUserIpmi,i_bmcPasswdIpmi,i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None, bmc=None):
        self.cv_BMC = bmc
        self.cv_IPMI = OpTestIPMI(bmc.cv_bmcIP,i_bmcUserIpmi,i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, bmc.cv_bmcIP)
        self.cv_WEB = OpTestWeb(bmc.cv_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi)
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
            time.sleep(BMC_CONST.LONG_WAIT_IPL)
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
    # @brief Power cycle the system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_power_cycle(self):
        try:
            return self.cv_IPMI.ipmi_power_cycle()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

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
    # @brief Cold reset on the bmc system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_cold_reset_bmc(self):
        try:
            rc = self.cv_IPMI.ipmi_cold_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Cold reset on the Host
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_host_cold_reset(self):
        try:
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

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

    def sys_ipmi_ipl_wait_for_login(self,i_timeout=10):
        l_con = self.sys_get_ipmi_console()
        try:
            rc = self.cv_IPMI.ipmi_ipl_wait_for_login(l_con, i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Wait for system to reach standby or[S5/G2: soft-off]
    #
    # @param i_timeout @type int: The number of seconds to wait for system to reach standby,
    #       i.e. How long to poll the ACPI sensor for soft-off state before giving up.
    #
    # @return l_rc @type constant BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_wait_for_standby_state(self, i_timeout=120):
        try:
            l_rc = self.cv_IPMI.ipmi_wait_for_standby_state(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return l_rc

    ##
    # @brief Wait for system boot to host OS, It uses OS Boot sensor
    #
    # @param i_timeout @type int: The number of minutes to wait for IPL to complete or Boot time,
    #       i.e. How long to poll the OS Boot sensor for working state before giving up.
    #
    # @return l_rc @type constant BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_wait_for_os_boot_complete(self, i_timeout=10):
        try:
            l_rc = self.cv_IPMI.ipmi_wait_for_os_boot_complete(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return l_rc

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
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_power_on_validate_host(self):
        # Check to see if host credentials are present
        if(self.cv_HOST.ip == None):
            l_msg = "Partition credentials not provided"
            print l_msg
            return BMC_CONST.FW_FAILED

        # Check if partition is active
        try:
            self.util.PingFunc(self.cv_HOST.ip, totalSleepTime=2)
            self.cv_HOST.host_get_OS_Level()
        except OpTestError as e:
            print("Trying to recover partition after error: %s" % (e) )
            try:
                self.cv_IPMI.ipmi_power_off()
                self.sys_cold_reset_bmc()
                self.cv_IPMI.ipmi_power_on()
                self.sys_check_host_status()
                self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            except OpTestError as e:
                return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function reboots the system(Power off/on) and
    #        check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_hard_reboot(self):
        print "Performing a IPMI Power OFF Operation"
        self.cv_IPMI.ipmi_power_off()
        rc = int(self.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY))
        if rc == BMC_CONST.FW_SUCCESS:
            print "System is in standby/Soft-off state"
        elif rc == BMC_CONST.FW_PARAMETER:
            print "Host Status sensor is not available"
            print "Skipping stand-by state check"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        print "Performing a IPMI Power ON Operation"
        self.cv_IPMI.ipmi_power_on()
        self.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_check_host_status(self):
        rc = int(self.sys_ipl_wait_for_working_state())
        if rc == BMC_CONST.FW_SUCCESS:
            print "System booted to working state"
        elif rc == BMC_CONST.FW_PARAMETER:
            print "Host Status sensor is not available"
            print "Skip wait for IPL runtime check"
        else:
            l_msg = "System failed to boot"
            raise OpTestError(l_msg)
        rc = int(self.sys_wait_for_os_boot_complete())
        if rc == BMC_CONST.FW_SUCCESS:
            print "System booted to Host OS"
        elif rc == BMC_CONST.FW_PARAMETER:
            print "OS Boot sensor is not available"
            print "Skip wait for wait for OS boot complete check"
        else:
            l_msg = "System failed to boot Host OS"
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_check_host_status_v1(self):
        if int(self.cv_IPMI.ipmi_ipl_wait_for_working_state_v1()) == BMC_CONST.FW_SUCCESS:
            print "System booted to working state"
        else:
            print "There is no Host Status sensor...."
        if int(self.cv_IPMI.ipmi_wait_for_os_boot_complete_v1()) == BMC_CONST.FW_SUCCESS:
            print "System booted to Host OS"
        else:
            print "There is no OS Boot sensor..."

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Issue IPMI PNOR Reprovision request command
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_issue_ipmi_pnor_reprovision_request(self):
        try:
            self.cv_HOST.host_run_command(BMC_CONST.HOST_IPMI_REPROVISION_REQUEST)
        except OpTestError as e:
            print "Failed to issue ipmi pnor reprovision request"
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Wait for IPMI PNOR Reprovision to complete(response to 00)
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_wait_for_ipmi_pnor_reprovision_to_complete(self, timeout=10):
        l_res = ""
        timeout = time.time() + 60*timeout
        while True:
            l_res = self.cv_HOST.host_run_command(BMC_CONST.HOST_IPMI_REPROVISION_PROGRESS)
            if "00" in l_res:
                print "IPMI: Reprovision completed"
                break
            if time.time() > timeout:
                l_msg = "Reprovision timeout, progress not reaching to 00"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(10)
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
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

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
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

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
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Update the BMC fw using hpm file using HOST
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_fw_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS



    ##
    # @brief Update the BMC pnor using hpm file using HOST
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_pnor_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC fw and pnor using hpm file using Host
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_fwandpnor_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE)
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
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
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
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


    ##
    # @brief reads msglog for getting Chip and Core information
    #
    # return Chip and Core information or BMC_CONST.FW_FAILED
    #
    def sys_read_msglog_core(self):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_read_msglog_core()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief clears the gard records using the gard tool from OS
    #
    # @param i_gard_dir @type string: directory where gard is installed
    #
    # return BMC.CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_clear_gard_records(self, i_gard_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            self.cv_HOST.host_clear_gard_records(i_gard_dir)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Lists all the gard records using the gard tool from OS
    #
    # @param i_gard_dir @type string: directory where gard is installed
    #
    # return gard records or BMC_CONST.FW_FAILED
    #
    def sys_list_gard_records(self, i_gard_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_list_gard_records(i_gard_dir)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief reads getscom data
    #
    # @param i_xscom_dir @type string: directory where getscom is installed
    #
    # return getscom data or BMC_CONST.FW_FAILED
    #
    def sys_read_getscom_data(self, i_xscom_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_read_getscom_data(i_xscom_dir)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief injects error using putscom
    #
    # @param i_xscom_dir @type string: directory where putscom is installed
    # @param i_error @type string: error to be injected including the location
    #
    # @return output generated after executing putscom command or BMC_CONST.FW_FAILED
    #
    def sys_putscom(self, i_xscom_dir, i_error):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_putscom(i_xscom_dir, i_error)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief This function gets the sel log
    #
    # @return sel list or BMC_CONST.FW_FAILED
    #
    def sys_get_sel_list(self):
        try:
            return self.cv_IPMI.ipmi_get_sel_list()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief This function gets the sdr list
    #
    # @return @type string: sdr list or BMC_CONST.FW_FAILED
    #
    def sys_get_sdr_list(self):
        try:
            return self.cv_IPMI.ipmi_get_sdr_list()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Set BMC to boot pnor from primary side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_pnor_boot_primary(self, i_bios_sensor, i_boot_sensor):

        try:
            self.cv_IPMI.ipmi_set_pnor_primary_side(i_bios_sensor,i_boot_sensor)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Set BMC to boot pnor from golden side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_pnor_boot_golden(self, i_bios_sensor, i_boot_sensor):

        try:
            self.cv_IPMI.ipmi_set_pnor_golden_side(i_bios_sensor,i_boot_sensor)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Determines which side of BMC and PNOR chip is active
    #
    # @return l_bmc_active and l_pnor_active @type string or return FWConstants.FW_FAILED
    #
    def sys_active_chip_side(self):
        try:
            l_bmc_active, l_pnor_active = self.cv_IPMI.ipmi_get_side_activated()
            return l_bmc_active, l_pnor_active
        except OpTestError as e:
            return BMC_CONST.FW_FAILED,BMC_CONST.FW_FAILED

    ##
    # @brief Uses the pflash tool to save the gard image
    #        Note: Overwrites the good_GUARD_image in the i_image_dir
    #
    # @param i_pflash_dir @type string: directory where the pflash tool is stored
    # @param i_gard_image_dir @type string: directory where the gard image will be stored
    #
    # @return BMC_CONST.FW_PASSED or BMC_CONST.FW_FAILED
    #
    def sys_pflash_save_gard_image(self, i_pflash_dir, i_gard_image_dir):
        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_BMC.pflash_save_gard_image(i_pflash_dir, i_gard_image_dir)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Uses the pflash tool to write the gard image
    #
    # @param i_plash_dir @type string: directory where the gard tool is stored
    # @param i_gard_image_dir @type string: directory where the gard image must be stored
    #
    # @return BMC_CONST.FW_PASSED or BMC_CONST.FW_FAILED
    def sys_pflash_write_gard_image(self, i_pflash_dir, i_gard_image_dir):
        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_BMC.pflash_write_gard_image(i_pflash_dir, i_gard_image_dir)
            self.sys_bmc_power_on_validate_host()
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief enable/disable cpu states
    #
    # @param i_cpu_state @type string: BMC_CONST.CPU_ENABLE_STATE/
    #                                  BMC_CONST.CPU_DISABLE_STATE
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_disable_enable_cpu_states(self,i_cpu_state):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_disable_enable_cpu_states(i_cpu_state)
        except OpTestError as e:
            print "Disable/Enable cpu idle states failed. Reason: " + e.Reason
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


    ###########################################################################
    # IPMI Console interfaces
    ###########################################################################

    ##
    # @brief It will get the ipmi sol console
    #
    # @return l_con @type Object: it is a object of pexpect.spawn class or raise OpTestError
    #
    def sys_get_ipmi_console(self):
        self.l_con = self.cv_IPMI.ipmi_get_console()
        return self.l_con

    ##
    # @brief This function is used to close ipmi console
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or return BMC_CONST.FW_FAILED
    #
    def sys_ipmi_close_console(self, i_con):
        try:
            l_con = i_con
            self.cv_IPMI.ipmi_close_console(l_con)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to boot the system up to petitboot
    #        So any petitboot related test cases can use this function
    #        to setupt the petitboot
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or return BMC_CONST.FW_FAILED
    #
    def sys_ipmi_boot_system_to_petitboot(self, i_console):
        self.console = i_console
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        self.cv_IPMI.ipmi_set_boot_to_petitboot()
        self.cv_IPMI.ipmi_power_on()

        # Exiting to petitboot shell
        self.console.expect('Petitboot', timeout=BMC_CONST.PETITBOOT_TIMEOUT)
        self.console.expect('x=exit', timeout=10)
        # Exiting to petitboot
        self.console.sendcontrol('l')
        self.console.send('\x1b[B')
        self.console.send('\x1b[B')
        self.console.send('\r')
        self.console.expect('Exiting petitboot')
        self.console.send('\r')
        self.console.send('\x08')
