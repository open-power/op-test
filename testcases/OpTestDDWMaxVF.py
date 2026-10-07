#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
# [+] International Business Machines Corp.
# Author: Vaishnavi Bhat <vaishnavi@linux.ibm.com>
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

"""
OpTestDDWMaxVF - DDW Disable + HNV Max VF (10 migratable SR-IOV ports) Test
=============================================================================

Validates that DDW can be disabled on both the host and peer LPARs and that
the maximum number (10) of HNV (migratable SR-IOV) virtual-function logical
ports can be added, assigned IP addresses, and successfully flood-pinged
end-to-end.

Test flow
---------
1.  Add ``disable_ddw`` to the kernel command line on both host and peer LPARs
    and reboot (RHEL9/RHEL10: ``grubby``; SLES: ``/etc/default/grub`` +
    ``grub2-mkconfig``).
2.  Verify ``disable_ddw`` is present in ``/proc/cmdline`` and that
    ``dmesg | grep create-pe`` returns no output on both LPARs (DDW disabled).
3.  Add the maximum 10 HNV (migratable SR-IOV) logical ports on the **host**
    LPAR via ``chhwres`` issued over an SSH session to the HMC.
4.  Add the maximum 10 HNV logical ports on the **peer** LPAR via ``chhwres``.
5.  Assign a unique IP address to each of the 10 bond interfaces on the host.
6.  Assign a unique IP address to each of the 10 bond interfaces on the peer.
7.  Perform a flood ping (``ping -f``) from every host bond interface to the
    corresponding peer IP address and verify zero packet loss.
8.  Cleanup: remove all newly added HNV ports from both LPARs.

Configuration parameters (in .conf file under [op-test])
---------------------------------------------------------
host_ip               IP of the host LPAR (management / control-plane)
host_user             SSH user for host LPAR
host_password         SSH password for host LPAR
peer_public_ip        IP of the peer LPAR (management / control-plane)
peer_user             SSH user for peer LPAR
peer_password         SSH password for peer LPAR
hmc_ip                IP address of the HMC
hmc_username          HMC login user (default: hscroot)
hmc_password          HMC login password
sriov_adapter         Physical slot location of the SR-IOV adapter on host
                      (e.g. "U78DA.ND1.WZS00A8-P1-C7")
sriov_port            Physical port ID on the SR-IOV adapter for host HNV
                      (e.g. "0")
peer_sriov_adapter    Physical slot location of the SR-IOV adapter on peer
peer_sriov_port       Physical port ID on the SR-IOV adapter for peer HNV
backup_veth_vnetwork  Virtual Ethernet network name used as the HNV backup
                      device (e.g. "ETHERNET0")
flood_ping_count      Number of packets per flood-ping run (default: 1000)

IP addressing (auto-generated — no conf entries required)
---------------------------------------------------------
The test generates 10 private /30 subnet pairs automatically.  Each pair i
(i = 1 … 10) uses the address range:

    Network : 192.i.9.0/30
    Host    : 192.i.9.1/30   (assigned to the host bond interface)
    Peer    : 192.i.9.2/30   (assigned to the peer bond interface)

Example for i = 1 … 3:

    Pair 1 — host 192.1.9.1/30  ↔  peer 192.1.9.2
    Pair 2 — host 192.2.9.1/30  ↔  peer 192.2.9.2
    Pair 3 — host 192.3.9.1/30  ↔  peer 192.3.9.2

All 10 subnets are non-overlapping private ranges.  /30 provides exactly
two usable host addresses per subnet — one for the host bond, one for the
peer bond — which is the minimum required for a point-to-point link.
"""

import re
import time
import subprocess
import unittest

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
_REBOOT_TIMEOUT = 900
# Poll interval while waiting for reboot.
_REBOOT_POLL_INTERVAL = 30

# Maximum migratable (HNV) SR-IOV logical ports per LPAR.
_HNV_MAX_PORTS = 10
# Maximum non-migratable SR-IOV logical ports per LPAR.
# NOTE: the actual HMC limit depends on adapter model; 10 is used here as
# a conservative default matching the migratable limit.  Update when the
# non-migratable add path is implemented.
_SRIOV_MAX_PORTS = 10


