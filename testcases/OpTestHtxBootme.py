#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
# [+] International Business Machines Corp.
# Author: Tasmiya Nalatwad <tasmiya@linux.vnet.ibm.com>
#
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

"""
HtxBootme Test

The test case is to run HTX workload and start bootme test.
When the Bootme is set to ON the Lpar goes to reboot everytime after 30 minutes
of time interval. And the reboot cycle continues.
After every reboot the HTX workload must continue without any error.
The cycle continues until the bootme is set to off.
"""

import re
import socket
import subprocess
import os
import sys
import time
import unittest
from common.OpTestSSHConnection import OpTestSSHConnection, OpTestCommandResult
from common.OpTestCommandExecutor import OpTestCommandExecutor
from common.Exceptions import SSHCommandFailed, SSHSessionDisconnected
from datetime import datetime

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse

import OpTestConfiguration
import OpTestLogger
from common.OpTestSSH import OpTestSSH
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestHTXUtil import (
    OpTestHTXUtil,
    HTX_ERR_FILE,
    HTX_MDT_DIR,
)

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


# SSH settle time (seconds) after port 22 opens before declaring the
# system ready.  This LPAR has ibmvfc SAN scan + LVM assembly in dracut
# which adds significant latency beyond when ping/sshd first respond.
_SSH_SETTLE_SECS = 60

# Matches the received-packet count in ping summary lines on both Linux
# ("2 received") and macOS ("2 packets received").  A non-zero count means
# the host is reachable.
_PING_RECEIVED_RE = re.compile(r',\s*(\d+)(?:\s+packets)?\s+received')

# Extra SSH deadline (seconds) beyond the initial 300 s window.
# Accommodates LPARs with dense device trees (many NVMe namespaces,
# multiple FC paths) where dracut SAN scan pushes sshd readiness past
# the 5-minute mark.
_SSH_DEADLINE_SECS = 600


