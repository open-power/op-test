#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestConstants.py $
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

## @package OpTestConstants
#  BMC package which contains all BMC related constants
#
#  This class encapsulates commands and constants which deals with the BMC in OpenPower
#  systems

class OpTestConstants():

    HABANERO = "habanero"
    FIRESTONE = "firestone"
    PALMETTO = "palmetto"

    BMC_COLD_RESET = " mc reset cold"
    BMC_COLD_RESET_DELAY = 100
    BMC_PASS_COLD_RESET = "Sent cold reset command to MC"

    BMC_WARM_RESET = " mc reset warm"
    BMC_WARM_RESET_DELAY = 100
    BMC_PASS_WARM_RESET = "Sent warm reset command to MC"

    BMC_PRESRV_LAN = " raw 0x32 0xba 0x18 0x00"
    BMC_MCHBLD = " raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 " \
                 "0x4f 0x4e 0x0 0x0 0x0 0x0 0x0 0x0 |xxd -r -p"
    BMC_IPMITOOL_H = "ipmitool -H "
    BMC_FLASH_IMAGE = "echo y | ipmitool -H "
    BMC_FW_IMAGE_UPDATE = " component 1 -z 30000 force"
    BMC_PNOR_IMAGE_UPDATE = " component 2 -z 30000"
    BMC_FWANDPNOR_IMAGE_UPDATE = " -z 30000 force"
    BMC_LANPLUS = " -I lanplus" #-U ADMIN -P admin"
    BMC_HPM_UPDATE = " hpm upgrade "
    BMC_ACTIVE_SIDE = " sensor list|grep -i golden"
    BMC_SOL_ACTIVATE = " sol activate"
    BMC_SOL_DEACTIVATE = " sol deactivate"
    BMC_GET_OS_RELEASE = "cat /etc/os-release"

    BMC_PASS_COLD_RESET = "Sent cold reset command to MC"
    BMC_ERROR_LAN = "Unable to establish LAN session"

    BMC_ADMIN_USER = "ADMIN"
    BMC_SYADMIN_USER = "sysadmin"

    PRIMARY_SIDE = "0x0080"
    GOLDEN_SIDE = "0x0180"

    # Framework Constants
    FW_SUCCESS = 0
    FW_FAILED = 1

    # PingFunc Constants
    PING_FAILED = 0
    PING_UNDETERMINED = 1
    PING_SUCCESS = 2

    # Commands to be executed on the OS
    OS_PRESERVE_NETWORK = "ipmitool -I usb raw 0x32 0xba 0x18 0x00"
    LPAR_COLD_RESET = "ipmitool -I usb mc reset cold"
    LPAR_WARM_RESET = "ipmitool -I usb mc reset warm"


    # Sleep times
    LPAR_BRINGUP_TIME = 80
