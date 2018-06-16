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
#from OpTestHost import OpTestHost
from Exceptions import CommandFailed, RecoverFailed, ConsoleSettings
#from OpTestSSH import ConsoleState

sudo_responses = ["not in the sudoers",
                  "incorrect password"]

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

    def build_prompt(self, prompt=None):
        if prompt:
          built_prompt = prompt
        else:
          built_prompt = "\[console-expect\]#"

        return built_prompt

    def clear_state(self, track_obj):
          track_obj.PS1_set = 0
          track_obj.SUDO_set = 0
          track_obj.LOGIN_set = 0

    def try_recover(self, term_obj, counter=3):
        # callers beware that the connect can affect previous states and objects
        for i in range(counter):
          print "OpTestSystem detected something, working on recovery"
          my_term = term_obj.connect()
          my_term.sendcontrol('c')
          time.sleep(1)
          try_rc = my_term.expect([".*#", "Petitboot", "login: ", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if try_rc in [0,1,2]:
            print "OpTestSystem recovered from temporary issue, continuing"
            return
          else:
            print "OpTestSystem Unable to recover from temporary issue, calling close and continuing"
            term_obj.close()
        print "OpTestSystem Unable to recover to known state, raised Exception RecoverFailed but continuing"
        raise RecoverFailed(before=my_term.before, after=my_term.after, msg='Unable to recover to known state, retry')

    def try_sendcontrol(self, term_obj, command, counter=3):
        my_term = term_obj.get_console()
        res = my_term.before
        print "OpTestSystem detected something, working on recovery"
        my_term.sendcontrol('c')
        time.sleep(1)
        try_list = []
        rc = my_term.expect([".*#", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc != 0:
          term_obj.close()
          self.try_recover(term_obj, counter)
          # if we get back here we still fail but have a working prompt to give back
          print ("OpTestSystem recovered from temporary issue, but the command output is unavailable,"
                  " raised Exception CommandFailed but continuing")
          raise CommandFailed(command, "run_command TIMEOUT in try_sendcontrol, we recovered the prompt,"
                  " but the command output is unavailable", -1)
        else:
          # may have lost prompt
          print "OpTestSystem recovered from a temporary issue, continuing"
          try_list = res.splitlines() # give back what we do have for triage
          echo_rc = 1
        return try_list, echo_rc

    def set_PS1(self, term_obj, my_term, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        # on success caller is returned 1, otherwise exception thrown
        # order of execution and commands are sensitive here to provide reliability
        if term_obj.setup_term_disable == 1:
          return -1
        expect_prompt = prompt + "$"
        my_term.sendline("which bash && exec bash --norc --noprofile")
        time.sleep(0.2)
        my_term.sendline('PS1=' + prompt)
        time.sleep(0.2)
        my_term.sendline("which stty && stty cols 300;which stty && stty rows 30")
        time.sleep(0.2)
        my_term.sendline("export LANG=C")
        time.sleep(0.2)
        my_term.sendline() # needed to sync buffers later on
        time.sleep(0.2) # pause for first time setup, buffers you know, more sensitive in petitboot shell, pexpect or console buffer not sure
        rc = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          print "Shell prompt changed"
          return 1 # caller needs to save state
        else: # we don't seem to have anything so try to get something
          term_obj.close()
          try:
            # special case to allow calls back to connect which is where we probably came from
            self.orig_system_setup_term = term_obj.get_system_setup_term()
            self.orig_block_setup_term = term_obj.get_block_setup_term()
            term_obj.set_system_setup_term(1) # block so the new connect will not try to come back here
            term_obj.set_block_setup_term(1) # block so the new connect will not try to come back here
            self.try_recover(term_obj, counter=3) # if try_recover bails we leave things blocked, they'll get reset
            # if we get back here we have a new prompt and unknown console
            # in future if state can change or block flags can change this needs revisted
            my_term = term_obj.connect() # need a new my_term since we recovered
            term_obj.set_system_setup_term = self.orig_system_setup_term
            term_obj.set_block_setup_term = self.orig_block_setup_term
            my_term.sendline("which bash && exec bash --norc --noprofile")
            time.sleep(0.2)
            my_term.sendline('PS1=' + prompt)
            time.sleep(0.2)
            my_term.sendline("which stty && stty cols 300;which stty && stty rows 30")
            time.sleep(0.2)
            my_term.sendline("export LANG=C")
            time.sleep(0.2)
            my_term.sendline() # needed to sync buffers later on
            time.sleep(0.2) # pause for first time setup, buffers you know, more sensitive in petitboot shell, pexpect or console buffer not sure
            rc = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc == 0:
              print "Shell prompt changed"
              return 1 # caller needs to save state
            else:
              if term_obj.setup_term_quiet == 0:
                print ("OpTestSystem Change of shell prompt not completed after last final retry,"
                        " probably a connection issue, raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=my_term.before, after=my_term.after,
                        msg="Change of shell prompt not completed after last final retry, probably a connection issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1
          except RecoverFailed as e:
            if term_obj.setup_term_quiet == 0:
              print ("OpTestSystem Change of shell prompt not completed after last retry,"
                      " probably a connection issue, raised Exception ConsoleSettings but continuing")
              raise ConsoleSettings(before=my_term.before, after=my_term.after,
                      msg="Change of shell prompt not completed after last retry, probably a connection issue, retry")
            else:
              term_obj.setup_term_disable = 1
              return -1

    def get_login(self, host, term_obj, my_term, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        if term_obj.setup_term_disable == 1:
          return -1, -1
        my_user = host.username()
        my_pwd = host.password()
        my_term.sendline()
        rc = my_term.expect(['login: ', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          my_term.sendline(my_user)
          time.sleep(0.1)
          rc = my_term.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc == 0:
            my_term.sendline(my_pwd)
            time.sleep(0.5)
            rc = my_term.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc not in [1,2,3]:
              if term_obj.setup_term_quiet == 0:
                print ("OpTestSystem Problem with the login and/or password prompt,"
                        " raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=my_term.before, after=my_term.after,
                        msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1, -1
          else:
            if term_obj.setup_term_quiet == 0:
              print "OpTestSystem Problem with the login and/or password prompt, raised Exception ConsoleSettings but continuing"
              raise ConsoleSettings(before=my_term.before, after=my_term.after,
                      msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
            else:
                term_obj.setup_term_disable = 1
                return -1, -1
          my_PS1_set = self.set_PS1(term_obj, my_term, prompt)
          my_LOGIN_set = 1
        else: # timeout eof
          my_term.sendline()
          rc = my_term.expect(['login: ', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc == 0:
            my_term.sendline(my_user)
            time.sleep(0.1)
            rc = my_term.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            if rc == 0:
              my_term.sendline(my_pwd)
              time.sleep(0.5)
              rc = my_term.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
              if rc not in [1,2,3]:
                if term_obj.setup_term_quiet == 0:
                  print ("OpTestSystem Problem with the login and/or password prompt,"
                          " raised Exception ConsoleSettings but continuing")
                  raise ConsoleSettings(before=my_term.before, after=my_term.after,
                          msg="Problem with the login and/or password prompt, probably a connection or credential issue, retry")
                else:
                  term_obj.setup_term_disable = 1
                  return -1, -1
            else:
              if term_obj.setup_term_quiet == 0:
                print ("OpTestSystem Problem with the login and/or password prompt after a secondary connection issue,"
                        " raised Exception ConsoleSettings but continuing")
                raise ConsoleSettings(before=my_term.before, after=my_term.after,
                        msg="Problem with the login and/or password prompt after a secondary connection or credential issue, retry")
              else:
                term_obj.setup_term_disable = 1
                return -1, -1
            my_PS1_set = self.set_PS1(term_obj, my_term, prompt)
            my_LOGIN_set = 1
          else: # timeout eof
            if term_obj.setup_term_quiet == 0:
              print ("OpTestSystem Problem with the login and/or password prompt after a previous connection issue,"
                    " raised Exception ConsoleSettings but continuing")
              raise ConsoleSettings(before=my_term.before, after=my_term.after,
                      msg="Problem with the login and/or password prompt last try, probably a connection or credential issue, retry")
            else:
              term_obj.setup_term_disable = 1
              return -1, -1
        return my_PS1_set, my_LOGIN_set # caller needs to save state

    def check_root(self, my_term, prompt):
        # we do the best we can to verify, but if not oh well
        expect_prompt = prompt + "$"
        my_term.sendline("date") # buffer kicker needed
        my_term.sendline("which whoami && whoami")
        time.sleep(1)
        rc = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          try:
            whoami = my_term.before.splitlines()[-1]
          except Exception as e:
            pass
          my_term.sendline("echo $?")
          time.sleep(1)
          rc = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc == 0:
            try:
              echo_rc = int(my_term.before.splitlines()[-1])
            except Exception as e:
              echo_rc = -1
            if echo_rc == 0:
              if whoami in "root":
                print "OpTestSystem now running as root"
              else:
                raise ConsoleSettings(before=my_term.before, after=my_term.after,
                        msg="Unable to confirm root access setting up terminal, check that you provided"
                        " root credentials or a properly enabled sudo user, retry")
            else:
                print "OpTestSystem should be running as root, unable to verify"

    def get_sudo(self, host, term_obj, my_term, prompt):
        # prompt comes in as the string desired, needs to be pre-built
        # must have PS1 expect_prompt already set
        # must be already logged in
        if term_obj.setup_term_disable == 1:
          return -1, -1
        my_term.sendline()
        expect_prompt = prompt + "$"
        my_user = host.username()
        my_pwd = host.password()
        my_term.sendline("which sudo && sudo -s")
        rc = my_term.expect([r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          my_term.sendline(my_pwd)
          time.sleep(0.5) # delays for next call
          my_PS1_set = self.set_PS1(term_obj, my_term, prompt)
          self.check_root(my_term, prompt)
          my_SUDO_set = 1
          return my_PS1_set, my_SUDO_set # caller needs to save state
        elif rc == 1: # we must have been root, we first filter out password prompt above
          my_PS1_set = self.set_PS1(term_obj, my_term, prompt)
          self.check_root(my_term, prompt)
          my_SUDO_set = 1
          return my_PS1_set, my_SUDO_set # caller needs to save state
        else:
          if term_obj.setup_term_quiet == 0:
            print ("OpTestSystem Unable to setup root access, probably a connection issue,"
                    " raised Exception ConsoleSettings but continuing")
            raise ConsoleSettings(before=my_term.before, after=my_term.after,
                    msg='Unable to setup root access, probably a connection issue, retry')
          else:
            term_obj.setup_term_disable = 1
            return -1, -1

    def setup_term(self, system, my_term, ssh_obj=None, block=0):
        # Login and/or setup any terminal
        # my_term needs to be the opexpect object
        # This will behave correctly even if already logged in
        # Petitboot Menu is special case to NOT participate in this setup, conditionally checks if system state is PETITBOOT and skips
        # CANNOT CALL GET_CONSOLE OR CONNECT from here since get_console and connect call into setup_term
        if block == 1:
          return
        if ssh_obj is not None:
          track_obj = ssh_obj
          term_obj = ssh_obj
          system_obj = ssh_obj.system
        else:
          track_obj = system
          term_obj = system.console
          system_obj = system
        my_term.sendline()
        rc = my_term.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          track_obj.PS1_set, track_obj.LOGIN_set = self.get_login(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          return
        if rc in [1,2,3]:
          track_obj.PS1_set = self.set_PS1(term_obj, my_term, self.build_prompt(system_obj.prompt))
          track_obj.LOGIN_set = 1 # ssh port 22 can get in which uses sshpass or Petitboot, do this after set_PS1 to make sure we have something
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          return
        if rc == 4:
          return # Petitboot so nothing to do
        if rc == 6: # EOF
          term_obj.close() # mark as bad
          raise ConsoleSettings(before=my_term.before, after=my_term.after,
                  msg="Getting login and sudo not successful, probably connection or credential issue, retry")
        # now just timeout
        my_term.sendline()
        rc = my_term.expect(['login: $', ".*#$", ".*# $", ".*\$", 'Petitboot', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          track_obj.PS1_set, track_obj.LOGIN_set = self.get_login(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          return
        if rc in [1,2,3]:
          track_obj.LOGIN_set = track_obj.PS1_set = self.set_PS1(term_obj, my_term, self.build_prompt(system_obj.prompt))
          track_obj.PS1_set, track_obj.SUDO_set = self.get_sudo(system_obj.cv_HOST, term_obj, my_term, self.build_prompt(system_obj.prompt))
          return
        if rc == 4:
          return # Petitboot do nothing
        else:
          if term_obj.setup_term_quiet == 0:
            term_obj.close() # mark as bad
            raise ConsoleSettings(before=my_term.before, after=my_term.after,
                    msg="Getting login and sudo not successful, probably connection issue, retry")
          else:
            # this case happens when detect_target sets the quiet flag and we are timing out
            print "OpTestSystem detected something, checking if your system is powered off, will retry"

    def set_env(self, term_obj, my_term):
        set_env_list = []
        my_term.sendline("which bash && exec bash --norc --noprofile")
        expect_prompt = self.build_prompt(term_obj.prompt) + "$"
        my_term.sendline('PS1=' + self.build_prompt(term_obj.prompt))
        rc = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if rc == 0:
          combo_io = (my_term.before + my_term.after).lstrip()
          set_env_list += combo_io.splitlines()
          # remove the expect prompt since matched generic #
          del set_env_list[-1]
          return set_env_list
        else:
          raise ConsoleSettings(before=my_term.before, after=my_term.after,
                  msg="Setting environment for sudo command not successful, probably connection issue, retry")

    def retry_password(self, term_obj, my_term, command):
        retry_list_output = []
        a = 0
        while a < 3:
          a += 1
          my_term.sendline(term_obj.system.cv_HOST.password())
          rc = my_term.expect([".*#", "try again.", pexpect.TIMEOUT, pexpect.EOF])
          if (rc == 0) or (rc == 1):
            combo_io = my_term.before + my_term.after
            retry_list_output += combo_io.splitlines()
            matching = [xs for xs in sudo_responses if any(xs in xa for xa in my_term.after.splitlines())]
            if len(matching):
              echo_rc = 1
              rc = -1 # use to flag the failure next
          if rc == 0:
            retry_list_output += self.set_env(term_obj, my_term)
            echo_rc = 0
            break
          elif a == 2:
            echo_rc = 1
            break
          elif (rc == 2):
            raise CommandFailed(command, 'Retry Password TIMEOUT ' + ''.join(retry_list_output), -1)
          elif (rc == 3):
            term_obj.close()
            raise ConsoleSettings(before=my_term.before, after=my_term.after,
                    msg='SSH session/console issue, probably connection issue, retry')

        return retry_list_output, echo_rc

    def handle_password(self, term_obj, my_term, command):
        # this is for run_command 'sudo -s' or the like
        handle_list_output = []
        failure_list_output = []
        pre_combo_io = my_term.before + my_term.after
        my_term.sendline(term_obj.system.cv_HOST.password())
        rc = my_term.expect([".*#$", "try again.", pexpect.TIMEOUT, pexpect.EOF])
        if (rc == 0) or (rc == 1):
          combo_io = pre_combo_io + my_term.before + my_term.after
          handle_list_output += combo_io.splitlines()
          matching = [xs for xs in sudo_responses if any(xs in xa for xa in my_term.after.splitlines())]
          if len(matching):
            # remove the expect prompt since matched generic #
            del handle_list_output[-1]
            echo_rc = 1
            rc = -1 # use this to flag the failure next
        if rc == 0:
          # with unknown prompts and unknown environment unable to capture echo $?
          echo_rc = 0
          self.set_env(term_obj, my_term)
          list_output = handle_list_output
        elif rc == 1:
          retry_list_output, echo_rc = self.retry_password(term_obj, my_term, command)
          list_output = (handle_list_output + retry_list_output)
        else:
          if (rc == 2) or (rc == 3):
            failure_list_output += ['Password Problem/TIMEOUT ']
            failure_list_output += pre_combo_io.splitlines()
          # timeout path needs access to output
          # handle_list_output empty if timeout or EOF
          failure_list_output += handle_list_output
          if (rc == 3):
            term_obj.close()
            raise SSHSessionDisconnected("SSH session/console exited early!")
          else:
            raise CommandFailed(command, ''.join(failure_list_output), -1)
        return list_output, echo_rc

    def run_command(self, term_obj, command, timeout=60, retry=0):
        # retry=0 will perform one pass
        counter = 0
        while counter <= retry:
          try:
            output = self.try_command(term_obj, command, timeout)
            return output
          except CommandFailed as cf:
            if counter == retry:
              raise cf
            else:
              counter += 1
              print ("\n \nOpTestSystem detected a command issue, we will retry the command,"
                    " this will be retry \"{:02}\" of a total of \"{:02}\"\n \n".format(counter, retry))

    def try_command(self, term_obj, command, timeout=60):
        running_sudo_s = False
        extra_sudo_output = False
        expect_prompt = self.build_prompt(term_obj.prompt) + "$"
        my_term = term_obj.get_console() # if previous caller environment leaves buffer hung can show up here, e.g. PS2 prompt
        my_term.sendline(command)
        if command == 'sudo -s':
          running_sudo_s = True
          # special case to catch loss of env
          rc = my_term.expect([".*#", r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        else:
          rc = my_term.expect([expect_prompt, r"[Pp]assword for", pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
        output_list = []
        output_list += my_term.before.splitlines()
        try:
          del output_list[:1] # remove command from the list
        except Exception as e:
          pass # nothing there
        # if we are running 'sudo -s' as root then catch on generic # prompt, restore env
        if running_sudo_s and (rc == 0):
          extra_sudo_output = True
          set_env_list = self.set_env(term_obj, my_term)
        if rc == 0:
          if extra_sudo_output:
            output_list += set_env_list
          my_term.sendline("echo $?")
          rc2 = my_term.expect([expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=timeout)
          if rc2 == 0:
            echo_output = my_term.before
            try:
              echo_rc = int(echo_output.splitlines()[-1])
            except Exception as e:
              echo_rc = -1
          else:
            raise CommandFailed(command, "run_command echo TIMEOUT, the command may have been ok,"
                    " but unable to get echo output to confirm result", -1)
        elif rc == 1:
          handle_output_list, echo_rc = self.handle_password(term_obj, my_term, command)
          # remove the expect prompt since matched generic #
          del handle_output_list[-1]
          output_list = handle_output_list
        elif rc == 2: # timeout
            output_list, echo_rc = self.try_sendcontrol(term_obj, command) # original raw buffer if it holds any clues
        else:
          term_obj.close()
          raise CommandFailed(command, "run_command TIMEOUT or EOF, the command timed out or something,"
                  " probably a connection issue, retry", -1)
        res = output_list
        if echo_rc != 0:
          raise CommandFailed(command, res, echo_rc)
        return res

    # This command just runs and returns the output & ignores the failure
    # A straight copy of what's in OpTestIPMI
    def run_command_ignore_fail(self, term_obj, command, timeout=60, retry=0):
        try:
            output = self.run_command(term_obj, command, timeout, retry)
        except CommandFailed as cf:
            output = cf.output
        return output
