#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestLpar.py $
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

## @package OpTestLpar
#  Lpar package which contains all functions related to LPAR communication
#
#  This class encapsulates all function which deals with the Lpar
#  in OpenPower systems

import sys
import os
import string
import time
import random
import subprocess
import re
import telnetlib
import socket
import select
import pty
import pexpect

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestUtil import OpTestUtil

class OpTestLpar():

    ##
    # @brief Initialize this object
    #
    # @param i_lparip @type string: IP Address of the lpar
    # @param i_lparuser @type string: Userid to log into the lpar
    # @param i_lparpasswd @type string: Password of the userid to log into the lpar
    #
    def __init__(self, i_lparip, i_lparuser, i_lparpasswd):
        self.ip = i_lparip
        self.user = i_lparuser
        self.passwd = i_lparpasswd
        self.util = OpTestUtil()

    ##
    #   @brief This method executes the command(i_cmd) on the host using a ssh session
    #
    #   @param i_cmd: @type string: Command to be executed on host through a ssh session
    #   @return command output if command execution is successful else raises OpTestError
    #
    def _ssh_execute(self, i_cmd):

        l_host = self.ip
        l_user = self.user
        l_pwd = self.passwd

        l_output = ''
        ssh_ver = '-2'

        count = 0
        while(1):
            value = self.util.PingFunc(l_host)[0]
            if(count > 5):
                l_msg = "Partition not pinging after 2.5 min, hence quitting."
                print l_msg
                raise OpTestError(l_msg)
            if(value == BMC_CONST.PING_SUCCESS):
                l_msg = "Partition is pinging"
                print l_msg
                break
            elif(value == BMC_CONST.PING_FAILED):
                print ("Partition not pinging")
                time.sleep(10)
                count += 1
            else:
                l_msg = "Can't ping! Abort"
                print(l_msg)
                raise OpTestError(l_msg)

        # Flush everything out prior to forking
        sys.stdout.flush()

        # Connect the child controlling terminal to a pseudo-terminal
        try:
            pid, fd = pty.fork()
        except OSError as e:
                # Explicit chain of errors
            l_msg = "Got OSError attempting to fork a pty session for ssh."
            raise OpTestError(l_msg)

        if pid == 0:
            # In child process.  Issue attempt ssh connection to remote host

            arglist = ('/usr/bin/ssh -o StrictHostKeyChecking=no',
                       l_host, ssh_ver, '-k', '-l', l_user, i_cmd)

            try:
                os.execv('/usr/bin/ssh', arglist)
            except Exception as e:
                # Explicit chain of errors
                l_msg = "Can not spawn os.execv for ssh."
                print l_msg
                raise OpTestError(l_msg)

        else:
            # In parent process
            # Polling child process for output
            poll = select.poll()
            poll.register(fd, select.POLLIN)

            start_time = time.time()
            # time.sleep(1)
            while True:
                try:
                    evt = poll.poll()
                    x = os.read(fd, 1024)
                    #print "ssh x= " + x
                    end_time = time.time()
                    if(end_time - start_time > 1500):
                        if(i_cmd.__contains__('updlic') or i_cmd.__contains__('update_flash')):
                            continue
                        else:
                            l_msg = "Timeout occured/SSH request " \
                                    "un-responded even after 25 minutes"
                            print l_msg
                            raise OpTestError(l_msg)

                    if(x.__contains__('(yes/no)')):
                        l_res = "yes\r\n"
                        os.write(fd, l_res)
                    if(x.__contains__('s password:')):
                        x = ''
                        os.write(fd, l_pwd + '\r\n')
                    if(x.__contains__('Password:')):
                        x = ''
                        os.write(fd, l_pwd + '\r\n')
                    if(x.__contains__('password')):
                        response = l_pwd + "\r\n"
                        os.write(fd, response)
                    if(x.__contains__('yes')):
                        response = '1' + "\r\n"
                        os.write(fd, response)
                    if(x.__contains__('Connection refused')):
                        print x
                        raise OpTestError(x)
                    if(x.__contains__('Received disconnect from')):
                        self.ssh_ver = '-1'
                    if(x.__contains__('Connection closed by')):
                        print (x)
                        raise OpTestError(x)
                    if(x.__contains__("WARNING: POSSIBLE DNS SPOOFING DETECTED")):
                        print (x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED")):
                        print (x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("Permission denied")):
                        l_msg = "Wrong Login or Password(" + l_user + "/" + l_pwd + ") :" + x
                        print (l_msg)
                        raise OpTestError(l_msg)
                    if(x.__contains__("Rebooting") or \
                       (x.__contains__("rebooting the system"))):
                        l_output = l_output + x
                        raise OpTestError(l_output)
                    if(x.__contains__("Connection timed out")):
                        l_msg = "Connection timed out/" + \
                            l_host + " is not pingable"
                        print (x)
                        raise OpTestError(l_msg)
                    if(x.__contains__("could not connect to CLI daemon")):
                        print(x)
                        raise OpTestError("Director server is not up/running("
                                          "Do smstop then smstart to restart)")
                    if((x.__contains__("Error:")) and (i_cmd.__contains__('rmsys'))):
                        print(x)
                        raise OpTestError("Error removing:" + l_host)
                    if((x.__contains__("Bad owner or permissions on /root/.ssh/config"))):
                        print(x)
                        raise OpTestError("Bad owner or permissions on /root/.ssh/config,"
                                          "Try 'chmod -R 600 /root/.ssh' & retry operation")

                    l_output = l_output + x
                    # time.sleep(1)
                except OSError:
                    break
        if l_output.__contains__("Name or service not known"):
            reason = 'SSH Failed for :' + l_host + \
                "\n Please provide a valid Hostname"
            print reason
            raise OpTestError(reason)

        # Gather child process status to freeup zombie and
        # Close child file descriptor before return
        if (fd):
            os.waitpid(pid, 0)
            os.close(fd)
        return l_output

    ##
    # @brief Get and Record Ubunto OS level
    #
    # @return l_oslevel @type string: OS level of the partition provided
    #         or raise OpTestError
    #
    def lpar_get_OS_Level(self):

        l_oslevel = self._ssh_execute(BMC_CONST.BMC_GET_OS_RELEASE)
        print l_oslevel
        return l_oslevel


    ##
    # @brief Executes a command on the os of the bmc to protect network setting
    #
    # @return OpTestError if failed
    #
    def lpar_protect_network_setting(self):
        try:
            l_rc = self._ssh_execute(BMC_CONST.OS_PRESERVE_NETWORK)
        except:
            l_errmsg = "Can't preserve network setting"
            print l_errmsg
            raise OpTestError(l_errmsg)

    ##
    # @brief Performs a cold reset onto the lpar
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def lpar_cold_reset(self):
        # TODO: cold reset command to os is not too stable
        l_cmd = BMC_CONST.LPAR_COLD_RESET
        print ("Applying Cold reset. Wait for "
                            + str(BMC_CONST.BMC_COLD_RESET_DELAY) + "sec")
        l_rc = self._ssh_execute(l_cmd)
        if BMC_CONST.BMC_PASS_COLD_RESET in l_rc:
            print l_rc
            time.sleep(BMC_CONST.BMC_COLD_RESET_DELAY)
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Cold reset Failed"
            print l_msg
            raise OpTestError(l_msg)

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
    def lpar_code_update(self, i_image, imagecomponent):

        # Copy the hpm file to the tmp folder in the partition
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying hpm file to lpar failed"
            print l_msg
            raise OpTestError(l_msg)

        #self.lpar_protect_network_setting() #writing to partition is not stable
        l_cmd = "\necho y | ipmitool -I usb " + BMC_CONST.BMC_HPM_UPDATE + "/tmp/" \
                + i_image.rsplit("/", 1)[-1] + imagecomponent
        print l_cmd
        try:
            l_rc = self._ssh_execute(l_cmd)
            print l_rc
        except subprocess.CalledProcessError:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

        if(l_rc.__contains__("Firmware upgrade procedure successful")):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)
