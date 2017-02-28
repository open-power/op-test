#!/usr/bin/python
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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

import sys
import time
import pexpect
try:
    import pxssh
except ImportError:
    from pexpect import pxssh

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class HostConsole():
    def __init__(self, host, username, password, port=22):
        self.state = ConsoleState.DISCONNECTED
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def terminate(self):
        if self.state == ConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

    def close(self):
        if self.state == ConsoleState.DISCONNECTED:
            return
        try:
            self.sol.send("\r")
            self.sol.send('~.')
            self.sol.expect(pexpect.EOF)
            self.sol.close()
        except pexpect.ExceptionPexpect:
            raise "HostConsole: failed to close OpenBMC host console"
        self.sol.terminate()
        self.state = ConsoleState.DISCONNECTED

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

        print "#OpenBMC Console CONNECT"

        cmd = ("sshpass -p %s " % (self.password)
               + " ssh -q"
               + " -o'RSAAuthentication=no' -o 'PubkeyAuthentication=no'"
               + " -o 'StrictHostKeyChecking=no'"
               + " -o 'UserKnownHostsFile=/dev/null' "
               + " -p %s" % str(self.port)
               + " -l %s %s" % (self.username, self.host)
           )
        print cmd
        solChild = pexpect.spawn(cmd,logfile=sys.stdout)
        self.state = ConsoleState.CONNECTED
        self.sol = solChild
        return solChild

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.sol.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(1)
            self.connect()
            count += 1
            if count > 120:
                raise "IPMI: not able to get sol console"

        return self.sol

    def run_command(self, command, timeout=60):
        console = self.get_console()
        console.sendline(command)
        console.expect("\n") # from us
        rc = console.expect_exact("[console-pexpect]#", timeout)

        if rc == 0:
            res = console.before
            res = res.splitlines()
            return res
        else:
            res = console.before
            res = res.split(i_cmd)
            return res[-1].splitlines()


class OpTestOpenBMC():
    def __init__(self, ip=None, username=None, password=None):
        self.hostname = ip
        self.username = username
        self.password = password
        # We kind of hack our way into pxssh by setting original_prompt
        # to also be \n, which appears to fool it enough to allow us
        # continue.
        self.console = HostConsole(ip, username, password, port=2200)

    def bmc_host(self):
        return self.hostname

    def get_ipmi(self):
        return None

    def get_host_console(self):
        return self.console
