#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestWeb.py $
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

import time
import subprocess
import os
import pexpect
import unittest

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError

## @package OpTestWeb
#  Contains all BMC related Web tools
#
#  This class encapsulates all function which deals with the BMC Using Web GUI
#  in OpenPower systems
#
class OpTestWeb():

    ##
    # @brief Initialize OpTestWeb Object
    #
    # @param i_ip The IP address of the BMC
    # @param i_id User id to login to the BMC web page
    # @param i_password The password for the user id to
    #        log into the bmc web page
    #
    def __init__(self, i_ip, i_id, i_password):

        self.ip = i_ip
        self.id = i_id
        self.password = i_password

    ##
    # @brief Update the BMC using the hpm file provided using web interface
    #
    # @param i_image @type string: hpm file including location
    # @param i_component @type int: component to be updated onto the BMC
    #        default BMC_CONST.UPDATE_BMCANDPNOR
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def web_update_hpm(self, i_image, i_component=BMC_CONST.UPDATE_BMCANDPNOR):

        try:

            import argparse
            from selenium import webdriver
            from easyprocess import EasyProcess
            from pyvirtualdisplay import Display
            from FWUpdatePage import FWUpdatePage
            from LoginPage import LoginPage
            from MaintenancePage import MaintenancePage
            from Page import Page

            #Open web browser using headless selenium
            display = Display(visible=0, size=(1024, 768))
            display.start()
            BMC_IP='https://'+self.ip
            browser = webdriver.Firefox()
        except:
            print BMC_CONST.ERROR_SELENIUM_HEADLESS
            raise OpTestError(BMC_CONST.ERROR_SELENIUM_HEADLESS)

        try:
            #Open BMC webpage
            BMC = Page(browser, BMC_IP)
            BMC.getPage()

            #Login to BMC
            BMCAuth = LoginPage(BMC, self.id, self.password)
            BMCAuth.login()

            #Find FW Update Option in menus
            BMCUpdate = FWUpdatePage(BMC)

            #Get Maintenance Page
            Maintenance = MaintenancePage(BMC)
            Maintenance.getMaintenancePage()
            Maintenance.preserveIPMI()
            Maintenance.preserveNetwork()
            Maintenance.savePage()

            #Configure TFTP Protocol Server and Image
            BMCUpdate.getProtocolConfigPage()
            BMCUpdate.selectProtocolType('TFTP')
            BMCUpdate.inputServerAddress(self.ip)
            BMCUpdate.inputImageName(i_image)
            BMCUpdate.doSave()

            #Traverse Back to FW Update Page
            BMCUpdate.getUpdateOptionsPage()
            BMCUpdate.selectHPM()
            BMCUpdate.doContinue()
            BMCUpdate.selectFile(i_image)
            BMCUpdate.doOK()

            if(i_component == BMC_CONST.UPDATE_BMC):
                BMCUpdate.selectUpdateBios()
            elif(i_component == BMC_CONST.UPDATE_PNOR):
                BMCUpdate.selectUpdateBoot_APP()
            else:
                BMCUpdate.selectUpdateAll()

            BMCUpdate.doProceed()
            BMCUpdate.WaitForFWUpdateComplete(BMC_CONST.WEB_UPDATE_DELAY)
            browser.quit()
        except:
            browser.close()
            l_msg = "hpm update using webgui failed"
            print l_msg
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS


