#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/../Page.py $
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

from selenium import webdriver

##
# @file: Page.py
# @brief: This file contains common functions for BMC web pages and maintain a
#         handle to selenium web driver
#

##
# Page
# @brief: This class maintains common functions across BMC Pages. It also
#         encapsulates selenium web driver
#
class Page():

    ##
    #  @brief Constructor
    #  @param selenium_driver - Handle to selenium web driver
    #  @param base_url - URL to BMC
    #  @return none
    #
    def __init__(self, selenium_driver, base_url):
        self.base_url = base_url
        self.driver = selenium_driver

    ##
    #  @brief This function opens the URL in the current browser
    #  @param none
    #  @return none
    #
    def getPage(self):
        self.driver.get(self.base_url)
