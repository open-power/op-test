#!/usr/bin/env python4
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
# Author: Pavaman Subramaniyam <pavsubra@linux.vnet.ibm.com>
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
OpTestAdapterFirmwareUpgrade
----------------------------

Verify that a Mellanox/ConnectX adapter firmware binary is successfully
written to flash and that the new firmware version is active after reboot.

Test Steps:
  1. Check if mstflint is installed; install it automatically when missing
     (yum on RHEL, zypper on SLES).
  2. Record the pre-flash firmware version and confirm the interface link
     is UP using:
       ethtool -i <iface>       -- driver/firmware info
       ethtool <iface>          -- link state (Link detected: yes)
       mstflint -d <bus> q      -- full image and running-version detail
  3. Download the firmware binary from the URL supplied via --adapter-fw-url.
  4. Flash the binary with: mstflint -d <bus> -i <file> b
  5. Confirm the new FW version appears in mstflint flash (FW Version field)
     immediately after burn, while the running version is still the old one.
  6. Reboot the system and wait for the OS to come back up.
  7. Re-query ethtool and mstflint; confirm the running firmware version
     matches the newly flashed version recorded in Step 5, and confirm the
     interface link is UP again after reboot.

Configuration parameters (conf file [op-test] section or command line):
  --adapter-fw-url   URL of the firmware binary to download and flash.
                     (required)
  --adapter-iface    Network interface name of the target adapter,
                     e.g. enP17p1s0f0np0.  When omitted the test will
                     attempt to auto-detect the first Mellanox interface.
                     (optional)

Example invocation:
  ./op-test --config-file Adapterfirmware_io_RHEL10_2_dedicated.conf \\
  --run testcases.OpTestAdapterFirmwareUpgrade.OpTestAdapterFirmwareUpgrade
