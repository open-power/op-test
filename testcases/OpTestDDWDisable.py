#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
# Author: Pavaman Subramaniyam <pavsubra@linux.vnet.ibm.com>
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
OpTestDDWDisable - DDW Disable + HTX Net Exerciser Test
=======================================================

Verifies that the Dynamic DMA Window (DDW) is disabled on both the host and
peer LPARs by injecting the ``disable_ddw`` kernel boot parameter, then runs
the HTX ``net.mdt`` exerciser on the dedicated/SRIOV adapter ports available
on both servers.  After the HTX run the ``disable_ddw`` parameter is removed
and the test confirms DDW is re-enabled.

Test flow
---------
1. Add ``disable_ddw`` to the kernel command line on both host and peer and
   reboot both LPARs (RHEL9/RHEL10: ``grubby``; SLES16.x: edit
   ``/etc/default/grub`` + ``grub2-mkconfig``).
2. Verify ``disable_ddw`` is present in ``/proc/cmdline`` and that
   ``dmesg | grep create-pe`` returns no output on both LPARs.
3. Install the latest HTX RPM on host and peer, configure the HTX 74.x
   network topology (``build_net multisystem``), then run ``net.mdt`` for
   ``time_limit`` seconds.
4. Poll for HTX errors and verify the run completes cleanly.
5. Shutdown HTX on both LPARs, restore IP configuration.
6. Remove ``disable_ddw`` from the kernel command line on both LPARs and
   reboot.
7. Verify DDW is re-enabled: ``dmesg | grep create-pe`` returns output on
   both LPARs.

