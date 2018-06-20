#!/usr/bin/env python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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

import re
import sys
import time
import pexpect

from Exceptions import CommandFailed, SSHSessionDisconnected
import OpTestSystem
try:
    from common import OPexpect
except ImportError:
    import OPexpect

sudo_responses = ["not in the sudoers",
                  "incorrect password"]

class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

def set_system_to_UNKNOWN_BAD(system):
    s = system.get_state()
    system.set_state(OpTestSystem.OpSystemState.UNKNOWN_BAD)
    return s

class OpTestSSH():
    def __init__(self, host, username, password, logfile=sys.stdout, port=22,
            prompt=None, check_ssh_keys=False, known_hosts_file=None, use_default_bash=None):
        self.state = ConsoleState.DISCONNECTED
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.logfile = logfile
        self.prompt = prompt
        self.check_ssh_keys=check_ssh_keys
        self.known_hosts_file=known_hosts_file
        self.use_default_bash = use_default_bash
        self.system = None

    def set_system(self, system):
        self.system = system

    def terminate(self):
        if self.state == ConsoleState.CONNECTED:
            self.console.terminate()
            self.state = ConsoleState.DISCONNECTED

    def close(self):
        if self.state == ConsoleState.DISCONNECTED:
            return
        try:
            self.console.send("\r")
            self.console.send('~.')
            self.console.expect(pexpect.EOF)
            self.console.close()
        except pexpect.ExceptionPexpect:
            raise "SSH Console: failed to close ssh console"
        self.console.terminate()
        self.state = ConsoleState.DISCONNECTED

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            self.console.terminate()
            self.state = ConsoleState.DISCONNECTED

        cmd = ("sshpass -p %s " % (self.password)
               + " ssh"
               + " -p %s" % str(self.port)
               + " -l %s %s" % (self.username, self.host)
               + " -o PubkeyAuthentication=no -o afstokenpassing=no"
               )

        if not self.check_ssh_keys:
            cmd = (cmd
                    + " -q"
                    + " -o 'UserKnownHostsFile=/dev/null' "
                    + " -o 'StrictHostKeyChecking=no'"
                    )
        elif self.known_hosts_file:
            cmd = (cmd + " -o UserKnownHostsFile=" + self.known_hosts_file)

        print cmd
        consoleChild = OPexpect.spawn(cmd,
                failure_callback=set_system_to_UNKNOWN_BAD,
                failure_callback_data=self.system)
        self.state = ConsoleState.CONNECTED
        # set for bash, otherwise it takes the 24x80 default
        consoleChild.setwinsize(1000,1000)
        self.console = consoleChild
        # Users expecting "Host IPMI" will reference console.sol so make it available
        self.sol = self.console
        consoleChild.logfile_read = self.logfile
        self.set_unique_prompt(consoleChild)

        return consoleChild

    def set_unique_prompt(self, console):
        if self.port == 2200:
            return
        if self.use_default_bash:
            console.sendline("exec bash --norc --noprofile")

        expect_prompt = self.build_prompt() + "$"

        console.sendline('PS1=' + self.build_prompt())

        # Check for an early EOF - this can happen if we had a bad ssh host key
        # console.isalive() can still return True in this case if called
        # quickly enough.
        try:
            console.expect([expect_prompt], timeout=60)
            output = console.before
        except pexpect.EOF as cf:
            print cf
            if self.check_ssh_keys:
                raise SSHSessionDisconnected("SSH session exited early - bad host key?")
            else:
                raise SSHSessionDisconnected("SSH session exited early!")

    def build_prompt(self):
        if self.prompt:
          built_prompt = self.prompt
        else:
          built_prompt = "\[console-pexpect\]#"

        return built_prompt

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.console.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(1)
            self.connect()
            count += 1
            if count > 120:
                raise "SSH: not able to get console"

        return self.console

    def set_env(self, console):
        set_env_list = []
        if self.use_default_bash:
          console.sendline("exec bash --norc --noprofile")
        expect_prompt = self.build_prompt() + "$"
        console.sendline('PS1=' + self.build_prompt())
        console.expect(expect_prompt)
        combo_io = (console.before + console.after).lstrip()
        set_env_list += combo_io.splitlines()
        # remove the expect prompt since matched generic #
        del set_env_list[-1]
        return set_env_list

    def try_sendcontrol(self, console, command):
        res = console.before
        expect_prompt = self.build_prompt() + "$"
        console.sendcontrol('c')
        try_list = []
        rc = console.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], 10)
        if rc != 0:
          self.terminate()
          self.state = ConsoleState.DISCONNECTED
          raise CommandFailed(command, 'run_command TIMEOUT', -1)
        else:
          try_list = res.splitlines()
          echo_rc = 1
        return try_list, echo_rc

    def retry_password(self, console, command):
        retry_list_output = []
        a = 0
        while a < 3:
          a += 1
          console.sendline(self.password)
          rc = console.expect([".*#", "try again.", pexpect.TIMEOUT, pexpect.EOF])
          if (rc == 0) or (rc == 1):
            combo_io = console.before + console.after
            retry_list_output += combo_io.splitlines()
            matching = [xs for xs in sudo_responses if any(xs in xa for xa in console.after.splitlines())]
            if len(matching):
              echo_rc = 1
              rc = -1 # use to flag the failure next
          if rc == 0:
            retry_list_output += self.set_env(console)
            echo_rc = 0
            break
          elif a == 2:
            echo_rc = 1
            break
          elif (rc == 2):
            raise CommandFailed(command, 'Retry Password TIMEOUT ' + ''.join(retry_list_output), -1)
          elif (rc == 3):
            self.state = ConsoleState.DISCONNECTED
            raise SSHSessionDisconnected("SSH session exited early!")

        return retry_list_output, echo_rc

    def handle_password(self, console, command):
        # this is for run_command 'sudo -s' or the like
        handle_list_output = []
        failure_list_output = []
        pre_combo_io = console.before + console.after
        console.sendline(self.password)
        rc = console.expect([".*#", "try again.", pexpect.TIMEOUT, pexpect.EOF])
        if (rc == 0) or (rc == 1):
          combo_io = pre_combo_io + console.before + console.after
          handle_list_output += combo_io.splitlines()
          matching = [xs for xs in sudo_responses if any(xs in xa for xa in console.after.splitlines())]
          if len(matching):
            # remove the expect prompt since matched generic #
            del handle_list_output[-1]
            echo_rc = 1
            rc = -1 # use this to flag the failure next
        if rc == 0:
          # with unknown prompts and unknown environment unable to capture echo $?
          echo_rc = 0
          self.set_env(console)
          list_output = handle_list_output
        elif rc == 1:
          retry_list_output, echo_rc = self.retry_password(console, command)
          list_output = (handle_list_output + retry_list_output)
        else:
          if (rc == 2) or (rc == 3):
            failure_list_output += ['Password Problem/TIMEOUT ']
            failure_list_output += pre_combo_io.splitlines()
          # timeout path needs access to output
          # handle_list_output empty if timeout or EOF
          failure_list_output += handle_list_output
          if (rc == 3):
            self.state = ConsoleState.DISCONNECTED
            raise SSHSessionDisconnected("SSH session exited early!")
          else:
            raise CommandFailed(command, ''.join(failure_list_output), -1)
        return list_output, echo_rc

    def run_command(self, command, timeout=60):
        running_sudo_s = False
        extra_sudo_output = False
        console = self.get_console()
        expect_prompt = self.build_prompt() + "$"
        console.sendline(command)
        console.expect("\n") # removes the echo of command from output
        if command == 'sudo -s':
          running_sudo_s = True
          # special case to catch loss of env
          rc = console.expect([".*#", r"[Pp]assword", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        else:
          rc = console.expect([expect_prompt, r"[Pp]assword", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        output_list = []
        output_list += console.before.splitlines()
        # if we are running 'sudo -s' as root then catch on generic # prompt, restore env
        if running_sudo_s and (rc == 0):
          extra_sudo_output = True
          set_env_list = self.set_env(console)
        if rc == 0:
          if extra_sudo_output:
            output_list += set_env_list
          console.sendline("echo $?")
          rc2 = console.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
          if rc2 == 0:
            echo_output = console.before
            echo_rc = int(echo_output.splitlines()[-1])
          elif rc2 == 2:
            self.state = ConsoleState.DISCONNECTED
            raise SSHSessionDisconnected("SSH session exited!")
          else:
            raise CommandFailed(command, 'echo TIMEOUT', -1)
        elif rc == 1:
          handle_output_list, echo_rc = self.handle_password(console, command)
          # remove the expect prompt since matched generic #
          del handle_output_list[-1]
          output_list = handle_output_list
        elif rc == 2:
          output_list, echo_rc = self.try_sendcontrol(console, command)
        else:
          self.state = ConsoleState.DISCONNECTED
          raise SSHSessionDisconnected("SSH session exited early!")
        res = output_list
        if echo_rc != 0:
          raise CommandFailed(command, res, echo_rc)
        return res

    # This command just runs and returns the ouput & ignores the failure
    # A straight copy of what's in OpTestIPMI
    def run_command_ignore_fail(self, command, timeout=60):
        try:
            output = self.run_command(command, timeout)
        except CommandFailed as cf:
            output = cf.output
        return output