class OpTestHtxBootmeIO():
    def setUp(self):
        """
        Setup
        """
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.console = self.cv_SYSTEM.console
        self.console_thread = OpSOLMonitorThread(1, "console")
        self.console_thread.start()
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        res = self.con.run_command('uname -a')
        if 'ppc64' not in ' '.join(res):
            self.fail("Platform does not support HTX tests")

        self.host_ip = self.conf.args.host_ip
        self.host_user = self.conf.args.host_user
        self.host_password = self.conf.args.host_password
        self.mdt_file = self.conf.args.mdt_file
        self.time_limit = int(self.conf.args.time_limit)
        self.boot_count = int(self.conf.args.boot_count)
        self.htx_rpm_link = self.conf.args.htx_rpm_link
        # bootme_mode: reboot behaviour passed to htxcmdline -bootme on.
        # Valid values: soft | softf | hard | hardf  (default: softf)
        self.bootme_mode = getattr(self.conf.args, 'bootme_mode', 'softf')
        # bootme_period: reboot interval index passed to htxcmdline -bootme on.
        # 1=20 min  2=30 min  3=1 hour  4=midnight  (default: 2 → 30 min)
        self.bootme_period = getattr(self.conf.args, 'bootme_period', '2')

        self.ssh_host = OpTestSSH(self.host_ip, self.host_user, self.host_password)
        self.ssh_host.set_system(self.conf.system())

        self.host_distro_name = self.util.distro_name()
        self.host_distro_version = self.util.get_distro_version().split(".")[0]

        self.htx = OpTestHTXUtil(
            console=self.con,
            ssh_host=self.ssh_host,
            distro_name=self.host_distro_name,
            distro_version=self.host_distro_version,
            rpm_link=self.htx_rpm_link,
            run_time=self.time_limit,
        )

    def _guard_against_framework_reboot(self):
        """
        Detect and absorb a framework-injected reboot that can occur when
        OpTestSystem.goto_state() issues 'reboot' via the console as part of
        its state-detection fallback path (triggered by the HMCConsole API
        signature mismatch in OpTestHMC).

        Symptom: the LPAR goes offline within ~90 seconds of setUp completing,
        before htxcmdline -bootme on has been issued.  If we detect that the
        system is already offline (or comes back online within a short window),
        we wait for it to fully boot, then re-establish self.con so the test
        proceeds cleanly against a live system.

        This does NOT fix the underlying framework bug — it makes the test
        resilient to it without masking real failures.
        """
        # Only act if the system dropped offline very quickly after setUp.
        # Poll for up to 120 s; if it's still up the framework did not reboot.
        went_offline = False
        deadline = time.time() + 120
        while time.time() < deadline:
            if not self.is_system_online():
                went_offline = True
                log.warning(
                    "LPAR went offline within 120 s of setUp — framework "
                    "reboot detected (likely OpTestSystem goto_state fallback). "
                    "Waiting for system to recover before starting HTX."
                )
                break
            time.sleep(5)

        if went_offline:
            if not self.wait_for_reboot_completion(self.cv_HOST.ip):
                self.fail(
                    "LPAR did not recover from framework-injected reboot "
                    "within the timeout. Check OpTestHMC / goto_state logs."
                )
            # Re-establish the SSH connection that was invalidated by the reboot.
            self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            self.htx = self.htx.__class__(
                console=self.con,
                ssh_host=self.ssh_host,
                distro_name=self.host_distro_name,
                distro_version=self.host_distro_version,
                rpm_link=self.htx_rpm_link,
                run_time=self.time_limit,
            )
            log.info("SSH connection and HTX handle refreshed after "
                     "framework-injected reboot.")

    def setup_htx(self):
        """
        Install HTX via OpTestHTXUtil.
        """
        log.info("Setting up HTX on host via OpTestHTXUtil")
        self.htx.install()

    def runTest(self):
        """
        Execute 'HTX' with appropriate parameters.
        """
        # Absorb any framework-injected reboot before touching HTX.
        self._guard_against_framework_reboot()
        self.setup_htx()
        self.start_htx_run()
        self.htx_check()
        self.htx_bootme_test()
        self.stop_htx_bootme()
        self.htx_stop()

    def start_htx_run(self):
        """
        Starting htx test.
        """
        if self.current_test_case != "HtxBootme_NicDevices":
            log.debug("Creating the HTX mdt files")
            self.con.run_command('htxcmdline -createmdt')

    def htx_check(self):
        """
        Checks if HTX is running, and if no errors.

        Verifies that HTX is actually executing workload against the MDT
        before bootme is enabled — catching the case where install succeeded
        but no -run was issued, which would result in bootme cycling an
        idle daemon.
        """
        log.debug("Checking HTX error file")
        file_size = self.ssh_host.run_command('wc -c %s' % HTX_ERR_FILE)
        if int(file_size[0].split()[0]) != 0:
            self.fail("HTX error file is non-empty before bootme. "
                      "Check %s for details." % HTX_ERR_FILE)

        # Confirm at least one device is in ACTIVE state in the MDT so
        # bootme has a live workload to preserve across reboots.
        cmd = 'htxcmdline -query  -mdt %s' % self.mdt_file
        res = self.con.run_command(cmd)
        if not any("ACTIVE" in line for line in res):
            self.fail(
                "No ACTIVE devices found in '%s' output before enabling "
                "bootme. Ensure htxcmdline -run was issued successfully."
                % cmd
            )
        log.info("HTX workload confirmed ACTIVE on mdt %s", self.mdt_file)
        time.sleep(60)

    def htx_bootme_test(self):
        """
        Starting bootme on htx.
        """
        # Maps bootme_period index → inter-reboot wait in seconds.
        # Mirrors the periods documented in htxcmdline -bootme help:
        #   1=every 20 min  2=every 30 min  3=every hour  4=every midnight
        _period_seconds = {'1': 1200, '2': 1800, '3': 3600, '4': 86400}
        total_wait_time = _period_seconds.get(str(self.bootme_period), 1800)

        bootme_cmd = 'htxcmdline -bootme on mode:%s period:%s' % (
            self.bootme_mode, self.bootme_period
        )
        log.debug("Running bootme command: %s", bootme_cmd)
        res = self.con.run_command_ignore_fail(bootme_cmd)
        output_text = ' '.join(res)
        if "bootme is already on" in output_text:
            log.info("HTX bootme is already on — verifying status")
        elif "bootme on is completed successfully" not in output_text:
            self.fail(
                "htxcmdline -bootme on gave unexpected output: %s" % res
            )

        # Confirm bootme is truly active regardless of which path was taken
        # above (fresh enable or "already on").  Exit code alone is not
        # sufficient — the status command is the authoritative check.
        log.debug("Verifying bootme status via htxcmdline -bootme status")
        status_res = self.con.run_command_ignore_fail(
            'htxcmdline -bootme status'
        )
        status_text = ' '.join(status_res)
        # htxcmdline -bootme status outputs "bootme status: on" (not "bootme is on")
        if "bootme status: on" not in status_text.lower():
            self.fail(
                "htxcmdline -bootme status does not show bootme as ON "
                "after '%s'. Status output: %s. "
                "Run 'htxcmdline -bootme off' on the LPAR to clear any "
                "stale state, then retry."
                % (bootme_cmd, status_res)
            )
        log.info("Bootme status confirmed ON (mode:%s period:%s)",
                 self.bootme_mode, self.bootme_period)

        # Wait for the system to go offline.  The deadline is the configured
        # period (total_wait_time) plus a 10-minute grace buffer.  The system
        # may remain pingable for up to ~90 s during a graceful soft shutdown
        # so we must not treat that as "still online" prematurely — hence the
        # poll uses consecutive offline confirmations before setting the flag.
        offline_grace = 600
        offline_deadline = time.time() + total_wait_time + offline_grace
        log.info(
            "Waiting up to %d min for LPAR to go offline "
            "(period:%s = %d s + %d s grace)",
            (total_wait_time + offline_grace) // 60,
            self.bootme_period, total_wait_time, offline_grace
        )
        went_offline = False
        consecutive_offline = 0
        while time.time() < offline_deadline:
            if not self.is_system_online():
                consecutive_offline += 1
                # Require two consecutive offline polls (20 s apart) to
                # confirm the LPAR is genuinely down and not mid-ARP-cache.
                if consecutive_offline >= 2:
                    went_offline = True
                    break
            else:
                consecutive_offline = 0
            time.sleep(10)
        if not went_offline:
            self.fail(
                "System did not go offline within %d minutes after "
                "'htxcmdline -bootme on mode:%s period:%s' — "
                "bootme status was confirmed ON but no reboot occurred. "
                "Expected %d reboot cycle(s), completed 0."
                % ((total_wait_time + offline_grace) // 60,
                   self.bootme_mode, self.bootme_period, self.boot_count)
            )

        completed_reboots = 0
        for i in range(self.boot_count):
            start_time = time.time()
            if not self.wait_for_reboot_completion(self.cv_HOST.ip):
                self.fail(
                    "System did not come back online after reboot cycle %d "
                    "of %d within the timeout. "
                    "Expected %d reboot cycle(s), completed %d."
                    % (i + 1, self.boot_count, self.boot_count,
                       completed_reboots)
                )
            # Re-establish SSH — wait_for_reboot_completion already applied
            # settle time; get_ssh_connection is safe to call now.
            self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

            # --- Wait for HTX to resume the MDT on host ---
            cmd = 'htxcmdline -query  -mdt %s' % self.mdt_file
            # Use a wider window (30 attempts × 20 s = 10 min) to allow
            # the HTX autostart service time to activate after a slow boot.
            for j in range(30):
                res = self.con.run_command_ignore_fail(cmd, timeout=60)
                if any(HTX_MDT_DIR in line for line in res):
                    log.debug("HTX MDT active after %d poll(s)", j + 1)
                    break
                time.sleep(20)
                log.debug("HTX MDT start still in progress (poll %d/30)",
                          j + 1)
            else:
                self.fail(
                    "HTX MDT '%s' did not become active within 10 minutes "
                    "after reboot cycle %d. HTX autostart may have failed."
                    % (self.mdt_file, i + 1)
                )
            self.con.run_command(cmd)

            # --- Check error log on host ---
            htxerr_file = self.con.run_command('wc -c %s' % HTX_ERR_FILE)
            if int(htxerr_file[0].split()[0]) != 0:
                self.fail("check error logs for exact error and failure")

            # --- NIC-specific: verify peer HTX and network after reboot ---
            if self.current_test_case == "HtxBootme_NicDevices":
                # Reconnect SSH to peer in case the connection timed out
                # during the host reboot window.
                self.ssh = OpTestSSH(self.peer_ip, self.peer_user,
                                     self.peer_password)
                self.ssh.set_system(self.conf.system())

                # Peer HTX should still be running (peer did not reboot).
                # Verify net.mdt is active on the peer.
                log.info("Cycle %d: verifying HTX still running on peer",
                         i + 1)
                peer_res = self.ssh.run_command_ignore_fail(cmd, timeout=60)
                if not any(HTX_MDT_DIR in line for line in peer_res):
                    self.fail("HTX net.mdt not running on peer after "
                              "host reboot (cycle %d)" % (i + 1))

                # Verify the HTX network is still up on both sides.
                log.info("Cycle %d: verifying pingum on host and peer",
                         i + 1)
                host_pingum = self.con.run_command('pingum')
                if not any("All networks ping Ok" in line
                           for line in host_pingum):
                    self.fail("pingum on host failed after reboot "
                              "(cycle %d)\npingum output:\n%s"
                              % (i + 1, "\n".join(host_pingum)))
                log.info("Cycle %d: pingum on host OK", i + 1)

                peer_pingum = self.ssh.run_command('pingum')
                if not any("All networks ping Ok" in line
                           for line in peer_pingum):
                    self.fail("pingum on peer failed after reboot "
                              "(cycle %d)\npingum output:\n%s"
                              % (i + 1, "\n".join(peer_pingum)))
                log.info("Cycle %d: pingum on peer OK", i + 1)

            completed_reboots += 1
            log.info("Reboot cycle %d of %d completed successfully"
                     % (completed_reboots, self.boot_count))
            reboot_time = time.time() - start_time
            remaining_wait_time = total_wait_time - reboot_time
            if remaining_wait_time > 0 and i < (self.boot_count - 1):
                log.info("Waiting for next reboot cycle")
                time.sleep(remaining_wait_time)

        if completed_reboots != self.boot_count:
            self.fail(
                "Bootme reboot cycle count mismatch: "
                "expected %d, completed %d."
                % (self.boot_count, completed_reboots)
            )
        log.info("Htx Bootme test is completed: %d of %d reboot cycle(s) "
                 "passed." % (completed_reboots, self.boot_count))

    def is_system_online(self):
        """
        This function pings to the host ip and checks system's availability.

        Uses a platform-portable success check: any line containing both
        "2" and "received" (covers Linux "2 received", macOS
        "2 packets received") is treated as a successful ping round.

        :return: True if the system is pinging.
                 False if system is not pinging.
        """
        cmd = ["ping", "-c", "2", self.cv_HOST.ip]
        i_try = 3
        while i_try != 0:
            ping = subprocess.Popen(cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    universal_newlines=True,
                                    encoding='utf-8')
            stdout_value, stderr_value = ping.communicate()
            # Match both Linux ("2 received") and macOS ("2 packets received").
            # A non-zero received count means the host is reachable.
            m = _PING_RECEIVED_RE.search(stdout_value)
            if m and int(m.group(1)) > 0:
                return True
            time.sleep(2)
            i_try -= 1
        return False

    def wait_for_reboot_completion(self, ip_addr, timeout=2700):
        """
        Wait for the system to become available after reboot.

        Three-phase check:
          1. Offline confirmation: wait until ping stops responding so we
             do not poll a still-running system and mistake stale ARP for
             a completed reboot.
          2. Ping: confirms the network stack is back up after boot.
             The Phase 2 deadline is anchored to the LPAR going offline, not
             to when this method is called, so time spent in Phase 1 is counted
             against the overall budget.  If the system comes back before Phase 1
             exhausts its 180 s window the ping loop exits immediately — no
             unnecessary waiting.
          3. SSH probe: confirms sshd is accepting connections.  This is
             necessary because on this LPAR ping responds 30–60 s before
             sshd is ready due to the ibmvfc SAN scan + LVM assembly in
             dracut initramfs.  _SSH_DEADLINE_SECS (600 s) accommodates
             LPARs with dense device trees (many FC paths, NVMe namespaces).
        """
        interval = 30

        # Phase 1: confirm the LPAR has actually gone offline first.
        # Without this, a slow graceful shutdown can fool the ping loop
        # into thinking the system is already back up on stale ARP entries.
        #
        # The overall deadline is started HERE so Phase 1 time counts
        # against the total budget.  This prevents the Phase 2 window from
        # silently expanding when the caller already knows the LPAR is down.
        overall_deadline = time.time() + timeout

        offline_confirmed = False
        offline_wait = time.time() + 180
        while time.time() < offline_wait:
            if not self.is_system_online():
                offline_confirmed = True
                log.info("LPAR confirmed offline — starting boot poll")
                break
            time.sleep(10)
        if not offline_confirmed:
            # System never went offline — treat as already up (e.g. very
            # fast reboot or bootme fired earlier than expected).
            log.warning("LPAR did not go offline within 180 s — "
                        "assuming already rebooting; skipping offline phase")

        # Phase 2: wait for ping to succeed.
        # Poll until the LPAR responds or the overall deadline expires.
        # Break out immediately on the first successful ping so the test
        # does not wait unnecessarily when the LPAR recovers quickly.
        ping_ok = False
        while time.time() < overall_deadline:
            if self.is_system_online():
                log.info("System is pinging after %.0f s — "
                         "waiting for SSH to become ready",
                         timeout - (overall_deadline - time.time()))
                ping_ok = True
                break
            time.sleep(interval)
        if not ping_ok:
            log.warning("System did not respond to ping within %d s", timeout)
            return False

        # Phase 3: wait for SSH port 22 to accept connections.
        # Use _SSH_DEADLINE_SECS instead of the original hard-coded 300 s
        # to handle dense-device-tree LPARs with slow dracut SAN scan.
        ssh_deadline = time.time() + _SSH_DEADLINE_SECS
        while time.time() < ssh_deadline:
            try:
                s = socket.create_connection((ip_addr, 22), timeout=10)
                s.close()
                log.info("SSH port is open — applying %d s settle delay",
                         _SSH_SETTLE_SECS)
                # Allow sshd auth subsystem and HTX autostart service to
                # finish initialising before the caller calls get_ssh_connection.
                time.sleep(_SSH_SETTLE_SECS)
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                time.sleep(10)

        log.warning("SSH port did not open within %d s after ping",
                    _SSH_DEADLINE_SECS)
        return False

    def stop_htx_bootme(self):
        """
        Stop HTX bootme.

        htxcmdline exit codes relevant here:
          0  — bootme off completed successfully
          81 — bootme is already on  (should not appear here, but harmless)
          83 — autostart flag file missing (bootme was never persisted,
               or a prior run left it in a half-enabled state); treat as
               "already off" so the test does not fail on cleanup.
        """
        res = self.con.run_command_ignore_fail('htxcmdline -bootme off')
        output_text = ' '.join(res)
        if "bootme off is completed successfully" in output_text:
            return
        if "bootme is already off" in output_text:
            log.info("HTX bootme was already off — nothing to do")
            return
        if "bootme flag file" in output_text and "was missing" in output_text:
            log.warning(
                "HTX bootme flag file missing (exit 83) — bootme was not "
                "active; treating as already-off"
            )
            return
        self.fail("Failed to turn off HTX bootme. Output: %s" % res)

    def htx_stop(self):
        """
        Shutdown the mdt file and the htx daemon and set SMT to original value.
        Stop the HTX Run.
        """
        if self.current_test_case == "HtxBootme_BlockDevice":
            if self.is_block_device_active() is True:
                log.debug("suspending active block_devices")
                self.suspend_all_block_device()

        log.info("Stopping HTX on host via OpTestHTXUtil")
        self.htx.stop()

    def tearDown(self):
        """
        Ensure the SOL monitor thread is stopped after every test outcome
        (pass, error, or failure).  Called automatically by unittest.
        """
        if (hasattr(self, 'console_thread')
                and self.console_thread.is_alive()):
            self.console_thread.console_terminate()
            self.console_thread.join(timeout=70)


