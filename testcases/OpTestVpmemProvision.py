#!/usr/bin/env python3
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

'''
OpTestVpmemProvision
--------------------

Validates the end-to-end vpmem provisioning and removal flow via HMC.

test_01_provision_vpmem_and_activate
    Pre-check A: If a vpmem volume is already configured on the LPAR,
                 skip the provisioning steps and go straight to activation.
    Pre-check B: If no volume is configured, verify the system has enough
                 free memory to back the requested vpmem size. SkipTest
                 if memory is insufficient.
    Provisioning (only when Pre-check A finds no volume):
        1. Shutdown the LPAR
        2. Verify vpmem_size is LMB-aligned
        3. Remove any stale vpmem volumes
        4. Create vpmem volume via HMC (default 8 GB, affinity=0)
        5. Confirm HMC reports volume count >= 1
    Common (always executed):
        6. Clear dmesg and activate LPAR to OS
        7. Verify kernel enumerates >= 1 NVDIMM region (ndctl list -R)
        8. Verify dmesg contains no errors (util.collect_errors_by_level)

test_02_remove_vpmem_and_validate
    1. Shutdown the LPAR; confirm NOT_ACTIVE state
    2. Remove all vpmem volumes via HMC
    3. Confirm HMC reports volume count == 0
    4. Set boot_mode=norm on profile to prevent firmware SMS menu
    5. Wait 30s for PHYP to settle the hardware config change
    6. Confirm LPAR is still NOT_ACTIVE before activation
    7. Clear dmesg and activate LPAR to OS
    8. Verify ndctl reports zero NVDIMM regions
    9. Verify dmesg contains no errors

tearDownClass
    Leaves the LPAR powered OFF (poweroff_lpar).

Configuration Parameters (optional):
-------------------------------------
--vpmem-size  <MB>  : vpmem volume size in MB (default: 8192 = 8 GB).
                      Must be a multiple of the system LMB size.
                      Set in the op-test config file or on the command line.
--vpmem-name  <str> : Volume name to use (default: vpmem_vol0).
                      Set in the op-test config file or on the command line.

Usage Examples:
---------------
# Run both tests in order (provision then remove):
./op-test --run testcases.OpTestVpmemProvision.VpmemProvisionTest

# Run provisioning test only:
./op-test --run \
    testcases.OpTestVpmemProvision.VpmemProvisionTest.test_01_provision_vpmem_and_activate

# Run removal test only:
./op-test --run testcases.OpTestVpmemProvision.VpmemProvisionTest.test_02_remove_vpmem_and_validate

# Run with a custom size and volume name:
./op-test --run testcases.OpTestVpmemProvision.VpmemProvisionTest \
    --vpmem-size 20480 \
    --vpmem-name my_pmem_vol
'''

import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Known-noisy dmesg messages unrelated to vpmem that are safe to skip.
# These are pre-existing environmental conditions on IBM Power LPARs:
#   - nvme probe ENOMEM: NVMe PCIe devices compete for DMA memory at boot
#     when the LPAR has limited memory; unrelated to vpmem configuration.
#   - platform_keystore: GRUB/firmware PKS not present warning; harmless.
#   - LPAR Platform KeyStore is not supported: same PKS noise from kernel.
_DMESG_SKIP_ERRORS = [
    'probe with driver nvme failed with error -12',
    'platform_keystore',
    'LPAR Platform KeyStore is not supported',
]


