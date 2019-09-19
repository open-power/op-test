#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
# [] International Business Machines Corp.
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

# @package OpTestHMC
#  This class can contain common functions which are useful for
#  FSP_PHYP (HMC) platforms

import os
import sys
import time
import pexpect

import OpTestLogger
from common.OpTestError import OpTestError
from common.OpTestSSH import OpTestSSH
from common.OpTestUtil import OpTestUtil
from common.Exceptions import CommandFailed
from common import OPexpect

from .OpTestConstants import OpTestConstants as BMC_CONST

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

WAITTIME = 15
BOOTTIME = 500
STALLTIME = 3


class OpHmcState():
    '''
    This class is used as an enum as to what state op-test *thinks* the LPAR is in.
    These states are used to check status of a LPAR.
    '''
    NOT_ACTIVE = 'Not Activated'
    RUNNING = 'Running'
    SHUTTING = 'Shutting Down'
    OF = 'Open Firmware'
    STARTING = 'Starting'
    NA = 'Not Available'


class OpManagedState():
    '''
    This class is used as an enum as to what state op-test *thinks* the managed
    system is in. These states are used to check status of managed system.
    '''
    OPERATING = 'Operating'
    INIT = 'Initializing'
    OFF = 'Power Off'
    PROG_OFF = 'Power Off In Progress'


class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1


class Spawn(OPexpect.spawn):
    def __init__(self, command, args=[], maxread=8000,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 ignore_sighup=False, echo=True, preexec_fn=None,
                 encoding='utf-8', codec_errors='ignore', dimensions=None,
                 failure_callback=None, failure_callback_data=None):
        super(Spawn, self).__init__(command, args=args,
                                    maxread=maxread,
                                    searchwindowsize=searchwindowsize,
                                    logfile=logfile,
                                    cwd=cwd, env=env,
                                    ignore_sighup=ignore_sighup,
                                    encoding=encoding,
                                    codec_errors=codec_errors)

    def sendline(self, command=''):
        # HMC console required an enter to be sent with each sendline
        super(Spawn, self).sendline(command)
        self.send("\r")


