#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestOOBIPMI.py $
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

#  @package OpTestOOBIPMI
#  Test the out-of-band ipmi fucntionality package for OpenPower platform.
#
#  This class will test the functionality of following ipmi commands
#  1. bmc, channel, chassis, dcmi, echo, event, exec, firewall, fru, lan
#     mc, pef, power, raw, sdr, sel, sensor, session, user


import time
import subprocess
import re
import os
import sys
import commands

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil


class OpTestOOBIPMI():
    ##  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.util = OpTestUtil()

    ##
    # @brief  It will execute and test all Out-of-band ipmi commands.
    #         bmc, channel, chassis, dcmi, echo, event, exec, firewall, fru, lan
    #         mc, pef, power, raw, sdr, sel, sensor, session, user
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_oob_ipmi(self):
        print "OOB IPMI: Chassis tests"
        self.test_chassis()
        print "OOB IPMI: chassis identify tests"
        self.test_chassisIdentifytests()
        print "OOB IPMI: chassis bootdevice tests"
        self.test_chassisBootdev()
        print "OOB IPMI: info tests"
        self.test_Info()
        print "OOB IPMI: sdr tests"
        self.test_sdr_list_by_type()
        self.test_sdr_elist_by_type()
        self.test_sdr_type_list()
        self.test_sdr_get_id()
        print "OOB IPMI: Fru tests"
        self.test_fru_print()
        self.test_fru_read()
        print "OOB IPMI: MC tests"
        self.test_mc()
        print "OOB IPMI: Sensor tests"
        self.test_sensor_list()
        self.test_sensor_byid("Host Status")
        self.test_sensor_byid("OS Boot")
        self.test_sensor_byid("OCC Active")
        print "OOB IPMI: SEL tests"
        self.test_sel_info()
        self.test_sel_list()
        self.test_sel_elist()
        l_res = self.test_sel_time_get()
        self.test_sel_time_set(l_res[0])
        i_num = "3"
        self.test_sel_list_first_n_entries(i_num)
        self.test_sel_list_last_n_entries(i_num)
        self.test_sel_get_functionality()
        self.test_sel_clear_functionality()
        print "OOB IPMI: Channel Tests"
        self.test_channel()
        print "OOB IPMI: dcmi tests"
        self.test_dcmi()
        print "OOB IPMI: echo tests"
        self.test_echo()
        print "OOB IPMI: event tests"
        self.test_event()
        print "OOB IPMI: Firewall test"
        self.test_firewall()
        print "OOB IPMI: Pef tests"
        self.test_pef()
        print "OOB IPMI: raw command execution tests"
        self.test_raw()
        print "OOB IPMI: exec tests"
        self.test_exec()
        print "OOB IPMI: Get BMC Golden side Version Test"
        self.test_bmc_golden_side_version()
        print "OOB IPMI: Get size of PNOR partition Test"
        self.test_get_pnor_partition_size_cmd()
        print "OOB IPMI: Get BMC boot completion status Test"
        self.test_bmc_boot_completed_cmd()
        print "OOB IPMI: Get state of various LED's"
        self.test_get_led_state_cmd()
        print "OOB IPMI: Set LED state of various LED's"
        self.test_set_led_state_cmd()
        print self.cv_IPMI.ipmi_get_bmc_golden_side_version()
        print self.cv_IPMI.ipmi_get_pnor_partition_size("NVRAM")
        print self.cv_IPMI.ipmi_get_pnor_partition_size("GUARD")
        print self.cv_IPMI.ipmi_get_pnor_partition_size("BOOTKERNEL")
        print self.cv_IPMI.ipmi_get_bmc_boot_completion_status()
        print self.cv_IPMI.ipmi_get_fault_led_state()
        print self.cv_IPMI.ipmi_get_power_on_led_state()
        print self.cv_IPMI.ipmi_get_host_status_led_state()
        print self.cv_IPMI.ipmi_get_chassis_identify_led_state()
        self.cv_IPMI.ipmi_enable_fan_control_task_command()
        self.cv_IPMI.ipmi_get_fan_control_task_state_command()
        self.cv_IPMI.ipmi_disable_fan_control_task_command()
        self.cv_IPMI.ipmi_get_fan_control_task_state_command()

    ##
    # @brief  This function is used to get the bmc golden image version.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_bmc_golden_side_version(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_BMC_GOLDEN_SIDE_VERSION)

    ##
    # @brief This function is used to get partition size of given PNOR Partition.
    #        Currently added NVRAM,GUARD and BOOTKERNEL partitions.
    #        TODO: Add all the necessary partitions to get the size.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_get_pnor_partition_size_cmd(self):
        print "OOB IPMI: Getting the size of NVRAM partition"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_NVRAM_PARTITION_SIZE)
        print "OOB IPMI: Getting the size of GUARD partition"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_GUARD_PARTITION_SIZE)
        print "OOB IPMI: Getting the size of BOOTKERNEL partition"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_BOOTKERNEL_PARTITION_SIZE)

    ##
    # @brief This function is used to test reading of pnor partition data
    #        via ipmitool command. Here it will currently read NVRAM
    #        and FIRDATA partition's data of size 254 bytes.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_read_pnor_partition_data(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_READ_NVRAM_PARTITION_DATA)
        self.run_ipmi_cmd(BMC_CONST.IPMI_READ_FIRDATA_PARTITION_DATA)

    ##
    # @brief This function is used to check whether BMC Completed Booting.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_bmc_boot_completed_cmd(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_HAS_BMC_BOOT_COMPLETED)

    ##
    # @brief This command is used to get the State of below Supported LED.
    #        LED Number Table:
    #        Fault RollUP LED      0x00
    #        Power ON LED          0x01
    #        Host Status LED       0x02
    #        Chassis Identify LED  0x03
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_get_led_state_cmd(self):
        print "LED: Fault RollUP LED      0x00"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_LED_STATE_FAULT_ROLLUP)
        print "LED: Power ON LED          0x01"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_LED_STATE_POWER_ON)
        print "LED: Host Status LED       0x02"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_LED_STATE_HOST_STATUS)
        print "LED: Chassis Identify LED  0x03"
        self.run_ipmi_cmd(BMC_CONST.IPMI_GET_LED_STATE_CHASSIS_IDENTIFY)

    ##
    # @brief This function is used to test set LED state feature.
    #        LED Number Table:
    #        Fault RollUP LED      0x00
    #        Power ON LED          0x01
    #        Host Status LED       0x02
    #        Chassis Identify LED  0x03
    #        LED State Table:
    #        LED State to be set.
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_set_led_state_cmd(self):
        self.cv_IPMI.ipmi_set_led_state("0x00", "0x0")
        self.cv_IPMI.ipmi_get_fault_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x00", "0x1")
        self.cv_IPMI.ipmi_get_fault_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x00", "0x2")
        self.cv_IPMI.ipmi_get_fault_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x00", "0x3")
        self.cv_IPMI.ipmi_get_fault_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x01", "0x0")
        self.cv_IPMI.ipmi_get_power_on_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x01", "0x1")
        self.cv_IPMI.ipmi_get_power_on_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x01", "0x2")
        self.cv_IPMI.ipmi_get_power_on_led_state()
        self.cv_IPMI.ipmi_set_led_state("0x01", "0x3")
        self.cv_IPMI.ipmi_get_power_on_led_state()

    ##
    # @brief Step 1: Stop Fan Control Thread:
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x12 0x00
    #        Step 2: Fan Control STOPPED OEM SEL created
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> sel list |grep OEM
    #           7b | 04/20/2015 | 03:03:14 | OEM record c0 | 000000 | 3a1100ffffff
    #        Step 3: #Run IsFanRunning OEM Command
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x13
    #           00
    #
    # @return return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_fan_control_algorithm_1(self):
        print "OOB IPMI: Testing Fan control disable functionality"
        self.cv_IPMI.ipmi_enable_fan_control_task_command()
        self.cv_IPMI.ipmi_sdr_clear()
        l_state = self.cv_IPMI.ipmi_get_fan_control_task_state_command()
        if str(BMC_CONST.IPMI_FAN_CONTROL_THREAD_RUNNING) in l_state:
            self.cv_IPMI.ipmi_disable_fan_control_task_command()
            l_state = self.cv_IPMI.ipmi_get_fan_control_task_state_command()
            if str(BMC_CONST.IPMI_FAN_CONTROL_THREAD_NOT_RUNNING) in l_state:
                l_output = self.cv_IPMI.ipmi_get_sel_list()
                print l_output
                if "OEM" in l_output:
                    print "IPMI: Disabling of fan control creates an OEM SEL event"
                    return BMC_CONST.FW_SUCCESS
                else:
                    l_msg = "IPMI: Disabling of fan control doesn't create an OEM SEL event"
                    raise OpTestError(l_msg)
            else:
                l_msg = "IPMI: Fan control thread still running, disable failed"
                raise OpTestError(l_msg)
        else:
            l_msg = "IPMI: Fan control thread still in not running state, enable failed"
            raise OpTestError(l_msg)

    ##
    # @brief Step 1: Start Fan Control Thread:
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x12 0x01
    #        Step 2: Fan Control STOPPED OEM SEL created
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> sel list |grep OEM
    #           7b | 04/20/2015 | 03:03:14 | OEM record c0 | 000000 | 3a1100ffffff
    #        Step 3: #Run IsFanRunning OEM Command
    #           ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x13
    #           01
    #
    # @return return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_fan_control_algorithm_2(self):
        print "OOB IPMI: Testing Fan control enable functionality"
        self.cv_IPMI.ipmi_disable_fan_control_task_command()
        self.cv_IPMI.ipmi_sdr_clear()
        l_state = self.cv_IPMI.ipmi_get_fan_control_task_state_command()
        if l_state == str(BMC_CONST.IPMI_FAN_CONTROL_THREAD_NOT_RUNNING):
            self.cv_IPMI.ipmi_enable_fan_control_task_command()
            l_state = self.cv_IPMI.ipmi_get_fan_control_task_state_command()
            if l_state == str(BMC_CONST.IPMI_FAN_CONTROL_THREAD_RUNNING):
                l_output = self.cv_IPMI.ipmi_get_sel_list()
                print l_output
                if "OEM" in l_output:
                    print "IPMI: Enabling of fan control creates an OEM SEL event"
                    return BMC_CONST.FW_SUCCESS
                else:
                    l_msg = "IPMI: Enabling of fan control doesn't create an OEM SEL event"
                    raise OpTestError(l_msg)
            else:
                l_msg = "IPMI: Fan control thread still in not running state, enable failed"
                raise OpTestError(l_msg)
        else:
            l_msg = "IPMI: Fan control thread still running, disable failed"
            raise OpTestError(l_msg)

    ##
    # @brief  It will check basic channel functionalities: info and authentication capabilities.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_channel(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHANNEL_AUTHCAP)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHANNEL_INFO)

    ##
    # @brief  It will execute and test the return code of ipmi command.
    #
    # @param i_cmd @type string:The ipmitool command, for example: chassis power on; echo $?
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def run_ipmi_cmd(self, i_cmd):
        l_cmd = i_cmd
        l_res = self.cv_IPMI.ipmitool_execute_command(l_cmd)
        print l_res
        l_res = l_res.splitlines()
        if int(l_res[-1]):
            l_msg = "IPMI: command failed %c" % l_cmd
            raise OpTestError(l_msg)
        return l_res

    ##
    # @brief  It will execute and test the ipmi chassis <cmd> commands
    #         cmd: status, poh, restart_cause, policy list and policy set
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_chassis(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_STATUS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_POH)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_RESTART_CAUSE)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_POLICY_LIST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_POLICY_ALWAYS_OFF)

    ##
    # @brief  It will execute and test the ipmi chassis identify commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_chassisIdentifytests(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_IDENTIFY)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_IDENTIFY_5)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_IDENTIFY)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_IDENTIFY_FORCE)
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_IDENTIFY)

    ##
    # @brief  It will execute and test the functionality of ipmi chassis bootdev <dev>
    #         dev: none,pxe,cdrom,disk,bios,safe,diag,floppy and none.
    #
    # @return BMC_CONST.FW_SUCCESS on success or raise OpTestError
    #
    def test_chassisBootdev(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_NONE)
        self.verify_bootdev("none")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_PXE)
        self.verify_bootdev("pxe")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_CDROM)
        self.verify_bootdev("cdrom")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_DISK)
        self.verify_bootdev("disk")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_BIOS)
        self.verify_bootdev("bios")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_SAFE)
        self.verify_bootdev("safe")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_DIAG)
        self.verify_bootdev("diag")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_FLOPPY)
        self.verify_bootdev("floppy")
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTDEV_NONE)
        self.verify_bootdev("none")

    ##
    # @brief  It will verify whether setting of given bootdevice is honoured or not
    #         by reading chassis bootparam get 5
    #
    # @param i_dev @type string: boot device name: Ex safe, disk and cdrom
    #
    # @return BMC_CONST.FW_SUCCESS on success or raise OpTestError
    #
    def verify_bootdev(self, i_dev):
        l_res = self.run_ipmi_cmd(BMC_CONST.IPMI_CHASSIS_BOOTPARAM_GET_5)
        if i_dev == "safe":
            l_msg = "Force Boot from default Hard-Drive, request Safe-Mode"
        elif i_dev == "disk":
            l_msg = "Force Boot from default Hard-Drive"
        elif i_dev == "diag":
            l_msg = "Force Boot from Diagnostic Partition"
        elif i_dev == "bios":
            l_msg = "Force Boot into BIOS Setup"
        elif i_dev == "pxe":
            l_msg = "Force PXE"
        elif i_dev == "cdrom":
            l_msg = "Force Boot from CD/DVD"
        elif i_dev == "none":
            l_msg = "No override"
        elif i_dev == "floppy":
            l_msg = "Force Boot from Floppy/primary removable media"
        else:
            print "pass proper bootdevice"

        for l_line in l_res:
            if l_line.__contains__(l_msg):
                print "Verifying bootdev is successfull for %s" % i_dev
                return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Boot device is not set to %s" % i_dev
            raise OpTestError(l_msg)

    ##
    # @brief  It will execute and test the ipmi <sdr/sel/mc/channel> info related commands.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_Info(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_CHANNEL_INFO)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_INFO)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_INFO)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_INFO)

    ##
    # @brief  It will execute and test the ipmi sdr list <all/fru/event/mcloc/compact/full/generic>
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_list_by_type(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_ALL)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_FRU)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_EVENT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_MCLOC)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_COMPACT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_FULL)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_LIST_GENERIC)

    ##
    # @brief  It will execute and test the ipmi sdr elist <all/fru/event/mcloc/compact/full/generic>
    #         commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_elist_by_type(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_ALL)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_FRU)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_EVENT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_MCLOC)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_COMPACT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_FULL)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_ELIST_GENERIC)

    ##
    # @brief  It will execute and test the ipmi sdr type <Temp/fan/Powersupply> commands
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_type_list(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_TYPE_LIST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_TYPE_TEMPERATURE)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_TYPE_FAN)
        self.run_ipmi_cmd(BMC_CONST.IPMI_SDR_TYPE_POWER_SUPPLY)

    ##
    # @brief  It will execute and test the ipmi sdr get <sensor-id> command
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sdr_get_id(self):
        l_cmd = BMC_CONST.IPMI_SDR_GET_WATCHDOG + "; echo $?"
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the ipmi fru print command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_fru_print(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_FRU_PRINT)

    ##
    # @brief  It will execute and test the ipmi fru read command.
    #         then the output file is displayed by hexdump
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_fru_read(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_FRU_READ)
        l_res = commands.getstatusoutput("hexdump -C file_fru")
        if int(l_res[0]) == 0:
            print l_res[1]
        else:
            l_msg = "Failing to do hexdump for fru file"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief  It will execute and test the ipmi sensor list functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_list(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SENSOR_LIST)

    ##
    # @brief  It will execute and test the ipmi sensor get <id> functionality
    #
    # @param i_sensor @type string:sensor id to retrieve the data
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sensor_byid(self, i_sensor):
        l_cmd = "sensor get \"%s\"; echo $?" % i_sensor
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the management controller(mc) commands functionality
    #         info-Displays information about the BMC hardware, including device revision,
    #              firmware revision, IPMI version supported, manufacturer ID,  and  information
    #               on additional device support
    #         watchdog get-Show current Watchdog Timer settings and countdown state.
    #         watchdog off-Turn off a currently running Watchdog countdown timer.
    #         watchdog reset-Reset the Watchdog Timer to its most recent state and restart the countdown timer.
    #         selftest- Check on the basic health of the BMC by executing the
    #                   Get Self Test results command and report the results.
    #         setenables-Enables  or disables the given option
    #         getenables-Displays a list of the currently enabled options for the BMC.
    #         getsysinfo-Retrieves system info from bmc for given argument
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_mc(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_INFO)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_WATCHDOG_GET)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_SELFTEST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_SELFTEST)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_SETENABLES_OEM_0_OFF)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_GETENABLES)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_SETENABLES_OEM_0_ON)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_GETENABLES)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_WATCHDOG_OFF)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_WATCHDOG_RESET)
        self.run_ipmi_cmd(BMC_CONST.IPMI_MC_GETSYS_INFO)

    ##
    # @brief  It will execute and test the ipmi sel info functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_info(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_INFO)

    ##
    # @brief  It will execute and test ipmi sel list functionality.
    #         the entire contents of the System Event Log are displayed.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_LIST)

    ##
    # @brief  It will execute and test the ipmi sel elist functionality
    #         If invoked as elist (extended list) it will also use the
    #         Sensor Data Record entries to display the sensor ID for
    #           the sensor that caused each event.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_elist(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_ELIST)

    ##
    # @brief  It will execute and test the ipmi sel time get functionality
    #         Displays the SEL clock's current time.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_time_get(self):
        l_res = self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_TIME_GET)
        return l_res

    ##
    # @brief  It will execute and test the ipmi sel set <time string> functionality
    #         Sets the SEL clock.  Future SEL entries will use the time set by this command.
    #
    # @param i_time @type string: the value to be set as a sel time
    #               <time string> is of the form "MM/DD/YYYY HH:MM:SS"
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_time_set(self, i_time):
        l_cmd = "sel time set \'%s\'; echo $?" % i_time
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the ipmi sel list first <n entries>
    #
    # @param i_num @type string:The num of entries of sel to be listed
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_first_n_entries(self, i_num):
        l_cmd = "sel list first %i; echo $?" % int(i_num)
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the ipmi sel list last <n entries>
    #
    # @param i_num @type string:The num of entries of sel to be listed
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_list_last_n_entries(self, i_num):
        l_cmd = "sel list last %i; echo $?" % int(i_num)
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the ipmi sel get <id> functionality
    #
    # @param i_sel_id @type string: for example 0x05, 0x06..
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_get_byid(self, i_sel_id):
        l_cmd = "sel get %s; echo $?" % i_sel_id
        self.run_ipmi_cmd(l_cmd)

    ##
    # @brief  It will execute and test the ipmi sel clear functionality
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_sel_clear(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_SEL_CLEAR)

    ##
    # @brief  It will execute and test the ipmi sel get <id> functionality
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_sel_get_functionality(self):
        l_res = self.cv_IPMI.ipmitool_execute_command("sel list first 3 | awk '{print $1}'; echo $?")
        l_list = l_res.splitlines()
        if int(l_list[-1]) == 0:
            if l_res.__contains__("SEL has no entries"):
                print "There are No sel entries to fetch"
                pass
            else:
                del l_list[-1]
                for l in l_list:
                    l_id = "0x" + l
                    self.test_sel_get_byid(l_id)
                return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Not able to get sel entries"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief  It will execute and test the ipmi sel clear functionality
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_sel_clear_functionality(self):
        self.test_sel_clear()
        l_res = self.cv_HOST.host_run_command("ipmitool sel list; echo $?")
        l_list = l_res.splitlines()
        for l_line in l_list:
            if l_line.__contains__("SEL has no entries"):
                print "Sel clear function got cleared event entries"
                return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "OOB IPMI: sel clear function failing in clearing entries"
            print l_msg
            print l_res
            raise OpTestError(l_msg)

    ##
    # @brief  It will execute and test the dcmi related ipmi commands.
    #         discover-This command is used to discover supported capabilities in DCMI
    #         Power reading-Get power related readings from the system.
    #               get_limit-Get the configured power limits.
    #         sensors-Prints the available DCMI sensors.
    #         get_mc_id_string-Get management controller identifier string
    #         get_temp_reading-Get Temperature Sensor Readings.
    #         get_conf_param-Get DCMI Configuration Parameters.
    #         oob_discover-Ping/Pong Message for DCMI Discovery
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_dcmi(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_DISCOVER)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_POWER_GET_LIMIT)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_SENSORS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_MC_ID_STRING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_TEMP_READING)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_GET_CONF_PARAM)
        self.run_ipmi_cmd(BMC_CONST.IPMI_DCMI_OOB_DISCOVER)

    ##
    # @brief  It will execute and test the functionality of ipmi echo command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_echo(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_ECHO_DONE)

    ##
    # @brief  It will execute and test event related commands to test sel functionality.
    #         Send a pre-defined test event to the System Event Log.  The following
    #         events are included as a means to test the functionality of  the  System
    #         Event Log component of the BMC (an entry will be added each time the
    #         event N command is executed)
    #         Currently supported values for N are:
    #         1    Temperature: Upper Critical: Going High
    #         2    Voltage Threshold: Lower Critical: Going Low
    #         3    Memory: Correctable ECC
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_event(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_EVENT_1)
        self.run_ipmi_cmd(BMC_CONST.IPMI_EVENT_2)
        self.run_ipmi_cmd(BMC_CONST.IPMI_EVENT_3)

    ##
    # @brief  It will execute and test ipmi exec command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_exec(self):
        pass
        # TODO: need to execute ipmi commands from a file

    ##
    # @brief  It will execute and test firmware firewall info command.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_firewall(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_FIREWALL_INFO)

    ##
    # @brief  It will execute and test pef related commands:
    #         info:This command will query the BMC and print information about the PEF supported features.
    #         status: This command prints the current PEF status
    #         policy: This command lists the PEF policy table entries
    #         list: This  command  lists  the PEF table entries.
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_pef(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_PEF_INFO)
        self.run_ipmi_cmd(BMC_CONST.IPMI_PEF_STATUS)
        self.run_ipmi_cmd(BMC_CONST.IPMI_PEF_POLICY)
        self.run_ipmi_cmd(BMC_CONST.IPMI_PEF_LIST)

    ##
    # @brief This will test raw IPMI commands. For example to query the POH counter with a raw command
    #
    # @return l_res @type list: output of command or raise OpTestError
    #
    def test_raw(self):
        self.run_ipmi_cmd(BMC_CONST.IPMI_RAW_POH)