class VpmemProvisionTest(unittest.TestCase):
    '''
    Provision and removal test for vpmem on an HMC-managed LPAR (FSP_PHYP
    or EBMC_PHYP). Validates the full lifecycle:
      test_01 — provision vpmem, activate, verify kernel sees the device.
      test_02 — remove vpmem, activate, verify kernel no longer sees the device.
    '''

    @classmethod
    def setUpClass(cls):
        '''
        Bind op-test configuration objects and validate that the target is
        an HMC-managed LPAR.  Skip the entire class for non-LPAR targets.
        '''
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.cv_HMC = cls.cv_SYSTEM.hmc
        cls.util = OpTestUtil(conf)
        cls.bmc_type = conf.args.bmc_type

        if cls.bmc_type not in ['FSP_PHYP', 'EBMC_PHYP']:
            raise unittest.SkipTest(
                'VpmemProvisionTest requires an HMC-managed LPAR '
                '(FSP_PHYP or EBMC_PHYP). Detected bmc_type: {}'.format(
                    cls.bmc_type
                )
            )

        cls.lpar_name = conf.args.lpar_name
        cls.system_name = conf.args.system_name
        cls.lpar_prof = conf.args.lpar_prof

        # --vpmem-size and --vpmem-name are registered in OpTestConfiguration
        # with defaults of 8192 MB and vpmem_vol0 respectively.
        # Users can override them in the op-test config file or on the
        # command line, e.g.:
        #   --vpmem-size 20480  (20 GB)
        #   --vpmem-name my_pmem_vol
        cls.vpmem_size = str(conf.args.vpmem_size)
        cls.vpmem_name = str(conf.args.vpmem_name)

    # ------------------------------------------------------------------
    # Private helpers — thin wrappers; each adds exactly one decision
    # on top of an existing API call.
    # ------------------------------------------------------------------

    def _get_vpmem_count(self):
        '''
        Return the number of vpmem volumes configured on the LPAR as an int.

        Wraps cv_HMC.vpmem_count() to handle the raw list return and
        null-output edge case in one place.

        :returns: int — number of configured vpmem volumes
        '''
        output = self.cv_HMC.vpmem_count()
        if not output:
            return 0
        return int(output[0].strip())

    def _check_free_memory(self):
        '''
        Guard: verify the system has enough free memory to back vpmem_size.

        Calls cv_HMC.get_available_mem_resources() which returns
        curr_avail_sys_mem (MB) for the managed system. Raises SkipTest
        when available memory is less than vpmem_size — this is an
        environment condition, not a product defect.

        :raises unittest.SkipTest: when available memory < vpmem_size
        :raises unittest.SkipTest: when HMC returns no data
        '''
        output = self.cv_HMC.get_available_mem_resources()
        if not output:
            raise unittest.SkipTest(
                'Could not retrieve available system memory from HMC. '
                'Cannot determine whether vpmem provisioning is feasible.'
            )
        avail_mb = int(output[0].strip())
        required_mb = int(self.vpmem_size)
        log.info(
            'Free memory check: available=%d MB, required=%d MB',
            avail_mb, required_mb
        )
        if avail_mb < required_mb:
            raise unittest.SkipTest(
                'Insufficient free system memory to provision vpmem: '
                'available={} MB, required={} MB. '
                'Free up memory on the CEC before running this test.'.format(
                    avail_mb, required_mb
                )
            )
        log.info('Free memory check passed')

    def _lmb_alignment_check(self):
        '''
        Guard: verify that vpmem_size is a multiple of the system LMB size.

        Calls cv_HMC.get_lmb_size() which returns the memory region size
        in MB. vpmem volumes must be LMB-aligned or HMC will reject the
        configure_vpmem call.

        :raises unittest.SkipTest: when HMC returns no LMB data
        :raises AssertionError (self.fail): when vpmem_size is misaligned
        '''
        output = self.cv_HMC.get_lmb_size()
        if not output:
            raise unittest.SkipTest(
                'Could not retrieve LMB size from HMC. '
                'Cannot verify vpmem size alignment.'
            )
        lmb_mb = int(output[0].strip())
        log.info('System LMB size: %d MB', lmb_mb)
        if int(self.vpmem_size) % lmb_mb != 0:
            self.fail(
                'vpmem_size {} MB is not a multiple of the system LMB size '
                '{} MB. Adjust --vpmem-size to an LMB-aligned value.'.format(
                    self.vpmem_size, lmb_mb
                )
            )
        log.info('LMB alignment check passed')

    def _ensure_ndctl(self):
        '''
        Ensure ndctl is installed on the OS.

        Uses util.install_package() which handles distro detection (RHEL/SLES)
        and the appropriate package manager internally.  A direct "which ndctl"
        check is done first via the host SSH connection to avoid unnecessary
        package manager invocations.

        :raises AssertionError (self.fail): if install fails
        '''
        try:
            self.cv_HOST.host_run_command('which ndctl', timeout=30)
            log.info('ndctl is already installed')
            return
        except Exception:
            log.info('ndctl not found — installing via util.install_package()')

        self.util.install_package(['ndctl'])

        # Confirm the binary is now available.
        try:
            self.cv_HOST.host_run_command('which ndctl', timeout=30)
            log.info('ndctl installation verified')
        except Exception:
            self.fail(
                'ndctl binary not found after installation attempt. '
                'Install ndctl manually before running this test.'
            )

    def _activate_and_get_console(self):
        '''
        Clear dmesg, activate the LPAR to OS, and return the console.

        Clears the dmesg ring buffer before activation so that
        util.collect_errors_by_level() only sees messages from this
        boot cycle when called after activation.

        :returns: console object from cv_SYSTEM.console
        '''
        log.info('Clearing dmesg before activation...')
        try:
            self.util.clear_dmesg()
        except Exception:
            log.warning('clear_dmesg() failed — dmesg may contain pre-existing messages')

        log.info('Activating LPAR to OS...')
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        console = self.cv_SYSTEM.console
        uname = console.run_command('uname -a', timeout=60)
        log.info('Kernel: %s', uname[0].strip() if uname else 'unknown')
        return console

    # ------------------------------------------------------------------
    # Test 1 — Provision vpmem and activate
    # ------------------------------------------------------------------

    def test_01_provision_vpmem_and_activate(self):
        '''
        Provision a vpmem volume and verify the LPAR boots with the device
        visible to the kernel.

        Pre-check A — vpmem already configured?
            YES: Skip provisioning steps, go directly to activation.
            NO:  Run Pre-check B.

        Pre-check B — enough free system memory?
            NO:  SkipTest (environment not ready, not a product failure).
            YES: Proceed with provisioning.

        Provisioning flow (when Pre-check A finds no volume):
            Step 1 — Shutdown the LPAR
            Step 2 — LMB alignment check
            Step 3 — Remove any stale vpmem volumes
            Step 4 — Create vpmem volume via HMC
            Step 5 — Confirm vpmem volume count >= 1

        Common flow (always executed):
            Step 6 — Clear dmesg and activate LPAR to OS
            Step 7 — Verify ndctl reports >= 1 NVDIMM region
            Step 8 — Verify dmesg is clean (no errors at level emerg-err)
        '''
        log.info('=' * 70)
        log.info('test_01_provision_vpmem_and_activate')
        log.info('  LPAR       : %s', self.lpar_name)
        log.info('  System     : %s', self.system_name)
        log.info('  vpmem name : %s', self.vpmem_name)
        log.info('  vpmem size : %s MB', self.vpmem_size)
        log.info('=' * 70)

        # ------------------------------------------------------------------
        # Pre-check A: Is vpmem already configured?
        # ------------------------------------------------------------------
        log.info('[Pre-check A] Querying existing vpmem configuration...')
        existing_count = self._get_vpmem_count()

        if existing_count >= 1:
            log.info(
                '  vpmem already configured (%d volume(s) found). '
                'Skipping provisioning steps — proceeding to activation.',
                existing_count
            )
        else:
            log.info('  No vpmem volumes found. Checking system resources...')

            # ------------------------------------------------------------------
            # Pre-check B: Is there enough free memory?
            # ------------------------------------------------------------------
            log.info('[Pre-check B] Checking available system memory...')
            self._check_free_memory()

            # ------------------------------------------------------------------
            # Step 1 — Shutdown the LPAR
            # ------------------------------------------------------------------
            log.info('[Step 1] Shutting down the LPAR...')
            self.cv_HMC.poweroff_lpar()
            time.sleep(10)
            log.info('  LPAR is powered off')

            # ------------------------------------------------------------------
            # Step 2 — LMB alignment check
            # ------------------------------------------------------------------
            log.info('[Step 2] Verifying vpmem size is LMB-aligned...')
            self._lmb_alignment_check()

            # ------------------------------------------------------------------
            # Step 3 — Remove stale vpmem volumes (defensive)
            # ------------------------------------------------------------------
            log.info('[Step 3] Checking for stale vpmem volumes...')
            stale_count = self._get_vpmem_count()
            if stale_count > 0:
                log.info('  Found %d stale volume(s) — removing...', stale_count)
                self.cv_HMC.remove_vpmem()
                log.info('  Stale volumes removed')
            else:
                log.info('  No stale volumes present')

            # ------------------------------------------------------------------
            # Step 4 — Create the vpmem volume
            # ------------------------------------------------------------------
            log.info(
                '[Step 4] Creating %s MB vpmem volume "%s" (affinity=0)...',
                self.vpmem_size, self.vpmem_name
            )
            self.cv_HMC.configure_vpmem(self.vpmem_name, self.vpmem_size, affinity=0)
            log.info('  configure_vpmem completed')

            # ------------------------------------------------------------------
            # Step 5 — Confirm volume was created
            # ------------------------------------------------------------------
            log.info('[Step 5] Confirming vpmem volume count...')
            count_after = self._get_vpmem_count()
            if count_after < 1:
                self.fail(
                    'vpmem volume was not created. '
                    'HMC reports {} volume(s) after configure_vpmem.'.format(
                        count_after
                    )
                )
            log.info('  vpmem volume confirmed (HMC count: %d)', count_after)

        # ------------------------------------------------------------------
        # Step 6 — Activate the LPAR (both paths merge here)
        # ------------------------------------------------------------------
        log.info('[Step 6] Activating LPAR and booting to OS...')
        console = self._activate_and_get_console()
        log.info('  System reached OS state')

        # ------------------------------------------------------------------
        # Step 7 — Verify NVDIMM region is visible to the kernel
        # ------------------------------------------------------------------
        log.info('[Step 7] Verifying NVDIMM region is enumerated by the kernel...')
        self._ensure_ndctl()
        regions = console.run_command('ndctl list -R', timeout=60)
        non_empty_regions = [r for r in regions if r.strip()]
        if not non_empty_regions:
            self.fail(
                'No NVDIMM regions reported by ndctl after vpmem provisioning. '
                'Expected at least one region for the {} MB volume.'.format(
                    self.vpmem_size
                )
            )
        log.info('  NVDIMM regions enumerated by kernel:')
        for line in non_empty_regions:
            log.info('    %s', line.strip())

        # ------------------------------------------------------------------
        # Step 8 — Verify dmesg is clean
        # ------------------------------------------------------------------
        log.info('[Step 8] Checking dmesg for errors (emerg/alert/crit/err)...')
        dmesg_err = self.util.collect_errors_by_level(
            level_check=4, skip_errors=_DMESG_SKIP_ERRORS
        )
        if dmesg_err:
            self.fail(
                'dmesg errors detected after vpmem provisioning and activation. '
                '{}'.format(dmesg_err)
            )
        log.info('  dmesg is clean')

        log.info('=' * 70)
        log.info(
            'SUCCESS: test_01 — vpmem "%s" (%s MB) is visible, '
            'kernel is stable',
            self.vpmem_name, self.vpmem_size
        )
        log.info('=' * 70)

    # ------------------------------------------------------------------
    # Test 2 — Remove vpmem and validate
    # ------------------------------------------------------------------

    def test_02_remove_vpmem_and_validate(self):
        '''
        Remove all vpmem volumes via HMC and verify the device is no longer
        visible to the kernel after the next LPAR activation.

        Step 1 — Shutdown the LPAR; confirm NOT_ACTIVE state
        Step 2 — Remove all vpmem volumes via HMC
        Step 3 — Confirm HMC reports zero volumes
        Step 4 — Set boot_mode=norm on the LPAR profile to prevent SMS menu
        Step 5 — Wait for PHYP to settle the hardware config change
        Step 6 — Confirm LPAR is still NOT_ACTIVE before activation
        Step 7 — Clear dmesg and activate LPAR to OS
        Step 8 — Verify ndctl reports zero NVDIMM regions
        Step 9 — Verify dmesg is clean
        '''
        log.info('=' * 70)
        log.info('test_02_remove_vpmem_and_validate')
        log.info('  LPAR   : %s', self.lpar_name)
        log.info('  System : %s', self.system_name)
        log.info('=' * 70)

        # ------------------------------------------------------------------
        # Step 1 — Shutdown the LPAR and confirm NOT_ACTIVE state
        # ------------------------------------------------------------------
        log.info('[Step 1] Shutting down the LPAR...')
        self.cv_HMC.poweroff_lpar()
        # Explicitly wait for NOT_ACTIVE rather than relying on a fixed sleep.
        # poweroff_lpar() calls wait_lpar_state(NOT_ACTIVE) internally, but we
        # re-confirm here to be certain before issuing the remove_vpmem HMC cmd.
        self.cv_HMC.wait_lpar_state(exp_state='Not Activated')
        log.info('  LPAR confirmed NOT_ACTIVE')

        # ------------------------------------------------------------------
        # Step 2 — Remove all vpmem volumes
        # ------------------------------------------------------------------
        log.info('[Step 2] Removing all vpmem volumes via HMC...')
        count_before = self._get_vpmem_count()
        if count_before == 0:
            log.info('  No vpmem volumes present — nothing to remove')
        else:
            log.info('  Removing %d volume(s)...', count_before)
            self.cv_HMC.remove_vpmem()
            log.info('  remove_vpmem completed')

        # ------------------------------------------------------------------
        # Step 3 — Confirm HMC reports zero volumes
        # ------------------------------------------------------------------
        log.info('[Step 3] Confirming vpmem volume count is zero...')
        count_after = self._get_vpmem_count()
        if count_after != 0:
            self.fail(
                'Expected 0 vpmem volumes after removal but HMC reports '
                '{} volume(s).'.format(count_after)
            )
        log.info('  HMC confirms zero vpmem volumes configured')

        # ------------------------------------------------------------------
        # Step 4 — Set boot_mode=norm to prevent firmware landing in SMS
        #
        # After a hardware config change (vpmem removal), PHYP firmware may
        # prompt for device re-selection on the next activation, dropping the
        # LPAR into the SMS menu. Explicitly setting boot_mode=norm on the
        # profile forces the stored boot list to be used and bypasses SMS.
        # ------------------------------------------------------------------
        log.info('[Step 4] Setting boot_mode=norm on profile "%s"...', self.lpar_prof)
        self.cv_HMC.set_lpar_cfg('boot_mode=norm')
        log.info('  boot_mode=norm set on profile')

        # ------------------------------------------------------------------
        # Step 5 — Allow PHYP time to commit the hardware config change
        #
        # The chhwres (remove_vpmem) command on HMC is acknowledged before
        # PHYP fully commits the memory descriptor change in the hypervisor.
        # Activating too quickly can result in the LPAR booting with stale
        # config or landing in SMS. A 30-second settling wait is sufficient.
        # ------------------------------------------------------------------
        log.info('[Step 5] Waiting 30s for PHYP to settle vpmem removal...')
        time.sleep(30)
        log.info('  Settling wait complete')

        # ------------------------------------------------------------------
        # Step 6 — Confirm LPAR is still NOT_ACTIVE before activation
        # ------------------------------------------------------------------
        log.info('[Step 6] Confirming LPAR state is NOT_ACTIVE before activation...')
        lpar_state = self.cv_HMC.get_lpar_state()
        log.info('  Current LPAR state: %s', lpar_state)
        if lpar_state != 'Not Activated':
            self.fail(
                'Expected LPAR to be NOT_ACTIVE before activation but '
                'current state is "{}". Aborting to avoid '
                'undefined behaviour.'.format(lpar_state)
            )
        log.info('  LPAR is NOT_ACTIVE — safe to activate')

        # ------------------------------------------------------------------
        # Step 7 — Activate the LPAR
        # ------------------------------------------------------------------
        log.info('[Step 7] Activating LPAR and booting to OS...')
        console = self._activate_and_get_console()
        log.info('  System reached OS state')

        # ------------------------------------------------------------------
        # Step 8 — Verify ndctl reports zero NVDIMM regions
        # ------------------------------------------------------------------
        log.info('[Step 8] Verifying no NVDIMM regions are present in kernel...')
        self._ensure_ndctl()
        try:
            regions = console.run_command('ndctl list -R', timeout=60)
        except Exception:
            # ndctl exits non-zero when no regions exist — treat as empty.
            regions = []

        non_empty_regions = [r for r in regions if r.strip()]
        if non_empty_regions:
            self.fail(
                'ndctl still reports NVDIMM region(s) after vpmem removal: '
                '{}'.format(non_empty_regions)
            )
        log.info('  No NVDIMM regions found — vpmem device removed from kernel')

        # ------------------------------------------------------------------
        # Step 9 — Verify dmesg is clean
        # ------------------------------------------------------------------
        log.info('[Step 9] Checking dmesg for errors after vpmem removal...')
        dmesg_err = self.util.collect_errors_by_level(
            level_check=4, skip_errors=_DMESG_SKIP_ERRORS
        )
        if dmesg_err:
            self.fail(
                'dmesg errors detected after vpmem removal and activation. '
                '{}'.format(dmesg_err)
            )
        log.info('  dmesg is clean')

        log.info('=' * 70)
        log.info('SUCCESS: test_02 — vpmem removed and kernel is stable')
        log.info('=' * 70)

    # ------------------------------------------------------------------
    # Teardown — leave the LPAR powered OFF
    # ------------------------------------------------------------------

    @classmethod
    def tearDownClass(cls):
        '''
        Ensure the LPAR is left powered OFF after the suite completes.
        poweroff_lpar() is idempotent — no-op if already NOT_ACTIVE.
        '''
        log.info('tearDownClass: powering off LPAR')
        try:
            cls.cv_HMC.poweroff_lpar()
            log.info('tearDownClass: LPAR is powered off')
        except Exception as exc:
            log.warning(
                'tearDownClass: poweroff_lpar() encountered an error '
                '(non-fatal): %s', str(exc)
            )


def suite():
    '''
    Return a TestSuite that runs test_01 (provision) then test_02 (remove)
    in explicit definition order.

    Usage: --run-suite vpmem_provision_suite
    '''
    s = unittest.TestSuite()
    s.addTest(VpmemProvisionTest('test_01_provision_vpmem_and_activate'))
    s.addTest(VpmemProvisionTest('test_02_remove_vpmem_and_validate'))
    return s


if __name__ == '__main__':
    unittest.main()
