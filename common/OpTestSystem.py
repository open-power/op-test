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

import OpTestIPMI # circular dependencies, use package
from OpTestFSP import OpTestFSP
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestHost import OpTestHost
from OpTestUtil import OpTestUtil
from OpTestSSH import ConsoleState as SSHConnectionState
from Exceptions import HostbootShutdown
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
                 state=OpSystemState.UNKNOWN):
        self.bmc = self.cv_BMC = bmc
        self.cv_HOST = host
        self.cv_IPMI = bmc.get_ipmi()
        self.rest = self.bmc.get_rest_api()
        self.console = self.bmc.get_host_console()
        self.util = OpTestUtil()

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
        if (self.state == OpSystemState.UNKNOWN):
          log.info("OpTestSystem CHECKING CURRENT STATE and TRANSITIONING for TARGET STATE: %s" % (state))
          self.state = self.run_DETECT(state)
          log.info("OpTestSystem CURRENT DETECTED STATE: %s" % (self.state))

        log.info("OpTestSystem START STATE: %s (target %s)" % (self.state, state))
        never_unknown = False
        while 1:
            if self.state != OpSystemState.UNKNOWN:
                never_unknown = True
            self.state = self.stateHandlers[self.state](state)
            log.info("OpTestSystem TRANSITIONED TO: %s" % (self.state))
            if self.state == state:
                break;
            if never_unknown and self.state == OpSystemState.UNKNOWN:
                raise 'System State transition failure: should not have progressed to UNKNOWN!'

    def run_DETECT(self, target_state):
        t = 0
        detect_state = OpSystemState.UNKNOWN
        never_rebooted = True
        while (detect_state == OpSystemState.UNKNOWN) and (t < 2):
          # two phases
          detect_state = self.detect_target(target_state, never_rebooted)
          never_rebooted = False
          t += 1
        return detect_state

    def detect_target(self, target_state, reboot):
        console = self.console.connect()
        # need to kick the buffer, login needs "r"
        console.send("\r")
        r = console.expect(["x=exit", "Petitboot", ".*#", "login:", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
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
        elif r == 2:
          detect_state = self.check_kernel()
          if (detect_state == target_state):
            return detect_state
          elif reboot:
            if detect_state in [OpSystemState.OS]:
              self.run_REBOOT(target_state)
              return OpSystemState.UNKNOWN
            elif detect_state in [OpSystemState.PETITBOOT]:
              self.exit_petitboot_shell()
              return OpSystemState.PETITBOOT
            elif detect_state in [OpSystemState.PETITBOOT_SHELL]:
              return OpSystemState.PETITBOOT_SHELL
            else:
              return OpSystemState.UNKNOWN
          else:
            return OpSystemState.UNKNOWN
        elif r == 3:
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
        elif (r == 4) or (r == 5):
          return OpSystemState.UNKNOWN

    def check_kernel(self):
        console = self.console.get_console()
        console.sendline("cat /proc/version | cut -d ' ' -f 3 | grep openpower")
        console.expect("\n")
        console.expect([".*#"])
        console.sendline("echo $?")
        console.expect("\n")
        console.expect([".*#"])
        echo_output = console.after
        try:
          echo_rc = int(echo_output.splitlines()[0])
        except Exception as e:
          # most likely cause is running while booting unknowlingly
          return OpSystemState.UNKNOWN
        if (echo_rc == 0):
          return OpSystemState.PETITBOOT_SHELL
        else:
          return OpSystemState.OS

    def wait_for_it(self, my_string=None, refresh=1, buffer_kicker=1, loop_max=50, threshold=1, timeout=10):
        console = self.console.get_console()
        previous_before = 'emptyfirst'
        x = 1
        reconnect_count = 0
        while (x <= loop_max):
            rc = console.expect([my_string, pexpect.TIMEOUT, pexpect.EOF], timeout)
            if (previous_before == console.before) and (rc != 0):
              # only attempt reconnect per threshold
              if (x % threshold == 0):
                reconnect_count += 1
                if isinstance(self.console, OpTestIPMI.IPMIConsole):
                  console = self.console.connect()
                  if buffer_kicker:
                    console.sendline("\r")
                  if refresh:
                    console.sendcontrol('l')
                  previous_before = 'emptyagain'
                else:
                  console = self.console.connect()
                  if buffer_kicker:
                    console.sendline("\r")
                  previous_before = 'emptyagain'
            else:
              previous_before = console.before
            if (rc == 0):
              break;
            else:
              x += 1
            if (x >= loop_max):
              raise Exception('Waiting for "{}" did not succeed, check the loop_max if needing to wait longer'
                              ' (number of reconnect attempts were {})'.format(my_string, reconnect_count))

    def run_REBOOT(self, target_state):
        # per console object detect stale indicator
        # used in conjunction with timeouts and loop_max
        if isinstance(self.console, OpTestIPMI.IPMIConsole):
          threshold = 3
        else:
          threshold = 6
        console = self.console.get_console()
        if (target_state == OpSystemState.PETITBOOT_SHELL) or (target_state == OpSystemState.PETITBOOT):
          self.sys_set_bootdev_setup()
          self.host_console_login()
        else:
          self.sys_set_bootdev_no_override()
        console.sendline('reboot')
        console.expect("\n")

        if (target_state == OpSystemState.OS):
          self.wait_for_it(my_string='login: ', threshold=threshold)
        else:
          self.wait_for_it(my_string='Petitboot', buffer_kicker=0, threshold=threshold)

    def run_UNKNOWN(self, state):
        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_OFF(self, state):
        if state == OpSystemState.OFF:
            return OpSystemState.OFF
        if state == OpSystemState.UNKNOWN:
            raise "Can't trasition to UNKNOWN state"

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
        if state == OpSystemState.OFF:
            self.sys_power_off()
            return OpSystemState.POWERING_OFF

        try:
            self.wait_for_petitboot()
        except pexpect.TIMEOUT:
            self.sys_sel_check()
            return OpSystemState.UNKNOWN
        except HostbootShutdown as e:
            log.error(e)
            self.sys_sel_check()
            return OpSystemState.UNKNOWN

        # Once reached to petitboot check for any SEL events
        self.sys_sel_check()
        return OpSystemState.PETITBOOT

    def run_PETITBOOT(self, state):
        if state == OpSystemState.PETITBOOT:
            return OpSystemState.PETITBOOT
        if state == OpSystemState.PETITBOOT_SHELL:
            self.petitboot_exit_to_shell()
            return OpSystemState.PETITBOOT_SHELL

        if state == OpSystemState.OFF:
            self.sys_power_off()
            return OpSystemState.POWERING_OFF

        if state == OpSystemState.OS:
            self.wait_for_kexec()
            return OpSystemState.BOOTING

        raise 'Invalid state transition'

    def run_PETITBOOT_SHELL(self, state):
        if state == OpSystemState.PETITBOOT_SHELL:
            console = self.console.get_console()
            console.sendcontrol('l')
            return OpSystemState.PETITBOOT_SHELL

        if state == OpSystemState.PETITBOOT:
            self.exit_petitboot_shell()
            return OpSystemState.PETITBOOT

        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_BOOTING(self, state):
        rc = self.wait_for_login()
        if rc != BMC_CONST.FW_FAILED:
            # Wait for ip to ping as we run host commands immediately
            self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            return OpSystemState.OS
        return OpSystemState.UNKNOWN

    def run_OS(self, state):
        if state == OpSystemState.OS:
            return OpSystemState.OS
        self.ipmiDriversLoaded = False
        self.sys_power_off()
        return OpSystemState.POWERING_OFF

    def run_POWERING_OFF(self, state):
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

    # Login to the host on the console
    # This will behave correctly even if already logged in
    def host_console_login(self):
        # we act on the raw pexpect console
        l_con = self.bmc.get_host_console().get_console()
        l_user = self.cv_HOST.username()
        l_pwd = self.cv_HOST.password()

        l_con.send("\r")
        l_rc = l_con.expect_exact(BMC_CONST.IPMI_CONSOLE_EXPECT_ENTER_OUTPUT, timeout=120)
        if l_rc == BMC_CONST.IPMI_CONSOLE_EXPECT_LOGIN:
            l_con.sendline(l_user)
            l_rc = l_con.expect([r"[Pp]assword:", pexpect.TIMEOUT, pexpect.EOF], timeout=120)
            time.sleep(0.5)
            if l_rc == BMC_CONST.IPMI_CONSOLE_EXPECT_PASSWORD:
                l_con.sendline(l_pwd)
            else:
                l_msg = "Error: host login failed"
                raise OpTestError(l_msg)
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_PETITBOOT:
            l_msg = "Error: system is at petitboot"
            raise OpTestError(l_msg)
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_RANDOM_STATE:
            l_msg = "Error: system is in random state"
            raise OpTestError(l_msg)
        elif l_rc in ["#"]:
            # already at root prompt, success!
            return
        elif l_rc in [pexpect.TIMEOUT, pexpect.EOF]:
            log.error(l_con.before)
            raise "Timeout/EOF waiting for SOL response"
        elif l_rc in ["$"]:
            pass # fallthrough and sudo into a root shell
        l_con.send("\r")
        l_rc = l_con.expect_exact(['$','#'])
        if l_rc == 0:
            l_con.sendline('sudo -s')
            l_con.expect("password for")
            l_con.sendline(l_pwd)
            self.host_console_unique_prompt()
        elif l_rc != 1:
            raise Exception("Invalid response to newline. expected $ or # prompt, got: %s" % (l_con.before))

        return BMC_CONST.FW_SUCCESS

    def host_console_unique_prompt(self):
        # We do things to the raw pexpect here
        # Must be logged in or at petitboot shell
        p = self.bmc.get_host_console().get_console()
        p.sendcontrol('l')
        p.expect(r'.+#')
        p.sendline('PS1=[console-pexpect]\#')
        p.expect("\n") # from us, because echo
        l_rc = p.expect("\[console-pexpect\]#$")
        if l_rc == 0:
            log.debug("Shell prompt changed")
        else:
            raise Exception("Failed during change of shell prompt")


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

    def sys_ipmi_ipl_wait_for_login(self,i_timeout=10):
        l_con = self.console.get_console()
        try:
            rc = self.cv_IPMI.ipmi_ipl_wait_for_login(l_con, i_timeout)
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
    # @brief This function will check for system status and wait for
    #        FW and Host OS Boot progress to complete.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def sys_check_host_status_v1(self):
        if int(self.cv_IPMI.ipmi_ipl_wait_for_working_state_v1()) == BMC_CONST.FW_SUCCESS:
            log.info("System booted to working state")
        else:
            log.info("There is no Host Status sensor....")
        if int(self.cv_IPMI.ipmi_wait_for_os_boot_complete_v1()) == BMC_CONST.FW_SUCCESS:
            log.info("System booted to Host OS")
        else:
            log.info("There is no OS Boot sensor...")

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



    ###########################################################################
    # CODE-UPDATE INTERFACES
    ###########################################################################

    ##
    # @brief Update the BMC fw image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_outofband_fw_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Update the BMC pnor image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_outofband_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Update the BMC fw and pnor image using hpm file
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_outofband_fwandpnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_IPMI.ipmi_code_update(i_image,BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE)
            return self.sys_bmc_power_on_validate_host()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Update the BMC fw using hpm file using HOST
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_fw_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_FW_IMAGE_UPDATE)
            self.cv_IPMI.ipmi_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS



    ##
    # @brief Update the BMC pnor using hpm file using HOST
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_pnor_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_PNOR_IMAGE_UPDATE)
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC fw and pnor using hpm file using Host
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_bmc_inband_fwandpnor_update_hpm(self,i_image):

        try:
            #TODO: remove power_off() once DEFECT:SW325477 is fixed
            self.cv_IPMI.ipmi_power_off()
            self.cv_IPMI.ipmi_cold_reset()
            l_rc = self.sys_bmc_power_on_validate_host()
            if(l_rc != BMC_CONST.FW_SUCCESS):
                return BMC_CONST.FW_FAILED
            self.cv_IPMI.ipmi_preserve_network_setting()
            self.cv_HOST.host_code_update(i_image, BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE)
            self.cv_HOST.host_cold_reset()
        except OpTestError as e:
            self.sys_cold_reset_bmc()
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the PNOR image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_pnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.bmc.cv_WEB.web_update_hpm(i_image,BMC_CONST.UPDATE_PNOR)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_bmc_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.bmc.cv_WEB.web_update_hpm(i_image,BMC_CONST.UPDATE_BMC)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Update the BMC and PNOR image using hpm file through web GUI
    #
    # @param i_image HPM file image including location
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED or BMC_CONST.FW_INVALID
    #
    def sys_bmc_web_bmcandpnor_update_hpm(self,i_image):

        try:
            self.cv_IPMI.ipmi_power_off()
            self.bmc.cv_WEB.web_update_hpm(i_image, BMC_CONST.UPDATE_BMCANDPNOR)
        except OpTestError as e:
            if(e.args[0] == BMC_CONST.ERROR_SELENIUM_HEADLESS):
                return BMC_CONST.FW_INVALID
            return BMC_CONST.FW_FAILED

        return BMC_CONST.FW_SUCCESS

    ###########################################################################
    # Energy Scale
    ###########################################################################

    ##
    # @brief Sets power limit of BMC
    #
    # @param i_powerlimit @type int: power limit to be set at BMC
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_power_limit(self, i_powerlimit):
        try:
            self.cv_IPMI.ipmi_power_status()
            self.cv_IPMI.ipmi_set_power_limit(i_powerlimit)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Gets the Power Limit
    #
    # @return l_powerlimit @type int: current power limit on bmc
    #         or BMC_CONST.FW_FAILED
    #
    def sys_get_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_get_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Activates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_activate_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_activate_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Dectivates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_deactivate_power_limit(self):
        try:
            return self.cv_IPMI.ipmi_deactivate_power_limit()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Enable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    def sys_enable_all_occ_sensor(self):
        try:
            return self.cv_IPMI.ipmi_enable_all_occ_sensor()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Disable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    def sys_disable_all_occ_sensor(self):
        try:
            return self.cv_IPMI.ipmi_disenable_all_occ_sensor()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc CPU sensors
    # example (CPU Core Func 1|0x0|discrete|0x8080|na|na|na|na|na|na)
    #         (CPU Core Temp 1|42.000|degrees C|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return CPU sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_cpu_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_CPU)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc Processor sensors
    # example (Mem Proc0 Pwr|0.000|Watts|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return Processor sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_processor_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_PROCESSOR)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc Fan sensors
    # example(Fan 1 |9000.000|RPM|ok|0.000|0.000|0.000|16500.000|16500.000|16500.000)
    #
    # @return Fan sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_fan_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_FAN)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read Bmc DIMM sensors
    # example(DIMM Func 0|0x0|discrete|0x4080|na|na|na|na|na|na)
    #        (DIMM Temp 0|27.000|degrees C|ok|0.000|0.000|0.000|255.000|255.000|255.000)
    #
    # @return Fan sensor reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_dimm_occ_sensor(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_DIMM)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read All BMC sensors
    #
    # @return BMC sensor readings if successful or
    #         return BMC_CONST.FW_FAILED
    def read_sensor_list(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_CHECK_SENSOR_LIST)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc power levels
    # example (Instantaneous power reading:                   297 Watts
    #          Minimum during sampling period:                284 Watts
    #          Maximum during sampling period:                317 Watts
    #          Average power reading over sample period:      297 Watts
    #          IPMI timestamp:                           Tue Nov 24 09:46:03 2015
    #          Sampling period:                          00010000 Milliseconds
    #          Power reading state is:                   activated)
    #
    # @return Power reading if successful or
    #         return BMC_CONST.FW_FAILED
    def read_power_level(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_GET_POWER)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Read Bmc temperature levels of CPU and baseboard
    # example (Entity ID Entity Instance              Temp. Readings
    #         (CPU temperature sensors(41h)             0       +28 C)
    #         (Baseboard temperature sensors(42h)       0       +22 C)
    #
    # @return Operating temperature readings if successful or
    #         return BMC_CONST.FW_FAILED
    def read_temperature_level(self):
        try:
            return self.cv_IPMI._ipmitool_cmd_run(
                self.cv_IPMI.cv_baseIpmiCmd + BMC_CONST.OP_GET_TEMP)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Read OCC status
    #
    # @return OCC status if successful or
    #         return BMC_CONST.FW_FAILED
    def read_occ_status(self):
        try:
            return self.cv_IPMI.ipmi_get_occ_status()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief clears the gard records using the gard tool from OS
    #
    # @param i_gard_dir @type string: directory where gard is installed
    #
    # return BMC.CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_clear_gard_records(self, i_gard_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            self.cv_HOST.host_clear_gard_records(i_gard_dir)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Lists all the gard records using the gard tool from OS
    #
    # @param i_gard_dir @type string: directory where gard is installed
    #
    # return gard records or BMC_CONST.FW_FAILED
    #
    def sys_list_gard_records(self, i_gard_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_list_gard_records(i_gard_dir)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief reads getscom data
    #
    # @param i_xscom_dir @type string: directory where getscom is installed
    #
    # return getscom data or BMC_CONST.FW_FAILED
    #
    def sys_read_getscom_data(self, i_xscom_dir):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_read_getscom_data(i_xscom_dir)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief injects error using putscom
    #
    # @param i_xscom_dir @type string: directory where putscom is installed
    # @param i_error @type string: error to be injected including the location
    #
    # @return output generated after executing putscom command or BMC_CONST.FW_FAILED
    #
    def sys_putscom(self, i_xscom_dir, i_error):
        try:
            self.sys_bmc_power_on_validate_host()
            return self.cv_HOST.host_putscom(i_xscom_dir, i_error)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


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

    ##
    # @brief This function gets the sdr list
    #
    # @return @type string: sdr list or BMC_CONST.FW_FAILED
    #
    def sys_get_sdr_list(self):
        try:
            return self.cv_IPMI.ipmi_get_sdr_list()
        except OpTestError as e:
            return BMC_CONST.FW_FAILED


    ##
    # @brief Set BMC to boot pnor from primary side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_pnor_boot_primary(self, i_bios_sensor, i_boot_sensor):

        try:
            self.cv_IPMI.ipmi_set_pnor_primary_side(i_bios_sensor,i_boot_sensor)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Set BMC to boot pnor from golden side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # return BMC_CONST.FW_SUCCESS or BMC_CONST.FW_FAILED
    #
    def sys_set_pnor_boot_golden(self, i_bios_sensor, i_boot_sensor):

        try:
            self.cv_IPMI.ipmi_set_pnor_golden_side(i_bios_sensor,i_boot_sensor)
            return BMC_CONST.FW_SUCCESS
        except OpTestError as e:
            return BMC_CONST.FW_FAILED

    ##
    # @brief Determines which side of BMC and PNOR chip is active
    #
    # @return l_bmc_active and l_pnor_active @type string or return FWConstants.FW_FAILED
    #
    def sys_active_chip_side(self):
        try:
            l_bmc_active, l_pnor_active = self.cv_IPMI.ipmi_get_side_activated()
            return l_bmc_active, l_pnor_active
        except OpTestError as e:
            return BMC_CONST.FW_FAILED,BMC_CONST.FW_FAILED



    ###########################################################################
    # IPMI Console interfaces
    ###########################################################################

    ##
    # @brief It will get the ipmi sol console
    #
    # @return l_con @type Object: it is a object of pexpect.spawn class or raise OpTestError
    #
    def sys_get_ipmi_console(self):
        self.l_con = self.bmc.get_host_console()
        return self.l_con

    ##
    # @brief This function is used to close ipmi console
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or return BMC_CONST.FW_FAILED
    #
    def sys_ipmi_close_console(self, i_con):
        try:
            l_con = i_con
            self.cv_IPMI.ipmi_close_console(l_con)
        except OpTestError as e:
            return BMC_CONST.FW_FAILED
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function is used to boot the system up to petitboot
    #        So any petitboot related test cases can use this function
    #        to setupt the petitboot
    #
    # @param i_con @type Object: it is a object of pexpect.spawn class
    #                            this is the active ipmi sol console object
    #
    # @return BMC_CONST.FW_SUCCESS or return BMC_CONST.FW_FAILED
    #
    def sys_ipmi_boot_system_to_petitboot(self):
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == 0:
            log.info("System is in standby/Soft-off state")
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        self.cv_IPMI.ipmi_set_boot_to_petitboot()
        self.cv_IPMI.ipmi_power_on()

        self.wait_for_petitboot()
        self.petitboot_exit_to_shell()

    def wait_for_petitboot(self):
        console = self.console.get_console()
        try:
            # Wait for petitboot (for a *LOOONNNG* time due to verbose IPLs)
            seen = 0
            r = 1
            t = 100
            while seen < 2 and t:
                # TODO check for forward progress
                r = console.expect(['x=exit', 'Petitboot', pexpect.TIMEOUT, '[0-9.]+\|IPMI: shutdown requested'], timeout=10)
                if r == 2 and t == 0:
                    raise pexpect.TIMEOUT
                if r == 3:
                    raise HostbootShutdown()
                if r in [0,1]:
                    seen = seen + 1
                else:
                    t = t - 1

            # there will be extra things in the pexpect buffer here
        except pexpect.TIMEOUT as e:
            log.error("Timeout waiting for Petitboot! error: {}".format(str(e)))
            raise e

    def wait_for_kexec(self):
        console = self.console.get_console()
        # Wait for kexec to start
        console.expect(['Performing kexec','kexec_core: Starting new kernel'], timeout=60)

    def petitboot_exit_to_shell(self):
        console = self.console.get_console()
        retry_count = 0
        while retry_count < 3:
            retry_count = retry_count + 1
            # Exiting to petitboot shell
            console.sendcontrol('l')
            r = console.expect(['x=exit','#',pexpect.TIMEOUT])
            if r == 0:
                console.send('x')
                console.expect('Exiting petitboot')
                console.expect('#')
                break
            elif r == 1:
                console.sendcontrol('c')
                console.expect('#')
                break
            else:
                continue
        console.sendcontrol('u') # remove any characters between cursor and start of line
        # we should have consumed everything in the buffer now.
        log.debug(console)

    def exit_petitboot_shell(self):
        console = self.console.get_console()
        console.sendcontrol('l')
        console.sendline('exit')
        self.wait_for_petitboot()

    def wait_for_login(self, timeout=600):
        console = self.console.get_console()
        console.sendline('')
        console.expect('login: ', timeout)

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

    def wait_for_petitboot(self):
        # Ensure IPMI console is open so not to miss petitboot
        console = self.console.get_console()
        self.cv_BMC.wait_for_runtime()
        return super(OpTestFSPSystem, self).wait_for_petitboot()

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

    def wait_for_petitboot(self):
        # Ensure IPMI console is open so not to miss petitboot
        console = self.console.get_console()
        self.rest.wait_for_runtime()
        return super(OpTestOpenBMCSystem, self).wait_for_petitboot()

    def sys_set_bootdev_setup(self):
        self.rest.set_bootdev_to_setup()

    def sys_set_bootdev_no_override(self):
        self.rest.set_bootdev_to_none()

    def sys_warm_reset(self):
        self.rest.bmc_reset()

    def sys_cold_reset_bmc(self):
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
