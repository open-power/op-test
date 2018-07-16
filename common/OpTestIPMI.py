#!/usr/bin/env python2
# encoding=utf8
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestIPMI.py $
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
import pexpect
import sys
import re
import commands
#from subprocess import check_output
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestUtil import OpTestUtil
from OpTestSystem import OpTestSystem,OpSystemState
from Exceptions import CommandFailed
from Exceptions import BMCDisconnected
from common import OPexpect

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class IPMITool():
    def __init__(self, method='lanplus', binary='ipmitool',
                 ip=None, username=None, password=None, logfile=sys.stdout):
        self.method = 'lanplus'
        self.ip = ip
        self.username = username
        self.password = password
        self.binary = binary
        self.logfile = logfile

    def binary_name(self):
        return self.binary

    def arguments(self):
        s = ' -H %s -I %s' % (self.ip, self.method)
        if self.username:
            s += ' -U %s' % (self.username)
        if self.password:
            s += ' -P %s' % (self.password)
        s += ' '
        return s

    def run(self, cmd, background=False, cmdprefix=None):
        if cmdprefix:
            cmd = cmdprefix + self.binary + self.arguments() + cmd
        else:
            cmd = self.binary + self.arguments() + cmd
        log.debug(cmd)
        if background:
            try:
                child = subprocess.Popen(cmd, shell=True)
            except:
                l_msg = "Ipmitool Command Failed: {}".format(cmd)
                log.error(l_msg)
                raise OpTestError(l_msg)
            return child
        else:
            # TODO - need python 2.7
            # output = check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            try:
                cmd = subprocess.Popen(cmd,stderr=subprocess.STDOUT,
                                       stdout=subprocess.PIPE,shell=True)
            except:
                l_msg = "Ipmitool Command Failed: {}".format(cmd)
                log.error(l_msg)
                raise OpTestError(l_msg)
            output = cmd.communicate()[0]
            return output

class pUpdate():
    def __init__(self, method='lan', binary='pUpdate',
                 ip=None, username=None, password=None):
        self.method = 'lan'
        self.ip = ip
        self.username = username
        self.password = password
        self.binary = binary

    def set_binary(self, binary):
        self.binary = binary

    def binary_name(self):
        return self.binary

    def arguments(self):
        s = ' -h %s -i %s' % (self.ip, self.method)
        if self.username:
            s += ' -u %s' % (self.username)
        if self.password:
            s += ' -p %s' % (self.password)
        s += ' '
        return s

    def run(self, cmd, background=False, cmdprefix=None):
        if cmdprefix:
            cmd = cmdprefix + self.binary + self.arguments() + cmd
        else:
            cmd = self.binary + self.arguments() + cmd
        log.debug(cmd)
        if background:
            try:
                child = subprocess.Popen(cmd, shell=True)
            except:
                l_msg = "pUpdate Command Failed: {}".format(cmd)
                log.error(l_msg)
                raise OpTestError(l_msg)
            return child
        else:
            # TODO - need python 2.7
            # output = check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            try:
                cmd = subprocess.Popen(cmd,stderr=subprocess.STDOUT,
                                       stdout=subprocess.PIPE,shell=True)
            except:
                l_msg = "pUpdate Command Failed: {}".format(cmd)
                log.error(l_msg)
                raise OpTestError(l_msg)
            output = cmd.communicate()[0]
            log.debug(output)
            return output

class IPMIConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

def set_system_to_UNKNOWN_BAD(system):
    s = system.get_state()
    system.set_state(OpSystemState.UNKNOWN_BAD)
    return s

