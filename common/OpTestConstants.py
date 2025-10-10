#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestConstants.py $
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

'''
OpTestConstants
---------------

BMC package which contains all BMC related constants

This class encapsulates commands and constants which deals with the BMC in
OpenPower systems
'''

import pexpect


class OpTestConstants():

    # Platforms
    HABANERO = "habanero"
    FIRESTONE = "firestone"
    PALMETTO = "palmetto"
    GARRISON = 'garrison'
    P9DSU = "p9dsu"
    WITHERSPOON = "witherspoon"
    MIHAWK = "mihawk"

    # Platform power limits in watts for different platforms taken from MRW xml file
    HABANERO_POWER_LIMIT_LOW = "1000"
    HABANERO_POWER_LIMIT_HIGH = "1100"
    FIRESTONE_POWER_LIMIT_LOW = "1240"
    FIRESTONE_POWER_LIMIT_HIGH = "1820"
    GARRISON_POWER_LIMIT_LOW = "1240"
    GARRISON_POWER_LIMIT_HIGH = "2880"
    P9DSU_POWER_LIMIT_LOW = "1550"
    P9DSU_POWER_LIMIT_HIGH = "1650"
    WITHERSPOON_POWER_LIMIT_LOW = "1550"
    WITHERSPOON_POWER_LIMIT_HIGH = "3050"
    MIHAWK_POWER_LIMIT_LOW = "1945"
    MIHAWK_POWER_LIMIT_HIGH = "2500"

    PRIMARY_SIDE = "0x0080"
    GOLDEN_SIDE = "0x0180"

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
    BMC_FWANDPNOR_IMAGE_UPDATE = "-z 15000 force"
    BMC_LANPLUS = " -I lanplus"
    BMC_LANPLUS = " -I lanplus"
    BMC_HPM_UPDATE = " hpm upgrade "
    BMC_ACTIVE_SIDE = " sensor list|grep -i golden"
    BMC_SOL_ACTIVATE = " sol activate"
    BMC_SOL_DEACTIVATE = " sol deactivate"
    BMC_SEL_LIST = 'sel list'
    BMC_SDR_ELIST = 'sdr elist'
    # (replace xx with boot count sensor)
    BMC_BOOT_COUNT_2 = 'raw 0x04 0x30 xx 0x01 0x00 0x2 0x00'
    # Sets sensor to 0 (replace xx with bios golden sensor)
    BMC_BIOS_GOLDEN_SENSOR_TO_PRIMARY = 'raw 0x04 0x30 xx 0x01 0x00 0x00 0 0 0 0 0 0'
    # Sets sensor to 1 (replace xx with bios golden sensor)
    BMC_BIOS_GOLDEN_SENSOR_TO_GOLDEN = 'raw 0x04 0x30 xx 0x01 0x00 0x01 0 0 0 0 0 0'

    # Commands to be executed on the OS
    OS_GETSCOM_LIST = "/getscom -l"
    OS_PUTSCOM_ERROR = "/putscom -c "
    OS_READ_MSGLOG_CORE = 'cat /sys/firmware/opal/msglog | grep -i chip | grep -i core'
    OS_PRESERVE_NETWORK = "ipmitool -I usb raw 0x32 0xba 0x18 0x00"
    HOST_COLD_RESET = "ipmitool -I usb mc reset cold"
    HOST_WARM_RESET = "ipmitool -I usb mc reset warm"
    SUDO_COMMAND = 'sudo '
    CLEAR_GARD_CMD = '/gard clear all'
    LIST_GARD_CMD = '/gard list'
    OPAL_MSG_LOG = "cat /sys/firmware/opal/msglog"
    PROC_CMDLINE = "cat /proc/cmdline"
    OPAL_DUMP_NODE = "/proc/device-tree/ibm,opal/dump/"
    NVRAM_PRINT_CFG = "nvram --print-config"
    NVRAM_UPDATE_CONFIG_TEST_DATA = "nvram --update-config test-name=test-value"
    NVRAM_TEST_DATA = "test-name=test-value"
    NVRAM_SET_FAST_RESET_MODE = "nvram -p ibm,skiboot --update-config experimental-fast-reset=feeling-lucky"
    NVRAM_DISABLE_FAST_RESET_MODE = "nvram -p ibm,skiboot --update-config experimental-fast-reset="
    NVRAM_PRINT_FAST_RESET_VALUE = "nvram --print-config=experimental-fast-reset -p ibm,skiboot"
    OCC_ENABLE = "opal-prd occ enable"
    OCC_DISABLE = "opal-prd occ disable"
    OCC_RESET = "opal-prd occ reset"
    OCC_QUERY_RESET_COUNTS = "opal-prd --expert-mode htmgt-passthru 1"
    OCC_SET_RESET_RELOAD_COUNT = "opal-prd --expert-mode htmgt-passthru 4"

    # Command to boot into PRIMARY and GOLDEN SIDE
    BMC_BOOT_PRIMARY = "/etc/init.d/boot_into_primary"
    BMC_BOOT_GOLDEN = "/etc/init.d/boot_into_golden"

    # TIME DELAYS & RETRIES
    BMC_WARM_RESET_DELAY = 20
    BMC_COLD_RESET_DELAY = 150
    HOST_BRINGUP_TIME = 80
    SHORT_WAIT_IPL = 10
    SHORT_WAIT_STANDBY_DELAY = 5
    LONG_WAIT_IPL = 50
    HOST_REBOOT_DELAY = 100
    WEB_UPDATE_DELAY = 600
    WEB_DRIVER_WAIT = 20
    OCC_RESET_RELOAD_COUNT = 15
    OCC_ENABLE_WAIT = 200
    OS_TELNET_WAIT = 20
    CHECKSTOP_ERROR_DELAY = 150
    SYSTEM_STANDBY_STATE_DELAY = 120
    PETITBOOT_TIMEOUT = 1500
    HTTP_RETRY = 10

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
    GARD_CLEAR_SUCCESSFUL = 'Clearing the entire gard partition...done'
    NO_GARD_RECORDS = 'No GARD entries to display'
    CMD_NOT_FOUND = 'command not found'
    CHASSIS_POWER_RESET = "Chassis Power Control: Reset"
    CHASSIS_SOFT_OFF = 'S5/G2: soft-off'
    OS_BOOT_COMPLETE = 'boot completed'
    OCC_DEVICE_ENABLED = "Device Enabled"

    # BMC ACTIVE SIDES
    PRIMARY_SIDE = "0x0080"
    GOLDEN_SIDE = "0x0180"

    # Framework Constants
    FW_SUCCESS = 0
    FW_FAILED = 1
    FW_INVALID = 2
    FW_PARAMETER = 4

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
    OP_CHECK_OCC = "sdr elist |grep -i 'OCC'"
    OP_CHECK_PROCESSOR = "sensor list|grep -i proc"
    OP_CHECK_CPU = "sensor list|grep -i cpu"
    OP_CHECK_DIMM = "sensor list|grep -i dimm"
    OP_CHECK_FAN = "sensor list|grep -i fan"
    OP_CHECK_SENSOR_LIST = "sensor list"
    OP_GET_TEMP = "dcmi get_temp_reading"
    OP_GET_POWER = "dcmi power reading"

    POWER_ACTIVATE_SUCCESS = "Power limit successfully activated"
    POWER_DEACTIVATE_SUCCESS = "Power limit successfully deactivated"

    # CPU states
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

    IPMI_SOL_CONSOLE_ACTIVATE_OUTPUT = ["[SOL Session operational.  Use ~? for help]\r\n",
                                        "Error: Unable to establish IPMI v2 / RMCP+ session", pexpect.TIMEOUT, pexpect.EOF]
    IPMI_CONSOLE_EXPECT_ENTER_OUTPUT = [
        "login: ", "#", "/ #", "Petitboot", pexpect.TIMEOUT, pexpect.EOF, "$"]
    IPMI_CONSOLE_EXPECT_LOGIN = 0
    IPMI_CONSOLE_EXPECT_PASSWORD = 0
    IPMI_CONSOLE_EXPECT_PETITBOOT = [2, 3]
    IPMI_CONSOLE_EXPECT_RANDOM_STATE = [4, 5]

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

    # PBAFIR_OCI_APAR_ERR: OCI Address Parity Error Det Address parity
    # error detected by PBA OCI Slave logic for any valid address.
    FAULT_ISOLATION_REGISTER_CONTENT = "0000000000000000"

    # Tools, repository and utility paths
    CLONE_SKIBOOT_DIR = "/tmp/skiboot"
    PFLASH_TOOL_DIR = "/tmp/"
    GARD_TOOL_DIR = "/tmp/skiboot/external/gard"
    SKIBOOT_WORKING_DIR = "/root/skiboot"

    # IPMI commands
    IPMITOOL_USB = "ipmitool -I usb "
    IPMITOOL_OPEN = "ipmitool "
    # IPMI White listed commands
    HOST_GET_DEVICE_ID = "ipmitool raw 0x06 0x01"
    HOST_GET_DEVICE_GUID = "ipmitool raw 0x06 0x08"
    HOST_GET_SYSTEM_GUID = "ipmitool raw 0x06 0x37"
    HOST_RESET_WATCHDOG = "ipmitool raw 0x06 0x22"
    HOST_GET_SEL_INFO = "ipmitool raw 0x0a 0x40"
    HOST_GET_SEL_TIME_RAW = "ipmitool raw 0x0a 0x48"
    HOST_GET_LAN_PARAMETERS = "ipmitool raw 0x0c 0x02 0x01 0x00 0x00 0x00"
    HOST_GET_SYSTEM_BOOT_OPTIONS = "ipmitool raw 0x00 0x09 0x05 0x00 0x00"
    HOST_SET_SYTEM_BOOT_OPTIONS = "ipmitool raw 0x00 0x08 0x05"
    HOST_RESERVE_SEL = "ipmitool  raw 0x0a 0x42"
    HOST_GET_SEL_TIME = "ipmitool sel time get"
    HOST_SET_SEL_TIME = "ipmitool sel time set"
    HOST_GET_BMC_GLOBAL_ENABLES = "ipmitool mc getenables"
    HOST_GET_BMC_GLOBAL_ENABLES_RAW = "ipmitool raw 0x06 0x2f"
    HOST_SET_BMC_GLOBAL_ENABLES_SEL_OFF = "ipmitool mc setenables system_event_log=off"
    HOST_SET_BMC_GLOBAL_ENABLES_SEL_ON = "ipmitool mc setenables system_event_log=on"
    HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_SSIF = "ipmitool raw 0x06 0x57 0x00"
    HOST_GET_SYSTEM_INTERFACE_CAPABILITIES_KCS = "ipmitool raw 0x06 0x57 0x01"
    HOST_GET_MESSAGE_FLAGS = "ipmitool raw 0x06 0x31"
    HOST_GET_BT_CAPABILITIES = "ipmitool raw 0x06 0x36"
    HOST_CLEAR_MESSAGE_FLAGS = "ipmitool raw 0x06 0x30 0xeb"
    HOST_PNOR_ACCESS_STATUS_DENY = "ipmitool raw 0x3a 0x07 0x00"
    HOST_PNOR_ACCESS_STATUS_GRANT = "ipmitool raw 0x3a 0x07 0x01"
    HOST_PNOR_ACCESS_RESPONSE = "ipmitool raw 0x3a 0x08"
    HOST_ADD_SEL_ENTRY = "ipmitool raw 0x0a 0x44 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00"
    HOST_SET_ACPI_POWER_STATE = "ipmitool raw 0x06 0x06 0xaa 0x00"
    HOST_GET_ACPI_POWER_STATE = "ipmitool raw 0x06 0x07"
    HOST_SET_WATCHDOG = "ipmitool raw 0x06 0x24 0x44 0x00 0x00 0x10 0xc8 0x00"
    HOST_GET_SENSOR_TYPE_FOR_WATCHDOG = "ipmitool raw 0x04 0x2f"
    HOST_GET_SENSOR_READING = "ipmitool raw 0x04 0x2d"
    HOST_PLATFORM_EVENT = "ipmitool raw 0x04 0x02 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00"
    HOST_CHASSIS_POWER_ON = "ipmitool raw 0x00 0x02 0x01"
    HOST_GET_CHANNEL_AUTH_CAP = "ipmitool raw 0x06 0x38 0x81 0x04"
    HOST_IPMI_REPROVISION_REQUEST = "ipmitool raw 0x3A 0x1C"
    HOST_IPMI_REPROVISION_PROGRESS = "ipmitool raw 0x3A 0x1D"

    # Kernel Config Options
    CONFIG_IPMI_DEVICE_INTERFACE = "CONFIG_IPMI_DEVICE_INTERFACE"
    CONFIG_IPMI_POWERNV = "CONFIG_IPMI_POWERNV"
    CONFIG_IPMI_HANDLER = "CONFIG_IPMI_HANDLER"

    # Module Names
    IPMI_DEV_INTF = "ipmi_devintf"
    IPMI_POWERNV = "ipmi_powernv"
    IPMI_MSG_HANDLER = "ipmi_msghandler"

    # OOB IPMI commands
    IPMI_CHASSIS_POH = "chassis poh"
    IPMI_CHASSIS_STATUS = "chassis status"
    IPMI_CHASSIS_RESTART_CAUSE = "chassis restart_cause"
    IPMI_CHASSIS_POLICY_LIST = "chassis policy list"
    IPMI_CHASSIS_POLICY_ALWAYS_ON = "chassis policy always-on"
    IPMI_CHASSIS_POLICY_ALWAYS_OFF = "chassis policy always-off"
    IPMI_CHASSIS_IDENTIFY = "chassis identify"
    IPMI_CHASSIS_IDENTIFY_5 = "chassis identify 5"
    IPMI_CHASSIS_IDENTIFY_FORCE = "chassis identify force"
    IPMI_CHANNEL_INFO = "channel info"
    IPMI_MC_INFO = "mc info"
    IPMI_SEL_INFO = "sel info"
    IPMI_SDR_INFO = "sdr info"
    IPMI_SDR_LIST = "sdr list"
    IPMI_SDR_LIST_ALL = "sdr list all"
    IPMI_SDR_LIST_FRU = "sdr list fru"
    IPMI_SDR_LIST_EVENT = "sdr list event"
    IPMI_SDR_LIST_MCLOC = "sdr list mcloc"
    IPMI_SDR_LIST_COMPACT = "sdr list compact"
    IPMI_SDR_LIST_FULL = "sdr list full"
    IPMI_SDR_LIST_GENERIC = "sdr list generic"
    IPMI_SDR_ELIST = "sdr elist"
    IPMI_SDR_ELIST_ALL = "sdr elist all"
    IPMI_SDR_ELIST_FRU = "sdr elist fru"
    IPMI_SDR_ELIST_EVENT = "sdr elist event"
    IPMI_SDR_ELIST_MCLOC = "sdr elist mcloc"
    IPMI_SDR_ELIST_COMPACT = "sdr elist compact"
    IPMI_SDR_ELIST_FULL = "sdr elist full"
    IPMI_SDR_ELIST_GENERIC = "sdr elist generic"
    IPMI_FRU_PRINT = "fru print"
    IPMI_SDR_TYPE_LIST = "sdr type list"
    IPMI_SDR_TYPE_TEMPERATURE = "sdr type Temperature"
    IPMI_SDR_TYPE_FAN = "sdr type Fan"
    IPMI_SDR_TYPE_POWER_SUPPLY = "sdr type 'Power Supply'"
    IPMI_FRU_READ = "fru read 0 file_fru"
    IPMI_CHASSIS_STATUS = "chassis status"
    IPMI_SENSOR_LIST = "sensor list"
    IPMI_MC_WATCHDOG_GET = "mc watchdog get"
    IPMI_MC_WATCHDOG_OFF = "mc watchdog off"
    IPMI_MC_WATCHDOG_RESET = "mc watchdog reset"
    IPMI_MC_SELFTEST = "mc selftest"
    IPMI_MC_GETENABLES = "mc getenables"
    IPMI_MC_SETENABLES_OEM_0_ON = "mc setenables oem_0=on"
    IPMI_MC_SETENABLES_OEM_0_OFF = "mc setenables oem_0=off"
    IPMI_MC_GUID = "mc guid"
    IPMI_MC_GETSYS_INFO = " mc getsysinfo system_name"
    IPMI_LAN_PRINT = "lan print"
    IPMI_LAN_STATS_GET = "lan stats get"
    IPMI_SEL_INFO = "sel info"
    IPMI_SEL_LIST = "sel list"
    IPMI_SEL_LIST_ENTRIES = "3"
    IPMI_SEL_ELIST = "sel elist"
    IPMI_SEL_TIME_GET = "sel time get"
    IPMI_SEL_CLEAR = "sel clear"
    IPMI_CHANNEL_AUTHCAP = "channel authcap 1 4"
    IPMI_DCMI_DISCOVER = "dcmi discover"
    IPMI_DCMI_POWER_READING = "dcmi power reading"
    IPMI_DCMI_POWER_GET_LIMIT = "dcmi power get_limit"
    IPMI_DCMI_SENSORS = "dcmi sensors"
    IPMI_DCMI_GET_MC_ID_STRING = "dcmi get_mc_id_string"
    IPMI_DCMI_GET_TEMP_READING = "dcmi get_temp_reading"
    IPMI_DCMI_GET_CONF_PARAM = "dcmi get_conf_param"
    IPMI_DCMI_OOB_DISCOVER = "dcmi oob_discover"
    IPMI_ECHO_DONE = "echo Done"
    IPMI_EVENT_1 = "event 1"
    IPMI_EVENT_2 = "event 2"
    IPMI_EVENT_3 = "event 3"
    IPMI_FIREWALL_INFO = "firewall info channel 1 lun 0"
    IPMI_PEF_INFO = "pef info"
    IPMI_PEF_STATUS = "pef status"
    IPMI_PEF_POLICY = "pef policy help"
    IPMI_PEF_LIST = "pef policy list"
    IPMI_RAW_POH = "-v raw 0x0 0xf"
    IPMI_SDR_GET = "sdr get "

    # Power Architecture Specific IPMI Commands
    IPMI_GET_BMC_GOLDEN_SIDE_VERSION = "raw 0x3a 0x1a"
    IPMI_GET_NVRAM_PARTITION_SIZE = "raw 0x3a 0x0c 0x4e 0x56 0x52 0x41 0x4d 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x0 0x0 0x0"
    IPMI_GET_GUARD_PARTITION_SIZE = "raw 0x3a 0x0c 0x47 0x55 0x41 0x52 0x44 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x0 0x0 0x0"
    IPMI_GET_BOOTKERNEL_PARTITION_SIZE = "raw 0x3a 0x0c 0x42 0x4f 0x4f 0x54 0x4b 0x45 0x52 0x4e 0x45 0x4c 0x00 0x00 0x00 0x00 0x0 0x0 0x0"
    IPMI_READ_NVRAM_PARTITION_DATA = "raw 0x3a 0x0b 0x4e 0x56 0x52 0x41 0x4d 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x01 0x00 0x00 0x00"
    IPMI_READ_FIRDATA_PARTITION_DATA = "raw 0x3a 0x0b 0x46 0x49 0x52 0x44 0x41 0x54 0x41 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x01 0x00 0x00 0x00"
    IPMI_HAS_BMC_BOOT_COMPLETED = "raw 0x3a 0x0a"
    IPMI_GET_LED_STATE_FAULT_ROLLUP = "raw 0x3a 0x02 0x00"
    IPMI_GET_LED_STATE_POWER_ON = "raw 0x3a 0x02 0x01"
    IPMI_GET_LED_STATE_HOST_STATUS = "raw 0x3a 0x02 0x02"
    IPMI_GET_LED_STATE_CHASSIS_IDENTIFY = "raw 0x3a 0x02 0x03"
    IPMI_ENABLE_FAN_CONTROL_TASK_THREAD = "raw 0x3a 0x12 0x01"
    IPMI_DISABLE_FAN_CONTROL_TASK_THREAD = "raw 0x3a 0x12 0x00"
    IPMI_FAN_CONTROL_TASK_THREAD_STATE = "raw 0x3a 0x13"
    IPMI_FAN_CONTROL_THREAD_RUNNING = "01"
    IPMI_FAN_CONTROL_THREAD_NOT_RUNNING = "00"
    PNOR_NVRAM_PART = "NVRAM"
    PNOR_GUARD_PART = "GUARD"
    PNOR_BOOTKERNEL_PART = "BOOTKERNEL"

    # Sensor names
    SENSOR_HOST_STATUS = "Host Status"
    SENSOR_OS_BOOT = "OS Boot"
    SENSOR_OCC_ACTIVE = "OCC Active"

    OPAL_ELOG_DIR = "/var/log/opal-elog"
    OPAL_DUMP_DIR = "/var/log/dump/"
    OPAL_ELOG_SYSFS_DIR = "/sys/firmware/opal/elog"
    OPAL_DUMP_SYSFS_DIR = "/sys/firmware/opal/dump"
