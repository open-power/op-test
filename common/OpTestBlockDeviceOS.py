#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestBlockDeviceOS.py $
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
OpTestBlockDeviceOS: OS-side block device data collectors and normalization
helpers.
'''

import json
import re

import OpTestLogger

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Normalization helpers
# ──────────────────────────────────────────────────────────────────────────────

def normalize_wwpn(raw):
    '''Normalize a WWPN/WWID string to lowercase 16-char hex without "0x".'''
    return raw.strip().lower().lstrip('0x').zfill(16)


def normalize_lun(raw_hex):
    '''Parse a raw LUN hex string into an integer.'''
    return int(raw_hex, 16)


def normalize_nsid(raw, base=16):
    '''Parse a namespace ID string into an integer.'''
    return int(raw.strip(), base)


def normalize_nvme_version(ver_uint32):
    '''Decode NVMe id-ctrl "ver" uint32 field to "major.minor" string.'''
    return '%d.%d' % ((ver_uint32 >> 16) & 0xffff, (ver_uint32 >> 8) & 0xff)


def _run(conn, cmd, timeout=60):
    '''Run a command via SSH and return non-empty output lines.'''
    try:
        out = conn.run_command(cmd, timeout=timeout)
        return [line for line in out if line.strip()]
    except Exception as e:
        log.warning('OS command failed: %r — %s', cmd, e)
        return []


def _run_json(conn, cmd, timeout=60):
    '''Run a command via SSH and parse stdout as JSON.'''
    lines = _run(conn, cmd, timeout=timeout)
    if not lines:
        return None
    try:
        return json.loads('\n'.join(lines))
    except json.JSONDecodeError as e:
        log.warning('JSON parse failed for %r: %s', cmd, e)
        return None


def _get_disks_for_host(conn, host_str):
    '''Return sorted list of /dev/sdX block device paths attached to host.'''
    m = re.match(r'host(\d+)', host_str)
    if not m:
        return []
    host_num = m.group(1)
    disks = []
    for line in _run(conn, 'lsscsi', timeout=20):
        if line.startswith('[%s:' % host_num):
            for tok in reversed(line.split()):
                if tok.startswith('/dev/sd'):
                    disks.append(tok.strip())
                    break
    return sorted(disks)


def _reverse_resolve_host_by_vio_addr(conn, vio_addr, subsystem_class):
    '''Resolve hostN name by matching vio_addr in sysfs symlinks.'''
    cmd = (
        'for h in /sys/class/%s/host*/; do '
        'target=$(readlink -f "$h/device" 2>/dev/null); '
        'echo "$h $target"; '
        'done' % subsystem_class
    )
    for line in _run(conn, cmd, timeout=20):
        parts = line.strip().split()
        if len(parts) >= 2 and vio_addr in parts[1]:
            m = re.search(r'(host\d+)', parts[0])
            if m:
                return m.group(1)
    return ''


def slot_to_pci_bdfs(conn, slot_drc):
    '''Map physical slot DRC to PCI BDF strings using lsslot -c pci.'''
    lines = _run(conn, 'lsslot -c pci', timeout=30)
    base = re.sub(r'-[TR]\d+$', '', slot_drc.strip())
    bdfs = []
    matched_current_slot = False
    for line in lines:
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split()
        if not parts:
            continue
        first_token = parts[0].strip()
        if first_token.startswith('U') and '-' in first_token:
            matched_current_slot = (
                first_token == slot_drc.strip()
                or first_token == base
                or first_token.startswith(base)
            )
            tokens_to_check = parts[1:]
        else:
            tokens_to_check = parts

        if matched_current_slot:
            for tok in tokens_to_check:
                if re.match(
                        r'^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}'
                        r'\.[0-9a-fA-F]$', tok):
                    bdfs.append(tok.strip())

    log.debug('slot_to_pci_bdfs: slot=%s → %s', slot_drc, bdfs)
    return bdfs


def slot_to_vio_addr(conn, slot_drc):
    '''Map virtual slot DRC to VIO bus address using lsslot -c slot.'''
    lines = _run(conn, 'lsslot -c slot', timeout=30)
    base = re.sub(r'-T\d+$', '', slot_drc.strip())
    for line in lines:
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split()
        if not parts:
            continue
        lsslot_drc = parts[0].strip()
        if lsslot_drc in (base, slot_drc.strip()):
            for tok in parts[1:]:
                if re.match(r'^[0-9a-fA-F]{8}$', tok):
                    return tok.strip()
    log.debug('slot_to_vio_addr: slot=%s → not found', slot_drc)
    return ''


# ──────────────────────────────────────────────────────────────────────────────
# NVMeOSCollector
# ──────────────────────────────────────────────────────────────────────────────

class NVMeOSCollector:
    '''Collect NVMe device information from OS for given slot DRC.'''

    def __init__(self, conn):
        self.conn = conn

    def collect(self, slot_drc):
        '''Collect NVMe controllers and namespaces for slot DRC.'''
        bdfs = slot_to_pci_bdfs(self.conn, slot_drc)
        if not bdfs:
            log.warning('NVMeOSCollector: no PCI BDFs for slot %s', slot_drc)
            return {}

        ctrl_map = self._build_controller_map()
        result = {}
        for bdf in bdfs:
            ctrl = ctrl_map.get(bdf)
            if not ctrl:
                log.warning('NVMeOSCollector: no controller for BDF %s', bdf)
                continue
            info = self._collect_controller(ctrl)
            if info:
                result[info['serial']] = info

        log.info('NVMeOSCollector: collected %d controller(s) for slot %s',
                 len(result), slot_drc)
        return result

    def _build_controller_map(self):
        '''Build dict of {pci_bdf: controller_name} from nvme list-subsys.'''
        data = _run_json(self.conn, 'nvme list-subsys -o json', timeout=30)
        if not data:
            return {}

        subsystems = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if 'Subsystems' in item and isinstance(
                            item['Subsystems'], list):
                        subsystems.extend(item['Subsystems'])
                    else:
                        subsystems.append(item)
        elif isinstance(data, dict):
            subsystems = data.get('Subsystems', [])

        ctrl_map = {}
        for sub in subsystems:
            if not isinstance(sub, dict):
                continue
            controllers = sub.get('Controllers', sub.get('Paths', []))
            if not isinstance(controllers, list):
                controllers = [controllers]
            for ctrl in controllers:
                name = ctrl.get('Name', '')
                address = ctrl.get('Address', '')
                if name and address:
                    ctrl_map[address.strip()] = name.strip()
        return ctrl_map

    def _collect_controller(self, ctrl):
        '''Collect all fields for a single nvmeX controller.'''
        dev = '/dev/' + ctrl
        nsids = self._get_nsids(dev)
        return {
            'controller': ctrl,
            'model': self._read_sysfs(ctrl, 'model'),
            'serial': self._read_sysfs(ctrl, 'serial'),
            'fw_rev': self._read_sysfs(ctrl, 'firmware_rev'),
            'nvme_version': self._decode_version(dev),
            'namespace_count': len(nsids),
            'nsid_set': set(nsids),
        }

    def _read_sysfs(self, ctrl, attr):
        '''Read and strip sysfs attribute for given controller.'''
        lines = _run(self.conn,
                     'cat /sys/class/nvme/%s/%s' % (ctrl, attr), timeout=10)
        return lines[0].strip() if lines else ''

    def _decode_version(self, dev):
        '''Decode NVMe version from id-ctrl JSON "ver" field.'''
        data = _run_json(self.conn,
                         'nvme id-ctrl %s -o json' % dev, timeout=20)
        if data and 'ver' in data:
            return normalize_nvme_version(int(data['ver']))
        return ''

    def _get_nsids(self, dev):
        '''Return list of int NSIDs from nvme list-ns.'''
        lines = _run(self.conn, 'nvme list-ns %s' % dev, timeout=20)
        nsids = []
        for line in lines:
            m = re.search(r'0x([0-9a-fA-F]+)', line)
            if m:
                nsids.append(int(m.group(1), 16))
        return nsids


class FCOSCollector:
    '''Collect physical Fibre Channel adapter information from OS.'''

    def __init__(self, conn):
        self.conn = conn

    def collect(self, slot_drc):
        '''Collect FC port info for slot DRC.'''
        bdfs = slot_to_pci_bdfs(self.conn, slot_drc)
        if not bdfs:
            log.warning('FCOSCollector: no PCI BDFs for slot %s', slot_drc)
            return {}

        result = {}
        for bdf in bdfs:
            host = self._pci_to_fc_host(bdf)
            if not host:
                log.warning('FCOSCollector: no fc_host for BDF %s', bdf)
                continue
            info = self._collect_host(host, collect_targets=False)
            if info:
                result[info['local_wwpn']] = info

        log.info('FCOSCollector: collected %d FC port(s) for slot %s',
                 len(result), slot_drc)
        return result

    def _pci_to_fc_host(self, bdf):
        '''Find fc_host name for given PCI BDF.'''
        lines = _run(self.conn,
                     'ls /sys/bus/pci/devices/%s/ 2>/dev/null' % bdf,
                     timeout=10)
        for entry in lines:
            if re.match(r'^host\d+$', entry.strip()):
                return entry.strip()
        return ''

    def _collect_host(self, host, collect_targets=True):
        '''Collect port info and disk list for one fc_host.'''
        base = '/sys/class/fc_host/%s' % host
        wwpn_lines = _run(self.conn, 'cat %s/port_name' % base, timeout=10)
        local_wwpn = normalize_wwpn(wwpn_lines[0]) if wwpn_lines else ''

        state_lines = _run(self.conn, 'cat %s/port_state' % base, timeout=10)
        port_state = state_lines[0].strip() if state_lines else ''

        disks = _get_disks_for_host(self.conn, host)
        targets = self._collect_targets(host) if collect_targets else {}

        return {
            'host': host,
            'port_state': port_state,
            'local_wwpn': local_wwpn,
            'disk_count': len(disks),
            'disks': disks,
            'targets': targets,
        }

    def _collect_targets(self, host):
        '''Build {target_wwpn: set(lun_int)} for visible rports on host.'''
        targets = {}
        find_cmd = (
            'find /sys/class/fc_host/%s/device -maxdepth 4 '
            '-name "rport-*" 2>/dev/null' % host
        )
        rport_dirs = _run(self.conn, find_cmd, timeout=20)
        for rport_path in rport_dirs:
            rport_path = rport_path.strip()
            if not rport_path:
                continue
            rport_name = rport_path.split('/')[-1]
            wwpn_lines = _run(
                self.conn,
                'cat %s/fc_remote_ports/%s/port_name 2>/dev/null'
                % (rport_path, rport_name),
                timeout=10,
            )
            if not wwpn_lines:
                wwpn_lines = _run(
                    self.conn,
                    'cat /sys/class/fc_remote_ports/%s/port_name 2>/dev/null'
                    % rport_name,
                    timeout=10,
                )
            if not wwpn_lines:
                wwpn_lines = _run(
                    self.conn,
                    'cat %s/port_name 2>/dev/null' % rport_path,
                    timeout=10,
                )
            if not wwpn_lines:
                continue
            target_wwpn = normalize_wwpn(wwpn_lines[0])
            luns = self._collect_luns_for_rport(rport_path)
            if target_wwpn in targets:
                targets[target_wwpn].update(luns)
            else:
                targets[target_wwpn] = set(luns)
        return targets

    def _collect_luns_for_rport(self, rport_path):
        '''Return list of int LUN values visible through rport.'''
        luns = []
        find_cmd = (
            'find %s -maxdepth 4 -name "lun" 2>/dev/null | '
            'xargs -I{} cat {} 2>/dev/null' % rport_path
        )
        lines = _run(self.conn, find_cmd, timeout=20)
        for line in lines:
            line = line.strip()
            if re.match(r'^0x[0-9a-fA-F]+$', line):
                luns.append(int(line, 16))
            elif re.match(r'^\d+$', line):
                luns.append(int(line))
        return luns


class FCNVMeOSCollector:
    '''Collect FC NVMe over Fabric namespace information from OS.'''

    def __init__(self, conn):
        self.conn = conn

    def collect(self, slot_drc):
        '''Collect FC NVMe namespaces for slot DRC.'''
        bdfs = slot_to_pci_bdfs(self.conn, slot_drc)
        if not bdfs:
            log.warning('FCNVMeOSCollector: no PCI BDFs for slot %s', slot_drc)
            return {}

        nvme_ctrl_map = self._build_nvme_ctrl_map()
        fc_collector = FCOSCollector(self.conn)
        result = {}

        for bdf in bdfs:
            host = fc_collector._pci_to_fc_host(bdf)
            if not host:
                continue
            fc_info = fc_collector._collect_host(host)
            local_wwpn = fc_info.get('local_wwpn', '')

            target_nsids = {}
            for target_wwpn in fc_info.get('targets', {}):
                nsids = self._nsids_for_target(nvme_ctrl_map, bdf, target_wwpn)
                if nsids is not None:
                    target_nsids[target_wwpn] = nsids

            result[local_wwpn] = {
                'host': host,
                'local_wwpn': local_wwpn,
                'targets': target_nsids,
            }

        log.info('FCNVMeOSCollector: collected %d port(s) for slot %s',
                 len(result), slot_drc)
        return result

    def _build_nvme_ctrl_map(self):
        '''Build {pci_bdf: [ctrl_name, ...]} from nvme list-subsys.'''
        data = _run_json(self.conn, 'nvme list-subsys -o json', timeout=30)
        if not data:
            return {}
        if isinstance(data, dict):
            subsystems = data.get('Subsystems', [])
        elif isinstance(data, list):
            subsystems = data
        else:
            return {}

        ctrl_map = {}
        for sub in subsystems:
            controllers = sub.get('Controllers', sub.get('Paths', []))
            if not isinstance(controllers, list):
                controllers = [controllers]
            for ctrl in controllers:
                name = ctrl.get('Name', '')
                address = ctrl.get('Address', '')
                if name and address:
                    ctrl_map.setdefault(
                        address.strip(), []).append(name.strip())
        return ctrl_map

    def _nsids_for_target(self, ctrl_map, bdf, target_wwpn):
        '''Return NSID set for controllers at bdf connected to target_wwpn.'''
        ctrls = ctrl_map.get(bdf, [])
        if not ctrls:
            return None
        nsid_set = set()
        for ctrl in ctrls:
            dev = '/dev/' + ctrl
            lines = _run(self.conn, 'nvme list-ns %s' % dev, timeout=20)
            for line in lines:
                m = re.search(r'0x([0-9a-fA-F]+)', line)
                if m:
                    nsid_set.add(int(m.group(1), 16))
        return nsid_set if nsid_set else None


class VSCSIOSCollector:
    '''Collect virtual SCSI adapter and disk information from OS.'''

    def __init__(self, conn):
        self.conn = conn

    def collect(self, slot_drc):
        '''Collect vSCSI adapter and attached disks for slot DRC.'''
        vio_addr = slot_to_vio_addr(self.conn, slot_drc)
        if not vio_addr:
            log.warning('VSCSIOSCollector: vio addr not found for slot %s',
                        slot_drc)
            return {}

        scsi_host = _reverse_resolve_host_by_vio_addr(
            self.conn, vio_addr, 'scsi_host')
        if not scsi_host:
            log.warning('VSCSIOSCollector: no scsi_host for vio_addr %s',
                        vio_addr)
            return {}

        disks = _get_disks_for_host(self.conn, scsi_host)
        info = {
            'slot_drc': slot_drc,
            'vio_addr': vio_addr,
            'scsi_host': scsi_host,
            'disk_count': len(disks),
            'disks': disks,
        }
        log.info('VSCSIOSCollector: slot=%s vio=%s host=%s disks=%s',
                 slot_drc, vio_addr, scsi_host, disks)
        return {vio_addr: info}


class VFCOSCollector:
    '''Collect virtual FC adapter and attached disk information from OS.'''

    def __init__(self, conn):
        self.conn = conn

    def collect(self, slot_drc):
        '''Collect vFC adapter and attached disks for slot DRC.'''
        vio_addr = slot_to_vio_addr(self.conn, slot_drc)
        if not vio_addr:
            log.warning('VFCOSCollector: vio addr not found for slot %s',
                        slot_drc)
            return {}

        fc_host = self._vio_addr_to_fc_host(vio_addr)
        if not fc_host:
            log.warning('VFCOSCollector: no fc_host for vio_addr %s',
                        vio_addr)
            return {}

        base = '/sys/class/fc_host/%s' % fc_host
        wwpn_lines = _run(self.conn, 'cat %s/port_name' % base, timeout=10)
        local_wwpn = normalize_wwpn(wwpn_lines[0]) if wwpn_lines else ''

        state_lines = _run(self.conn, 'cat %s/port_state' % base, timeout=10)
        port_state = state_lines[0].strip() if state_lines else ''

        disks = _get_disks_for_host(self.conn, fc_host)

        info = {
            'slot_drc': slot_drc,
            'vio_addr': vio_addr,
            'fc_host': fc_host,
            'local_wwpn': local_wwpn,
            'port_state': port_state,
            'disk_count': len(disks),
            'disks': disks,
        }
        log.info('VFCOSCollector: slot=%s vio=%s host=%s wwpn=%s disks=%d',
                 slot_drc, vio_addr, fc_host, local_wwpn, len(disks))
        return {vio_addr: info}

    def _vio_addr_to_fc_host(self, vio_addr):
        '''Find fc_host name for virtual FC adapter via VIO bus sysfs.'''
        lines = _run(self.conn,
                     'ls /sys/bus/vio/devices/%s/ 2>/dev/null' % vio_addr,
                     timeout=10)
        for entry in lines:
            if re.match(r'^host\d+$', entry.strip()):
                return entry.strip()
        return _reverse_resolve_host_by_vio_addr(
            self.conn, vio_addr, 'fc_host')
