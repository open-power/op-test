#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestUtil.py $
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
import commands

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
    def PingFunc(self, i_ip, i_try=1, totalSleepTime=BMC_CONST.HOST_BRINGUP_TIME):
	sleepTime = 0;
        while(i_try != 0):
            p1 = subprocess.Popen(["ping", "-c 2", str(i_ip)],
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)
            stdout_value, stderr_value = p1.communicate()

            if(stdout_value.__contains__("2 received")):
                print (i_ip + " is pinging")
                return BMC_CONST.PING_SUCCESS

            else:
                print "%s is not pinging (Waited %d of %d, %d tries remaining)" % (i_ip, sleepTime, totalSleepTime, i_try)
		time.sleep(1)
		sleepTime += 1
		if (sleepTime == totalSleepTime):
			i_try -= 1
			sleepTime = 0

        print stderr_value
        raise OpTestError(stderr_value)


    def copyFilesToDest(self, hostfile, destid, destName, destPath, passwd):
        arglist = (
            "sshpass",
            "-p", passwd,
            "/usr/bin/scp",
            "-o","UserKnownHostsFile=/dev/null",
            "-o","StrictHostKeyChecking=no",
            hostfile,
            "{}@{}:{}".format(destid,destName,destPath))
        print(' '.join(arglist))
        subprocess.check_call(arglist)

    def copyFilesFromDest(self, destid, destName, destPath, passwd, sourcepath):
        arglist = (
            "sshpass",
            "-p", passwd,
            "/usr/bin/scp",
            "-r",
            "-o","UserKnownHostsFile=/dev/null",
            "-o","StrictHostKeyChecking=no",
            "{}@{}:{}".format(destid,destName,destPath),
            sourcepath)
        print(' '.join(arglist))
        subprocess.check_output(arglist)

    # It waits for a ping to fail, Ex: After a BMC/FSP reboot
    def ping_fail_check(self, i_ip):
        cmd = "ping -c 1 " + i_ip + " 1> /dev/null; echo $?"
        count = 0
        while count < 500:
            output = commands.getstatusoutput(cmd)
            if output[1] != '0':
                print "IP %s Comes down" % i_ip
                break
            count = count + 1
            time.sleep(2)
        else:
            print "IP %s keeps on pinging up" % i_ip
            return False
        return True
