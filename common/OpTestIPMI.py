#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestIPMI.py $
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

## @package OpTestIPMI
#  IPMI package which contains all BMC related IPMI commands
#
#  This class encapsulates all function which deals with the BMC over IPMI
#  in OpenPower systems

import time
import subprocess
import os
import pexpect
import sys
#from subprocess import check_output
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestLpar import OpTestLpar
from OpTestUtil import OpTestUtil

class OpTestIPMI():

    ##
    # @brief Initialize this object
    #
    # @param i_bmcIP @type string: IP Address of the BMC
    # @param i_bmcUser @type string: Userid to log into the BMC
    # @param i_bmcPwd @type string: Password of the userid to log into the BMC
    # @param i_ffdcDir @type string: Optional param to indicate where to write FFDC
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPwd, i_ffdcDir, i_lparip=None,
                       i_lparuser=None, i_lparPasswd=None):

        self.cv_bmcIP = i_bmcIP
        self.cv_bmcUser = i_bmcUser
        self.cv_bmcPwd = i_bmcPwd
        self.cv_ffdcDir = i_ffdcDir
        self.cv_baseIpmiCmd = 'ipmitool -H %s -I lanplus -U %s -P %s ' \
                      % (self.cv_bmcIP, self.cv_bmcUser, self.cv_bmcPwd)
        self.util = OpTestUtil()
        self.lpar_ip = i_lparip
        self.lpar_user = i_lparuser
        self.lpar_passwd = i_lparPasswd


    ##
    # @brief Runs an ipmitool command.
    #    The command argument is the last ipmitool command argument, for example:
    #    'chassis power cycle' or 'sdr elist'.  You can append other shell commands
    #    to the string, for instance 'sdr elist|grep Host'.
    #    Use backround=1, to spawn the child process and return the popen object,
    #    rather than waiting for the command completion and returning only the
    #    output.
    #
    # @param cmd @type string: The ipmitool command, for example: chassis power on
    # @param background @type bool: Spawn the command in as a background process.
    #        This is useful to monitor sensors or other runtime info. With
    #        background=False the function will block until the command finishes.
    #
    # @returns When background=1 it returns the subprocess child object. When
    #        background==False,it returns the output of the command.
    #
    #        raises: OpTestError when fails
    #
    def _ipmitool_cmd_run(self, cmd, background=False):

        print cmd
        if background:
            try:
                child = subprocess.Popen(cmd, shell=True)
            except:
                l_msg = "Ipmitool Command Failed"
                print l_msg
                raise OpTestError(l_msg)
            return child
        else:
            # TODO - need python 2.7
            # output = check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            try:
                cmd = subprocess.Popen(cmd,stderr=subprocess.STDOUT,
                                       stdout=subprocess.PIPE,shell=True)
            except:
                l_msg = "Ipmitool Command Failed"
                print l_msg
                raise OpTestError(l_msg)
            output = cmd.communicate()[0]
            return output


    ##
    # @brief Runs an ipmitool command
    #    The command argument is the last ipmitool command argument, for example:
    #    'chassis power cycle' or 'sdr elist'.  You can append other shell commands
    #    to the string, for instance 'sdr elist|grep Host'.
    #
    # @param i_cmd @type string: The ipmitool command, for example: chassis power on
    #
    # @return l_output @type string: it returns the output of the command or raise OpTestError
    #
    def ipmitool_execute_command(self, i_cmd):
        l_cmd = i_cmd
        l_output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)
        return l_output


    ##
    # @brief This function clears the sensor data
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_sdr_clear(self):

        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'sel clear')
        if 'Clearing SEL' in output:
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'sel elist')
            if 'no entries' in output:
                return BMC_CONST.FW_SUCCESS
            else:
                l_msg = "Sensor data still has entries!"
                print l_msg
                raise OpTestError(l_msg)
        else:
            l_msg = "Clearing the sensor data Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power off ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_off(self):
        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power off')
        time.sleep(BMC_CONST.LONG_WAIT_IPL)
        if 'Down/Off' in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power OFF Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power on ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_on(self):
        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power on')
        time.sleep(BMC_CONST.LONG_WAIT_IPL)
        if 'Up/On' in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power ON Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power soft ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_soft(self):
        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power soft')
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if "Chassis Power Control: Soft" in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Soft Failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function sends the chassis power cycle ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_cycle(self):
        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power cycle')
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if "Chassis Power Control: Cycle" in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Cycle Failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function sends the chassis power reset ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_reset(self):
        l_output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power reset')
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if BMC_CONST.CHASSIS_POWER_RESET in l_output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Reset Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief Spawns the sol logger expect script as a background process. In order to
    #        properly kill the process the caller should call the ipmitool sol
    #        deactivate command, i.e.: ipmitool_cmd_run('sol deactivate'). The sol.log
    #        file is placed in the FFDC directory
    #
    # @return OpTestError
    #
    def _ipmi_sol_capture(self):

        try:
            self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'sol deactivate')
        except OpTestError:
            print 'SOL already deactivated'
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        logFile = self.cv_ffdcDir + '/' + 'host_sol.log'
        cmd = os.getcwd() + '/../common/sol_logger.exp %s %s %s %s' % (
            self.cv_bmcIP,
            self.cv_bmcUser,
            self.cv_bmcPwd,
            logFile)
        print cmd
        try:
            solChild = subprocess.Popen(cmd, shell=True)
        except:
            raise OpTestError("sol capture Failed")
        return solChild


    ##
    # @brief This function starts the sol capture and waits for the IPL to end. The
    #        marker for IPL completion is the Host Status sensor which reflects the ACPI
    #        power state of the system.  When it reads S0/G0: working it means that the
    #        petitboot is has began loading.  The overall timeout for the IPL is defined
    #        in the test configuration options.'''
    #
    # @param timeout @type int: The number of minutes to wait for IPL to complete,
    #       i.e. How long to poll the ACPI sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipl_wait_for_working_state(self, timeout=10):

        ''' WORKAROUND FOR AMI BUG
         A sleep is required here because Host status sensor is set incorrectly
         to working state right after power on '''
        sol = self._ipmi_sol_capture()
        time.sleep(60)

        timeout = time.time() + 60*timeout

        ''' AMI BUG is fixed now
         After updating the AMI level the Host Status sensor works as expected.
         '''
        cmd = 'sdr elist |grep \'Host Status\''
        while True:
            output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + cmd)
            if 'S0/G0: working' in output:
                print "Host Status is S0/G0: working, IPL finished"
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)

        try:
            self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'sol deactivate')
        except subprocess.CalledProcessError:
            l_msg = 'SOL already deactivated'
            print l_msg
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function waits for system to reach standby state or soft off. The
    #        marker for standby state is the Host Status sensor which reflects the ACPI
    #        power state of the system.  When it reads S5/G2: soft-off it means that the
    #        system reached standby or soft-off state. The overall timeout for the standby is defined
    #        in the test configuration options.'''
    #
    # @param i_timeout @type int: The number of seconds to wait for system to reach standby,
    #       i.e. How long to poll the ACPI sensor for soft-off state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_standby_state(self, i_timeout=120):
        l_timeout = time.time() + i_timeout
        l_cmd = 'sdr elist |grep \'Host Status\''
        while True:
            l_output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)
            if BMC_CONST.CHASSIS_SOFT_OFF in l_output:
                print "Host Status is S5/G2: soft-off, system reached standby"
                break
            if time.time() > l_timeout:
                l_msg = "Standby timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_STANDBY_DELAY)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function waits for the Host OS Boot(IPL) to end. The
    #        marker for IPL completion is the OS Boot sensor which reflects status
    #        of host OS Boot. When it reads boot completed it means that the
    #        Host OS Booted successfully.  The overall timeout for the IPL is defined
    #        in the test configuration options.'''
    #
    # @param i_timeout @type int: The number of minutes to wait for IPL to complete or Boot time,
    #       i.e. How long to poll the OS Boot sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_os_boot_complete(self, i_timeout=10):
        l_timeout = time.time() + 60*i_timeout
        l_cmd = 'sdr elist |grep \'OS Boot\''
        while True:
            l_output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)
            if BMC_CONST.OS_BOOT_COMPLETE in l_output:
                print "Host OS is booted"
                break
            if time.time() > l_timeout:
                l_msg = "IPL timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function dumps the sel log and looks for specific hostboot error
    #        log string
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_sel_check(self,i_string):

        selDesc = 'Transition to Non-recoverable'
        logFile = self.cv_ffdcDir + '/' + 'host_sol.log'
        output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'sel elist')

        with open('%s' % logFile, 'w') as f:
            for line in output:
                f.write(line)

        if i_string in output:
            l_msg = 'Error log(s) detected during IPL. Please see %s' % logFile
            print l_msg
            raise OpTestError(l_msg)
        else:
            return BMC_CONST.FW_SUCCESS


    ##
    # @brief Determines the power status of the bmc
    #
    # @return l_output @type string: Power status of bmc
    #         "Chassis Power is on" or "Chassis Power is off"
    #
    def ipmi_power_status(self):
        l_output = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + 'chassis power status')
        if('on' in l_output):
            return BMC_CONST.CHASSIS_POWER_ON
        elif('off' in l_output):
            return BMC_CONST.CHASSIS_POWER_OFF
        else:
            raise OpTestError("Can't recognize chassis power status: " + str(l_output))

    ##
    # @brief Performs a cold reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_cold_reset(self):

        l_initstatus = self.ipmi_power_status()
        print ("Applying Cold reset.")
        rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_COLD_RESET)
        if BMC_CONST.BMC_PASS_COLD_RESET in rc:
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            self.util.PingFunc(self.cv_bmcIP, BMC_CONST.PING_RETRY_FOR_STABILITY)
            l_finalstatus = self.ipmi_power_status()
            if (l_initstatus != l_finalstatus):
                print('initial status ' + str(l_initstatus))
                print('final status ' + str(l_finalstatus))
                print ('Power status changed during cold reset')
                raise OpTestError('Power status changed')
            return BMC_CONST.FW_SUCCESS
        else:
            print "Cold reset failed"
            print rc
            raise OpTestError(rc)


    ##
    # @brief Performs a warm reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_warm_reset(self):

        l_cmd = BMC_CONST.BMC_WARM_RESET
        print ("Applying Warm reset. Wait for "
                            + str(BMC_CONST.BMC_WARM_RESET_DELAY) + "sec")
        rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)
        if BMC_CONST.BMC_PASS_WARM_RESET in rc:
            print rc
            time.sleep(BMC_CONST.BMC_WARM_RESET_DELAY)
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Warm reset Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief Preserves the network setting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_preserve_network_setting(self):

        print ("Protecting BMC network setting")
        l_cmd =  BMC_CONST.BMC_PRESRV_LAN
        rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)

        if BMC_CONST.BMC_ERROR_LAN in rc:
            l_msg = "Can't protect setting! Please preserve setting manually"
            print l_msg
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Flashes image using ipmitool
    #
    # @param i_image @type string: hpm file including location
    # @param i_imagecomponent @type string: component to be
    #        update from the hpm file BMC_CONST.BMC_FW_IMAGE_UPDATE
    #        or BMC_CONST.BMC_PNOR_IMAGE
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_code_update(self, i_image, i_imagecomponent):

        self.ipmi_cold_reset()
        l_cmd = BMC_CONST.BMC_HPM_UPDATE + i_image + " " + i_imagecomponent
        self.ipmi_preserve_network_setting()
        try:
            rc = self._ipmitool_cmd_run("echo y | " + self.cv_baseIpmiCmd + l_cmd)
            print rc
            self.ipmi_cold_reset()

        except subprocess.CalledProcessError:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

        if(rc.__contains__("Firmware upgrade procedure successful")):
            self.clear_ssh_keys(self.cv_bmcIP)
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Get information on active sides for both BMC and PNOR
    # example 0x0080 indicates primary side is activated
    #         0x0180 indicates golden side is activated
    #
    # @return returns the active sides for BMC and PNOR chip (that are either primary of golden)
    #         l_bmc_side, l_pnor_side or raise OpTestError
    #
    def ipmi_get_side_activated(self):

        l_result = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_ACTIVE_SIDE).strip().split('\n')

        for i in range(len(l_result)):
            if('BIOS' in l_result[i]):
                if(l_result[i].__contains__(BMC_CONST.PRIMARY_SIDE)):
                    print("Primary side of PNOR is active")
                    l_pnor_side = BMC_CONST.PRIMARY_SIDE
                elif(BMC_CONST.GOLDEN_SIDE in l_result[i]):
                    print ("Golden side of PNOR is active")
                    l_pnor_side = BMC_CONST.GOLDEN_SIDE
                else:
                    l_msg = "Error determining active side: " + l_result
                    print l_msg
                    raise OpTestError(l_msg)
            elif('BMC' in l_result[i]):
                if(l_result[i].__contains__(BMC_CONST.PRIMARY_SIDE)):
                    print("Primary side of BMC is active")
                    l_bmc_side = BMC_CONST.PRIMARY_SIDE
                elif(BMC_CONST.GOLDEN_SIDE in l_result[i]):
                    print ("Golden side of BMC is active")
                    l_bmc_side = BMC_CONST.GOLDEN_SIDE
                else:
                    l_msg = "Error determining active side: " + l_result
                    print l_msg
                    raise OpTestError(l_msg)
            else:
                l_msg = "Error determining active side: " + + l_result
                print l_msg
                raise OpTestError(l_msg)

        return l_bmc_side, l_pnor_side

    ##
    # @brief Get PNOR level
    #
    # @return pnor level of the bmc
    #         or raise OpTestError
    #
    def ipmi_get_PNOR_level(self):
        l_rc =  self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                       BMC_CONST.BMC_MCHBLD)
        return l_rc

    ##
    # @brief set power limit of bmc
    #
    # @param i_powerlimit @type int: power limit to be set at BMC
    #
    # @return raise OpTestError when fails
    #
    def ipmi_set_power_limit(self, i_powerlimit):

        l_rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                      BMC_CONST.SET_POWER_LIMIT + i_powerlimit)
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if(i_powerlimit not in l_rc):
            raise OpTestError(l_rc)


    ##
    # @brief Determines the power limit on the bmc
    #
    # @return l_powerlimit @type int: current power limit on bmc
    #         or raise OpTestError
    #
    def ipmi_get_power_limit(self):

        l_powerlimit = self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                              BMC_CONST.GET_POWER_LIMIT)
        return l_powerlimit

    ##
    # @brief Activates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_activate_power_limit(self):

        l_rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                      BMC_CONST.DCMI_POWER_ACTIVATE)
        if(BMC_CONST.POWER_ACTIVATE_SUCCESS in l_rc):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power limit activation failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief Deactivates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_deactivate_power_limit(self):

        l_rc = self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                      BMC_CONST.DCMI_POWER_DEACTIVATE)
        if(BMC_CONST.POWER_DEACTIVATE_SUCCESS in l_rc):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power limit deactivation failed. " \
                    "Make sure a power limit is set before activating it"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief Enable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_enable_all_occ_sensor(self):

        l_status = self.ipmi_get_occ_status()
        # example ssample: OCC Active | 08h | ok  | 210.0 |)

        # Get sensor ids to enable all OCCs
        l_status = l_status.rsplit("\n", 1)[0].split("\n")
        for i in range(len(l_status)):
            l_sensor_id = l_status[i].split("|")[1].strip()[:2]
            self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_OCC_SENSOR +
                                   l_sensor_id + BMC_CONST.BMC_ENABLE_OCC)

        # Wait for OCC to stabilize
        time.sleep(BMC_CONST.OCC_ENABLE_WAIT)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Disable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_disable_all_occ_sensor(self):

        l_status = self.ipmi_get_occ_status()

        # Get sensor ids to disable all OCCs
        l_status = l_status.rsplit("\n", 1)[0].split("\n")
        for i in range(len(l_status)):
            l_sensor_id = l_status[i].split("|")[1].strip()[:2]
            self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_OCC_SENSOR +
                                   l_sensor_id + BMC_CONST.BMC_DISABLE_OCC)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Get OCC status
    #  (example:
    #   OCC 1 Active     | 08h | ok  | 210.0 | Device Enabled
    #   OCC 2 Active     | 09h | ok  | 210.1 | Device Enabled)
    #
    # @return OCC sensor status or raise OpTestError
    #
    def ipmi_get_occ_status(self):
        l_result = self._ipmitool_cmd_run(self.cv_baseIpmiCmd +
                                          BMC_CONST.OP_CHECK_OCC)
        if ("Device" not in l_result):
            l_msg = "Can't recognize output"
            print(l_msg + ": " + l_result)
            raise OpTestError(l_msg)

        return l_result

    ##
    # @brief This function gets the sel log
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_get_sel_list(self):
        return self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_SEL_LIST)

    ##
    # @brief This function gets the sdr list
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_get_sdr_list(self):
        return self._ipmitool_cmd_run(self.cv_baseIpmiCmd + BMC_CONST.BMC_SDR_ELIST)


    ##
    # @brief Sets BIOS sensor and BOOT count to boot pnor from the primary side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_pnor_primary_side(self, i_bios_sensor, i_boot_sensor):

        print '\nSetting PNOR to boot into Primary Side'

        #Set the Boot Count sensor to 2
        l_cmd = BMC_CONST.BMC_BOOT_COUNT_2.replace('xx', i_boot_sensor)
        self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)

        #Set the BIOS Golden Side sensor to 0
        l_cmd = BMC_CONST.BMC_BIOS_GOLDEN_SENSOR_TO_PRIMARY.replace('xx', i_bios_sensor)
        self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Sets BIOS sensor and BOOT count to boot pnor from the golden side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_pnor_golden_side(self, i_bios_sensor, i_boot_sensor):

        print '\nSetting PNOR to boot into Golden Side'

        #Set the Boot Count sensor to 2
        l_cmd = BMC_CONST.BMC_BOOT_COUNT_2.replace('xx', i_boot_sensor)
        self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)

        #Set the BIOS Golden Side sensor to 1
        l_cmd = BMC_CONST.BMC_BIOS_GOLDEN_SENSOR_TO_GOLDEN.replace('xx', i_bios_sensor)
        self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Sets auto-reboot policy with given policy(i_policy)
    #
    # @param i_policy @type string: type of policy to be set(chassis policy <i_policy>)
    #                               always-off
    #                               always-on
    #                               previous
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_power_policy(self, i_policy):
        print "IPMI: Setting the power policy to %s" % i_policy
        l_cmd = "chassis policy %s" % i_policy
        l_res = self._ipmitool_cmd_run(self.cv_baseIpmiCmd + l_cmd)
        print l_res

    ##
    # @brief Clears the SSH keys from the known host file
    #
    # @param i_hostname @type string: name of the host to be removed from known host file
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError if failed
    #
    def clear_ssh_keys(self, i_hostname):
        self._ipmitool_cmd_run(BMC_CONST.CLEAR_SSH_KEYS + i_hostname)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will deactivates ipmi sol console
    #
    # @return l_con @type Object: it is a object of pexpect.spawn class or raise OpTestError
    #
    def ipmi_sol_deactivate(self):
        print "running:%s sol deactivate" % self.cv_baseIpmiCmd
        try:
            l_con = pexpect.spawn('%s sol deactivate' % self.cv_baseIpmiCmd)
        except pexpect.ExceptionPexpect:
            l_msg = "IPMI: sol deactivate failed"
            raise OpTestError(l_msg)
        return l_con

    ##
    # @brief This function will activates ipmi sol console
    #
    # @return l_con @type Object: it is a object of pexpect.spawn class or raise OpTestError
    #
    def ipmi_sol_activate(self):
        print  "running:%s sol activate" % self.cv_baseIpmiCmd
        try:
            l_con = pexpect.spawn('%s sol activate' % self.cv_baseIpmiCmd)
        except pexpect.ExceptionPexpect:
            l_msg = "IPMI: sol activate failed"
            raise OpTestError(l_msg)
        return l_con

    ##
    # @brief This function waits for getting ipmi sol console activated.
    #
    # @return l_con @type Object: it is a object of pexpect.spawn class
    #         or raise OpTestError in case of not connecting up to 10mins.
    #
    def ipmi_get_console(self):
        self.ipmi_sol_deactivate()
        # Waiting for a small time interval as latter versions of ipmi takes a bit of time to deactivate.
        time.sleep(BMC_CONST.IPMI_SOL_DEACTIVATE_TIME)
        l_con = self.ipmi_sol_activate()
        time.sleep(BMC_CONST.IPMI_SOL_ACTIVATE_TIME)
        count = 0
        while (not l_con.isalive()):
            l_con = self.ipmi_sol_activate()
            time.sleep(BMC_CONST.IPMI_SOL_ACTIVATE_TIME)
            count += 1
            if count > 120:
                l_msg = "IPMI: not able to get sol console"
                raise OpTestError(l_msg)
        l_con.logfile = sys.stdout
        l_con.delaybeforesend = BMC_CONST.IPMI_CON_DELAY_BEFORE_SEND
        return l_con

    ##
    # @brief This function make sure, ipmi console is activated and then login to the lpar
    # if host is already up.
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #        and this is the console object used for ipmi sol console access and for lpar login.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_lpar_login(self, i_con):
        l_con = i_con
        l_host = self.lpar_ip
        l_user = self.lpar_user
        l_pwd = self.lpar_passwd
        l_rc = l_con.expect_exact(BMC_CONST.IPMI_SOL_CONSOLE_ACTIVATE_OUTPUT, timeout=120)
        if l_rc == 0:
            print "IPMI: sol console activated"
        else:
            l_msg = "Error: not able to get IPMI console"
            raise OpTestError(l_msg)

        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        l_con.send("\r")
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        l_rc = l_con.expect_exact(BMC_CONST.IPMI_CONSOLE_EXPECT_ENTER_OUTPUT, timeout=120)
        if l_rc == BMC_CONST.IPMI_CONSOLE_EXPECT_LOGIN:
            l_con.sendline(l_user)
            l_rc = l_con.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            if l_rc == BMC_CONST.IPMI_CONSOLE_EXPECT_PASSWORD:
                l_con.sendline(l_pwd)
            else:
                l_msg = "Error: lpar login failed"
                raise OpTestError(l_msg)
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_PETITBOOT:
            l_msg = "Error: system is at petitboot"
            raise OpTestError(l_msg)
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_RANDOM_STATE:
            l_msg = "Error: system is in random state"
            raise OpTestError(l_msg)
        else:
            l_con.expect(pexpect.TIMEOUT, timeout=30)
            print l_con.before
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will used for setting the shell prompt to [pexpect]#, so that it can be used for
    #        running lpar os commands. Each time we can expect for this string [pexpect]#
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_lpar_set_unique_prompt(self, i_con):
        self.l_con = i_con
        self.l_con.sendline(BMC_CONST.IPMI_LPAR_UNIQUE_PROMPT)
        l_rc = self.l_con.expect_exact(BMC_CONST.IPMI_LPAR_EXPECT_PEXPECT_PROMPT)
        if l_rc == 0:
            print "Shell prompt changed"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Failed during change of shell prompt"
            raise OpTestError(l_msg)

    ##
    # @brief This function will be used for running lpar OS commands through ipmi console and for monitoring ipmi
    #        console for any system boots and kernel panic's etc. This function will be helpfull when ssh to host or
    #        network is down. This function should be followed by below functions inorder to work properly.
    #        sys_get_ipmi_console()--> For getting ipmi console
    #        ipmi_lpar_login()---> For login to lpar
    #        ipmi_lpar_set_unique_prompt()--> For setting the unique shell prompt [pexpect]#
    #        run_lpar_cmd_on_ipmi_console()--> Run the lpar commands and for monitoring ipmi console
    #
    # @param i_cmd @type string: lpar linux command
    #
    # @return res @type list: command output-if successfull,
    #                         monitor and returns console output(up to 8 mins)- if fails or raise OpTestError
    #
    def run_lpar_cmd_on_ipmi_console(self, i_cmd):
        self.l_con.sendline(i_cmd)
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        try:
            rc = self.l_con.expect(BMC_CONST.IPMI_LPAR_EXPECT_PEXPECT_PROMPT_LIST, timeout=500)
            if rc == 0:
                res = self.l_con.before
                res = res.splitlines()
                return res
            else:
                res = self.l_con.before
                res = res.split(i_cmd)
                return res[-1].splitlines()
        except pexpect.ExceptionPexpect, e:
            l_msg =  "lpar command execution on ipmi sol console failed"
            print str(e)
            raise OpTestError(l_msg)

    ##
    # @brief This function will closes ipmi sol console
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_close_console(self, i_con):
        l_con = i_con
        try:
            l_con.send('~.')
            time.sleep(BMC_CONST.IPMI_WAIT_FOR_TERMINATING_SESSION)
            l_con.close()
        except pexpect.ExceptionPexpect:
            l_msg = "IPMI: failed to close ipmi console"
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS
