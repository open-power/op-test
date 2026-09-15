#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
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
#Author: Shirisha Ganta <shirisha@linux.ibm.com>

'''
OpTestLparRename
----------------

While the LPAR is running, rename it via an HMC command and verify:

  Step 1 - Record original name from HMC (lssyscfg).
  Step 2 - Rename on HMC (chsyscfg new_name=).
  Step 3 - Confirm HMC now shows the new name (lssyscfg).
  Step 4 - Run lparstat -i inside the running OS and record the Partition Name.
           NOTE: PowerVM does NOT push a live rename into the running kernel.
           The device-tree Partition Name is frozen at boot time, so lparstat
           will still show the OLD name here — that is expected behaviour.
  Step 5 - Reboot the LPAR via HMC (chsysstate --restart) and wait for OS.
  Step 6 - Run lparstat -i again after reboot and ASSERT it now shows the
           new name — the device-tree is refreshed on every boot.
  Step 7 - Restore the original LPAR name on HMC (chsyscfg new_name=).
  Step 8 - Confirm HMC shows the restored original name (lssyscfg).
  Step 9 - Run lparstat -i immediately after restore (informational —
           device-tree still holds the renamed value until next reboot).
  Step 10 - Reboot the LPAR again and wait for OS.
  Step 11 - Run lparstat -i after the restore-reboot and ASSERT it shows
            the original name — confirming the restore is fully reflected.

Prerequisites:
  hmc_ip, hmc_username, hmc_password, system_name, lpar_name must be set
  in ~/.op-test-framework.conf (or passed on the command line).
  The LPAR must already be in Running state.

Optional conf key:
  new_lpar_name  Temporary name to use (default: <original>-renamed).
'''

import time
import unittest

import OpTestConfiguration
import OpTestLogger

from common.OpTestError import OpTestError
from common.OpTestHMC import OpHmcState
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Seconds to wait after the HMC rename before querying lparstat (pre-reboot).
RENAME_SETTLE_TIME = 5
# Seconds to wait for SSH to become available after reboot before retrying.
POST_REBOOT_SSH_WAIT = 30
# Number of SSH retry attempts while waiting for OS to come back after reboot.
POST_REBOOT_SSH_RETRIES = 20


