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
#from subprocess import check_output

class OpTestIPMI():


    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPwd, i_ffdcDir=None):
        self.cv_bmcIP = i_bmcIP
        self.cv_bmcUser = i_bmcUser
        self.cv_bmcPwd = i_bmcPwd
        self.cv_ffdcDir = i_ffdcDir

    def _ipmitool_cmd_run(self, command, background=False):
        """ Runs an ipmitool command.

        The command argument is the last ipmitool command argument, for example:
        'chassis power cycle' or 'sdr elist'.  You can append other shell commands
        to the string, for instance 'sdr elist|grep Host'.
        Use backround=1, to spawn the child process and return the popen object,
        rather than waiting for the command completion and returning only the
        output.

        :param command: The ipmitool command, for example: chassis power on
        :type command: str.
        :param background: Spawn the command in as a background process. This is
            useful to monitor sensors or other runtime info. With background=False
            the function will block until the command finishes.
        :type background: bool.
        :returns: When background=1 it returns the subprocess child object. When
            background is not present in the args, the it returns the output of the
            command.
        :raises: subprocess exceptions

        """
        cmd1 = 'ipmitool -H %s -I lanplus -U %s -P %s ' % (self.cv_bmcIP, \
               self.cv_bmcUser, self.cv_bmcPwd)
        cmd = cmd1 + command
        print cmd
        if background:
            child = subprocess.Popen(cmd, shell=True)
            return child
        else:
            # TODO - need python 2.7
            # output = check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            cmd = subprocess.Popen(cmd,stderr=subprocess.STDOUT,
                                   stdout=subprocess.PIPE,shell=True)
            output = cmd.communicate()[0]
            #print "OUTPUT: " + output
            return output


    def ipmi_sdr_clear(self):
        """This function clears the sensor data

        :returns: int -- 0: success, 1: error
        """
        output = self._ipmitool_cmd_run('sel clear')
        if 'Clearing SEL' in output:
            time.sleep(3)
            output = self._ipmitool_cmd_run('sel elist')
            if 'no entries' in output:
                return 0
            else:
                return 1


    def ipmi_power_off(self):
        """This function sends the chassis power off ipmitool command.

        :returns: int -- 0: success, 1: error
        """
        output = self._ipmitool_cmd_run('chassis power off')
        if 'Down/Off' in output:
            return 0
        else:
            return 1


    def ipmi_power_on(self):
        """This function sends the chassis power on ipmitool command.

        :returns: int -- 0: success, 1: error
        """
        output = self._ipmitool_cmd_run('chassis power on')
        if 'Up/On' in output:
            return 0
        else:
            return 1


    def _ipmi_sol_capture(self):
        """Spawns the sol logger expect script as a background process. In order to
        properly kill the process the caller should call the ipmitool sol
        deactivate command, i.e.: ipmitool_cmd_run('sol deactivate'). The sol.log
        file file is placed in the FFDC directory.

        :returns: subprocess child object
        """
        try:
            self._ipmitool_cmd_run('sol deactivate')
        except subprocess.CalledProcessError:
            print 'SOL already deactivated'
        time.sleep(2)
        logFile = self.cv_ffdcDir + '/' + 'host_sol.log'
        cmd = os.getcwd() + '/../common/sol_logger.exp %s %s %s %s' % (
            self.cv_bmcIP,
            self.cv_bmcUser,
            self.cv_bmcPwd,
            logFile)
        print cmd
        solChild = subprocess.Popen(cmd, shell=True)
        return solChild


    def ipl_wait_for_working_state(self, timeout=10):
        """This function starts the sol capture and waits for the IPL to end. The
        marker for IPL completion is the Host Status sensor which reflects the ACPI
        power state of the system.  When it reads S0/G0: working it means that the
        petitboot is has began loading.  The overall timeout for the IPL is defined
        in the test configuration options.

        :param timeout: The number of minutes to wait for IPL to complete, i.e. How
            long to poll the ACPI sensor for working state before giving up.
        :type timeout: int.
        :returns: int -- 0: success, 1: error
        """

        ''' WORKAROUND FOR AMI BUG
         A sleep is required here because Host status sensor is set incorrectly
         to working state right after power on '''
        sol = self._ipmi_sol_capture()
        time.sleep(60)

        timeout = time.time() + 60*timeout

        ''' WORKAROUND FOR AMI BUG
         After updating the AMI level the Host Status sensor no longer works
         as expected.  To workaround this we use the OCC Active sensor instead.
         When OCC Active is in Device Enabled state we consider this working
         state.'''
    #    cmd = 'sdr elist |grep \'Host Status\''
        cmd = 'sdr elist |grep \'OCC Active\''
        while True:
            output = self._ipmitool_cmd_run(cmd)
            #if 'S0/G0: working' in output:
            if 'Device Enabled' in output:
                print "Host Status is S0/G0: working, IPL finished"
                break
            if time.time() > timeout:
                print "IPL timeout"
                return 1
            time.sleep(5)

        try:
            self._ipmitool_cmd_run('sol deactivate')
        except subprocess.CalledProcessError:
            print 'SOL already deactivated'
            return 1

        return 0


    def ipmi_sel_check(self,i_string):
        """This function dumps the sel log and looks for specific hostboot error
        log string.

        :returns: int -- 0: success, 1: error
        """
        selDesc = 'Transition to Non-recoverable'
        logFile = self.cv_ffdcDir + '/' + 'sel.log'
        output = self._ipmitool_cmd_run('sel elist')

        with open('%s' % logFile, 'w') as f:
            for line in output:
                f.write(line)

        if i_string in output:
            print 'Error log(s) detected during IPL. Please see %s' % logFile
            return 1
        else:
            return 0
