#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
# Author: Vaishnavi Bhat <vaishnavi@linux.ibm.com>
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

'''
OpTestSMSNetworkAdapter
-----------------------

This test verifies that a user-specified network adapter is visible and
carries a valid MAC address in the SMS (System Management Services) menu,
then cross-references those MAC addresses against live OS network interfaces.

Steps performed:
  1. Shut down the LPAR via HMC.
  2. Activate the LPAR in its current profile with an SMS boot (Open Firmware).
  3. Connect to the LPAR console via mkvterm.
  4. Navigate to the "Available Network Ports" screen using one of two paths
     depending on what the firmware exposes:
       Path A (some firmware): Main -> 2 (Setup Remote IPL) — adapters listed
                               directly on this screen.
       Path B (default):       Main -> 3 (I/O Device Information)
                               -> 6 (Network ports).
     The test tries Path A first; if no adapter data is visible it falls back
     to Path B automatically.
  5. Verify the user-supplied adapter location code is listed.
  6. Verify that the adapter has a valid (non-zero, unicast) MAC address.
  7. For every valid MAC address found in the SMS menu, identify the matching
     network interface on the already-booted OS (via ``ip link show``) and log:
       MAC: <sms_mac>  interface on the OS with matching mac: <iface>
  8. Exit the SMS menu and power off the LPAR.

Required command-line arguments:
  --network-loc-code  Physical location code of the network adapter to verify
                      (e.g. "U780C.ND0.WZS0042-P1-C2-T1")

Supported platforms: FSP_PHYP, EBMC_PHYP (any HMC-managed LPAR)

Example invocation:
  ./op-test --bmc-type FSP_PHYP \
            --hmc-ip <HMC_IP> --hmc-username <user> --hmc-password <pass> \
            --system-name <managed_system> --lpar-name <lpar> \
            --lpar-prof <profile> \
            --network-loc-code U780C.ND0.WZS0042-P1-C2-T1 \
            --run testcases.OpTestSMSNetworkAdapter.OpTestSMSNetworkAdapter
'''

import os
import re
import time
import unittest
import pexpect

import OpTestConfiguration
import OpTestLogger
from common.OpTestError import OpTestError
from common.OpTestUtil import is_valid_mac, collect_pexpect_screen
from common.OpTestHMC import OpHmcState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Timeouts (seconds)
SMS_BOOT_TIMEOUT = 300   # time to reach SMS after LPAR activation
SMS_MENU_TIMEOUT = 60    # time between SMS menu interactions
SMS_NAV_TIMEOUT = 30    # short wait for sub-menu responses


