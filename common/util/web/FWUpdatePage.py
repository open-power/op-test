#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/../FWUpdatePage.py $
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

from .seleniumimports import *
from .BmcPageConstants import BmcPageConstants
from OpTestConstants import OpTestConstants as BMC_CONST
import time

##
# @file: FWUpdatePage.py
# @brief: This file contains functions to browse through FW Update Menus and
#         manage FW Update related Pages
#

##
# FWUpdatePage
# @brief: This class manages interaction with FW Update
# menus and webpages
#


class FWUpdatePage():

    ##
    #  @brief Constructor - Takes a pointer to BMC WebDriver
    #  @param page instance
    #  @return none
    #
    def __init__(self, page):
        self.Page = page

    ##
    #  @brief Function to traverse to BMC FW Update page
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def getUpdateOptionsPage(self):
        try:
            WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
                EC.alert_is_present())
            alert = self.Page.driver.switch_to.alert.accept()
        except TimeoutException:
            print("FWUpdate_Page::getUpdateOptionsPage - \
                                 No alert present. Moving forward")
        self.Page.driver.switch_to.default_content()
        self.Page.driver.switch_to.frame(
            self.Page.driver.find_element_by_id(
                BmcPageConstants.BMC_MAINFRAME))
        FWUpdate = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_LN_FIRMWARE_UPDATE)))
        FWUpdate.click()
        FWUpdate_menu = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_LN_FIRMWARE_UPDATE_MENU)))
        FWUpdate_submenu = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                                            BmcPageConstants.BMC_LN_FIRMWARE_UPDATE_HREF)))
        FWUpdate_submenu.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief Function to traverse to BMC FW Protocol Configuration Page
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def getProtocolConfigPage(self):
        self.Page.driver.switch_to.default_content()
        self.Page.driver.switch_to.frame(
            self.Page.driver.find_element_by_id(
                BmcPageConstants.BMC_MAINFRAME))
        FWUpdate = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_LN_FIRMWARE_UPDATE)))
        FWUpdate.click()
        FWUpdate_menu = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_LN_FIRMWARE_UPDATE_MENU)))
        FWUpdate_submenu = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                                            BmcPageConstants.BMC_LN_PROTOCOL_CONFIG_HREF)))
        FWUpdate_submenu.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects AMI option in the FW Update page
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectAMI(self):
        self.Page.driver.switch_to.frame(
            self.Page.driver.find_element_by_id(
                BmcPageConstants.BMC_PAGEFRAME))
        FWUpdate_AMI = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_AMI_RADIO_BTN)))
        FWUpdate_AMI.click()
        FWUpdate_AMI = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).\
            until(EC.presence_of_element_located(
                (By.ID, BmcPageConstants.BMC_CONTINUE_BTN)))
        FWUpdate_AMI.click()
        print("Selected AMI Option")
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function hits continue button on all FW Update web pages
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def doContinue(self):
        FWUpdate_EnterUpdateMode = WebDriverWait(self.Page.driver,
                                                 BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_FWUPDATE_BTN)))
        FWUpdate_EnterUpdateMode.click()
        WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).\
            until(EC.alert_is_present())
        alert = self.Page.driver.switch_to.alert.accept()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects HPM option in the FW Update page
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectHPM(self):
        self.Page.driver.switch_to.frame(
            self.Page.driver.find_element_by_id(
                BmcPageConstants.BMC_PAGEFRAME))
        FWUpdate_HPM = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_HPM_RADIO_BTN)))
        FWUpdate_HPM.click()
        FWUpdate_HPM = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_CONTINUE_BTN)))
        FWUpdate_HPM.click()
        WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.alert_is_present())
        self.Page.driver.switch_to.alert.accept()
        print("Selected HPM Option")
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects Protocol options from the drop down menu
    #         in Protocol config page(This is hard-coded to select TFTP protocol for now)
    #
    #  @param protocol - String which identified hwat protocol to select. This
    #                    string should match the options listed in BMC drop down menu
    #
    # @return BMC_CONST.FW_SUCCESS upon success
    #         This function may throw some unexpected exception on failure
    #         which will be caught by the calling function
    #
    def selectProtocolType(self, protocol):
        WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_PAGEFRAME)))
        self.Page.driver.switch_to.frame(
            self.Page.driver.find_element_by_id(
                BmcPageConstants.BMC_PAGEFRAME))
        for i in range(1, BmcPageConstants.WEB_PROTOCOL_SELECT_RETRY):
            time.sleep(BMC_CONST.WEB_DRIVER_WAIT)
            # This is hard-coded to select TFTP protocol for now
            FWUpdate_protocoltype = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
                EC.presence_of_element_located((By.ID,
                                                BmcPageConstants.BMC_TFTP_OPTION)))
            for option in FWUpdate_protocoltype.find_elements_by_tag_name(
                    BmcPageConstants.BMC_OPTION_TAG):
                if option.text == protocol:
                    option.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function updates text field which contains server hosting
    #         BMC image
    #
    #  @param addr - Fills out IP address of server providing the BMC image
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def inputServerAddress(self, addr):
        FWUpdate_protocoltype = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_SERVER_ADDR_TEXT_AREA)))
        FWUpdate_protocoltype.clear()
        FWUpdate_protocoltype.send_keys(addr)
        print(("Server Address: " + addr))
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function updates imagename field. Full path to the image
    #         needs to be provided
    #
    #  @param image - full path to the BMC image
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def inputImageName(self, image):
        FWUpdate_imagename = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_IMAGE_PATH_TEXT_AREA)))
        FWUpdate_imagename.clear()
        FWUpdate_imagename.send_keys(image)
        print(("Server Image: " + image))
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function saves the updated protocol configuration. This page
    #         prompts a javascript alert which will be accepted
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def doSave(self):
        FWUpdate_Save = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_SAVE_BTN)))
        FWUpdate_Save.click()
        WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.alert_is_present())
        alert = self.Page.driver.switch_to.alert.accept()
        print("Protocol Config Saved")
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function provides the path to a BMC FW Image file
    #
    #  @param Full path to the BMC image file
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectFile(self, path):
        FWUpdate_FileSelect = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_UPLOAD_FILE)))
        FWUpdate_FileSelect.send_keys(path)
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function clicks the OK button at FW Update option
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def doOK(self):
        FWUpdate_OK_BUTTON = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.XPATH,
                                            BmcPageConstants.BMC_OK_BTN)))
        FWUpdate_OK_BUTTON.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects all FW images to be updated BIOS and Boot-App
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectUpdateAll(self):
        FWUpdate_SELECT_BIOS_RADIO = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_BIOS_UPDATE_OPTION)))
        FWUpdate_SELECT_BIOS_RADIO.click()
        FWUpdate_SELECT_BOOT_RADIO = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_BOOT_UPDATE_OPTION)))
        FWUpdate_SELECT_BOOT_RADIO.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects only BIOS FW images to be updated
    #
    #  @param none
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectUpdateBios(self):
        FWUpdate_SELECT_BIOS_RADIO = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_BIOS_UPDATE_OPTION)))
        FWUpdate_SELECT_BIOS_RADIO.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects only BIOS FW images to be updated
    #
    #  @param None
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def selectUpdateBoot_APP(self):
        FWUpdate_SELECT_BOOT_RADIO = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_BOOT_UPDATE_OPTION)))
        FWUpdate_SELECT_BOOT_RADIO.click()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects proceed button
    #
    #  @param None
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def doProceed(self):
        FWUpdate_PROCEED_BUTTON = WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.presence_of_element_located((By.ID,
                                            BmcPageConstants.BMC_BOOT_PROCEED)))
        FWUpdate_PROCEED_BUTTON.click()
        WebDriverWait(self.Page.driver, BMC_CONST.WEB_DRIVER_WAIT).until(
            EC.alert_is_present())
        alert = self.Page.driver.switch_to.alert.accept()
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function waits for fw update to be completed. Expectation
    #         is that an alert box will popup at the end of the FW update
    #
    #  @param timeout @type int time to wait for an alert to be present
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          This function may throw some unexpected exception on failure
    #          which will be caught by the calling function
    #
    def WaitForFWUpdateComplete(self, timeout):
        try:
            WebDriverWait(self.Page.driver, timeout).until(
                EC.alert_is_present())
            alert = self.Page.driver.switch_to.alert.accept()
        except TimeoutException:
            print("FWUpdate_Page::WaitForFWUpdateComplete- \
                                 No alert present. FW Update may not have \
                                 completed successfully. Need to check!!")
        return BMC_CONST.FW_SUCCESS