class IPMIConsole():
    def __init__(self, ipmitool=None, delaybeforesend=None):
        self.ipmitool = ipmitool
        self.state = IPMIConsoleState.DISCONNECTED
        self.delaybeforesend = delaybeforesend
        self.system = None

    def set_system(self, system):
        self.system = system

    def terminate(self):
        if self.state == IPMIConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = IPMIConsoleState.DISCONNECTED

    def close(self):
        if self.state == IPMIConsoleState.DISCONNECTED:
            return
        try:
            if not self.sol.isalive():
                log.warning("IPMI SOL Console is already disconnected")
                pass
            self.sol.send("\r")
            self.sol.send('~.')
            self.sol.expect('[terminated ipmitool]')
            self.sol.close()
        except pexpect.ExceptionPexpect:
            raise OpTestError("IPMI: failed to close ipmi console")

        self.sol.terminate()
        self.state = IPMIConsoleState.DISCONNECTED

    def connect(self):
        if self.state == IPMIConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = IPMIConsoleState.DISCONNECTED

        log.info("#IPMI SOL CONNECT")
        try:
            self.ipmitool.run('sol deactivate')
        except OpTestError:
            log.info('SOL already deactivated')

        cmd = self.ipmitool.binary_name() + self.ipmitool.arguments() + ' sol activate'
        log.debug(cmd)
        solChild = OPexpect.spawn(cmd,
                                  failure_callback=set_system_to_UNKNOWN_BAD,
                                  failure_callback_data=self.system)
        self.state = IPMIConsoleState.CONNECTED
        self.sol = solChild
        solChild.logfile_read = OpTestLogger.FileLikeLogger(log)
        if self.delaybeforesend:
	    self.sol.delaybeforesend = self.delaybeforesend
        self.sol.expect_exact('[SOL Session operational.  Use ~? for help]')
        # we pause for a moment to allow ipmitool to catch up with
        # itself and to start accepting input
        time.sleep(0.2)
        return solChild

    def get_console(self):
        if self.state == IPMIConsoleState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.sol.isalive()):
            log.warning('# Reconnecting')
            if (count > 0):
                time.sleep(BMC_CONST.IPMI_SOL_ACTIVATE_TIME)
            self.connect()
            count += 1
            if count > 120:
                raise "IPMI: not able to get sol console"

        return self.sol

    def mc_reset(self):
        self.ipmitool.run('mc reset cold')
        retries = 0
        log.info('# Waiting for BMC reboot to complete...')
        time.sleep(10)
        while True:
            try:
                subprocess.check_call(["ping", self.cv_bmcIP, "-c1"])
                break
            except subprocess.CalledProcessError as e:
                log.info("Ping return code: ", e.returncode, "retrying...")
                retries += 1
                time.sleep(10)

            if retries > 10:
                l_msg = "Error. BMC is not responding to pings"
                log.error(l_msg)
                raise OpTestError(l_msg)



    def run_command(self, command, timeout=60):
        console = self.get_console()
        BMC_DISCONNECT = 'SOL session closed by BMC'
        try:
            console.sendline(command)
            console.expect("\n") # from us
            rc = console.expect([BMC_DISCONNECT, "\[console-pexpect\]#$"], timeout=timeout)
            if rc == 0:
                raise BMCDisconnected(BMC_DISCONNECT)
            output = console.before
            console.sendline("echo $?")
            rc = console.expect([BMC_DISCONNECT, "\n"]) # from us
            if rc == 0:
                raise BMCDisconnected(BMC_DISCONNECT)
            rc = console.expect([BMC_DISCONNECT, "\[console-pexpect\]#$"], timeout=timeout)
            if rc == 0:
                raise BMCDisconnected(BMC_DISCONNECT)
            exitcode = int(console.before)
            log.debug("# LAST COMMAND EXIT CODE %d (%s)" % (exitcode, repr(console.before)))
        except pexpect.TIMEOUT as e:
            log.error(e)
            log.error("# TIMEOUT waiting for command to finish.")
            log.error("# Attempting to control-c")
            try:
                console.sendcontrol('c')
                rc = console.expect([BMC_DISCONNECT, "\[console-pexpect\]#$"], 10)
                if rc == 0:
                    log.error("# BMC Disconnect while cancelling timed-out command")
                    log.error("# Failing test, disconnecting/reconnecting")
                    self.terminate()
                    raise CommandFailed("ipmitool", BMC_DISCONNECT, -1)
                if rc == 1:
                    raise CommandFailed(command, "TIMEOUT", -1)
            except pexpect.TIMEOUT:
                log.info("# Timeout trying to kill timed-out command.")
                log.info("# Failing current command and attempting to continue")
                self.terminate()
                raise CommandFailed("ipmitool", "timeout", -1)
            raise e
        except BMCDisconnected as e:
            log.error("# %s" % str(e))
            log.error("# We can possibly continue...")
            log.error("# Failing current command and attempting to continue")
            self.terminate()
            self.connect()
            console = self.get_console()
            log.info("# On reconnect, attempt to cancel last command (ctrl-c)")
            # Note: this is a terrible idea. If BMC vendors created reliable
            # SoL implementations this kind of crap wouldn't be needed.
            # This is incorrect on so many levels it's not funny. For a start,
            # we really don't want to send random control characters during
            # boot!
            console.sendcontrol('c')
            try:
                rc = console.expect([BMC_DISCONNECT,
                                     "\[console-pexpect\]#$"], 10)
                if rc == 0:
                    self.terminate()
                    raise BMCDisconnected(BMC_DISCONNECT)
            except pexpect.TIMEOUT:
                log.error("# No response from BMC... trying 'mc reset cold'")
                self.mc_reset()
                self.terminate()
                self.connect()
                console = self.get_console()
                console.sendcontrol('c')
            raise CommandFailed("ipmitool", BMC_DISCONNECT, -1)

        if rc == 1:
            res = output
            res = res.splitlines()
            if exitcode != 0:
                raise CommandFailed(command, res, exitcode)
            return res
        else:
            res = console.before
            res = res.split(command)
            return res[-1].splitlines()

    # This command just runs and returns the ouput & ignores the failure
    def run_command_ignore_fail(self, command, timeout=60):
        try:
            output = self.run_command(command, timeout)
        except CommandFailed as cf:
            output = cf.output
        return output

