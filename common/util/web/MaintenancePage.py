#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/../MaintenancePage.py $
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

from __future__ import print_function
from __future__ import absolute_import
from builtins import object
from .Page import Page
from .seleniumimports import *
from .BmcPageConstants import BmcPageConstants
from selenium.webdriver.support.ui import Select
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
import time

##
# @file: MaintenancePage.py
# @brief: This file contains functions to browse through Maintenance options
#

##
#  Maintenance_Page
#  @brief: This class provides interface to Maintenance menu and other page interactions
#
class MaintenancePage(object):
    OptionDict = {
        'IPMI':'_chkPrsrvStatus3',
        'NETWORK':'_chkPrsrvStatus4'
    }

    ##
    #  @brief Constructor - Takes a pointer to BMC WebDriver
    #  @param page instance
    #  @return none
    #
    def __init__(self, page):
        self.Page = page

    ##
    #  @brief Function to traverse to BMC Maintenance Page
    #
    #  @param None
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          raise OpTestError when fails
    #
    def getMaintenancePage(self):
        try:
            Maintenance = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       BmcPageConstants.BMC_LN_MAINTENANCE)))
            Maintenance.click()
            Maintenance_menu = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                            EC.presence_of_element_located((By.ID,
                            BmcPageConstants.BMC_LN_MAINTENANCE_MENU)))
            Maintenance_submenu = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                               EC.presence_of_element_located((By.CSS_SELECTOR,
                               BmcPageConstants.BMC_LN_PRESERVE_CONFIG_HREF)))
            Maintenance_submenu.click()
        except:
            l_msg = "Failed to get Maintainance Page"
            print(l_msg)
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function selects various options to be preserved
    #
    #  @param optionname - Name of the option to be preserved. Has to be from
    #         OptionDict
    #  @param iselect - Set to true if option needs to be preserved
    #
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          raise OpTestError when fails
    #
    def selectOption(self, optionname, iselect):

        try:
            #Switch to top-level page/frame container
            self.Page.driver.switch_to.default_content()
            self.Page.driver.switch_to.frame(
                      self.Page.driver.find_element_by_id(
                      BmcPageConstants.BMC_MAINFRAME))
            self.Page.driver.switch_to.frame(
                             self.Page.driver.find_element_by_id(
                             BmcPageConstants.BMC_PAGEFRAME))
            Maintenance = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       optionname)))
            if iselect is True:
                if Maintenance.is_selected() is False:
                    Maintenance.click()
            else:
                if Maintenance.is_selected() is True:
                    Maintenance.click()
        except:
            l_msg = "Failed to select Options for preserving settings"
            print(l_msg)
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS

    ##
    #  @brief This function preserves IPMI option
    #  @param none
    #  @return BMC_CONST.FW_SUCCESS upon success
    #
    def preserveIPMI(self):
        return self.selectOption(self.OptionDict['IPMI'], True)

    ##
    #  @brief This function preserves NETWORK option
    #  @param none
    #  @return BMC_CONST.FW_SUCCESS upon success
    #
    def preserveNetwork(self):
        return self.selectOption(self.OptionDict['NETWORK'], True)

    ##
    #  @brief This function hits 'Save' button on the Maintenance page
    #  @param none
    #  @return BMC_CONST.FW_SUCCESS upon success
    #          raise OpTestError when fails
    #
    def savePage(self):

        try:
            #Switch to top-level page/frame container
            self.Page.driver.switch_to.default_content()
            self.Page.driver.switch_to.frame(
                      self.Page.driver.find_element_by_id(
                      BmcPageConstants.BMC_MAINFRAME))
            self.Page.driver.switch_to.frame(
                             self.Page.driver.find_element_by_id(
                             BmcPageConstants.BMC_PAGEFRAME))
            Maintenance = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       BmcPageConstants.BMC_SAVE_BTN)))
            Maintenance.click()
        except:
            l_msg = "Failed to savePage"
            print(l_msg)
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS