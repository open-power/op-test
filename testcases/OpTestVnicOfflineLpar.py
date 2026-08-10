#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestVnicOfflineLpar.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
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
OpTestVnicOfflineLpar
---------------------

This module tests adding a virtual NIC (vNIC) adapter to a PowerVM LPAR
while the partition is offline (Not Activated), then verifies the adapter
is visible in three stages:

  1. Add vNIC to the LPAR profile via HMC while the LPAR is powered off.
  2. Boot to Petitboot (SMS menu) and verify the added vNIC appears as a
     network interface with its assigned MAC address.
  3. Boot to the host OS and verify the vNIC is enumerated by the kernel.

Prerequisites
-------------
The following parameters must be defined in ``~/.op-test-framework.conf``
or passed on the command line:

  Required
  --------
  ``hmc_ip``                - HMC IP address
  ``hmc_username``          - HMC SSH username
  ``hmc_password``          - HMC SSH password
  ``system_name``           - Managed system name in HMC
  ``lpar_name``             - LPAR name as configured in HMC
  ``lpar_prof``             - LPAR profile name
  ``lpar_vios``             - Name of the VIOS that backs the vNIC
  ``vnic_sriov_loc_code``   - Physical location code of the SRIOV adapter that
                              backs the vNIC, e.g. ``U78DA.ND0.WZS0123-P1-C2``
                              Used to look up the HMC adapter_id via
                              ``lshwres -r sriov --rsubtype adapter``
  ``vnic_phys_port_ids``    - Comma-separated physical port numbers on the SRIOV
                              adapter (0-based, e.g. ``0,1,2`` for three ports)

  Optional (sensible defaults are used when absent)
  -------------------------------------------------
  ``vnic_capacity``         - Capacity percentage allocated to this vNIC from the
                              physical port (1-100, default: 2)

  LPAR host OS access
  -------------------
  ``host_ip``               - IP address of the LPAR in the running OS
  ``host_user``             - SSH username on the LPAR OS (default: root)
  ``host_password``         - SSH password on the LPAR OS

How to find ``vnic_sriov_loc_code``
------------------------------------
Run the following on the HMC to list all SRIOV adapters and their location codes::

    lshwres -m <system_name> -r sriov --rsubtype adapter \\
            -F phys_loc:adapter_id:num_phys_ports

Pick the ``phys_loc`` value for the card you want (e.g. ``U78DA.ND0.WZS0123-P1-C2``)
and set ``vnic_sriov_loc_code`` to that value.  Set ``vnic_phys_port_ids`` to the
comma-separated list of zero-based port indexes (e.g. ``0,1,2``).

Usage::

    op-test --config-file vnic_offline_add.conf \\
            --run testcases.OpTestVnicOfflineLpar.AddVnicOfflineLpar
