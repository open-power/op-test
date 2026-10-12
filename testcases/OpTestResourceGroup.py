#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestResourceGroup.py $
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
OpTestResourceGroup
--------------------
Tests for HMC Resource Group (Physical Processor Pool) feature on IBM Power11.

Background
~~~~~~~~~~
Resource Groups (Physical Processor Pools) are a Power11 feature providing
workload isolation across shared and dedicated partitions. A resource group
is a pool of cores isolated from other resource groups in the system.

Key HMC commands
~~~~~~~~~~~~~~~~
Create RG:
    chhwres -r resgroup -m <sys> -o a -g <name> --gid <id>
            -a "procs=<n>,affinity_priority=<p>"

Assign LPAR to existing RG (LPAR must be Not Activated):
    chhwres -r resgroup -m <sys> -o s -p <lpar>
            -a "resource_group_name=<rg>"

Modify RG attributes:
    chhwres -r resgroup -m <sys> -o s -g <name> -a "affinity_priority=<p>"

Delete RG (must be empty):
    chhwres -r resgroup -m <sys> -o r -g <name>

List RGs with available procs:
    lshwres -r resgroup -m <sys> -F name:curr_avail_procs
    Example output:
        Default Resource Group:35.0
        RG2:3.0

Pre-requisites
~~~~~~~~~~~~~~
machine.conf must contain:

    [op-test]
    bmc_type             = FSP_PHYP
    hmc_ip               = <hmc-ip>
    hmc_username         = hscpe
    hmc_password         = <hscpe-password>
    system_name          = <managed-system>   # Power11 required
    lpar_name            = <lpar-name>
    rg_name              = RG2
    rg_gid               = 2
    rg_procs             = 4
    rg_affinity_priority = 128
    rg_su_password       = <su-password>

