#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSMSBlockDeviceValidation.py $
#
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

'''
OpTestSMSBlockDeviceValidation: Validates block devices visible in SMS TUI
against the booted host OS for a given physical slot DRC.
'''

import dataclasses
import datetime
import json
import os
import re
import time
import unittest

import OpTestConfiguration
import OpTestLogger
from common.OpTestError import OpTestError
from common.OpTestHMC import OpHmcState
from common.OpTestSMS import (
    SMSNavigator, SMSSlotResolver, SMSSlotResult,
)
from common.OpTestBlockDeviceOS import (
    NVMeOSCollector, FCOSCollector, FCNVMeOSCollector, VSCSIOSCollector,
    VFCOSCollector,
    normalize_wwpn, normalize_nsid,
)

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

OS_BOOT_TIMEOUT = 600
OS_POLL_INTERVAL = 20
SMS_CONSOLE_SETTLE = 5


class OpTestSMSBlockDeviceValidation(unittest.TestCase):
    '''Validates SMS TUI block devices against OS for slot DRC.'''

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type
        if self.bmc_type not in ('FSP_PHYP', 'EBMC_PHYP'):
            self.skipTest(
                'OpTestSMSBlockDeviceValidation requires an HMC-managed '
                'LPAR (FSP_PHYP or EBMC_PHYP); got: %s' % self.bmc_type)

        self.cv_HMC = self.cv_SYSTEM.hmc
        self.lpar_name = conf.args.lpar_name
        self.system_name = conf.args.system_name
        self.lpar_prof = conf.args.lpar_prof
        self.logdir = conf.logdir

        try:
            self.slot_drc = conf.args.physical_slot
        except AttributeError:
            self.fail(
                'Missing required argument --physical-slot. '
                'Provide the full DRC of the slot to validate '
                '(e.g. U50EE.001.WZS0011-P3-C5-R1).')
        if not self.slot_drc:
            self.fail('--physical-slot must not be empty.')

        self.category = getattr(conf.args, 'sms_device_category', 'all')
        self._sms_result = None
        self._os_data = {}
        self._console_active = False
        self._test_completed = False

        log.info('OpTestSMSBlockDeviceValidation setup: '
                 'system=%s lpar=%s profile=%s slot=%s category=%s',
                 self.system_name, self.lpar_name, self.lpar_prof,
                 self.slot_drc, self.category)

    def runTest(self):
        '''Drive the full SMS block-device validation flow.'''
        log.info('=== OpTestSMSBlockDeviceValidation START ===')
        log.info('Slot: %s  Category: %s', self.slot_drc, self.category)

        self._boot_to_sms()
        self._capture_sms_data()
        self._boot_to_os()
        self._collect_os_data()
        self._validate()

        self._test_completed = True
        log.info('=== OpTestSMSBlockDeviceValidation PASS ===')

    def _boot_to_sms(self):
        '''Shut down LPAR (if running) and activate it to SMS boot mode.'''
        log.info('--- Step 1: Boot to SMS ---')
        if not self.cv_HMC.is_lpar_in_managed_system(
                self.system_name, self.lpar_name):
            self.fail(
                "LPAR '%s' not found on managed system '%s'. "
                "Verify --system-name and --lpar-name."
                % (self.lpar_name, self.system_name))

        state = self.cv_HMC.get_lpar_state()
        log.info('LPAR current state before SMS boot: %s', state)

        if state not in (OpHmcState.NOT_ACTIVE, OpHmcState.NA):
            log.info('Shutting down LPAR (current state: %s)', state)
            try:
                self.cv_HMC.poweroff_lpar()
            except Exception as e:
                self.fail(
                    'Failed to shut down LPAR before SMS activation: %s' % e)

        cmd = ('chsysstate -m %s -r lpar -n %s -o on -b sms'
               % (self.system_name, self.lpar_name))
        if self.lpar_prof:
            cmd += ' -f %s' % self.lpar_prof

        log.info('Activating LPAR to SMS boot mode: %s', cmd)
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=60)
        except Exception as e:
            self.fail(
                "Failed to activate LPAR '%s' to SMS. "
                "Check profile with: lssyscfg -m %s -r lpar "
                "--filter lpar_names=%s -F curr_profile,default_profile\n"
                "Error: %s"
                % (self.lpar_name, self.system_name, self.lpar_name, e))

        try:
            self.cv_HMC.wait_lpar_state(OpHmcState.OF, timeout=120)
        except Exception as e:
            state_now = self.cv_HMC.get_lpar_state()
            self.fail(
                "LPAR did not reach Open Firmware (SMS) state within 120s. "
                "Current state: %s. Error: %s" % (state_now, e))

        log.info('LPAR is in Open Firmware (SMS) state -- Step 1 complete')

    def _capture_sms_data(self):
        '''Connect to LPAR console via mkvterm and collect SMS device data.'''
        log.info('--- Step 2: Capture SMS data (slot=%s category=%s) ---',
                 self.slot_drc, self.category)
        try:
            pty = self.cv_HMC.console.connect()
            self._console_active = True
        except Exception as e:
            self.fail('Failed to open LPAR console (mkvterm): %s' % e)

        nav = SMSNavigator(pty)
        result = SMSSlotResult(slot_drc=self.slot_drc)

        log.info('Waiting %ss for console buffer to settle',
                 SMS_CONSOLE_SETTLE)
        time.sleep(SMS_CONSOLE_SETTLE)

        try:
            try:
                nav.navigate_to_main_menu()
            except OpTestError as e:
                self.fail(
                    'Failed to reach SMS main menu: %s\n'
                    'Verify the LPAR is in Open Firmware state and the '
                    'console is not locked by another session.' % e)

            try:
                nav.navigate_to_io_info()
            except OpTestError as e:
                self.fail(
                    'Failed to navigate to I/O Device Information: %s' % e)

            self._run_sms_capture(nav, result)
        finally:
            try:
                nav.exit_sms()
            except Exception as e:
                log.warning('exit_sms failed (non-fatal): %s', e)
            self._deactivate_console()

        total = (len(result.nvme) + len(result.fcp) +
                 len(result.fcnvme) + len(result.vscsi) + len(result.vfc))

        if result.errors:
            if total == 0:
                self.fail(
                    'SMS data capture FAILED -- no adapters found and '
                    '%d error(s) occurred for slot %s (category=%s):\n%s'
                    % (len(result.errors), self.slot_drc, self.category,
                       '\n'.join('  * ' + e for e in result.errors)))
            log.warning('SMS capture completed with %d error(s):',
                        len(result.errors))
            for err in result.errors:
                log.warning('  * %s', err)

        if total == 0:
            self.fail(
                "SMS data capture FAILED -- slot '%s' was not found in any "
                "SMS adapter list for category '%s'. "
                "Verify --physical-slot matches a DRC shown in the SMS "
                "I/O Device Information menu."
                % (self.slot_drc, self.category))

        self._sms_result = result
        self._save_json(result)
        log.info('Step 2 complete: nvme=%d fcp=%d fcnvme=%d vscsi=%d vfc=%d',
                 len(result.nvme), len(result.fcp),
                 len(result.fcnvme), len(result.vscsi), len(result.vfc))

    def _run_sms_capture(self, nav, result):
        '''Navigate and collect data for every requested category.'''
        resolver = SMSSlotResolver(self.slot_drc)
        cats = self._requested_categories()

        cat_handlers = [
            ('nvme', 'NVMe',
             lambda: self._collect_nvme_sms(nav, resolver, result)),
            ('fcp', 'FCP',
             lambda: result.fcp.extend(
                 resolver.resolve(
                     nav.collect_fcp_adapters(slot_filter=resolver)))),
            ('fcnvme', 'FC NVMe',
             lambda: result.fcnvme.extend(
                 resolver.resolve(
                     nav.collect_fcnvme_adapters(slot_filter=resolver)))),
            ('vscsi', 'vSCSI',
             lambda: result.vscsi.extend(
                 resolver.resolve(
                     nav.collect_vscsi_adapters(slot_filter=resolver)))),
            ('vfc', 'VFC',
             lambda: result.vfc.extend(
                 resolver.resolve(
                     nav.collect_vfc_adapters(slot_filter=resolver)))),
        ]

        for cat_key, display_name, collect_fn in cat_handlers:
            if cat_key in cats:
                try:
                    log.info('Collecting %s adapters (slot filter: %s)',
                             display_name, self.slot_drc)
                    collect_fn()
                    self._back_to_io_info(nav)
                except OpTestError as e:
                    msg = '%s collection failed: %s' % (display_name, e)
                    log.error(msg)
                    result.errors.append(msg)
                    self._back_to_io_info(nav)

    def _collect_nvme_sms(self, nav, resolver, result):
        all_adapters = nav.collect_nvme_adapters()
        matched = resolver.resolve(all_adapters)
        log.info('NVMe: %d total, %d matched slot %s',
                 len(all_adapters), len(matched), self.slot_drc)
        for a in matched:
            nav.collect_nvme_detail(a)
            result.nvme.append(a)

    def _back_to_io_info(self, nav):
        '''Return to I/O Device Information from any sub-menu.'''
        try:
            nav._sms_send(nav.C.NAV_MAIN,
                          r'5\s*\.\s*Select Boot Options',
                          timeout=nav.C.T_MENU)
            nav.navigate_to_io_info()
        except OpTestError:
            pass

    def _requested_categories(self):
        '''Return set of category strings to collect.'''
        if self.category == 'all':
            return {'nvme', 'fcp', 'fcnvme', 'vscsi', 'vfc'}
        return {self.category}

    def _boot_to_os(self):
        '''Restart LPAR into OS and wait for Running state.'''
        log.info('--- Step 3: Boot to OS (timeout=%ss) ---', OS_BOOT_TIMEOUT)
        try:
            self.cv_HMC.restart_lpar()
        except Exception as e:
            self.fail('Failed to restart LPAR into OS: %s' % e)

        elapsed = 0
        state = None
        while elapsed < OS_BOOT_TIMEOUT:
            state = self.cv_HMC.get_lpar_state()
            log.debug('LPAR state after %ds: %s', elapsed, state)
            if state == OpHmcState.RUNNING:
                break
            time.sleep(OS_POLL_INTERVAL)
            elapsed += OS_POLL_INTERVAL
        else:
            self.fail(
                'LPAR did not reach Running state within %ss '
                '(last observed state: %s). '
                'Check the LPAR console for boot errors.'
                % (OS_BOOT_TIMEOUT, state))

        log.info('Step 3 complete: LPAR is Running (elapsed ~%ds)', elapsed)

    def _collect_os_data(self):
        '''Collect block device data from booted OS via SSH.'''
        log.info('--- Step 4: Collect OS data ---')
        try:
            conn = OpTestConfiguration.conf.host().get_ssh_connection()
        except Exception as e:
            self.fail('Failed to open SSH connection to OS: %s' % e)

        collectors = [
            ('nvme', NVMeOSCollector, self.slot_drc),
            ('fcp', FCOSCollector, self.slot_drc),
            ('fcnvme', FCNVMeOSCollector,
             self._fc_slot_from_fcnvme(self._sms_result.fcnvme)
             if self._sms_result.fcnvme else self.slot_drc),
            ('vscsi', VSCSIOSCollector, self.slot_drc),
            ('vfc', VFCOSCollector, self.slot_drc),
        ]

        for cat, collector_cls, target_slot in collectors:
            if getattr(self._sms_result, cat, None):
                log.info('Collecting %s OS data for slot %s', cat, target_slot)
                try:
                    self._os_data[cat] = collector_cls(
                        conn).collect(target_slot)
                except Exception as e:
                    self.fail('OS %s data collection failed for slot %s: %s'
                              % (cat, target_slot, e))

        log.info('Step 4 complete: OS categories collected: %s',
                 list(self._os_data.keys()))

    def _fc_slot_from_fcnvme(self, fcnvme_adapters):
        '''Extract physical slot DRC base from FC NVMe adapter list.'''
        for a in fcnvme_adapters:
            if not a.is_virtual:
                return re.sub(r'-T\d+$', '', a.drc.strip())
        return self.slot_drc

    def _validate(self):
        '''Validate SMS vs OS data, compare fields, fail on mismatch.'''
        log.info('--- Step 5: Validate SMS vs OS data ---')
        all_mismatches = []
        validators = [
            ('nvme', self._validate_nvme),
            ('fcp', self._validate_fcp),
            ('fcnvme', self._validate_fcnvme),
            ('vscsi', self._validate_vscsi),
            ('vfc', self._validate_vfc),
        ]
        for cat, val_fn in validators:
            sms_list = getattr(self._sms_result, cat, None)
            if sms_list:
                all_mismatches.extend(
                    val_fn(sms_list, self._os_data.get(cat, {})))

        if all_mismatches:
            self._print_mismatch_report(all_mismatches)
            self.fail(
                'SMS block device validation FAILED: %d mismatch(es) '
                'for slot %s -- see mismatch report above.'
                % (len(all_mismatches), self.slot_drc))

        log.info('Step 5 complete: all devices validated for slot %s',
                 self.slot_drc)

    def _validate_common_fc_vscsi(self, category, sms_adapters, os_data,
                                  key_extractor, skip_condition=None,
                                  check_wwpn=False):
        '''Generic validator for port_state, disk_count, and slot presence.'''
        mismatches = []
        for sms in sms_adapters:
            if skip_condition and skip_condition(sms):
                log.info('%s: drc=%s skipped', category, sms.drc)
                continue

            lookup_key = key_extractor(sms)
            os_info = os_data.get(lookup_key)
            if os_info is None:
                mismatches.append({
                    'category': category,
                    'drc': sms.drc,
                    'field': ('slot_presence' if hasattr(sms, 'vio_addr')
                              else 'local_wwpn'),
                    'sms': getattr(sms, 'local_wwpn', sms.drc),
                    'os': '(not found)',
                    'note': '%s entry not found on OS' % category,
                })
                continue

            if check_wwpn and getattr(sms, 'local_wwpn', None):
                sms_wwpn = normalize_wwpn(sms.local_wwpn)
                os_wwpn = os_info.get('local_wwpn', '')
                if sms_wwpn and os_wwpn and sms_wwpn != os_wwpn:
                    mismatches.append({
                        'category': category,
                        'drc': sms.drc,
                        'field': 'local_wwpn',
                        'sms': sms_wwpn,
                        'os': os_wwpn,
                        'note': '%s local WWPN mismatch' % category,
                    })

            if ('port_state' in os_info and
                    os_info.get('port_state') != 'Online'):
                mismatches.append({
                    'category': category,
                    'drc': sms.drc,
                    'field': 'port_state',
                    'sms': 'Online (expected)',
                    'os': os_info.get('port_state', ''),
                    'note': 'Port not Online on OS',
                })

            if hasattr(sms, 'devices'):
                sms_disk_count = len(sms.devices)
                os_disk_count = os_info.get('disk_count', -1)
                if sms_disk_count != os_disk_count:
                    extra = (' %s' % os_info.get('disks', [])
                             if os_disk_count != -1 else '')
                    mismatches.append({
                        'category': category,
                        'drc': sms.drc,
                        'field': 'disk_count',
                        'sms': str(sms_disk_count),
                        'os': str(os_disk_count) + extra,
                        'note': '%s disk count mismatch' % category,
                    })
        return mismatches

    def _validate_nvme(self, sms_adapters, os_data):
        '''Compare SMS NVMe adapters against OS NVMe data.'''
        mismatches = []
        for sms in sms_adapters:
            serial = sms.serial.strip().upper()
            os_info = self._find_nvme_by_serial(os_data, serial)
            if os_info is None:
                mismatches.append({
                    'category': 'nvme',
                    'drc': sms.drc,
                    'field': 'serial',
                    'sms': serial,
                    'os': '(not found)',
                    'note': 'controller not found on OS',
                })
                continue

            checks = [
                ('model', sms.model.strip(),
                 os_info.get('model', '').strip()),
                ('fw_rev', sms.fw_rev.strip().upper(),
                 os_info.get('fw_rev', '').strip().upper()),
                ('nvme_version', sms.nvme_version.strip(),
                 os_info.get('nvme_version', '').strip()),
                ('namespace_count', str(len(sms.namespaces)),
                 str(os_info.get('namespace_count', -1))),
            ]
            for field, sms_val, os_val in checks:
                if sms_val and os_val and sms_val != os_val:
                    mismatches.append({
                        'category': 'nvme',
                        'drc': sms.drc,
                        'field': field,
                        'sms': sms_val,
                        'os': os_val,
                        'note': 'value mismatch',
                    })

            if sms.namespaces:
                sms_nsids = {
                    normalize_nsid(ns.nsid_hex, 16) for ns in sms.namespaces
                }
                os_nsids = os_info.get('nsid_set', set())
                if sms_nsids and os_nsids and sms_nsids != os_nsids:
                    mismatches.append({
                        'category': 'nvme',
                        'drc': sms.drc,
                        'field': 'nsid_set',
                        'sms': repr(sms_nsids),
                        'os': repr(os_nsids),
                        'note': 'namespace ID set mismatch',
                    })
        return mismatches

    def _find_nvme_by_serial(self, os_data, serial):
        '''Return OS NVMe info dict whose serial matches, or None.'''
        for s, info in os_data.items():
            if s.strip().upper() == serial:
                return info
        return None

    def _validate_fcp(self, sms_adapters, os_data):
        '''Validate physical FC HBA adapters for a slot.'''
        return self._validate_common_fc_vscsi(
            'fcp', sms_adapters, os_data,
            key_extractor=lambda s: normalize_wwpn(s.local_wwpn),
            skip_condition=lambda s: s.is_virtual or s.no_devices)

    def _validate_fcnvme(self, sms_adapters, os_data):
        '''Compare FC NVMe over Fabric adapters.'''
        mismatches = []
        for sms in sms_adapters:
            if sms.is_virtual or sms.link_down or sms.no_devices:
                log.info('FC NVMe: drc=%s skipped (virt/linkdown/nodev)',
                         sms.drc)
                continue

            if not os_data:
                mismatches.append({
                    'category': 'fcnvme',
                    'drc': sms.drc,
                    'field': 'os_data',
                    'sms': '(has namespaces)',
                    'os': '(no OS data collected)',
                    'note': 'OS collection returned no data',
                })
                continue

            sms_targets = {}
            for ns in sms.namespaces:
                wwpn = ns.target_wwpn.lower()
                nsid = normalize_nsid(ns.nsid_hex, 16)
                sms_targets.setdefault(wwpn, set()).add(nsid)

            for port_wwpn, os_info in os_data.items():
                os_tgts = os_info.get('targets', {})
                for wwpn, sms_nsids in sms_targets.items():
                    os_nsids = os_tgts.get(wwpn, set())
                    if os_nsids is None:
                        mismatches.append({
                            'category': 'fcnvme',
                            'drc': sms.drc,
                            'field': 'target[%s]' % wwpn,
                            'sms': repr(sms_nsids),
                            'os': '(target not found)',
                            'note': 'target WWPN not found on OS',
                        })
                    elif sms_nsids and os_nsids and sms_nsids != os_nsids:
                        mismatches.append({
                            'category': 'fcnvme',
                            'drc': sms.drc,
                            'field': 'nsid_set[%s]' % wwpn,
                            'sms': repr(sms_nsids),
                            'os': repr(os_nsids),
                            'note': 'NSID set mismatch',
                        })
        return mismatches

    def _validate_vscsi(self, sms_adapters, os_data):
        '''Compare vSCSI adapters.'''
        return self._validate_common_fc_vscsi(
            'vscsi', sms_adapters, os_data,
            key_extractor=lambda s: s.vio_addr)

    def _validate_vfc(self, sms_adapters, os_data):
        '''Validate virtual FC (vfc-client) adapters.'''
        return self._validate_common_fc_vscsi(
            'vfc', sms_adapters, os_data,
            key_extractor=lambda s: s.vio_addr,
            skip_condition=lambda s: s.no_devices,
            check_wwpn=True)

    def tearDown(self):
        '''Safety-net cleanup.'''
        if self._test_completed:
            log.info('tearDown: test completed normally -- no cleanup needed')
            return

        log.info('tearDown: test did not complete normally -- cleaning up')
        self._deactivate_console()
        try:
            log.info('tearDown: restarting LPAR into OS')
            self.cv_HMC.restart_lpar()
            log.info('tearDown: LPAR is Running')
        except Exception as e:
            log.warning(
                'tearDown: restart failed (%s); attempting shutdown', e)
            try:
                self.cv_HMC.poweroff_lpar()
                log.info('tearDown: LPAR powered off')
            except Exception as e2:
                log.warning('tearDown: shutdown also failed: %s', e2)

    def _deactivate_console(self):
        '''Deactivate mkvterm PTY if currently open.'''
        if self._console_active:
            try:
                self.cv_HMC.console.deactivate_lpar_console()
                log.info('Console deactivated')
            except Exception as e:
                log.warning('Failed to deactivate console: %s', e)
            self._console_active = False

    def _save_json(self, result):
        '''Serialise SMSSlotResult to JSON in logdir.'''
        slot_safe = re.sub(r'[^A-Za-z0-9._-]', '_', self.slot_drc)
        ts = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        filepath = os.path.join(
            self.logdir, 'sms_blockdev_%s_%s.json' % (slot_safe, ts))
        try:
            with open(filepath, 'w') as f:
                json.dump(dataclasses.asdict(result), f, indent=2)
            log.info('SMS result saved to: %s', filepath)
        except Exception as e:
            log.warning('Could not save JSON artefact: %s', e)

    def _print_mismatch_report(self, mismatches):
        '''Log a formatted mismatch table.'''
        log.error('=== SMS BLOCK DEVICE VALIDATION -- MISMATCH REPORT ===')
        log.error('Slot:     %s', self.slot_drc)
        log.error('Category: %s\n', self.category)
        hdr = ' %-10s | %-30s | %-30s | %-30s | %s'
        sep = (' ' + '-' * 10 + '-+-' + '-' * 30 + '-+-' +
               '-' * 30 + '-+-' + '-' * 30 + '-+-' + '-' * 20)
        log.error(hdr, 'Category', 'DRC', 'Field', 'SMS Value',
                  'OS Value / Note')
        log.error(sep)
        for m in mismatches:
            log.error(
                ' %-10s | %-30s | %-30s | %-30s | %s -> %s',
                m['category'], m['drc'][-30:], m['field'],
                str(m['sms'])[:30], str(m['os'])[:30], m.get('note', ''))
        log.error(sep)
        log.error('Total: %d mismatch(es)', len(mismatches))


# --- Test suite entry point -------------------------------------------------

def suite():
    s = unittest.TestSuite()
    s.addTest(OpTestSMSBlockDeviceValidation('runTest'))
    return s