class HMCUtil():
    '''
    Utility and functions of HMC object
    '''
    def __init__(self, hmc_ip, user_name, password, scratch_disk="", proxy="",
                 logfile=sys.stdout, managed_system=None, lpar_name=None, prompt=None,
                 block_setup_term=None, delaybeforesend=None, timeout_factor=None,
                 lpar_prof=None, lpar_vios=None, lpar_user=None, lpar_password=None,
                 check_ssh_keys=False, known_hosts_file=None):
        self.hmc_ip = hmc_ip
        self.user = user_name
        self.passwd = password
        self.logfile = logfile
        self.mg_system = managed_system
        self.check_ssh_keys = check_ssh_keys
        self.known_hosts_file = known_hosts_file
        self.lpar_name = lpar_name
        self.lpar_prof = lpar_prof
        self.lpar_user = lpar_user
        self.lpar_password = lpar_password
        self.lpar_vios = lpar_vios
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.ssh = OpTestSSH(hmc_ip, user_name, password, logfile=self.logfile,
                             check_ssh_keys=check_ssh_keys,
                             known_hosts_file=known_hosts_file,
                             block_setup_term=block_setup_term)
        self.scratch_disk = scratch_disk
        self.proxy = proxy
        self.scratch_disk_size = None
        self.delaybeforesend = delaybeforesend
        self.system = None
        # OpTestUtil instance is NOT conf's
        self.pty = None
        # allows caller specific control of when to block setup_term
        self.block_setup_term = block_setup_term
        # tells setup_term to not throw exceptions, like when system off
        self.setup_term_quiet = 0
        # flags the object to abandon setup_term operations, like when system off
        self.setup_term_disable = 0
        # functional simulators are very slow, so multiply all default timeouts by this factor
        self.timeout_factor = timeout_factor

        # state tracking, reset on boot and state changes
        # console tracking done on System object for the system console
        self.PS1_set = -1
        self.LOGIN_set = -1
        self.SUDO_set = -1

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.util.run_command_ignore_fail(self, command, timeout*self.timeout_factor, retry)

    def run_command(self, i_cmd, timeout=15):
        return self.ssh.run_command(i_cmd, timeout)

    def deactivate_lpar_console(self):
        self.run_command("rmvterm -m %s -p %s" %
                         (self.mg_system, self.lpar_name), timeout=10)

    def poweroff_system(self):
        if self.get_system_state() != OpManagedState.OPERATING:
            raise OpTestError('Managed Systen not in Operating state')
        self.run_command("chsysstate -m %s -r sys -o off" % self.mg_system)
        self.wait_system_state(OpManagedState.OFF)

    def poweron_system(self):
        if self.get_system_state() != OpManagedState.OFF:
            raise OpTestError('Managed Systen not is Power off state!')
        self.run_command("chsysstate -m %s -r sys -o on" % self.mg_system)
        self.wait_system_state()
        if self.lpar_vios:
            log.debug("Starting VIOS %s", self.lpar_vios)
            self.poweron_lpar(vios=True)

    def poweroff_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state(OpHmcState.NOT_ACTIVE)

    def poweron_lpar(self, vios=False):
        if self.get_lpar_state(vios) == OpHmcState.RUNNING:
            log.info('LPAR Already powered on!')
            return BMC_CONST.FW_SUCCESS
        lpar_name = self.lpar_name
        if vios:
            lpar_name = self.lpar_vios
        cmd = "chsysstate -m %s -r lpar -n %s -o on" % (self.mg_system, lpar_name)

        if self.lpar_prof:
            cmd = "%s -f %s" % (cmd, self.lpar_prof)

        self.wait_lpar_state(OpHmcState.NOT_ACTIVE, vios=vios)
        self.run_command(cmd)
        self.wait_lpar_state(vios=vios)
        time.sleep(STALLTIME)
        return BMC_CONST.FW_SUCCESS

    def dumprestart_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.run_command("chsysstate -m %s -r lpar -n %s -o dumprestart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def restart_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed --restart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def get_lpar_state(self, vios=False):
        lpar_name = self.lpar_name
        if vios:
            lpar_name = self.lpar_vios
        state = self.run_command(
            'lssyscfg -m %s -r lpar --filter lpar_names=%s -F state' % (self.mg_system, lpar_name))
        return state[-1]

    def get_system_state(self):
        state = self.run_command(
            'lssyscfg -m %s -r sys -F state' % self.mg_system)
        return state[-1]

    def wait_lpar_state(self, exp_state=OpHmcState.RUNNING, vios=False, timeout=WAITTIME):
        state = self.get_lpar_state(vios)
        count = 0
        while state != exp_state:
            state = self.get_lpar_state(vios)
            log.info("Current state: %s", state)
            time.sleep(timeout)
            count = 1
            if count > 120:
                raise OpTestError("Time exceeded for reaching %s" % exp_state)

    def wait_system_state(self, exp_state=OpManagedState.OPERATING, timeout=WAITTIME):
        state = self.get_system_state()
        count = 0
        while state != exp_state:
            state = self.get_system_state()
            log.info("Current state: %s", state)
            time.sleep(timeout)
            count = 1
            if count > 60:
                raise OpTestError("Time exceeded for reaching %s" % exp_state)


class OpTestHMC(HMCUtil):
    '''
    This class contains the modules to perform various HMC operations on an LPAR.
    The Host IP, username and password of HMC have to be passed to the class intially
    while creating the object for the class.
    '''

    def __init__(self, hmc_ip, user_name, password, scratch_disk="", proxy="",
                 logfile=sys.stdout, managed_system=None, lpar_name=None, prompt=None,
                 block_setup_term=None, delaybeforesend=None, timeout_factor=None,
                 lpar_prof=None, lpar_vios=None, lpar_user=None, lpar_password=None,
                 check_ssh_keys=False, known_hosts_file=None):
        super(OpTestHMC, self).__init__(hmc_ip, user_name, password, scratch_disk,
                                        proxy, logfile, managed_system, lpar_name, prompt,
                                        block_setup_term, delaybeforesend, timeout_factor,
                                        lpar_prof, lpar_vios, lpar_user, lpar_password,
                                        check_ssh_keys, known_hosts_file)

        self.console = HMCConsole(hmc_ip, user_name, password, managed_system, lpar_name,
                                  lpar_vios, lpar_prof, lpar_user, lpar_password)

    def set_system(self, system):
        self.console.set_system(system)
        self.ssh.set_system(system)

    def get_rest_api(self):
        return None

    def has_os_boot_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_inband_bootdev(self):
        return False

    def get_host_console(self):
        return self.console


class HMCConsole(HMCUtil):
    """
    HMCConsole Class
    OpenBMC methods to manage the Host
    """
    def __init__(self, hmc_ip, user_name, password, managed_system, lpar_name,
                 lpar_vios, lpar_prof, lpar_user, lpar_password,
                 block_setup_term=None, delaybeforesend=None, timeout_factor=1,
                 logfile=sys.stdout, prompt=None, scratch_disk="",
                 check_ssh_keys=False, known_hosts_file=None, proxy=""):
        self.logfile = logfile
        self.hmc_ip = hmc_ip
        self.user = user_name
        self.passwd = password
        self.mg_system = managed_system
        self.lpar_name = lpar_name
        self.lpar_vios = lpar_vios
        self.lpar_prof = lpar_prof
        self.lpar_user = lpar_user
        self.lpar_password = lpar_password
        self.scratch_disk = scratch_disk
        self.proxy = proxy
        self.state = ConsoleState.DISCONNECTED
        self.delaybeforesend = delaybeforesend
        self.system = None
        # OpTestUtil instance is NOT conf's
        self.util = OpTestUtil()
        self.prompt = prompt
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
        self.pty = None
        self.delaybeforesend = delaybeforesend
        # allows caller specific control of when to block setup_term
        self.block_setup_term = block_setup_term
        # tells setup_term to not throw exceptions, like when system off
        self.setup_term_quiet = 0
        # flags the object to abandon setup_term operations, like when system off
        self.setup_term_disable = 0

        # FUTURE - System Console currently tracked in System Object
        # state tracking, reset on boot and state changes
        self.PS1_set = -1
        self.LOGIN_set = -1
        self.SUDO_set = -1
        super(HMCConsole, self).__init__(hmc_ip, user_name, password, scratch_disk, proxy,
                                         logfile, managed_system, lpar_name, prompt,
                                         block_setup_term, delaybeforesend, timeout_factor,
                                         lpar_prof, lpar_vios, lpar_user, lpar_password,
                                         check_ssh_keys, known_hosts_file)

    def get_host_console(self):
        return self.pty

    def set_system(self, system):
        self.ssh.system = system
        self.system = system

    def set_system_setup_term(self, flag):
        self.system.block_setup_term = flag

    def get_system_setup_term(self):
        return self.system.block_setup_term

    def get_scratch_disk(self):
        return self.scratch_disk

    def get_proxy(self):
        return self.proxy

    def hostname(self):
        return self.hmc_ip

    def username(self):
        return self.user

    def password(self):
        return self.passwd

    def set_block_setup_term(self, flag):
        self.block_setup_term = flag

    def get_block_setup_term(self):
        return self.block_setup_term

    def enable_setup_term_quiet(self):
        self.setup_term_quiet = 1
        self.setup_term_disable = 0

    def disable_setup_term_quiet(self):
        self.setup_term_quiet = 0
        self.setup_term_disable = 0

    def close(self):
        self.util.clear_state(self)
        try:
            self.pty.close()
            if self.pty.status != -1:  # leaving for debug
                if os.WIFEXITED(self.pty.status):
                    os.WEXITSTATUS(self.pty.status)
                else:
                    os.WTERMSIG(self.pty.status)
            self.state = ConsoleState.DISCONNECTED
        except pexpect.ExceptionPexpect:
            self.state = ConsoleState.DISCONNECTED
            raise "HMC Console: failed to close console"
        except Exception:
            self.state = ConsoleState.DISCONNECTED
        log.debug("HMC close -> TERMINATE")

    def connect(self, logger=None):
        if self.state == ConsoleState.CONNECTED:
            return self.pty
        self.util.clear_state(self)  # clear when coming in DISCONNECTED

        if self.get_lpar_state() != OpHmcState.RUNNING:
            raise OpTestError(
                'LPAR is not in Running State. Please check!')
        log.info("De-activating the console")
        self.deactivate_lpar_console()

        log.debug("#HMC Console CONNECT")

        command = "sshpass -p %s ssh -p 22 -l %s %s -o PubkeyAuthentication=no"\
                  " -o afstokenpassing=no -q -o 'UserKnownHostsFile=/dev/null'"\
                  " -o 'StrictHostKeyChecking=no'"
        try:
            self.pty = Spawn(
                command % (self.passwd, self.user, self.hmc_ip))
            self.wait_lpar_state()
            log.info("Opening the LPAR console")
            time.sleep(STALLTIME)
            self.pty.send('\r')
            self.pty.sendline("mkvterm -m %s -p %s" % (self.mg_system, self.lpar_name))
            self.pty.send('\r')
            time.sleep(STALLTIME)
            i = self.pty.expect(
                ["Open Completed.", pexpect.TIMEOUT], timeout=60)
            self.pty.logfile = sys.stdout
            if logger:
                self.pty.logfile_read = OpTestLogger.FileLikeLogger(logger)
            else:
                self.pty.logfile_read = OpTestLogger.FileLikeLogger(log)

            if i == 0:
                time.sleep(STALLTIME)
                self.state = ConsoleState.CONNECTED
                self.pty.setwinsize(1000, 1000)
                #return self.pty
            else:
                raise OpTestError("Check the lpar activate command")
        except Exception as exp:
            self.state = ConsoleState.DISCONNECTED
            raise CommandFailed('OPexpect.spawn',
                                'OPexpect.spawn encountered a problem: ' + str(exp), -1)


        if self.delaybeforesend:
            self.pty.delaybeforesend = self.delaybeforesend

        if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
            self.util.setup_term(self.system, self.pty,
                                 None, self.system.block_setup_term)

        if not self.pty.isalive():
            raise CommandFailed("mkvterm", self.pty.read(), self.pty.status)
        return self.pty

    def check_state(self):
        return self.state

    def get_console(self, logger=None):
        if self.state == ConsoleState.DISCONNECTED:
            self.util.clear_state(self)
            self.connect(logger=logger)
            time.sleep(STALLTIME)
            l_rc = self.pty.expect(["login:", pexpect.TIMEOUT], timeout=WAITTIME)
            if l_rc == 0:
                self.pty.send('\r')
            else:
                time.sleep(STALLTIME)
                self.pty.send('\r')
                self.pty.sendline('PS1=' + self.util.build_prompt(self.prompt))
                self.pty.send('\r')
                time.sleep(STALLTIME)
                l_rc = self.pty.expect(
                    [self.expect_prompt, pexpect.TIMEOUT], timeout=WAITTIME)
                if l_rc == 0:
                    log.debug("Shell prompt changed")
                else:
                    self.pty.send('\r')
                    log.debug("Waiting till booting!")
                    self.pty = self.get_login_prompt()
            return self.pty

        if self.system.SUDO_set != 1 or self.system.LOGIN_set != 1 or self.system.PS1_set != 1:
            self.util.setup_term(self.system, self.pty,
                                 None, self.system.block_setup_term)
        # Clear buffer before usage
        self.pty.buffer = ""
        return self.pty

    def get_login_prompt(self):
        # Assuming 'Normal' boot set in LPAR profile
        # We wait for upto 500 seconds for LPAR to boot to OS
        self.pty.send('\r')
        time.sleep(STALLTIME)
        log.debug("Waiting for login screen")
        i = self.pty.expect(["login:", self.expect_prompt, pexpect.TIMEOUT], timeout=BOOTTIME)
        if i == 0:
            log.debug("System has booted")
            time.sleep(STALLTIME)
        elif i == 1:
            log.debug("Console already logged in")
        else:
            log.error("%s %s", i, self.pty.before)
            raise OpTestError("Console in different state")
        return self.pty
