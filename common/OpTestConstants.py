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

import pexpect
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
    SHORT_WAIT_STANDBY_DELAY = 5
    LONG_WAIT_IPL = 50
    HOST_REBOOT_DELAY = 100
    WEB_UPDATE_DELAY = 600
    WEB_DRIVER_WAIT = 20
    OCC_ENABLE_WAIT = 200
    OS_TELNET_WAIT = 20
    CHECKSTOP_ERROR_DELAY = 150
    SYSTEM_STANDBY_STATE_DELAY = 120

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
    CHASSIS_POWER_RESET = "Chassis Power Control: Reset"
    CHASSIS_SOFT_OFF = 'S5/G2: soft-off'
    OS_BOOT_COMPLETE = 'boot completed'

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

    IPMI_SOL_CONSOLE_ACTIVATE_OUTPUT = ["[SOL Session operational.  Use ~? for help]\r\n", \
        "Error: Unable to establish IPMI v2 / RMCP+ session", pexpect.TIMEOUT, pexpect.EOF]
    IPMI_CONSOLE_EXPECT_ENTER_OUTPUT = ["login: ", "#", "/ #", "Petitboot", pexpect.TIMEOUT, pexpect.EOF]
    IPMI_CONSOLE_EXPECT_LOGIN = 0
    IPMI_CONSOLE_EXPECT_PASSWORD = 0
    IPMI_CONSOLE_EXPECT_PETITBOOT = [2,3]
    IPMI_CONSOLE_EXPECT_RANDOM_STATE = [4,5]
    IPMI_LPAR_UNIQUE_PROMPT = "PS1=[pexpect]#"
    IPMI_LPAR_EXPECT_PEXPECT_PROMPT = "[pexpect]#"
    IPMI_LPAR_EXPECT_PEXPECT_PROMPT_LIST = [r"\[pexpect\]#$", pexpect.TIMEOUT]

    # HMI Test case constants
    HMI_PROC_RECV_DONE = 1
    HMI_PROC_RECV_ERROR_MASKED = 2
    HMI_MALFUNCTION_ALERT = 3
    HMI_HYPERVISOR_RESOURCE_ERROR = 4
    HMI_TEST_CASE_SLEEP_TIME = 30

    # Timer facility constants
    TOD_ERROR_REG = 40031
    TOD_ERRORS = 5
    # PSS Hamming Distance
    PSS_HAMMING_DISTANCE = "0000200000000000"
    # internal path: delay, step check components: parity error
    INTERNAL_PATH_OR_PARITY_ERROR = "0000020000000000"
    # internal path: delay, step check components: parity error
    # TOD Reg 0x10 data parity error
    TOD_DATA_PARITY_ERROR = "0000000080000000"
    # TOD Sync Check error
    TOD_SYNC_CHECK_ERROR = "0000000040000000"
    # FSM state parity error
    FSM_STATE_PARITY_ERROR = "0000000020000000"
    # Master path control register (0x00): data parity error
    MASTER_PATH_CONTROL_REGISTER = "8000000000000000"
    # port-0 primary configuration register (0x01): data parity error
    PORT_0_PRIMARY_CONFIGURATION_REGISTER = "1000000000000000"
    # port-1 primary configuration register (0x02): data parity error
    PORT_1_PRIMARY_CONFIGURATION_REGISTER = "0800000000000000"
    # port-0 secondary configuration register (0x03): data parity error
    PORT_0_SECONDARY_CONFIGURATION_REGISTER = "0400000000000000"
    # port-1 secondary configuration register (0x04): data parity error
    PORT_1_SECONDARY_CONFIGURATION_REGISTER = "0200000000000000"
    # slave path control register (0x05): data parity error
    SLAVE_PATH_CONTROL_REGISTER = "0100000000000000"
    # internal path control register (0x06): data parity error
    INTERNAL_PATH_CONTROL_REGISTER = "0080000000000000"
    # primary/secondary master/slave control register(0x07); data parity error
    PR_SC_MS_SL_CONTROL_REGISTER = "0040000000000000"
    TFMR_ERRORS = 6
    TB_PARITY_ERROR = "0003080000000000"
    TFMR_PARITY_ERROR = "0001080000000000"
    TFMR_HDEC_PARITY_ERROR = "0002080000000000"
    TFMR_DEC_PARITY_ERROR = "0006080000000000"
    TFMR_PURR_PARITY_ERROR = "0004080000000000"
    TFMR_SPURR_PARITY_ERROR = "0005080000000000"

    # CPU sleep states constants
    GET_CPU_SLEEP_STATE2 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state2/disable"
    GET_CPU_SLEEP_STATE1 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state1/disable"
    GET_CPU_SLEEP_STATE0 = "cat /sys/devices/system/cpu/cpu*/cpuidle/state0/disable"

    DISABLE_CPU_SLEEP_STATE1 = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state1/disable; do echo 1 > $i; done"
    DISABLE_CPU_SLEEP_STATE2 = "for i in /sys/devices/system/cpu/cpu*/cpuidle/state2/disable; do echo 1 > $i; done"

    # PRD driver specific registers
    IPOLL_MASK_REGISTER = "0x01020013"
    # PBAFIR_OCI_APAR_ERR: OCI Address Parity Error Det Address parity
    # error detected by PBA OCI Slave logic for any valid address.
    PBAFIR_OCI_APAR_ERR = 0x8000000000000000
    PBAFIR_PB_CE_FW  = 0x0400000000000000
    PBAFIR_PB_RDDATATO_FW = 0x2000000000000000
    PBAFIR_PB_RDADRERR_FW = 0x6000000000000000
    PBA_FAULT_ISOLATION_REGISTER = "0x02010840"
    PBA_FAULT_ISOLATION_MASK_REGISTER = "0x02010843"

    # Tools, repository and utility paths
    CLONE_SKIBOOT_DIR = "/tmp/skiboot"
    PFLASH_TOOL_DIR = "/tmp/"

    # IPMI commands
    IPMI_LOCK_CMD = "raw 0x32 0xf3 0x4c 0x4f 0x43 0x4b 0x00; echo $?"
    IPMI_UNLOCK_CMD = "raw 0x32 0xF4 0x55 0x4e 0x4c 0x4f 0x43 0x4b 0x00"
    IPMI_LIST_LAST_SEL_EVENT = "sel list last 1"
    IPMI_MC_WATCHDOG_GET = "mc watchdog get"
    IPMI_SDR_GET_WATCHDOG = "sdr get \'Watchdog\'"
    # IPMI White listed commands
    LPAR_GET_DEVICE_ID = "ipmitool raw 0x06 0x01; echo $?"
    LPAR_GET_DEVICE_GUID = "ipmitool raw 0x06 0x08; echo $?"
    LPAR_GET_SYSTEM_GUID = "ipmitool raw 0x06 0x37; echo $?"
    LPAR_RESET_WATCHDOG = "ipmitool raw 0x06 0x22; echo $?"
    LPAR_GET_SEL_INFO = "ipmitool raw 0x0a 0x40; echo $?"
    LPAR_GET_SEL_TIME_RAW = "ipmitool raw 0x0a 0x48; echo $?"
    LPAR_GET_LAN_PARAMETERS = "ipmitool raw 0x0c 0x02 0x01 0x00 0x00 0x00; echo $?"
    LPAR_GET_SYSTEM_BOOT_OPTIONS = "ipmitool raw 0x00 0x09 0x05 0x00 0x00; echo $?"
    LPAR_SET_SYTEM_BOOT_OPTIONS = "ipmitool raw 0x00 0x08 0x05; echo $?"
    LPAR_RESERVE_SEL = "ipmitool  raw 0x0a 0x42; echo $?"
    LPAR_GET_SEL_TIME = "ipmitool sel time get"
    LPAR_SET_SEL_TIME = "ipmitool sel time set"
    LPAR_GET_BMC_GLOBAL_ENABLES = "ipmitool mc getenables"
    LPAR_GET_BMC_GLOBAL_ENABLES_RAW = "ipmitool raw 0x06 0x2f; echo $?"
    LPAR_SET_BMC_GLOBAL_ENABLES_SEL_OFF = "ipmitool mc setenables system_event_log=off; echo $?"
    LPAR_SET_BMC_GLOBAL_ENABLES_SEL_ON = "ipmitool mc setenables system_event_log=on; echo $?"
    LPAR_GET_SYSTEM_INTERFACE_CAPABILITIES_SSIF = "ipmitool raw 0x06 0x57 0x00; echo $?"
    LPAR_GET_SYSTEM_INTERFACE_CAPABILITIES_KCS = "ipmitool raw 0x06 0x57 0x01; echo $?"
    LPAR_GET_MESSAGE_FLAGS = "ipmitool raw 0x06 0x31; echo $?"
    LPAR_GET_BT_CAPABILITIES = "ipmitool raw 0x06 0x36; echo $?"
    LPAR_CLEAR_MESSAGE_FLAGS = "ipmitool raw 0x06 0x30 0xeb; echo $?"
    LPAR_PNOR_ACCESS_STATUS_DENY = "ipmitool raw 0x3a 0x07 0x00; echo $?"
    LPAR_PNOR_ACCESS_STATUS_GRANT = "ipmitool raw 0x3a 0x07 0x01; echo $?"
    LPAR_PNOR_ACCESS_RESPONSE = "ipmitool raw 0x3a 0x08; echo $?"
    LPAR_ADD_SEL_ENTRY = "ipmitool raw 0x0a 0x44 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00; echo $?"
    LPAR_SET_ACPI_POWER_STATE = "ipmitool raw 0x06 0x06 0xaa 0x00; echo $?"
    LPAR_GET_ACPI_POWER_STATE = "ipmitool raw 0x06 0x07; echo $?"
    LPAR_SET_WATCHDOG = "ipmitool raw 0x06 0x24 0x44 0x00 0x00 0x10 0xc8 0x00; echo $?"
    LPAR_GET_SENSOR_TYPE_FOR_WATCHDOG = "ipmitool raw 0x04 0x2f"
    LPAR_GET_SENSOR_READING = "ipmitool raw 0x04 0x2d"
    LPAR_PLATFORM_EVENT = "ipmitool raw 0x04 0x02 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00; echo $?"
    LPAR_CHASSIS_POWER_ON = "ipmitool raw 0x00 0x02 0x01; echo $?"
    LPAR_GET_CHANNEL_AUTH_CAP = "ipmitool raw 0x06 0x38 0x81 0x04; echo $?"

    # Kernel Config Options
    CONFIG_IPMI_DEVICE_INTERFACE = "CONFIG_IPMI_DEVICE_INTERFACE"
    CONFIG_IPMI_POWERNV = "CONFIG_IPMI_POWERNV"
    CONFIG_IPMI_HANDLER = "CONFIG_IPMI_HANDLER"

    # Module Names
    IPMI_DEV_INTF = "ipmi_devintf"
    IPMI_POWERNV = "ipmi_powernv"
    IPMI_MSG_HANDLER = "ipmi_msghandler"