'''

import re
import sys
import time
import argparse
import unittest

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Seconds to wait for the OS to come back after reboot
REBOOT_TIMEOUT = 600

# Seconds the mstflint burn command may take
FLASH_TIMEOUT = 1800

class OpTestAdapterFirmwareUpgrade(unittest.TestCase):
    '''
    Verify that the adapter firmware is written to flash and becomes active
    on the adapter after a system reboot.
    '''

    @classmethod
    def setUpClass(cls):
        '''
        Resolve configuration and fail fast if required parameters are absent.
        '''
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.bmc_type = conf.args.bmc_type

        if cls.bmc_type not in ['FSP_PHYP', 'EBMC_PHYP']:
            raise unittest.SkipTest(
                'This test is only supported on LPAR (FSP_PHYP or EBMC_PHYP)')

        cls.hmc_user = conf.args.hmc_username
        cls.hmc_password = conf.args.hmc_password
        cls.hmc_ip = conf.args.hmc_ip
        cls.lpar_name = conf.args.lpar_name
        cls.system_name = conf.args.system_name
        cls.lpar_prof = conf.args.lpar_prof

        cls.fw_url = conf.args.adapter_fw_url
        cls.iface = conf.args.adapter_iface  # may be None; auto-detected later

        if not cls.fw_url:
            raise unittest.SkipTest(
                'Required parameter --adapter-fw-url is not set. '
                'Provide the URL of the firmware binary to flash, e.g.: '
                '--adapter-fw-url https://host/path/fw-ConnectX6Dx.bin'
            )

        log.info('Adapter firmware upgrade test configuration:')
        log.info('  bmc_type    : %s', cls.bmc_type)
        log.info('  hmc_ip      : %s', cls.hmc_ip)
        log.info('  system_name : %s', cls.system_name)
        log.info('  lpar_name   : %s', cls.lpar_name)
        log.info('  lpar_prof   : %s', cls.lpar_prof)
        log.info('  fw_url      : %s', cls.fw_url)
        log.info('  iface       : %s', cls.iface if cls.iface else '(auto-detect)')

    # ------------------------------------------------------------------
    # setUp / tearDown
    # ------------------------------------------------------------------

    def setUp(self):
        '''Ensure the system is booted to OS before each test method.'''
        self.console = self.cv_SYSTEM.console

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run(self, cmd, timeout=120):
        '''
        Run *cmd* on the host via SSH and return the output lines.

        Raises CommandFailed on non-zero exit so callers get a clear error.
        '''
        log.debug('HOST CMD: %s', cmd)
        output = self.cv_HOST.host_run_command(cmd, timeout=timeout)
        log.debug('OUTPUT  : %s', output)
        return output

    def _run_ignore_fail(self, cmd, timeout=60):
        '''Run *cmd*, returning output lines; never raises on failure.'''
        try:
            return self._run(cmd, timeout=timeout)
        except CommandFailed as exc:
            log.debug('Command failed (ignored): %s -> %s', cmd, exc)
            return []

    def _detect_distro(self):
        '''
        Return 'rhel', 'sles', or 'unknown' by reading /etc/os-release.
        '''
        lines = self._run_ignore_fail('cat /etc/os-release', timeout=30)
        content = '\n'.join(lines)
        if 'Red Hat' in content or 'rhel' in content.lower():
            return 'rhel'
        if 'SLES' in content or 'suse' in content.lower():
            return 'sles'
        return 'unknown'

    def _ensure_mstflint(self):
        '''
        Step 1: Verify mstflint is present; install it if missing.

        Returns the full path to the mstflint binary.

        Raises:
            AssertionError: when mstflint cannot be installed or found.
        '''
        log.info('Step 1: Checking for mstflint tool')

        # Check if already available
        which_out = self._run_ignore_fail('which mstflint', timeout=30)
        if which_out and which_out[0].strip():
            path = which_out[0].strip()
            log.info('mstflint already installed: %s', path)
            return path

        log.info('mstflint not found — attempting installation')
        distro = self._detect_distro()

        if distro == 'rhel':
            log.info('RHEL detected: running yum install -y mstflint')
            self._run('yum install -y mstflint', timeout=300)
        elif distro == 'sles':
            log.info('SLES detected: running zypper install -y mstflint')
            self._run('zypper install -y mstflint', timeout=300)
        else:
            self.fail(
                'Cannot install mstflint: unsupported or unrecognised '
                'Linux distribution (distro=%s). '
                'Install mstflint manually and re-run the test.' % distro
            )

        # Verify the installation succeeded
        which_out = self._run('which mstflint', timeout=30)
        self.assertTrue(
            which_out and which_out[0].strip(),
            'mstflint binary not found after installation attempt',
        )
        path = which_out[0].strip()
        log.info('mstflint installed successfully: %s', path)
        return path

    def _resolve_interface(self):
        '''
        Return the interface name to use for this test.

        If the user supplied --adapter-iface that value is returned as-is
        after confirming it exists.  Otherwise the first Mellanox interface
        found via lspci + ethtool is returned.

        Raises:
            AssertionError: when no suitable interface can be found.
        '''
        if self.iface:
            # Verify the user-supplied interface exists
            out = self._run_ignore_fail(
                'ip link show %s' % self.iface, timeout=30
            )
            self.assertTrue(
                out,
                'Interface %s not found on the system. '
                'Check --adapter-iface value.' % self.iface,
            )
            log.info('Using user-supplied interface: %s', self.iface)
            return self.iface

        # Auto-detect: find interfaces whose bus-info matches a Mellanox PCI ID
        log.info('No --adapter-iface specified; auto-detecting Mellanox interface')
        mlx_pci = self._run_ignore_fail(
            "lspci | grep -i mellanox | awk '{print $1}'", timeout=30
        )
        for pci in mlx_pci:
            pci = pci.strip()
            if not pci:
                continue
            # Find the network interface for this PCI slot
            iface_out = self._run_ignore_fail(
                "ls /sys/bus/pci/devices/0000:%s/net/ 2>/dev/null "
                "|| ls /sys/bus/pci/devices/%s/net/ 2>/dev/null" % (pci, pci),
                timeout=30,
            )
            for candidate in iface_out:
                candidate = candidate.strip()
                if candidate:
                    log.info(
                        'Auto-detected Mellanox interface: %s (PCI %s)',
                        candidate, pci,
                    )
                    return candidate

        self.fail(
            'Could not auto-detect a Mellanox network interface. '
            'Specify the interface explicitly via --adapter-iface.'
        )

    def _get_bus_info(self, iface):
        '''
        Return the PCI bus-info string for *iface* from ethtool -i output,
        e.g. "0011:01:00.0".

        Raises:
            AssertionError: when bus-info cannot be parsed.
        '''
        out = self._run('ethtool -i %s' % iface, timeout=30)
        for line in out:
            m = re.match(r'bus-info:\s+(\S+)', line)
            if m:
                bus = m.group(1)
                log.info('Bus-info for %s: %s', iface, bus)
                return bus
        self.fail(
            'Could not parse bus-info from "ethtool -i %s" output:\n%s'
            % (iface, '\n'.join(out))
        )

    def _query_mstflint(self, bus):
        '''
        Run "mstflint -d <bus> q" and return (fw_version, running_version).

        *fw_version*      is the version stored in the flash image.
        *running_version* is the version the adapter is currently running.
        Both are returned as strings, e.g. "22.47.1088".

        Raises:
            AssertionError: when either field cannot be parsed.
        '''
        out = self._run('mstflint -d %s q' % bus, timeout=60)
        fw_ver = None
        run_ver = None
        for line in out:
            m = re.match(r'FW Version:\s+(\S+)', line)
            if m:
                fw_ver = m.group(1)
                continue
            m = re.match(r'FW Version\(Running\):\s+(\S+)', line)
            if m:
                run_ver = m.group(1)

        self.assertIsNotNone(
            fw_ver,
            'Could not parse "FW Version" from mstflint -d %s q output:\n%s'
            % (bus, '\n'.join(out)),
        )
        # "FW Version(Running)" is absent when flash == running; treat them
        # as equal in that case.
        if run_ver is None:
            run_ver = fw_ver
            log.debug(
                'mstflint -d %s q: "FW Version(Running)" not present — '
                'flash and running versions are the same (%s)',
                bus, fw_ver,
            )
        return fw_ver, run_ver

    def _get_fw_from_ethtool(self, iface):
        '''
        Return the firmware-version string from "ethtool -i <iface>",
        e.g. "22.46.1006 (IBM0000000037)".

        Returns None when the field is absent or empty.
        '''
        out = self._run_ignore_fail('ethtool -i %s' % iface, timeout=30)
        for line in out:
            m = re.match(r'firmware-version:\s+(.*)', line)
            if m:
                return m.group(1).strip()
        return None

    def _check_link_state(self, iface, assert_up=True):
        '''
        Check whether the interface link is detected as UP via ethtool.

        Runs "ethtool <iface>" and looks for the "Link detected: yes" field.

        Args:
            iface     (str):  Network interface name, e.g. enP17p1s0f0np0.
            assert_up (bool): When True (default), the method calls
                              self.fail() if the link is not UP.
                              When False it only logs and returns the state.

        Returns:
            bool: True when link is UP, False when link is DOWN or unknown.
        '''
        log.info('Checking link state for interface: %s', iface)
        out = self._run_ignore_fail('ethtool %s' % iface, timeout=30)
        output_str = '\n'.join(out)
        log.debug('ethtool %s output:\n%s', iface, output_str)

        link_up = False
        for line in out:
            # ethtool reports "Link detected: yes" or "Link detected: no"
            m = re.search(r'Link detected:\s+(\w+)', line)
            if m:
                link_up = (m.group(1).lower() == 'yes')
                break

        state_str = 'UP' if link_up else 'DOWN (or unknown)'
        log.info('Interface %s link state: %s', iface, state_str)

        if assert_up and not link_up:
            self.fail(
                'Interface %s link is not UP (ethtool reports: %s). '
                'Verify the cable is connected and the adapter is seated '
                'correctly.\nethtool output:\n%s'
                % (iface, state_str, output_str)
            )
        return link_up

    def _download_firmware(self, url):
        '''
        Step 3: Download the firmware binary from *url* into /tmp using wget.

        Returns the local file path of the downloaded binary.

        Raises:
            CommandFailed / AssertionError: on download failure.
        '''
        log.info('Step 3: Downloading firmware from %s', url)
        fname = url.split('/')[-1]
        local_path = '/tmp/%s' % fname

        # Remove any stale copy
        self._run_ignore_fail('rm -f %s' % local_path, timeout=30)

        self._run(
            'wget -q --no-check-certificate -O %s %s' % (local_path, url),
            timeout=600,
        )

        # Confirm the file exists and is non-empty
        size_out = self._run('stat -c %%s %s' % local_path, timeout=30)
        try:
            size = int(size_out[0].strip())
        except (IndexError, ValueError):
            size = 0

        self.assertGreater(
            size, 0,
            'Downloaded firmware file %s is empty or missing' % local_path,
        )
        log.info('Firmware downloaded to %s (%d bytes)', local_path, size)
        return local_path

    def _flash_firmware(self, bus, fw_file):
        '''
        Step 4: Burn the firmware binary to the adapter flash.

        Runs: mstflint -d <bus> -i <fw_file> b

        Raises:
            CommandFailed / AssertionError: on flash failure.
        '''
        log.info(
            'Step 4: Flashing firmware — device: %s  image: %s', bus, fw_file
        )
        cmd = 'echo y | mstflint -d %s -i %s b' % (bus, fw_file)
        out = self._run(cmd, timeout=FLASH_TIMEOUT)
        log.info('mstflint burn output:\n%s', '\n'.join(out))

        # Verify the burn completed without error text
        output_str = '\n'.join(out).lower()
        error_indicators = ['error', 'failed', 'failure']
        for indicator in error_indicators:
            self.assertNotIn(
                indicator, output_str,
                'mstflint reported an error during firmware burn:\n%s'
                % '\n'.join(out),
            )
        log.info('Firmware burn completed successfully')

    def _reboot_and_wait(self):
        '''
        Step 6: Reboot the system and wait for the OS to return.

        Issues the op-test state machine to OpSystemState.OS,
        which handles the full power-off / boot-to-OS 
        sequence with appropriate timeouts.
        '''
        log.info('Step 6: Rebooting the system')

        # Drive the state machine: OFF then OS handles power cycle + boot
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

        # Refresh the console handle after reboot
        self.console = self.cv_SYSTEM.console
        log.info('System is back up and running')

    # ------------------------------------------------------------------
    # Main test method
    # ------------------------------------------------------------------


    def test_adapter_firmware_upgrade(self):
        '''
        End-to-end adapter firmware flash and post-reboot validation.

        Executes all six steps in sequence and asserts that the firmware
        version active on the adapter after reboot matches the version
        that was flashed in Step 4.
        '''
        # Step 1: Ensure mstflint is available
        self._ensure_mstflint()

        # Resolve interface and PCI bus address
        iface = self._resolve_interface()
        bus = self._get_bus_info(iface)

        log.info('Target adapter — interface: %s  PCI bus: %s', iface, bus)

        # Step 2: Record pre-flash firmware levels and verify link is UP
        log.info('Step 2: Recording pre-flash firmware versions and link state')

        link_up_before = self._check_link_state(iface, assert_up=True)
        ethtool_fw_before = self._get_fw_from_ethtool(iface)
        flash_ver_before, running_ver_before = self._query_mstflint(bus)

        log.info('--- Pre-flash firmware state ---')
        log.info('  Link state               : %s', 'UP' if link_up_before else 'DOWN')
        log.info('  ethtool firmware-version : %s', ethtool_fw_before)
        log.info('  mstflint FW Version      : %s', flash_ver_before)
        log.info('  mstflint FW Ver(Running) : %s', running_ver_before)

        # Step 3: Download the firmware binary
        fw_file = self._download_firmware(self.fw_url)

        # Step 4: Flash the firmware
        self._flash_firmware(bus, fw_file)

        # Step 5: Verify the flash image version changed (running still old)
        log.info('Step 5: Verifying flash image version post-burn')

        flash_ver_after_burn, running_ver_after_burn = self._query_mstflint(bus)

        log.info('--- Post-burn (pre-reboot) firmware state ---')
        log.info('  mstflint FW Version      : %s', flash_ver_after_burn)
        log.info('  mstflint FW Ver(Running) : %s', running_ver_after_burn)

        self.assertNotEqual(
            flash_ver_after_burn, running_ver_after_burn,
            'Expected FW Version in flash (%s) to differ from running version '
            '(%s) immediately after burn but before reboot.'
            % (flash_ver_after_burn, running_ver_after_burn),
        )
        log.info(
            'Post-burn state confirmed: flash=%s  running=%s',
            flash_ver_after_burn, running_ver_after_burn,
        )

        # The version we must see active after reboot
        expected_active_version = flash_ver_after_burn

        # Step 6: Reboot
        self._reboot_and_wait()

        # Step 7: Validate post-reboot firmware levels and link state
        log.info('Step 7: Validating firmware versions and link state after reboot')

        link_up_after = self._check_link_state(iface, assert_up=True)
        ethtool_fw_after = self._get_fw_from_ethtool(iface)
        flash_ver_after_reboot, running_ver_after_reboot = self._query_mstflint(bus)

        log.info('--- Post-reboot firmware state ---')
        log.info('  Link state               : %s', 'UP' if link_up_after else 'DOWN')
        log.info('  ethtool firmware-version : %s', ethtool_fw_after)
        log.info('  mstflint FW Version      : %s', flash_ver_after_reboot)
        log.info('  mstflint FW Ver(Running) : %s', running_ver_after_reboot)

        # The running version must now equal the flashed version
        self.assertEqual(
            running_ver_after_reboot, expected_active_version,
            'Post-reboot running firmware version (%s) does not match the '
            'expected flashed version (%s). Firmware did not take effect.'
            % (running_ver_after_reboot, expected_active_version),
        )

        # The flash image version must match the running version (both updated)
        self.assertEqual(
            flash_ver_after_reboot, running_ver_after_reboot,
            'Post-reboot FW Version in flash (%s) does not match '
            'FW Version(Running) (%s). Unexpected mismatch.'
            % (flash_ver_after_reboot, running_ver_after_reboot),
        )

        log.info(
            '=== PASS: Adapter firmware upgraded from %s to %s and is '
            'active after reboot ===',
            running_ver_before, running_ver_after_reboot,
        )

        # Summary report
        log.info('--- Firmware Upgrade Summary ---')
        log.info('  Interface             : %s', iface)
        log.info('  PCI bus               : %s', bus)
        log.info('  Firmware URL          : %s', self.fw_url)
        log.info('  Version before flash  : %s', running_ver_before)
        log.info('  Version after reboot  : %s', running_ver_after_reboot)
        log.info('  Link state before     : %s', 'UP' if link_up_before else 'DOWN')
        log.info('  Link state after      : %s', 'UP' if link_up_after else 'DOWN')

def suite():
    '''Return a unittest.TestSuite for this module.'''
    s = unittest.TestSuite()
    s.addTest(OpTestAdapterFirmwareUpgrade('test_adapter_firmware_upgrade'))
    return s