class OpTestSMSNetworkAdapter(unittest.TestCase):
    '''
    Verify that the user-specified network adapter location code appears in the
    SMS "Setup Remote IPL -> Network ports" menu and has a valid MAC address.
    '''

    def setUp(self):
        self._OpHmcState = OpHmcState

        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.bmc_type = conf.args.bmc_type

        if self.bmc_type not in ('FSP_PHYP', 'EBMC_PHYP'):
            self.skipTest(
                "OpTestSMSNetworkAdapter requires an HMC-managed LPAR "
                "(bmc_type FSP_PHYP or EBMC_PHYP); got: %s" % self.bmc_type)

        self.cv_HMC = self.cv_SYSTEM.hmc
        self.lpar_name = conf.args.lpar_name
        self.system_name = conf.args.system_name
        self.lpar_prof = conf.args.lpar_prof
        self.logdir = conf.logdir
        self._console_active = False
        # Populated in runTest (Path A only); used by
        #_reboot_to_os_and_match_macs
        self._sms_valid_macs = []
        # Set True by _reboot_to_os_and_match_macs once the LPAR is Running;
        # prevents tearDown from issuing a redundant restart on the success path.
        self._os_ready = False

        # The adapter location code to look for in SMS
        try:
            self.network_loc_code = conf.args.network_loc_code
        except AttributeError:
            self.fail(
                "Missing required argument --network-loc-code. "
                "Provide the physical location code of the network adapter "
                "to verify (e.g. U780C.ND0.WZS0042-P1-C2-T1).")

        if not self.network_loc_code:
            self.fail("--network-loc-code must not be empty.")

        log.info("Test setup: system=%s lpar=%s profile=%s loc_code=%s",
                 self.system_name, self.lpar_name,
                 self.lpar_prof, self.network_loc_code)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _shutdown_lpar(self):
        '''Shut down the LPAR if it is not already off.'''
        state = self.cv_HMC.get_lpar_state()
        if state not in (self._OpHmcState.NOT_ACTIVE, self._OpHmcState.NA):
            log.info("Shutting down LPAR (current state: %s)", state)
            self.cv_HMC.poweroff_lpar()
        else:
            log.info("LPAR is already powered off (%s)", state)

    def _activate_lpar_to_sms(self):
        '''
        Activate the LPAR to SMS boot mode.

        Follows the same pattern as OpTestHMC.poweron_lpar():
          - If --lpar-prof is explicitly set in the conf, use it via -f.
          - Otherwise omit -f entirely so HMC activates using the
            LPAR's curr_profile (the profile it was last running with),
            falling back to default_profile if never activated.
        This ensures any runtime profile changes (e.g. added physical
        I/O slots) are always picked up without editing the conf file.
        '''
        cmd = ("chsysstate -m %s -r lpar -n %s -o on -b sms"
               % (self.system_name, self.lpar_name))
        if self.lpar_prof:
            cmd += " -f %s" % self.lpar_prof

        log.info("Activating LPAR to SMS boot mode — command: %s", cmd)
        try:
            self.cv_HMC.ssh.run_command(cmd, timeout=60)
        except Exception as e:
            raise OpTestError(
                "Failed to activate LPAR '%s' to SMS. "
                "Check profile with: lssyscfg -m %s -r lpar "
                "--filter lpar_names=%s -F curr_profile,default_profile\n"
                "Original error: %s"
                % (self.lpar_name, self.system_name, self.lpar_name, e))
        # LPAR booted to SMS lands in 'Open Firmware' state, NOT 'Running'.
        # 'Running' is only reached when the OS is fully booted.
        self.cv_HMC.wait_lpar_state(self._OpHmcState.OF, timeout=30)
        log.info("LPAR is in Open Firmware (SMS) state — ready for console")

    def _drain_overlays(self, pty):
        '''
        Consume all pending "Invalid entry!" overlays from the pexpect buffer.

        After any keypress, SMS may have queued one or more overlays in the
        terminal buffer before the underlying screen repaint arrives.  This
        method sends \\r for each overlay found (up to 5) and waits for the
        buffer to go quiet (TIMEOUT on a short poll) before returning, so the
        next send lands on a clean prompt.
        '''
        for _ in range(5):
            idx = pty.expect([r'Invalid entry', pexpect.TIMEOUT], timeout=2)
            if idx == 0:
                log.debug("_drain_overlays: dismissing overlay")
                pty.send('\r')
                time.sleep(0.5)
            else:
                break   # buffer is quiet

    def _sms_send(self, pty, key, confirm_pattern, timeout=SMS_MENU_TIMEOUT):
        '''
        Send a single key/choice to SMS and wait for confirmation, retrying
        automatically whenever "Invalid entry!" is seen.

        After dismissing an overlay, _drain_overlays() flushes the entire
        buffer before the key is re-sent, ensuring it lands on the live prompt
        rather than another queued overlay from the same flush.

        :param pty:             pexpect pty object
        :param key:             string to send (e.g. "2", "M")
        :param confirm_pattern: regex that must match to confirm the send
                                was accepted (e.g. r'Setup Remote IPL')
        :param timeout:         per-attempt wait timeout in seconds
        :returns:               (idx, before+after text) of the confirmed match
        '''
        patterns = [confirm_pattern, r'Invalid entry',
                    pexpect.TIMEOUT, pexpect.EOF]
        for attempt in range(10):
            log.debug("_sms_send: sending %r (attempt %d)", key, attempt + 1)
            pty.sendline(key)
            idx = pty.expect(patterns, timeout=timeout)
            if idx == 0:
                return idx, (pty.before or '') + (pty.after or '')
            if idx == 1:
                log.debug("_sms_send: 'Invalid entry!' — draining and retrying")
                pty.send('\r')          # dismiss this overlay
                time.sleep(1)           # let SMS repaint the underlying screen
                self._drain_overlays(pty)   # flush any further queued overlays
                continue
            # TIMEOUT or EOF
            raise OpTestError(
                "SMS did not respond to %r within %ss. Got: %r"
                % (key, timeout, pty.before))
        raise OpTestError(
            "SMS kept showing 'Invalid entry!' after 10 attempts "
            "sending %r" % key)

    def _navigate_to_main_menu(self, pty):
        '''
        Bring the SMS session to a known state: the main menu.

        Sends 'M' (return to Main Menu) up to SMS_BOOT_TIMEOUT // 3 times.
        Each send goes through _sms_send() which automatically dismisses any
        "Invalid entry!" overlays and retries, so the key only lands on a
        clean prompt.  Stops when the main-menu-only item
        "5 . Select Boot Options" is confirmed.
        '''
        log.info("Navigating to SMS main menu (timeout=%ss)", SMS_BOOT_TIMEOUT)

        # Initial nudge — repaint whatever screen is currently active so we
        # have something in the buffer to work with.
        time.sleep(1)
        pty.send('\r')
        time.sleep(2)

        for attempt in range(SMS_BOOT_TIMEOUT // 3):
            try:
                idx, _ = self._sms_send(
                    pty, 'M',
                    confirm_pattern=r'5\s*\.\s*Select Boot Options',
                    timeout=5,
                )
                log.info("SMS main menu confirmed (attempt %d)", attempt + 1)
                return
            except OpTestError:
                # _sms_send timed out — not on a known menu yet, nudge and
                # retry
                log.debug("Main menu not confirmed yet (attempt %d), nudging",
                          attempt + 1)
                pty.send('\r')
                time.sleep(1)

        raise OpTestError(
            "SMS main menu did not appear within %s seconds."
            % SMS_BOOT_TIMEOUT)

    def _send_and_wait(self, pty, choice, patterns, timeout=SMS_MENU_TIMEOUT):
        '''
        Send a menu selection and wait for one of the expected patterns,
        retrying automatically on "Invalid entry!" overlays.

        Wraps _sms_send using the first pattern in *patterns* as the
        confirmation target.  Returns the index into the original *patterns*
        list for compatibility with existing callers.

        :param pty:      pexpect pty object
        :param choice:   string to send (e.g. "2")
        :param patterns: list of regex patterns ending with TIMEOUT/EOF
                         sentinels
        :param timeout:  wait timeout in seconds
        :returns:        0 on success (first pattern matched)
        '''
        # Find the success patterns (everything before the TIMEOUT/EOF
        # sentinels)
        success_patterns = [p for p in patterns
                            if p not in (pexpect.TIMEOUT, pexpect.EOF)]
        # Build a combined OR pattern to match any of the success patterns
        combined = '|'.join('(?:%s)' % p for p in success_patterns)
        log.info("Sending SMS menu choice: %r", choice)
        idx, _ = self._sms_send(pty, choice, confirm_pattern=combined,
                                timeout=timeout)
        return idx

    @staticmethod
    def _extract_mac_addresses(text):
        '''
        Return all MAC addresses found in *text* as a list of lower-case
        colon-separated strings.  Handles both xx:xx:xx:xx:xx:xx and
        xxxxxxxxxxxx (12 hex digits without separators) formats.
        '''
        # Colon-separated format
        macs = re.findall(
            r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', text)
        # Dot-separated format (e.g. xxxx.xxxx.xxxx used by some IBM firmware)
        dot_macs = re.findall(
            r'(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}', text)
        for m in dot_macs:
            clean = m.replace('.', '')
            macs.append(':'.join(clean[i:i+2] for i in range(0, 12, 2)))
        # 12-hex-digit no-separator format
        raw_macs = re.findall(r'\b[0-9A-Fa-f]{12}\b', text)
        for m in raw_macs:
            macs.append(':'.join(m[i:i+2] for i in range(0, 12, 2)))
        return [m.lower() for m in macs]

    @staticmethod
    def _extract_port_macs(screen_text, adapter_loc_code):
        '''
        Parse the SMS "Available Network Ports" screen and return a dict of
        ``{full_port_loc_code: mac_address}`` for every port that belongs to
        the given adapter.

        The screen format is one row per port::

            N.  <description>    <adapter_loc_code>-T<n>
                                 <12hexMAC or xx:xx:...>

        ``adapter_loc_code`` may be supplied as:
          - the adapter base  (e.g. ``U78CD.001.FZHAE88-P1-C2``) — all ports
            (-T0, -T1, …) are collected.
          - a specific port   (e.g. ``U78CD.001.FZHAE88-P1-C2-T0``) — only
            that single port row is collected.

        :param screen_text:     full SMS screen as a string
        :param adapter_loc_code: the value of --network-loc-code
        :returns: dict  {port_loc_code: normalised_mac, ...}
                  Empty dict if no matching rows are found.
        '''
        # Regex for a single MAC token at the end of a row (or anywhere after
        # the loc-code).  Handles:
        #   083a8816e16c          (12 hex digits, no separator)
        #   08:3a:88:16:e1:6c     (colon-separated)
        #   0830.8816.e16c        (dot-separated, Cisco style)
        mac_token_re = re.compile(
            r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}'   # colon-sep
            r'|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}'  # dot-sep
            r'|\b[0-9A-Fa-f]{12}\b',                    # raw 12 hex
            re.IGNORECASE)

        # Match the full loc-code on a line, starting with adapter_loc_code and
        # followed by any additional loc-code segments (e.g. -C0-T0-S2, -T1).
        # Capture the entire loc-code token so that different ports of the same
        # adapter each get a unique key in port_mac_map.
        loc_re = re.compile(
            r'(' + re.escape(adapter_loc_code) + r'(?:-[A-Za-z0-9]+)*)\b',
            re.IGNORECASE)

        port_mac_map = {}
        for line in screen_text.splitlines():
            loc_match = loc_re.search(line)
            if not loc_match:
                continue
            port_loc = loc_match.group(1)

            # Extract all MAC candidates from the rest of the line (after the
            # loc-code) so we pick the MAC belonging to this port, not one
            # that might appear earlier in the line for a different reason.
            rest = line[loc_match.end():]
            mac_matches = mac_token_re.findall(rest)
            if not mac_matches:
                # Fallback: search the whole line
                mac_matches = mac_token_re.findall(line)
            if not mac_matches:
                continue

            raw = mac_matches[0]
            # Normalise to lower-case colon-separated form
            clean = raw.replace(':', '').replace('.', '')
            mac = ':'.join(clean[i:i+2] for i in range(0, 12, 2)).lower()
            port_mac_map[port_loc] = mac

        return port_mac_map

    # ------------------------------------------------------------------
    # Main test
    # ------------------------------------------------------------------

    def _navigate_to_network_ports(self, pty):
        '''
        Navigate to the "Available Network Ports" screen.

        Strategy
        --------
        1. Enter SMS option 2 (Setup Remote IPL) and read the resulting screen.
        2. If adapter / location-code / MAC data is already visible there,
           return that screen text directly (Path A — some firmware versions
           list adapters with MAC addresses right on the Remote IPL screen).
        3. Otherwise go back to the main menu and take the alternative path:
           Main Menu -> 3 (I/O Device Information) -> 6 (Network ports).
           NOTE: Path B lists adapter location codes but does NOT show MAC
           addresses; the caller must handle that case accordingly.

        :returns: tuple (screen_text: str, path: str)
                  path is 'A' (Remote IPL screen) or 'B' (I/O Device Info).
        '''
        # --- Try option 2 first (Setup Remote IPL) ---
        _, initial = self._sms_send(
            pty,
            key='2',
            confirm_pattern=(r'Setup Remote IPL|Network\s+Boot'
                             r'|Select\s+Network\s+Service'
                             r'|Network\s+Parameters'
                             r'|[Ll]ocation\s+[Cc]ode|[Aa]dapter'),
            timeout=SMS_MENU_TIMEOUT,
        )
        log.info("Entered Remote IPL sub-menu")
        time.sleep(1)

        remote_ipl_screen = (
            initial + collect_pexpect_screen(pty, timeout=SMS_NAV_TIMEOUT))

        nic_pattern = re.compile(
            r'[Ll]ocation\s+[Cc]ode|Available\s+Network|[Mm][Aa][Cc]\s+[Aa]ddress',
            re.IGNORECASE)

        if nic_pattern.search(remote_ipl_screen):
            log.info("Adapter listing is directly on the Remote IPL screen — "
                     "no further navigation needed (Path A)")
            return remote_ipl_screen, 'A'

        # --- Adapters not on the Remote IPL screen: go back to main menu ---
        self._navigate_to_main_menu(pty)

        # --- Main Menu -> 3: I/O Device Information ---
        self._sms_send(
            pty,
            key='3',
            confirm_pattern=r'I/O Device Information|Network\s+[Pp]ort',
            timeout=SMS_MENU_TIMEOUT,
        )
        time.sleep(1)

        # --- I/O Device Information -> 6: Network ports ---
        self._sms_send(
            pty,
            key='6',
            confirm_pattern=(r'Available\s+Network\s+[Pp]ort'
                             r'|[Ll]ocation\s+[Cc]ode|[Aa]dapter'),
            timeout=SMS_MENU_TIMEOUT,
        )

        screen = collect_pexpect_screen(pty, timeout=SMS_NAV_TIMEOUT)
        log.info("Available Network Ports screen reached via "
                 "I/O Device Information -> Network ports (Path B)")
        return screen, 'B'

    @staticmethod
    def _get_os_mac_map(host):
        '''
        Return a dict mapping lower-case MAC address -> interface name by
        running ``ip -o link show`` on the OS.

        The ``-o`` (oneline) flag collapses each interface entry to a single
        line, making parsing unambiguous regardless of how SSH returns the
        output.  ``altname`` entries that ``ip`` emits as separate lines in
        normal mode do not appear with ``-o``.

        Example output line::

            6: enP306p96s0f0: <BROADCAST,MULTICAST,UP> ... \\
                link/ether 08:3a:88:16:e1:6c brd ff:ff:ff:ff:ff:ff

        :param host: OpTestHost object (conf.host())
        :returns:    dict  {mac_str: iface_name, ...}
        '''
        mac_map = {}
        try:
            lines = host.host_run_command("ip -o link show", timeout=30)
        except Exception as e:
            log.warning("Could not run 'ip -o link show' on OS: %s", e)
            return mac_map

        # Each line: "<idx>: <iface>: <flags> ... link/ether <mac> ..."
        iface_re = re.compile(r'^\d+:\s+([\w@.-]+):')
        mac_re = re.compile(
            r'link/ether\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})')

        for line in lines:
            iface_match = iface_re.match(line)
            mac_match = mac_re.search(line)
            if iface_match and mac_match:
                iface = iface_match.group(1).split('@')[0]
                mac = mac_match.group(1).lower()
                mac_map[mac] = iface

        return mac_map

    def _match_sms_macs_to_os_interfaces(self, sms_macs):
        '''
        For each MAC address found in the SMS menu, look up a matching
        network interface on the OS and log the result.

        Logs one line per SMS MAC in the format::

            MAC: <sms_mac>  interface on the OS with matching mac: <iface>

        or a warning when no interface matches.

        :param sms_macs: iterable of lower-case colon-separated MAC strings
        '''
        conf = OpTestConfiguration.conf
        host = conf.host()

        log.info("Querying OS network interfaces to match SMS MAC addresses")
        os_mac_map = self._get_os_mac_map(host)

        if not os_mac_map:
            log.warning("No OS interface MAC addresses retrieved; "
                        "skipping SMS-to-OS MAC matching")
            return

        log.debug("OS interface MAC map: %s", os_mac_map)

        failed = []
        for sms_mac in sms_macs:
            if sms_mac in os_mac_map:
                iface = os_mac_map[sms_mac]
                log.info("MAC: %s  interface on the OS with matching mac: %s",
                         sms_mac, iface)
                log.info("PASS: MAC %s matched to OS interface '%s'",
                         sms_mac, iface)
            else:
                log.error("FAIL: MAC %s not found on any OS interface", sms_mac)
                failed.append(sms_mac)

        if failed:
            self.fail(
                "The following SMS MAC(s) were not found on any OS interface: %s"
                % failed)
        log.info("PASS: all %d SMS MAC(s) matched to OS interfaces",
                 len(sms_macs))

    def _reboot_to_os_and_match_macs(self):
        '''
        Exit SMS, reboot the LPAR into the OS, wait until it reaches the
        Running state, then match the SMS MAC addresses collected during the
        test against live OS network interfaces.

        This must be called only after the SMS work is complete.  It:
          1. Deactivates the mkvterm console (releasing the SMS session).
          2. Issues a hard restart via HMC and waits for Running state.
          3. Calls _match_sms_macs_to_os_interfaces() once the OS is up.

        tearDown() is left as a safety net for the failure path; on the
        success path the LPAR is already Running when tearDown executes.
        '''
        # --- Deactivate the SMS console ---
        if self._console_active:
            try:
                self.cv_HMC.console.deactivate_lpar_console()
                log.info("Console deactivated — SMS session closed")
            except Exception as e:
                log.warning("Could not deactivate console cleanly: %s", e)
            self._console_active = False

        # --- Restart LPAR and wait for OS ---
        self.cv_HMC.restart_lpar()
        log.info("Waiting for LPAR to reach Running state")
        self.cv_HMC.wait_lpar_state(self._OpHmcState.RUNNING)
        self._os_ready = True
        log.info("LPAR is Running — OS is up")

        # --- Match MACs ---
        if self._sms_valid_macs:
            self._match_sms_macs_to_os_interfaces(self._sms_valid_macs)
        else:
            log.info("No SMS MACs to match (Path B or empty list)")

    def runTest(self):
        '''
        Full end-to-end flow:
          1. Shut down LPAR.
          2. Boot LPAR to SMS.
          3. Navigate to "Available Network Ports":
             - Try Main -> 2 (Setup Remote IPL); if adapter listing is already
               visible there, use it.
             - Otherwise: Main -> 3 (I/O Device Information)
               -> 6 (Network ports).
          4. Verify adapter location code and MAC address.
          5. Deactivate console, reboot LPAR into OS, wait for Running state,
             then match SMS MAC addresses to OS network interfaces.
          tearDown() is a safety net for the failure path only.
        '''
        # --- Step 1: Shut down LPAR ---
        self._shutdown_lpar()

        # --- Step 2: Activate to SMS ---
        self._activate_lpar_to_sms()

        log.info("Connecting to LPAR console via mkvterm")
        pty = self.cv_HMC.console.connect()
        self._console_active = True

        # --- Step 3a: Wait for SMS main menu ---
        self._navigate_to_main_menu(pty)

        # --- Step 3b–c: Navigate to the network ports screen ---
        screen_output, nav_path = self._navigate_to_network_ports(pty)

        log.info("Network ports screen output (path %s):\n%s",
                 nav_path, screen_output)

        # Save raw SMS screen to logdir for post-run inspection
        screen_log = os.path.join(
            self.logdir,
            "sms_network_ports_%s.log" % self.lpar_name)
        with open(screen_log, 'w') as f:
            f.write(screen_output)
        log.info("SMS network ports screen saved to: %s", screen_log)

        # --- Step 4a: Verify location code ---
        if self.network_loc_code not in screen_output:
            self.fail(
                "Adapter location code '%s' was NOT found in the SMS "
                "'Network ports' screen.\nScreen output:\n%s"
                % (self.network_loc_code, screen_output))
        log.info("Location code '%s' found in SMS network ports listing",
                 self.network_loc_code)

        # --- Step 4b: Verify MAC address ---
        # Path B (I/O Device Information -> Network ports) lists adapter
        # location codes but does NOT display MAC addresses — firmware simply
        # does not show them on that screen.  In that case we issue a warning
        # rather than failing the test, because the adapter is confirmed
        # present; the MAC check is a best-effort verification.
        if nav_path == 'B':
            log.warning(
                "MAC address check skipped: the 'I/O Device Information -> "
                "Network ports' screen (Path B) does not display MAC "
                "addresses.  Adapter '%s' is listed — location code "
                "confirmed present.",
                self.network_loc_code)
            log.info("PASS: adapter '%s' visible in SMS (Path B, no MAC "
                     "displayed by firmware)", self.network_loc_code)
            return

        # Path A — Remote IPL screen includes MAC addresses.
        #
        # The SMS screen lists one row per port, e.g.:
        #   5.  PCIe2 4-port 1GbE  U78CD.001.FZHAE88-P1-C2-T0  083a8816e16c
        #   6.  PCIe2 4-port 1GbE  U78CD.001.FZHAE88-P1-C2-T1  083a8816e16d
        #
        # --network-loc-code may be the adapter base (e.g. -P1-C2) or a
        # specific port (e.g. -P1-C2-T0).  We collect every port row whose
        # loc-code *starts with* network_loc_code so that all ports of the
        # same physical adapter are included regardless of which form was
        # supplied.  The MAC is extracted per-line so no cross-row bleed
        # can occur.
        port_mac_map = self._extract_port_macs(
            screen_output, self.network_loc_code)

        if not port_mac_map:
            self.fail(
                "No MAC address found on the SMS 'Network ports' screen "
                "for adapter '%s'.\nScreen output:\n%s"
                % (self.network_loc_code, screen_output))

        valid_port_mac_map = {
            loc: mac for loc, mac in port_mac_map.items() if is_valid_mac(mac)
        }
        if not valid_port_mac_map:
            self.fail(
                "MAC address(es) found for adapter '%s' but none are "
                "valid (non-zero, unicast): %s\nScreen output:\n%s"
                % (self.network_loc_code, port_mac_map, screen_output))

        for port_loc, mac in sorted(valid_port_mac_map.items()):
            log.info("SMS port '%s'  MAC: %s", port_loc, mac)

        valid_macs = list(valid_port_mac_map.values())
        log.info(
            "PASS: adapter '%s' visible in SMS with %d valid port MAC(s): %s",
            self.network_loc_code, len(valid_macs), valid_macs)

        self._sms_valid_macs = valid_macs

        # --- Step 5: Reboot to OS, then match SMS MACs to OS interfaces ---
        self._reboot_to_os_and_match_macs()

    def tearDown(self):
        '''
        Safety-net cleanup.

        On the success path _reboot_to_os_and_match_macs() has already
        deactivated the console and booted the LPAR into the OS, so
        tearDown skips the restart to avoid a redundant ~90s reboot cycle.

        On the failure path (runTest raised before reaching step 5) the
        console may still be active and the LPAR may be in SMS/OF state,
        so tearDown deactivates the console and restarts into the OS.
        '''
        if self._os_ready:
            log.info("tearDown: LPAR already Running — skipping restart")
            return

        log.info("tearDown: test did not complete normally — "
                 "cleaning up console and rebooting LPAR into OS")
        if self._console_active:
            try:
                self.cv_HMC.console.deactivate_lpar_console()
            except Exception as e:
                log.warning("tearDown: failed to deactivate console: %s", e)
            self._console_active = False
        try:
            log.info("tearDown: restarting LPAR to boot into OS")
            self.cv_HMC.restart_lpar()
            log.info("tearDown: LPAR is Running")
        except Exception as e:
            log.warning(
                "tearDown: restart failed (%s); falling back to shutdown", e)
            try:
                self._shutdown_lpar()
            except Exception as e2:
                log.warning("tearDown: shutdown also failed: %s", e2)


def suite():
    s = unittest.TestSuite()
    s.addTest(OpTestSMSNetworkAdapter())
    return s