Test plan
~~~~~~~~~
1.  test_1_check_rg_capability         – Verify system supports RGs + clean slate.
2.  test_2_create_resource_group       – Create RG using available procs dynamically.
3.  test_3_verify_rg_listed            – Confirm RG in lshwres with empty lpar_names.
4.  test_4_shutdown_lpar               – Shut LPAR down (required before assign).
5.  test_5_assign_lpar_to_rg           – Assign LPAR to RG via -o s.
6.  test_6_verify_lpar_in_rg           – Confirm LPAR in RG2 lpar_names.
7.  test_7_poweron_lpar                – Power LPAR back on.
8.  test_8_verify_rg_persists_after_boot – RG assignment survives reboot.
9.  test_9_modify_rg_affinity          – Modify affinity_priority dynamically.
10. test_10_verify_modified_affinity   – Confirm new affinity in lshwres.
11. test_11_delete_rg_with_lpar_fails  – Delete with LPAR assigned must fail HSCLCA07.
12. test_12_move_lpar_back_to_default  – Move LPAR back to Default RG.
13. test_13_delete_empty_rg            – Delete empty RG (must succeed).
14. test_14_verify_rg_deleted          – Confirm RG no longer listed.
'''

import math
import time
import unittest
import pexpect
import OpTestConfiguration
import OpTestLogger
from common.OpTestHMC import OpHmcState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

SETTLE_TIME = 10
HMC_ROOT_PROMPT = r'\[root@\S+ \S+\] #'
DEFAULT_RG = "Default Resource Group"
# New affinity used in test_9 (different from configured value)
MODIFIED_AFFINITY = "200"


class OpTestResourceGroup(unittest.TestCase):
    '''
    Resource Group (Physical Processor Pool) feature test suite for Power11.
    '''

    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HMC = cls.cv_SYSTEM.hmc
        cls.hmc_ip = conf.args.hmc_ip
        cls.hmc_user = conf.args.hmc_username
        cls.hmc_password = conf.args.hmc_password
        cls.system_name = conf.args.system_name
        cls.lpar_name = conf.args.lpar_name
        try:
            cls.rg_name = conf.args.rg_name
        except AttributeError:
            cls.rg_name = "RG2"
        try:
            cls.rg_gid = conf.args.rg_gid
        except AttributeError:
            cls.rg_gid = "2"
        try:
            cls.rg_procs = int(conf.args.rg_procs)
        except AttributeError:
            cls.rg_procs = 4
        try:
            cls.rg_affinity_priority = conf.args.rg_affinity_priority
        except AttributeError:
            cls.rg_affinity_priority = "128"
        try:
            cls.rg_su_password = conf.args.rg_su_password
        except AttributeError:
            raise AttributeError(
                "rg_su_password is required in machine.conf "
                "(HMC root su password). Add: rg_su_password = <su-password>")
        # Runtime state flags used by teardown
        cls._rg_created = False
        cls._lpar_assigned = False
        # Actual procs used at creation time (set in test_2, used in teardown)
        cls._actual_procs = None
        log.info("OpTestResourceGroup: system=%s lpar=%s rg=%s gid=%s "
                 "requested_procs=%s affinity=%s",
                 cls.system_name, cls.lpar_name, cls.rg_name,
                 cls.rg_gid, cls.rg_procs, cls.rg_affinity_priority)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_as_root(self, cmd, su_password=None, timeout=60):
        '''
        SSH into HMC as hscpe, escalate to root via su, run cmd, return output.
        '''
        su_password = su_password or self.rg_su_password
        ssh_cmd = (
            "sshpass -p {pw} ssh -o StrictHostKeyChecking=no"
            " -o UserKnownHostsFile=/dev/null -q {user}@{host}".format(
                pw=self.hmc_password, user=self.hmc_user, host=self.hmc_ip))
        log.info("_run_as_root: %s", cmd)
        child = pexpect.spawn(ssh_cmd, encoding='utf-8', timeout=timeout)
        child.logfile_read = None
        child.expect(r'\$\s*$', timeout=30)
        child.sendline('su')
        child.expect(r'[Pp]assword:', timeout=10)
        child.sendline(su_password)
        child.expect(HMC_ROOT_PROMPT, timeout=15)
        child.sendline(cmd)
        child.expect(HMC_ROOT_PROMPT, timeout=timeout)
        output = child.before.strip()
        log.info("_run_as_root output: %s", output)
        child.sendline('exit')
        child.sendline('exit')
        child.close()
        return output

    def _rg_exists(self):
        '''Return True if self.rg_name exists on the managed system.'''
        try:
            out = self._run_as_root(
                "lshwres -r resgroup -m %s -F name" % self.system_name)
            return self.rg_name in out
        except Exception:
            return False

    def _lpar_current_rg(self):
        '''
        Return the non-default RG name the LPAR belongs to, or "" if
        LPAR is in the Default Resource Group.
        '''
        try:
            out = self._run_as_root(
                "lshwres -r resgroup -m %s -F name:lpar_names"
                % self.system_name)
            for line in out.splitlines():
                if self.lpar_name in line:
                    rg = line.split(':')[0].strip()
                    if rg != DEFAULT_RG:
                        return rg
            return ""
        except Exception:
            return ""

    def _get_available_procs(self, rg_name=DEFAULT_RG):
        '''
        Query curr_avail_procs for *rg_name* from HMC and return as int.

        lshwres -r resgroup -m <sys> -F name:curr_avail_procs returns lines:
            Default Resource Group:35.0
            RG2:3.0

        Returns 0 if the RG is not found or on any error.
        '''
        try:
            out = self._run_as_root(
                "lshwres -r resgroup -m %s -F name:curr_avail_procs"
                % self.system_name)
            for line in out.splitlines():
                if line.startswith(rg_name + ':'):
                    val = line.split(':', 1)[1].strip()
                    return int(math.floor(float(val)))
        except Exception as e:
            log.warning("_get_available_procs error: %s", e)
        return 0

    def _get_rg_attribute(self, attr):
        '''Return value of a single attribute from lshwres for self.rg_name.'''
        try:
            out = self._run_as_root(
                "lshwres -r resgroup -m %s -F name:%s" % (self.system_name, attr))
            for line in out.splitlines():
                if line.startswith(self.rg_name + ':'):
                    return line.split(':', 1)[1].strip()
        except Exception:
            pass
        return ""

    def _wait_lpar_state(self, expected, timeout=300):
        '''Poll LPAR state until it matches *expected* or timeout expires.'''
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.cv_HMC.get_lpar_state()
            log.info("LPAR state: %s  (waiting for: %s)", state, expected)
            if state == expected:
                return
            time.sleep(SETTLE_TIME)
        self.fail("Timed out waiting for LPAR state '%s'; last state: %s"
                  % (expected, self.cv_HMC.get_lpar_state()))

    # ------------------------------------------------------------------
    # Test 1 – Capability check + clean slate
    # ------------------------------------------------------------------

    def test_01_check_rg_capability(self):
        '''
        Verify the managed system supports Resource Groups (Power11+).
        lshwres -r resgroup fails with HSCLCA00 on unsupported systems.
        Also removes any leftover RG from a previous partial run.
        '''
        out = self._run_as_root(
            "lshwres -r resgroup -m %s -F name" % self.system_name)
        if 'HSCLCA00' in out:
            raise unittest.SkipTest(
                "System '%s' does not support resource groups (HSCLCA00)"
                % self.system_name)

        if self._rg_exists():
            log.info("Leftover RG '%s' found – removing before test run.",
                     self.rg_name)
            if self._lpar_current_rg() == self.rg_name:
                self._run_as_root(
                    "chhwres -r resgroup -m %s -o s -p %s"
                    " -a \"resource_group_name=%s\""
                    % (self.system_name, self.lpar_name, DEFAULT_RG))
            self._run_as_root(
                "chhwres -r resgroup -m %s -o r -g %s"
                % (self.system_name, self.rg_name))
            self.assertFalse(self._rg_exists(),
                             "Failed to remove leftover RG '%s'" % self.rg_name)

        log.info("System '%s' supports resource groups – ready.", self.system_name)

    # ------------------------------------------------------------------
    # Test 2 – Create RG using dynamically determined proc count
    # ------------------------------------------------------------------

    def test_02_create_resource_group(self):
        '''
        Create a new Resource Group.

        The procs value is determined dynamically at runtime:
          - Query curr_avail_procs from the Default Resource Group
          - Use min(configured_rg_procs, available_procs)
          - Skip if available_procs < 1 (system has no free processors)

        This prevents failures on systems with fewer available processors
        than the configured rg_procs value.

        lshwres -r resgroup -m <sys> -F name:curr_avail_procs
        Example output:
            Default Resource Group:35.0   → available = 35
            RG2:3.0
        '''
        available = self._get_available_procs(DEFAULT_RG)
        log.info("Default RG curr_avail_procs = %d  (requested rg_procs = %d)",
                 available, self.rg_procs)

        if available < 1:
            raise unittest.SkipTest(
                "No available processors in Default Resource Group "
                "(curr_avail_procs=%d) – cannot create RG." % available)

        # Use the lesser of what was configured and what is available
        procs = min(self.rg_procs, available)
        log.info("Using procs=%d for RG creation.", procs)

        cmd = ("chhwres -r resgroup -m %s -o a -g %s --gid %s"
               " -a \"procs=%d,affinity_priority=%s\""
               % (self.system_name, self.rg_name, self.rg_gid,
                  procs, self.rg_affinity_priority))
        log.info("Creating resource group: %s", cmd)
        out = self._run_as_root(cmd)
        if out and any(e in out for e in ('HSCL', 'error', 'Error', 'invalid')):
            self.fail("RG creation failed: %s" % out)

        self.assertTrue(self._rg_exists(),
                        "RG '%s' not found after creation." % self.rg_name)
        self.__class__._rg_created = True
        self.__class__._actual_procs = procs
        log.info("Resource group '%s' created with procs=%d.", self.rg_name, procs)

    # ------------------------------------------------------------------
    # Test 3 – Verify RG listed with empty lpar_names
    # ------------------------------------------------------------------

    def test_03_verify_rg_listed(self):
        '''
        Confirm RG2 appears in lshwres -r resgroup output and has no
        LPARs assigned yet (lpar_names should be empty).
        '''
        out = self._run_as_root(
            "lshwres -r resgroup -m %s -F name:lpar_names" % self.system_name)
        self.assertIn(self.rg_name, out,
                      "RG '%s' not found in lshwres output." % self.rg_name)
        for line in out.splitlines():
            if line.startswith(self.rg_name + ':'):
                lpar_part = line.split(':', 1)[1].strip()
                self.assertEqual(
                    lpar_part, "",
                    "RG '%s' should have no LPARs yet, got: '%s'"
                    % (self.rg_name, lpar_part))
                break
        log.info("RG '%s' listed correctly with no LPARs assigned.", self.rg_name)

    # ------------------------------------------------------------------
    # Test 4 – Shutdown LPAR
    # ------------------------------------------------------------------

    def test_04_shutdown_lpar(self):
        '''
        Shut the LPAR down. LPAR must be in Not Activated state before it
        can be moved to a different resource group.
        '''
        state = self.cv_HMC.get_lpar_state()
        log.info("LPAR '%s' current state: %s", self.lpar_name, state)
        if state == OpHmcState.NOT_ACTIVE:
            log.info("LPAR already powered off – no shutdown needed.")
            return
        try:
            self.cv_HMC.poweroff_lpar()
        except CommandFailed as cf:
            self.fail("poweroff_lpar failed: %s" % cf.output)
        self._wait_lpar_state(OpHmcState.NOT_ACTIVE)
        log.info("LPAR '%s' is now Not Activated.", self.lpar_name)

    # ------------------------------------------------------------------
    # Test 5 – Assign LPAR to RG
    # ------------------------------------------------------------------

    def test_05_assign_lpar_to_rg(self):
        '''
        Assign the LPAR to RG2 via:
            chhwres -r resgroup -m <sys> -o s -p <lpar>
                    -a "resource_group_name=<rg>"
        LPAR must be Not Activated (enforced by test_4).
        '''
        state = self.cv_HMC.get_lpar_state()
        if state != OpHmcState.NOT_ACTIVE:
            self.fail("LPAR must be Not Activated before RG assignment, "
                      "current state: %s" % state)
        cmd = ("chhwres -r resgroup -m %s -o s -p %s"
               " -a \"resource_group_name=%s\""
               % (self.system_name, self.lpar_name, self.rg_name))
        out = self._run_as_root(cmd)
        if out and any(e in out for e in ('HSCL', 'error', 'Error', 'invalid')):
            self.fail("LPAR RG assignment failed: %s" % out)
        self.__class__._lpar_assigned = True
        log.info("LPAR '%s' assigned to '%s'.", self.lpar_name, self.rg_name)

    # ------------------------------------------------------------------
    # Test 6 – Verify LPAR appears in RG lpar_names
    # ------------------------------------------------------------------

    def test_06_verify_lpar_in_rg(self):
        '''
        Confirm lshwres -r resgroup shows the LPAR under RG2:lpar_names.
        '''
        current_rg = self._lpar_current_rg()
        self.assertEqual(
            current_rg, self.rg_name,
            "LPAR '%s' not found in RG '%s'. Current RG: '%s'"
            % (self.lpar_name, self.rg_name, current_rg))
        log.info("Verified: LPAR '%s' is in RG '%s'.",
                 self.lpar_name, self.rg_name)

    # ------------------------------------------------------------------
    # Test 7 – Power LPAR back on
    # ------------------------------------------------------------------

    def test_07_poweron_lpar(self):
        '''
        Power the LPAR on after RG assignment and wait for Running state.
        '''
        try:
            self.cv_HMC.poweron_lpar()
        except CommandFailed as cf:
            self.fail("poweron_lpar failed: %s" % cf.output)
        self._wait_lpar_state(OpHmcState.RUNNING)
        log.info("LPAR '%s' is Running.", self.lpar_name)

    # ------------------------------------------------------------------
    # Test 8 – Verify RG assignment persists after boot
    # ------------------------------------------------------------------

    def test_08_verify_rg_persists_after_boot(self):
        '''
        Confirm the LPAR is still in RG2 after it has fully booted.
        Validates that RG assignment is persistent across power cycles.
        '''
        current_rg = self._lpar_current_rg()
        self.assertEqual(
            current_rg, self.rg_name,
            "RG assignment lost after boot: expected '%s', got '%s'"
            % (self.rg_name, current_rg))
        log.info("RG assignment persists after boot.")

    # ------------------------------------------------------------------
    # Test 9 – Modify RG affinity_priority dynamically
    # ------------------------------------------------------------------

    def test_09_modify_rg_affinity(self):
        '''
        Modify the affinity_priority of RG2 while LPARs are running:
            chhwres -r resgroup -m <sys> -o s -g <rg>
                    -a "affinity_priority=<new>"

        Uses a value different from the configured rg_affinity_priority
        to confirm the change takes effect. RG attribute changes do not
        require the LPAR to be shut down.
        '''
        # Pick a value different from what was configured
        new_affinity = MODIFIED_AFFINITY
        if new_affinity == self.rg_affinity_priority:
            new_affinity = "64"
        cmd = ("chhwres -r resgroup -m %s -o s -g %s"
               " -a \"affinity_priority=%s\""
               % (self.system_name, self.rg_name, new_affinity))
        out = self._run_as_root(cmd)
        if out and any(e in out for e in ('HSCL', 'error', 'Error', 'invalid')):
            self.fail("RG affinity modify failed: %s" % out)
        self.__class__._modified_affinity = new_affinity
        log.info("RG '%s' affinity_priority changed to %s.",
                 self.rg_name, new_affinity)

    # ------------------------------------------------------------------
    # Test 10 – Verify modified affinity reflected in lshwres
    # ------------------------------------------------------------------

    def test_10_verify_modified_affinity(self):
        '''
        Confirm lshwres reflects the updated affinity_priority value.
        '''
        expected = getattr(self.__class__, '_modified_affinity', MODIFIED_AFFINITY)
        val = self._get_rg_attribute("affinity_priority")
        self.assertEqual(
            val, expected,
            "affinity_priority mismatch: expected '%s', got '%s'"
            % (expected, val))
        log.info("Verified: RG '%s' affinity_priority = %s.", self.rg_name, val)

    # ------------------------------------------------------------------
    # Test 11 – Delete RG with LPAR assigned must fail (HSCLCA07)
    # ------------------------------------------------------------------

    def test_11_delete_rg_with_lpar_fails(self):
        '''
        Attempt to delete RG2 while the LPAR is still assigned to it.
        Must fail with HSCLCA07:
            "The resource group cannot be deleted because the following
             partitions are assigned to it: [<lpar>]"
        This validates the guard against accidental RG deletion.
        '''
        out = self._run_as_root(
            "chhwres -r resgroup -m %s -o r -g %s"
            % (self.system_name, self.rg_name))
        self.assertIn(
            'HSCLCA07', out,
            "Expected HSCLCA07 when deleting RG with assigned LPAR, got: '%s'"
            % out)
        self.assertTrue(self._rg_exists(),
                        "RG '%s' was incorrectly deleted." % self.rg_name)
        log.info("Confirmed: delete with assigned LPAR correctly rejected (HSCLCA07).")

    # ------------------------------------------------------------------
    # Test 12 – Move LPAR back to Default Resource Group
    # ------------------------------------------------------------------

    def test_12_move_lpar_back_to_default(self):
        '''
        Shut LPAR down and move it back to the Default Resource Group:
            chhwres -r resgroup -m <sys> -o s -p <lpar>
                    -a "resource_group_name=Default Resource Group"
        LPAR must be Not Activated for the move.
        '''
        state = self.cv_HMC.get_lpar_state()
        if state != OpHmcState.NOT_ACTIVE:
            log.info("Shutting LPAR down before move back to Default RG ...")
            try:
                self.cv_HMC.poweroff_lpar()
            except CommandFailed as cf:
                self.fail("poweroff_lpar failed: %s" % cf.output)
            self._wait_lpar_state(OpHmcState.NOT_ACTIVE)

        cmd = ("chhwres -r resgroup -m %s -o s -p %s"
               " -a \"resource_group_name=%s\""
               % (self.system_name, self.lpar_name, DEFAULT_RG))
        out = self._run_as_root(cmd)
        if out and any(e in out for e in ('HSCL', 'error', 'Error', 'invalid')):
            self.fail("Move LPAR to Default RG failed: %s" % out)
        self.__class__._lpar_assigned = False

        self.assertEqual(
            self._lpar_current_rg(), "",
            "LPAR '%s' still in non-default RG after move back."
            % self.lpar_name)
        log.info("LPAR '%s' moved back to Default Resource Group.", self.lpar_name)

    # ------------------------------------------------------------------
    # Test 13 – Delete empty RG
    # ------------------------------------------------------------------

    def test_13_delete_empty_rg(self):
        '''
        Delete RG2 now that it has no LPARs assigned.
        Empty output = success on HMC commands.
        '''
        out = self._run_as_root(
            "chhwres -r resgroup -m %s -o r -g %s"
            % (self.system_name, self.rg_name))
        if out and any(e in out for e in ('HSCL', 'error', 'Error', 'invalid')):
            self.fail("RG delete failed: %s" % out)
        self.__class__._rg_created = False
        log.info("Resource group '%s' deleted successfully.", self.rg_name)

    # ------------------------------------------------------------------
    # Test 14 – Verify RG no longer listed
    # ------------------------------------------------------------------

    def test_14_verify_rg_deleted(self):
        '''
        Confirm RG2 no longer appears in lshwres output after deletion.
        '''
        self.assertFalse(
            self._rg_exists(),
            "RG '%s' still listed after deletion." % self.rg_name)
        log.info("Verified: RG '%s' is gone.", self.rg_name)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @classmethod
    def tearDownClass(cls):
        '''
        Best-effort cleanup:
        - Move LPAR back to Default RG if still assigned to test RG
        - Delete RG if it still exists
        - Power LPAR back on
        '''
        if not cls._rg_created and not cls._lpar_assigned:
            log.info("tearDownClass: nothing to clean up.")
            try:
                state = cls.cv_HMC.get_lpar_state()
                if state == OpHmcState.NOT_ACTIVE:
                    cls.cv_HMC.poweron_lpar()
            except Exception:
                pass
            return

        log.info("tearDownClass: cleaning up RG '%s' ...", cls.rg_name)
        try:
            # Shut down if running
            state = cls.cv_HMC.get_lpar_state()
            if state != OpHmcState.NOT_ACTIVE:
                cls.cv_HMC.poweroff_lpar()
                time.sleep(SETTLE_TIME * 3)

            # Move LPAR back to Default RG if still in test RG
            rg_out = cls._run_as_root(
                cls,
                "lshwres -r resgroup -m %s -F name:lpar_names" % cls.system_name,
                su_password=cls.rg_su_password)
            if any(line.startswith(cls.rg_name + ':') and cls.lpar_name in line
                   for line in rg_out.splitlines()):
                cls._run_as_root(
                    cls,
                    "chhwres -r resgroup -m %s -o s -p %s"
                    " -a \"resource_group_name=%s\""
                    % (cls.system_name, cls.lpar_name, DEFAULT_RG),
                    su_password=cls.rg_su_password)

            # Delete RG if it still exists
            rg_names = cls._run_as_root(
                cls,
                "lshwres -r resgroup -m %s -F name" % cls.system_name,
                su_password=cls.rg_su_password)
            if cls.rg_name in rg_names:
                cls._run_as_root(
                    cls,
                    "chhwres -r resgroup -m %s -o r -g %s"
                    % (cls.system_name, cls.rg_name),
                    su_password=cls.rg_su_password)

            cls.cv_HMC.poweron_lpar()
            log.info("tearDownClass: cleanup complete.")
        except Exception as exc:
            log.warning("tearDownClass error: %s", exc)


# ---------------------------------------------------------------------------
# Suite helper
# ---------------------------------------------------------------------------

def suite():
    tests = [
        'test_01_check_rg_capability',
        'test_02_create_resource_group',
        'test_03_verify_rg_listed',
        'test_04_shutdown_lpar',
        'test_05_assign_lpar_to_rg',
        'test_06_verify_lpar_in_rg',
        'test_07_poweron_lpar',
        'test_08_verify_rg_persists_after_boot',
        'test_09_modify_rg_affinity',
        'test_10_verify_modified_affinity',
        'test_11_delete_rg_with_lpar_fails',
        'test_12_move_lpar_back_to_default',
        'test_13_delete_empty_rg',
        'test_14_verify_rg_deleted',
    ]
    return unittest.TestSuite(list(map(OpTestResourceGroup, tests)))
