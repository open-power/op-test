#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestUtil.py $
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

import sys
import os
import string
import subprocess
import random
import re
import telnetlib
import socket
import select
import time
import pty
import pexpect

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError

class OpTestUtil():


    def __init__(self):
        pass

    ##
    # @brief Pings 2 packages to system under test
    #
    # @param i_ip @type string: ip address of system under test
    # @param i_try @type int: number of times the system is
    #        pinged before returning Failed
    #
    # @return   BMC_CONST.PING_SUCCESS when PASSED or
    #           raise OpTestError when FAILED
    #
    def PingFunc(self, i_ip, i_try=1):

        arglist = "ping -c 2 " + str(i_ip)
        while(i_try != 0):

            try:
                p1 = subprocess.Popen(
                    arglist, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                stdout_value, stderr_value = p1.communicate()
            except:
                l_msg = "Ping Test Failed."
                print l_msg
                raise OpTestError(l_msg)

            if(stdout_value.__contains__("2 received")):
                print (i_ip + " is pinging")
                return BMC_CONST.PING_SUCCESS

            else:
                print (i_ip + " is not pinging")
                i_try -= 1
                time.sleep(BMC_CONST.LPAR_BRINGUP_TIME)

        print stderr_value
        raise OpTestError(stderr_value)


    ##
    #   @brief    This method does a scp from local system (where files are found)
    #             to destination(Path where files will be stored) or
    #             scp to local system(where files will be stored) from
    #             destination(where files are found).
    #   @param    hostfile
    #   @param    destid
    #   @param    destName
    #   @param    destPath
    #   @param    passwd
    #   @param    ssh_ver
    #   @param    i_function @type int: SCP_TO_REMOTE = 1(scp to remote system(default))
    #                                   SCP_TO_LOCAL = 2 (scp to local system)
    #   @return   output from terminal
    #   @throw    subprocess or OpTestError
    #
    def copyFilesToDest(
            self,
            hostfile,
            destid,
            destName,
            destPath,
            passwd,
            ssh_ver="2",
            i_function=1):
        pid, fd = pty.fork()
        Password = passwd + "\r\n"
        list = ''
        destinationPath = destid.strip() + "@" + destName.strip() + \
            ":" + destPath

        # We've spawned a separate process with the .fork above so one process
        # will execute the scp command, and the other process will handle the
        # back and forth of the password and the error paths
        if pid == 0:
            if i_function == 1:
                arglist = (
                    "/usr/bin/scp",
                    "-o AfsTokenPassing=no",
                    "-" +
                    ssh_ver.strip(),
                    hostfile,
                    destinationPath)
            elif i_function == 2:
                arglist = (
                    "/usr/bin/scp",
                    "-" +
                    ssh_ver.strip(),
                    destinationPath,
                    hostfile)
            else:
                l_msg = "Please provide valid scp function"
                print l_msg
                raise OpTestError(l_msg)
            print(arglist)
            os.execv("/usr/bin/scp", arglist)
        else:
            while True:
                try:
                    x = os.read(fd, 1024)
                    print("x=" + x)
                    if(x.__contains__('(yes/no)')):
                        l_res = "yes\r\n"
                        os.write(fd, l_res)
                    if(x.__contains__('s password:')):
                        x = ''
                        print("Entered password")
                        pwd = Password
                        os.write(fd, pwd)
                    if(x.__contains__('Password:')):
                        x = ''
                        os.write(fd, Password)
                    if(x.__contains__('password')):
                        response = Password
                        os.write(fd, response)
                    if(x.__contains__('yes')):
                        response = '1' + "\r\n"
                        os.write(fd, response)
                    if(x.__contains__('100%')):
                        # We copied 100% of file so break out
                        break
                    if(x.__contains__("Invalid ssh2 packet type")):
                        print(x)
                        raise OpTestError(x)
                    if(x.__contains__("Protocol major versions differ: 1 vs. 2")):
                        print (x)
                        raise OpTestError(x)
                    if(x.__contains__("Connection refused")):
                        print (x)
                        raise OpTestError(x)
                    if(x.__contains__('Connection closed by')):
                        print (x)
                        raise OpTestError(x)
                    if(x.__contains__("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED")):
                        print (x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("WARNING: POSSIBLE DNS SPOOFING DETECTED")):
                        print(x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("Permission denied")):
                        print(x)
                        raise OpTestError("Wrong Login or Password :" + x)
                    list = list + x
                    time.sleep(1)
                except OSError as e:
                    print("OSError string: " + e.strerror)
                    raise OpTestError(e.strerror)

        if list.__contains__("Name or service not known"):
            reason = 'SSH Failed for :' + destid + \
                "\n Please provide a valid Hostname"
            print("scp command failed!")
            raise OpTestError(reason)

        print(list)
        return list
