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

    # Platforms
    HABANERO = "habanero"
    FIRESTONE = "firestone"
    PALMETTO = "palmetto"

    # BMC COMMANDS
    BMC_COLD_RESET = " mc reset cold"
    BMC_PASS_COLD_RESET = "Sent cold reset command to MC"
    BMC_WARM_RESET = " mc reset warm"
    BMC_PASS_WARM_RESET = "Sent warm reset command to MC"
    BMC_PRESRV_LAN = " raw 0x32 0xba 0x18 0x00"
    BMC_MCHBLD = " raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 " \
                 "0x4f 0x4e 0x00 0x00 0x00 0x00 0x00 0x00 " \
                 "0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 | xxd -r -p"

    BMC_OCC_SENSOR = "raw 0x04 0x30 0x"
    BMC_DISABLE_OCC = " 0x01 0x00 0x01"
    BMC_ENABLE_OCC = " 0x01 0x00 0x02"
    BMC_IPMITOOL_H = "ipmitool -H "
    BMC_FLASH_IMAGE = "echo y | ipmitool -H "
    BMC_FW_IMAGE_UPDATE = "component 1 -z 30000 force"
    BMC_PNOR_IMAGE_UPDATE = "component 2 -z 30000"
    BMC_FWANDPNOR_IMAGE_UPDATE = "-z 30000 force"
    BMC_LANPLUS = " -I lanplus"
    BMC_HPM_UPDATE = " hpm upgrade "
    BMC_ACTIVE_SIDE = " sensor list|grep -i golden"
    BMC_SOL_ACTIVATE = " sol activate"
    BMC_SOL_DEACTIVATE = " sol deactivate"
    BMC_GET_OS_RELEASE = "cat /etc/os-release"

    # Commands to be executed on the OS
    OS_PRESERVE_NETWORK = "ipmitool -I usb raw 0x32 0xba 0x18 0x00"
    LPAR_COLD_RESET = "ipmitool -I usb mc reset cold"
    LPAR_WARM_RESET = "ipmitool -I usb mc reset warm"

    # Command to boot into PRIMARY and GOLDEN SIDE
    BMC_BOOT_PRIMARY = "/etc/init.d/boot_into_primary"
    BMC_BOOT_GOLDEN = "/etc/init.d/boot_into_golden"

    # TIME DELAYS & RETRIES
    BMC_WARM_RESET_DELAY = 150
    BMC_COLD_RESET_DELAY = 150
    LPAR_BRINGUP_TIME = 100
    SHORT_WAIT_IPL = 10
    HOST_REBOOT_DELAY = 100
    WEB_UPDATE_DELAY = 600
    WEB_DRIVER_WAIT = 20
    OCC_ENABLE_WAIT = 200

    PING_RETRY_POWERCYCLE = 7
    PING_RETRY_FOR_STABILITY = 5
    CMD_RETRY_BMC = 2

    # RETURN MESSAGES
    BMC_PASS_COLD_RESET = "Sent cold reset command to MC"
    BMC_ERROR_LAN = "Unable to establish LAN session"
    HOST_CONNECTION_LOST = "closed by remote host"
    ERROR_SELENIUM_HEADLESS = "Host doesn't have selenium installed"
    POWER_ACTIVATE_SUCCESS = "Power limit successfully activated"
    POWER_DEACTIVATE_SUCCESS = "Power limit successfully deactivated"

    # BMC ACTIVE SIDES
    PRIMARY_SIDE = "0x0080"
    GOLDEN_SIDE = "0x0180"

    # Framework Constants
    FW_SUCCESS = 0
    FW_FAILED = 1
    FW_INVALID = 2

    # PingFunc Constants
    PING_FAILED = 0
    PING_UNDETERMINED = 1
    PING_SUCCESS = 2

    # UPDATE_OPTIONS
    UPDATE_BMC = 1
    UPDATE_PNOR = 2
    UPDATE_BMCANDPNOR = 3

    # Energy Scale constants
    ACTIVATE_POWER_LIMIT = " dcmi power activate "
    SET_POWER_LIMIT = " dcmi power set_limit limit "
    ACTIVATE_POWER_LIMIT_SUCCESS = "Power limit successfully activated"
    GET_POWER_LIMIT = " dcmi power get_limit "
    DCMI_POWER_DEACTIVATE = "dcmi power deactivate"
    DCMI_POWER_ACTIVATE = "dcmi power activate"
    OP_CHECK_OCC = "sdr elist |grep 'OCC'"
    OP_CHECK_PROCESSOR = "sensor list|grep -i proc"
    OP_CHECK_CPU = "sensor list|grep -i cpu"
    OP_CHECK_DIMM = "sensor list|grep -i dimm"
    OP_CHECK_FAN = "sensor list|grep -i fan"
    OP_CHECK_SENSOR_LIST = "sensor list"
    OP_GET_TEMP = "dcmi get_temp_reading"
    OP_GET_POWER = "dcmi power reading"

    POWER_ACTIVATE_SUCCESS = "Power limit successfully activated"
    POWER_DEACTIVATE_SUCCESS = "Power limit successfully deactivated"

    # SCP functionality constants
    SCP_TO_REMOTE = 1
    SCP_TO_LOCAL = 2

