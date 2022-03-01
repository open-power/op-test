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
import shlex

import OpTestLogger
from common.OpTestError import OpTestError
from common.OpTestSSH import OpTestSSH
from common.OpTestUtil import OpTestUtil
from common.Exceptions import CommandFailed
from common import OPexpect

from .OpTestConstants import OpTestConstants as BMC_CONST

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

WAITTIME = 15
SYS_WAITTIME = 200
BOOTTIME = 500
STALLTIME = 5


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
                 check_ssh_keys=False, known_hosts_file=None, tgt_managed_system=None,
                 tgt_lpar=None):
        self.hmc_ip = hmc_ip
        self.user = user_name
        self.passwd = password
        self.logfile = logfile
        self.mg_system = managed_system
        self.tgt_mg_system = tgt_managed_system
        self.tgt_lpar = tgt_lpar
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

    def deactivate_lpar_console(self):
        self.ssh.run_command("rmvterm -m %s -p %s" %
                         (self.mg_system, self.lpar_name), timeout=10)

    def poweroff_system(self):
        if self.get_system_state() != OpManagedState.OPERATING:
            raise OpTestError('Managed Systen not in Operating state')
        self.ssh.run_command("chsysstate -m %s -r sys -o off" % self.mg_system)
        self.wait_system_state(OpManagedState.OFF)

    def poweron_system(self):
        if self.get_system_state() != OpManagedState.OFF:
            raise OpTestError('Managed Systen not is Power off state!')
        self.ssh.run_command("chsysstate -m %s -r sys -o on" % self.mg_system)
        self.wait_system_state()
        if self.lpar_vios:
            log.debug("Starting VIOS %s", self.lpar_vios)
            self.poweron_lpar(vios=True)

    def poweroff_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.ssh.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed" %
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
        self.ssh.run_command(cmd)
        self.wait_lpar_state(vios=vios)
        time.sleep(STALLTIME)
        return BMC_CONST.FW_SUCCESS

    def dumprestart_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.ssh.run_command("chsysstate -m %s -r lpar -n %s -o dumprestart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def restart_lpar(self):
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.ssh.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed --restart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def get_lpar_cfg(self):
        out = self.ssh.run_command("lssyscfg -r prof -m %s --filter 'lpar_names=%s'" %
                (self.mg_system, self.lpar_name))[-1]
        cfg_dict = {}
        splitter = shlex.shlex(out)
        splitter.whitespace += ','
        splitter.whitespace_split = True
        for values in list(splitter):
            data = values.split("=")
            key = data[0]
            value = data[1]
            cfg_dict[key] = value
        return cfg_dict

    def set_lpar_cfg(self, arg_str):
        if not self.lpar_prof:
            raise OpTestError("Profile needs to be defined to use this method")
        self.ssh.run_command("chsyscfg -r prof -m %s -p %s -i 'lpar_name=%s,name=%s,%s' --force" %
                (self.mg_system, self.lpar_name, self.lpar_name, self.lpar_prof,arg_str))

    def get_lpar_state(self, vios=False):
        lpar_name = self.lpar_name
        if vios:
            lpar_name = self.lpar_vios
        state = self.ssh.run_command(
            'lssyscfg -m %s -r lpar --filter lpar_names=%s -F state' % (self.mg_system, lpar_name))[-1]
        ref_code = self.ssh.run_command(
            'lsrefcode -m %s -r lpar --filter lpar_names=%s -F refcode' % (self.mg_system, lpar_name))[-1]
        if state == 'Running':
            if 'Linux' in ref_code or not ref_code:
                return 'Running'
            else:
                return 'Booting'
        return state

    def get_system_state(self):
        state = self.ssh.run_command(
            'lssyscfg -m %s -r sys -F state' % self.mg_system)
        return state[-1]

    def wait_lpar_state(self, exp_state=OpHmcState.RUNNING, vios=False, timeout=WAITTIME):
        state = self.get_lpar_state(vios)
        count = 0
        while state != exp_state:
            state = self.get_lpar_state(vios)
            log.info("Current state: %s", state)
            time.sleep(timeout)
            count += 1
            if count > 120:
                raise OpTestError("Time exceeded for reaching %s" % exp_state)

    def wait_system_state(self, exp_state=OpManagedState.OPERATING, timeout=SYS_WAITTIME):
        state = self.get_system_state()
        count = 0
        while state != exp_state:
            state = self.get_system_state()
            log.info("Current state: %s", state)
            time.sleep(timeout)
            count += 1
            if count > 60:
                raise OpTestError("Time exceeded for reaching %s" % exp_state)

    def is_lpar_in_managed_system(self, mg_system=None, lpar_name=None, remote_hmc=None):
        hmc = remote_hmc if remote_hmc else self
        lpar_list = hmc.ssh.run_command(
                   'lssyscfg -r lpar -m %s -F name' % mg_system)
        if lpar_name in lpar_list:
            log.info("%s lpar found in managed system %s" % (lpar_name, mg_system))
            return True
        return False

    def migrate_lpar(self, src_mg_system=None, dest_mg_system=None, options=None, param="", timeout=300):
        if src_mg_system == None or dest_mg_system == None:
            raise OpTestError("Source and Destination Managed System required for LPM")
        if not self.is_lpar_in_managed_system(src_mg_system, self.lpar_name):
            raise OpTestError("Lpar %s not found in managed system %s" % (self.lpar_name, src_mg_system))
        self.ssh.run_command(
            'migrlpar -o v -m %s -t %s -p %s' % (src_mg_system, dest_mg_system, self.lpar_name))
        cmd = 'migrlpar -o m -m %s -t %s -p %s %s' % (src_mg_system, dest_mg_system, self.lpar_name, param)
        if options:
            cmd = "%s %s" % (cmd, options)
        self.ssh.run_command(cmd, timeout=timeout)
        log.debug("Waiting for %.2f minutes." % (timeout/60))
        time.sleep(timeout)
        if self.is_lpar_in_managed_system(dest_mg_system, self.lpar_name):
            cmd = "lssyscfg -m %s -r lpar --filter lpar_names=%s -F state" % (
                   dest_mg_system, self.lpar_name)
            lpar_state = self.ssh.run_command(cmd)[0]
            if lpar_state not in ['Migrating - Running', 'Migrating - Not Activated']:
                log.info("Migration of lpar %s from %s to %s is successfull" %
                         (self.lpar_name, src_mg_system, dest_mg_system))
                self.mg_system = dest_mg_system
                return True
            self.recover_lpar(src_mg_system, dest_mg_system, stop_lpm=True, timeout=timeout)
        log.info("Migration of lpar %s from %s to %s failed" %
                 (self.lpar_name, src_mg_system, dest_mg_system))
        return False

    def set_ssh_key_auth(self, hmc_ip, hmc_user, hmc_passwd, remote_hmc=None):
        hmc = remote_hmc if remote_hmc else self
        try:
            cmd = "mkauthkeys -u %s --ip %s --test" % (hmc_user, hmc_ip)
            hmc.run_command(cmd, timeout=120)
        except CommandFailed:
            try:
                cmd = "mkauthkeys -u %s --ip %s --passwd %s" % (
                       hmc_user, hmc_ip, hmc_passwd)
                hmc.run_command(cmd, timeout=120)
            except CommandFailed as cf:
                raise cf

    def cross_hmc_migration(self, src_mg_system=None, dest_mg_system=None,
                            target_hmc_ip=None, target_hmc_user=None, target_hmc_passwd=None,
                            remote_hmc=None, options=None, param="", timeout=300):
        hmc = remote_hmc if remote_hmc else self

        if src_mg_system == None or dest_mg_system == None:
            raise OpTestError("Source and Destination Managed System "\
            "required for Cross HMC LPM")
        if target_hmc_ip == None or target_hmc_user == None or target_hmc_passwd == None:
            raise OpTestError("Destination HMC IP, Username, and Password "\
            "required for Cross HMC LPM")
        if not self.is_lpar_in_managed_system(src_mg_system, self.lpar_name, remote_hmc):
            raise OpTestError("Lpar %s not found in managed system %s" % (
            self.lpar_name, src_mg_system))

        self.set_ssh_key_auth(target_hmc_ip, target_hmc_user,
                              target_hmc_passwd, remote_hmc)

        cmd = "migrlpar -o v -m %s -t %s -p %s -u %s --ip %s" % (
        src_mg_system, dest_mg_system, self.lpar_name, target_hmc_user, target_hmc_ip)
        hmc.ssh.run_command(cmd, timeout=timeout)
        
        cmd = "migrlpar -o m -m %s -t %s -p %s -u %s --ip %s %s" % (src_mg_system,
        dest_mg_system, self.lpar_name, target_hmc_user, target_hmc_ip, param)
        if options:
            cmd = "%s %s" % (cmd, options)
        hmc.ssh.run_command(cmd, timeout=timeout)

    def recover_lpar(self, src_mg_system, dest_mg_system, stop_lpm=False, timeout=300):
        if stop_lpm:
            self.ssh.run_command("migrlpar -o s -m %s -p %s" % (
                src_mg_system, self.lpar_name), timeout=timeout)
        self.ssh.run_command("migrlpar -o r -m %s -p %s" % (
                src_mg_system, self.lpar_name), timeout=timeout)
        if not self.is_lpar_in_managed_system(dest_mg_system, self.lpar_name):
            log.info("LPAR recovered at managed system %s" % src_mg_system)
            return True
        log.info("LPAR failed to recover at managed system %s" % src_mg_system)
        return False

    def get_adapter_id(self, mg_system, loc_code):
        cmd = 'lshwres -m {} -r sriov --rsubtype adapter -F phys_loc:adapter_id'.format(mg_system)
        adapter_id_output = self.ssh.run_command(cmd)
        for line in adapter_id_output:
            if str(loc_code) in line:
                return line.split(':')[1]
        return ''

    def get_lpar_id(self, mg_system, l_lpar_name):
        cmd = 'lssyscfg -m %s -r lpar --filter lpar_names=%s -F lpar_id' % (mg_system, l_lpar_name)
        lpar_id_output = self.ssh.run_command(cmd)
        for line in lpar_id_output:
            if l_lpar_name in line:
                return 0
            return line
        return 0

    def is_msp_enabled(self, mg_system, vios_name):
        '''
        The function checks if the moving service option is enabled
        on the given lpar partition.
        '''
        cmd = "lssyscfg -m %s -r lpar --filter lpar_names=%s -F msp" % (
                mg_system, vios_name)
        msp_output = self.ssh.run_command(cmd)
        if int(msp_output[0]) != 1:
            return False
        return True

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        return self.ssh.run_command_ignore_fail(command, timeout*self.timeout_factor, retry)

    def run_command(self, i_cmd, timeout=15):
        return self.ssh.run_command(i_cmd, timeout)


class OpTestHMC(HMCUtil):
    '''
    This class contains the modules to perform various HMC operations on an LPAR.
    The Host IP, username and password of HMC have to be passed to the class intially
    while creating the object for the class.
    '''

    def __init__(self, hmc_ip, user_name, password, scratch_disk="", proxy="",
                 logfile=sys.stdout, managed_system=None, lpar_name=None, prompt=None,
                 block_setup_term=None, delaybeforesend=None, timeout_factor=1,
                 lpar_prof=None, lpar_vios=None, lpar_user=None, lpar_password=None,
                 check_ssh_keys=False, known_hosts_file=None, tgt_managed_system=None,
                 tgt_lpar=None):
        super(OpTestHMC, self).__init__(hmc_ip, user_name, password, scratch_disk,
                                        proxy, logfile, managed_system, lpar_name, prompt,
                                        block_setup_term, delaybeforesend, timeout_factor,
                                        lpar_prof, lpar_vios, lpar_user, lpar_password,
                                        check_ssh_keys, known_hosts_file, tgt_managed_system,
                                        tgt_lpar)

        self.console = HMCConsole(hmc_ip, user_name, password, managed_system, lpar_name,
                                  lpar_vios, lpar_prof, lpar_user, lpar_password)

    def set_system(self, system):
        self.system = system
        self.ssh.set_system(system)
        self.console.set_system(system)

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
    Methods to manage the console of LPAR
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
        self.util = OpTestUtil()
        self.expect_prompt = self.util.build_prompt(prompt) + "$"
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
        self.prompt = prompt
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

    def set_system(self, system):
        self.ssh.set_system(system)
        self.system = system
        self.pty = self.get_console()
        self.pty.set_system(system)

    def get_host_console(self):
        return self.pty

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

        log.info("De-activating the console")
        self.deactivate_lpar_console()

        log.debug("#HMC Console CONNECT")

        command = "sshpass -p %s ssh -p 22 -l %s %s -o PubkeyAuthentication=no"\
                  " -o afstokenpassing=no -q -o 'UserKnownHostsFile=/dev/null'"\
                  " -o 'StrictHostKeyChecking=no'"
        try:
            self.pty = Spawn(
                command % (self.passwd, self.user, self.hmc_ip))
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
            else:
                raise OpTestError("Check the lpar activate command")
        except Exception as exp:
            self.state = ConsoleState.DISCONNECTED
            raise CommandFailed('OPexpect.spawn',
                                'OPexpect.spawn encountered a problem: ' + str(exp), -1)


        if self.delaybeforesend:
            self.pty.delaybeforesend = self.delaybeforesend

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
            l_rc = self.pty.expect(["login:", pexpect.TIMEOUT], timeout=30)
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
        i = self.pty.expect(["login:", self.expect_prompt, pexpect.TIMEOUT], timeout=30)
        if i == 0:
            log.debug("System has booted")
            time.sleep(STALLTIME)
        elif i == 1:
            log.debug("Console already logged in")
        else:
            log.error("Failed to get login prompt %s", self.pty.before)
            # To cheat system for making using of HMC SSH
            self.system.PS1_set = 1
            self.system.LOGIN_set = 1
            self.system.SUDO_set = 1
        return self.pty

    def run_command(self, i_cmd, timeout=15):
        return self.util.run_command(self, i_cmd, timeout)

