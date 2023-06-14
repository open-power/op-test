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

'''
OpTestHMC
---------

Hardware Management Console (HMC) package contains all HMC related
interfaces/functions.

This package encapsulates all HMC functions required to manage/control IBM Power
server running PowerVM hypervisor.
'''

import os
import sys
import time
import pexpect
import shlex
import re

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

class OpSecureBootUtilities():
    '''
    This class addresses the secureboot related pre-requisites.
    '''

    def __init__(self, console=None, distro=None):
        self.console = console
        self.distro = distro

    def check_kernel_signature(self):
        '''
        Check whether the kernel is signed or unsigned.
        If, string - "Module signature appended" is found,
        then the kernel is signed, else, the kernel is unsigned.
        '''
        vmlinux = "vmlinuz"  # RHEL
        if self.distro == 'SLES' or self.distro == "suse":
            vmlinux = "vmlinux"

        cmd = "strings /boot/%s-$(uname -r) | tail -1" % vmlinux
        output = self.console.run_command(cmd)
        if "Module signature appended" in output[0]:
            return "signed_kernel"
        return "unsigned_kernel"

    def check_os_level_secureboot_state(self):
        '''
        Check whether the secure-boot is enabled at os level.
        To do this, check the entry of "00000002" in "/proc/device-tree/ibm,secure-boot" file.
        If found, then secure-boot is enabled.
        '''
        cmd = "lsprop /proc/device-tree/ibm,secure-boot"
        output = self.console.run_command(cmd)
        for line in output:
            if '00000002' in line:
                return True
        return False

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
        '''
        Deactivate/disconnect the LPAR Console
        '''
        self.ssh.run_command("rmvterm -m %s -p %s" %
                         (self.mg_system, self.lpar_name), timeout=10)

    def poweroff_system(self):
        '''
        PowerOFF the managed system
        '''
        if self.get_system_state() != OpManagedState.OPERATING:
            raise OpTestError('Managed Systen not in Operating state')
        self.ssh.run_command("chsysstate -m %s -r sys -o off" % self.mg_system)
        self.wait_system_state(OpManagedState.OFF)

    def poweron_system(self):
        '''
        PowerON the managed system
        '''
        if self.get_system_state() != OpManagedState.OFF:
            raise OpTestError('Managed Systen not is Power off state!')
        self.ssh.run_command("chsysstate -m %s -r sys -o on" % self.mg_system)
        self.wait_system_state()
        if self.lpar_vios:
            log.debug("Starting VIOS %s", self.lpar_vios)
            self.poweron_lpar(vios=True)

    def poweroff_lpar(self, remote_hmc=None):
        '''
        PowerOFF the LPAR

        :param remote_hmc: object, remote HMC instance
        '''
        hmc = remote_hmc if remote_hmc else self
        if self.get_lpar_state(remote_hmc=remote_hmc) in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        hmc.ssh.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed" %
                         (hmc.mg_system, self.lpar_name))
        self.wait_lpar_state(OpHmcState.NOT_ACTIVE, remote_hmc=remote_hmc)

    def poweron_lpar(self, vios=False, remote_hmc=None):
        '''
        PowerON the LPAR

        :param vios: Boolean, to identify VIOS partition
        :param remote_hmc: object, remote HMC instance
        :returns: BMC_CONST.FW_SUCCESS up on success
        '''
        hmc = remote_hmc if remote_hmc else self
        if self.get_lpar_state(vios, remote_hmc=remote_hmc) == OpHmcState.RUNNING:
            log.info('LPAR Already powered on!')
            return BMC_CONST.FW_SUCCESS
        lpar_name = self.lpar_name
        if vios:
            lpar_name = hmc.lpar_vios
        cmd = "chsysstate -m %s -r lpar -n %s -o on" % (hmc.mg_system, lpar_name)

        if self.lpar_prof:
            cmd = "%s -f %s" % (cmd, self.lpar_prof)

        self.wait_lpar_state(OpHmcState.NOT_ACTIVE, vios=vios, remote_hmc=remote_hmc)
        hmc.ssh.run_command(cmd)
        self.wait_lpar_state(vios=vios, remote_hmc=remote_hmc)
        time.sleep(STALLTIME)
        return BMC_CONST.FW_SUCCESS

    def dumprestart_lpar(self):
        '''
        Capture dump and restart the LPAR
        '''
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.ssh.run_command("chsysstate -m %s -r lpar -n %s -o dumprestart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def restart_lpar(self):
        '''
        Restart LPAR immediately
        '''
        if self.get_lpar_state() in [OpHmcState.NOT_ACTIVE, OpHmcState.NA]:
            log.info('LPAR Already powered-off!')
            return
        self.ssh.run_command("chsysstate -m %s -r lpar -n %s -o shutdown --immed --restart" %
                         (self.mg_system, self.lpar_name))
        self.wait_lpar_state()

    def get_lpar_cfg(self):
        '''
        Get LPAR configuration parameters

        :returns: LPAR configuration parameters in key, value pair
        '''
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
        '''
        Set LPAR configuration parameter values

        :param arg_str: configuration values in key, value pair seperated by
                        comma
        '''
        if not self.lpar_prof:
            raise OpTestError("Profile needs to be defined to use this method")
        self.ssh.run_command("chsyscfg -r prof -m %s -i 'lpar_name=%s,name=%s,%s' --force" %
                (self.mg_system, self.lpar_name, self.lpar_prof,arg_str))

    def change_proc_mode(self, proc_mode, sharing_mode, min_proc_units, desired_proc_units, max_proc_units, overcommit_ratio=1):
        '''
        Sets processor mode to shared or dedicated based on proc_mode

        :param proc_mode: "shared" or "ded", to change proc mode to shared or dedicated
        :param sharing_mode: "cap", "uncap", "share_idle_procs" to specify the sharing mode.
        :param min_proc_units: minimum number of processing units.
        :param desired_proc_units: desired number of processing units
        :param max_proc_units: maximum number of processing units
        :param overcommit_ratio: overcommit ratio can be 1 to 5 for ideal cases
        '''
        if proc_mode == 'shared':
            self.set_lpar_cfg("proc_mode=shared,sharing_mode=%s,min_proc_units=%s,max_proc_units=%s,"
                              "desired_proc_units=%s,min_procs=%s,desired_procs=%s,max_procs=%s" %
                              (sharing_mode, min_proc_units, max_proc_units, desired_proc_units,
                               overcommit_ratio*int(min_proc_units), overcommit_ratio*int(desired_proc_units),
                               overcommit_ratio*int(max_proc_units)))
        elif proc_mode == 'ded':
            self.set_lpar_cfg("proc_mode=ded,sharing_mode=%s,min_procs=%s,max_procs=%s,desired_procs=%s" %
                             (sharing_mode, min_proc_units, max_proc_units, desired_proc_units))
        else:
            log.info("Please pass valid proc_mode, \"shared\" or \"ded\"")

    def get_proc_mode(self):
        '''
        Checks if the lpar is in shared mode or dedicated mode.

        :returns: "shared" if lpar is in shared mode, "ded" if lpar is in dedicated mode.
        '''
        return self.run_command("lshwres -r proc -m %s --level lpar --filter lpar_names=%s -F curr_proc_mode" %
                               (self.mg_system, self.lpar_name))

    def enable_disable_vtpm(self, vtpm_mode):
        '''
        Enables or disables vtpm mode.

        :param vtpm_mode: Enables vtpm if vtpm_mode is 1 and disables vtpm if vtpm_mode is 0
        '''
        self.run_command("chsyscfg -r lpar -m %s -i \"name=%s, vtpm_enabled=%s\"" %
                               (self.mg_system, self.lpar_name, vtpm_mode))
        time.sleep(5)

    def vtpm_state(self):
        '''
        Get vtpm state for the lpar

        :returns: 0 if vtpm is disabled, 1 if vtpm is enabled
        '''
        return self.run_command("lssyscfg -m %s -r lpar --filter lpar_names=%s -F vtpm_enabled" %
                                      (self.mg_system, self.lpar_name))

    def vpmem_count(self):
        '''
        Get number of vpmem volumes configured for lpar

        :returns: number of vpmem volumes on the lpar
        '''
        return self.run_command("lshwres -r pmem -m %s --level lpar --filter lpar_names=%s -F curr_num_volumes" %
                                      (self.mg_system, self.lpar_name))

    def configure_vpmem(self, pmem_name, pmem_size):
        '''
        Configures vpmem on lpar

        :param pmem_name: name of vpmem volume
        :param pmem_size: size of vpmem volume, should be multiple of lmb size
        '''
        self.run_command("chhwres -r pmem -m %s -o a --rsubtype volume --volume %s --device dram -p %s -a size=%s,affinity=1" %
                               (self.mg_system, pmem_name, self.lpar_name, pmem_size)) 

    def profile_bckup(self):
        '''
        Takes lpar profile backup
        '''
        self.run_command("mksyscfg -r prof -m %s -o save -p %s -n %s_bck --force" %
                        (self.mg_system, self.lpar_name, self.lpar_prof))

    def configure_lmb(self, lmb_size):
        '''
        Configures managed system with LMB size passed as argument

        :param lmb_size: LMB size to configure on managed system
         Valid LMB values are "128,256,1024,2048,4096"
        '''
        self.run_command("chhwres -m %s -r mem -o s -a pend_mem_region_size=%s" %
                               (self.mg_system, lmb_size))
        time.sleep(2)

    def get_lmb_size(self):
        '''
        Get current LMB size

        :returns: current lmb size of managed system
        '''
        return self.run_command("lshwres -r mem -m %s --level sys -F mem_region_size" % self.mg_system)

    def get_lpar_state(self, vios=False, remote_hmc=None):
        '''
        Get current state of LPAR

        :param vios: Boolean, to identify VIOS partition
        :param remote_hmc: object, remote HMC instance
        :returns: the current status of the LPAR e.g 'Running' or 'Booting'
        '''
        hmc = remote_hmc if remote_hmc else self
        lpar_name = self.lpar_name
        if vios:
            lpar_name = hmc.lpar_vios
        state = hmc.ssh.run_command(
            'lssyscfg -m %s -r lpar --filter lpar_names=%s -F state' % (hmc.mg_system, lpar_name))[-1]
        ref_code = hmc.ssh.run_command(
            'lsrefcode -m %s -r lpar --filter lpar_names=%s -F refcode' % (hmc.mg_system, lpar_name))[-1]
        if state == 'Running':
            if 'Linux' in ref_code or not ref_code:
                return 'Running'
            else:
                return 'Booting'
        return state

    def get_system_state(self):
        '''
        Get current state of managed system

        :returns: the current status of the managed system
        '''
        state = self.ssh.run_command(
            'lssyscfg -m %s -r sys -F state' % self.mg_system)
        return state[-1]

    def wait_lpar_state(self, exp_state=OpHmcState.RUNNING, vios=False, timeout=WAITTIME, remote_hmc=None):
        '''
        Wait for a particular state of LPAR

        :param exp_state: constant, expected HMC STATE, default is OpHmcState.RUNNING
        :param vios: Boolean, to identify VIOS partition
        :param timeout: number, Wait time in seconds
        :param remote_hmc: object, remote HMC instance
        :raises: :class:`common.OpTestError` when the timeout happens
        '''
        state = self.get_lpar_state(vios, remote_hmc=remote_hmc)
        count = 0
        while state != exp_state:
            state = self.get_lpar_state(vios, remote_hmc=remote_hmc)
            log.info("Current state: %s", state)
            time.sleep(timeout)
            count += 1
            if count > 120:
                raise OpTestError("Time exceeded for reaching %s" % exp_state)

    def wait_system_state(self, exp_state=OpManagedState.OPERATING, timeout=SYS_WAITTIME):
        '''
        Wait for a particular state of managed system

        :param exp_state: constatn, expected STATE, default is OpManagedState.OPERATING
        :param timeout: number, Wait time in seconds
        :raises: :class:`common.OpTestError` when the timeout happens
        '''
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
        '''
        Check if LPAR is available on a managed system

        :param mg_system: string, managed system name
        :param lpar_name: string, LPAR name
        :param remote_hmc: object, remote HMC instance
        :returns: True  - when the LPAR is in managed system
                  False - when the LPAR is not in managed system
        '''
        hmc = remote_hmc if remote_hmc else self
        lpar_list = hmc.ssh.run_command(
                   'lssyscfg -r lpar -m %s -F name' % mg_system)
        if lpar_name in lpar_list:
            log.info("%s lpar found in managed system %s" % (lpar_name, mg_system))
            return True
        return False

    def migrate_lpar(self, src_mg_system=None, dest_mg_system=None, options=None, param="", timeout=300):
        '''
        Migrate the LPAR from source managed system to the destination managed
        system

        :param src_mg_system: string, source managed system name
        :param dest_mg_system: string, destination manages system name
        :param options: string, options for migration
        :param param: string, required parameters for migration
        :param timeout: number, time out value in seconds, default 300
        :returns: True  - when LPAR migration success
                  False - when LPAR migration unsuccess
        '''
        if src_mg_system == None or dest_mg_system == None:
            raise OpTestError("Source and Destination Managed System required for LPM")
        if not self.is_lpar_in_managed_system(src_mg_system, self.lpar_name):
            raise OpTestError("Lpar %s not found in managed system %s" % (self.lpar_name, src_mg_system))
        for mode in ['v', 'm']:
            cmd = 'migrlpar -o %s -m %s -t %s -p %s %s' % (
                   mode, src_mg_system, dest_mg_system, self.lpar_name, param)
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
        '''
        Set SSH authentication keys

        :param hmc_ip: number, in ip address format
        :param hmc_user: string, HMC user name
        :param hmc_passwd: string, HMC user password
        :param remote_hmc: object, remote HMC instance
        :raises: `CommandFailed`
        '''
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
        '''
        migration of LPAR across HMC

        :param src_mg_system: string, Source managed system
        :param dest_mg_system: string, Destination managed system
        :param target_hmc_ip: number, in IP address format
        :param target_hmc_user: string, target HMC user name
        :param target_hmc_passwd: string, target HMC user password
        :param remote_hmc: object, remote HMC instance
        :param options: string, migration options
        :param param: string, migration parameters
        :param timeout: number, time in seconds
        '''
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

        for mode in ['v', 'm']:
            cmd = "migrlpar -o %s -m %s -t %s -p %s -u %s --ip %s %s" % (mode, src_mg_system,
                   dest_mg_system, self.lpar_name, target_hmc_user, target_hmc_ip, param)
            if options:
                cmd = "%s %s" % (cmd, options)
            hmc.ssh.run_command(cmd, timeout=timeout)

    def recover_lpar(self, src_mg_system, dest_mg_system, stop_lpm=False, timeout=300):
        '''
        Recover LPAR

        :param src_mg_system: string, Source managed system
        :param dest_mg_system: string, Destination managed system
        :param stop_lpm: Boolean, to stop migration, default False
        :param timeout: number, time in seconds
        :returns: True  - when LPAR recovery success
                  False - when LPAR recovery unsuccess
        '''
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

    def get_adapter_id(self, mg_system, loc_code, remote_hmc=None):
        '''
        Get SRIOV adapter id

        :param mg_system: string, Source managed system
        :param loc_code: string, adapater
        :param remote_hmc: object, remote HMC instance
        :returns: string, adapter id
        '''
        hmc = remote_hmc if remote_hmc else self
        cmd = 'lshwres -m {} -r sriov --rsubtype adapter -F phys_loc:adapter_id'.format(mg_system)
        adapter_id_output = hmc.ssh.run_command(cmd)
        for line in adapter_id_output:
            if str(loc_code) in line:
                return line.split(':')[1]
        return ''

    def get_lpar_id(self, mg_system, l_lpar_name, remote_hmc=None):
        '''
        Get LPAR id

        :param mg_system: string, Source managed system
        :param l_lpar_name: string, LPAR name
        :param remote_hmc: object, remote HMC instance
        :returns: number, LPAR id on success, 0 on failure
        '''
        hmc = remote_hmc if remote_hmc else self
        cmd = 'lssyscfg -m %s -r lpar --filter lpar_names=%s -F lpar_id' % (mg_system, l_lpar_name)
        lpar_id_output = hmc.ssh.run_command(cmd)
        for line in lpar_id_output:
            if l_lpar_name in line:
                return 0
            return line
        return 0

    def is_msp_enabled(self, mg_system, vios_name, remote_hmc=None):
        '''
        The function checks if the moving service option is enabled
        on the given lpar partition.

        :param mg_system: string, Source managed system
        :param vios_name: string, VIOS name
        :param remote_hmc: object, remote HMC instance
        :returns: Boolean, True on success, False on failure
        '''
        hmc = remote_hmc if remote_hmc else self
        cmd = "lssyscfg -m %s -r lpar --filter lpar_names=%s -F msp" % (
                mg_system, vios_name)
        msp_output = hmc.ssh.run_command(cmd)
        if int(msp_output[0]) != 1:
            return False
        return True

    def gather_logs(self, list_of_commands=[], remote_hmc=None, output_dir=None):
        '''
        Gather the logs for the commands at the given directory

        :param list_of_commands: list, list of commands
        :param remote_hmc: object, remote HMC instance
        :param output_dir: string, dir to store logs
        :returns: Boolean, True on success, False on failure
        :raises: `CommandFailed`
        '''
        hmc = remote_hmc if remote_hmc else self
        if not output_dir:
            output_dir = "HMC_Logs_%s" % (time.asctime(time.localtime())).replace(" ", "_")
        output_dir = os.path.join(self.system.cv_HOST.results_dir, output_dir, "hmc-"+hmc.hmc_ip)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        default_commands = ['lshmc -V', 'pedbg -c -q 4']
        list_of_commands.extend(default_commands)

        try:
            for cmd in set(list_of_commands):
                output = "\n".join(hmc.run_command(r"%s" % cmd, timeout=1800))
                filename = "%s.log" % '-'.join((re.sub(r'[^a-zA-Z0-9]', ' ', cmd)).split())
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'w') as f:
                    f.write(output)
            log.warn("Please collect the pedbg logs immediately. At risk of being overwritten.")
            return True
        except CommandFailed as cmd_failed:
            raise cmd_failed

    def run_command_ignore_fail(self, command, timeout=60, retry=0):
        '''
        Wrapper function for `ssh.run_command_ignore_fail`

        :param command: string, command
        :param timeout: number, time out in seconds
        :param retry: number, number of retries
        '''
        return self.ssh.run_command_ignore_fail(command, timeout*self.timeout_factor, retry)

    def run_command(self, i_cmd, timeout=15):
        '''
        Wrapper function for `ssh.run_command`

        :param i_cmd: string, command
        :param timeout: number, time out in seconds
        '''
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
        '''
        Set system values
        '''
        self.ssh.set_system(system)
        self.system = system
        self.pty = self.get_console()
        self.pty.set_system(system)

    def get_host_console(self):
        '''
        Get host console

        :returns: string, Host console name
        '''
        return self.pty

    def set_system_setup_term(self, flag):
        '''
        Set system setup terminal

        :param flag: string, value to set system setup terminal
        '''
        self.system.block_setup_term = flag

    def get_system_setup_term(self):
        '''
        Get system setup terminal

        :returns: string, system setup terminal
        '''
        return self.system.block_setup_term

    def get_scratch_disk(self):
        '''
        Get scratch disk name

        :returns: string, scratch disk name
        '''
        return self.scratch_disk

    def get_proxy(self):
        '''
        Get proxy name

        :returns: string, proxy name
        '''
        return self.proxy

    def hostname(self):
        '''
        Get HMC IP address

        :returns: number, in IP format
        '''
        return self.hmc_ip

    def username(self):
        '''
        Get HMC user name

        :returns: string, HMC user name
        '''
        return self.user

    def password(self):
        '''
        Get HMC password

        :returns: string, HMC password
        '''
        return self.passwd

    def set_block_setup_term(self, flag):
        '''
        Set block setup terminal

        :param flag: string, to set block setup terminal
        '''
        self.block_setup_term = flag

    def get_block_setup_term(self):
        '''
        Get block setup terminal

        :returns: string, block setup terminal name
        '''
        return self.block_setup_term

    def enable_setup_term_quiet(self):
        '''
        Enable terminal quiet values
        '''
        self.setup_term_quiet = 1
        self.setup_term_disable = 0

    def disable_setup_term_quiet(self):
        '''
        Disable terminal quiet values
        '''
        self.setup_term_quiet = 0
        self.setup_term_disable = 0

    def close(self):
        '''
        Close HMC console

        :raises: `pexpect.ExceptionPexpect`
        '''
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
        '''
        Gets LPAR console using mkvterm

        :param logger: string, name of the logger to use other than default log
        :raises: `CommandFailed`
        :returns: object, LPAR console using mkvterm
        '''
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
        '''
        Get HMC state

        :returns: string, HMC state
        '''
        return self.state

    def get_console(self, logger=None):
        '''
        Get HMC console from 'connect' API, wait till the Operating System boot
        complete and set the command prompt.

        :param logger: string, name of the logger to use other than default log
        :returns: object, HMC console with command prompt set
        '''
        if self.state == ConsoleState.DISCONNECTED:
            self.util.clear_state(self)
            self.connect(logger=logger)
            time.sleep(STALLTIME)
            l_rc = self.pty.expect(["login:", pexpect.TIMEOUT], timeout=30)
            if l_rc == 0:
                self.pty.send('\r')
                # In case when OS reboot/multireboot test and we lose prompt, reset prompt
                self.system.LOGIN_set = -1
                self.system.PS1_set = -1
                self.system.SUDO_set = -1
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
        '''
        Get login prompt

        :returns: string, HMC console prompt
        '''
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
        '''
        Wrapper command for run_command from util
        '''
        return self.util.run_command(self, i_cmd, timeout)

