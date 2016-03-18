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
    GARRISON = 'garrison'

    # BMC COMMANDS
    BMC_COLD_RESET = " mc reset cold"
    BMC_PASS_COLD_RESET = "Sent cold reset command to MC"
    BMC_WARM_RESET = " mc reset warm"
    BMC_PASS_WARM_RESET = "Sent warm reset command to MC"
    BMC_PRESRV_LAN = " raw 0x32 0xba 0x18 0x00"
    BMC_MCHBLD = " raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 " \
                 "0x4f 0x4e 0x00 0x00 0x00 0x00 0x00 0x00 " \
                 "0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 | xxd -r -p"
    BMC_MCHBLD = " raw 0x3a 0x0b 0x56 0x45 0x52 0x53 0x49 0x4f 0x4e 0x00 0x00 0x00 " \
                 "0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 | xxd -r -p"
    BMC_OCC_SENSOR = "raw 0x04 0x30 0x"
    BMC_DISABLE_OCC = " 0x01 0x00 0x01"
    BMC_ENABLE_OCC = " 0x01 0x00 0x02"
    BMC_IPMITOOL_H = "ipmitool -H "
    BMC_FLASH_IMAGE = "echo y | ipmitool -H "
    BMC_FW_IMAGE_UPDATE = "component 1 -z 30000 force"
    BMC_PNOR_IMAGE_UPDATE = "component 2 -z 30000"
    BMC_FWANDPNOR_IMAGE_UPDATE = "-z 30000 force"
    BMC_LANPLUS = " -I lanplus"
    BMC_LANPLUS = " -I lanplus"
    BMC_HPM_UPDATE = " hpm upgrade "
    BMC_ACTIVE_SIDE = " sensor list|grep -i golden"
    BMC_SOL_ACTIVATE = " sol activate"
    BMC_SOL_DEACTIVATE = " sol deactivate"
    BMC_GET_OS_RELEASE = "cat /etc/os-release"
    BMC_SEL_LIST = 'sel list'
    BMC_SDR_ELIST = 'sdr elist'
    BMC_BOOT_COUNT_2 = 'raw 0x04 0x30 xx 0x01 0x00 0x2 0x00' # (replace xx with boot count sensor)
    BMC_BIOS_GOLDEN_SENSOR_TO_PRIMARY = 'raw 0x04 0x30 xx 0x01 0x00 0x00 0 0 0 0 0 0' #Sets sensor to 0 (replace xx with bios golden sensor)
    BMC_BIOS_GOLDEN_SENSOR_TO_GOLDEN = 'raw 0x04 0x30 xx 0x01 0x00 0x01 0 0 0 0 0 0' #Sets sensor to 1 (replace xx with bios golden sensor)


    # Commands to be executed on the OS
    OS_GETSCOM_LIST = "/getscom -l"
    OS_PUTSCOM_ERROR = "/putscom -c "
    OS_READ_MSGLOG_CORE = 'cat /sys/firmware/opal/msglog | grep -i chip | grep -i core'
    OS_PRESERVE_NETWORK = "ipmitool -I usb raw 0x32 0xba 0x18 0x00"
    LPAR_COLD_RESET = "ipmitool -I usb mc reset cold"
    LPAR_WARM_RESET = "ipmitool -I usb mc reset warm"
    SUDO_COMMAND = 'sudo '
    CLEAR_GARD_CMD = '/gard clear all'
    LIST_GARD_CMD = '/gard list'

    # Command to boot into PRIMARY and GOLDEN SIDE
    BMC_BOOT_PRIMARY = "/etc/init.d/boot_into_primary"
    BMC_BOOT_GOLDEN = "/etc/init.d/boot_into_golden"

    # TIME DELAYS & RETRIES
    BMC_WARM_RESET_DELAY = 150
    BMC_COLD_RESET_DELAY = 150
    LPAR_BRINGUP_TIME = 80
    SHORT_WAIT_IPL = 10
    LONG_WAIT_IPL = 50
    HOST_REBOOT_DELAY = 100
    WEB_UPDATE_DELAY = 600
    WEB_DRIVER_WAIT = 20
    OCC_ENABLE_WAIT = 200
    OS_TELNET_WAIT = 20
    CHECKSTOP_ERROR_DELAY = 150

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
    CHASSIS_POWER_ON = 'Chassis Power is on'
    CHASSIS_POWER_OFF = 'Chassis Power is off'
    GARD_CLEAR_SUCCESSFUL = 'Clearing the entire gard partition...done'
    NO_GARD_RECORDS = 'No GARD entries to display'
    CMD_NOT_FOUND = 'command not found'

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

    #Generic Commands
    CLEAR_SSH_KEYS = 'ssh-keygen -R '

    #CPU states
    CPU_ENABLE_STATE = '0'
    CPU_DISABLE_STATE = '1'

    CPU_IDLEMODE_STATE1 = '/sys/devices/system/cpu/cpu*/cpuidle/state1/disable'
    CPU_IDLEMODE_STATE2 = '/sys/devices/system/cpu/cpu*/cpuidle/state2/disable'

    # SCP functionality constants
    SCP_TO_REMOTE = 1
    SCP_TO_LOCAL = 2

    # Constants related to ipmi console interfaces
    IPMI_SOL_ACTIVATE_TIME = 5
    IPMI_SOL_DEACTIVATE_TIME = 10
    IPMI_WAIT_FOR_TERMINATING_SESSION = 10
    IPMI_CON_DELAY_BEFORE_SEND = 0.9

    IPMI_SOL_CONSOLE_ACTIVATE_OUTPUT = "[SOL Session operational.  Use ~? for help]\r\n", \
        "Error: Unable to establish IPMI v2 / RMCP+ session, pexpect.TIMEOUT, pexpect.EOF"
    IPMI_CONSOLE_EXPECT_ENTER_OUTPUT = "login: ", "#", "/ #", "Petitboot", "pexpect.TIMEOUT, pexpect.EOF"
    IPMI_CONSOLE_EXPECT_LOGIN = 0
    IPMI_CONSOLE_EXPECT_PASSWORD = 0
    IPMI_CONSOLE_EXPECT_PETITBOOT = [2,3]
    IPMI_CONSOLE_EXPECT_RANDOM_STATE = [4,5]
    IPMI_LPAR_UNIQUE_PROMPT = "PS1=[pexpect]#"
    IPMI_LPAR_EXPECT_PEXPECT_PROMPT = "[pexpect]#"
    IPMI_LPAR_EXPECT_PEXPECT_PROMPT_LIST = "\[pexpect\]#$"

    # HMI Test case constants
    HMI_PROC_RECV_DONE = 1
    HMI_PROC_RECV_ERROR_MASKED = 2
    HMI_MALFUNCTION_ALERT = 3
    HMI_HYPERVISOR_RESOURCE_ERROR = 4
    HMI_TEST_CASE_SLEEP_TIME = 30

    # CPU sleep states constants
    GET_CPU_SLEEP_STATE2 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state2/disable"
    GET_CPU_SLEEP_STATE1 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state1/disable"
    GET_CPU_SLEEP_STATE0 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state0/disable"

    DISABLE_CPU_SLEEP_STATE1 = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state1/disable; do echo 1 > $i; done"
    DISABLE_CPU_SLEEP_STATE2 = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state2/disable; do echo 1 > $i; done"