class HtxBootme_AllMdt(OpTestHtxBootmeIO, unittest.TestCase):
    """
    This Test case is to test Htx bootme on all mdt files mdt.all
    """

    def setUp(self):
        super(HtxBootme_AllMdt, self).setUp()

        self.current_test_case = "HtxBootme_AllMdt"
        self.time_unit = self.conf.args.time_unit
        if self.time_unit == 'm':
            self.time_limit = self.time_limit * 60
        elif self.time_unit == 'h':
            self.time_limit = self.time_limit * 3600
        else:
            self.fail(
                "running time unit is not proper, please pass as 'm' or 'h' ")

    def start_htx_run(self):
        super(HtxBootme_AllMdt, self).start_htx_run()

        log.debug("selecting the mdt file")
        cmd = "htxcmdline -select -mdt %s" % self.mdt_file
        self.con.run_command(cmd, timeout=30)

        log.debug("Activating the %s", self.mdt_file)
        cmd = "htxcmdline -activate -mdt %s" % self.mdt_file
        self.con.run_command(cmd)

        log.debug("Running the HTX ")
        cmd = "htxcmdline -run  -mdt %s" % self.mdt_file
        self.con.run_command(cmd)


class HtxBootme_BlockDevice(OpTestHtxBootmeIO, unittest.TestCase):
    """
    The Test case is to run Htx on Block Devices mdt.hd
    """
    def setUp(self):
        super(HtxBootme_BlockDevice, self).setUp()

        self.current_test_case = "HtxBootme_BlockDevice"
        self.mdt_file = getattr(self.conf.args, 'mdt_file', 'mdt.hd')
        self.block_devices = getattr(self.conf.args, 'htx_disks', 'all')

        # If block_devices is None or empty, fall back to 'all'.
        if not self.block_devices:
            self.block_devices = 'all'

        # self.all is derived from block_devices: no separate cfg arg needed.
        self.all = (self.block_devices.strip().lower() == 'all')

        if self.all:
            self.block_device = ""
        else:
            self.block_device = []
            for dev in self.block_devices.split():
                dev_base = self.ssh_host.run_command(
                    'basename $(realpath {})'.format(dev))[0]
                if 'dm' in dev_base:
                    dev_base = self.get_mpath_from_dm(dev_base)
                self.block_device.append(dev_base)
            self.block_device = " ".join(self.block_device)

    def start_htx_run(self):
        super(HtxBootme_BlockDevice, self).start_htx_run()

        if self.all or not self.block_device:
            devices_to_activate = ['all']
        else:
            if self.is_block_device_in_mdt() is False:
                self.fail(f"Block devices {self.block_device} are not available"
                          f"in {self.mdt_file}")
            devices_to_activate = self.block_device.split()

        log.debug("Starting HTX on block devices via OpTestHTXUtil: %s",
                  devices_to_activate)
        self.htx.start(block_devs=devices_to_activate, mdt=self.mdt_file)
        if not self.all:
            if self.is_block_device_active() is False:
                self.fail("Block devices failed to activate")

    def is_block_device_in_mdt(self):
        """
        Verify that all requested block devices appear in the MDT query output.

        Returns True if every device is present, False if any are missing.
        The caller is responsible for acting on a False return value.
        """
        log.debug(
            "Checking if block devices are present in %s", self.mdt_file)
        cmd = "htxcmdline -query -mdt %s" % self.mdt_file
        output = self.con.run_command(cmd)
        # Flatten list output to a single string for substring search.
        output_text = ' '.join(output)
        missing = []
        for dev in self.block_device.split():
            if dev not in output_text:
                missing.append(dev)
        if missing:
            log.warning(
                "Block device(s) %s not found in '%s' output",
                missing, self.mdt_file
            )
            return False
        log.debug("All block devices %s present in %s",
                  self.block_device, self.mdt_file)
        return True

    def suspend_all_block_device(self):
        """
        Suspend the Block devices, if active.
        """
        log.debug("suspending block_devices if any running")
        cmd = f"htxcmdline -suspend all  -mdt {self.mdt_file}"
        self.con.run_command(cmd)

    def is_block_device_active(self):
        """
        Verifies whether the block devices are active or not
        """
        log.debug("checking whether all block_devices are active ot not")
        cmd = f"htxcmdline -query {self.block_device} -mdt {self.mdt_file}"
        output = self.con.run_command(cmd)
        device_list = self.block_device.split(" ")
        active_devices = []
        for line in output:
            for dev in device_list:
                if dev in line and "ACTIVE" in line:
                    active_devices.append(dev)
        non_active_device = list(set(device_list) - set(active_devices))
        if non_active_device:
            return False
        log.debug(f"BLOCK DEVICES {self.block_device} ARE ACTIVE")
        return True

    def get_mpath_from_dm(self, dm_id):
        """
        Get the mpath name for given device mapper id

        :param dev_mapper: Input device mapper dm-x
        :return: mpath name like mpathx
        :rtype: str
        """
        cmd = "multipathd show maps format '%d %n'"
        try:
            mpaths = self.con.run_command(cmd)
        except process.CmdError as ex:
            raise MPException(f"Multipathd Command Failed : {ex} ")
        for mpath in mpaths:
            if dm_id in mpath:
                return mpath.split()[-1]


