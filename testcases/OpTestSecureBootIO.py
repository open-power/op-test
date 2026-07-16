#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSecureBootIO.py $
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
OpTestSecureBootIO
------------------
Validates that IO device state is preserved across a Secure Boot enable
transition on IBM Power LPARs (RHEL/SUSE, ppc64le).

Each IO device type (NVMe, FC, vSCSI) is encapsulated in its own plugin
class derived from IODevicePlugin.  Adding a new device type requires only
a new plugin class and a new runnable test class — no changes to the base
flow are needed.
'''
import re
import unittest
import OpTestConfiguration
import OpTestLogger

from common.OpTestSystem import OpSystemState
from common.OpTestUtil import OpTestUtil
from testcases.OpTestGSBStaticKey import OpTestGSBStaticKey

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


# ======================================================================= #
#  IO Device Plugin Base Class                                             #
# ======================================================================= #

class IODevicePlugin:
    '''
    Abstract base for IO device plugins.

    Each subclass encapsulates one device type (NVMe, FC, vSCSI, ...) and
    must implement collect() and compare().  The test host console handle
    is injected at construction time.
    '''

    def __init__(self, console):
        self.c = console

    def is_available(self):
        '''Return True if this device type is present on the host.'''
        raise NotImplementedError

    def collect(self):
        '''
        Capture device state and return a dict snapshot.
        All keys in the returned dict must be stable across reboots.
        '''
        raise NotImplementedError

    def compare(self, baseline, snapshot):
        '''
        Compare baseline dict to snapshot dict.
        Return a list of failure strings (empty list means pass).
        '''
        raise NotImplementedError


# ======================================================================= #
#  NVMe Plugin                                                             #
# ======================================================================= #

class NVMePlugin(IODevicePlugin):
    '''
    IO device plugin for NVMe PCIe-attached controllers.

    Controller identity is keyed by serial number (SN) from nvme id-ctrl.
    Fallback to NQN-embedded SN, then to PCI address when id-ctrl fails.
    An optional filter list (set of tokens) limits which controllers are
    included; empty filter means all discovered controllers.
    '''

    def __init__(self, console, device_filter=None):
        super().__init__(console)
        self._filter = device_filter or set()
        self._serial_to_dev = {}

    # ------------------------------------------------------------------ #

    def _parse_subsys_map(self):
        '''
        Parse 'nvme list-subsys' and return a per-controller dict.
        Returns: { 'nvmeX': { 'pci': '<addr>', 'nqn': '<NQN>' }, ... }
        '''
        out = self.c.run_command_ignore_fail('nvme list-subsys')
        pci_re = re.compile(
            r'^\s*\+-\s+(nvme\d+)\s+pcie\s+(?:traddr=)?'
            r'([\da-fA-F]{4}:[\da-fA-F]{2}:[\da-fA-F]{2}\.\d)'
        )
        nqn_re = re.compile(r'NQN=(\S+)')
        result = {}
        current_nqn = ''
        for line in out:
            m = nqn_re.search(line)
            if m:
                current_nqn = m.group(1)
                continue
            m = pci_re.match(line)
            if m:
                result[m.group(1)] = {
                    'pci': m.group(2),
                    'nqn': current_nqn,
                }
        return result

    @staticmethod
    def _sn_from_nqn(nqn):
        '''
        Extract a serial-number candidate from the last colon segment of an NQN.
        Returns the segment if it is 6–24 alphanumeric characters, else ''.
        '''
        if not nqn:
            return ''
        candidate = nqn.rstrip().split(':')[-1]
        return candidate if re.match(r'^[A-Za-z0-9]{6,24}$', candidate) else ''

    def _resolve_identity(self, ctrl, subsys_map):
        '''
        Resolve the stable identity key for a controller.
        Priority: id-ctrl SN > NQN-embedded SN > PCI address.
        Returns (identity_key, pci_addr) or (None, pci_addr) to skip.
        '''
        ctrl_name = ctrl.replace('/dev/', '')
        pci_addr = subsys_map.get(ctrl_name, {}).get('pci', '')
        nqn = subsys_map.get(ctrl_name, {}).get('nqn', '')

        sn = ''
        sn_out = self.c.run_command_ignore_fail(
            "nvme id-ctrl %s | grep '^sn'" % ctrl
        )
        for line in sn_out:
            if line.startswith('sn'):
                sn = line.split(':', 1)[-1].strip()
                break

        if not sn:
            sn = self._sn_from_nqn(nqn)
            if sn:
                log.warning("%s: using NQN-derived SN '%s'", ctrl, sn)

        if sn:
            return sn, pci_addr

        if pci_addr:
            identity = 'pci:' + pci_addr
            log.warning("%s: using PCI address key '%s'", ctrl, identity)
            return identity, pci_addr

        log.warning("%s: SN and PCI address unavailable — skipping", ctrl)
        return None, pci_addr

    def _build_serial_map(self):
        '''
        Build self._serial_to_dev = { identity_key: '/dev/nvmeX' }.
        Applies self._filter if non-empty.  Skips if no controllers found.
        '''
        subsys_map = self._parse_subsys_map()
        out = self.c.run_command('nvme list')
        ctrl_paths = []
        for line in out:
            if not line.startswith('/dev/nvme'):
                continue
            ctrl_name = re.sub(r'n\d+$', '', line.split()[0].replace('/dev/', ''))
            ctrl_path = '/dev/' + ctrl_name
            if ctrl_path not in ctrl_paths:
                ctrl_paths.append(ctrl_path)

        serial_map = {}
        for ctrl in ctrl_paths:
            ctrl_name = ctrl.replace('/dev/', '')
            identity, pci_addr = self._resolve_identity(ctrl, subsys_map)
            if not identity:
                continue
            if self._filter:
                if not (identity in self._filter
                        or ctrl_name in self._filter
                        or (pci_addr and pci_addr in self._filter)):
                    continue
            serial_map[identity] = ctrl
            log.info("Mapped %-32s  →  %s  (pci=%s)",
                     identity, ctrl, pci_addr or 'unknown')

        self._serial_to_dev = serial_map

    # ------------------------------------------------------------------ #

    def is_available(self):
        '''Return True if at least one NVMe controller is listed.'''
        out = self.c.run_command_ignore_fail('nvme list')
        return any(line.startswith('/dev/nvme') for line in out)

    def collect(self):
        '''
        Capture NVMe controller/namespace/queue state.
        Returns a dict keyed by serial number where applicable.
        All identity keys are stable across reboots.
        '''
        self._build_serial_map()
        if not self._serial_to_dev:
            return {}

        data = {}

        nvme_list_out = self.c.run_command('nvme list')
        serials = set()
        for line in nvme_list_out:
            if line.startswith('/dev/nvme'):
                fields = line.split()
                if len(fields) >= 3:
                    serials.add(fields[2].strip())
        data['nvme_list_serials'] = serials

        subsys_out = self.c.run_command('nvme list-subsys')
        nqns = set()
        for line in subsys_out:
            m = re.search(r'NQN=(\S+)', line)
            if m:
                nqns.add(m.group(1))
        data['subsys_nqns'] = nqns

        lsmod_out = self.c.run_command('lsmod | grep nvme')
        loaded = {line.split()[0] for line in lsmod_out if line.split()}
        data['nvme_core_loaded'] = 'nvme_core' in loaded
        data['nvme_loaded'] = 'nvme' in loaded

        modinfo_out = self.c.run_command_ignore_fail(
            r"modinfo nvme | grep '^signer'"
        )
        data['mod_signer'] = ''
        for line in modinfo_out:
            if line.startswith('signer'):
                data['mod_signer'] = line.split(':', 1)[-1].strip()
                break

        lsblk_out = self.c.run_command(
            "lsblk --noheadings -o SERIAL,TRAN | grep nvme"
        )
        data['lsblk_serials'] = {
            line.split()[0].strip() for line in lsblk_out if line.split()
        }

        data['id_ctrl'] = {}
        data['list_ns'] = {}
        for sn, dev in self._serial_to_dev.items():
            data['id_ctrl'][sn] = self.c.run_command(
                r"nvme id-ctrl %s | grep -E '^mn|^sn|^fr|^nn|^frmw'" % dev
            )
            data['list_ns'][sn] = self.c.run_command('nvme list-ns %s' % dev)

        data['queue_attrs'] = {}
        for sn, ctrl_dev in self._serial_to_dev.items():
            ctrl_name = ctrl_dev.replace('/dev/', '')
            ns_out = self.c.run_command_ignore_fail(
                "lsblk --noheadings -o NAME,TYPE %s "
                "| awk '$2==\"disk\"{print $1}'" % ctrl_dev
            )
            ns_name = ''
            for line in ns_out:
                if re.match(r'^nvme\d+n\d+$', line.strip()):
                    ns_name = line.strip()
                    break
            if not ns_name:
                ns_name = ctrl_name + 'n1'

            attrs = {}
            for attr in ('physical_block_size', 'logical_block_size',
                         'minimum_io_size', 'optimal_io_size'):
                out = self.c.run_command_ignore_fail(
                    'cat /sys/block/%s/queue/%s' % (ns_name, attr)
                )
                if out:
                    attrs[attr] = out[0].strip()
            data['queue_attrs'][sn] = attrs

        return data

    def compare(self, baseline, snapshot):
        '''
        Compare NVMe baseline vs snapshot dicts.
        Returns a list of failure strings.
        '''
        failures = []

        def _set_diff(key, label):
            b = baseline.get(key, set())
            s = snapshot.get(key, set())
            missing = b - s
            extra = s - b
            if missing:
                failures.append(
                    "MISSING %s after SB enable: %s"
                    % (label, ', '.join(sorted(missing)))
                )
            if extra:
                failures.append(
                    "UNEXPECTED new %s after SB enable: %s"
                    % (label, ', '.join(sorted(extra)))
                )

        _set_diff('nvme_list_serials', 'controllers (nvme list serials)')
        _set_diff('subsys_nqns', 'subsystem NQNs')
        _set_diff('lsblk_serials', 'block devices (lsblk serials)')

        for mod_key, mod_name in (('nvme_core_loaded', 'nvme_core'),
                                  ('nvme_loaded', 'nvme')):
            if baseline.get(mod_key) and not snapshot.get(mod_key):
                failures.append(
                    "MODULE MISSING: '%s' absent after SB enable" % mod_name
                )

        b_signer = baseline.get('mod_signer', '')
        s_signer = snapshot.get('mod_signer', '')
        if b_signer and s_signer and b_signer != s_signer:
            failures.append(
                "MISMATCH mod_signer: '%s' → '%s'" % (b_signer, s_signer)
            )

        for sn in baseline.get('id_ctrl', {}):
            if sn not in snapshot.get('id_ctrl', {}):
                failures.append("MISSING id_ctrl for SN=%s" % sn)
            elif baseline['id_ctrl'][sn] != snapshot['id_ctrl'][sn]:
                failures.append(
                    "MISMATCH id_ctrl[SN=%s]: BEFORE=%s AFTER=%s"
                    % (sn,
                       ' | '.join(baseline['id_ctrl'][sn]),
                       ' | '.join(snapshot['id_ctrl'][sn]))
                )

        for sn in baseline.get('list_ns', {}):
            if sn not in snapshot.get('list_ns', {}):
                failures.append("MISSING list_ns for SN=%s" % sn)
            elif baseline['list_ns'][sn] != snapshot['list_ns'][sn]:
                failures.append(
                    "MISMATCH list_ns[SN=%s]: BEFORE=%s AFTER=%s"
                    % (sn,
                       ' | '.join(baseline['list_ns'][sn]),
                       ' | '.join(snapshot['list_ns'][sn]))
                )

        b_qa = baseline.get('queue_attrs', {})
        s_qa = snapshot.get('queue_attrs', {})
        for sn in b_qa:
            for attr, b_val in b_qa[sn].items():
                s_val = s_qa.get(sn, {}).get(attr, '')
                if s_val and b_val != s_val:
                    failures.append(
                        "MISMATCH queue_attrs[SN=%s][%s]: %s → %s"
                        % (sn, attr, b_val, s_val)
                    )

        nvme_present = bool(
            self.c.run_command_ignore_fail('command -v nvme')
        )
        if nvme_present:
            for sn, dev in self._serial_to_dev.items():
                out = self.c.run_command_ignore_fail(
                    'nvme show-regs %s -H' % dev
                )
                out_text = ' '.join(out).lower()
                if not any(kw in out_text for kw in
                           ('permission', 'eperm',
                            'operation not permitted', 'lockdown')):
                    failures.append(
                        "LOCKDOWN BYPASS: 'nvme show-regs %s -H' (SN=%s) "
                        "succeeded under lockdown=integrity — expected EPERM"
                        % (dev, sn)
                    )

        return failures


# ======================================================================= #
#  Secure Boot IO Base Test Class                                          #
# ======================================================================= #

class OpTestSecureBootIO(unittest.TestCase):
    '''
    Base class for IO integrity validation across a Secure Boot enable cycle.

    Subclasses provide a populated self.io_plugins list of IODevicePlugin
    instances.  The 6-phase flow is device-type agnostic: collect baseline,
    enable SB, collect snapshot, diff.  Adding a new IO type requires only
    a new IODevicePlugin subclass and a new test class.
    '''

    # Subclasses set this to the list of IODevicePlugin instances to exercise.
    io_plugins = []

    def setUp(self):
        conf = OpTestConfiguration.conf

        if conf.args.bmc_type not in ('FSP_PHYP', 'EBMC_PHYP'):
            self.skipTest(
                "OpTestSecureBootIO requires bmc_type FSP_PHYP or EBMC_PHYP"
            )

        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.c = self.cv_HMC.get_host_console()
        self.hmc_con = self.cv_HMC.ssh
        self.util = OpTestUtil(conf)

        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        os_level = self.cv_HOST.host_get_OS_Level()
        if 'Red Hat' in os_level:
            self.distro = 'rhel'
        elif 'SLES' in os_level:
            self.distro = 'sles'
        else:
            self.skipTest(
                "OpTestSecureBootIO: unsupported distro — RHEL and SUSE only"
            )

    # ------------------------------------------------------------------ #

    def _enable_secureboot_via_hmc(self):
        '''
        PHASE 3 — OS-level SB prep followed by HMC power-cycle.

        Delegates OS-level preparation (grub signing, PReP write) to
        OpTestGSBStaticKey.os_secureboot_enable() to avoid duplicating
        that logic.  Then issues chsyscfg secure_boot=2 and reboots.
        '''
        gsb = OpTestGSBStaticKey.__new__(OpTestGSBStaticKey)
        gsb.c = self.c
        gsb.cv_HMC = self.cv_HMC
        gsb.cv_SYSTEM = self.cv_SYSTEM
        gsb.hmc_con = self.hmc_con
        gsb.distro = self.distro
        gsb.util = self.util
        gsb.prepDisk = ''
        gsb.backup_prep_filename = '/root/save-prep'
        gsb.distro_version = self.util.get_distro_version()
        gsb.kernel_signature = self.util.check_kernel_signature()
        gsb.grub_filename = self.util.get_grub_file()
        gsb.grub_signature = self.util.check_grub_signature(gsb.grub_filename)

        log.info("PHASE 3: OS-level Secure Boot preparation")
        gsb.os_secureboot_enable(enable=True)

        log.info("PHASE 3: Powering off LPAR")
        self.cv_HMC.poweroff_lpar()

        log.info("PHASE 3: Setting secure_boot=2 via HMC chsyscfg")
        cmd = (
            'chsyscfg -r lpar -m %s -i "name=%s, secure_boot=2"'
            % (self.cv_HMC.mg_system, self.cv_HMC.lpar_name)
        )
        self.hmc_con.run_command(cmd, timeout=300)

        log.info("PHASE 3: Booting LPAR to OS with Secure Boot enabled")
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    # ------------------------------------------------------------------ #

    def _collect_sb_state(self):
        '''
        Collect lockdown sysfs value and device-tree SB property.
        Returns a dict with keys: lockdown_state, dt_sb.
        '''
        data = {}

        lockdown_out = self.c.run_command(
            'cat /sys/kernel/security/lockdown'
        )
        m = re.search(r'\[(\w+)\]', ' '.join(lockdown_out))
        data['lockdown_state'] = m.group(1) if m else ''

        data['dt_sb'] = self.c.run_command(
            'lsprop /proc/device-tree/ibm,secure-boot'
        )
        return data

    # ------------------------------------------------------------------ #

    def _compare_sb_state(self, baseline_sb, snapshot_sb):
        '''
        Validate must-change SB indicators in the post-SB snapshot.
        Returns a list of failure strings.
        '''
        failures = []

        if snapshot_sb.get('lockdown_state') != 'integrity':
            failures.append(
                "MUST-CHANGE lockdown_state: expected 'integrity', "
                "got: '%s'" % snapshot_sb.get('lockdown_state', '')
            )

        if '00000002' not in ' '.join(snapshot_sb.get('dt_sb', [])):
            failures.append(
                "MUST-CHANGE dt_sb: '00000002' not found in "
                "lsprop /proc/device-tree/ibm,secure-boot"
            )

        return failures

    # ------------------------------------------------------------------ #

    def runTest(self):
        '''
        Orchestrates the 6-phase Secure Boot IO validation flow.

        Phase 1: Capture IO baseline (SB=OFF).
        Phase 2: Check SB state; enable if currently disabled.
        Phase 3: OS prep + HMC power-cycle (secure_boot=2).
        Phase 4: Collect post-SB SB state indicators.
        Phase 5: Capture post-SB IO snapshot.
        Phase 6: Diff baseline vs snapshot; report all failures.
        '''
        active_plugins = [p for p in self.io_plugins if p.is_available()]
        if not active_plugins:
            self.skipTest(
                "No configured IO devices found on host — skipping"
            )

        log.info("PHASE 1: Capturing IO baseline (pre-Secure Boot)")
        baselines = {p: p.collect() for p in active_plugins}
        baseline_sb = self._collect_sb_state()

        log.info("PHASE 2: Checking current Secure Boot state")
        sb_on = self.cv_HMC.check_lpar_secureboot_state(self.hmc_con)
        if sb_on:
            log.warning(
                "PHASE 2: Secure Boot already enabled — skipping PHASE 3"
            )
        else:
            log.info("PHASE 3: Enabling Secure Boot via OS prep + HMC")
            self._enable_secureboot_via_hmc()

        log.info("PHASE 4: Collecting post-SB state indicators")
        snapshot_sb = self._collect_sb_state()

        log.info("PHASE 5: Capturing IO snapshot (post-Secure Boot)")
        snapshots = {p: p.collect() for p in active_plugins}

        log.info("PHASE 6: Comparing baseline vs post-SB snapshot")
        all_failures = self._compare_sb_state(baseline_sb, snapshot_sb)
        for plugin in active_plugins:
            all_failures.extend(
                plugin.compare(baselines[plugin], snapshots[plugin])
            )

        if all_failures:
            self.fail(
                "PHASE 6: IO comparison failures:\n  "
                + "\n  ".join(all_failures)
            )
        log.info(
            "PHASE 6: All IO parameters match baseline; "
            "all lockdown restrictions confirmed"
        )


# ======================================================================= #
#  Runnable Test Classes                                                   #
# ======================================================================= #

class NVMeSecureBootIO(OpTestSecureBootIO):
    '''
    Validates NVMe device integrity across the Secure Boot enable transition.

    Run with:
      op-test --run testcases.OpTestSecureBootIO.NVMeSecureBootIO
    '''

    def setUp(self):
        super().setUp()
        raw_filter = getattr(
            OpTestConfiguration.conf.args, 'nvme_devices', None
        )
        device_filter = set()
        if raw_filter:
            for token in raw_filter.split(','):
                token = token.strip().replace('/dev/', '')
                if token:
                    device_filter.add(token)
        self.io_plugins = [NVMePlugin(self.c, device_filter)]

    def runTest(self):
        super().runTest()


def SecureBootIO_suite():
    '''Return a TestSuite containing all OpTestSecureBootIO test classes.'''
    s = unittest.TestSuite()
    s.addTest(NVMeSecureBootIO())
    return s
