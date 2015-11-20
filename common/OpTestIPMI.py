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
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPwd, i_ffdcDir):

        self.cv_bmcIP = i_bmcIP
        self.cv_bmcUser = i_bmcUser
        self.cv_bmcPwd = i_bmcPwd
        self.cv_ffdcDir = i_ffdcDir
        self.cv_cmd = 'ipmitool -H %s -I lanplus -U %s -P %s ' \
                      % (self.cv_bmcIP, self.cv_bmcUser, self.cv_bmcPwd)
        self.util = OpTestUtil()


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
    # @brief This function clears the sensor data
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_sdr_clear(self):

        output = self._ipmitool_cmd_run(self.cv_cmd + 'sel clear')
        if 'Clearing SEL' in output:
            time.sleep(3)
            output = self._ipmitool_cmd_run(self.cv_cmd + 'sel elist')
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
        output = self._ipmitool_cmd_run(self.cv_cmd + 'chassis power off')
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
        output = self._ipmitool_cmd_run(self.cv_cmd + 'chassis power on')
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
        output = self._ipmitool_cmd_run(self.cv_cmd + 'chassis power soft')
        if "Chassis Power Control: Soft" in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Soft Failed"
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
            self._ipmitool_cmd_run(self.cv_cmd + 'sol deactivate')
        except OpTestError:
            print 'SOL already deactivated'
        time.sleep(2)
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
            output = self._ipmitool_cmd_run(self.cv_cmd + cmd)
            if 'S0/G0: working' in output:
                print "Host Status is S0/G0: working, IPL finished"
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)

        try:
            self._ipmitool_cmd_run(self.cv_cmd + 'sol deactivate')
        except subprocess.CalledProcessError:
            l_msg = 'SOL already deactivated'
            print l_msg
            raise OpTestError(l_msg)

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
        output = self._ipmitool_cmd_run(self.cv_cmd + 'sel elist')

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
    # @brief Performs a cold reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_cold_reset(self):

        l_cmd = BMC_CONST.BMC_COLD_RESET
        print ("Applying Cold reset. Wait for "
                            + str(BMC_CONST.BMC_COLD_RESET_DELAY) + "sec")
        rc = self._ipmitool_cmd_run(self.cv_cmd + l_cmd)
        if BMC_CONST.BMC_PASS_COLD_RESET in rc:
            print rc
            time.sleep(BMC_CONST.BMC_COLD_RESET_DELAY)
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Cold reset Failed"
            print l_msg
            raise OpTestError(l_msg)


    ##
    # @brief Performs a warm reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_warm_reset(self):

        l_cmd = BMC_CONST.BMC_WARM_RESET
        print ("Applying Warm reset. Wait for "
                            + str(BMC_CONST.BMC_WARM_RESET_DELAY) + "sec")
        rc = self._ipmitool_cmd_run(self.cv_cmd + l_cmd)
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
        rc = self._ipmitool_cmd_run(self.cv_cmd + l_cmd)

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
            rc = self._ipmitool_cmd_run("echo y | " + self.cv_cmd + l_cmd)
            print rc
            self.ipmi_cold_reset()

        except subprocess.CalledProcessError:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

        if(rc.__contains__("Firmware upgrade procedure successful")):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Verify Primary side activated for both BMC and PNOR
    # example 0x0080 indicates primary side is activated
    #         0x0180 indicates golden side is activated
    #
    # @return prints and returns BMC_CONST.PRIMARY_SIDE
    #         or BMC_CONST.GOLDEN_SIDE or raise OpTestError
    #
    def ipmi_get_side_activated(self):

        rc = self._ipmitool_cmd_run(self.cv_cmd + BMC_CONST.BMC_ACTIVE_SIDE)
        if(rc.__contains__(BMC_CONST.PRIMARY_SIDE)):
            print("Primary side is active")
            return BMC_CONST.PRIMARY_SIDE
        elif(BMC_CONST.GOLDEN_SIDE in rc):
            print ("Golden side is active")
            return BMC_CONST.GOLDEN_SIDE
        else:
            l_msg = "Error determining active side"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Get PNOR level
    #
    # @return pnor level of the bmc
    #         or raise OpTestError
    #
    def ipmi_get_PNOR_level(self):
        l_rc =  self._ipmitool_cmd_run(self.cv_cmd + BMC_CONST.BMC_MCHBLD)
        print l_rc
        return l_rc