class HtxBootme_NicDevices(OpTestHtxBootmeIO, unittest.TestCase):
    """
    The Test case is to run htx bootme on Network device net.mdt
    """
    def setUp(self):
        super(HtxBootme_NicDevices, self).setUp()

        self.current_test_case = "HtxBootme_NicDevices"
        self.host_intfs = []
        self.peer_ip = self.conf.args.peer_public_ip
        self.peer_user = self.conf.args.peer_user
        self.peer_password = self.conf.args.peer_password
        devices = self.conf.args.htx_host_interfaces
        if devices:
            raw = self.ssh_host.run_command('ls /sys/class/net')
            interfaces = [intf for line in raw for intf in line.split()]
            for device in devices.split():
                if device in interfaces:
                    self.host_intfs.append(device)
                else:
                    self.fail("Please check the network device: %s" % device)
        self.peer_intfs = self.conf.args.peer_interfaces.split()
        self.mdt_file = self.conf.args.mdt_file
        self.query_cmd = "htxcmdline -query -mdt %s" % self.mdt_file

        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Flush out the ip addresses on host and peer before starting the test
        self.ip_restore_host()
        self.ip_restore_peer()

        # Get distro details of peer lpar
        self.get_peer_distro()
        self.get_peer_distro_version()

        self.peer_htx = OpTestHTXUtil(
            console=self.ssh,
            ssh_host=self.ssh,
            distro_name=self.peer_distro,
            distro_version=self.peer_distro_version,
            rpm_link=self.htx_rpm_link,
            run_time=self.time_limit,
        )

    def setup_htx(self):
        """
        Install HTX on both host and peer via OpTestHTXUtil.
        """
        log.info("Setting up HTX on host via OpTestHTXUtil")
        self.htx.install()
        log.info("Setting up HTX on peer via OpTestHTXUtil")
        self.peer_htx.install()

    def get_peer_distro(self):
        """
        Get the distro name that is installed on peer lpar
        """
        res = "\n".join(self.ssh.run_command("cat /etc/os-release"))
        if "Ubuntu" in res:
            self.peer_distro = "ubuntu"
        elif 'Red Hat' in res:
            self.peer_distro = "rhel"
        elif 'SLES' in res:
            self.peer_distro = "sles"
        else:
            self.peer_distro = "unknown"

    def get_peer_distro_version(self):
        """
        Get the distro version that is installed on peer lpar
        """
        res = self.ssh.run_command("cat /etc/os-release")
        for line in res:
            if 'VERSION_ID' in line:
                self.peer_distro_version = line.split('=')[1].strip('"').split('.')[0]

    def update_host_peer_names(self):
        """
        Update hostname & IP of both Host & Peer in /etc/hosts on both machines.
        """
        res = self.ssh_host.run_command("nslookup %s" % self.host_ip)
        self.host_name = re.search(r'name = (.+)\.', res[0]).group(1)
        res = self.ssh.run_command("nslookup %s" % self.peer_ip)
        self.peer_name = re.search(r'name = (.+)\.', res[0]).group(1)

        self.hosts_file = "/etc/hosts"

        log.info("Updating hostname of both Host & Peer in %s file", self.hosts_file)

        self.delete_unwanted_entries()

        # Update for Host
        existing_entries_host = set(self.ssh_host.run_command(f"cat {self.hosts_file}"))
        for ip, name in [(self.host_ip, self.host_name)]:
            line = f"{ip} {name}"
            if line not in existing_entries_host:
                log.info("Adding missing entry on Host: %s", line)
                self.ssh_host.run_command(f'echo "{line}" | sudo tee -a {self.hosts_file}')
            else:
                log.info("Entry exists on Host: %s", line)

        # Update for Peer
        existing_entries_peer = set(self.ssh.run_command(f"cat {self.hosts_file}"))
        for ip, name in [(self.peer_ip, self.peer_name)]:
            line = f"{ip} {name}"
            if line not in existing_entries_peer:
                log.info("Adding missing entry on Peer: %s", line)
                self.ssh.run_command(f'echo "{line}" | sudo tee -a {self.hosts_file}')
            else:
                log.info("Entry exists on Peer: %s", line)

    def delete_unwanted_entries(self):
        """
        Deletes entries from /etc/hosts that match 'netXX.XX' pattern based on host and peer IPs.
        """
        host_last_two = ".".join(self.host_ip.split(".")[-2:])
        peer_last_two = ".".join(self.peer_ip.split(".")[-2:])

        pattern_host = rf"net{host_last_two}"
        pattern_peer = rf"net{peer_last_two}"

        sed_command = f"sudo sed -i.bak -E '/{pattern_host}/d; /{pattern_peer}/d' {self.hosts_file}"

        # Run on host
        log.debug("Running on Host : %s" % sed_command)
        self.ssh_host.run_command(sed_command)

        # Run on peer
        log.debug("Running on Peer : %s" % sed_command)
        self.ssh.run_command(sed_command)

        log.info("Deletion complete.")

    def htx_configure_net(self):
        """
        Configure network topology for the HTX NIC run on host and peer.

        Runs ``build_net multisystem <peer_ip>`` (up to 3 attempts) then
        verifies connectivity by running ``pingum`` on both host and peer.

        ``pingum`` names its test networks after the peer IP octets
        (e.g. "101net35.61"), not after the interface name — so the only
        reliable pass signal is "All networks ping Ok" appearing in the
        output.  Both host and peer must report this before net.mdt starts.
        """
        log.debug("Setting up the Network configuration on Host and Peer")

        for i in range(3):
            output = self.con.run_command(
                "build_net multisystem %s" % self.peer_ip, timeout=900)
            if any("All networks ping Ok" in line for line in output):
                log.debug("build_net reported all networks ping Ok "
                          "(attempt %d)", i + 1)
                break
            log.debug("build_net attempt %d did not report all Ok, "
                      "retrying", i + 1)

        # --- pingum on host ---
        log.debug("Running pingum on host")
        host_pingum = self.con.run_command('pingum')
        if not any("All networks ping Ok" in line for line in host_pingum):
            self.fail("pingum on host did not report 'All networks ping Ok'\n"
                      "pingum output:\n%s" % "\n".join(host_pingum))
        log.info("pingum on host: All networks ping Ok")

        # --- pingum on peer ---
        log.debug("Running pingum on peer")
        peer_pingum = self.ssh.run_command('pingum')
        if not any("All networks ping Ok" in line for line in peer_pingum):
            self.fail("pingum on peer did not report 'All networks ping Ok'\n"
                      "pingum output:\n%s" % "\n".join(peer_pingum))
        log.info("pingum on peer: All networks ping Ok")

        log.info("HTX network configuration verified on host and peer — "
                 "host interfaces: %s  peer interfaces: %s",
                 self.host_intfs, self.peer_intfs)

    def start_htx_run(self):
        super(HtxBootme_NicDevices, self).start_htx_run()

        self.update_host_peer_names()
        self.htx_configure_net()
        log.debug("Running the HTX for %s on Host", self.mdt_file)
        cmd = "htxcmdline -run -mdt %s" % self.mdt_file
        self.con.run_command(cmd)

        log.debug("Running the HTX for %s on Peer", self.mdt_file)
        self.ssh.run_command(cmd)

    def htx_check(self):
        """
        Check HTX error logs and query active status for the declared
        host and peer test interfaces.
        """
        log.debug("Checking HTX error logs on host")
        file_size = self.ssh_host.run_command('wc -c %s' % HTX_ERR_FILE)
        if int(file_size[0].split()[0]) != 0:
            self.fail("HTX errors on host: check %s" % HTX_ERR_FILE)

        # Query HTX status for each declared host interface
        log.debug("Querying HTX status for host interfaces: %s",
                  self.host_intfs)
        for intf in self.host_intfs:
            cmd = "htxcmdline -query %s -mdt %s" % (intf, self.mdt_file)
            res = self.con.run_command(cmd)
            log.info("HTX status on host for %s: %s", intf,
                     " ".join(res).strip())

        # Query HTX status for each declared peer interface on the peer
        log.debug("Querying HTX status for peer interfaces: %s",
                  self.peer_intfs)
        for intf in self.peer_intfs:
            cmd = "htxcmdline -query %s -mdt %s" % (intf, self.mdt_file)
            res = self.ssh.run_command(cmd)
            log.info("HTX status on peer for %s: %s", intf,
                     " ".join(res).strip())

        time.sleep(60)

    def htx_stop(self):
        """
        Shutdown the mdt and the htx daemon on host and peer, then restore IP.
        """
        log.info("Stopping HTX on host via OpTestHTXUtil")
        self.htx.stop()

        log.info("Stopping HTX on peer via OpTestHTXUtil")
        self.peer_htx.stop()

        self.ip_restore_host()
        self.ip_restore_peer()

    def ip_restore_host(self):
        '''
        restoring ip for host
        '''
        for interface in self.host_intfs:
            cmd = "ip addr flush %s" % interface
            self.con.run_command(cmd)
            cmd = "ip link set dev %s up" % interface
            self.con.run_command(cmd)

    def ip_restore_peer(self):
        '''
        config ip for peer
        '''
        for interface in self.peer_intfs:
            cmd = "ip addr flush %s" % interface
            self.ssh.run_command(cmd)
            cmd = "ip link set dev %s up" % interface
            self.ssh.run_command(cmd)
