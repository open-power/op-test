#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestVtpm.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2025
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

'''
OpTestVtpm
----------
Standalone enable and disable tests for vTPM (Virtual Trusted Platform
Module) on IBM Power LPARs managed via HMC.

Designed to be used as a suite that mirrors GuestSecureBootSuite:

    op-test -c <lpar.cfg> --run-suite GuestVtpmSuite \
            --host-cmd-file <workload.cfg> --host-cmd-timeout 7200

Suite sequence:
    VtpmEnable  ->  RunHostTest (optional workload)  ->  VtpmDisable

Design notes
------------
- Calls cv_HMC.enable_vtpm() / disable_vtpm() / vtpm_state() directly.
  No conf.args.machine_config is read or written, so this module is safe
  to import and instantiate at runner startup without --machine-config
  being present in the cfg file.
- vTPM version (1.2 or 2.0) and encryption algorithm are resolved from
  the LPAR processor compatibility mode at setUp() time, matching the
  logic already proven in MachineConfig.LparConfig.LparSetup().
- Supported processor compatibility modes:
    POWER10 / POWER11  ->  vTPM 2.0, encryption from vtpm_encryption cfg
                           param (default "Power10v1")
    POWER9 / POWER9_base / POWER8  ->  vTPM 1.2, no encryption param
- bmc_type must be FSP_PHYP or EBMC_PHYP; test is skipped otherwise.

Required cfg parameters (standard HMC LPAR setup):
    bmc_type, hmc_ip, hmc_username, hmc_password,
    lpar_name, system_name, lpar_prof,
    host_ip, host_user, host_password

Optional cfg parameters:
    vtpm_encryption   Encryption algorithm for vTPM 2.0 (default: Power10v1)
'''

import unittest

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Processor modes that select vTPM 2.0
_VTPM2_PROC_MODES = ('POWER10', 'POWER11')
# Default encryption algorithm when vtpm_encryption is not in the cfg file
_VTPM2_DEFAULT_ENCRYPTION = 'Power10v1'


class OpTestVtpm(unittest.TestCase):
    '''
    Base class shared by VtpmEnable and VtpmDisable.

    Wires up HMC/system handles in setUp() and provides the shared
    helpers _resolve_vtpm_version(), _enable_vtpm(), _disable_vtpm().
    Subclasses only implement runTest().
    '''

    def setUp(self):
        conf = OpTestConfiguration.conf

        if conf.args.bmc_type not in ('FSP_PHYP', 'EBMC_PHYP'):
            self.skipTest(
                'OpTestVtpm requires bmc_type FSP_PHYP or EBMC_PHYP'
            )

        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.c = self.cv_HMC.get_host_console()
        self.hmc_con = self.cv_HMC.ssh

        try:
            self.vtpm_encryption = conf.args.vtpm_encryption
        except AttributeError:
            self.vtpm_encryption = _VTPM2_DEFAULT_ENCRYPTION

    # ------------------------------------------------------------------ #

    def _resolve_vtpm_version(self):
        '''
        Query current LPAR processor compatibility mode and return the
        appropriate vTPM version and encryption setting.

        :returns: (float vtpm_version, str|None vtpm_encryption)
        '''
        proc_compat = self.cv_HMC.get_proc_compat_mode()
        mode = proc_compat[0] if proc_compat else ''
        if any(p in mode for p in _VTPM2_PROC_MODES):
            log.info('Processor mode %s -> vTPM 2.0 (encryption=%s)',
                     mode, self.vtpm_encryption)
            return 2.0, self.vtpm_encryption
        log.info('Processor mode %s -> vTPM 1.2', mode)
        return 1.2, None

    # ------------------------------------------------------------------ #

    def _enable_vtpm(self):
        '''
        Enable vTPM on the LPAR:
          1. Read current vtpm_enabled state; skip HMC call if already 1.
          2. Power off LPAR via HMC.
          3. Resolve vTPM version from processor compat mode.
          4. Call cv_HMC.enable_vtpm(version, encryption).
          5. Power on LPAR and wait for OS via goto_state(OS).
          6. Assert vtpm_state() == "1".
        '''
        current = self.cv_HMC.vtpm_state()
        if current[0] == '1':
            log.info('vTPM already enabled; no HMC change needed')
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            return

        log.info('Powering off LPAR before enabling vTPM')
        self.cv_HMC.poweroff_lpar()

        vtpm_version, vtpm_encryption = self._resolve_vtpm_version()
        log.info('Enabling vTPM %.1f via HMC chsyscfg', vtpm_version)
        self.cv_HMC.enable_vtpm(vtpm_version, vtpm_encryption)

        log.info('Powering on LPAR after vTPM enable')
        self.cv_SYSTEM.set_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        state = self.cv_HMC.vtpm_state()
        self.assertEqual(
            state[0], '1',
            'HMC reports vtpm_enabled=%s after enable — expected 1' % state[0]
        )
        log.info('vTPM enable confirmed: vtpm_enabled=1')

    # ------------------------------------------------------------------ #

    def _disable_vtpm(self):
        '''
        Disable vTPM on the LPAR:
          1. Read current vtpm_enabled state; skip HMC call if already 0.
          2. Power off LPAR via HMC.
          3. Call cv_HMC.disable_vtpm().
          4. Power on LPAR and wait for OS via goto_state(OS).
          5. Assert vtpm_state() == "0".
        '''
        current = self.cv_HMC.vtpm_state()
        if current[0] == '0':
            log.info('vTPM already disabled; no HMC change needed')
            self.cv_SYSTEM.goto_state(OpSystemState.OS)
            return

        log.info('Powering off LPAR before disabling vTPM')
        self.cv_HMC.poweroff_lpar()

        log.info('Disabling vTPM via HMC chsyscfg (vtpm_enabled=0)')
        self.cv_HMC.disable_vtpm()

        log.info('Powering on LPAR after vTPM disable')
        self.cv_SYSTEM.set_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        state = self.cv_HMC.vtpm_state()
        self.assertEqual(
            state[0], '0',
            'HMC reports vtpm_enabled=%s after disable — expected 0' % state[0]
        )
        log.info('vTPM disable confirmed: vtpm_enabled=0')


# ======================================================================= #
#  Runnable test classes                                                   #
# ======================================================================= #

class VtpmEnable(OpTestVtpm):
    '''
    Enable vTPM on the LPAR via HMC and boot to OS.

    Run standalone:
      op-test -c <lpar.cfg> --run testcases.OpTestVtpm.VtpmEnable
    '''

    def runTest(self):
        self._enable_vtpm()


class VtpmDisable(OpTestVtpm):
    '''
    Disable vTPM on the LPAR via HMC and boot to OS.

    Run standalone:
      op-test -c <lpar.cfg> --run testcases.OpTestVtpm.VtpmDisable
    '''

    def runTest(self):
        self._disable_vtpm()