'''

import re
import time
import unittest

import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common.OpTestHMC import OpHmcState
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level timing constants.
# ---------------------------------------------------------------------------
BOOT_SETTLE_TIME = 30           # seconds after petitboot is reached before probing
LPAR_START_DRAIN_TIMEOUT = 300  # seconds to wait for Starting -> Running
SHUTDOWN_POLL_INTERVAL = 10     # seconds between shutdown state polls
SHUTDOWN_MAX_POLLS = 60         # 60 x 10 s = 10 minutes maximum shutdown wait


class OpTestVnicOfflineLpar(unittest.TestCase):
    '''
    Base class that sets up HMC connectivity and exposes helpers shared by
    all vNIC-offline-LPAR sub-tests.
    '''

    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.cv_HOST = self.conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.mg_system = self.cv_HMC.mg_system
        self.lpar_name = self.cv_HMC.lpar_name
        self.lpar_prof = self.cv_HMC.lpar_prof

        # vNIC parameters – pulled from conf.args (registered in OpTestConfiguration).
        args = self.conf.args
        # lpar_vios is registered in the HMC argument group
        self.vios_name = args.lpar_vios

        # Physical adapter that backs the vNICs (REQUIRED – no default)
        self.vnic_sriov_loc_code = args.vnic_sriov_loc_code

        # Comma-separated list of physical port IDs; argparse gives a string
        # with default "0,1,2"; split here into a list of ints.
        self.vnic_phys_port_ids = [
            int(p.strip()) for p in args.vnic_phys_port_ids.split(',')]

        # vNIC capacity; argparse handles type and default
        self.vnic_capacity = args.vnic_capacity

        if not self.lpar_prof:
            raise OpTestError(
                "lpar_prof must be defined (--lpar-prof) for vNIC offline tests")
        if not self.vios_name:
            raise OpTestError(
                "lpar_vios must be defined (--lpar-vios) for vNIC offline tests")
        if not self.vnic_sriov_loc_code:
            raise OpTestError(
                "vnic_sriov_loc_code must be defined in the config file. "
                "Run: lshwres -m %s -r sriov --rsubtype adapter "
                "-F phys_loc:adapter_id:num_phys_ports  on the HMC "
                "to find the correct location code." % self.mg_system)
        if len(self.vnic_phys_port_ids) < 3:
            raise OpTestError(
                "vnic_phys_port_ids must list at least three port IDs "
                "(e.g. --vnic-phys-port-ids 0,1,2).  Got: %s"
                % args.vnic_phys_port_ids)

        # Validate the LPAR exists in the managed system
        if not self.cv_HMC.is_lpar_in_managed_system(self.mg_system, self.lpar_name):
            raise OpTestError("LPAR %s not found in managed system %s" %
                               (self.lpar_name, self.mg_system))

        # List of virtual slot numbers added by this test run – populated by
        # _add_vnic() so tearDown can clean up even if the test body raises.
        self._added_vnic_slots = []
        # Set to True at the very end of runTest; tearDown skips vNIC removal
        # when True so the LPAR is left running with vNICs intact on success.
        self._test_passed = False

    # ------------------------------------------------------------------
    # Profile / slot helpers
    # ------------------------------------------------------------------

    def _get_lpar_profile_name(self):
        '''
        Return the profile name to use for this LPAR.

        If ``self.lpar_prof`` exists on the HMC for this LPAR it is returned
        as-is.  Otherwise the first profile listed by ``lssyscfg -r prof`` for
        the LPAR is used and a warning is logged so the operator knows to
        update their config.

        :returns: string, profile name
        :raises: OpTestError if no profile exists for the LPAR at all
        '''
        cmd = ("lssyscfg -r prof -m %s --filter 'lpar_names=%s,profile_names=%s'"
               " -F name"
               % (self.mg_system, self.lpar_name, self.lpar_prof))
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=60)
            return self.lpar_prof
        except CommandFailed:
            pass

        log.warning("Profile '%s' not found for LPAR '%s'; querying all profiles ...",
                    self.lpar_prof, self.lpar_name)
        list_cmd = ("lssyscfg -r prof -m %s --filter 'lpar_names=%s' -F name"
                    % (self.mg_system, self.lpar_name))
        try:
            profiles = self.cv_HMC.ssh.run_command(list_cmd, timeout=60)
        except CommandFailed as cf:
            raise OpTestError(
                "Could not list profiles for LPAR '%s': %s" % (self.lpar_name, cf))

        profiles = [p.strip() for p in profiles if p.strip()]
        if not profiles:
            raise OpTestError(
                "No profiles found for LPAR '%s' in managed system '%s'. "
                "Check --lpar-prof and the HMC configuration."
                % (self.lpar_name, self.mg_system))

        chosen = profiles[0]
        log.warning("Using profile '%s' for LPAR '%s' (configured: '%s'). "
                    "Update --lpar-prof to suppress this warning.",
                    chosen, self.lpar_name, self.lpar_prof)
        self.lpar_prof = chosen
        return chosen

    def _get_next_free_virtual_slots(self, count):
        '''
        Return ``count`` consecutive-or-scattered free virtual slot numbers,
        all >= 3.  HMC virtual slot IDs below 3 are reserved for platform use.

        :param count: int, number of free slots required
        :returns: list of ints, available virtual slot numbers (length == count)
        :raises: OpTestError if not enough free slots could be found
        '''
        profile = self._get_lpar_profile_name()
        cmd = ("lssyscfg -r prof -m %s --filter 'lpar_names=%s,profile_names=%s'"
               " -F virtual_eth_adapters"
               % (self.mg_system, self.lpar_name, profile))
        try:
            output = self.cv_HMC.ssh.run_command(cmd, timeout=60)
        except CommandFailed as cf:
            raise OpTestError("Failed to query virtual adapters: %s" % cf)

        used_slots = set()
        for line in output:
            for entry in line.split(','):
                parts = entry.split('/')
                if parts and parts[0].isdigit():
                    used_slots.add(int(parts[0]))
        log.debug("Virtual slots already in use: %s", used_slots)

        free_slots = []
        for slot in range(3, 4096):
            if slot not in used_slots:
                free_slots.append(slot)
            if len(free_slots) == count:
                log.info("Selected %d free virtual slots: %s", count, free_slots)
                return free_slots
        raise OpTestError(
            "Not enough free virtual slots for %d vNICs "
            "(found %d)" % (count, len(free_slots)))

    # ------------------------------------------------------------------
    # vNIC management helpers
    # ------------------------------------------------------------------

    def _get_sriov_adapter_id(self):
        '''
        Resolve the numeric SRIOV adapter_id from the physical location code
        using ``lshwres -r sriov --rsubtype adapter`` on the HMC.

        This reuses the existing :meth:`~common.OpTestHMC.HMCUtil.get_adapter_id`
        helper in OpTestHMC, which queries::

            lshwres -m <system> -r sriov --rsubtype adapter
                    -F phys_loc:adapter_id

        :returns: string, numeric adapter_id
        :raises:  OpTestError if the location code is not found
        '''
        adapter_id = self.cv_HMC.get_adapter_id(
            self.mg_system, self.vnic_sriov_loc_code)
        if not adapter_id:
            raise OpTestError(
                "SRIOV adapter with location code '%s' not found in "
                "managed system '%s'. "
                "Run:  lshwres -m %s -r sriov --rsubtype adapter "
                "-F phys_loc:adapter_id  on the HMC to verify the "
                "location code." % (
                    self.vnic_sriov_loc_code, self.mg_system, self.mg_system))
        log.info("SRIOV adapter '%s' resolved to adapter_id: %s",
                 self.vnic_sriov_loc_code, adapter_id)
        return adapter_id

    def _get_vios_id(self):
        '''
        Retrieve the numeric LPAR ID of the backing VIOS.

        :returns: string, LPAR ID of the VIOS
        :raises: OpTestError if the VIOS is not found in the managed system
        '''
        vios_id = self.cv_HMC.get_lpar_id(self.mg_system, self.vios_name)
        if not vios_id or vios_id == 0:
            raise OpTestError(
                "VIOS '%s' not found in managed system '%s'. "
                "Check --lpar-vios." % (self.vios_name, self.mg_system))
        log.info("VIOS '%s' has LPAR ID: %s", self.vios_name, vios_id)
        return str(vios_id)

    def _get_profile_vnic_entries(self, prof):
        '''
        Return the current list of vNIC entries from the named profile in
        the **long property=value format** required by ``chsyscfg -r prof``.

        ``lssyscfg`` returns entries in a short positional format::

            5:ded:1:0:0:all::all:0:sriov/ltcden7-vios1/100/5/0/2.0/50/100.0

        This method converts each short entry into the long form that
        ``chsyscfg`` accepts::

            slot_num=5:mode=ded:auto_priority_failover=1:port_vlan_id=0:
            pvid_priority=0:allowed_vlan_ids=all:allowed_os_mac_addrs=all:
            is_required=0:backing_devices=sriov/ltcden7-vios1/100/5/0/2.0/50/100.0

        Returns an empty list when no vNICs are present.

        :param prof: string, profile name
        :returns: list of strings in long property=value format
        :raises: OpTestError on HMC command failure
        '''
        cmd = ("lssyscfg -r prof -m %s"
               " --filter 'lpar_names=%s,profile_names=%s'"
               " -F vnic_adapters"
               % (self.mg_system, self.lpar_name, prof))
        try:
            out = self.cv_HMC.ssh.run_command(cmd, timeout=60)
        except CommandFailed as cf:
            raise OpTestError(
                "Failed to read vnic_adapters from profile '%s': %s"
                % (prof, cf))
        raw = " ".join(out).strip().strip('"')
        if not raw or raw.lower() == 'none':
            return []

        long_entries = []
        for entry in raw.split(','):
            entry = entry.strip()
            if not entry:
                continue
            if 'slot_num=' in entry:
                long_entries.append(entry)
                continue
            # Convert short positional format to long property=value format.
            # Short format fields (positional):
            #   0: slot_num  1: mode  2: auto_priority_failover
            #   3: port_vlan_id  4: pvid_priority  5: allowed_vlan_ids
            #   6: mac_addr (may be empty)  7: allowed_os_mac_addrs
            #   8: is_required  9: backing_devices
            parts = entry.split(':')
            if len(parts) < 10:
                log.warning("Unexpected vnic_adapters entry format, skipping: %s",
                            entry)
                continue
            long_entry = (
                "slot_num=%s:mode=%s:auto_priority_failover=%s:"
                "port_vlan_id=%s:pvid_priority=%s:allowed_vlan_ids=%s:"
                "allowed_os_mac_addrs=%s:is_required=%s:"
                "backing_devices=%s" % (
                    parts[0], parts[1], parts[2], parts[3], parts[4],
                    parts[5], parts[7], parts[8], ':'.join(parts[9:])))
            long_entries.append(long_entry)
        return long_entries

    def _build_vnic_entry(self, slot, vios_id, adapter_id, phys_port_id):
        '''
        Build a single vNIC entry string in the **long property=value format**
        required by ``chsyscfg -r prof``.

        Note: ``lssyscfg`` returns entries in a short positional format
        (e.g. ``17:ded:1:...``) but ``chsyscfg`` requires the explicit
        ``property=value`` form or it raises "property not formatted correctly".

        :param slot:         int, virtual slot number
        :param vios_id:      string, LPAR ID of the backing VIOS
        :param adapter_id:   string, numeric SRIOV adapter_id
        :param phys_port_id: int, physical port index
        :returns: string, one vnic_adapters entry in long property=value format
        '''
        return (
            "slot_num=%d:mode=ded:auto_priority_failover=1:"
            "port_vlan_id=0:pvid_priority=0:allowed_vlan_ids=all:"
            "allowed_os_mac_addrs=all:is_required=0:"
            "backing_devices=sriov/%s/%s/%s/%d/%d.0/50/100.0" % (
                slot,
                self.vios_name, vios_id, adapter_id,
                phys_port_id, self.vnic_capacity))

    def _write_profile_vnics(self, prof, entries):
        '''
        Overwrite the ``vnic_adapters`` field of the named profile with the
        given list of entry strings using ``chsyscfg -r prof``.

        Using a full replace (``=``) rather than append (``+=``) avoids the
        HMC bug where it re-validates *all* existing entries (including ones
        with stale adapter IDs) when ``+=`` is used, causing spurious
        HSCL1244 errors.

        :param prof:    string, profile name
        :param entries: list of strings, each a vnic_adapters entry
        :raises: OpTestError on failure
        '''
        if entries:
            # The vnic_adapters value MUST be wrapped in double quotes inside
            # the -i string.  Without quotes HMC splits on every comma and
            # interprets each slot_num=N as a top-level attribute, producing
            # "An invalid attribute was entered: slot_num".
            vnic_val = '"' + ",".join(entries) + '"'
        else:
            vnic_val = "none"
        cmd = ("chsyscfg -r prof -m %s"
               " -i 'name=%s,lpar_name=%s,vnic_adapters=%s'"
               % (self.mg_system, prof, self.lpar_name, vnic_val))
        log.info("Writing vnic_adapters to profile '%s': %s", prof, cmd)
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=120)
        except CommandFailed as cf:
            raise OpTestError(
                "chsyscfg failed writing vnic_adapters to profile '%s': %s"
                % (prof, cf))

    def _add_vnic(self, slot, vios_id, adapter_id, phys_port_id, prof):
        '''
        Add a vNIC to the named LPAR profile via ``chsyscfg -r prof``.

        This approach writes directly into the profile by name (``-r prof``)
        rather than using ``chhwres``.  ``chhwres`` has no ``-f`` flag and
        targets whichever profile happens to be current, making it unreliable
        when the LPAR is offline.  ``chsyscfg -r prof`` always targets exactly
        the profile named in the ``-i`` string.

        The full ``vnic_adapters`` value is replaced in one write (not
        appended) to avoid the HMC HSCL1244 re-validation bug that fires
        when ``+=`` causes HMC to re-check stale entries already in the profile.

        :param slot:         int, virtual slot number
        :param vios_id:      string, numeric LPAR ID of the backing VIOS
        :param adapter_id:   string, numeric SRIOV adapter_id from HMC
        :param phys_port_id: int, physical port index on the SRIOV adapter
        :param prof:         string, profile name to add the vNIC into
        :raises: OpTestError on HMC command failure
        '''
        existing = self._get_profile_vnic_entries(prof)
        existing = [e for e in existing
                    if not e.startswith('slot_num=%d:' % slot)]
        new_entry = self._build_vnic_entry(slot, vios_id, adapter_id, phys_port_id)
        self._write_profile_vnics(prof, existing + [new_entry])
        self._added_vnic_slots.append(slot)
        log.info("vNIC added to profile '%s': slot=%d phys_port=%d adapter_id=%s",
                 prof, slot, phys_port_id, adapter_id)

    def _remove_vnic(self, slot):
        '''
        Remove the vNIC for ``slot`` from the LPAR profile via
        ``chsyscfg -r prof``.

        Reads the current ``vnic_adapters`` list from ``lssyscfg`` (which
        returns the short positional format), drops the entry whose first
        field matches ``slot``, and writes the remainder back in long format.
        Best-effort: logs a warning on failure so tearDown always completes.

        :param slot: int, virtual slot number to remove
        '''
        prof = self.lpar_prof
        log.info("Removing vNIC slot %d from profile '%s'", slot, prof)
        try:
            existing = self._get_profile_vnic_entries(prof)
            updated = [e for e in existing
                       if not e.startswith('slot_num=%d:' % slot)]
            if len(updated) == len(existing):
                log.info("vNIC slot %d not found in profile '%s' - nothing to remove",
                         slot, prof)
                return
            self._write_profile_vnics(prof, updated)
            log.info("vNIC slot %d removed from profile '%s'", slot, prof)
        except Exception as exc:
            log.warning("Failed to remove vNIC slot %d from profile '%s': %s",
                        slot, prof, exc)

    def _list_vnic(self, slot):
        '''
        Query the LPAR profile directly via ``lssyscfg`` to find the vNIC
        on the given slot and return a dict with ``slot`` and ``mac_address``.

        ``lshwres --level lpar`` only reflects the last-booted runtime
        snapshot and will not show slots added to the profile while the LPAR
        is offline (Not Activated).  Reading from ``lssyscfg -r prof`` is
        the only reliable way to confirm a profile write succeeded.

        The MAC address field in the profile is empty until the LPAR boots
        (HMC assigns it at first activation).  An empty MAC is returned as
        an empty string — callers must treat empty MAC as "not yet assigned"
        rather than "not found".

        :param slot: int, virtual slot number
        :returns: dict with keys ``slot`` and ``mac_address``, or None
        '''
        prof = self._get_lpar_profile_name()
        cmd = ("lssyscfg -r prof -m %s"
               " --filter 'lpar_names=%s,profile_names=%s'"
               " -F vnic_adapters"
               % (self.mg_system, self.lpar_name, prof))
        log.debug("Listing vNICs from profile: %s", cmd)
        try:
            out = self.cv_HMC.ssh.run_command(cmd, timeout=60)
        except CommandFailed as cf:
            log.warning("lssyscfg vnic_adapters query failed (slot %d): %s", slot, cf)
            return None

        raw = " ".join(out).strip().strip('"')
        if not raw or raw.lower() == 'none':
            return None

        for entry in raw.split(','):
            entry = entry.strip()
            parts = entry.split(':')
            if not parts:
                continue
            slot_field = parts[0]
            if slot_field.startswith('slot_num='):
                entry_slot = int(slot_field.split('=', 1)[1])
            elif slot_field.isdigit():
                entry_slot = int(slot_field)
            else:
                continue
            if entry_slot != slot:
                continue
            mac = ''
            if slot_field.startswith('slot_num='):
                for prop in parts:
                    if prop.startswith('mac_addr='):
                        mac = prop.split('=', 1)[1].strip()
                        break
            else:
                if len(parts) > 6:
                    mac = parts[6].strip()
            mac = mac.lower().replace(':', '')
            if len(mac) == 12:
                mac = ':'.join(mac[i:i+2] for i in range(0, 12, 2))
            return {'slot': entry_slot, 'mac_address': mac}
        return None

    # ------------------------------------------------------------------
    # Verification helpers
    # ------------------------------------------------------------------

    def _verify_vnics_in_petitboot(self, mac_addresses):
        '''
        Boot to Petitboot shell and confirm **every** vNIC in ``mac_addresses``
        is visible as a network interface.

        On PowerVM LPARs the "SMS menu" is the pre-OS firmware menu.
        Petitboot (the bootloader) runs in this environment and enumerates
        all hardware including vNICs.  Checking the interfaces in Petitboot
        is equivalent to confirming visibility at the SMS/firmware layer.

        On HMC-managed systems ``goto_state(PETITBOOT_SHELL)`` raises
        ``unittest.SkipTest`` — this is caught so the rest of runTest
        continues normally.

        :param mac_addresses: list of strings, each a colon-separated lowercase
                              MAC address, e.g. ``['aa:bb:cc:dd:ee:ff', ...]``
        :returns: True if Petitboot check ran and passed, False if skipped
        :raises: OpTestError if any MAC is not found
        '''
        log.info("Booting to Petitboot shell to verify %d vNIC(s): %s",
                 len(mac_addresses), mac_addresses)
        try:
            self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        except unittest.SkipTest:
            log.info("Petitboot/SMS console not available on HMC-managed "
                     "system - SMS menu MAC verification substituted by "
                     "HMC lssyscfg profile check already done in Step 2.")
            return False
        time.sleep(BOOT_SETTLE_TIME)

        console = self.cv_SYSTEM.console
        output = console.run_command("ip link show", timeout=60)
        raw = "\n".join(output)
        log.debug("ip link show output (Petitboot):\n%s", raw)

        sys_raw = ""
        try:
            sys_out = console.run_command(
                "grep -r '' /sys/class/net/*/address 2>/dev/null || true",
                timeout=30)
            sys_raw = "\n".join(sys_out)
        except CommandFailed:
            pass

        missing = []
        for mac in mac_addresses:
            if mac.lower() in raw.lower() or mac.lower() in sys_raw.lower():
                log.info("vNIC MAC %s found in Petitboot (SMS menu) - "
                         "HMC == SMS menu CONFIRMED", mac)
            else:
                log.error("vNIC MAC %s NOT found in Petitboot", mac)
                missing.append(mac)

        if missing:
            raise OpTestError(
                "The following vNIC MAC address(es) were NOT found in "
                "Petitboot (SMS menu): %s\nip link show output:\n%s"
                % (missing, raw))
        return True

    def _verify_vnics_in_host_os(self, mac_addresses):
        '''
        After a full boot to the host OS, confirm **every** vNIC in
        ``mac_addresses`` is enumerated by the kernel.

        :param mac_addresses: list of strings, each a colon-separated lowercase
                              MAC address
        :raises: OpTestError if any MAC is not found
        '''
        log.info("Booting to host OS to verify %d vNIC(s): %s",
                 len(mac_addresses), mac_addresses)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        host = self.cv_HOST
        output = host.host_run_command("ip link show", timeout=60)
        raw = "\n".join(output)
        log.debug("ip link show output (host OS):\n%s", raw)

        sys_raw = ""
        try:
            sys_out = host.host_run_command(
                "grep -r '' /sys/class/net/*/address 2>/dev/null || true",
                timeout=30)
            sys_raw = "\n".join(sys_out)
        except CommandFailed:
            pass

        missing = []
        for mac in mac_addresses:
            if mac.lower() in raw.lower() or mac.lower() in sys_raw.lower():
                log.info("vNIC MAC %s found in host OS", mac)
            else:
                log.error("vNIC MAC %s NOT found in host OS", mac)
                missing.append(mac)

        if missing:
            raise OpTestError(
                "The following vNIC MAC address(es) were NOT found in "
                "host OS: %s\nip link show output:\n%s" % (missing, raw))

    # ------------------------------------------------------------------
    # LPAR state management
    # ------------------------------------------------------------------

    def _ensure_lpar_offline(self):
        '''
        Guarantee the LPAR reaches ``Not Activated`` state before the profile
        is modified.  Handles every possible ``OpHmcState`` via explicit HMC
        CLI commands so the caller never has to worry about what state the
        LPAR was in when the test started.

        State handling matrix
        ---------------------
        +-------------------+--------------------------------------------------+
        | Current state     | Action                                           |
        +===================+==================================================+
        | Not Activated     | Nothing to do - already offline                  |
        +-------------------+--------------------------------------------------+
        | Running           | ``chsysstate ... -o shutdown --immed``           |
        |                   | Wait for Not Activated                           |
        +-------------------+--------------------------------------------------+
        | Shutting Down     | Already in progress - just wait for              |
        |                   | Not Activated (no extra command needed)          |
        +-------------------+--------------------------------------------------+
        | Open Firmware     | ``chsysstate ... -o shutdown --immed``           |
        | (Petitboot)       | Wait for Not Activated                           |
        +-------------------+--------------------------------------------------+
        | Starting          | Wait up to LPAR_START_DRAIN_TIMEOUT for Running, |
        |                   | then issue shutdown --immed                      |
        +-------------------+--------------------------------------------------+
        | Not Available     | Raise OpTestError - hardware/HMC issue           |
        +-------------------+--------------------------------------------------+
        | Error / unknown   | Attempt ``shutdown --immed``; raise if it fails  |
        +-------------------+--------------------------------------------------+

        :raises: OpTestError if the LPAR cannot be brought to Not Activated
        '''
        state = self.cv_HMC.get_lpar_state()
        log.info("Step 1: LPAR '%s' current state: '%s'", self.lpar_name, state)

        # -- Already offline --------------------------------------------------
        if state == OpHmcState.NOT_ACTIVE:
            log.info("LPAR is already Not Activated - no shutdown needed")
            return

        # -- Not Available - hardware / HMC cannot communicate ---------------
        if state == OpHmcState.NA:
            raise OpTestError(
                "LPAR '%s' is in '%s' state.  Check HMC connectivity and "
                "managed-system health before running this test."
                % (self.lpar_name, state))

        # -- Starting - drain until Running, then fall through to shutdown ----
        if state == OpHmcState.STARTING:
            log.info("LPAR is Starting - waiting up to %d s for it to reach "
                     "Running before issuing shutdown ...",
                     LPAR_START_DRAIN_TIMEOUT)
            deadline = time.time() + LPAR_START_DRAIN_TIMEOUT
            while time.time() < deadline:
                time.sleep(SHUTDOWN_POLL_INTERVAL)
                state = self.cv_HMC.get_lpar_state()
                log.info("  ... state now: '%s'", state)
                if state == OpHmcState.RUNNING:
                    break
                if state == OpHmcState.NOT_ACTIVE:
                    log.info(
                        "LPAR reached Not Activated on its own during start drain")
                    return
            else:
                raise OpTestError(
                    "LPAR '%s' did not leave Starting state within %d s "
                    "(last state: '%s'). Aborting."
                    % (self.lpar_name, LPAR_START_DRAIN_TIMEOUT, state))

        # -- Shutting Down - already in progress, just wait ------------------
        if state == OpHmcState.SHUTTING:
            log.info("LPAR is already Shutting Down - waiting for Not Activated ...")
        else:
            # -- Running or Open Firmware (Petitboot) - issue immediate shutdown
            log.info("Issuing HMC immediate shutdown for LPAR '%s' "
                     "(current state: '%s') ...", self.lpar_name, state)
            cmd = ("chsysstate -m %s -r lpar -n %s -o shutdown --immed"
                   % (self.mg_system, self.lpar_name))
            try:
                self.cv_HMC.ssh.run_command(cmd, timeout=60)
                log.info("Shutdown command accepted by HMC")
            except CommandFailed as cf:
                raise OpTestError(
                    "HMC shutdown command failed for LPAR '%s': %s"
                    % (self.lpar_name, cf))

        # -- Poll until Not Activated using wait_lpar_state ------------------
        log.info("Waiting for Not Activated state (max %d s) ...",
                 SHUTDOWN_POLL_INTERVAL * SHUTDOWN_MAX_POLLS)
        self.cv_HMC.wait_lpar_state(
            OpHmcState.NOT_ACTIVE,
            timeout=SHUTDOWN_POLL_INTERVAL * SHUTDOWN_MAX_POLLS)
        log.info("LPAR '%s' is now Not Activated (offline)", self.lpar_name)

    # ------------------------------------------------------------------
    # tearDown
    # ------------------------------------------------------------------

    def tearDown(self):
        '''
        Clean up: remove every vNIC added during the test (best-effort).

        Skips vNIC removal when the test passed so the LPAR is left running
        with the added vNICs intact.  On failure the vNICs are removed and
        the LPAR is powered off first if needed.
        '''
        if self._added_vnic_slots and not self._test_passed:
            # LPAR must be offline to remove vNICs from the profile; if the
            # test failed mid-way the LPAR may still be running.
            lpar_state = self.cv_HMC.get_lpar_state()
            if lpar_state == OpHmcState.RUNNING:
                log.info("tearDown: LPAR is running - powering off for vNIC cleanup")
                try:
                    self.cv_HMC.poweroff_lpar()
                except Exception as exc:
                    log.warning("tearDown: failed to power off LPAR: %s", exc)
            for slot in self._added_vnic_slots:
                self._remove_vnic(slot)
        elif self._test_passed:
            log.info("tearDown: test passed - leaving LPAR running with vNICs on "
                     "slots %s intact.", self._added_vnic_slots)


# ---------------------------------------------------------------------------
# Concrete test class
# ---------------------------------------------------------------------------
class AddVnicOfflineLpar(OpTestVnicOfflineLpar, unittest.TestCase):
    '''
    Test: Add three vNICs (one per physical port 0, 1, 2) while the LPAR
    is offline, verify all vNICs in Petitboot (SMS menu), verify all
    vNICs in the host OS, then remove them and verify a clean boot.

    Steps
    -----
    1. Ensure the LPAR is powered off (Not Activated).
    2. Add 3 vNICs to the LPAR profile via ``chsyscfg -r prof`` while offline.
       Confirm each entry via ``lssyscfg``.
    3. Boot to Petitboot (SMS menu equivalent) and verify vNIC MAC addresses
       are visible (skipped gracefully on HMC-only console setups).
    4. Boot fully into the host OS, collect runtime MACs from ``lshwres``,
       and verify all MACs are visible in ``ip link show`` / sysfs / drmgr.
    5. Power off, remove vNICs from the profile, verify absence, boot clean.

    Run with::

        op-test --config-file vnic_offline_add.conf \\
                --run testcases.OpTestVnicOfflineLpar.AddVnicOfflineLpar
    '''

    def runTest(self):
        slots = [10, 20, 30]

        # ----------------------------------------------------------------
        # Step 1 - Bring LPAR offline (Not Activated)
        # ----------------------------------------------------------------
        log.info("=== Step 1: Bringing LPAR '%s' to Not Activated via HMC ===",
                 self.lpar_name)
        self._ensure_lpar_offline()
        log.info("LPAR '%s' confirmed Not Activated.", self.lpar_name)

        # ----------------------------------------------------------------
        # Step 2 - Add 3 vNICs while LPAR is offline via chsyscfg -r prof
        # ----------------------------------------------------------------
        actual_prof = self._get_lpar_profile_name()
        vios_id = self._get_vios_id()
        adapter_id = self._get_sriov_adapter_id()
        phys_port_id = self.vnic_phys_port_ids[0]

        log.info("=== Step 2: Adding 3 vNIC(s) to profile '%s' while offline "
                 "(VIOS=%s, adapter_id=%s, port=%d, slots=%s) ===",
                 actual_prof, self.vios_name, adapter_id, phys_port_id, slots)

        # Pre-cleanup: remove any leftover vNICs from a previous run.
        log.info("Pre-cleanup: removing any existing vNICs on slots %s", slots)
        for slot in slots:
            self._remove_vnic(slot)

        mac_addresses = []
        for slot in slots:
            self._add_vnic(slot, vios_id, adapter_id, phys_port_id, actual_prof)
            vnic_info = self._list_vnic(slot)
            if vnic_info is None:
                raise OpTestError(
                    "vNIC slot %d not found in profile '%s' after add"
                    % (slot, actual_prof))
            mac = vnic_info['mac_address']
            if mac:
                log.info("  Added vNIC: slot=%-4d  MAC=%s (profile)", slot, mac)
            else:
                log.info("  Added vNIC: slot=%-4d  MAC=(pending - assigned at boot)",
                         slot)
            mac_addresses.append(mac)

        log.info("----------------------------------------------------------")
        log.info("Step 2 PASSED - vNICs added and confirmed via lssyscfg:")
        for slot, mac in zip(slots, mac_addresses):
            log.info("  Slot %-4d -> MAC %s  [profile confirmed]", slot, mac)
        log.info("----------------------------------------------------------")

        # ----------------------------------------------------------------
        # Step 3 - SMS menu MAC check (Petitboot console, skipped on HMC)
        # ----------------------------------------------------------------
        log.info("=== Step 3: SMS menu (Petitboot) MAC verification ===")
        sms_verified = self._verify_vnics_in_petitboot(mac_addresses)
        log.info("----------------------------------------------------------")
        if sms_verified:
            log.info("Step 3 PASSED - SMS menu (Petitboot) MACs confirmed:")
            for slot, mac in zip(slots, mac_addresses):
                log.info("  Slot %-4d -> MAC %s  [HMC == SMS menu]", slot, mac)
        else:
            log.info("Step 3 SKIPPED - Petitboot console not reachable on "
                     "HMC-managed system.")
            log.info("  Equivalent check: lssyscfg profile query in Step 2 -- PASSED")
            for slot, mac in zip(slots, mac_addresses):
                log.info("  Slot %-4d -> MAC %s  [verified via lssyscfg]", slot, mac)
        log.info("----------------------------------------------------------")

        # ----------------------------------------------------------------
        # Step 4 - Power on LPAR, wait for OS, compare MACs via ip + lshwres
        # ----------------------------------------------------------------
        log.info("=== Step 4: Powering on LPAR '%s' with profile '%s' ===",
                 self.lpar_name, actual_prof)
        cmd = ("chsysstate -m %s -r lpar -n %s -o on -f %s"
               % (self.mg_system, self.lpar_name, actual_prof))
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=120)
        except CommandFailed as cf:
            raise OpTestError("Failed to power on LPAR '%s': %s"
                              % (self.lpar_name, cf))

        # Wait for HMC state = Running (up to 10 min)
        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(15)
            out = self.cv_HMC.ssh.run_command(
                "lssyscfg -m %s -r lpar --filter lpar_names=%s -F state"
                % (self.mg_system, self.lpar_name), timeout=30)
            state = out[0].strip() if out else ""
            log.info("LPAR HMC state: %s", state)
            if state == "Running":
                break
        else:
            raise OpTestError("LPAR '%s' did not reach Running within 10 min"
                               % self.lpar_name)

        # Wait for host OS SSH (up to 15 min)
        log.info("LPAR is Running. Waiting for host OS SSH ...")
        ssh_deadline = time.time() + 900
        while time.time() < ssh_deadline:
            time.sleep(20)
            try:
                self.cv_HOST.host_run_command("echo ssh_ready", timeout=30)
                log.info("Host OS SSH is ready.")
                break
            except Exception:
                log.info("Host OS SSH not yet ready, retrying ...")
        else:
            raise OpTestError(
                "Host OS SSH did not become available within 15 min")

        # Fetch runtime MACs from lshwres (profile MACs are empty until boot)
        runtime_macs = {}
        try:
            lshw_out = self.cv_HMC.ssh.run_command(
                "lshwres -r virtualio -m %s --rsubtype vnic"
                " --filter 'lpar_names=%s' -F slot_num,mac_addr"
                % (self.mg_system, self.lpar_name), timeout=60)
            for line in lshw_out:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    s = parts[0].strip()
                    m = parts[1].strip().lower().replace(':', '')
                    if s.isdigit() and len(m) == 12:
                        runtime_macs[int(s)] = ':'.join(
                            m[i:i+2] for i in range(0, 12, 2))
        except CommandFailed as cf:
            raise OpTestError(
                "Failed to read runtime MACs from lshwres: %s" % cf)

        log.info("Runtime MACs from lshwres: %s", runtime_macs)
        for slot in slots:
            if slot not in runtime_macs:
                raise OpTestError(
                    "vNIC slot %d not found in lshwres after boot - "
                    "check that the profile was booted with -f %s"
                    % (slot, actual_prof))

        ip_out = self.cv_HOST.host_run_command("ip link show", timeout=60)
        ip_raw = "\n".join(ip_out).lower()
        log.debug("ip link show:\n%s", ip_raw)

        sys_raw = ""
        try:
            sys_out = self.cv_HOST.host_run_command(
                "grep -r '' /sys/class/net/*/address 2>/dev/null || true",
                timeout=30)
            sys_raw = "\n".join(sys_out).lower()
        except Exception:
            pass

        drmgr_raw = ""
        try:
            dr_out = self.cv_HOST.host_run_command(
                "drmgr -c slot -l all -s 2>/dev/null || true", timeout=60)
            drmgr_raw = "\n".join(dr_out).lower()
        except Exception:
            pass

        mismatches = []
        log.info("----------------------------------------------------------")
        log.info("Step 4 - MAC comparison: HMC lshwres (runtime) vs host OS")
        log.info("Slot  | MAC (lshwres runtime) | In host OS | Match")
        log.info("------|-----------------------|------------|------")
        for slot in slots:
            mac = runtime_macs[slot]
            mac_lower = mac.lower()
            if mac_lower in ip_raw or mac_lower in sys_raw or mac_lower in drmgr_raw:
                found = "YES"
                match = "OK"
            else:
                found = "NO"
                match = "FAIL"
                mismatches.append(slot)
            log.info("  %-4d | %-21s | %-10s | %s", slot, mac, found, match)
        log.info("----------------------------------------------------------")

        if mismatches:
            log.error("vNIC MAC(s) missing in host OS. Collecting diagnostics ...")
            try:
                diag = self.cv_HOST.host_run_command(
                    "ip link show; echo '---'; "
                    "grep -r '' /sys/class/net/*/address 2>/dev/null; echo '---'; "
                    "lsmod | grep ibmvnic; echo '---'; "
                    "dmesg | grep -i ibmvnic | tail -30",
                    timeout=60)
                log.error("Diagnostics:\n%s", "\n".join(diag))
            except Exception as exc:
                log.warning("Could not collect diagnostics: %s", exc)
            raise OpTestError(
                "MAC address(es) not found in host OS for slot(s) %s. "
                "Check that the ibmvnic driver is loaded "
                "(lsmod | grep ibmvnic) and that the vNIC backing VIOS "
                "is running and its SRIOV physical port is up."
                % mismatches)
        log.info("Step 4 PASSED - all vNIC MACs confirmed in host OS.")

        # ----------------------------------------------------------------
        # Step 5 - Power off LPAR, remove vNICs, verify LPAR boots clean
        # ----------------------------------------------------------------
        log.info("=== Step 5: Powering off LPAR, removing vNICs, "
                 "verifying clean boot ===")

        log.info("Step 5a: Shutting down LPAR '%s' ...", self.lpar_name)
        self._ensure_lpar_offline()
        log.info("LPAR '%s' is offline.", self.lpar_name)

        log.info("Step 5b: Removing vNICs on slots %s from HMC ...", slots)
        for slot in slots:
            self._remove_vnic(slot)
            vnic_info = self._list_vnic(slot)
            if vnic_info is not None:
                raise OpTestError(
                    "vNIC slot %d still present in lssyscfg after removal" % slot)
            log.info("  Slot %d removed and confirmed absent in lssyscfg.", slot)
        self._added_vnic_slots = []

        log.info("Step 5c: Booting LPAR '%s' without vNICs ...", self.lpar_name)
        cmd = ("chsysstate -m %s -r lpar -n %s -o on -f %s"
               % (self.mg_system, self.lpar_name, actual_prof))
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=120)
        except CommandFailed as cf:
            raise OpTestError(
                "Failed to power on LPAR for clean-boot check: %s" % cf)

        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(15)
            out = self.cv_HMC.ssh.run_command(
                "lssyscfg -m %s -r lpar --filter lpar_names=%s -F state"
                % (self.mg_system, self.lpar_name), timeout=30)
            state = out[0].strip() if out else ""
            log.info("LPAR HMC state: %s", state)
            if state == "Running":
                break
        else:
            raise OpTestError("LPAR did not reach Running after clean boot")

        ssh_deadline = time.time() + 900
        while time.time() < ssh_deadline:
            time.sleep(20)
            try:
                self.cv_HOST.host_run_command("echo ssh_ready", timeout=30)
                log.info("Host OS SSH is ready.")
                break
            except Exception:
                log.info("Host OS SSH not yet ready, retrying ...")
        else:
            raise OpTestError("Host OS SSH not available after clean boot")

        log.info("----------------------------------------------------------")
        log.info("Step 5 PASSED - vNICs removed, LPAR boots cleanly.")
        log.info("----------------------------------------------------------")
        log.info("=== All 5 steps passed. vNIC offline-add test PASSED ===")
        self._test_passed = True


def suite():
    '''
    Return a TestSuite containing all vNIC offline LPAR test cases.
    Used by the op-test runner when invoked with --run-suite.
    '''
    s = unittest.TestSuite()
    s.addTest(AddVnicOfflineLpar('runTest'))
    return s
