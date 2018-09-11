#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestSystem.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

## @package OpTestSystem
#  System package for OpenPower testing.
#
#  This class encapsulates all interfaces and classes required to do end to end
#  automated flashing and testing of OpenPower systems.

import time
import subprocess
import pexpect
import socket
import commands
import unittest

import OpTestIPMI # circular dependencies, use package
import OpTestQemu
from OpTestFSP import OpTestFSP
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
import OpTestHost
from OpTestUtil import OpTestUtil
from OpTestSSH import ConsoleState as SSHConnectionState
from Exceptions import HostbootShutdown, WaitForIt, RecoverFailed, UnknownStateTransition, ConsoleSettings, UnexpectedCase, StoppingSystem
from OpTestSSH import OpTestSSH

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpSystemState():
    '''
    This class is used as an enum as to what state op-test *thinks* the host is in.
    These states are used to drive a state machine in OpTestSystem.
    '''
    UNKNOWN = 0
    OFF = 1
    IPLing = 2
    PETITBOOT = 3
    PETITBOOT_SHELL = 4
    BOOTING = 5
    OS = 6
    POWERING_OFF = 7
    UNKNOWN_BAD = 8 # special case, use set_state to place system in hold for later goto

class OpTestSystem(object):

    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the Host
    # @param i_hostuser The userid to log into the Host
    # @param i_hostPasswd The password of the userid to log into the host with
    #

    def __init__(self,
                 bmc=None, host=None,
                 prompt=None,
                 state=OpSystemState.UNKNOWN):
        self.bmc = self.cv_BMC = bmc
        self.cv_HOST = host
        self.cv_IPMI = bmc.get_ipmi()
        self.rest = self.bmc.get_rest_api()
        self.console = self.bmc.get_host_console()
        self.util = OpTestUtil()
        self.prompt = prompt # build_prompt located in OpTestUtil
        # system console state tracking, reset on boot and state changes, set when valid
        self.PS1_set = -1
        self.SUDO_set = -1
        self.LOGIN_set = -1
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.previous_state = None # used for PS1, LOGIN, SUDO state tracking
        self.target_state = None # used in WaitForIt
        self.detect_counter = 0 # outside scope of detection to prevent loops
        self.never_rebooted = True # outside scope to prevent loops
        self.block_setup_term = 0
        self.stop = 0
        self.ignore = 0

        self.openpower = 'openpower' # string to define petitboot kernel cat /proc/version column 3, change if using debug petitboot kernel

        # dictionary used in sorted order
        # column 1 is the string, column 2 is the action
        # normally None is the action, otherwise a handler mostly used for exceptions
        self.petitboot_expect_table = {
          'Petitboot'                              : None,
          '/ #'                                    : None,
          'shutdown requested'                     : self.hostboot_callback,
          'x=exit'                                 : None,
          'login: '                                : self.login_callback,
          'mon> '                                  : self.xmon_callback,
          'System shutting down with error status' : self.guard_callback,
          'Aborting!'                              : self.skiboot_callback,
        }

        self.login_expect_table = {
          'login: '                           : None,
          '/ #'                               : self.petitboot_callback,
          'mon> '                             : self.xmon_callback,
        }

        # tunables for customizations, put them here all together

        # ipmi versus ssh settings, sometimes tuning is needed based on type, so keeping split for tuning
        # to basically turn off reconnect based on stale buffers set threshold equal to watermark, e.g. 100
        if isinstance(self.console, OpTestIPMI.IPMIConsole):
          self.threshold_petitboot = 12 # stale buffer check
          self.threshold_login = 12 # long enough to skip the refresh until kexec, stale buffers need to be jumped over
          self.petitboot_kicker = 0
          self.petitboot_refresh = 0 # petitboot menu cannot tolerate, cancels default boot
          self.petitboot_reconnect = 1
          self.login_refresh = 0
          self.login_reconnect = 1 # less reliable connections, ipmi act/deact does not trigger default boot cancel
          self.login_fresh_start = 0
        else:
          self.threshold_petitboot = 12 # stale buffer check
          self.threshold_login = 12 # long enough to skip the refresh until kexec, stale buffers need to be jumped over
          self.petitboot_kicker = 0
          self.petitboot_refresh = 0 # petitboot menu cannot tolerate, cancels default boot
          self.petitboot_reconnect = 1 # NEW ssh triggers default boot cancel, just saying
          self.login_refresh = 0
          self.login_reconnect = 1 # NEW ssh triggers default boot cancel, just saying
          self.login_fresh_start = 0

        # watermark is the loop counter (loop_max) used in conjunction with timeout
        # timeout is the expect timeout for each iteration
        # watermark will automatically increase in case the loop is too short
        self.ipl_watermark = 100
        self.ipl_timeout = 4 # needs consideration with petitboot timeout
        self.booting_watermark = 100
        self.booting_timeout = 5
        self.kill_cord = 150 # just a ceiling on giving up

        # We have a state machine for going in between states of the system
        # initially, everything in UNKNOWN, so we reset things.
        # UNKNOWN is used to flag the system to auto-detect the state if
        # possible to efficiently achieve state transitions.
        # But, we allow setting an initial state if you, say, need to
        # run against an already IPLed system
        self.state = state
        self.stateHandlers = {}
        self.stateHandlers[OpSystemState.UNKNOWN] = self.run_UNKNOWN
        self.stateHandlers[OpSystemState.OFF] = self.run_OFF
        self.stateHandlers[OpSystemState.IPLing] = self.run_IPLing
        self.stateHandlers[OpSystemState.PETITBOOT] = self.run_PETITBOOT
        self.stateHandlers[OpSystemState.PETITBOOT_SHELL] = self.run_PETITBOOT_SHELL
        self.stateHandlers[OpSystemState.BOOTING] = self.run_BOOTING
        self.stateHandlers[OpSystemState.OS] = self.run_OS
        self.stateHandlers[OpSystemState.POWERING_OFF] = self.run_POWERING_OFF
        self.stateHandlers[OpSystemState.UNKNOWN_BAD] = self.run_UNKNOWN

        # We track the state of loaded IPMI modules here, that way
        # we only need to try the modprobe once per IPL.
        # We reset as soon as we transition away from OpSystemState.OS
        # a TODO is to support doing this in petitboot shell as well.
        self.ipmiDriversLoaded = False

    def hostboot_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        self.state = OpSystemState.UNKNOWN_BAD
        self.stop = 1
        raise HostbootShutdown()

    def login_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        log.warning("\n\n *** OpTestSystem found the login prompt \"{}\" but this is unexpected, we will retry\n\n".format(kwargs['value']))
        # raise the WaitForIt exception to be bubbled back to recycle early rather than having to wait the full loop_max
        raise WaitForIt(expect_dict=self.petitboot_expect_table, reconnect_count=-1)

    def petitboot_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        log.warning("\n\n *** OpTestSystem found the petitboot prompt \"{}\" but this is unexpected, we will retry\n\n".format(kwargs['value']))
        # raise the WaitForIt exception to be bubbled back to recycle early rather than having to wait the full loop_max
        raise WaitForIt(expect_dict=self.login_expect_table, reconnect_count=-1)

    def guard_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        guard_exception = UnexpectedCase(state=self.state, msg="We hit the guard_callback value={}, manually restart the system".format(kwargs['value']))
        self.state = OpSystemState.UNKNOWN_BAD
        self.stop = 1
        raise guard_exception

    def xmon_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        xmon_check_r = kwargs['my_r']
        xmon_value = kwargs['value']
        time.sleep(2)
        sys_console = self.console.get_console()
        time.sleep(2)
        sys_console.sendline("t")
        time.sleep(2)
        rc = sys_console.expect([".*mon> ", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        xmon_backtrace = sys_console.after
        sys_console.sendline("r")
        time.sleep(2)
        rc = sys_console.expect([".*mon> ", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        xmon_registers = sys_console.after
        sys_console.sendline("S")
        time.sleep(2)
        rc = sys_console.expect([".*mon> ", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        xmon_special_registers = sys_console.after
        self.stop = 1
        my_msg = ('We hit the xmon_callback with \"{}\" backtrace=\n{}\n registers=\n{}\n special_registers=\n{}\n'
                  .format(xmon_value, xmon_backtrace, xmon_registers, xmon_special_registers))
        xmon_exception = UnexpectedCase(state=self.state, msg=my_msg)
        self.state = OpSystemState.UNKNOWN_BAD
        raise xmon_exception

    def skiboot_callback(self, **kwargs):
        default_vals = {'my_r': None, 'value': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        skiboot_exception = UnexpectedCase(state=self.state, msg="We hit the skiboot_callback value={}, manually restart the system".format(kwargs['value']))
        self.state = OpSystemState.UNKNOWN_BAD
        self.stop = 1
        raise skiboot_exception

    def skiboot_log_on_console(self):
        return True

    def has_host_accessible_eeprom(self):
        return True

    def has_host_led_support(self):
        return False

    def has_centaurs_in_dt(self):
        proc_gen = self.host().host_get_proc_gen()
        if proc_gen in ["POWER9"]:
            return False
        return True

    def has_mtd_pnor_access(self):
        return True

    def host(self):
        return self.cv_HOST

    def bmc(self):
        return self.cv_BMC

    def rest(self):
        return self.rest

    def ipmi(self):
        return self.cv_IPMI

    def get_state(self):
        return self.state;

    def set_state(self, state):
        self.state = state

    def goto_state(self, state):
        # only perform detection when incoming state is UNKNOWN
        # if user overrides from command line and machine not at desired state can lead to exceptions
        self.block_setup_term = 1 # block in case the system is not on/up
        self.target_state = state # used in WaitForIt
        if isinstance(self.console, OpTestQemu.QemuConsole) and (state == OpSystemState.OS):
          raise unittest.SkipTest("OpTestSystem running QEMU so skipping OpSystemState.OS test")
        if (self.state == OpSystemState.UNKNOWN):
          log.debug("OpTestSystem CHECKING CURRENT STATE and TRANSITIONING for TARGET STATE: %s" % (state))
          self.state = self.run_DETECT(state)
          log.debug("OpTestSystem CURRENT DETECTED STATE: %s" % (self.state))

        log.debug("OpTestSystem START STATE: %s (target %s)" % (self.state, state))
        never_unknown = False
        while 1:
            if self.stop == 1:
              raise StoppingSystem()
            self.block_setup_term = 1 # block until we are clear, exceptions can re-enter while booting
            if self.state != OpSystemState.UNKNOWN:
                never_unknown = True
            self.state = self.stateHandlers[self.state](state)
            # transition from states invalidate the previous PS1 setting, so clear it
            if self.previous_state != self.state:
              self.util.clear_state(self)
              self.previous_state = self.state
            log.debug("OpTestSystem TRANSITIONED TO: %s" % (self.state))
            if self.state == state:
                break;
            if never_unknown and self.state == OpSystemState.UNKNOWN:
                 self.stop = 1
                 raise UnknownStateTransition(state=self.state,
                         msg=("OpTestSystem something set the system to UNKNOWN,"
                           " check the logs for details, we will be stopping the system"))

    def run_DETECT(self, target_state):
        self.detect_counter += 1
        detect_state = OpSystemState.UNKNOWN
        if self.detect_counter >= 3:
          return OpSystemState.UNKNOWN
        while (detect_state == OpSystemState.UNKNOWN) and (self.detect_counter <= 2):
          # two phases
          detect_state = self.detect_target(target_state, self.never_rebooted)
          self.block_setup_term = 1 # block after check_kernel unblocked
          self.never_rebooted = False
          self.detect_counter += 1
        return detect_state

    def detect_target(self, target_state, reboot):
        self.block_setup_term = 0 # unblock to allow setup_term during get_console
        self.console.enable_setup_term_quiet()
        sys_console = self.console.get_console()
        self.console.disable_setup_term_quiet()
        sys_console.sendline()
        r = sys_console.expect(["x=exit", "Petitboot", ".*#", ".*\$", "login:", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        if r in [0,1]:
          if (target_state == OpSystemState.PETITBOOT):
            return OpSystemState.PETITBOOT
          elif (target_state == OpSystemState.PETITBOOT_SHELL):
            self.petitboot_exit_to_shell()
            return OpSystemState.PETITBOOT_SHELL
          elif (target_state == OpSystemState.OS) and reboot:
            self.petitboot_exit_to_shell()
            self.run_REBOOT(target_state)
            return OpSystemState.UNKNOWN
          else:
            return OpSystemState.UNKNOWN
        elif r in [2,3]:
          detect_state = self.check_kernel()
          if (detect_state == target_state):
            self.previous_state = detect_state # preserve state
            return detect_state
          elif reboot:
            if target_state in [OpSystemState.OS]:
              self.run_REBOOT(target_state)
              return OpSystemState.UNKNOWN
            elif target_state in [OpSystemState.PETITBOOT]:
              if (detect_state == OpSystemState.PETITBOOT_SHELL):
                self.exit_petitboot_shell()
                return OpSystemState.PETITBOOT
              else:
                self.run_REBOOT(target_state)
                return OpSystemState.UNKNOWN
            elif target_state in [OpSystemState.PETITBOOT_SHELL]:
              self.run_REBOOT(target_state)
              return OpSystemState.UNKNOWN
            else:
              return OpSystemState.UNKNOWN
          else:
            if (detect_state == target_state):
              self.previous_state = detect_state # preserve state
              return detect_state
            elif (detect_state == OpSystemState.PETITBOOT_SHELL) and (target_state == OpSystemState.PETITBOOT):
              self.exit_petitboot_shell()
              return OpSystemState.PETITBOOT
            elif target_state in [OpSystemState.PETITBOOT_SHELL]:
              return OpSystemState.PETITBOOT_SHELL
            else:
              return OpSystemState.UNKNOWN
        elif r == 4:
          if (target_state == OpSystemState.OS):
            return OpSystemState.OS
          elif reboot:
            if target_state in [OpSystemState.OS,OpSystemState.PETITBOOT,OpSystemState.PETITBOOT_SHELL]:
              self.run_REBOOT(target_state)
              return OpSystemState.UNKNOWN
            else:
              return OpSystemState.UNKNOWN
          else:
            return OpSystemState.UNKNOWN
        elif (r == 5) or (r == 6):
          self.detect_counter += 1
          return OpSystemState.UNKNOWN

    def check_kernel(self):
        self.block_setup_term = 0 # unblock to allow setup_term during get_console
        self.console.enable_setup_term_quiet()
        sys_console = self.console.get_console()
        self.console.disable_setup_term_quiet()
        sys_console.sendline()
        rc = sys_console.expect(["x=exit", "Petitboot", ".*#", ".*\$", "login:", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
        if rc in [0,1,5,6]:
          return OpSystemState.UNKNOWN # we really should not have arrived in here and not much we can do
        sys_console.sendline("cat /proc/version | cut -d ' ' -f 3 | grep %s; echo $?" % (self.openpower))
        time.sleep(0.2)
        rc = sys_console.expect([self.expect_prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=1)
        if rc == 0:
          echo_output = sys_console.before
          try:
            echo_rc = int(echo_output.splitlines()[-1])
          except Exception as e:
            # most likely cause is running while booting unknowlingly
            return OpSystemState.UNKNOWN
          if (echo_rc == 0):
            self.previous_state = OpSystemState.PETITBOOT_SHELL
            return OpSystemState.PETITBOOT_SHELL
          elif echo_rc == 1:
            self.previous_state = OpSystemState.OS
            return OpSystemState.OS
          else:
            return OpSystemState.UNKNOWN
        else: # TIMEOUT EOF from cat
            return OpSystemState.UNKNOWN

    def wait_for_it(self, **kwargs):
        default_vals = {'expect_dict': None, 'refresh': 1, 'buffer_kicker': 1, 'loop_max': 8, 'threshold': 1, 'reconnect': 1, 'fresh_start' : 1, 'last_try': 1, 'timeout': 5}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        base_seq = [pexpect.TIMEOUT, pexpect.EOF]
        expect_seq = list(base_seq) # we want a *copy*
        expect_seq = expect_seq + list(sorted(kwargs['expect_dict'].keys()))
        if kwargs['fresh_start']:
          sys_console = self.console.connect() # new connect gets new pexpect buffer, stale buffer from power off can linger
        else:
          sys_console = self.console.get_console() # cannot tolerate new connect on transition from 3/4 to 6
        # we do not perform buffer_kicker here since it can cause changes to things like the petitboot menu and default boot
        if kwargs['refresh']:
          sys_console.sendcontrol('l')
        previous_before = 'emptyfirst'
        x = 1
        reconnect_count = 0
        timeout_count = 1
        while (x <= kwargs['loop_max']):
            sys_console = self.console.get_console() # preemptive in case EOF came
            r = sys_console.expect(expect_seq, kwargs['timeout'])
            # if we have a stale buffer and we are still timing out
            if (previous_before == sys_console.before) and ((r + 1) in range(len(base_seq))):
              timeout_count += 1
              # only attempt reconnect if we've timed out per threshold
              if (timeout_count % kwargs['threshold'] == 0):
                if kwargs['reconnect']:
                  reconnect_count += 1
                  try:
                    sys_console = self.console.connect()
                  except Exception as e:
                    log.error(e)
                  if kwargs['refresh']:
                    sys_console.sendcontrol('l')
                  if kwargs['buffer_kicker']:
                    sys_console.sendline("\r")
                    sys_console.expect("\n")
                previous_before = 'emptyagain'
            else:
              previous_before = sys_console.before
              timeout_count = 1

            working_r = self.check_it(my_r=r, check_base_seq=base_seq, check_expect_seq=expect_seq, check_expect_dict=kwargs['expect_dict'])
            # if we found a hit on the callers string return it, otherwise keep looking
            if working_r != -1:
              return working_r, reconnect_count
            else:
              x += 1
              log.debug("\n *** WaitForIt CURRENT STATE \"{:02}\" TARGET STATE \"{:02}\"\n"
                      " *** WaitForIt working on transition\n"
                      " *** Current loop iteration \"{:02}\"             - Reconnect attempts \"{:02}\" - loop_max \"{:02}\"\n"
                      " *** WaitForIt timeout interval \"{:02}\" seconds - Stale buffer check every \"{:02}\" times\n"
                      " *** WaitForIt variables \"{}\"\n"
                      " *** WaitForIt Refresh=\"{}\" Buffer Kicker=\"{}\" - Kill Cord=\"{:02}\"\n".format(self.state, self.target_state,
                      x, reconnect_count, kwargs['loop_max'], kwargs['timeout'], kwargs['threshold'],
                      sorted(kwargs['expect_dict'].keys()), kwargs['refresh'], kwargs['buffer_kicker'], self.kill_cord))
            if (x >= kwargs['loop_max']):
              if kwargs['last_try']:
                sys_console = self.console.connect()
                sys_console.sendcontrol('l')
                sys_console.sendline("\r")
                r = sys_console.expect(expect_seq, kwargs['timeout'])
                try:
                  last_try_r = self.check_it(my_r=r, check_base_seq=base_seq, check_expect_seq=expect_seq,
                                               check_expect_dict=kwargs['expect_dict'])
                  if last_try_r != -1:
                    return last_try_r, reconnect_count
                  else:
                    raise WaitForIt(expect_dict=kwargs['expect_dict'], reconnect_count=reconnect_count)
                except Exception as e:
                  raise e
              raise WaitForIt(expect_dict=kwargs['expect_dict'], reconnect_count=reconnect_count)

    def check_it(self, **kwargs):
        default_vals = {'my_r': None, 'check_base_seq': None, 'check_expect_seq': None, 'check_expect_dict': None}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        check_r = kwargs['my_r']
        check_expect_seq = kwargs['check_expect_seq']
        check_base_seq = kwargs['check_base_seq']
        check_expect_dict = kwargs['check_expect_dict']
        # if we have a hit on the callers string process it
        if (check_r + 1) in range(len(check_base_seq) + 1, len(check_expect_seq) + 1):
          # if there is a handler callback
          if check_expect_dict[check_expect_seq[check_r]]:
            try:
              # this calls the handler callback, mostly intended for raising exceptions
              check_expect_dict[check_expect_seq[check_r]](my_r=check_r, value=check_expect_seq[check_r])
              if self.ignore == 1: # future use, set this flag in a handler callback
                self.ignore = 0
                # if we go to a callback and get back here flag this to ignore the find
                # this allows special handling without interrupting the waiting for a good case
                return -1
            except Exception as e:
              # if a callback handler raised an exception this will catch it and then re-raise it
              raise e
          # r based on sorted order of dict
          return check_r - len(check_base_seq)
        else:
          if check_r == 1: # EOF
            self.console.close() # while loop will get_console
        # we found nothing so return -1
        return -1

    def run_REBOOT(self, target_state):
        self.block_setup_term = 0 # allow login/setup
        # if run_REBOOT is used in the future outside of first time need to review previous_state handling
        sys_console = self.console.get_console()
        if (target_state == OpSystemState.PETITBOOT_SHELL) or (target_state == OpSystemState.PETITBOOT):
          self.sys_set_bootdev_setup()
        else:
          self.sys_set_bootdev_no_override()
        self.util.clear_state(self)
        self.block_setup_term = 1 # block during reboot
        sys_console.sendline('reboot') # connect will have the login/root setup_term done
        sys_console.expect("\n")

        try:
          if (target_state == OpSystemState.OS):
            my_r, my_reconnect = self.wait_for_it(expect_dict=self.login_expect_table,
               reconnect=self.login_reconnect, threshold=self.threshold_login, loop_max=100)
          else:
            my_r, my_reconnect = self.wait_for_it(expect_dict=self.petitboot_expect_table,
               reconnect=self.petitboot_reconnect, refresh=self.petitboot_refresh, buffer_kicker=self.petitboot_kicker,
               threshold=self.threshold_petitboot, loop_max=100)
        except Exception as e:
          return

    def run_UNKNOWN(self, state):
        self.block_setup_term = 1
        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_OFF(self, state):
        self.block_setup_term = 1
        if state == OpSystemState.OFF:
            return OpSystemState.OFF
        if state == OpSystemState.UNKNOWN:
            raise UnknownStateTransition(state=self.state,
                    msg="OpTestSystem in run_OFF and something caused the system to go to UNKNOWN")

        # We clear any possible errors at this stage
        self.sys_sdr_clear()

        if state == OpSystemState.OS:
            # By default auto-boot will be enabled, set no override
            # otherwise system endup booting in default disk.
            self.sys_set_bootdev_no_override()
            #self.cv_IPMI.ipmi_set_boot_to_disk()
        if state == OpSystemState.PETITBOOT or state == OpSystemState.PETITBOOT_SHELL:
            self.sys_set_bootdev_setup()

        r = self.sys_power_on()
        # Only retry once
        if r == BMC_CONST.FW_FAILED:
            r = self.sys_power_on()
            if r == BMC_CONST.FW_FAILED:
                raise 'Failed powering on system'
        return OpSystemState.IPLing

    def run_IPLing(self, state):
        self.block_setup_term = 1
        if state == OpSystemState.OFF:
            self.sys_power_off()
            return OpSystemState.POWERING_OFF

        try:

            # if petitboot cannot be reached it will automatically increase the watermark and retry
            # see the tunables ipl_watermark and ipl_timeout for customization for extra long boot cycles for debugging, etc
            petit_r, petit_reconnect = self.wait_for_it(expect_dict=self.petitboot_expect_table, reconnect=self.petitboot_reconnect,
                buffer_kicker=self.petitboot_kicker, threshold=self.threshold_petitboot, refresh=self.petitboot_refresh,
                loop_max=self.ipl_watermark, timeout=self.ipl_timeout)
        except HostbootShutdown as e:
            log.error(e)
            self.sys_sel_check()
            raise e
        except WaitForIt as e:
            if self.ipl_watermark < self.kill_cord:
              self.ipl_watermark += 1
              log.warning("OpTestSystem UNABLE TO REACH PETITBOOT or we missed it - \"{}\", increasing ipl_watermark for loop_max to {},"
                      " will re-IPL for another try".format(e, self.ipl_watermark))
              return OpSystemState.UNKNOWN_BAD
            else:
              log.error("OpTestSystem has reached the limit on re-IPL'ing to try to recover, we will be stopping")
              return OpSystemState.UNKNOWN
        except Exception as e:
            self.stop = 1 # Exceptions like in OPexpect Assert fail
            my_msg = ("OpTestSystem in run_IPLing and the Exception=\n\"{}\"\n caused the system to"
                       " go to UNKNOWN_BAD and the system will be stopping.".format(e))
            my_exception = UnknownStateTransition(state=self.state, msg=my_msg)
            self.state = OpSystemState.UNKNOWN_BAD
            raise my_exception

        if petit_r != -1:
          # Once reached to petitboot check for any SEL events
          self.sys_sel_check()
          return OpSystemState.PETITBOOT

    def run_PETITBOOT(self, state):
        self.block_setup_term = 1
        if state == OpSystemState.PETITBOOT:
            # verify that we are at the petitboot menu
            self.exit_petitboot_shell()
            return OpSystemState.PETITBOOT
        if state == OpSystemState.PETITBOOT_SHELL:
            self.petitboot_exit_to_shell()
            return OpSystemState.PETITBOOT_SHELL

        if state == OpSystemState.OFF:
            self.sys_power_off()
            return OpSystemState.POWERING_OFF

        if state == OpSystemState.OS:
            return OpSystemState.BOOTING

        raise UnknownStateTransition(state=self.state, msg="OpTestSystem in run_PETITBOOT and something caused the system to go to UNKNOWN")

    def run_PETITBOOT_SHELL(self, state):
        self.block_setup_term = 1
        if state == OpSystemState.PETITBOOT_SHELL:
            # verify that we are at the petitboot shell
            self.petitboot_exit_to_shell()
            return OpSystemState.PETITBOOT_SHELL

        if state == OpSystemState.PETITBOOT:
            self.exit_petitboot_shell()
            return OpSystemState.PETITBOOT

        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_BOOTING(self, state):
        self.block_setup_term = 1
        try:
          # if login cannot be reached it will automatically increase the watermark and retry
          # see the tunables booting_watermark and booting_timeout for customization for extra long boot cycles for debugging, etc
          login_r, login_reconnect = self.wait_for_it(expect_dict=self.login_expect_table, reconnect=self.login_reconnect,
            threshold=self.threshold_login, refresh=self.login_refresh, loop_max=self.booting_watermark,
            fresh_start=self.login_fresh_start, timeout=self.booting_timeout)
        except WaitForIt as e:
          if self.booting_watermark < self.kill_cord:
            self.booting_watermark += 1
            log.warning("OpTestSystem UNABLE TO REACH LOGIN or we missed it - \"{}\", increasing booting_watermark for loop_max to {},"
                    " will re-IPL for another try".format(e, self.booting_watermark))
            return OpSystemState.UNKNOWN_BAD
          else:
            log.error("OpTestSystem has reached the limit on re-IPL'ing to try to recover, we will be stopping")
            return OpSystemState.UNKNOWN
        except Exception as e:
            my_msg = ("OpTestSystem in run_IPLing and Exception=\"{}\" caused the system to"
                       " go to UNKNOWN_BAD and the system will be stopping.".format(e))
            my_exception = UnknownStateTransition(state=self.state, msg=my_msg)
            self.stop = 1 # hits like in OPexpect Assert fail
            self.state = OpSystemState.UNKNOWN_BAD
            raise my_exception

        if login_r != -1:
          self.block_setup_term = 0
          return OpSystemState.OS

    def run_OS(self, state):
        self.block_setup_term = 0
        if state == OpSystemState.OS:
            return OpSystemState.OS
        self.ipmiDriversLoaded = False
        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_POWERING_OFF(self, state):
        self.block_setup_term = 1
        rc = int(self.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY))
        if rc == BMC_CONST.FW_SUCCESS:
            msg = "System is in standby/Soft-off state"
        elif rc == BMC_CONST.FW_PARAMETER:
            msg = "Host Status sensor is not available/Skipping stand-by state check"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        log.info(msg)
        self.cv_HOST.ssh.state = SSHConnectionState.DISCONNECTED
        self.util.clear_state(self)
        return OpSystemState.OFF

    def load_ipmi_drivers(self, force=False):
        if self.ipmiDriversLoaded and not force:
            return

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Checking for ipmitool command and package
        self.cv_HOST.host_check_command("ipmitool")

        l_pkg = self.cv_HOST.host_check_pkg_for_utility(l_oslevel, "ipmitool")
        log.debug("Installed package: %s" % l_pkg)

        # loading below ipmi modules based on config option
        # ipmi_devintf, ipmi_powernv and ipmi_masghandler
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_DEVICE_INTERFACE,
                                                      BMC_CONST.IPMI_DEV_INTF)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_POWERNV,
                                                      BMC_CONST.IPMI_POWERNV)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_HANDLER,
                                                      BMC_CONST.IPMI_MSG_HANDLER)
        self.ipmiDriversLoaded = True
        log.debug("IPMI drivers loaded")
        return

    ############################################################################
    # System Interfaces
    ############################################################################

    def sys_sdr_clear(self):
        '''
        Clear all SDRs in the System

        Returns BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
        '''
        try:
            rc =  self.cv_IPMI.ipmi_sdr_clear()
        except OpTestError as e:
            time.sleep(BMC_CONST.LONG_WAIT_IPL)
            log.debug("Retry clearing SDR")
            try:
                rc = self.cv_IPMI.ipmi_sdr_clear()
            except OpTestError as e:
                return BMC_CONST.FW_FAILED
        return rc

    def sys_power_on(self):
        '''
        Power on the host system, probably via `ipmitool power on`
        '''
        try:
            rc = self.cv_IPMI.ipmi_power_on()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    def sys_power_cycle(self):
        '''
        Power cycle the host, most likely `ipmitool power cycle`
        '''
        try:
            return self.cv_IPMI.ipmi_power_cycle()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    def sys_power_soft(self):
        '''
        Soft power cycle the system. This allows OS to gracefully shutdown
        '''
        try:
            rc = self.cv_IPMI.ipmi_power_soft()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Power off the system
    #
    def sys_power_off(self):
        self.cv_IPMI.ipmi_power_off()

    def sys_set_bootdev_setup(self):
        self.cv_IPMI.ipmi_set_boot_to_petitboot()

    def sys_set_bootdev_no_override(self):
        self.cv_IPMI.ipmi_set_no_override()

    def sys_power_reset(self):
        self.cv_IPMI.ipmi_power_reset()

    ##
    # @brief Warm reset on the bmc system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_warm_reset(self):
        try:
            rc = self.cv_IPMI.ipmi_warm_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Cold reset on the bmc system
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_cold_reset_bmc(self):
        try:
            rc = self.cv_IPMI.ipmi_cold_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    ##
    # @brief Cold reset on the Host
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_host_cold_reset(self):
        try:
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Wait for boot to end based on serial over lan output data
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_ipl_wait_for_working_state(self,i_timeout=10):
        try:
            rc = self.cv_IPMI.ipl_wait_for_working_state(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc

    def sys_wait_for_standby_state(self, i_timeout=120):
        '''
        Wait for system to reach standby or[S5/G2: soft-off]

        :param i_timeout: The number of seconds to wait for system to reach standby, i.e. How long to poll the ACPI sensor for soft-off state before giving up.
        :rtype: BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
        '''
        try:
            l_rc = self.cv_IPMI.ipmi_wait_for_standby_state(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return l_rc

    def sys_wait_for_os_boot_complete(self, i_timeout=10):
        '''
        Wait for system boot to host OS, It uses OS Boot sensor

        :param i_timeout: The number of minutes to wait for IPL to complete or Boot time,
            i.e. How long to poll the OS Boot sensor for working state before giving up.
        :rtype: BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
        '''
        try:
            l_rc = self.cv_IPMI.ipmi_wait_for_os_boot_complete(i_timeout)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return l_rc

    def sys_sel_check(self,i_string="Transition to Non-recoverable"):
        '''
        Check for error during IPL that would result in test case failure

        :param i_string: string to search for
        :rtype: BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
        '''
        try:
            rc = self.cv_IPMI.ipmi_sel_check(i_string)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return rc


    def sys_bmc_reboot(self):
        '''
        Reboot the BMC

        This may use ``ipmitool mc reset cold`` or it may do an inline ``reboot``
        '''
        try:
            rc = self.cv_BMC.reboot()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Validates the partition and waits for partition to connect
    #        important to perform before all inband communications
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_power_on_validate_host(self):
        # Check to see if host credentials are present
        if(self.cv_HOST.ip == None):
            l_msg = "Partition credentials not provided"
            log.error(l_msg)
            return BMC_CONST.FW_FAILED

        # Check if partition is active
        try:
            self.util.PingFunc(self.cv_HOST.ip, totalSleepTime=2)
            self.cv_HOST.host_get_OS_Level()
        except OpTestError as e:
            log.error("Trying to recover partition after error: %s" % (e) )
            try:
                self.cv_IPMI.ipmi_power_off()
                self.sys_cold_reset_bmc()
                self.cv_IPMI.ipmi_power_on()
                self.sys_check_host_status()
                self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            except OpTestError as e:
                return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function reboots the system(Power off/on) and
    #        check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_hard_reboot(self):
        log.debug("Performing a IPMI Power OFF Operation")
        self.cv_IPMI.ipmi_power_off()
        rc = int(self.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY))
        if rc == BMC_CONST.FW_SUCCESS:
            log.info("System is in standby/Soft-off state")
        elif rc == BMC_CONST.FW_PARAMETER:
            log.info("Host Status sensor is not available")
            log.info("Skipping stand-by state check")
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)
        log.info("Performing a IPMI Power ON Operation")
        self.cv_IPMI.ipmi_power_on()
        self.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_check_host_status(self):
        rc = int(self.sys_ipl_wait_for_working_state())
        if rc == BMC_CONST.FW_SUCCESS:
            log.info("System booted to working state")
        elif rc == BMC_CONST.FW_PARAMETER:
            log.info("Host Status sensor is not available")
            log.info("Skip wait for IPL runtime check")
        else:
            l_msg = "System failed to boot"
            raise OpTestError(l_msg)
        rc = int(self.sys_wait_for_os_boot_complete())
        if rc == BMC_CONST.FW_SUCCESS:
            log.info("System booted to Host OS")
        elif rc == BMC_CONST.FW_PARAMETER:
            log.info("OS Boot sensor is not available")
            log.info("Skip wait for wait for OS boot complete check")
        else:
            l_msg = "System failed to boot Host OS"
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Issue IPMI PNOR Reprovision request command
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_issue_ipmi_pnor_reprovision_request(self):
        try:
            self.cv_HOST.host_run_command(BMC_CONST.HOST_IPMI_REPROVISION_REQUEST)
        except OpTestError as e:
            log.error("Failed to issue ipmi pnor reprovision request")
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Wait for IPMI PNOR Reprovision to complete(response to 00)
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_wait_for_ipmi_pnor_reprovision_to_complete(self, timeout=10):
        l_res = ""
        timeout = time.time() + 60*timeout
        while True:
            l_res = self.cv_HOST.host_run_command(BMC_CONST.HOST_IPMI_REPROVISION_PROGRESS)
            if "00" in l_res:
                log.info("IPMI: Reprovision completed")
                break
            if time.time() > timeout:
                l_msg = "Reprovision timeout, progress not reaching to 00"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(10)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function gets the sel log
    #
    # @return sel list or BMC_CONST.FW_FAILED
    #
    def sys_get_sel_list(self):
        try:
            return self.cv_IPMI.ipmi_get_sel_list()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    def petitboot_exit_to_shell(self):
        sys_console = self.console.get_console()
        for i in range(3):
          pp = self.get_petitboot_prompt()
          if pp == 1:
            break;
        if pp != 1:
            log.warning("OpTestSystem detected something, tried to recover, but still we have a problem, retry")
            raise ConsoleSettings(before=sys_console.before, after=sys_console.after,
                    msg="System at Petitboot Menu unable to exit to shell after retry")

    def get_petitboot_prompt(self):
        my_pp = 0
        sys_console = self.console.get_console()
        sys_console.sendline()
        pes_rc = sys_console.expect([".*#", ".*# $", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if pes_rc in [0,1]:
          if self.PS1_set != 1:
            self.SUDO_set = self.LOGIN_set = self.PS1_set = self.util.set_PS1(self.console, sys_console, self.util.build_prompt(self.prompt))
          self.block_setup_term = 0 # unblock in case connections are lost during state=4 the get_console/connect can properly setup again
          self.previous_state = OpSystemState.PETITBOOT_SHELL # preserve state
          my_pp = 1
        else:
          sys_console = self.console.connect() # try new connect, sometimes stale buffers
        return my_pp

    def exit_petitboot_shell(self):
        sys_console = self.console.get_console()
        eps_rc = self.try_exit(sys_console)
        if eps_rc == 0: # Petitboot
          return
        else: # we timed out or eof
          self.util.try_recover(self.console, counter=3)
          # if we get back here we're good and at the prompt
          sys_console.sendline()
          eps_rc = self.try_exit(sys_console)
          if eps_rc == 0: # Petitboot
            return
          else:
            raise RecoverFailed(before=sys_console.before, after=sys_console.after,
                    msg="Unable to get the Petitboot prompt stage 3, we were trying to exit back to menu")

    def try_exit(self, sys_console):
          self.util.clear_state(self)
          sys_console.sendline()
          sys_console.sendline("exit")
          rc_return = sys_console.expect(["Petitboot", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
          if rc_return == 0:
            return rc_return
          else:
            return -1

    def get_my_ip_from_host_perspective(self):
        rawc = self.console.get_console()
        port = 12340
        my_ip = None
        try:
            if self.get_state() == OpSystemState.PETITBOOT_SHELL:
                rawc.send("nc -l -p %u -v -e /bin/true\n" % port)
            else:
                rawc.send("nc -l -p %u -v\n" % port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            time.sleep(0.5)
            log.debug("# Connecting to %s:%u" % (self.host().hostname(), port))
            sock.connect((self.host().hostname(), port))
            sock.send('Hello World!')
            sock.close()
            rawc.expect('Connection from ')
            rawc.expect([':', ' '])
            my_ip = rawc.before
            rawc.expect('\n')
            log.debug(repr(my_ip))
            return my_ip
        except Exception as e:  # Looks like older nc does not support -v, lets fallback
            rawc.sendcontrol('c')  # to avoid incase nc command hangs
            my_ip = None
            ip = commands.getoutput("hostname -i")
            ip_lst = commands.getoutput("hostname -I").split(" ")
            # Let's validate the IP
            for item in ip_lst:
                if item == ip:
                    my_ip = ip
                    break
            if not my_ip:
                if len(ip_lst) == 1:
                    my_ip = ip_lst[0]
                else:
                    log.error("hostname -i does not provide valid IP, correct and proceed with installation")
        return my_ip

    def sys_enable_tpm(self):
        self.cv_IPMI.set_tpm_required()

    def sys_disable_tpm(self):
        self.cv_IPMI.clear_tpm_required()

    def sys_is_tpm_enabled(self):
        return self.cv_IPMI.is_tpm_enabled()

class OpTestFSPSystem(OpTestSystem):
    '''
    Implementation of an OpTestSystem for IBM FSP based systems (such as Tuleta and ZZ)

    Main differences are that some functions need to be done via the service processor
    rather than via IPMI due to differences in functionality.
    '''
    def __init__(self,
                 host=None,
                 bmc=None,
                 state=OpSystemState.UNKNOWN):
        bmc.fsp_get_console()
        super(OpTestFSPSystem, self).__init__(host=host,
                                              bmc=bmc,
                                              state=state)

    def sys_wait_for_standby_state(self, i_timeout=120):
        return self.cv_BMC.wait_for_standby(i_timeout)

    def wait_for_it(self, **kwargs):
        # Ensure IPMI console is open so not to miss petitboot
        sys_console = self.console.get_console()
        self.cv_BMC.wait_for_runtime()
        return super(OpTestFSPSystem, self).wait_for_it(**kwargs)

    def skiboot_log_on_console(self):
        return False

    def has_host_accessible_eeprom(self):
        return False

    def has_host_led_support(self):
        return True

    def has_centaurs_in_dt(self):
        return False

    def has_mtd_pnor_access(self):
        return False

class OpTestOpenBMCSystem(OpTestSystem):
    '''
    Implementation of an OpTestSystem for OpenBMC based platforms.

    Near all IPMI functionality is done via the OpenBMC REST interface instead.
    '''
    def __init__(self,
                 host=None,
                 bmc=None,
                 state=OpSystemState.UNKNOWN):
        # Ensure we grab host console early, in order to not miss
        # any messages
        self.console = bmc.get_host_console()
        super(OpTestOpenBMCSystem, self).__init__(host=host,
                                                  bmc=bmc,
                                                  state=state)
    # REST Based management
    def sys_inventory(self):
        self.rest.get_inventory()

    def sys_sensors(self):
        self.rest.sensors()

    def sys_bmc_state(self):
        self.rest.get_bmc_state()

    def sys_power_on(self):
        self.rest.power_on()

    def sys_power_off(self):
        self.rest.power_off()

    def sys_power_reset(self):
        self.rest.hard_reboot()

    def sys_power_cycle(self):
        self.rest.soft_reboot()

    def sys_power_soft(self):
        #self.rest.power_soft() currently rest command for softPowerOff failing
        self.rest.power_off()

    def sys_sdr_clear(self):
        try:
            # Try clearing all with DeleteAllAPI
            self.rest.clear_sel()
        except FailedCurlInvocation as f:
            # Which may not be implemented, so we try by ID instead
            self.rest.clear_sel_by_id()

    def sys_get_sel_list(self):
        self.rest.list_sel()

    def sys_sel_check(self):
        self.rest.list_sel()

    def sys_wait_for_standby_state(self, i_timeout=120):
        self.rest.wait_for_standby()
        return 0

    def wait_for_it(self, **kwargs):
        # Ensure IPMI console is open so not to miss petitboot
        sys_console = self.console.get_console()
        self.rest.wait_for_runtime()
        return super(OpTestOpenBMCSystem, self).wait_for_it(**kwargs)

    def sys_set_bootdev_setup(self):
        self.rest.set_bootdev_to_setup()

    def sys_set_bootdev_no_override(self):
        self.rest.set_bootdev_to_none()

    def sys_warm_reset(self):
        self.console.close()
        self.rest.bmc_reset()

    def sys_cold_reset_bmc(self):
        self.console.close()
        self.rest.bmc_reset()

    def sys_enable_tpm(self):
       self.rest.enable_tpm()

    def sys_disable_tpm(self):
       self.rest.disable_tpm()

    def sys_is_tpm_enabled(self):
        return self.rest.is_tpm_enabled()

class OpTestQemuSystem(OpTestSystem):
    '''
    Implementation of OpTestSystem for the Qemu Simulator

    Running against a simulator is rather different than running against a machine,
    but only in some *specific* cases. Many tests will run as-is, but ones that require
    a bunch of manipulation of the BMC will likely not.
    '''
    def __init__(self,
                 host=None,
                 bmc=None,
                 state=OpSystemState.UNKNOWN):
        # Ensure we grab host console early, in order to not miss
        # any messages
        self.console = bmc.get_host_console()
        if host.scratch_disk in [None,'']:
            host.scratch_disk = "/dev/sda"
        super(OpTestQemuSystem, self).__init__(host=host,
                                               bmc=bmc,
                                               state=state)

    def sys_wait_for_standby_state(self, i_timeout=120):
        self.bmc.power_off()
        return 0

    def sys_sdr_clear(self):
        return 0

    def sys_power_on(self):
        self.bmc.power_on()

    def get_my_ip_from_host_perspective(self):
        return "10.0.2.2"

    def has_host_accessible_eeprom(self):
        return False

    def has_mtd_pnor_access(self):
        return False
