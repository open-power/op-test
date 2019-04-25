#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/../LoginPage.py $
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
from engine.FWObject import FWObject
from .BmcPageConstants import BmcPageConstants
from connection.common.FWConnection import FWConnection
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from .seleniumimports import *

##
# @file: LoginPage.py
# @brief: This file contains functions to manage BMC Login page activities
#

##
# LoginPage # @brief: This class manages interaction with BMC Login
#                      webpage (no telnet and ssh)
#
class LoginPage(object):
    ##
    #  @brief Constructor for Login_Page class
    #  @param Page - Handle to the BMC Web-browswer
    #  @param i_username - User name to log into the BMC
    #  @param i_password - Password for the given username
    #  @return FW_SUCCESS
    #
    def __init__(self, page, i_username, i_password):
        self.Page = page
        self.Username = i_username
        self.Password = i_password

    ##
    #  @brief Function to enter user-name password on BMC Login page.
    #         Error handling is not done 100% correctly
    #         This function may throw some unexpected exception
    #  @param none
    #  @return BMC_CONST.FW_SUCCESS upon success and
    #          raise OpTestError when fails.
    #
    #
    def login(self):
        try:
            self.Page.driver.switch_to.frame(
                 self.Page.driver.find_element_by_id(
                 BmcPageConstants.BMC_MAINFRAME))
        except NoSuchElementException:
            l_msg=("Error getting BMC login page. Check if BMC is up and connected to network")
            print(l_msg)
            raise OpTestError(l_msg)

        try:
            username = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       BmcPageConstants.BMC_LOGIN_TEXT_AREA)))
            password = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       BmcPageConstants.BMC_PASSWORD_TEXT_AREA)))
            submitbutton = WebDriverWait(self.Page.driver,BMC_CONST.WEB_DRIVER_WAIT).until(
                       EC.presence_of_element_located((By.ID,
                       BmcPageConstants.BMC_LOGIN_BTN)))
            username.send_keys(self.Username)
            password.send_keys(self.Password)
            submitbutton.click()
        except:
            l_msg=("Error passing BMC login page. Check username/password")
            print(l_msg)
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS

