#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/../BmcPageConstants.py $
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

## @package BmcPageConstants
#  package which contains all BMC related Web constants
#
#  This class encapsulates all constants which deals with the BMC Using Web GUI
#  in OpenPower systems


class BmcPageConstants():

    #BMC MainFrame
    BMC_MAINFRAME = 'MAINFRAME'

    #BMC PageFrame
    BMC_PAGEFRAME = 'pageFrame'

    #FW Update Menu Option
    BMC_LN_FIRMWARE_UPDATE = 'LN_FIRMWARE_UPDATE'

    #FW Update Menu Option
    BMC_LN_FIRMWARE_UPDATE_MENU = 'LN_FIRMWARE_UPDATE_menu'

    #FW Update HREF Link
    BMC_LN_FIRMWARE_UPDATE_HREF = "a[href='../page/fw_update.html']"

    #Protocol config HREF Link
    BMC_LN_PROTOCOL_CONFIG_HREF = "a[href='../page/configure_fw_image.html']"

    #FW Update Menu Option
    BMC_LN_MAINTENANCE = 'LN_MAINTENANCE'

    #FW Update Menu Option
    BMC_LN_MAINTENANCE_MENU = 'LN_MAINTENANCE_menu'

    #Protocol config HREF Link
    BMC_LN_PRESERVE_CONFIG_HREF = "a[href='../page/preserve_cfg.html']"

    #HPM Radio Buton
    BMC_HPM_RADIO_BTN = '_rdoHPM'

    #AMI Radio Buton
    BMC_AMI_RADIO_BTN = '_rdoAMI'

    #Continue Buton
    BMC_CONTINUE_BTN = '_btnContinue'

    #FW Update Buton
    BMC_FWUPDATE_BTN = '_btnFWUpdate'

    #Save Buton (Protocol Config, Preserve Config)
    BMC_SAVE_BTN = '_btnSave'

    #TFTP Drop Down Option
    BMC_TFTP_OPTION = '_lstProtocol'

    #Option html tag
    BMC_OPTION_TAG = 'option'

    #Text box to enter server info
    BMC_SERVER_ADDR_TEXT_AREA = '_txtAddress'

    #Text box to enter filepath info
    BMC_IMAGE_PATH_TEXT_AREA = '_txtSrcPath'

    #Text box to enter user login id
    BMC_LOGIN_TEXT_AREA = 'login_username'

    #Text box to enter user login password
    BMC_PASSWORD_TEXT_AREA = 'login_password'

    #Login submit button
    BMC_LOGIN_BTN = 'LOGIN_VALUE_1'

    #Upload File Button
    BMC_UPLOAD_FILE = 'brwsUpld'

    #OK Button
    BMC_OK_BTN = '//input[@type="button" and @value="Ok"]'

    #SELECT_BIOS_UPDATE
    BMC_BIOS_UPDATE_OPTION = '_chkSecStatus0'

    #SELECT_BOOT_UPDATE
    BMC_BOOT_UPDATE_OPTION = '_chkSecStatus1'

    #BOOT Proceed Button
    BMC_BOOT_PROCEED = '__proceed'

    # Select PROTOCAL RETRY
    WEB_PROTOCOL_SELECT_RETRY = 3