class OpTestLparRename(unittest.TestCase):
    '''Rename a live LPAR via HMC and verify lparstat -i output is recorded.'''

    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.cv_HMC = self.cv_SYSTEM.hmc
        # Direct SSH to the LPAR OS — independent of the HMC serial console,
        # so a mid-test LPAR rename cannot break the connection.
        self.host = self.conf.host()
        self.system_name = self.conf.args.system_name
        self.original_name = self.conf.args.lpar_name
        try:
            self.new_name = self.conf.args.new_lpar_name
        except AttributeError:
            self.new_name = None
        if not self.new_name:
            self.new_name = self.original_name + "-renamed"
        lpar_state = self.cv_HMC.get_lpar_state()
        if lpar_state != OpHmcState.RUNNING:
            raise unittest.SkipTest(
                "LPAR is not Running (state=%s); test requires a live LPAR"
                % lpar_state)


    def _hmc_get_lpar_name(self):
        out = self.cv_HMC.run_command(
            "lssyscfg -r lpar -m %s --filter lpar_names=%s -F name"
            % (self.system_name, self.cv_HMC.lpar_name))
        return out[0].strip()

    def _hmc_rename_lpar(self, current_name, target_name):
        self.cv_HMC.run_command(
            "chsyscfg -r lpar -m %s -i \"name=%s,new_name=%s\""
            % (self.system_name, current_name, target_name))
        # Keep both HMCUtil and HMCConsole lpar_name in sync so that any
        # future call that uses the LPAR name (e.g. rmvterm) still works.
        self.cv_HMC.lpar_name = target_name
        self.cv_HMC.console.lpar_name = target_name

    def _os_get_lpar_name(self):
        '''Return the Partition Name field from lparstat -i inside the OS.
        Uses direct SSH to the host IP — no dependency on the HMC console
        or the current LPAR name registered on the HMC.
        '''
        lines = self.host.run_command("lparstat -i")
        for line in lines:
            if "Partition Name" in line:
                return line.split(":", 1)[-1].strip()
        raise OpTestError(
            "Could not find 'Partition Name' in lparstat -i output:\n%s"
            % "\n".join(lines))


    def _reboot_and_wait(self):
        '''Reboot the LPAR via HMC and wait until the OS is back up via SSH.'''
        log.info("Rebooting LPAR '%s' via HMC ...", self.cv_HMC.lpar_name)
        self.cv_HMC.run_command(
            "chsysstate -m %s -r lpar -n %s -o shutdown --immed --restart"
            % (self.system_name, self.cv_HMC.lpar_name))

        self.cv_HMC.wait_lpar_state(OpHmcState.RUNNING)
        time.sleep(POST_REBOOT_SSH_WAIT)
        self.host.run_command("uptime", retry=POST_REBOOT_SSH_RETRIES)
        log.info("SSH is up — OS is ready after reboot")

    def runTest(self):
        try:
            name_before = self._hmc_get_lpar_name()
            self.assertEqual(
                name_before, self.original_name,
                "HMC reports '%s' but conf says '%s'; check configuration"
                % (name_before, self.original_name))
            log.info("Step 1 PASS: HMC confirms original name '%s'",
                     name_before)
            self._hmc_rename_lpar(self.original_name, self.new_name)

            name_hmc = self._hmc_get_lpar_name()
            self.assertEqual(
                name_hmc, self.new_name,
                "HMC still shows '%s' after rename (expected '%s')"
                % (name_hmc, self.new_name))
            log.info("Step 3 PASS: HMC now reports new name '%s'", name_hmc)
            time.sleep(RENAME_SETTLE_TIME)
            name_os_before = self._os_get_lpar_name()
            # Device-tree is frozen at boot; old name is expected here.
            if name_os_before not in (self.original_name, self.new_name):
                self.fail(
                    "lparstat -i (pre-reboot) shows unexpected name '%s' "
                    "(expected '%s' or '%s')"
                    % (name_os_before, self.original_name, self.new_name))
            log.info("Step 4 PASS: pre-reboot lparstat Partition Name = '%s'",
                     name_os_before)

            self._reboot_and_wait()
            name_os_after = self._os_get_lpar_name()
            self.assertEqual(
                name_os_after, self.new_name,
                "lparstat -i (post-reboot) shows '%s' but expected new name '%s'"
                % (name_os_after, self.new_name))
            log.info("Step 6 PASS: post-reboot lparstat Partition Name = '%s'",
                     name_os_after)

        finally:
            # Steps 7-11 always run so the environment is cleaned up and
            # fully verified regardless of whether steps 1-6 passed or failed.
            restore_errors = []
            if self.cv_HMC.lpar_name != self.original_name:
                try:
                    self._hmc_rename_lpar(
                        self.cv_HMC.lpar_name, self.original_name)
                except Exception as exc:
                    restore_errors.append("Step 7 FAIL: rename restore: %s" % exc)
                    log.error(restore_errors[-1])
            try:
                name_restored_hmc = self._hmc_get_lpar_name()
                if name_restored_hmc == self.original_name:
                    log.info("Step 8 PASS: HMC confirms name restored to '%s'",
                             name_restored_hmc)
                else:
                    msg = ("Step 8 FAIL: HMC shows '%s' after restore "
                           "(expected '%s')" % (name_restored_hmc,
                                                self.original_name))
                    restore_errors.append(msg)
                    log.error(msg)
            except Exception as exc:
                restore_errors.append("Step 8 FAIL: lssyscfg after restore: %s" % exc)
                log.error(restore_errors[-1])
            try:
                name_os_restore = self._os_get_lpar_name()
                if name_os_restore not in (self.original_name, self.new_name):
                    msg = ("Step 9 FAIL: lparstat -i shows unexpected name '%s' "
                           "(expected '%s' or '%s')"
                           % (name_os_restore, self.original_name, self.new_name))
                    restore_errors.append(msg)
                    log.error(msg)
                else:
                    log.info("Step 9 PASS: post-restore lparstat Partition Name = '%s'",
                             name_os_restore)
            except Exception as exc:
                restore_errors.append("Step 9 FAIL: lparstat -i post-restore: %s" % exc)
                log.error(restore_errors[-1])
            try:
                self._reboot_and_wait()
            except Exception as exc:
                restore_errors.append("Step 10 FAIL: reboot after restore: %s" % exc)
                log.error(restore_errors[-1])
            try:
                name_os_final = self._os_get_lpar_name()
                if name_os_final == self.original_name:
                    log.info("Step 11 PASS: lparstat Partition Name = '%s'",
                             name_os_final)
                else:
                    msg = ("Step 11 FAIL: lparstat -i shows '%s' after restore "
                           "reboot (expected original name '%s')"
                           % (name_os_final, self.original_name))
                    restore_errors.append(msg)
                    log.error(msg)
            except Exception as exc:
                restore_errors.append("Step 11 FAIL: lparstat -i post-restore reboot: %s" % exc)
                log.error(restore_errors[-1])

            if restore_errors:
                raise AssertionError(
                    "Restore/cleanup phase had %d error(s):\n%s"
                    % (len(restore_errors), "\n".join(restore_errors)))
