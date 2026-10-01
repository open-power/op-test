#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestSMS.py $
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
OpTestSMS: SMS TUI navigation engine for POWER firmware IO device capture.
'''

import re
import time
import pexpect
from dataclasses import dataclass, field
from typing import List

import OpTestLogger
from common.OpTestError import OpTestError
from common.OpTestUtil import collect_pexpect_screen

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

class SMSConst:
    '''SMS menu indices, screen title strings, and timeouts.'''
    MAIN_IO_INFO = '3'
    IO_SAN = '1'
    IO_NVME = '3'
    IO_VSCSI = '4'
    SAN_DEVICES = '2'
    NVME_LIST = '2'
    FABRIC_FCP = '1'
    FABRIC_FCNVME = '2'
    NS_INFO = '1'

    T_BOOT_OPTIONS = 'Select Boot Options'
    T_IO_INFO = 'I/O Device Information'
    T_SAN_MENU = 'SAN Devices Menu'
    T_FABRIC = 'Select Fabric'
    T_NVME_INFO = 'NVMe Device Information'
    T_SELECT_ADAPTER = 'Select Media Adapter'
    T_NVME_DETAIL = 'NVMe Adapter Information'
    T_SELECT_NS = 'Select Namespace'
    T_SELECT_DEVICE = 'Select Attached Device'

    NO_NVME_NS = 'No NVMe namespaces defined'
    NO_SAN_DEV = 'No SAN devices present'
    PLEASE_WAIT = 'PLEASE WAIT'
    PRESS_ANY_KEY = 'Press any key to continue'
    LINK_DOWN = 'Link down'
    CANNOT_INIT = 'Cannot Init Link'
    INVALID_ENTRY = 'Invalid entry'
    PAGINATION = 'N = Next page'

    NAV_MAIN = 'M'
    NAV_BACK = '\x1b'
    NAV_EXIT = 'X'
    NAV_NEXT_PAGE = 'N'

    T_MENU = 60
    T_PLEASE_WAIT = 90
    T_SCREEN_QUIET = 3
    T_BOOT_MENU = 300


class SMSRegex:
    '''Regex patterns for parsing SMS screens.'''
    NVME_ADAPTER = re.compile(
        r'^\s*(\d+)\.\s{1,4}(U[A-Za-z0-9._-]+)\s{2,}(.+?)\s*$')
    SAN_ADAPTER = re.compile(
        r'^\s*(\d+)\.\s{1,4}(U[A-Za-z0-9._-]+)\s{2,}(/\S+)\s*$')
    NVME_FIELD = re.compile(
        r'^[ \t]+([A-Za-z][A-Za-z0-9 -]+?)\s+\.+\s+(.+?)\s*$')
    NVME_NS = re.compile(
        r'^\s*([0-9a-fA-F]+)\.\s{1,4}(U[A-Za-z0-9._-]+-L[0-9a-fA-F]+)'
        r'\s{2,}(\d+)\s+GB\s+Namespace(.*?)\s*$')
    NS_HEADER = re.compile(r'Namespace\s+(\d+)\s+of\s+(\d+)')
    FCP_DEVICE = re.compile(
        r'^\s*(\d+)\.\s{1,4}([0-9a-fA-F]{16}),([0-9a-fA-F]+)\s+(.+?)\s*$')
    FC_PATHNAME = re.compile(r'Pathname:\s*(\S+)')
    FC_WWPN = re.compile(r'WorldWidePortName:\s*([0-9a-fA-F]+)')
    FCNVME_NS = re.compile(
        r'^\s*(\d+)\.\s{1,4}(U[A-Za-z0-9._-]+-W([0-9a-fA-F]+)-L0-L'
        r'([0-9a-fA-F]+))\s{2,}(\d+)\s+GB\s+Namespace(.*?)\s*$')
    HOST_NQN = re.compile(r'Host NQN:\s*(nqn\.\S+)')
    VSCSI_DEVICE = re.compile(
        r'^\s*(\d+)\.\s{1,4}([0-9a-fA-F]{16})\s+-\s+(\d+)\s+GB\s+(.+?)\s*$')
    VSCSI_NULL = re.compile(
        r'^\s*\d+\.\s+0\s+-\s+No device information available')


@dataclass
class SMSNVMeNamespace:
    ns_drc: str
    nsid_hex: str
    size_gb: int
    bootable: bool


@dataclass
class SMSNVMeAdapter:
    index: str
    drc: str
    description: str
    model: str
    serial: str
    nvme_version: str
    fw_rev: str
    driver_level: str
    namespaces: List[SMSNVMeNamespace] = field(default_factory=list)


@dataclass
class SMSFCPDevice:
    target_wwpn: str
    lun_hex: str
    size_desc: str


@dataclass
class SMSFCAdapter:
    index: str
    drc: str
    of_path: str
    is_virtual: bool
    local_wwpn: str = ''
    devices: List[SMSFCPDevice] = field(default_factory=list)
    no_devices: bool = False


@dataclass
class SMSFCNVMeNamespace:
    ns_drc: str
    target_wwpn: str
    nsid_hex: str
    size_gb: int


@dataclass
class SMSFCNVMeAdapter:
    index: str
    drc: str
    of_path: str
    is_virtual: bool
    host_nqn: str
    namespaces: List[SMSFCNVMeNamespace] = field(default_factory=list)
    no_devices: bool = False
    link_down: bool = False


@dataclass
class SMSVSCSIDevice:
    index: str
    wwid: str
    size_gb: int
    bootable: bool


@dataclass
class SMSVSCSIAdapter:
    index: str
    drc: str
    of_path: str
    vio_addr: str
    devices: List[SMSVSCSIDevice] = field(default_factory=list)


@dataclass
class SMSVFCDevice:
    target_wwpn: str
    lun_hex: str
    size_desc: str


@dataclass
class SMSVFCAdapter:
    index: str
    drc: str
    of_path: str
    vio_addr: str
    local_wwpn: str = ''
    devices: List[SMSVFCDevice] = field(default_factory=list)
    no_devices: bool = False


@dataclass
class SMSSlotResult:
    slot_drc: str
    nvme: List[SMSNVMeAdapter] = field(default_factory=list)
    fcp: List[SMSFCAdapter] = field(default_factory=list)
    fcnvme: List[SMSFCNVMeAdapter] = field(default_factory=list)
    vscsi: List[SMSVSCSIAdapter] = field(default_factory=list)
    vfc: List[SMSVFCAdapter] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class SMSSlotResolver:
    '''Match user-supplied base DRC against an SMS adapter list.'''

    def __init__(self, base_drc):
        self.base = base_drc.strip()

    def resolve(self, adapters):
        '''Resolve matching adapters by exact match or prefix.'''
        exact = [a for a in adapters if a.drc.strip() == self.base]
        return exact if exact else [
            a for a in adapters if a.drc.strip().startswith(self.base)
        ]

    def matches(self, adapter):
        '''Return True if adapter.drc matches base DRC.'''
        drc = adapter.drc.strip()
        return drc == self.base or drc.startswith(self.base)


# ──────────────────────────────────────────────────────────────────────────────
# SMSNavigator
# ──────────────────────────────────────────────────────────────────────────────

class SMSNavigator:
    '''PTY navigation engine for the POWER firmware SMS TUI.'''

    def __init__(self, pty):
        self.pty = pty
        self.C = SMSConst
        self.R = SMSRegex

    def _drain_overlays(self):
        '''Consume pending "Invalid entry!" overlays from pexpect buffer.'''
        for _ in range(5):
            idx = self.pty.expect([self.C.INVALID_ENTRY, pexpect.TIMEOUT],
                                  timeout=2)
            if idx == 0:
                log.debug('_drain_overlays: dismissing overlay')
                self.pty.send('\r')
                time.sleep(0.5)
            else:
                break

    def _sms_send(self, key, confirm_pattern, timeout=None):
        '''Send menu key, retry automatically on "Invalid entry!" overlays.'''
        if timeout is None:
            timeout = self.C.T_MENU
        patterns = [
            confirm_pattern, self.C.INVALID_ENTRY,
            pexpect.TIMEOUT, pexpect.EOF
        ]
        for attempt in range(10):
            log.debug('_sms_send: sending %r (attempt %d)', key, attempt + 1)
            self.pty.sendline(key)
            idx = self.pty.expect(patterns, timeout=timeout)
            if idx == 0:
                return idx, (self.pty.before or '') + (self.pty.after or '')
            if idx == 1:
                log.debug(
                    "_sms_send: 'Invalid entry!' — draining and retrying")
                self.pty.send('\r')
                time.sleep(1)
                self._drain_overlays()
                continue
            raise OpTestError(
                "SMS did not respond to %r within %ss. Got: %r"
                % (key, timeout, self.pty.before))
        raise OpTestError(
            "SMS kept showing 'Invalid entry!' after 10 attempts sending %r"
            % key)

    def _capture_screen(self):
        '''Capture current SMS screen text.'''
        return collect_pexpect_screen(self.pty, timeout=self.C.T_SCREEN_QUIET)

    def _collect_all_pages(self, parse_fn, screen_text,
                           next_page_confirm=None):
        '''Parse screen and collect pages if pagination is present.'''
        if next_page_confirm is None:
            next_page_confirm = self.C.T_SELECT_ADAPTER
        results = parse_fn(screen_text)
        while self.C.PAGINATION in screen_text:
            log.debug('_collect_all_pages: next page detected')
            self._sms_send(self.C.NAV_NEXT_PAGE, next_page_confirm)
            screen_text = self._capture_screen()
            results.extend(parse_fn(screen_text))
        return results

    def navigate_to_main_menu(self):
        '''Bring SMS session to main menu.'''
        log.info('Navigating to SMS main menu (timeout=%ss)',
                 self.C.T_BOOT_MENU)
        self._drain_overlays()
        self.pty.send('\r')
        time.sleep(1)
        for attempt in range(self.C.T_BOOT_MENU // 3):
            try:
                self._sms_send(
                    self.C.NAV_MAIN,
                    confirm_pattern=r'5\s*\.\s*Select Boot Options',
                    timeout=5,
                )
                log.info('SMS main menu confirmed (attempt %d)', attempt + 1)
                return
            except OpTestError:
                log.debug(
                    'Main menu not confirmed yet (attempt %d), nudging',
                    attempt + 1)
                self.pty.send('\r')
                time.sleep(1)
        raise OpTestError(
            'SMS main menu did not appear within %s seconds.'
            % self.C.T_BOOT_MENU)

    def navigate_to_io_info(self):
        '''From main menu: send '3' → I/O Device Information.'''
        log.info('Navigating to I/O Device Information')
        self._sms_send(self.C.MAIN_IO_INFO, self.C.T_IO_INFO)

    def exit_sms(self):
        '''Exit SMS (send X).'''
        log.info('Exiting SMS')
        self.pty.sendline(self.C.NAV_EXIT)

    def collect_nvme_adapters(self):
        '''Navigate to NVMe adapter list and return all entries.'''
        log.info('Collecting NVMe adapter list')
        self._sms_send(self.C.IO_NVME, self.C.T_NVME_INFO)
        self._sms_send(self.C.NVME_LIST, self.C.T_SELECT_ADAPTER)
        screen = self._capture_screen()

        def _parse(text):
            entries = []
            for line in text.splitlines():
                m = self.R.NVME_ADAPTER.match(line)
                if m:
                    entries.append(SMSNVMeAdapter(
                        index=m.group(1), drc=m.group(2).strip(),
                        description=m.group(3).strip(),
                        model='', serial='', nvme_version='',
                        fw_rev='', driver_level='',
                    ))
            return entries

        adapters = self._collect_all_pages(_parse, screen)
        log.info('Found %d NVMe adapter(s)', len(adapters))
        return adapters

    def collect_nvme_detail(self, adapter):
        '''Navigate into NVMe adapter and populate detail fields.'''
        log.info('Collecting NVMe detail for adapter index %s drc=%s',
                 adapter.index, adapter.drc)
        self._sms_send(adapter.index, self.C.T_NVME_DETAIL)
        screen = self._capture_screen()

        field_map = {
            'Model Number': 'model',
            'Serial Number': 'serial',
            'NVM-e Version': 'nvme_version',
            'Firmware Revision': 'fw_rev',
            'Firmware Device Driver Level': 'driver_level',
        }
        for line in screen.splitlines():
            m = self.R.NVME_FIELD.match(line)
            if m:
                attr = field_map.get(m.group(1).strip())
                if attr:
                    setattr(adapter, attr, m.group(2).strip())

        log.info('NVMe detail: model=%r serial=%r fw=%r ver=%r',
                 adapter.model, adapter.serial,
                 adapter.fw_rev, adapter.nvme_version)

        self._sms_send(self.C.NS_INFO,
                       r'%s|%s' % (self.C.T_SELECT_NS, self.C.NO_NVME_NS),
                       timeout=self.C.T_MENU)
        ns_screen = self._capture_screen()

        if self.C.NO_NVME_NS in ns_screen:
            log.info('No NVMe namespaces defined for drc=%s', adapter.drc)
            self.pty.sendline(self.C.NAV_MAIN)
            time.sleep(1)
        else:
            adapter.namespaces = self._parse_nvme_namespaces(ns_screen)
            log.info('Found %d namespace(s) for drc=%s',
                     len(adapter.namespaces), adapter.drc)
            self.pty.sendline(self.C.NAV_BACK)
            time.sleep(0.5)

        return adapter

    def _parse_nvme_namespaces(self, screen_text):
        '''Parse Select Namespace screen into SMSNVMeNamespace objects.'''
        def _parse(text):
            entries = []
            for line in text.splitlines():
                m = self.R.NVME_NS.match(line)
                if m:
                    ns_drc = m.group(2).strip()
                    entries.append(SMSNVMeNamespace(
                        ns_drc=ns_drc,
                        nsid_hex=ns_drc.rsplit('-L', 1)[-1],
                        size_gb=int(m.group(3)),
                        bootable='- bootable' in m.group(4).lower(),
                    ))
            return entries

        return self._collect_all_pages(
            _parse, screen_text, next_page_confirm=self.C.T_SELECT_NS)

    def _navigate_to_san_adapter_list(self, fabric_key):
        '''Navigate from I/O Device Info to SAN adapter list for fabric_key.'''
        log.info('Navigating to SAN adapter list (fabric=%s)', fabric_key)
        _, after = self._sms_send(
            self.C.IO_SAN, r'%s|%s' % (self.C.T_SAN_MENU, self.C.T_FABRIC))
        if self.C.T_SAN_MENU in after:
            self._sms_send(self.C.SAN_DEVICES, self.C.T_FABRIC)

        self._sms_send(
            fabric_key,
            r'%s|%s' % (self.C.PLEASE_WAIT, self.C.T_SELECT_ADAPTER),
            timeout=self.C.T_PLEASE_WAIT,
        )
        screen = self._capture_screen()
        if self.C.PLEASE_WAIT in screen:
            idx = self.pty.expect(
                [self.C.T_SELECT_ADAPTER, pexpect.TIMEOUT],
                timeout=self.C.T_PLEASE_WAIT)
            if idx != 0:
                raise OpTestError(
                    'SAN adapter list did not appear within %ss'
                    % self.C.T_PLEASE_WAIT)
            screen = self._capture_screen()

        host_nqn = ''
        m = self.R.HOST_NQN.search(screen)
        if m:
            host_nqn = m.group(1).strip()
            log.info('FC NVMe Host NQN: %s', host_nqn)
        return host_nqn, screen

    def _parse_san_adapters(self, screen_text, fabric_key, host_nqn=''):
        '''Parse SMS SAN adapter list into SMSFCAdapter / SMSFCNVMeAdapter.'''
        def _parse(text):
            entries = []
            for line in text.splitlines():
                m = self.R.SAN_ADAPTER.match(line)
                if m:
                    of_path = m.group(3).strip()
                    is_virtual = '/vdevice/vfc-client@' in of_path
                    if fabric_key == self.C.FABRIC_FCP:
                        entries.append(SMSFCAdapter(
                            index=m.group(1), drc=m.group(2).strip(),
                            of_path=of_path, is_virtual=is_virtual,
                        ))
                    else:
                        entries.append(SMSFCNVMeAdapter(
                            index=m.group(1), drc=m.group(2).strip(),
                            of_path=of_path, is_virtual=is_virtual,
                            host_nqn=host_nqn,
                        ))
            return entries

        return self._collect_all_pages(_parse, screen_text)

    def _collect_common_fcp_vfc_devices(self, adapter, dev_type_cls,
                                        category_name):
        '''Collect attached FCP / VFC devices and parse local WWPN.'''
        log.info('Collecting %s devices for index=%s drc=%s',
                 category_name, adapter.index, adapter.drc)
        self._sms_send(
            adapter.index,
            r'%s|%s' % (self.C.T_SELECT_DEVICE, self.C.NO_SAN_DEV),
            timeout=self.C.T_PLEASE_WAIT,
        )
        screen = self._capture_screen()
        if self.C.NO_SAN_DEV in screen:
            log.info('No SAN devices for %s drc=%s',
                     category_name, adapter.drc)
            adapter.no_devices = True
            self.pty.send(' ')
            time.sleep(0.5)
            return

        m_wwpn = self.R.FC_WWPN.search(screen)
        if m_wwpn:
            adapter.local_wwpn = m_wwpn.group(1).lower()

        def _parse(text):
            devices = []
            for line in text.splitlines():
                m = self.R.FCP_DEVICE.match(line)
                if m:
                    devices.append(dev_type_cls(
                        target_wwpn=m.group(2).lower(),
                        lun_hex=m.group(3).lower(),
                        size_desc=m.group(4).strip(),
                    ))
            return devices

        adapter.devices = self._collect_all_pages(_parse, screen)
        log.info('Found %d %s device(s) for drc=%s',
                 len(adapter.devices), category_name, adapter.drc)
        self.pty.sendline(self.C.NAV_BACK)
        time.sleep(0.5)

    def collect_fcp_adapters(self, slot_filter=None):
        '''Collect FCP adapter list and devices for physical HBAs.'''
        _, screen = self._navigate_to_san_adapter_list(self.C.FABRIC_FCP)
        adapters = self._parse_san_adapters(screen, self.C.FABRIC_FCP)
        log.info('Found %d FCP adapter(s) (%d physical FC, %d vFC)',
                 len(adapters),
                 sum(1 for a in adapters if not a.is_virtual),
                 sum(1 for a in adapters if a.is_virtual))
        for adapter in adapters:
            if adapter.is_virtual or (
                    slot_filter is not None and
                    not slot_filter.matches(adapter)):
                log.info('FCP: drc=%s skipping navigation (virtual/filtered)',
                         adapter.drc)
                adapter.no_devices = True
                continue
            self._collect_common_fcp_vfc_devices(adapter, SMSFCPDevice, 'FCP')
        return adapters

    def collect_fcnvme_adapters(self, slot_filter=None):
        '''Collect FC NVMe over Fabric adapter list and namespaces.'''
        host_nqn, screen = self._navigate_to_san_adapter_list(
            self.C.FABRIC_FCNVME)
        adapters = self._parse_san_adapters(
            screen, self.C.FABRIC_FCNVME, host_nqn)
        log.info('Found %d FC NVMe adapter(s)', len(adapters))
        for adapter in adapters:
            if slot_filter is not None and not slot_filter.matches(adapter):
                log.info('FC NVMe: drc=%s not in slot filter -- skipping',
                         adapter.drc)
                adapter.no_devices = True
                continue
            self._collect_fcnvme_namespaces(adapter)
        return adapters

    def _collect_fcnvme_namespaces(self, adapter):
        '''Populate namespaces for an FC NVMe adapter.'''
        log.info('Collecting FC NVMe namespaces for index=%s drc=%s',
                 adapter.index, adapter.drc)
        self._sms_send(
            adapter.index,
            r'%s|%s|%s' % (self.C.T_SELECT_NS, self.C.NO_NVME_NS,
                           self.C.LINK_DOWN),
            timeout=self.C.T_PLEASE_WAIT,
        )
        screen = self._capture_screen()

        if self.C.LINK_DOWN in screen or self.C.CANNOT_INIT in screen:
            log.warning('FC NVMe drc=%s: link down — skipping', adapter.drc)
            adapter.link_down = True
            self.pty.send(' ')
            time.sleep(0.5)
            return

        if self.C.NO_NVME_NS in screen:
            log.info('No FC NVMe namespaces for drc=%s', adapter.drc)
            adapter.no_devices = True
            self.pty.send(' ')
            time.sleep(0.5)
            return

        def _parse(text):
            entries = []
            for line in text.splitlines():
                m = self.R.FCNVME_NS.match(line)
                if m:
                    entries.append(SMSFCNVMeNamespace(
                        ns_drc=m.group(2).strip(),
                        target_wwpn=m.group(3).lower(),
                        nsid_hex=m.group(4).lower(),
                        size_gb=int(m.group(5)),
                    ))
            return entries

        adapter.namespaces = self._collect_all_pages(
            _parse, screen, next_page_confirm=self.C.T_SELECT_NS)
        log.info('Found %d FC NVMe namespace(s) for drc=%s',
                 len(adapter.namespaces), adapter.drc)
        self.pty.sendline(self.C.NAV_BACK)
        time.sleep(0.5)

    def collect_vscsi_adapters(self, slot_filter=None):
        '''Navigate to vSCSI adapter list and collect attached devices.'''
        log.info('Collecting vSCSI adapter list')
        self._sms_send(self.C.IO_VSCSI, self.C.T_SELECT_ADAPTER)
        screen = self._capture_screen()

        def _parse(text):
            entries = []
            for line in text.splitlines():
                m = self.R.SAN_ADAPTER.match(line)
                if m:
                    of_path = m.group(3).strip()
                    vio_addr = of_path.split('@')[-1] if '@' in of_path else ''
                    entries.append(SMSVSCSIAdapter(
                        index=m.group(1), drc=m.group(2).strip(),
                        of_path=of_path, vio_addr=vio_addr,
                    ))
            return entries

        adapters = self._collect_all_pages(_parse, screen)
        log.info('Found %d vSCSI adapter(s)', len(adapters))

        for adapter in adapters:
            if slot_filter is not None and not slot_filter.matches(adapter):
                log.info('vSCSI: drc=%s not in slot filter -- skipping',
                         adapter.drc)
                continue
            self._collect_vscsi_devices(adapter)
        return adapters

    def _collect_vscsi_devices(self, adapter):
        '''Navigate into vSCSI adapter and populate devices list.'''
        log.info('Collecting vSCSI devices for index=%s drc=%s',
                 adapter.index, adapter.drc)
        self._sms_send(adapter.index, self.C.T_SELECT_DEVICE)
        screen = self._capture_screen()

        def _parse(text):
            devices = []
            for line in text.splitlines():
                if self.R.VSCSI_NULL.match(line):
                    continue
                m = self.R.VSCSI_DEVICE.match(line)
                if m:
                    devices.append(SMSVSCSIDevice(
                        index=m.group(1),
                        wwid=m.group(2).lower(),
                        size_gb=int(m.group(3)),
                        bootable='bootable' in m.group(4).lower(),
                    ))
            return devices

        adapter.devices = self._collect_all_pages(_parse, screen)
        log.info('Found %d vSCSI device(s) for drc=%s',
                 len(adapter.devices), adapter.drc)
        self.pty.sendline(self.C.NAV_BACK)
        time.sleep(0.5)

    def collect_vfc_adapters(self, slot_filter=None):
        '''Collect virtual FC adapters and attached devices.'''
        log.info('Collecting VFC adapter list (via FCP SAN path)')
        _, screen = self._navigate_to_san_adapter_list(self.C.FABRIC_FCP)
        fcp_adapters = self._parse_san_adapters(screen, self.C.FABRIC_FCP)
        vfc_raw = [a for a in fcp_adapters if a.is_virtual]
        log.info('Found %d VFC adapter(s) out of %d FCP entries',
                 len(vfc_raw), len(fcp_adapters))

        for fa in fcp_adapters:
            if not fa.is_virtual:
                fa.no_devices = True

        adapters = []
        for fa in vfc_raw:
            vio_addr = fa.of_path.split('@')[-1] if '@' in fa.of_path else ''
            va = SMSVFCAdapter(
                index=fa.index, drc=fa.drc,
                of_path=fa.of_path, vio_addr=vio_addr,
            )
            if slot_filter is not None and not slot_filter.matches(va):
                log.info('VFC: drc=%s not in slot filter -- skipping', va.drc)
                va.no_devices = True
                adapters.append(va)
                continue
            self._collect_common_fcp_vfc_devices(va, SMSVFCDevice, 'VFC')
            adapters.append(va)

        return adapters
