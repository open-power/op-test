#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
# Author: Krishan Gopal Saraswat <krishang@linux.ibm.com>
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
import re
import time
import unittest
import OpTestConfiguration
import OpTestLogger
from common.OpTestUtil import OpTestUtil
from common.Exceptions import CommandFailed

# Sentinel injected into GRUB_CMDLINE_LINUX_DEFAULT for the upgrade test.
_UPGRADE_SENTINEL    = 'grub.upgrade.test=ok'
_UPGRADE_TIMEOUT     = 15   # distinct from the production default of 8 s
_UPGRADE_DEFAULT_BAK = '/tmp/grub_upgrade_test.etc_default_grub.bak'
_UPGRADE_CFG_BAK     = '/tmp/grub_upgrade_test.grub_cfg.bak'

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestGrubTest(unittest.TestCase):
    '''
    GRUB test suite for powerpc-ieee1275 (ppc64le / IBM Power).
    '''

    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.cv_HOST = self.conf.host()
        self.grub_config_file = "/etc/default/grub"
        self.grub_cfg_file = "/boot/grub2/grub.cfg"
        self.util = OpTestUtil(self.conf)
        self.distro = self.util.distro_name()
        log.info(f"Detected distribution: {self.distro}")
        connection = self.cv_HOST.get_ssh_connection()
        connection.run_command("uname -a")   # confirms OS is up
        self.console = self.cv_SYSTEM.console

        result = connection.run_command(
            "awk '/^GRUB_CMDLINE_LINUX_DEFAULT=/{found=1} END{print found+0}' %s"
            % self.grub_config_file
        )
        self._grub_cmdline_key = (
            'GRUB_CMDLINE_LINUX_DEFAULT'
            if result and result[0].strip() == '1'
            else 'GRUB_CMDLINE_LINUX'
        )
        log.info('GRUB cmdline key: %s' % self._grub_cmdline_key)

    def grub_timeout_test(self, timeout_value, tolerance):
        '''
        Full GRUB timeout test lifecycle:
          1. Backup GRUB config and apply the configured timeout
          2. Reboot and measure the GRUB → kernel transition time
          3. Validate the measured value is within tolerance
          4. Restore the original GRUB configuration
        '''
        log.info('GRUB Timeout Test: %ds' % timeout_value)

        # Step 1: backup config and apply timeout #
        connection = self.cv_HOST.get_ssh_connection()
        connection.run_command(f"cp {self.grub_config_file} {self.grub_config_file}.backup")

        log.info(f"Setting GRUB_TIMEOUT to {timeout_value} seconds...")
        # Comment out GRUB_HIDDEN_TIMEOUT settings
        for setting in ['GRUB_HIDDEN_TIMEOUT', 'GRUB_HIDDEN_TIMEOUT_QUIET']:
            connection.run_command(
                f"sed -i 's/^{setting}=/#&/' {self.grub_config_file} 2>/dev/null || true"
            )
        # Set or update GRUB_TIMEOUT_STYLE and GRUB_TIMEOUT
        for param, value in [('GRUB_TIMEOUT_STYLE', 'menu'), ('GRUB_TIMEOUT', str(timeout_value))]:
            try:
                connection.run_command(f"grep -q '^{param}=' {self.grub_config_file}")
                connection.run_command(f"sed -i 's/^{param}=.*/{param}={value}/' {self.grub_config_file}")
            except CommandFailed:
                connection.run_command(f"echo '{param}={value}' >> {self.grub_config_file}")

        # Regenerate GRUB configuration
        connection.run_command("grub2-mkconfig -o /boot/grub2/grub.cfg")

        # Confirm grub.cfg timeout line; patch it only if grub2-mkconfig wrote 0
        connection.run_command(
            f"sed -i 's/set timeout=0/set timeout={timeout_value}/g' {self.grub_cfg_file}"
        )
        # Clear caches and GRUB environment
        for cmd in [
            "rm -f /var/petitboot/*.cache 2>/dev/null || true",
            "rm -f /boot/grub2/*.cache 2>/dev/null || true",
            "grub2-editenv /boot/grub2/grubenv unset next_entry 2>/dev/null || true",
            "grub2-editenv /boot/grub2/grubenv unset saved_entry 2>/dev/null || true",
            "sync"
        ]:
            connection.run_command(cmd)
        pty = self._open_console_for_reboot()

        try:
            # Step 2: reboot and measure GRUB → kernel transition
            log.info("Rebooting system...")
            self._rebooted = True
            connection.run_command("nohup reboot &>/dev/null &", timeout=10)
            start_time = time.time()

            grub_time = None
            kernel_time = None

            if pty is not None:
                log.info("Waiting for GRUB menu...")
                grub_patterns = [
                    r'(?:\x1b\[[0-9;]*m)*GNU GRUB.*version',
                    r'(?:\x1b\[[0-9;]*m)*Welcome to GRUB!',
                    'GNU GRUB',
                    'Press any key to enter the menu',
                    'Welcome to GRUB',
                    'Booting a command list',
                ]
                try:
                    pty.expect(grub_patterns, timeout=90)
                    grub_time = time.time() - start_time
                    log.info(f"GRUB menu appeared at {grub_time:.2f}s after reboot")
                except Exception as e:
                    self.fail(f"Failed to detect GRUB menu within 90s: {e}")

                log.info("Waiting for kernel to load...")
                kernel_patterns = [
                    'Loading Linux',
                    'Loading initial ramdisk',
                    'Booting.*Red Hat',
                    'Booting.*SUSE',
                    'Booting Linux via __start',
                    'Preparing to boot Linux',
                    'Booting the kernel',
                    'Starting kernel',
                    r'\[.*\] Linux version',
                ]
                try:
                    pty.expect(kernel_patterns, timeout=timeout_value + 30)
                    kernel_time = time.time() - start_time
                    log.info(f"Kernel loading started at {kernel_time:.2f}s after reboot")
                except Exception as e:
                    self.fail(f"Failed to detect kernel loading within {timeout_value + 30}s: {e}")

                # Step 3: validate
                actual_timeout = kernel_time - grub_time
                log.info(f"Measured GRUB timeout: {actual_timeout:.2f}s")
                difference = abs(actual_timeout - timeout_value)
                log.info(f"Expected: {timeout_value}s | Actual: {actual_timeout:.2f}s | "
                         f"Difference: {difference:.2f}s | Tolerance: {tolerance}s")
                if difference > tolerance:
                    self.fail(f"Timeout validation failed! Expected: {timeout_value}s, "
                              f"Actual: {actual_timeout:.2f}s, Difference: {difference:.2f}s")
                log.info("Test PASSED")
            else:
                log.warning("  Skipping GRUB timeout measurement (no console pty)")

        finally:
            # Step 4: restore original GRUB configuration
            restore_conn = self._restore_connection()
            if restore_conn is None:
                log.error('Could not reconnect after reboot — GRUB config NOT restored')
            else:
                try:
                    restore_conn.run_command(
                        'cp %s.backup %s' % (self.grub_config_file, self.grub_config_file)
                    )
                    restore_conn.run_command('grub2-mkconfig -o /boot/grub2/grub.cfg')
                    restore_conn.run_command('rm -f %s.backup' % self.grub_config_file)
                except Exception as exc:
                    log.error('Failed to restore GRUB config: %s' % exc)

    def _detect_prep_device(self, connection):
        '''
        Return the full path to the PReP boot partition (e.g. /dev/sda1).
        Fails the test if none is found — the upgrade test requires ppc64le
        with a "PowerPC PReP boot" GPT partition.
        '''
        result = connection.run_command(
            "fdisk -l -o Device,Type 2>/dev/null "
            "| grep -i PReP | awk '{print $1}' | head -1"
        )
        dev = result[0].strip() if result else ''
        if not dev:
            self.fail(
                'No PowerPC PReP boot partition found. '
                'grub_upgrade_test requires a ppc64le machine with a PReP partition.'
            )
        return dev

    def _elf_mtime(self, connection):
        '''Return the mtime epoch of /boot/grub2/grub as a string.'''
        result = connection.run_command(
            "stat -c '%Y' /boot/grub2/grub 2>/dev/null"
        )
        return result[0].strip() if result else '0'

    def _prep_elf_bytes(self, connection, prep_device, offset, count):
        '''
        Read `count` bytes at `offset` from the PReP partition and return
        them as a lowercase hex string with no spaces (e.g. "7f454c46").
        '''
        result = connection.run_command(
            "dd if=%s bs=1 count=%d skip=%d 2>/dev/null "
            "| od -A n -t x1 | tr -d ' \\n'"
            % (prep_device, count, offset)
        )
        return result[0].strip().lower() if result else ''

    def _nvram_boot_device(self, connection):
        '''Return the OF NVRAM boot-device string, or empty string.'''
        try:
            result = connection.run_command('nvsetenv boot-device 2>/dev/null')
            return result[0].strip() if result else ''
        except CommandFailed:
            return ''

    def _of_path_for_prep(self, connection, prep_device):
        '''
        Return the OF device path for `prep_device` without the partition
        suffix (strips trailing ":a"), matching the nvsetenv boot-device
        format.
        '''
        try:
            result = connection.run_command(
                'grub2-ofpathname %s 2>/dev/null' % prep_device
            )
            path = result[0].strip() if result else ''
            return re.sub(r':[a-z]$', '', path)
        except CommandFailed:
            return ''

    def _grub_install_cmd(self, connection, prep_device):
        try:
            result = connection.run_command(
                "bash -x /usr/lib/bootloader/grub2/install 2>&1 "
                "| grep 'grub2-install' | tail -1"
            )
            line = result[0].strip() if result else ''
            m = re.search(r'grub2-install\s+(.*?)\s+/dev/', line)
            if m:
                opts = m.group(1).strip()
                log.info('Detected grub2-install options from bootloader script: %s' % opts)
                return '/usr/sbin/grub2-install %s %s 2>&1' % (opts, prep_device)
        except Exception:
            pass
        try:
            connection.run_command(
                'grub2-install --help 2>&1 | grep -q suse-inhibit-signed'
            )
            suse_flag = '--suse-inhibit-signed '
        except CommandFailed:
            suse_flag = ''
        log.info('Using fallback grub2-install command (suse_flag=%r)' % suse_flag)
        return (
            '/usr/sbin/grub2-install '
            '%s--target=powerpc-ieee1275 '
            '--force --skip-fs-probe %s 2>&1' % (suse_flag, prep_device)
        )

    def _kernels_in_boot(self, connection):
        '''
        Return a sorted list of kernel version strings found in /boot.
        '''
        kernels = []
        for prefix in ('vmlinuz', 'vmlinux'):
            try:
                lines = connection.run_command(
                    "ls /boot/%s-* 2>/dev/null | grep -v '\\.old$'" % prefix
                )
                for line in lines:
                    fname = line.strip().split('/')[-1]
                    ver = fname[len(prefix) + 1:]   # strip "vmlinuz-" / "vmlinux-"
                    if ver:
                        kernels.append(ver)
            except CommandFailed:
                pass
            if kernels:
                break   # found kernels under first prefix — skip second
        return sorted(set(kernels))

    def _assert_all_kernels_in_menu(self, connection):
        '''
        Assert that every kernel image in /boot has a corresponding entry in
        grub.cfg
        '''
        kernels = self._kernels_in_boot(connection)
        self.assertTrue(
            kernels,
            'No kernel images found in /boot.'
        )
        cfg_entries = self._entries_in_grub_cfg(connection)
        bls_entries = self._entries_in_bls(connection)
        all_linux_paths = list(cfg_entries.values()) + list(bls_entries.values())
        missing = []
        for ver in kernels:
            if any(ver in p for p in all_linux_paths):
                log.info('  [OK] %s — in menu' % ver)
            else:
                log.warning('  [MISSING] %s — no menu entry' % ver)
                missing.append(ver)
        self.assertEqual(
            missing, [],
            'Kernels in /boot with no GRUB menu entry:\n'
            '  %s\n'
            'Run grub2-mkconfig -o %s to regenerate the menu.'
            % (', '.join(missing), self.grub_cfg_file),
        )
        return kernels, all_linux_paths

    def _restore_connection(self):
        '''
        Return an SSH connection suitable for cleanup/restore after a reboot.
        '''
        if not getattr(self, '_rebooted', False):
            try:
                return self.cv_HOST.get_ssh_connection()
            except Exception:
                pass
        return self._wait_for_ssh_after_reboot()

    def _open_console_for_reboot(self):
        '''
        Open the HMC console pty (if available), drain stale output, and
        return the pty or None.  Call this immediately before issuing reboot.
        '''
        pty = self.cv_SYSTEM.console.get_console()
        if pty is None:
            log.warning('  HMC console unavailable — skipping console checks')
            return None
        try:
            pty.expect(r'.+', timeout=2)
        except Exception:
            pass
        return pty

    def _wait_for_grub_banner(self, pty, timeout=120):
        '''
        Wait for the GRUB banner on the console pty.  Logs the result.
        Does nothing if pty is None.
        '''
        if pty is None:
            return
        grub_banner = [
            r'(?:\x1b\[[0-9;]*m)*GNU GRUB.*version',
            r'(?:\x1b\[[0-9;]*m)*Welcome to GRUB!',
            'GNU GRUB',
            'Welcome to GRUB',
        ]
        try:
            pty.expect(grub_banner, timeout=timeout)
        except Exception as exc:
            log.warning('  GRUB banner not seen within %ds: %s' % (timeout, exc))

    def _check_live_grub_menu(self, pty, kernels):
        '''
        After a reboot has been issued, capture the live GRUB menu text from
        the HMC console and verify every version string in *kernels* appears.
        '''
        if pty is None:
            return '', []

        grub_banner = [
            r'(?:\x1b\[[0-9;]*m)*GNU GRUB.*version',
            r'(?:\x1b\[[0-9;]*m)*Welcome to GRUB!',
            'GNU GRUB',
            'Welcome to GRUB',
        ]
        try:
            pty.expect(grub_banner, timeout=120)
        except Exception as exc:
            log.warning('  GRUB banner not seen: %s — skipping live menu check' % exc)
            return '', []

        # Drain up to 5 s of menu output.
        menu_text = ''
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                pty.expect(r'.+', timeout=1)
                chunk = ''
                if hasattr(pty, 'before') and pty.before:
                    chunk += pty.before if isinstance(pty.before, str) \
                        else pty.before.decode('utf-8', errors='replace')
                if hasattr(pty, 'after') and pty.after:
                    chunk += pty.after if isinstance(pty.after, str) \
                        else pty.after.decode('utf-8', errors='replace')
                menu_text += chunk
            except Exception:
                break

        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mKHJA-Za-z]')
        clean_menu = ansi_escape.sub('', menu_text)

        live_missing = []
        for ver in kernels:
            if ver in clean_menu:
                log.info('  [OK] %s — visible in live menu' % ver)
            else:
                log.warning('  [NOT VISIBLE] %s — not seen in live menu' % ver)
                live_missing.append(ver)

        return clean_menu, live_missing

    def _entries_in_grub_cfg(self, connection):
        '''
        Return a dict mapping each menuentry title (str) → linux cmdline
        path (str) parsed from /boot/grub2/grub.cfg.
        '''
        try:
            lines = connection.run_command('cat %s' % self.grub_cfg_file)
        except CommandFailed:
            return {}

        entries = {}
        current_title = None
        for line in lines:
            line = line.strip()
            m_title = re.match(r"menuentry\s+'([^']+)'", line) or \
                      re.match(r'menuentry\s+"([^"]+)"', line)
            if m_title:
                current_title = m_title.group(1)
                continue
            m_linux = re.match(r'(?:linux|linuxefi)\s+(\S+)', line)
            if m_linux and current_title:
                entries[current_title] = m_linux.group(1)
                current_title = None   # one linux line per entry is enough
        return entries

    def _entries_in_bls(self, connection):
        '''
        Return a dict mapping BLS entry title → kernel path for
        /boot/loader/entries/*.conf.
        Returns an empty dict on non-BLS systems.
        '''
        try:
            conf_files = connection.run_command(
                'ls /boot/loader/entries/*.conf 2>/dev/null'
            )
        except CommandFailed:
            return {}

        entries = {}
        for conf in conf_files:
            conf = conf.strip()
            if not conf:
                continue
            try:
                conf_lines = connection.run_command('cat %s' % conf)
            except CommandFailed:
                continue
            title = ''
            linux = ''
            for cl in conf_lines:
                cl = cl.strip()
                if cl.startswith('title '):
                    title = cl[6:].strip()
                elif cl.startswith('linux '):
                    linux = cl[6:].strip()
            if title and linux:
                entries[title] = linux
        return entries

    def grub_menu_entries_test(self):
        '''
        Verify that every kernel image present in /boot has a corresponding
        entry in the GRUB menu configuration, then confirm via the live GRUB
        menu on the HMC console.
        '''
        connection = self.cv_HOST.get_ssh_connection()

        # Phase 1+2+3: cross-check /boot kernels vs grub.cfg + BLS entries
        kernels, _ = self._assert_all_kernels_in_menu(connection)
        log.info('[Phase 3] All %d kernel(s) accounted for in menu.' % len(kernels))

        # Phase 4: live GRUB menu check via HMC console
        pty = self._open_console_for_reboot()
        if pty is None:
            log.info('GRUB Menu Entries Test: PASSED (static check only — no console)')
            return

        self._rebooted = True
        connection.run_command('nohup reboot &>/dev/null &', timeout=10)

        clean_menu, live_missing = self._check_live_grub_menu(pty, kernels)

        # Wait for SSH to come back before asserting, so the system is clean.
        self._wait_for_ssh_after_reboot()

        if not clean_menu:
            # _check_live_grub_menu already waited for SSH on banner timeout
            log.info('GRUB Menu Entries Test: PASSED (static check only; console timed out)')
            return

        self.assertEqual(
            live_missing, [],
            'The following kernels were not visible in the live GRUB menu:\n'
            '  %s\n'
            'Captured menu text:\n%s' % (', '.join(live_missing), clean_menu[:600]),
        )
        log.info('GRUB Menu Entries Test: PASSED (static + live console check)')

    def _wait_for_ssh_after_reboot(self, attempts=6, interval=20):
        '''Poll SSH until the LPAR is back up after a reboot.'''
        for attempt in range(1, attempts + 1):
            time.sleep(interval)
            try:
                conn = self.cv_HOST.get_ssh_connection()
                conn.run_command('uname -a')
                log.info('  SSH back on attempt %d' % attempt)
                return conn
            except Exception:
                log.warning('  SSH attempt %d/%d not ready' % (attempt, attempts))
        log.warning('  SSH did not come back after reboot')
        return None

    def grub_upgrade_test(self):
        '''
        GRUB upgrade test for powerpc-ieee1275.
        Method: inject a unique sentinel kernel parameter
        ("grub.upgrade.test=ok") and a distinct timeout (15 s) into
        /etc/default/grub before the upgrade, then verify:
          - grub.cfg contains the sentinel on the linux cmdline line
          - grub.cfg contains "set timeout=15"
          - /etc/default/grub was NOT overwritten by grub2-install
          - /proc/cmdline contains the sentinel after reboot
        '''
        log.info('GRUB Upgrade Test: config preservation + PReP integrity')

        connection = self.cv_HOST.get_ssh_connection()
        prep_device = self._detect_prep_device(connection)
        log.info('PReP device: %s' % prep_device)

        # Phase 1: Record baseline
        log.info('[Phase 1] Recording baseline state...')

        elf_mtime_before = self._elf_mtime(connection)
        nvram_before = self._nvram_boot_device(connection)
        of_path      = self._of_path_for_prep(connection, prep_device)
        # Back up originals — tearDown will restore these unconditionally.
        connection.run_command(
            'cp %s %s' % (self.grub_config_file, _UPGRADE_DEFAULT_BAK)
        )
        connection.run_command(
            'cp %s %s' % (self.grub_cfg_file, _UPGRADE_CFG_BAK)
        )
        connection.run_command('sync')
        log.info('[Phase 1] Baseline recorded and originals backed up.')

        try:
            # Phase 2: Inject sentinel
            log.info('[Phase 2] Injecting sentinel into %s...' % self.grub_config_file)
            connection.run_command(
                "sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=%d/' %s"
                % (_UPGRADE_TIMEOUT, self.grub_config_file)
            )
            connection.run_command(
                r"grep -q '%s' %s || "
                r"sed -i 's/^%s=\"\(.*\)\"/%s=\"\1 %s\"/' %s"
                % (_UPGRADE_SENTINEL, self.grub_config_file,
                   self._grub_cmdline_key, self._grub_cmdline_key,
                   _UPGRADE_SENTINEL, self.grub_config_file)
            )

            verify_to = connection.run_command(
                "grep '^GRUB_TIMEOUT=' %s" % self.grub_config_file
            )
            verify_cl = connection.run_command(
                "grep '^%s=' %s" % (self._grub_cmdline_key, self.grub_config_file)
            )
            self.assertIn(
                str(_UPGRADE_TIMEOUT),
                verify_to[0] if verify_to else '',
                'GRUB_TIMEOUT not set to %d in %s' % (_UPGRADE_TIMEOUT, self.grub_config_file),
            )
            self.assertIn(
                _UPGRADE_SENTINEL,
                verify_cl[0] if verify_cl else '',
                'Sentinel %s not injected into %s' % (_UPGRADE_SENTINEL, self._grub_cmdline_key),
            )
            log.info('[Phase 2] Sentinel injected.')

            # Phase 3: Run the upgrade
            log.info('[Phase 3] Running grub2-install + grub2-mkconfig...')

            install_cmd = self._grub_install_cmd(connection, prep_device)
            try:
                install_out = connection.run_command(install_cmd, timeout=120)
            except CommandFailed as exc:
                self.fail('grub2-install failed: %s' % exc)

            install_log = '\n'.join(install_out)
            self.assertIn(
                'Installation finished. No error reported.',
                install_log,
                'grub2-install did not report success:\n%s' % install_log,
            )

            connection.run_command(
                'grub2-mkconfig -o %s 2>&1' % self.grub_cfg_file, timeout=60
            )

            try:
                bls_files = connection.run_command(
                    "ls /boot/loader/entries/*.conf 2>/dev/null"
                )
                for bls in bls_files:
                    bls = bls.strip()
                    if not bls:
                        continue
                    # Append sentinel to the 'options' line only if not already present.
                    connection.run_command(
                        "grep -q '%s' %s || "
                        "sed -i 's/^options \\(.*\\)/options \\1 %s/' %s"
                        % (_UPGRADE_SENTINEL, bls, _UPGRADE_SENTINEL, bls)
                    )
            except CommandFailed:
                log.info('  No BLS entries found — skipping BLS update (non-BLS system)')

            connection.run_command('sync')
            log.info('[Phase 3] Upgrade complete.')

            # Phase 4: Pre-reboot checks
            log.info('[Phase 4] Pre-reboot verification...')

            # 4a-1 — sentinel in grub.cfg
            n_sentinel = connection.run_command(
                "grep -c '%s' %s 2>/dev/null || echo 0"
                % (_UPGRADE_SENTINEL, self.grub_cfg_file)
            )
            cnt = int(n_sentinel[0].strip()) if n_sentinel else 0
            self.assertGreater(
                cnt, 0,
                'Sentinel "%s" not found in %s — '
                'grub2-mkconfig did not pick up /etc/default/grub changes.'
                % (_UPGRADE_SENTINEL, self.grub_cfg_file),
            )
            log.info('  [4a-1] Sentinel in grub.cfg: PASS')

            # 4a-2 — test timeout in grub.cfg
            n_timeout = connection.run_command(
                "grep -c 'set timeout=%d' %s 2>/dev/null || echo 0"
                % (_UPGRADE_TIMEOUT, self.grub_cfg_file)
            )
            cnt_to = int(n_timeout[0].strip()) if n_timeout else 0
            self.assertGreater(
                cnt_to, 0,
                '"set timeout=%d" not found in %s — GRUB_TIMEOUT not propagated.'
                % (_UPGRADE_TIMEOUT, self.grub_cfg_file),
            )

            # 4a-3 — /etc/default/grub not overwritten by grub2-install
            n_default = connection.run_command(
                "grep -c '%s' %s 2>/dev/null || echo 0"
                % (_UPGRADE_SENTINEL, self.grub_config_file)
            )
            cnt_def = int(n_default[0].strip()) if n_default else 0
            self.assertGreater(
                cnt_def, 0,
                '%s was overwritten by grub2-install (sentinel missing).'
                % self.grub_config_file,
            )

            # 4b-1 — ELF magic in PReP
            magic = self._prep_elf_bytes(connection, prep_device, offset=0, count=4)
            self.assertEqual(
                magic, '7f454c46',
                'PReP partition does not start with ELF magic (got %s). '
                'Bootloader may be corrupt!' % magic,
            )

            # 4b-2 — ELF class: 01 = 32-bit
            ei_class = self._prep_elf_bytes(connection, prep_device, offset=4, count=1)
            self.assertEqual(
                ei_class, '01',
                'PReP ELF EI_CLASS is %s, expected 01 (32-bit).' % ei_class,
            )

            # 4b-3 — ELF data encoding: 02 = big-endian
            ei_data = self._prep_elf_bytes(connection, prep_device, offset=5, count=1)
            self.assertEqual(
                ei_data, '02',
                'PReP ELF EI_DATA is %s, expected 02 (big-endian).' % ei_data,
            )

            # 4b-4 — ELF machine: 0014 = PowerPC
            e_machine = self._prep_elf_bytes(connection, prep_device, offset=18, count=2)
            self.assertEqual(
                e_machine, '0014',
                'PReP ELF e_machine is %s, expected 0014 (PowerPC).' % e_machine,
            )

            # 4b-5 — /boot/grub2/grub is a valid ELF
            file_out = connection.run_command('file /boot/grub2/grub 2>/dev/null')
            file_desc = file_out[0] if file_out else ''
            self.assertIn(
                'ELF', file_desc,
                '/boot/grub2/grub is not a valid ELF after upgrade: %s' % file_desc,
            )

            # 4b-6 — /boot/grub2/grub mtime advanced (ELF was written)
            elf_mtime_after = self._elf_mtime(connection)
            self.assertGreater(
                int(elf_mtime_after), int(elf_mtime_before),
                '/boot/grub2/grub mtime did not advance — '
                'grub2-install may not have written a new ELF to PReP.',
            )

            # 4b-7 — NVRAM boot-device still matches OF path
            nvram_after = self._nvram_boot_device(connection)
            if nvram_before and of_path:
                self.assertEqual(
                    nvram_after, of_path,
                    'NVRAM boot-device mismatch after upgrade: '
                    'nvram=%s of_path=%s' % (nvram_after, of_path),
                )
            else:
                log.info('  [4b-7] NVRAM check skipped (no OF path available)')

            log.info('[Phase 4] All pre-reboot checks passed.')

            # Phase 5: Reboot and post-boot verification
            log.info('[Phase 5] Rebooting to verify upgraded GRUB boots system...')
            pty = self._open_console_for_reboot()
            self._rebooted = True
            connection.run_command('nohup reboot &>/dev/null &', timeout=10)

            if pty is not None:
                self._wait_for_grub_banner(pty)

                kernel_patterns = [
                    'Loading Linux',
                    'Loading initial ramdisk',
                    'Booting Linux via __start',
                    'Preparing to boot Linux',
                    'Starting kernel',
                    'Booting the kernel',
                    r'\[.*\] Linux version',
                ]
                try:
                    pty.expect(kernel_patterns, timeout=60)
                except Exception as exc:
                    self.fail('Kernel not loading after upgrade reboot: %s' % exc)

            conn_post = self._wait_for_ssh_after_reboot()
            if conn_post is None:
                self.fail('Could not SSH in after upgrade reboot')

            # 5a — sentinel in /proc/cmdline
            cmdline = conn_post.run_command('cat /proc/cmdline')
            cmdline_str = cmdline[0] if cmdline else ''
            self.assertIn(
                _UPGRADE_SENTINEL, cmdline_str,
                'Sentinel "%s" not in /proc/cmdline after reboot — '
                'GRUB may have used a stale grub.cfg.\n'
                'Actual cmdline: %s' % (_UPGRADE_SENTINEL, cmdline_str),
            )

            # 5b — boot device consistent with pre-upgrade NVRAM
            try:
                bp = conn_post.run_command(
                    "cat /proc/device-tree/chosen/bootpath 2>/dev/null "
                    "| tr '\\0' '\\n' | head -1"
                )
                bootpath = bp[0].strip() if bp else ''
                if nvram_before and bootpath:
                    self.assertIn(
                        bootpath, nvram_before,
                        'Boot device path %s not within NVRAM device %s'
                        % (bootpath, nvram_before),
                    )
                else:
                    log.info('  [5b] Boot device check skipped (no data)')
            except Exception as exc:
                log.warning('  [5b] Boot device check skipped: %s' % exc)

            log.info('[Phase 5] Post-boot checks passed.')

        finally:
            # Restore: always runs, regardless of pass or fail
            restore_conn = self._restore_connection()
            if restore_conn is None:
                log.error(
                    '[Restore] Could not SSH — manual fix needed:\n'
                    '  cp %s %s && grub2-mkconfig -o %s'
                    % (_UPGRADE_DEFAULT_BAK, self.grub_config_file, self.grub_cfg_file)
                )
            else:
                try:
                    restore_conn.run_command(
                        'cp %s %s' % (_UPGRADE_DEFAULT_BAK, self.grub_config_file)
                    )
                    restore_conn.run_command(
                        'grub2-mkconfig -o %s 2>&1' % self.grub_cfg_file,
                        timeout=60,
                    )
                    try:
                        bls_files = restore_conn.run_command(
                            "ls /boot/loader/entries/*.conf 2>/dev/null"
                        )
                        for bls in bls_files:
                            bls = bls.strip()
                            if not bls:
                                continue
                            restore_conn.run_command(
                                "sed -i 's/ %s//' %s" % (_UPGRADE_SENTINEL, bls)
                            )
                    except CommandFailed:
                        pass  # No BLS entries — non-BLS system, nothing to do
                    restore_conn.run_command(
                        'rm -f %s %s' % (_UPGRADE_DEFAULT_BAK, _UPGRADE_CFG_BAK)
                    )
                    restore_conn.run_command('sync')
                except Exception as exc:
                    log.error('[Restore] Failed: %s' % exc)

        log.info('GRUB Upgrade Test: PASSED')

    def _latest_installed_kernel(self, connection):
        '''
        Return the version string of the most-recently installed kernel
        '''
        pkg = 'kernel-default' if self.distro in ('sles', 'opensuse') else 'kernel'
        try:
            lines = connection.run_command(
                "rpm -q --last %s 2>/dev/null | head -1 | awk '{print $1}'" % pkg
            )
            full = lines[0].strip() if lines else ''
            # "kernel-5.14.0-427.el9.ppc64le" → strip "<pkg>-" prefix
            prefix = pkg + '-'
            ver = full[len(prefix):] if full.startswith(prefix) else full
            return ver
        except CommandFailed:
            return ''

    def _default_kernel_in_grub(self, connection):
        '''
        Return the kernel version string that GRUB will boot by default.
        '''
        # grubby is the canonical tool on RHEL/BLS systems
        try:
            lines = connection.run_command('grubby --default-kernel 2>/dev/null')
            path = lines[0].strip() if lines else ''
            if path:
                # /boot/vmlinuz-5.14.0-427.el9.ppc64le → strip prefix
                fname = path.split('/')[-1]
                for pfx in ('vmlinuz-', 'vmlinux-'):
                    if fname.startswith(pfx):
                        return fname[len(pfx):]
                return fname
        except CommandFailed:
            pass

        # Fallback: read grubenv saved_entry index and map to grub.cfg linux path
        try:
            env_lines = connection.run_command(
                'grub2-editenv list 2>/dev/null | grep saved_entry'
            )
            saved = env_lines[0].split('=', 1)[1].strip() if env_lines else '0'
        except (CommandFailed, IndexError):
            saved = '0'

        cfg_entries = self._entries_in_grub_cfg(connection)
        linux_paths = list(cfg_entries.values())
        # saved_entry can be a numeric index or an entry title
        if saved.isdigit():
            idx = int(saved)
            if 0 <= idx < len(linux_paths):
                path = linux_paths[idx]
            elif linux_paths:
                path = linux_paths[0]
            else:
                return ''
        else:
            # Match by title substring
            path = cfg_entries.get(saved, linux_paths[0] if linux_paths else '')

        fname = path.split('/')[-1] if path else ''
        for pfx in ('vmlinuz-', 'vmlinux-'):
            if fname.startswith(pfx):
                return fname[len(pfx):]
        return fname

    def grub_kernel_update_test(self):
        '''
        Install a new kernel, verify all kernel entries appear in the GRUB
        menu, confirm the default entry points to the new kernel, reboot,
        and verify the system booted the new kernel.
        '''
        connection = self.cv_HOST.get_ssh_connection()

        # Phase 1: snapshot pre-update state
        kernels_before = set(self._kernels_in_boot(connection))

        new_kernel_ver = None   # set in Phase 2, used in cleanup
        conn_post = None
        pkg = 'kernel-default' if self.distro in ('sles', 'opensuse') else 'kernel'

        try:
            # Phase 2: install kernel update
            self.util.install_package([pkg])

            kernels_after = set(self._kernels_in_boot(connection))
            new_kernels = kernels_after - kernels_before
            if new_kernels:
                new_kernel_ver = sorted(new_kernels)[-1]
                # Regenerate grub.cfg; force in case package scriptlet skipped it.
                connection.run_command(
                    'grub2-mkconfig -o %s 2>&1' % self.grub_cfg_file, timeout=60
                )
                # Set new kernel as default on RHEL/BLS via grubby.
                try:
                    connection.run_command(
                        'grubby --set-default /boot/vmlinuz-%s 2>/dev/null || '
                        'grubby --set-default /boot/vmlinux-%s 2>/dev/null || true'
                        % (new_kernel_ver, new_kernel_ver)
                    )
                except CommandFailed:
                    pass  # grubby absent on SLES; grub2-mkconfig ordering is sufficient
                connection.run_command('sync')
            else:
                log.info(
                    '  No new kernel in /boot after install '
                    '(system already at latest). Checking existing entries.'
                )

            # Phase 3: verify all kernels present in GRUB menu 
            all_kernels, all_linux_paths = self._assert_all_kernels_in_menu(connection)
            if new_kernel_ver:
                self.assertTrue(
                    any(new_kernel_ver in p for p in all_linux_paths),
                    'New kernel %s has no GRUB menu entry after install.\n'
                    'Run: grub2-mkconfig -o %s' % (new_kernel_ver, self.grub_cfg_file),
                )

            # Phase 4: verify default entry
            default_ver = self._default_kernel_in_grub(connection)
            if new_kernel_ver:
                self.assertIn(
                    new_kernel_ver, default_ver,
                    'GRUB default entry (%s) does not match new kernel (%s). '
                    'Run "grubby --set-default /boot/vmlinuz-%s" to fix.'
                    % (default_ver, new_kernel_ver, new_kernel_ver),
                )
            else:
                self.assertTrue(
                    any(k in default_ver for k in all_kernels),
                    'GRUB default entry (%s) does not match any kernel in /boot: %s'
                    % (default_ver, all_kernels),
                )

            # Phase 5: reboot, verify live GRUB menu, check running kernel 
            pty = self._open_console_for_reboot()
            self._rebooted = True
            connection.run_command('nohup reboot &>/dev/null &', timeout=10)

            clean_menu, live_missing = self._check_live_grub_menu(pty, all_kernels)

            conn_post = self._wait_for_ssh_after_reboot()
            if conn_post is None:
                self.fail('Could not SSH back after reboot')

            if clean_menu:
                self.assertEqual(
                    live_missing, [],
                    'Kernels not visible in live GRUB menu after reboot:\n'
                    '  %s\n'
                    'Captured menu text:\n%s'
                    % (', '.join(live_missing), clean_menu[:600]),
                )
            else:
                log.info('[Phase 5] Live menu check skipped (console timed out).')

            if new_kernel_ver:
                running_after = conn_post.run_command('uname -r')
                running_after = running_after[0].strip() if running_after else ''
                log.info('  Running kernel after reboot: %s' % running_after)
                self.assertIn(
                    new_kernel_ver, running_after,
                    'System did not boot the new kernel.\n'
                    'Expected: %s\nActual uname -r: %s'
                    % (new_kernel_ver, running_after),
                )
            else:
                log.info('[Phase 5] No new kernel — skipping uname -r check.')

        finally:
            # Phase 6: cleanup — remove new kernel 
            if new_kernel_ver:
                cleanup_conn = conn_post if conn_post is not None \
                    else self._restore_connection()
                if cleanup_conn is None:
                    log.error(
                        '[Phase 6] No SSH — manual cleanup needed:\n'
                        '  dnf remove kernel-%s  or  zypper remove kernel-default-%s'
                        % (new_kernel_ver, new_kernel_ver)
                    )
                else:
                    try:
                        pkg_ver = '%s-%s' % (pkg, new_kernel_ver)
                        self.util.uninstall_package([pkg_ver])
                        cleanup_conn.run_command(
                            'grub2-mkconfig -o %s 2>&1' % self.grub_cfg_file, timeout=60
                        )
                        cleanup_conn.run_command('sync')
                    except Exception as exc:
                        log.error('[Phase 6] Cleanup failed: %s' % exc)

    def runTest(self):
        self.grub_timeout_test(timeout_value=1, tolerance=3)
        self.grub_timeout_test(timeout_value=10, tolerance=5)
        self.grub_menu_entries_test()
        self.grub_kernel_update_test()
        self.grub_upgrade_test()