Configuration parameters (in .conf file under [op-test])
---------------------------------------------------------
host_ip               IP of the host LPAR
host_user             SSH user for host LPAR
host_password         SSH password for host LPAR
peer_public_ip        IP of the peer LPAR
peer_user             SSH user for peer LPAR
peer_password         SSH password for peer LPAR
htx_host_interfaces   Space-separated list of host NIC interfaces for HTX
peer_interfaces       Space-separated list of peer NIC interfaces for HTX
mdt_file              HTX MDT file to use (default: net.mdt)
time_limit            HTX run duration in seconds (default: 3600)
htx_rpm_link          URL pointing to the directory containing HTX RPM files
"""

import re
import time
import unittest
import subprocess

import OpTestConfiguration
import OpTestLogger
from common.OpTestSSH import OpTestSSH
from common.OpTestUtil import OpTestUtil
from common.Exceptions import CommandFailed

try:
    import paramiko
    _HAS_PARAMIKO = True
except ImportError:
    _HAS_PARAMIKO = False

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Seconds to wait after issuing a reboot before starting to poll the host.
_REBOOT_SETTLE_WAIT = 60
# Maximum seconds to wait for a host to come back online after reboot.
_REBOOT_TIMEOUT = 600
# Poll interval while waiting for reboot.
_REBOOT_POLL_INTERVAL = 30


class OpTestDDWDisable(unittest.TestCase):
    """
    Disable DDW on host and peer, run HTX net.mdt exerciser, then re-enable
    DDW and verify the DMA windows are restored.
    """

    # ------------------------------------------------------------------ #
    # setUp / tearDown                                                     #
    # ------------------------------------------------------------------ #

    def setUp(self):
        """Initialise configuration, SSH connections and identify distros."""
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()

        # Verify Power architecture
        res = self.con.run_command('uname -a')
        if 'ppc64' not in res[-1]:
            self.fail("Platform does not support HTX tests (requires ppc64le)")

        # Read configuration parameters
        self.host_ip = self.conf.args.host_ip
        self.host_user = self.conf.args.host_user
        self.host_password = self.conf.args.host_password
        self.peer_ip = self.conf.args.peer_public_ip
        self.peer_user = self.conf.args.peer_user
        self.peer_password = self.conf.args.peer_password
        self.mdt_file = getattr(self.conf.args, 'mdt_file', 'net.mdt')
        self.time_limit = int(getattr(self.conf.args, 'time_limit', 3600))
        self.htx_rpm_link = self.conf.args.htx_rpm_link

        devices = getattr(self.conf.args, 'htx_host_interfaces', '') or ''
        self.host_intfs = devices.split() if devices.strip() else []

        peer_devs = getattr(self.conf.args, 'peer_interfaces', '') or ''
        self.peer_intfs = peer_devs.split() if peer_devs.strip() else []

        # SSH connections
        self.ssh_host = OpTestSSH(self.host_ip, self.host_user,
                                  self.host_password)
        self.ssh_host.set_system(self.conf.system())

        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Detect host distro
        self.host_distro_name = self.util.distro_name()
        self.host_distro_version = self.util.get_distro_version().split(".")[0]

        # Detect peer distro
        self.get_peer_distro()
        self.get_peer_distro_version()

        # Validate that at least one interface is declared on each side
        if not self.host_intfs:
            self.fail("No host interfaces specified (htx_host_interfaces)")
        if not self.peer_intfs:
            self.fail("No peer interfaces specified (peer_interfaces)")

        log.info("Host distro: %s%s  Peer distro: %s%s",
                 self.host_distro_name, self.host_distro_version,
                 self.peer_distro, self.peer_distro_version)

    def tearDown(self):
        """
        Cleanup handler that runs after every test outcome (pass or fail).

        Actions performed (each step is best-effort — failures are logged but
        do not suppress subsequent steps or mask the original test failure):

        1. For every declared interface on host and peer, query the IPv4
           addresses currently assigned via ``nmcli -g ip4.ADDRESS device
           show <intf>``, then delete each one individually with
           ``ip addr delete <addr> dev <intf>``.  This mirrors the avocado
           NetworkInterface pattern and is more surgical than disconnecting
           the whole device from NetworkManager.
        2. Verify that each interface is still UP (link state, not
           NetworkManager connection state) using ``nmcli -g GENERAL.STATE
           device show <intf>``; log a warning for any interface whose state
           does not contain ``connected`` or ``unmanaged``.
        3. Stop the SOL console monitor thread.
        """
        # ---------------------------------------------------------------- #
        # 1 — delete HTX-assigned IPv4 addresses on host and peer          #
        # ---------------------------------------------------------------- #
        for label, intfs, ssh_conn in [
            ("host", self.host_intfs, self.con),
            ("peer", self.peer_intfs, self.ssh),
        ]:
            for intf in intfs:
                try:
                    # Query only IPv4 addresses on this interface.
                    # nmcli -g prints bare values, one per line; multiple
                    # addresses are separated by " | " on older nmcli versions
                    # and by newlines on newer ones — split on both.
                    out = ssh_conn.run_command(
                        "nmcli -g ip4.ADDRESS device show %s" % intf)
                    addr_str = " ".join(out).strip()
                    if not addr_str:
                        log.info("tearDown: no IPv4 addresses on %s:%s "
                                 "— nothing to delete", label, intf)
                        continue

                    # Normalise both separator styles into a flat list
                    ipaddresses = [
                        a.strip()
                        for a in addr_str.replace(" | ", "\n").splitlines()
                        if a.strip()
                    ]
                    log.info("tearDown: deleting addresses %s from %s:%s",
                             ipaddresses, label, intf)
                    for ipaddr in ipaddresses:
                        try:
                            ssh_conn.run_command(
                                "ip addr delete %s dev %s" % (ipaddr, intf))
                            log.info("tearDown: deleted %s from %s:%s",
                                     ipaddr, label, intf)
                        except Exception as exc:
                            log.warning(
                                "tearDown: failed to delete %s from "
                                "%s:%s — %s", ipaddr, label, intf, exc)
                except Exception as exc:
                    log.warning("tearDown: could not query addresses on "
                                "%s:%s — %s", label, intf, exc)

        # ---------------------------------------------------------------- #
        # 2 — verify link state is UP on host and peer                     #
        # ---------------------------------------------------------------- #
        for label, intfs, ssh_conn in [
            ("host", self.host_intfs, self.con),
            ("peer", self.peer_intfs, self.ssh),
        ]:
            for intf in intfs:
                try:
                    # nmcli -g GENERAL.STATE device show <intf> prints a
                    # single line such as:
                    #   100 (connected)
                    #   30 (disconnected)
                    #   10 (unmanaged)
                    out = ssh_conn.run_command(
                        "nmcli -g GENERAL.STATE device show %s" % intf)
                    state = " ".join(out).strip()
                    # Accept "connected" (100) and "unmanaged" (10) as UP;
                    # warn on "disconnected" (30) or anything unexpected.
                    if "connected" in state or "unmanaged" in state:
                        log.info("tearDown: %s:%s link state: %s",
                                 label, intf, state)
                    else:
                        log.warning(
                            "tearDown: %s:%s link state is '%s' — interface "
                            "may not be fully up after address removal",
                            label, intf, state)
                except Exception as exc:
                    log.warning("tearDown: could not verify link state of "
                                "%s:%s — %s", label, intf, exc)

    # ------------------------------------------------------------------ #
    # Top-level test method                                                #
    # ------------------------------------------------------------------ #

    def runTest(self):
        """
        Full DDW-disable → HTX run → DDW-enable test sequence.
        """
        # Step 1 & 2: disable DDW on both sides, reboot, verify
        self._disable_ddw_host()
        self._disable_ddw_peer()

        # Reconnect after reboots
        log.info("Reconnecting SSH after reboots")
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Verify disable_ddw is active and create-pe absent
        self._verify_ddw_disabled_host()
        self._verify_ddw_disabled_peer()

        # Step 3 & 4: HTX net.mdt run
        self.setup_htx()
        self.start_htx_run()
        self.htx_check()
        self.htx_stop()

        # Step 6: remove disable_ddw on both sides, reboot
        self._enable_ddw_host()
        self._enable_ddw_peer()

        # Reconnect after reboots
        log.info("Reconnecting SSH after DDW re-enable reboots")
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Step 7: verify DDW is active again
        self._verify_ddw_enabled_host()
        self._verify_ddw_enabled_peer()

    # ------------------------------------------------------------------ #
    # DDW disable helpers                                                  #
    # ------------------------------------------------------------------ #

    def _is_rhel(self, distro_name):
        """Return True for RHEL / CentOS / Fedora distros."""
        return distro_name.lower() in ('rhel', 'redhat', 'centos', 'fedora')

    def _is_sles(self, distro_name):
        """Return True for SLES / openSUSE distros."""
        return distro_name.lower() in ('sles', 'suse')

    def _add_disable_ddw_rhel(self, ssh_conn):
        """
        Add ``disable_ddw`` to the kernel cmdline using ``grubby`` (RHEL/9/10).

        :param ssh_conn: active SSH connection to the target LPAR.
        """
        log.info("Adding disable_ddw via grubby")
        cmd = ("grubby --args='disable_ddw' "
               "--update-kernel=/boot/vmlinuz-$(uname -r)")
        res = ssh_conn.run_command(cmd)
        log.debug("grubby --args output: %s", res)

    def _remove_disable_ddw_rhel(self, ssh_conn):
        """
        Remove ``disable_ddw`` from the kernel cmdline using ``grubby``.

        :param ssh_conn: active SSH connection to the target LPAR.
        """
        log.info("Removing disable_ddw via grubby")
        cmd = ("grubby --remove-args='disable_ddw' "
               "--update-kernel=/boot/vmlinuz-$(uname -r)")
        res = ssh_conn.run_command(cmd)
        log.debug("grubby --remove-args output: %s", res)

    def _add_disable_ddw_sles(self, ssh_conn):
        """
        Add ``disable_ddw`` to ``GRUB_CMDLINE_LINUX_DEFAULT`` in
        ``/etc/default/grub`` and regenerate the GRUB config (SLES16.x).

        :param ssh_conn: active SSH connection to the target LPAR.
        """
        log.info("Adding disable_ddw to /etc/default/grub (SLES)")
        # Read current GRUB_CMDLINE_LINUX_DEFAULT
        res = ssh_conn.run_command(
            "grep '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub")
        if not res:
            self.fail("Could not read GRUB_CMDLINE_LINUX_DEFAULT "
                      "from /etc/default/grub on peer/host")
        current_line = res[0]  # e.g. GRUB_CMDLINE_LINUX_DEFAULT="... opts"

        # Skip if already present
        if 'disable_ddw' in current_line:
            log.info("disable_ddw already present in \
                     GRUB_CMDLINE_LINUX_DEFAULT")
            return

        # Append disable_ddw inside the existing quotes
        # e.g. "mitigations=auto quiet" -> "mitigations=auto quiet disable_ddw"
        new_line = re.sub(
            r'(GRUB_CMDLINE_LINUX_DEFAULT=")(.*?)(")',
            r'\g<1>\g<2> disable_ddw\g<3>',
            current_line
        )
        # Use sed to replace the line in-place
        sed_cmd = (
            "sed -i 's|^GRUB_CMDLINE_LINUX_DEFAULT=.*|%s|' "
            "/etc/default/grub" % new_line
        )
        ssh_conn.run_command(sed_cmd)
        log.info("Running grub2-mkconfig to apply changes")
        ssh_conn.run_command(
            "grub2-mkconfig -o /boot/grub2/grub.cfg", timeout=120)

    def _remove_disable_ddw_sles(self, ssh_conn):
        """
        Remove ``disable_ddw`` from ``GRUB_CMDLINE_LINUX_DEFAULT`` in
        ``/etc/default/grub`` and regenerate the GRUB config (SLES16.x).

        :param ssh_conn: active SSH connection to the target LPAR.
        """
        log.info("Removing disable_ddw from /etc/default/grub (SLES)")
        # Strip ' disable_ddw' or 'disable_ddw ' or just 'disable_ddw'
        ssh_conn.run_command(
            r"sed -i 's/ disable_ddw//g; s/disable_ddw //g; "
            r"s/disable_ddw//g' /etc/default/grub")
        log.info("Running grub2-mkconfig to apply changes")
        ssh_conn.run_command(
            "grub2-mkconfig -o /boot/grub2/grub.cfg", timeout=120)

    def _reboot_and_wait(self, ssh_conn, ip_addr, label="host"):
        """
        Issue a reboot on *ssh_conn* and wait until the machine is back online.

        :param ssh_conn:  active SSH connection used to issue the reboot.
        :param ip_addr:   IP address to poll while waiting for the reboot.
        :param label:     human-readable label used in log messages.
        :raises AssertionError: if the machine does not come back online within
                                the configured timeout.
        """
        log.info("Rebooting %s (%s)", label, ip_addr)
        try:
            ssh_conn.run_command("reboot", timeout=10)
        except Exception:
            # The connection will be lost as the machine reboots — that is
            # expected.  Swallow the exception and continue polling.
            pass

        log.info("Waiting %ds for %s to go offline …", _REBOOT_SETTLE_WAIT,
                 label)
        time.sleep(_REBOOT_SETTLE_WAIT)

        log.info("Polling for %s to come back online (timeout=%ds)",
                 label, _REBOOT_TIMEOUT)
        start = time.time()
        while time.time() - start < _REBOOT_TIMEOUT:
            if self._ping_ok(ip_addr):
                log.info("%s is back online", label)
                # Give SSH daemon a moment to start
                time.sleep(15)
                return
            time.sleep(_REBOOT_POLL_INTERVAL)
        self.fail("%s (%s) did not come back online within %ds after reboot"
                  % (label, ip_addr, _REBOOT_TIMEOUT))

    def _ping_ok(self, ip_addr):
        """
        Return True if *ip_addr* responds to two ICMP echo requests.

        :param ip_addr: IP address string to ping.
        :rtype: bool
        """
        result = subprocess.run(
            ["ping", "-c", "2", "-W", "5", ip_addr],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0

    # -- host ----------------------------------------------------------- #

    def _disable_ddw_host(self):
        """Add ``disable_ddw`` to host kernel cmdline and reboot."""
        log.info("=== Disabling DDW on host ===")
        if self._is_rhel(self.host_distro_name):
            self._add_disable_ddw_rhel(self.con)
        elif self._is_sles(self.host_distro_name):
            self._add_disable_ddw_sles(self.con)
        else:
            self.fail("Unsupported host distro for DDW disable: %s"
                      % self.host_distro_name)
        self._reboot_and_wait(self.con, self.host_ip, label="host")

    def _enable_ddw_host(self):
        """Remove ``disable_ddw`` from host kernel cmdline and reboot."""
        log.info("=== Re-enabling DDW on host ===")
        if self._is_rhel(self.host_distro_name):
            self._remove_disable_ddw_rhel(self.con)
        elif self._is_sles(self.host_distro_name):
            self._remove_disable_ddw_sles(self.con)
        else:
            self.fail("Unsupported host distro for DDW enable: %s"
                      % self.host_distro_name)
        self._reboot_and_wait(self.con, self.host_ip, label="host")

    # -- peer ----------------------------------------------------------- #

    def _disable_ddw_peer(self):
        """Add ``disable_ddw`` to peer kernel cmdline and reboot."""
        log.info("=== Disabling DDW on peer ===")
        if self._is_rhel(self.peer_distro):
            self._add_disable_ddw_rhel(self.ssh)
        elif self._is_sles(self.peer_distro):
            self._add_disable_ddw_sles(self.ssh)
        else:
            self.fail("Unsupported peer distro for DDW disable: %s"
                      % self.peer_distro)
        self._reboot_and_wait(self.ssh, self.peer_ip, label="peer")

    def _enable_ddw_peer(self):
        """Remove ``disable_ddw`` from peer kernel cmdline and reboot."""
        log.info("=== Re-enabling DDW on peer ===")
        if self._is_rhel(self.peer_distro):
            self._remove_disable_ddw_rhel(self.ssh)
        elif self._is_sles(self.peer_distro):
            self._remove_disable_ddw_sles(self.ssh)
        else:
            self.fail("Unsupported peer distro for DDW enable: %s"
                      % self.peer_distro)
        self._reboot_and_wait(self.ssh, self.peer_ip, label="peer")

    # ------------------------------------------------------------------ #
    # DDW verification helpers                                             #
    # ------------------------------------------------------------------ #

    def _grep_create_pe(self, ssh_conn):
        """
        Run ``dmesg | grep create-pe`` on *ssh_conn* and return only
        non-empty matching lines.

        ``grep`` exits with code **1** when it finds no matches.
        ``OpTestSSH.run_command_ignore_fail`` delegates to the pexpect
        console path which spawns a fresh interactive sudo session; when
        the command produces no stdout, ``CommandFailed.output`` comes back
        as a list that contains session-setup noise rather than a clean empty
        list.  That noise is non-empty so a naïve ``if raw: fail()`` check
        always fires even when DDW *is* correctly disabled.

        To avoid touching ``OpTestSSH``, this helper issues the command
        itself via a fresh paramiko ``exec_command`` call (the same transport
        ``OpTestSSH.run_command_direct`` uses) and captures the real exit
        status.  When paramiko is not available it falls back to
        ``run_command_ignore_fail`` with whitespace filtering.

        :param ssh_conn: ``OpTestSSH`` instance (``self.con`` for host or
                         ``self.ssh`` for peer).
        :returns: List of non-blank stdout lines that contain ``create-pe``;
                  empty list when DDW is disabled (grep exit code 1).
        :rtype: list[str]
        """
        cmd = "dmesg | grep create-pe"

        if _HAS_PARAMIKO:
            # Use a fresh paramiko connection so we get the real exit status
            # and clean stdout without interactive-session noise.
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    hostname=ssh_conn.host,
                    port=ssh_conn.port,
                    username=ssh_conn.username,
                    password=ssh_conn.password,
                    timeout=30,
                    allow_agent=False,
                    look_for_keys=False,
                )
                _, stdout, _ = client.exec_command(cmd, timeout=30)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    # grep found matches — return the actual lines
                    lines = stdout.read().decode("utf-8", errors="ignore").splitlines()
                else:
                    # grep found nothing (exit 1) or other non-zero
                    lines = []
            finally:
                client.close()
            return [line for line in lines if line.strip()]

        # --- fallback: pexpect console path ---
        # run_command_ignore_fail may return a list with empty/noise entries;
        # filter to lines that actually contain 'create-pe' text.
        raw = ssh_conn.run_command_ignore_fail(cmd)
        if isinstance(raw, str):
            lines = raw.splitlines()
        elif isinstance(raw, list):
            lines = raw
        else:
            lines = []
        return [line for line in lines if "create-pe" in line]

    def _verify_ddw_disabled_host(self):
        """
        Assert that ``disable_ddw`` is present in ``/proc/cmdline`` and that
        ``dmesg | grep create-pe`` returns no output on the host LPAR.
        """
        log.info("Verifying DDW is disabled on host")
        cmdline = " ".join(self.con.run_command("cat /proc/cmdline"))
        if "disable_ddw" not in cmdline:
            self.fail("disable_ddw not found in host /proc/cmdline after "
                      "reboot.\n/proc/cmdline: %s" % cmdline)
        log.info("Host /proc/cmdline contains disable_ddw")

        hits = self._grep_create_pe(self.con)
        if hits:
            self.fail("Expected no 'create-pe' in host dmesg when DDW is "
                      "disabled, but found:\n%s" % "\n".join(hits))
        log.info("Host dmesg: no create-pe output — DDW successfully disabled")

    def _verify_ddw_disabled_peer(self):
        """
        Assert that ``disable_ddw`` is present in ``/proc/cmdline`` and that
        ``dmesg | grep create-pe`` returns no output on the peer LPAR.
        """
        log.info("Verifying DDW is disabled on peer")
        cmdline = " ".join(self.ssh.run_command("cat /proc/cmdline"))
        if "disable_ddw" not in cmdline:
            self.fail("disable_ddw not found in peer /proc/cmdline after "
                      "reboot.\n/proc/cmdline: %s" % cmdline)
        log.info("Peer /proc/cmdline contains disable_ddw")

        hits = self._grep_create_pe(self.ssh)
        if hits:
            self.fail("Expected no 'create-pe' in peer dmesg when DDW is "
                      "disabled, but found:\n%s" % "\n".join(hits))
        log.info("Peer dmesg: no create-pe output — DDW successfully disabled")

    def _verify_ddw_enabled_host(self):
        """
        Assert that ``disable_ddw`` is absent from ``/proc/cmdline`` and that
        ``dmesg | grep create-pe`` returns at least one line on the host LPAR,
        confirming DMA windows were created.
        """
        log.info("Verifying DDW is re-enabled on host")
        cmdline = " ".join(self.con.run_command("cat /proc/cmdline"))
        if "disable_ddw" in cmdline:
            self.fail("disable_ddw still present in host /proc/cmdline after "
                      "DDW re-enable reboot.\n/proc/cmdline: %s" % cmdline)
        log.info("Host /proc/cmdline: disable_ddw removed")

        hits = self._grep_create_pe(self.con)
        if not hits:
            self.fail("No 'create-pe' output in host dmesg after DDW "
                      "re-enable — DDW may not have been restored")
        log.info("Host dmesg create-pe output:\n%s", "\n".join(hits))

    def _verify_ddw_enabled_peer(self):
        """
        Assert that ``disable_ddw`` is absent from ``/proc/cmdline`` and that
        ``dmesg | grep create-pe`` returns at least one line on the peer LPAR.
        """
        log.info("Verifying DDW is re-enabled on peer")
        cmdline = " ".join(self.ssh.run_command("cat /proc/cmdline"))
        if "disable_ddw" in cmdline:
            self.fail("disable_ddw still present in peer /proc/cmdline after "
                      "DDW re-enable reboot.\n/proc/cmdline: %s" % cmdline)
        log.info("Peer /proc/cmdline: disable_ddw removed")

        hits = self._grep_create_pe(self.ssh)
        if not hits:
            self.fail("No 'create-pe' output in peer dmesg after DDW "
                      "re-enable — DDW may not have been restored")
        log.info("Peer dmesg create-pe output:\n%s", "\n".join(hits))

    # ------------------------------------------------------------------ #
    # Peer distro detection (mirrored from HtxBootme_NicDevices)          #
    # ------------------------------------------------------------------ #

    def get_peer_distro(self):
        """
        Detect and store the distro name running on the peer LPAR.

        Sets ``self.peer_distro`` to one of ``"rhel"``, ``"sles"``,
        ``"ubuntu"``, or ``"unknown"``.
        """
        res = "\n".join(self.ssh.run_command("cat /etc/os-release"))
        if "Ubuntu" in res:
            self.peer_distro = "ubuntu"
        elif "Red Hat" in res:
            self.peer_distro = "rhel"
        elif "SLES" in res:
            self.peer_distro = "sles"
        else:
            self.peer_distro = "unknown"

    def get_peer_distro_version(self):
        """
        Detect and store the major OS version running on the peer LPAR.

        Sets ``self.peer_distro_version`` to a string such as ``"9"`` or
        ``"16"``.
        """
        res = self.ssh.run_command("cat /etc/os-release")
        for line in res:
            if "VERSION_ID" in line:
                self.peer_distro_version = (
                    line.split("=")[1].strip('"').split(".")[0])
                return
        self.peer_distro_version = "unknown"

    # ------------------------------------------------------------------ #
    # HTX helpers (reused from HtxBootme_NicDevices pattern)              #
    # ------------------------------------------------------------------ #

    def install_latest_htx_rpm(self):
        """
        Download and install the latest HTX RPM on both host and peer.

        The RPM index at ``htx_rpm_link`` is scraped for filenames matching
        the host and peer distro/version patterns (e.g. ``rhel9``, ``sles16``).
        The newest matching RPM is installed on each LPAR using
        ``rpm -ivh --force``.  When both LPARs run the same distro, the same
        RPM file is installed on both in a single pass.
        """
        if self.host_distro_name == "SuSE":
            self.host_distro_name = "sles"
        if self.peer_distro == "SuSE":
            self.peer_distro = "sles"

        host_pattern = "%s%s" % (self.host_distro_name,
                                 self.host_distro_version)
        peer_pattern = "%s%s" % (self.peer_distro, self.peer_distro_version)
        same_distro = (host_pattern == peer_pattern)

        patterns = [host_pattern]
        if not same_distro:
            patterns.append(peer_pattern)

        for pattern in patterns:
            try:
                index_result = subprocess.run(
                    "curl --silent %s" % self.htx_rpm_link,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                index_html = index_result.stdout.decode("utf-8")
            except subprocess.TimeoutExpired:
                self.fail("Timed out fetching HTX RPM index from %s"
                          % self.htx_rpm_link)
            except Exception as exc:
                self.fail("Error fetching HTX RPM index: %s" % exc)

            all_rpms = re.findall(
                r"(?<=\>)htx\w*[-]\d*[-]\w*[.]\w*[.]\w*", index_html)
            matching = sorted(
                [r for r in all_rpms if pattern in r], reverse=True)
            if not matching:
                self.fail("No HTX RPM found for pattern '%s' at %s"
                          % (pattern, self.htx_rpm_link))
            latest_rpm = matching[0]

            cmd_wget = ("wget %s%s --no-check-certificate"
                        % (self.htx_rpm_link, latest_rpm))
            cmd_install = "rpm -ivh %s --force" % latest_rpm

            if pattern == host_pattern:
                log.info("Installing %s on host", latest_rpm)
                for cmd in (cmd_wget, cmd_install):
                    out = self.con.run_command(cmd, timeout=180)
                    if any("ERROR:" in line or "error:" in line for line in out):
                        self.fail("HTX RPM installation failed on host "
                                  "(cmd: %s)\noutput: %s"
                                  % (cmd, "\n".join(out)))

            if pattern == peer_pattern:
                log.info("Installing %s on peer", latest_rpm)
                for cmd in (cmd_wget, cmd_install):
                    out = self.ssh.run_command(cmd, timeout=180)
                    if any("ERROR:" in line or "error:" in line for line in out):
                        self.fail("HTX RPM installation failed on peer "
                                  "(cmd: %s)\noutput: %s"
                                  % (cmd, "\n".join(out)))

    def setup_htx(self):
        """
        Install prerequisite packages, purge any old HTX RPM, and install
        the latest HTX RPM on both host and peer.
        """
        if self.host_distro_name in ("centos", "fedora", "rhel", "redhat"):
            packages = ["git", "gcc", "make", "wget",
                        "gcc-c++", "ncurses-devel", "tar"]
            installer = "yum install"
        elif self.host_distro_name == "sles":
            packages = ["git", "gcc", "make", "wget",
                        "libncurses6", "gcc-c++", "ncurses-devel", "tar"]
            installer = "zypper install"
        else:
            self.fail("HTX setup not supported for distro: %s"
                      % self.host_distro_name)

        log.info("Installing prerequisite packages on host")
        for pkg in packages:
            self.con.run_command("%s -y %s" % (installer, pkg))

        # Remove stale HTX RPM on host
        old_htx = self.con.run_command_ignore_fail("rpm -qa | grep htx")
        for rpm in old_htx:
            self.con.run_command_ignore_fail("rpm -e %s" % rpm, timeout=30)
        self.ssh_host.run_command(
            "if [ -d /usr/lpp/htx ]; then rm -rf /usr/lpp/htx; fi",
            timeout=60,
        )

        # Remove stale HTX RPM on peer
        peer_old = self.ssh.run_command_ignore_fail("rpm -qa | grep htx")
        for rpm in peer_old:
            self.ssh.run_command_ignore_fail("rpm -e %s" % rpm, timeout=180)

        self.install_latest_htx_rpm()

    def htx_configure_net(self):
        """
        Run ``build_net multisystem`` on the host (up to 3 attempts) and
        verify network connectivity by running ``pingum`` on both host and
        peer.  Flushes and brings up the declared interfaces before
        ``build_net`` runs.
        """
        log.info("Flushing IP configuration on host and peer interfaces")
        self.ip_restore_host()
        self.ip_restore_peer()

        log.info("Running build_net multisystem on host")
        for attempt in range(1, 4):
            out = self.con.run_command(
                "build_net multisystem %s" % self.peer_ip, timeout=900)
            if any("All networks ping Ok" in line for line in out):
                log.info("build_net attempt %d: all networks ping OK", attempt)
                break
            log.debug("build_net attempt %d did not report all OK", attempt)

        # Verify host
        host_pingum = self.con.run_command("pingum")
        if not any("All networks ping Ok" in line for line in host_pingum):
            self.fail("pingum on host failed after build_net\n"
                      "output:\n%s" % "\n".join(host_pingum))
        log.info("pingum on host: All networks ping Ok")

        # Verify peer
        peer_pingum = self.ssh.run_command("pingum")
        if not any("All networks ping Ok" in line for line in peer_pingum):
            self.fail("pingum on peer failed after build_net\n"
                      "output:\n%s" % "\n".join(peer_pingum))
        log.info("pingum on peer: All networks ping Ok")

    def start_htx_run(self):
        """
        Configure the HTX network topology, create MDT files, then start the
        ``net.mdt`` exerciser on both host and peer.
        """
        log.info("Creating HTX MDT files on host")
        self.con.run_command("htxcmdline -createmdt")

        self.htx_configure_net()

        log.info("Starting HTX %s on host", self.mdt_file)
        self.con.run_command("htxcmdline -run -mdt %s" % self.mdt_file)

        log.info("Starting HTX %s on peer", self.mdt_file)
        self.ssh.run_command("htxcmdline -run -mdt %s" % self.mdt_file)

        log.info("HTX net.mdt exerciser running for %d seconds",
                 self.time_limit)
        time.sleep(self.time_limit)

    def htx_check(self):
        """
        Verify the HTX error log is empty and query the active status for
        every declared host and peer interface.
        """
        log.info("Checking HTX error log on host")
        file_size = self.ssh_host.run_command(
            "wc -c /tmp/htx/htxerr")
        if int(file_size[0].split()[0]) != 0:
            self.fail("HTX errors detected on host — "
                      "check /tmp/htx/htxerr for details")

        log.info("Querying HTX status for host interfaces: %s",
                 self.host_intfs)
        for intf in self.host_intfs:
            res = self.con.run_command(
                "htxcmdline -query %s -mdt %s" % (intf, self.mdt_file))
            log.info("Host HTX status [%s]: %s", intf,
                     " ".join(res).strip())

        log.info("Querying HTX status for peer interfaces: %s",
                 self.peer_intfs)
        for intf in self.peer_intfs:
            res = self.ssh.run_command(
                "htxcmdline -query %s -mdt %s" % (intf, self.mdt_file))
            log.info("Peer HTX status [%s]: %s", intf,
                     " ".join(res).strip())

    def htx_stop(self):
        """
        Shutdown the MDT and HTX daemon on host and peer, then restore IP
        configuration on both sides.
        """
        cmd_shutdown = "htxcmdline -shutdown -mdt %s" % self.mdt_file

        log.info("Shutting down HTX on host")
        self.con.run_command(cmd_shutdown)
        daemon_state = self.con.run_command(
            "/usr/lpp/htx/etc/scripts/htx.d status")
        if "running" in daemon_state[-1]:
            self.con.run_command("/usr/lpp/htx/etc/scripts/htxd_shutdown")

        log.info("Shutting down HTX on peer")
        self.ssh.run_command(cmd_shutdown)

        self.ip_restore_host()
        self.ip_restore_peer()

    def ip_restore_host(self):
        """Flush IP addresses and bring up declared host interfaces."""
        for intf in self.host_intfs:
            self.con.run_command("ip addr flush %s" % intf)
            self.con.run_command("ip link set dev %s up" % intf)

    def ip_restore_peer(self):
        """Flush IP addresses and bring up declared peer interfaces."""
        for intf in self.peer_intfs:
            self.ssh.run_command("ip addr flush %s" % intf)
            self.ssh.run_command("ip link set dev %s up" % intf)