class OpTestIPMI():
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPwd, logfile=sys.stdout, host=None, delaybeforesend=None):
        self.cv_bmcIP = i_bmcIP
        self.cv_bmcUser = i_bmcUser
        self.cv_bmcPwd = i_bmcPwd
        self.logfile = logfile
        self.ipmitool = IPMITool(method='lanplus',
                                 ip=i_bmcIP,
                                 username=i_bmcUser,
                                 password=i_bmcPwd,
                                 logfile=logfile)
        self.pUpdate = pUpdate(method='lan',
                               ip=i_bmcIP,
                               username=i_bmcUser,
                               password=i_bmcPwd)
        self.console = IPMIConsole(ipmitool=self.ipmitool,
                                   delaybeforesend=delaybeforesend)
        self.util = OpTestUtil()
        self.host = host

    def set_system(self, system):
        self.console.set_system(system)

    # Get the IPMIConsole object, to run commands on the host etc.
    def get_host_console(self):
        return self.console

    ##
    # @brief This function clears the sensor data
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_sdr_clear(self):
        output = self.ipmitool.run('sel clear')
        if 'Clearing SEL' in output:
            # FIXME: This code should instead check for 'erasure completed'
            #        and the status of the erasure, rather than this crude loop
            retries = 20
            while (retries > 0):
                output = self.ipmitool.run('sel elist')
                if 'no entries' in output:
                    return BMC_CONST.FW_SUCCESS
                else:
                    l_msg = "Sensor data still has entries!"
                    log.error(l_msg)
                    retries -= 1
                    if (retries == 0):
                        raise OpTestError(l_msg)
                    time.sleep(1)
        else:
            l_msg = "Clearing the sensor data Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power off ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_off(self):
        output = self.ipmitool.run('chassis power off')
        if 'Down/Off' in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power OFF Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power on ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_on(self):
        output = self.ipmitool.run('chassis power on')
        if 'Up/On' in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power ON Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)


    ##
    # @brief This function sends the chassis power soft ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_soft(self):
        output = self.ipmitool.run('chassis power soft')
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if "Chassis Power Control: Soft" in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Soft Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)

    ##
    # @brief This function sends the chassis power cycle ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_cycle(self):
        output = self.ipmitool.run('chassis power cycle')
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        if "Chassis Power Control: Cycle" in output:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power Cycle Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)

    ##
    # @brief This function sends the chassis power reset ipmitool command
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_power_reset(self):
        r = self.ipmitool.run('chassis power reset')
        if not BMC_CONST.CHASSIS_POWER_RESET in r:
            raise Exception("IPMI 'chassis power reset' failed: %s " % r)


    ##
    # @brief This function sends the chassis power diag ipmitool command
    #
    def ipmi_power_diag(self):
        r = self.ipmitool.run('chassis power diag')
        if not "Chassis Power Control: Diag" in r:
            raise Exception("IPMI 'chassis power diag' failed: %s " % r)


    ##
    # @brief This function starts the sol capture and waits for the IPL to end. The
    #        marker for IPL completion is the Host Status sensor which reflects the ACPI
    #        power state of the system.  When it reads S0/G0: working it means that the
    #        petitboot is has began loading.  The overall timeout for the IPL is defined
    #        in the test configuration options.'''
    #
    # @param timeout @type int: The number of minutes to wait for IPL to complete,
    #       i.e. How long to poll the ACPI sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipl_wait_for_working_state(self, timeout=10):
        sol = self.console.get_console()
        timeout = time.time() + 60*timeout
        cmd = 'sdr elist |grep \'Host Status\''
        output = self.ipmitool.run(cmd)
        if not "Host Status" in output:
            return BMC_CONST.FW_PARAMETER
        while True:
            output = self.ipmitool.run(cmd)
            if 'S0/G0: working' in output:
                log.debug("Host Status is S0/G0: working, IPL finished")
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(5)

        try:
            self.ipmitool.run('sol deactivate')
            self.console.terminate()
        except subprocess.CalledProcessError:
            l_msg = 'SOL already deactivated'
            log.error(l_msg)
            self.console.terminate()
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function waits for the IPL to end. The marker for IPL completion is the
    #        Host Status sensor which reflects the ACPI power state of the system.  When it
    #        reads S0/G0: working it means that the petitboot is has began loading.
    #
    # @param timeout @type int: The number of minutes to wait for IPL to complete,
    #       i.e. How long to poll the ACPI sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_ipl_wait_for_working_state_v1(self, timeout=10):
        timeout = time.time() + 60*timeout
        cmd = 'sdr elist |grep \'Host Status\''
        output = self.ipmitool.run(cmd)
        if not "Host Status" in output:
            return BMC_CONST.FW_PARAMETER

        while True:
            if 'S0/G0: working' in output:
                log.debug("Host Status is S0/G0: working, IPL finished")
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(5)
            output = self.ipmitool.run(cmd)
        return BMC_CONST.FW_SUCCESS

    def ipmi_ipl_wait_for_login(self, l_con, timeout=10):
        l_rc = l_con.expect_exact(BMC_CONST.IPMI_SOL_CONSOLE_ACTIVATE_OUTPUT, timeout=120)
        if l_rc == 0:
            log.info("IPMI: sol console activated")
        else:
            l_msg = "Error: not able to get IPMI console"
            raise OpTestError(l_msg)
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        l_con.send("\r")
        time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        l_rc = l_con.expect_exact(BMC_CONST.IPMI_CONSOLE_EXPECT_ENTER_OUTPUT, timeout=120)
        if l_rc == BMC_CONST.IPMI_CONSOLE_EXPECT_LOGIN:
            return BMC_CONST.FW_SUCCESS
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_PETITBOOT:
            return BMC_CONST.FW_SUCCESS
        elif l_rc in BMC_CONST.IPMI_CONSOLE_EXPECT_RANDOM_STATE:
            l_msg = "Error: system is in random state"
            raise OpTestError(l_msg)
        else:
            l_con.expect(pexpect.TIMEOUT, timeout=30)
            log.error(l_con.before)
            raise OpTestError("Timeout waiting for IPL")
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function waits for system to reach standby state or soft off. The
    #        marker for standby state is the Host Status sensor which reflects the ACPI
    #        power state of the system.  When it reads S5/G2: soft-off it means that the
    #        system reached standby or soft-off state. The overall timeout for the standby is defined
    #        in the test configuration options.'''
    #
    # @param i_timeout @type int: The number of seconds to wait for system to reach standby,
    #       i.e. How long to poll the ACPI sensor for soft-off state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_standby_state(self, i_timeout=120):
        l_timeout = time.time() + i_timeout
        l_cmd = ' power status '
        wait_for = 'Chassis Power is off'
        while True:
            l_output = self.ipmitool.run(l_cmd)
            if wait_for in l_output:
                log.debug("Host power is off, system reached standby")
                break
            if time.time() > l_timeout:
                l_msg = "Standby timeout"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_STANDBY_DELAY)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function waits for the Host OS Boot(IPL) to end. The
    #        marker for IPL completion is the OS Boot sensor which reflects status
    #        of host OS Boot. When it reads boot completed it means that the
    #        Host OS Booted successfully.  The overall timeout for the IPL is defined
    #        in the test configuration options.'''
    #
    # @param i_timeout @type int: The number of minutes to wait for IPL to complete or Boot time,
    #       i.e. How long to poll the OS Boot sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_os_boot_complete(self, i_timeout=10):
        l_timeout = time.time() + 60*i_timeout
        l_cmd = 'sdr elist |grep \'OS Boot\''
        output = self.ipmitool.run(l_cmd)
        if not "OS Boot" in output:
            return BMC_CONST.FW_PARAMETER
        while True:
            l_output = self.ipmitool.run(l_cmd)
            if BMC_CONST.OS_BOOT_COMPLETE in l_output:
                log.debug("Host OS is booted")
                break
            if time.time() > l_timeout:
                l_msg = "IPL timeout"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function waits for the Host OS Boot(IPL) to end. The
    #        marker for IPL completion is the OS Boot sensor which reflects status
    #        of host OS Boot. When it reads boot completed it means that the
    #        Host OS Booted successfully.
    #
    # @param i_timeout @type int: The number of minutes to wait for IPL to complete or Boot time,
    #       i.e. How long to poll the OS Boot sensor for working state before giving up.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_os_boot_complete_v1(self, i_timeout=10):
        l_timeout = time.time() + 60*i_timeout
        l_cmd = 'sdr elist |grep \'OS Boot\''
        l_output = self.ipmitool.run(l_cmd)
        if not "OS Boot" in l_output:
            return BMC_CONST.FW_PARAMETER

        while True:
            if BMC_CONST.OS_BOOT_COMPLETE in l_output:
                log.debug("Host OS is booted")
                break
            if time.time() > l_timeout:
                l_msg = "IPL timeout"
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            l_output = self.ipmitool.run(l_cmd)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function dumps the sel log and looks for specific hostboot error
    #        log string
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_sel_check(self, i_string="Transition to Non-recoverable"):
        output = self.ipmitool.run('sel elist')

        if self.logfile:
            for line in output:
                self.logfile.write(line)

        if i_string in output:
            raise OpTestError('Error log(s) detected during IPL: %s' % output)
        else:
            return BMC_CONST.FW_SUCCESS


    ##
    # @brief Determines the power status of the bmc
    #
    # @return l_output @type string: Power status of bmc
    #         "Chassis Power is on" or "Chassis Power is off"
    #
    def ipmi_power_status(self):
        l_output = self.ipmitool.run('chassis power status')
        if('on' in l_output):
            return BMC_CONST.CHASSIS_POWER_ON
        elif('off' in l_output):
            return BMC_CONST.CHASSIS_POWER_OFF
        else:
            raise OpTestError("Can't recognize chassis power status: " + str(l_output))

    ##
    # @brief Performs a cold reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_cold_reset(self):

        l_initstatus = self.ipmi_power_status()
        log.debug("Applying Cold reset.")
        rc = self.ipmitool.run(BMC_CONST.BMC_COLD_RESET)
        if BMC_CONST.BMC_PASS_COLD_RESET in rc:
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
            self.util.PingFunc(self.cv_bmcIP, BMC_CONST.PING_RETRY_FOR_STABILITY)
            self.ipmi_wait_for_bmc_runtime()
            l_finalstatus = self.ipmi_power_status()
            if (l_initstatus != l_finalstatus):
                log.debug('initial status ' + str(l_initstatus))
                log.debug('final status ' + str(l_finalstatus))
                log.debug('Power status changed during cold reset')
                raise OpTestError('Power status changed')
            return BMC_CONST.FW_SUCCESS
        else:
            loge.error("Cold reset failed, rc={}".format(rc))
            raise OpTestError(rc)



    ##
    # @brief This function waits until BMC Boot finishes after a BMC Cold reset
    #        0x00 = Boot Complete
    #        0xC0 = Not Complete
    #        Here AMI systems returns 00 and SMC Systems return NULL for success
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_wait_for_bmc_runtime(self, i_timeout=10):
        l_timeout = time.time() + 60*i_timeout
        l_cmd = ' raw 0x3a 0x0a '
        while True:
            try:
                l_output = self.ipmitool.run(l_cmd)
                log.debug(l_output)
            except:
                continue
            if "0xc0"in l_output:
                log.info("BMC Still booting...")
            elif "00" in l_output: # AMI BMC returns 00 as output
                log.info("BMC Completed booting...")
                break
            else: # SMC BMC returns empty as output
                log.info("BMC Completed booting...")
                break
            if time.time() > l_timeout:
                l_msg = "BMC Boot timeout..."
                log.error(l_msg)
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_IPL)
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Performs a warm reset onto the bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_warm_reset(self):
        l_initstatus = self.ipmi_power_status()
        l_cmd = BMC_CONST.BMC_WARM_RESET
        log.info("Applying Warm reset. Wait for "
                            + str(BMC_CONST.BMC_WARM_RESET_DELAY) + "sec")
        rc = self.ipmitool.run(l_cmd)
        if BMC_CONST.BMC_PASS_WARM_RESET in rc:
            log.info("Warm reset result: {}".format(rc))
            time.sleep(BMC_CONST.BMC_WARM_RESET_DELAY)
            self.util.PingFunc(self.cv_bmcIP, BMC_CONST.PING_RETRY_FOR_STABILITY)
            l_finalstatus = self.ipmi_power_status()
            if (l_initstatus != l_finalstatus):
                log.debug('initial status ' + str(l_initstatus))
                log.debug('final status ' + str(l_finalstatus))
                log.debug('Power status changed during cold reset')
                raise OpTestError('Power status changed')
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Warm reset Failed"
            log.error(l_msg)
            raise OpTestError(l_msg)



    ##
    # @brief Preserves the network setting
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_preserve_network_setting(self):

        log.info("Protecting BMC network setting")
        l_cmd =  BMC_CONST.BMC_PRESRV_LAN
        rc = self.ipmitool.run(l_cmd)

        if BMC_CONST.BMC_ERROR_LAN in rc:
            l_msg = "Can't protect setting! Please preserve setting manually"
            log.error(l_msg)
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS


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
    def ipmi_code_update(self, i_image, i_imagecomponent):

        self.ipmi_cold_reset()
        time.sleep(5)
        l_cmd = BMC_CONST.BMC_HPM_UPDATE + i_image + " " + i_imagecomponent
        # We need to do a re-try of hpm code update if it fails for the first time
        # As AMI systems are some times failed to flash for the first time.
        count = 0
        while (count <2):
            self.ipmi_preserve_network_setting()
            time.sleep(5)
            rc = self.ipmitool.run(l_cmd, background=False, cmdprefix = "echo y |")
            log.info("IPMI code update result: {}".format(rc))
            if(rc.__contains__("Firmware upgrade procedure successful")):
                return BMC_CONST.FW_SUCCESS
            elif count == 1:
                l_msg = "Code Update Failed"
                log.error(l_msg)
                raise OpTestError(l_msg)
            else:
                count = count + 1
                continue

    ##
    # @brief Get information on active sides for both BMC and PNOR
    # example 0x0080 indicates primary side is activated
    #         0x0180 indicates golden side is activated
    #
    # @return returns the active sides for BMC and PNOR chip (that are either primary of golden)
    #         l_bmc_side, l_pnor_side or raise OpTestError
    #
    def ipmi_get_side_activated(self):

        l_result = self.ipmitool.run(BMC_CONST.BMC_ACTIVE_SIDE).strip().split('\n')

        for i in range(len(l_result)):
            if('BIOS' in l_result[i]):
                if(l_result[i].__contains__(BMC_CONST.PRIMARY_SIDE)):
                    log.info("Primary side of PNOR is active")
                    l_pnor_side = BMC_CONST.PRIMARY_SIDE
                elif(BMC_CONST.GOLDEN_SIDE in l_result[i]):
                    log.info("Golden side of PNOR is active")
                    l_pnor_side = BMC_CONST.GOLDEN_SIDE
                else:
                    l_msg = "Error determining active side: " + l_result
                    log.error(l_msg)
                    raise OpTestError(l_msg)
            elif('BMC' in l_result[i]):
                if(l_result[i].__contains__(BMC_CONST.PRIMARY_SIDE)):
                    log.info("Primary side of BMC is active")
                    l_bmc_side = BMC_CONST.PRIMARY_SIDE
                elif(BMC_CONST.GOLDEN_SIDE in l_result[i]):
                    log.info("Golden side of BMC is active")
                    l_bmc_side = BMC_CONST.GOLDEN_SIDE
                else:
                    l_msg = "Error determining active side: " + l_result
                    log.error(l_msg)
                    raise OpTestError(l_msg)
            else:
                l_msg = "Error determining active side: " + + l_result
                log.error(l_msg)
                raise OpTestError(l_msg)

        return l_bmc_side, l_pnor_side

    ##
    # @brief Get PNOR level
    #
    # @return pnor level of the bmc
    #         or raise OpTestError
    #
    def ipmi_get_PNOR_level(self):
        l_rc =  self.ipmitool.run(BMC_CONST.BMC_MCHBLD)
        return l_rc

    ##
    # @brief This function gets the BMC golden side firmware version.
    #        Below are the fields to decode the version of firmware
    #        1      Completion code
    #                   0x00 – success
    #                   0x81 – Not a valid image in golden SPI.
    #                   0xff – Reading Golden side SPI failed.
    #       2       Device ID (0x02)
    #       3       IPMI Dev version (0x01)
    #       4       Firmware Revision 1 (Major )
    #       5       Firmware Revision 2 (Minor)
    #       6       IPMI Version
    #       7       Additional Device support refer IPMI spec.
    #       8-10    Manufacture ID
    #       11-12   Product ID
    #       13-16   Auxiliary Firmware Revision
    #
    # @return l_rc @type str: BMC golden side firmware version
    #         or raise OpTestError
    #           ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x1a
    #           20 01 02 16 02 bf 00 00 00 bb aa 4d 4c 01 00
    #
    def ipmi_get_bmc_golden_side_version(self):
        log.debug("IPMI: Getting the BMC Golden side version")
        l_rc = self.ipmitool.run(BMC_CONST.IPMI_GET_BMC_GOLDEN_SIDE_VERSION)
        return l_rc

    ##
    # @brief This function gets the size of pnor partition
    #
    # @param i_part @type str: partition name to retrieve the size.
    #                          partition can be NVRAM, GUARD and BOOTKERNEL
    #                          TODO: Add support for remaining partitions.
    #
    # @return l_rc @type str: size of partition raise OpTestError when fails
    #         Ex:ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x0c
    #            0x42 0x4f 0x4f 0x54 0x4b 0x45 0x52 0x4e 0x45 0x4c 0x00 0x00 0x00 0x00 0x0 0x0 0x0
    #           00 00 f0 00
    #           This function will return "00 00 f0 00"
    #
    def ipmi_get_pnor_partition_size(self, i_part):
        log.debug("IPMI: Getting the size of %s PNOR Partition" % i_part)
        if i_part == BMC_CONST.PNOR_NVRAM_PART:
            l_rc = self.ipmitool.run(BMC_CONST.IPMI_GET_NVRAM_PARTITION_SIZE)
        elif i_part == BMC_CONST.PNOR_GUARD_PART:
            l_rc = self.ipmitool.run(BMC_CONST.IPMI_GET_GUARD_PARTITION_SIZE )
        elif i_part == BMC_CONST.PNOR_BOOTKERNEL_PART:
            l_rc = self.ipmitool.run(BMC_CONST.IPMI_GET_BOOTKERNEL_PARTITION_SIZE)
        else:
            l_msg = "please provide valid partition eye catcher name ({} is invalid)".format(i_part)
            log.error(l_msg)
            raise OpTestError(l_msg)
        return l_rc

    ##
    # @brief This function is used to check whether BMC Completed Booting.
    #        BMC Booting Status:
    #           00h = Booting Completed.
    #           C0h = Still Booting.
    #
    # @return l_res @type str: output of command or raise OpTestError
    #          ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x0a
    #          00
    #        It returns 00 if BMC completed booting else it gives C0
    #
    def ipmi_get_bmc_boot_completion_status(self):
        log.debug("IPMI: Getting the BMC Boot completion status")
        l_res = self.ipmitool.run(BMC_CONST.IPMI_HAS_BMC_BOOT_COMPLETED)
        return l_res

    ##
    # @brief This command is used to get the State of Fault RollUP LED.
    #        Fault RollUP LED      0x00
    #
    # @return l_res @type str: output of command or raise OpTestError
    #          ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x02 0x00
    #          00
    #        LED State Table: Below are the states it can get
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    def ipmi_get_fault_led_state(self):
        log.debug("IPMI: Getting the fault rollup LED state")
        l_res = self.ipmitool.run(BMC_CONST.IPMI_GET_LED_STATE_FAULT_ROLLUP)
        return l_res

    ##
    # @brief This command is used to get the State of Power ON LED.
    #        Power ON LED      0x01
    #
    # @return l_res @type str: output of command or raise OpTestError
    #           ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x02 0x01
    #           01
    #
    #        LED State Table: Below are the states it can get
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    def ipmi_get_power_on_led_state(self):
        log.debug("IPMI: Getting the Power ON LED state")
        l_res = self.ipmitool.run(BMC_CONST.IPMI_GET_LED_STATE_POWER_ON)
        return l_res

    ##
    # @brief This command is used to get the State of Host Status LED.
    #        Host Status LED       0x02
    #
    # @return l_res @type str: output of command or raise OpTestError
    #       ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x02 0x02
    #       00
    #
    #        LED State Table: Below are the states it can get
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    def ipmi_get_host_status_led_state(self):
        log.debug("IPMI: Getting the Host status LED state")
        l_res = self.ipmitool.run(BMC_CONST.IPMI_GET_LED_STATE_HOST_STATUS)
        return l_res

    ##
    # @brief This command is used to get the State of Chassis Identify LED.
    #        Chassis Identify LED  0x03
    #
    # @return l_res @type str: output of command or raise OpTestError
    #       ipmitool -I lanplus -H <BMC-IP> -U ADMIN -P admin raw 0x3a 0x02 0x03
    #       00
    #
    #        LED State Table: Below are the states it can get
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    def ipmi_get_chassis_identify_led_state(self):
        log.debug("IPMI: Getting the Chassis Identify LED state")
        l_res = self.ipmitool.run(BMC_CONST.IPMI_GET_LED_STATE_CHASSIS_IDENTIFY)
        return l_res

    ##
    # @brief This function is used to set the state of a given LED.
    #
    # @param i_led @type str: led number to set the state.
    #        EX: LED Number Table to use.
    #            Fault RollUP LED      0x00
    #            Power ON LED          0x01
    #            Host Status LED       0x02
    #            Chassis Identify LED  0x03
    #
    # @param i_state @type str: state of led to set.
    #           LED State to be set.
    #               0x0  LED OFF
    #               0x1  LED ON
    #               0x2  LED Standby Blink Rate
    #               0x3  LED Slow Blink rate.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_set_led_state(self, i_led, i_state):
        l_led = i_led
        l_state = i_state
        log.debug("IPMI: Setting the %s LED with %s state" % (l_led, l_state))
        l_cmd = "raw 0x3a 0x03 %s %s" % (l_led, l_state)
        l_res = self.ipmitool.run(l_cmd)
        if "00" in l_res:
            log.debug("Set LED state got success")
            return BMC_CONST.FW_SUCCESS
        elif "0x90" in l_res:
            log.error("Invalid LED number (i_led={},i_state={}) res:{}".format(i_led,i_state,l_les))
        else:
            l_msg = "IPMI: Set LED state failed (i_led={},i_state={}) res:{}".format(i_led, i_state, l_les)
            log.error(l_msg)
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to enable Fan control Task thread running on BMC
    #        Ex: ipmitool raw 0x3a 0x12 0x01
    #
    # @return l_rc @type str: return code of command or raise OpTestError when fails
    #           Completion Code: 00h = success
    #                            cch = Invalid Request Data
    #                            83 h = File not created in start case.
    #                            80 h – Invalid Operation Mode
    #
    def ipmi_enable_fan_control_task_command(self):
        log.debug("IPMI: Enabling the Fan control task thread state")
        l_rc = self.ipmitool.run(BMC_CONST.IPMI_ENABLE_FAN_CONTROL_TASK_THREAD)
        return l_rc

    ##
    # @brief This function is used to disable Fan control Task thread running on BMC
    #        Ex: ipmitool raw 0x3a 0x12 0x00
    #
    # @return l_rc @type str: return code of command or raise OpTestError when fails
    #           Completion Code: 00h = success
    #                            cch = Invalid Request Data
    #                            83 h = File not created in start case.
    #                            80 h – Invalid Operation Mode
    #
    def ipmi_disable_fan_control_task_command(self):
        log.debug("IPMI: Disabling the Fan control task thread state")
        l_rc = self.ipmitool.run(BMC_CONST.IPMI_DISABLE_FAN_CONTROL_TASK_THREAD)
        return l_rc

    ##
    # @brief This function is used to get the state of fan control task thread.
    #        Ex: ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x13
    #            00
    #            ipmitool -I lanplus -U admin -P admin -H <BMC IP> raw 0x3a 0x13
    #            01
    #
    # @return l_state @type str: raise OpTestError when fails
    #           IPMI_FAN_CONTROL_THREAD_RUNNING = "01"
    #           IPMI_FAN_CONTROL_THREAD_NOT_RUNNING = "00"
    #           If fan control loop is running it will return "01"
    #           else it will return "00"
    #
    def ipmi_get_fan_control_task_state_command(self):
        log.debug("IPMI: Getting the state of fan control task thread")
        l_rc = self.ipmitool.run(BMC_CONST.IPMI_FAN_CONTROL_TASK_THREAD_STATE)
        if BMC_CONST.IPMI_FAN_CONTROL_THREAD_NOT_RUNNING in l_rc:
            log.info("IPMI: Fan control task thread state is not running")
            l_state = BMC_CONST.IPMI_FAN_CONTROL_THREAD_NOT_RUNNING
        elif BMC_CONST.IPMI_FAN_CONTROL_THREAD_RUNNING in l_rc:
            log.info("IPMI: Fan control task thread state is running")
            l_state = BMC_CONST.IPMI_FAN_CONTROL_THREAD_RUNNING
        else:
            l_msg = "IPMI: Invalid response from fan control thread state command"
            raise OpTestError(l_msg)
        return l_state

    ##
    # @brief set power limit of bmc
    #
    # @param i_powerlimit @type int: power limit to be set at BMC
    #
    # @return raise OpTestError when fails
    #
    def ipmi_set_power_limit(self, i_powerlimit):

        l_rc = self.ipmitool.run(BMC_CONST.SET_POWER_LIMIT + i_powerlimit)
        if(i_powerlimit not in l_rc):
            raise OpTestError(l_rc)


    ##
    # @brief Determines the power limit on the bmc
    #
    # @return l_powerlimit @type int: current power limit on bmc
    #         or raise OpTestError
    #
    def ipmi_get_power_limit(self):

        l_powerlimit = self.ipmitool.run(BMC_CONST.GET_POWER_LIMIT)
        return l_powerlimit

    ##
    # @brief Activates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_activate_power_limit(self):

        l_rc = self.ipmitool.run(BMC_CONST.DCMI_POWER_ACTIVATE)
        if(BMC_CONST.POWER_ACTIVATE_SUCCESS in l_rc):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power limit activation failed"
            log.error(l_msg)
            raise OpTestError(l_msg)


    ##
    # @brief Deactivates the power limit of the target bmc
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_deactivate_power_limit(self):

        l_rc = self.ipmitool.run(BMC_CONST.DCMI_POWER_DEACTIVATE)
        if(BMC_CONST.POWER_DEACTIVATE_SUCCESS in l_rc):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Power limit deactivation failed. " \
                    "Make sure a power limit is set before activating it"
            log.error(l_msg)
            raise OpTestError(l_msg)


    ##
    # @brief Enable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_enable_all_occ_sensor(self):

        l_status = self.ipmi_get_occ_status()
        # example ssample: OCC Active | 08h | ok  | 210.0 |)

        # Get sensor ids to enable all OCCs
        l_status = l_status.rsplit("\n", 1)[0].split("\n")
        for i in range(len(l_status)):
            l_sensor_id = l_status[i].split("|")[1].strip()[:2]
            self.ipmitool.run(BMC_CONST.BMC_OCC_SENSOR +
                              l_sensor_id + BMC_CONST.BMC_ENABLE_OCC)

        # Wait for OCC to stabilize
        time.sleep(BMC_CONST.OCC_ENABLE_WAIT)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Disable OCC Sensor
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_disable_all_occ_sensor(self):

        l_status = self.ipmi_get_occ_status()

        # Get sensor ids to disable all OCCs
        l_status = l_status.rsplit("\n", 1)[0].split("\n")
        for i in range(len(l_status)):
            l_sensor_id = l_status[i].split("|")[1].strip()[:2]
            self.ipmitool.run(BMC_CONST.BMC_OCC_SENSOR +
                                   l_sensor_id + BMC_CONST.BMC_DISABLE_OCC)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Get OCC status
    #  (example:
    #   OCC 1 Active     | 08h | ok  | 210.0 | Device Enabled
    #   OCC 2 Active     | 09h | ok  | 210.1 | Device Enabled)
    #
    # @return OCC sensor status or raise OpTestError
    #
    def ipmi_get_occ_status(self):
        l_result = self.ipmitool.run(BMC_CONST.OP_CHECK_OCC)
        if ("Device" not in l_result):
            l_msg = "Can't recognize output"
            log.error(l_msg + ": " + l_result)
            raise OpTestError(l_msg)

        return l_result

    ##
    # @brief This function gets the sel log
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_get_sel_list(self):
        return self.ipmitool.run(BMC_CONST.BMC_SEL_LIST)

    ##
    # @brief This function gets the sdr list
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def ipmi_get_sdr_list(self):
        return self.ipmitool.run(BMC_CONST.BMC_SDR_ELIST)


    ##
    # @brief Sets BIOS sensor and BOOT count to boot pnor from the primary side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_pnor_primary_side(self, i_bios_sensor, i_boot_sensor):

        log.info('\nSetting PNOR to boot into Primary Side')

        #Set the Boot Count sensor to 2
        l_cmd = BMC_CONST.BMC_BOOT_COUNT_2.replace('xx', i_boot_sensor)
        self.ipmitool.run(l_cmd)

        #Set the BIOS Golden Side sensor to 0
        l_cmd = BMC_CONST.BMC_BIOS_GOLDEN_SENSOR_TO_PRIMARY.replace('xx', i_bios_sensor)
        self.ipmitool.run(l_cmd)

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Sets BIOS sensor and BOOT count to boot pnor from the golden side
    #
    # @param i_bios_sensor @type string: Id for BIOS Golden Sensor (example habanero=0x5c)
    # @param i_boot_sensor @type string: Id for BOOT Count Sensor (example habanero=80)
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_pnor_golden_side(self, i_bios_sensor, i_boot_sensor):

        log.info('\nSetting PNOR to boot into Golden Side')

        #Set the Boot Count sensor to 2
        l_cmd = BMC_CONST.BMC_BOOT_COUNT_2.replace('xx', i_boot_sensor)
        self.ipmitool.run(l_cmd)

        #Set the BIOS Golden Side sensor to 1
        l_cmd = BMC_CONST.BMC_BIOS_GOLDEN_SENSOR_TO_GOLDEN.replace('xx', i_bios_sensor)
        self.ipmitool.run(l_cmd)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Sets auto-reboot policy with given policy(i_policy)
    #
    # @param i_policy @type string: type of policy to be set(chassis policy <i_policy>)
    #                               always-off
    #                               always-on
    #                               previous
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError if failed
    #
    def ipmi_set_power_policy(self, i_policy):
        log.debug("IPMI: Setting the power policy to %s" % i_policy)
        l_cmd = "chassis policy %s" % i_policy
        l_res = self.ipmitool.run(l_cmd)
        log.debug(l_res)

    ##
    # @brief Set boot device to be boot to BIOS (i.e. petitboot)
    # @return 0 for success or throws exception
    #
    def ipmi_set_boot_to_petitboot(self):
        l_output = self.ipmitool.run('chassis bootdev bios')
        if('Set Boot Device to bios' in l_output):
            return 0
        else:
            raise OpTestError("Failure setting bootdev to bios: " + str(l_output))

    ##
    # @brief Set boot device to be boot to disk (i.e. OS)
    # @return 0 for success or throws exception
    #
    def ipmi_set_boot_to_disk(self):
        l_output = self.ipmitool.run('chassis bootdev disk')
        if('Set Boot Device to disk' in l_output):
            return 0
        else:
            raise OpTestError("Failure setting bootdev to disk: " + str(l_output))

    ##
    # @brief Set no boot override so that local config will be effective
    # @return 0 for success or throws exception
    #
    def ipmi_set_no_override(self):
        l_output = self.ipmitool.run('chassis bootdev none')
        if('Set Boot Device to none' in l_output):
            return 0
        else:
            raise OpTestError("Failure setting bootdev to none: " + str(l_output))

    def enter_ipmi_lockdown_mode(self):
        self.ipmitool.run('raw 0x32 0xf3 0x4c 0x4f 0x43 0x4b 0x00')

    def exit_ipmi_lockdown_mode(self):
        self.ipmitool.run('raw 0x32 0xF4 0x55 0x4e 0x4c 0x4f 0x43 0x4b 0x00')

    def last_sel(self):
        return self.ipmitool.run("sel list last 1")

    def sdr_get_watchdog(self):
        return self.ipmitool.run("sdr get \'Watchdog\'")

    def mc_get_watchdog(self):
        return self.ipmitool.run("mc watchdog get")

    def set_tpm_required(self):
        pass

    def clear_tpm_required(self):
        pass

    def is_tpm_enabled(self):
        pass

    def ipmi_get_golden_side_sensor_id(self):
        cmd = "sdr elist -v | grep -i 'BIOS Golden'"
        output = self.ipmitool.run(cmd)
        matchObj = re.search( "BIOS Golden Side \((.*)\)", output)
        id = None
        if matchObj:
            id = matchObj.group(1)
        return id

    def ipmi_get_boot_count_sensor_id(self):
        cmd = "sdr elist -v | grep -i 'Boot Count'"
        output = self.ipmitool.run(cmd)
        matchObj = re.search( "Boot Count \((.*)\)", output)
        id = None
        if matchObj:
            id = matchObj.group(1)
        return id


class OpTestSMCIPMI(OpTestIPMI):

    def enter_ipmi_lockdown_mode(self):
        self.ipmitool.run('raw 0x3a 0xf3 0x4c 0x4f 0x43 0x4b 0x00')

    def exit_ipmi_lockdown_mode(self):
        self.ipmitool.run('raw 0x3a 0xF4 0x55 0x4e 0x4c 0x4f 0x43 0x4b 0x00')

    def set_tpm_required(self):
        self.ipmitool.run('raw 0x04 0x30 0x49 0x10 0x00 0x02 0 0 0 0 0 0')

    def clear_tpm_required(self):
        self.ipmitool.run('raw 0x04 0x30 0x49 0x10 0x00 0x01 0 0 0 0 0 0')

    def is_tpm_enabled(self):
        res = self.ipmitool.run("sdr elist | grep -i TPM")
        if "State Deasserted" in res:
            log.info("#TPM is disabled")
            return False
        elif "State Asserted" in res:
            log.info("#TPM is enabled")
            return True

    def disable_sensor_polling(self):
        self.ipmitool.run("raw 0x30 0x70 0xdf 0")

    def enable_sensor_polling(self):
        self.ipmitool.run("raw 0x30 0x70 0xdf 1")
