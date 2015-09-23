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

from OpTestError import OpTestError

class OpTestConnection():


    def __init__(self, i_ip, i_user, i_passwd, i_Type, i_id):
        self.ip = i_ip
        self.user = i_user
        self.passwd = i_passwd
        self.OsType = i_Type
        self.id = i_id



    def PingFunc(self, ip):
        arglist = "ping -c 2 " + str(ip)
        try:
            p1 = subprocess.Popen(
                arglist, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout_value, stderr_value = p1.communicate()
        except:
            l_msg = "Ping Test Failed."
            print l_msg
            raise OpTestError(l_msg)

        if(stdout_value.__contains__("2 received")):
            return 2, stderr_value
        elif(stdout_value.__contains__("1 received")):
            return 1, stderr_value
        else:
            return 0, stderr_value


    ##
    #   @details   This method executes the command(cmd) on the host using a ssh session from linux box where test is executing.
    #   @param     cmd: @type string: Command that has to be executed on host through a ssh session
    #   @param     ispol: @type bool: True if host is HMC(selects version 1).False if host SDMC(selects version 2)
    #   @return    returns command output if command execution is successful else raises SshConnectionError
    #   @throw     OpTestError
    #
    def SshExecute(self, cmd, ispol=False):

        host = self.ip
        user = self.user
        pwd = self.passwd

        list = ''
        ssh_ver = '-2'

        count = 0
        while(1):
            value = self.PingFunc(host)[0]
            if(count > 5):
                l_msg = "Partition not pinging after 2.5 min, hence quitting."
                print l_msg
                raise OpTestError(l_msg)
            if(value == 2):
                l_msg = "Partition is pinging"
                print l_msg
                break
            elif(value == 1):
                print ("Partition started pinging")
            elif(value == 0):
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
                       host, ssh_ver, '-k', '-l', user, cmd)

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
                        if(cmd.__contains__('updlic') or cmd.__contains__('update_flash')):
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
                        os.write(fd, pwd + '\r\n')
                    if(x.__contains__('Password:')):
                        x = ''
                        os.write(fd, pwd + '\r\n')
                    if(x.__contains__('password')):
                        response = pwd + "\r\n"
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
                        l_msg = "Wrong Login or Password(" + user + "/" + pwd + ") :" + x
                        print (l_msg)
                        raise OpTestError(l_msg)
                    if(x.__contains__("Rebooting") or \
                       (x.__contains__("rebooting the system"))):
                        list = list + x
                        raise OpTestError(list)
                    if(x.__contains__("Connection timed out")):
                        l_msg = "Connection timed out/" + \
                            host + " is not pingable"
                        print (x)
                        raise OpTestError(l_msg)
                    if(x.__contains__("could not connect to CLI daemon")):
                        print(x)
                        raise OpTestError("Director server is not up/running("
                                          "Do smstop then smstart to restart)")
                    if((x.__contains__("Error:")) and (cmd.__contains__('rmsys'))):
                        print(x)
                        raise OpTestError("Error removing FSP from FSM:" + host)
                    if((x.__contains__("Bad owner or permissions on /root/.ssh/config"))):
                        print(x)
                        raise OpTestError("Bad owner or permissions on /root/.ssh/config,"
                                          "Try 'chmod -R 600 /root/.ssh' & retry operation")

                    list = list + x
                    # time.sleep(1)
                except OSError:
                    break
        if list.__contains__("Name or service not known"):
            reason = 'SSH Failed for :' + host + \
                "\n Please provide a valid Hostname"
            print reason
            raise OpTestError(reason)

        # Gather child process status to freeup zombie and
        # Close child file descriptor before return
        if (fd):
            os.waitpid(pid, 0)
            os.close(fd)
        return list




# Unit Test
if __name__ == '__main__':

    lpar = OpTestConnection("alp046p1.aus.stglabs.ibm.com", "root", "coolpw0rd" , "aix", "1" )

    cmd = "ls"
    l_res = lpar.SshExecute(cmd)
    print l_res
    print "Done"