class OpTestDDWMaxVF(unittest.TestCase):
    """
    Disable DDW on host and peer, add max (10) HNV migratable SR-IOV ports on
    both LPARs, assign IPs, and flood-ping across all 10 port pairs.
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
            self.fail("Platform does not support this test (requires ppc64le)")

        # Read configuration parameters
        self.host_ip = self.conf.args.host_ip
        self.host_user = self.conf.args.host_user
        self.host_password = self.conf.args.host_password
        self.peer_ip = self.conf.args.peer_public_ip
        self.peer_user = self.conf.args.peer_user
        self.peer_password = self.conf.args.peer_password

        # SR-IOV adapter / port (host)
        self.sriov_adapter = self.conf.args.sriov_adapter
        self.sriov_port = getattr(self.conf.args, 'sriov_port', '0')

        # SR-IOV adapter / port (peer)
        self.peer_sriov_adapter = self.conf.args.peer_sriov_adapter
        self.peer_sriov_port = getattr(self.conf.args, 'peer_sriov_port', '0')

        # HNV backup virtual Ethernet network — may differ per LPAR
        self.backup_veth_vnetwork = self.conf.args.backup_veth_vnetwork
        self.peer_backup_veth_vnetwork = getattr(
            self.conf.args, 'peer_backup_veth_vnetwork',
            self.backup_veth_vnetwork)

        # SR-IOV port type: True = migratable (HNV), False = non-migratable.
        # Read as a string from conf ("true"/"false") and convert to bool.
        _mig_raw = getattr(self.conf.args, 'migratable_sriov', 'true')
        self.migratable_sriov = str(_mig_raw).strip().lower() != 'false'

        # Flood-ping packet count
        self.flood_ping_count = int(
            getattr(self.conf.args, 'flood_ping_count', 1000))

        # Auto-generate 10 private /30 subnet pairs
        self.host_hnv_ips, self.peer_hnv_ips = self._generate_hnv_ips()

        # SSH connections — host LPAR
        self.ssh_host = OpTestSSH(self.host_ip, self.host_user,
                                  self.host_password)
        self.ssh_host.set_system(self.conf.system())

        # SSH connection — peer LPAR
        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Use the framework-built HMC object (cv_HMC) instead of a manually
        # constructed OpTestSSH; cv_HMC.run_command() is the same call but
        # already bound to the correct HMC connection.
        self.cv_HMC = self.cv_SYSTEM.hmc

        # Use system_name from conf directly; lssyscfg -r sys with no -m filter
        # returns all systems on the HMC, not necessarily the intended one.
        self.server = self.conf.args.system_name
        if not self.server:
            self.fail("system_name not set in conf")

        # peer_system_name is required when the peer LPAR lives on a different
        # managed system than the host; falls back to self.server if omitted.
        self.peer_server = getattr(
            self.conf.args, 'peer_system_name', None) or self.server

        # Detect host distro
        self.host_distro_name = self.util.distro_name()
        self.host_distro_version = self.util.get_distro_version().split('.')[0]

        # Detect peer distro
        self.get_peer_distro()
        self.get_peer_distro_version()

        # Both LPAR names come from conf; no SSH call to lparstat needed.
        self.host_lpar = self.conf.args.lpar_name
        self.peer_lpar = getattr(self.conf.args, 'peer_lpar_name', '').strip()
        if not self.host_lpar:
            self.fail("lpar_name not set in conf")
        if not self.peer_lpar:
            self.fail("peer_lpar_name not set in conf")

        # Resolve SR-IOV adapter IDs once at setUp time
        self.host_adapter_id = self._get_adapter_id(
            self.sriov_adapter, self.server)
        self.peer_adapter_id = self._get_adapter_id(
            self.peer_sriov_adapter, self.peer_server)

        # State tracking used by tearDown
        self._host_added_macs = []
        self._peer_added_macs = []

        log.info("Host LPAR: %s  Peer LPAR: %s  Server: %s",
                 self.host_lpar, self.peer_lpar, self.server)
        log.info("Host distro: %s%s  Peer distro: %s%s",
                 self.host_distro_name, self.host_distro_version,
                 self.peer_distro, self.peer_distro_version)

    def tearDown(self):
        """
        Cleanup handler that runs after every test outcome (pass or fail).

        Actions performed (each step is best-effort — failures are logged but
        do not suppress subsequent steps or mask the original test failure):

        1. Remove all HNV logical ports that were added on host and peer via
           ``chhwres -o r``.
        2. Flush IP addresses from any bond interfaces that are still up on
           both LPARs using ``ip addr flush``.
        """
        for label, lpar, server, adapter_id, macs, ssh_conn in [
            ("host", getattr(self, 'host_lpar', ''),
             getattr(self, 'server', ''),
             getattr(self, 'host_adapter_id', ''),
             getattr(self, '_host_added_macs', []),
             self.con),
            ("peer", getattr(self, 'peer_lpar', ''),
             getattr(self, 'peer_server', getattr(self, 'server', '')),
             getattr(self, 'peer_adapter_id', ''),
             getattr(self, '_peer_added_macs', []),
             self.ssh),
        ]:
            # Remove HNV ports added during the test
            for mac in macs:
                try:
                    port_id = self._get_logical_port_id(lpar, mac, server)
                    self._chhwres_remove(lpar, adapter_id, port_id, server)
                    log.info("tearDown: removed HNV port MAC %s from %s",
                             mac, label)
                except Exception as exc:
                    log.warning("tearDown: failed to remove HNV port MAC %s "
                                "from %s — %s", mac, label, exc)

            # Flush any leftover IP addresses from bond interfaces
            for mac in macs:
                try:
                    bond = self._get_hnv_bond(ssh_conn, mac)
                    ssh_conn.run_command("ip addr flush dev %s" % bond)
                    log.info("tearDown: flushed IPs from %s:%s", label, bond)
                except Exception as exc:
                    log.warning("tearDown: failed to flush IP on %s bond "
                                "for MAC %s — %s", label, mac, exc)

    # ------------------------------------------------------------------ #
    # Top-level test method                                                #
    # ------------------------------------------------------------------ #

    def runTest(self):
        """
        Full DDW-disable → HNV max-VF → flood-ping test sequence.

        Steps:
        1. Add disable_ddw on both LPARs and reboot.
        2. Verify disable_ddw is in /proc/cmdline and create-pe absent in dmesg.
        3. Add 10 HNV migratable SR-IOV ports on host and peer, assigning IPs
           to each bond as soon as it is added.
        4. Flood-ping across all 10 host–peer port pairs.
        """
        # Step 1: disable DDW on both sides, reboot
        self._disable_ddw_host()
        self._disable_ddw_peer()

        # Reconnect SSH after reboots
        log.info("Reconnecting SSH after DDW-disable reboots")
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Step 2: verify DDW is disabled on both LPARs
        self._verify_ddw_disabled_host()
        self._verify_ddw_disabled_peer()

        # Step 3: add max SR-IOV ports on host and peer (assigning IPs progressively)
        self.add_max_vf(migratable=self.migratable_sriov)

        # Step 4: flood-ping across all pairs
        self._flood_ping_all()

    # ------------------------------------------------------------------ #
    # DDW disable / enable helpers                                         #
    # ------------------------------------------------------------------ #

    def _is_rhel(self, distro_name):
        """Return True for RHEL / CentOS / Fedora distros."""
        return distro_name.lower() in ('rhel', 'redhat', 'centos', 'fedora')

    def _is_sles(self, distro_name):
        """Return True for SLES / openSUSE distros."""
        return distro_name.lower() in ('sles', 'suse')

    def _add_disable_ddw_rhel(self, ssh_conn):
        """
        Add ``disable_ddw`` to the kernel cmdline using ``grubby``
        (RHEL9 / RHEL10).
        """
        log.info("Adding disable_ddw via grubby")
        cmd = ("grubby --args='disable_ddw' "
               "--update-kernel=/boot/vmlinuz-$(uname -r)")
        res = ssh_conn.run_command(cmd)
        log.debug("grubby --args output: %s", res)

    def _remove_disable_ddw_rhel(self, ssh_conn):
        """Remove ``disable_ddw`` from the kernel cmdline using ``grubby``."""
        log.info("Removing disable_ddw via grubby")
        cmd = ("grubby --remove-args='disable_ddw' "
               "--update-kernel=/boot/vmlinuz-$(uname -r)")
        res = ssh_conn.run_command(cmd)
        log.debug("grubby --remove-args output: %s", res)

    def _add_disable_ddw_sles(self, ssh_conn):
        """
        Add ``disable_ddw`` to ``GRUB_CMDLINE_LINUX_DEFAULT`` in
        ``/etc/default/grub`` and regenerate the GRUB config (SLES).
        """
        log.info("Adding disable_ddw to /etc/default/grub (SLES)")
        res = ssh_conn.run_command(
            "grep '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub")
        if not res:
            self.fail("Could not read GRUB_CMDLINE_LINUX_DEFAULT "
                      "from /etc/default/grub")
        current_line = res[0]
        if 'disable_ddw' in current_line:
            log.info("disable_ddw already present in "
                     "GRUB_CMDLINE_LINUX_DEFAULT")
            return
        new_line = re.sub(
            r'(GRUB_CMDLINE_LINUX_DEFAULT=")(.*?)(")',
            r'\g<1>\g<2> disable_ddw\g<3>',
            current_line
        )
        ssh_conn.run_command(
            "sed -i 's|^GRUB_CMDLINE_LINUX_DEFAULT=.*|%s|' "
            "/etc/default/grub" % new_line)
        log.info("Running grub2-mkconfig to apply changes")
        ssh_conn.run_command(
            "grub2-mkconfig -o /boot/grub2/grub.cfg", timeout=120)

    def _remove_disable_ddw_sles(self, ssh_conn):
        """
        Remove ``disable_ddw`` from ``GRUB_CMDLINE_LINUX_DEFAULT`` in
        ``/etc/default/grub`` and regenerate the GRUB config (SLES).
        """
        log.info("Removing disable_ddw from /etc/default/grub (SLES)")
        ssh_conn.run_command(
            r"sed -i 's/ disable_ddw//g; s/disable_ddw //g; "
            r"s/disable_ddw//g' /etc/default/grub")
        log.info("Running grub2-mkconfig to apply changes")
        ssh_conn.run_command(
            "grub2-mkconfig -o /boot/grub2/grub.cfg", timeout=120)

    def _reboot_and_wait(self, ssh_conn, ip_addr, label="host"):
        """
        Issue a reboot on *ssh_conn* and wait until the machine is back online.

        Uses ``OpTestUtil.wait_for`` to poll ``_is_host_online`` (checking SSH
        and ICMP ping) rather than an open-coded loop.

        :param ssh_conn:  active SSH connection used to issue the reboot.
        :param ip_addr:   IP address to poll while waiting for the reboot.
        :param label:     human-readable label used in log messages.
        :raises AssertionError: if the machine does not come back within
                                the configured timeout.
        """
        log.info("Rebooting %s (%s)", label, ip_addr)
        try:
            ssh_conn.run_command("reboot", timeout=10)
        except Exception:
            # Connection drop on reboot is expected — swallow and continue.
            pass

        log.info("Waiting %ds for %s to go offline, then polling (timeout=%ds)",
                 _REBOOT_SETTLE_WAIT, label, _REBOOT_TIMEOUT)
        result = self.util.wait_for(
            self._is_host_online,
            timeout=_REBOOT_TIMEOUT,
            first=_REBOOT_SETTLE_WAIT,
            step=_REBOOT_POLL_INTERVAL,
            text="Waiting for %s to come back online" % label,
            args=[ip_addr, ssh_conn],
        )
        if not result:
            self.fail("%s (%s) did not come back online within %ds after reboot"
                      % (label, ip_addr, _REBOOT_TIMEOUT))
        # Allow SSH daemon a moment to settle
        time.sleep(15)
        log.info("%s is back online", label)

    def _is_host_online(self, ip_addr, ssh_conn=None):
        """
        Return True if *ip_addr* is reachable via direct SSH or ICMP echo request.

        :param ip_addr: IP address string to check.
        :param ssh_conn: Optional OpTestSSH instance to probe direct SSH command.
        :rtype: bool
        """
        if ssh_conn is not None:
            try:
                ssh_conn.run_command_direct("uname -r", timeout=5)
                return True
            except Exception:
                pass

        result = subprocess.run(
            ["ping", "-c", "2", "-W", "5", ip_addr],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0

    # -- host DDW -------------------------------------------------------- #

    def _disable_ddw_host(self):
        """Add ``disable_ddw`` to host kernel cmdline and reboot if not already active."""
        log.info("=== Disabling DDW on host ===")
        cmdline = " ".join(self.con.run_command("cat /proc/cmdline"))
        if "disable_ddw" in cmdline:
            log.info("disable_ddw is already active in host /proc/cmdline; skipping reboot")
            return

        if self._is_rhel(self.host_distro_name):
            self._add_disable_ddw_rhel(self.con)
        elif self._is_sles(self.host_distro_name):
            self._add_disable_ddw_sles(self.con)
        else:
            self.fail("Unsupported host distro for DDW disable: %s"
                      % self.host_distro_name)
        self._reboot_and_wait(self.con, self.host_ip, label="host")

    def _enable_ddw_host(self):
        """Remove ``disable_ddw`` from host kernel cmdline and reboot if active."""
        log.info("=== Re-enabling DDW on host ===")
        cmdline = " ".join(self.con.run_command("cat /proc/cmdline"))
        if "disable_ddw" not in cmdline:
            log.info("disable_ddw is not active in host /proc/cmdline; skipping reboot")
            return

        if self._is_rhel(self.host_distro_name):
            self._remove_disable_ddw_rhel(self.con)
        elif self._is_sles(self.host_distro_name):
            self._remove_disable_ddw_sles(self.con)
        else:
            self.fail("Unsupported host distro for DDW enable: %s"
                      % self.host_distro_name)
        self._reboot_and_wait(self.con, self.host_ip, label="host")

    # -- peer DDW -------------------------------------------------------- #

    def _disable_ddw_peer(self):
        """Add ``disable_ddw`` to peer kernel cmdline and reboot if not already active."""
        log.info("=== Disabling DDW on peer ===")
        cmdline = " ".join(self.ssh.run_command("cat /proc/cmdline"))
        if "disable_ddw" in cmdline:
            log.info("disable_ddw is already active in peer /proc/cmdline; skipping reboot")
            return

        if self._is_rhel(self.peer_distro):
            self._add_disable_ddw_rhel(self.ssh)
        elif self._is_sles(self.peer_distro):
            self._add_disable_ddw_sles(self.ssh)
        else:
            self.fail("Unsupported peer distro for DDW disable: %s"
                      % self.peer_distro)
        self._reboot_and_wait(self.ssh, self.peer_ip, label="peer")

    def _enable_ddw_peer(self):
        """Remove ``disable_ddw`` from peer kernel cmdline and reboot if active."""
        log.info("=== Re-enabling DDW on peer ===")
        cmdline = " ".join(self.ssh.run_command("cat /proc/cmdline"))
        if "disable_ddw" not in cmdline:
            log.info("disable_ddw is not active in peer /proc/cmdline; skipping reboot")
            return

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

        ``grep`` exits with code 1 when it finds no matches.
        ``OpTestSSH.run_command_ignore_fail`` delegates to the pexpect
        console path which may return session-setup noise rather than a
        clean empty list.  To avoid false positives, when paramiko is
        available this helper opens a direct ``exec_command`` session to
        get the real exit status.  When paramiko is not available it falls
        back to ``run_command_ignore_fail`` with whitespace filtering.

        :param ssh_conn: ``OpTestSSH`` instance (``self.con`` or ``self.ssh``).
        :returns: list of non-blank lines that contain ``create-pe``.
        :rtype: list[str]
        """
        cmd = "dmesg | grep create-pe"

        if _HAS_PARAMIKO:
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
                    lines = stdout.read().decode(
                        "utf-8", errors="ignore").splitlines()
                else:
                    lines = []
            finally:
                client.close()
            return [line for line in lines if line.strip()]

        # Fallback: pexpect console path
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

    # ------------------------------------------------------------------ #
    # Peer distro detection (mirrored from OpTestDDWDisable)              #
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
    # HMC helpers — all HMC commands are issued over self.ssh_hmc         #
    # (OpTestSSH), exactly the same pattern used for host/peer commands.  #
    # ------------------------------------------------------------------ #

    def _hmc_run(self, cmd, timeout=120):
        """
        Run *cmd* on the HMC via ``self.cv_HMC`` and return the output lines.

        :param cmd:     Shell command string to execute on the HMC.
        :param timeout: Command timeout in seconds (default 120).
        :returns:       List of output lines from ``run_command``.
        :rtype:         list[str]
        """
        return self.cv_HMC.run_command(cmd, timeout=timeout)

    def _get_adapter_id(self, phys_loc, server):
        """
        Return the HMC ``adapter_id`` for the SR-IOV adapter at *phys_loc*.

        Queries ``lshwres -r sriov --rsubtype adapter`` on the HMC and matches
        the physical location code to extract the numeric adapter_id.

        :param phys_loc: Physical location code string (e.g.
                         ``"U78DA.ND1.WZS00A8-P1-C7"``).
        :param server:   Managed system name to query (host or peer).
        :raises AssertionError: if no adapter matches *phys_loc*.
        """
        out = self._hmc_run(
            "lshwres -m %s -r sriov --rsubtype adapter "
            "-F phys_loc:adapter_id" % server)
        for line in out:
            if phys_loc in line:
                return line.split(':')[-1].strip()
        self.fail("SR-IOV adapter not found at slot '%s' on server '%s'"
                  % (phys_loc, server))

    def _count_sriov_ports(self, lpar, server, migratable=True):
        """
        Return the current count of SR-IOV logical ports on *lpar*.

        Queries ``lshwres -r sriov --rsubtype logport`` on the HMC and counts
        lines where ``migratable`` equals ``1`` (HNV) or ``0`` (non-migratable)
        depending on the *migratable* argument.

        :param lpar:       Partition name string.
        :param server:     Managed system name to query (host or peer).
        :param migratable: ``True`` to count migratable (HNV) ports;
                           ``False`` to count non-migratable ports.
        :rtype: int
        """
        flag = '1' if migratable else '0'
        out = self._hmc_run(
            'lshwres -r sriov --rsubtype logport -m %s '
            '--level eth --filter "lpar_names=%s" -F migratable'
            % (server, lpar))
        return sum(1 for line in out if line.strip() == flag)

    def _get_latest_port_mac(self, lpar, server, known_macs, migratable=True):
        """
        Return the MAC address of the most recently added SR-IOV logical port
        on *lpar* that is not already in *known_macs*.

        Queries ``lshwres`` for ``mac_addr,migratable`` pairs and walks the
        list in reverse (newest entry last).  Only ports whose ``migratable``
        flag matches the *migratable* argument are considered.

        :param lpar:       Partition name string.
        :param server:     Managed system name to query (host or peer).
        :param known_macs: List of MAC strings already tracked (no colons).
        :param migratable: ``True`` to match migratable (HNV) ports;
                           ``False`` to match non-migratable ports.
        :raises AssertionError: if no new matching MAC is found.
        """
        flag = '1' if migratable else '0'
        out = self._hmc_run(
            'lshwres -r sriov --rsubtype logport -m %s '
            '--level eth --filter "lpar_names=%s" -F mac_addr,migratable'
            % (server, lpar))
        for line in reversed(out):
            parts = line.strip().split(',')
            if len(parts) == 2 and parts[1].strip() == flag:
                mac = parts[0].strip().replace(':', '')
                if mac not in known_macs:
                    return mac
        self.fail("Could not determine MAC of newly added HNV port on %s"
                  % lpar)

    def _get_logical_port_id(self, lpar, mac, server):
        """
        Return the ``logical_port_id`` for the migratable port identified by
        *mac* on *lpar*.

        Queries ``lshwres`` and greps for the line that matches both the LPAR
        name and the MAC.  Column index 6 (0-based) of the comma-separated
        output holds ``logical_port_id=<value>``.

        :param lpar:   Partition name string.
        :param mac:    MAC address string (no colons, lower-case).
        :param server: Managed system name to query (host or peer).
        :rtype: str
        """
        out = self._hmc_run(
            "lshwres -r sriov --rsubtype logport -m %s "
            "--level eth | grep %s | grep %s" % (server, lpar, mac))
        # The joined output contains the matching CSV line; column 6 is
        # "logical_port_id=<value>".
        line = " ".join(out).strip()
        return line.split(',')[6].split('=')[-1]

    def _chhwres_add(self, lpar, server, adapter_id, phys_port, migratable=True,
                     backup_veth_vnetwork=None):
        """
        Add one SR-IOV logical port on *lpar* via the HMC.

        The HMC auto-assigns the MAC address (no ``mac_addr=`` attribute is
        passed so the firmware picks one).

        **Migratable (HNV) path** — ``migratable=True`` (default):
            Issues ``chhwres`` with ``migratable=1``,
            ``backup_device_type=veth`` and ``backup_veth_vnetwork``.
            This is the live SR-IOV / HNV logical port type.

        **Non-migratable path** — ``migratable=False``:
            Not yet implemented.  Raises ``NotImplementedError`` so the
            caller gets a clear signal rather than a silent wrong command.
            Fill in the correct ``chhwres`` attribute string when ready.

        :param lpar:                 Partition name string.
        :param server:               Managed system name (host or peer).
        :param adapter_id:           Numeric adapter_id from
                                     ``_get_adapter_id()``.
        :param phys_port:            Physical port ID string (e.g. ``"0"``).
        :param migratable:           ``True`` for HNV / migratable port
                                     (default); ``False`` for non-migratable
                                     port (not yet implemented).
        :param backup_veth_vnetwork: Virtual Ethernet network name for the
                                     backup device.  When ``None``, falls back
                                     to ``self.backup_veth_vnetwork``.
        :raises NotImplementedError: when ``migratable=False``.
        :raises AssertionError:      if the HMC command reports an error.
        """
        vnet = backup_veth_vnetwork or self.backup_veth_vnetwork
        if migratable:
            cmd = (
                'chhwres -r sriov -m %s --rsubtype logport '
                '-o a -p %s -a "adapter_id=%s,phys_port_id=%s,'
                'logical_port_type=eth,migratable=1,'
                'backup_device_type=veth,backup_veth_vnetwork=%s"'
                % (server, lpar, adapter_id, phys_port, vnet)
            )
        else:
            # TODO: fill in the correct chhwres attribute string for
            # non-migratable SR-IOV logical ports and remove this error.
            raise NotImplementedError(
                "_chhwres_add: non-migratable SR-IOV add is not yet "
                "implemented.  Add the chhwres attribute string here."
            )
        out = self._hmc_run(cmd, timeout=120)
        log.debug("chhwres add [%s] migratable=%s: %s", lpar, migratable, out)

    def _chhwres_remove(self, lpar, adapter_id, logical_port_id, server):
        """
        Remove a migratable HNV logical port identified by *logical_port_id*.

        Issues ``chhwres -r sriov -o r`` on the HMC.  Failures are logged as
        warnings rather than hard failures so that tearDown can attempt to
        clean up remaining ports.

        :param lpar:            Partition name string.
        :param adapter_id:      Numeric adapter_id from ``_get_adapter_id()``.
        :param logical_port_id: Port ID returned by ``_get_logical_port_id()``.
        :param server:          Managed system name (host or peer).
        """
        cmd = (
            'chhwres -r sriov -m %s --rsubtype logport '
            '-o r -p %s -a "adapter_id=%s,logical_port_id=%s"'
            % (server, lpar, adapter_id, logical_port_id)
        )
        try:
            out = self._hmc_run(cmd, timeout=120)
            log.debug("chhwres remove [%s]: %s", lpar, out)
        except Exception as exc:
            log.warning("chhwres remove failed on %s port %s — %s",
                        lpar, logical_port_id, exc)

    # ------------------------------------------------------------------ #
    # add_max_vf — add SR-IOV ports (migratable or non-migratable)        #
    # ------------------------------------------------------------------ #

    def add_max_vf(self, migratable=True):
        """
        Add the maximum number of SR-IOV logical ports on both host and peer
        LPARs via the HMC.

        For each port added:
        1. Waits for the corresponding bond interface to appear on the OS.
        2. Immediately assigns the IP and brings the bond up using nmcli (if
           NetworkManager is active) or ip commands as fallback.

        :param migratable: ``True`` for HNV / migratable ports (default);
                           ``False`` for non-migratable SR-IOV ports.
        :type migratable: bool
        """
        port_limit = _HNV_MAX_PORTS if migratable else _SRIOV_MAX_PORTS
        port_type = "migratable (HNV)" if migratable else "non-migratable"

        for label, lpar, server, adapter_id, phys_port, backup_vnet, added_macs_attr, ssh_conn, ip_list in [
            ("host", self.host_lpar, self.server, self.host_adapter_id,
             self.sriov_port, self.backup_veth_vnetwork, '_host_added_macs',
             self.con, self.host_hnv_ips),
            ("peer", self.peer_lpar, self.peer_server, self.peer_adapter_id,
             self.peer_sriov_port, self.peer_backup_veth_vnetwork,
             '_peer_added_macs', self.ssh, ["%s/30" % ip for ip in self.peer_hnv_ips]),
        ]:
            added_macs = getattr(self, added_macs_attr)
            existing = self._count_sriov_ports(lpar, server, migratable=migratable)
            log.info("add_max_vf [%s]: existing %s ports = %d",
                     label, port_type, existing)

            # If existing ports are already present, assign IPs to their bonds
            if existing > 0:
                current_macs = self._list_sriov_macs(lpar, server, migratable=migratable)
                for idx, mac in enumerate(current_macs[:existing]):
                    if mac not in added_macs:
                        added_macs.append(mac)
                    if idx < len(ip_list):
                        cidr = ip_list[idx]
                        bond = self._get_hnv_bond(ssh_conn, mac, timeout=60)
                        self._configure_bond_ip(ssh_conn, bond, cidr, label=label)

            to_add = port_limit - existing
            if to_add <= 0:
                log.warning("add_max_vf [%s]: already at %d %s ports "
                            "— skipping add", label, existing, port_type)
                continue

            log.info("add_max_vf [%s]: adding %d %s port(s) to reach "
                     "limit of %d", label, to_add, port_type, port_limit)
            for i in range(to_add):
                self._chhwres_add(lpar, server, adapter_id, phys_port,
                                  migratable=migratable,
                                  backup_veth_vnetwork=backup_vnet)
                mac = self._get_latest_port_mac(lpar, server, added_macs,
                                                migratable=migratable)
                added_macs.append(mac)
                log.info("add_max_vf [%s]: added %s port %d/%d  MAC=%s",
                         label, port_type, i + 1, to_add, mac)

                # Locate bond immediately and assign IP as soon as it is added
                port_idx = len(added_macs) - 1
                if port_idx < len(ip_list):
                    cidr = ip_list[port_idx]
                    bond = self._get_hnv_bond(ssh_conn, mac, timeout=90)
                    self._configure_bond_ip(ssh_conn, bond, cidr, label=label)
                    log.info("[%s] Bond %s (%s) assigned IP %s (port %d/%d)",
                             label, bond, mac, cidr, port_idx + 1, port_limit)

            final_count = self._count_sriov_ports(lpar, server, migratable=migratable)
            if final_count != port_limit:
                self.fail(
                    "add_max_vf [%s]: expected %d %s ports after add, "
                    "got %d" % (label, port_limit, port_type, final_count))
            log.info("add_max_vf [%s]: %d %s ports present and configured",
                     label, final_count, port_type)

    # ------------------------------------------------------------------ #
    # IP address generation                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _generate_hnv_ips():
        """
        Generate 10 private /30 subnet pairs for host and peer HNV bonds.

        Subnet scheme for pair index i (1-based, i = 1 … 10):

            Network : 192.i.9.0/30
            Host    : 192.i.9.1  (CIDR: "192.i.9.1/30")
            Peer    : 192.i.9.2  (bare IP: "192.i.9.2")

        :returns: Tuple of (host_ips, peer_ips), each a list of 10 strings.
                  ``host_ips`` are CIDR strings; ``peer_ips`` are bare IPs.
        :rtype: tuple[list[str], list[str]]
        """
        host_ips = []
        peer_ips = []
        for i in range(1, _HNV_MAX_PORTS + 1):
            host_ips.append("192.%d.9.1/30" % i)
            peer_ips.append("192.%d.9.2" % i)
        return host_ips, peer_ips

    # ------------------------------------------------------------------ #
    # IP assignment helpers                                                #
    # ------------------------------------------------------------------ #

    def _is_networkmanager_running(self, ssh_conn):
        """
        Return True if NetworkManager is running and responsive on *ssh_conn*.

        :param ssh_conn: OpTestSSH connection.
        :rtype: bool
        """
        try:
            out = ssh_conn.run_command("systemctl is-active NetworkManager", timeout=10)
            if any("active" in line for line in out):
                return True
        except Exception:
            pass

        try:
            out = ssh_conn.run_command("nmcli general status", timeout=10)
            if any("running" in line.lower() for line in out):
                return True
        except Exception:
            pass

        return False

    def _configure_bond_ip(self, ssh_conn, bond, cidr, label=""):
        """
        Assign *cidr* to *bond* and bring it up.

        Uses ``nmcli c mod id <bond> ipv4.method manual ipv4.address <cidr>``
        and ``nmcli c up <bond>`` if NetworkManager is running. Otherwise
        falls back to ``ip addr replace`` and ``ip link set ... up``.

        :param ssh_conn: OpTestSSH connection to the target LPAR.
        :param bond:     Bond interface / connection name.
        :param cidr:     IP address with prefix length (e.g. ``"192.1.9.1/30"``).
        :param label:    LPAR label for logging.
        """
        nm_active = self._is_networkmanager_running(ssh_conn)
        if nm_active:
            log.info("[%s] NetworkManager is active; configuring %s with nmcli", label, bond)
            try:
                ssh_conn.run_command(
                    "nmcli c mod id %s ipv4.method manual ipv4.addresses %s" % (bond, cidr),
                    timeout=30
                )
                ssh_conn.run_command("nmcli c up %s" % bond, timeout=30)
                log.info("[%s] nmcli configured and brought up %s with %s", label, bond, cidr)
                return
            except Exception as exc:
                log.warning("[%s] nmcli command failed for %s (%s); falling back to ip command",
                            label, bond, exc)

        # Fallback or when NetworkManager is not running (e.g. wicked/systemd-networkd)
        ssh_conn.run_command("ip addr replace %s dev %s" % (cidr, bond), timeout=20)
        ssh_conn.run_command("ip link set dev %s up" % bond, timeout=20)
        log.info("[%s] ip command configured and brought up %s with %s", label, bond, cidr)

    def _get_hnv_bond(self, ssh_conn, mac, timeout=90):
        """
        Return the kernel bond interface name whose MAC matches *mac*.

        Polls ``/sys/class/net/bonding_masters`` and compares each bond's MAC
        (from sysfs ``address`` or slave interface addresses) against *mac*
        (normalised to lower-case no-colon form).

        :param ssh_conn: OpTestSSH connection to the target LPAR.
        :param mac:      MAC address string (with or without colons).
        :param timeout:  Maximum seconds to wait for the bond interface to appear.
        :raises AssertionError: if no matching bond is found within timeout.
        """
        mac_norm = mac.lower().replace(':', '')
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                masters_raw = ssh_conn.run_command(
                    "cat /sys/class/net/bonding_masters", timeout=10)
                masters = " ".join(masters_raw).split()
                for bond in masters:
                    try:
                        out = ssh_conn.run_command(
                            "cat /sys/class/net/%s/address" % bond, timeout=10)
                        bond_mac = " ".join(out).strip().lower().replace(':', '')
                        if bond_mac == mac_norm:
                            return bond

                        # Check slave interfaces under this bond
                        slaves_raw = ssh_conn.run_command(
                            "cat /sys/class/net/%s/bonding/slaves" % bond, timeout=10)
                        for slave in " ".join(slaves_raw).split():
                            slave_out = ssh_conn.run_command(
                                "cat /sys/class/net/%s/address" % slave, timeout=10)
                            slave_mac = " ".join(slave_out).strip().lower().replace(':', '')
                            if slave_mac == mac_norm:
                                return bond
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(3)

        self.fail("No bond interface found for MAC %s within %ds" % (mac, timeout))

    # ------------------------------------------------------------------ #
    # Flood ping                                                           #
    # ------------------------------------------------------------------ #

    def _flood_ping_all(self):
        """
        Flood-ping from each host bond interface to the corresponding peer IP.

        Uses ``ping -f -c <count> -I <bond> <peer_ip>`` issued from the host
        LPAR.  Parses the ``% packet loss`` summary line; fails if any pair
        reports non-zero loss.  All pairs are tested before reporting failures
        so that a single bad interface does not hide others.
        """
        log.info("Starting flood-ping across %d HNV port pairs "
                 "(%d packets each)", _HNV_MAX_PORTS, self.flood_ping_count)
        macs = (self._host_added_macs if self._host_added_macs
                else self._list_sriov_macs(self.host_lpar, self.server))

        failures = []
        for idx, mac in enumerate(macs[:_HNV_MAX_PORTS]):
            bond = self._get_hnv_bond(self.con, mac)
            peer_target = self.peer_hnv_ips[idx]
            cmd = ("ping -f -c %d -I %s %s"
                   % (self.flood_ping_count, bond, peer_target))
            log.info("Flood-ping [%d/%d]: %s -> %s",
                     idx + 1, _HNV_MAX_PORTS, bond, peer_target)
            try:
                out = self.con.run_command(cmd, timeout=120)
                output_str = " ".join(out)
                match = re.search(r'(\d+)%\s+packet\s+loss', output_str)
                if match:
                    loss = int(match.group(1))
                    if loss != 0:
                        msg = ("Flood-ping %s -> %s: %d%% packet loss"
                               % (bond, peer_target, loss))
                        log.error(msg)
                        failures.append(msg)
                    else:
                        log.info("Flood-ping %s -> %s: 0%% packet loss — OK",
                                 bond, peer_target)
                else:
                    log.warning("Could not parse packet-loss from ping "
                                "output on %s -> %s:\n%s",
                                bond, peer_target, output_str)
            except Exception as exc:
                msg = ("Flood-ping %s -> %s raised exception: %s"
                       % (bond, peer_target, exc))
                log.error(msg)
                failures.append(msg)

        if failures:
            self.fail("Flood-ping failures (%d/%d):\n%s"
                      % (len(failures), _HNV_MAX_PORTS,
                         "\n".join(failures)))
        log.info("All %d flood-ping checks passed", _HNV_MAX_PORTS)

    # ------------------------------------------------------------------ #
    # Utility helpers                                                      #
    # ------------------------------------------------------------------ #

    def _list_sriov_macs(self, lpar, server, migratable=True):
        """
        Return MAC addresses of all currently present SR-IOV logical ports on
        *lpar* that match the requested *migratable* type.

        Used as a fallback inside ``_assign_ips_host``, ``_assign_ips_peer``
        and ``_flood_ping_all`` when the LPAR already had ports before
        ``add_max_vf`` ran (so ``_host_added_macs`` / ``_peer_added_macs``
        would otherwise be empty).

        :param lpar:       Partition name string.
        :param server:     Managed system name to query (host or peer).
        :param migratable: ``True`` to return migratable (HNV) port MACs;
                           ``False`` to return non-migratable port MACs.
        :rtype: list[str]
        """
        flag = '1' if migratable else '0'
        out = self._hmc_run(
            'lshwres -r sriov --rsubtype logport -m %s '
            '--level eth --filter "lpar_names=%s" -F mac_addr,migratable'
            % (server, lpar))
        macs = []
        for line in out:
            parts = line.strip().split(',')
            if len(parts) == 2 and parts[1].strip() == flag:
                macs.append(parts[0].strip().replace(':', ''))
        return macs
