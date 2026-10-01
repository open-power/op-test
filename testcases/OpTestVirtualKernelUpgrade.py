#!/usr/bin/env python3
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

'''
OpTestVirtualKernelUpgrade
--------------------------

Verifies that ibmveth (veth) and ibmvnic (vnic) network interfaces retain
their names, MAC addresses, and IP addresses (when assigned) across a kernel
upgrade on a PowerVM LPAR.

Test Flow
~~~~~~~~~
1. Pre-upgrade snapshot
   - Enumerate all ibmveth/ibmvnic interfaces, recording their names, driver,
     MAC address, and IP address (if any).

2. Kernel upgrade
   - Install the kernel RPM specified by ``target_kernel_version`` from the
     conf file using the distro package manager (yum/dnf for RHEL,
     zypper for SLES).
   - Set the new kernel as the default boot entry via grubby/grub2-set-default.

3. Reboot and wait for OS
   - Issue a reboot (power off / on cycle via ``goto_state``).
   - Wait until the system is back at ``OpSystemState.OS``.

4. Post-upgrade verification
   - Confirm ``uname -r`` reports the newly installed kernel version.
   - Re-enumerate ibmveth/ibmvnic interfaces.
   - Assert that every interface name, MAC address, and IP address recorded
     in Step 1 is still present after the upgrade.

Configuration Parameters (conf file)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Required
--------
``target_kernel_version``
    Full kernel version string to install, e.g. ``5.14.0-427.31.1.el9_4.ppc64le``.
    The test constructs an install command using this string directly.

Optional
--------
``kernel_install_timeout``
    Seconds to allow for the kernel package install command (default: 600).

Supported platforms
~~~~~~~~~~~~~~~~~~~
``bmc_type = FSP_PHYP`` or ``bmc_type = EBMC_PHYP`` (HMC-managed PowerVM LPARs)

Usage
~~~~~
::

    ./op-test --config-file virtual_kernel_upgrade.conf \\
              --run testcases.OpTestVirtualKernelUpgrade.VirtualKernelUpgradeTest

Sample conf file (virtual_kernel_upgrade.conf)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    [op-test]
    bmc_type            = FSP_PHYP
    hmc_ip              = 192.168.10.1
    hmc_username        = hscroot
    hmc_password        = abc123
    system_name         = Server-9080-M9S-SN12345XY
    lpar_name           = my-test-lpar
    lpar_prof           = default
    host_ip             = 192.168.20.50
    host_user           = root
    host_password       = passw0rd
    target_kernel_version = 5.14.0-427.31.1.el9_4.ppc64le
    # kernel_install_timeout = 600
'''

import re
import time
import unittest

import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed
from common.OpTestUtil import OpTestUtil
from common.OpTestInstallUtil import InstallUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

_VIRTUAL_DRIVERS = ('ibmveth', 'ibmvnic')
_POST_BOOT_SETTLE = 30


class OpTestVirtualKernelUpgrade(unittest.TestCase):
    '''
    Base class: reads configuration, discovers virtual interfaces, performs
    the kernel upgrade, reboots, and validates interface integrity post-boot.
    '''

    @classmethod
    def setUpClass(cls):
        '''
        Resolve all required and optional configuration parameters.

        Raises:
            unittest.SkipTest: if the platform is not an HMC-managed LPAR.
            unittest.SkipTest: if ``target_kernel_version`` is not provided.
        '''
        conf = OpTestConfiguration.conf
        cls.conf = conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.cv_HMC = cls.cv_SYSTEM.hmc
        cls.bmc_type = conf.args.bmc_type

        if cls.bmc_type not in ('FSP_PHYP', 'EBMC_PHYP'):
            raise unittest.SkipTest(
                "OpTestVirtualKernelUpgrade is only supported on HMC-managed "
                "PowerVM LPARs (bmc_type = FSP_PHYP or EBMC_PHYP). "
                "Got: {}".format(cls.bmc_type)
            )

        raw_ver = getattr(conf.args, 'target_kernel_version', None)
        if not raw_ver:
            raise unittest.SkipTest(
                "Required parameter 'target_kernel_version' not provided. "
                "Add it to the conf file, e.g.:\n"
                "  target_kernel_version = 5.14.0-427.31.1.el9_4.ppc64le\n"
                "  (arch suffix and .rpm extension are stripped automatically)"
            )

        # Normalise the value so architecture suffixes and the .rpm extension
        # that users sometimes copy from an RPM filename are removed.
        #
        # Pattern removes, in order (both optional):
        #   1. a known arch token:  .ppc64le  .ppc64  .x86_64  .aarch64
        #                           .s390x  .noarch
        #   2. the .rpm extension
        #
        # Examples:
        #   6.4.0-150700.53.52.1.ppc64le.rpm  →  6.4.0-150700.53.52.1
        #   6.4.0-150700.53.52.1.ppc64le      →  6.4.0-150700.53.52.1
        #   5.14.0-427.31.1.el9_4.ppc64le     →  5.14.0-427.31.1.el9_4
        #   5.14.0-427.31.1.el9_4             →  5.14.0-427.31.1.el9_4 (unchanged)
        _strip_arch_rpm = re.compile(
            r'(?:\.(?:ppc64le|ppc64|x86_64|aarch64|s390x|noarch))?'
            r'(?:\.rpm)?$'
        )
        cls.target_kernel_version = _strip_arch_rpm.sub(
            '', raw_ver.strip())
        log.info(
            "target_kernel_version: raw='%s'  normalised='%s'",
            raw_ver.strip(), cls.target_kernel_version
        )

        cls.kernel_install_timeout = int(getattr(
            conf.args, 'kernel_install_timeout', 600))

        cls.util = OpTestUtil(conf)
        cls.install_util = InstallUtil()

    def setUp(self):
        '''Refresh the console reference before each test method.'''
        self.console = self.cv_SYSTEM.console

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_ssh(self):
        '''
        Return the SSH connection for the host OS.

        Delegates to :meth:`~common.OpTestHost.OpTestHost.get_ssh_connection`
        which is the standard op-test accessor for the host SSH handle.

        :returns: SSH connection object (supports run_command())
        '''
        return self.cv_HOST.get_ssh_connection()

    def _distro_name(self):
        '''
        Return a normalised distro identifier: 'rhel', 'sles', or 'ubuntu'.

        Delegates to :meth:`~common.OpTestUtil.OpTestUtil.distro_name` which
        reads ``/etc/os-release`` on the host and returns the canonical name.

        :returns: str  ('rhel', 'sles', or 'ubuntu')
        :raises:  OpTestError for unrecognised distros
        '''
        name = self.util.distro_name()
        if name in ('rhel', 'sles', 'ubuntu'):
            return name
        raise OpTestError(
            "Unsupported or unrecognised Linux distribution: '{}'. "
            "Supported: rhel, sles, ubuntu.".format(name)
        )

    def _discover_virtual_interfaces(self, con):
        '''
        Enumerate all network interfaces whose kernel driver is ibmveth or
        ibmvnic using ``ip link show`` + ``ethtool -i``.

        For each matched interface the method records:
        - ``name``   : interface name (e.g. ``eth0``, ``env3``)
        - ``driver`` : ``ibmveth`` or ``ibmvnic``
        - ``mac``    : colon-separated lowercase MAC address
        - ``ip``     : IPv4/IPv6 address string if assigned, else ``None``

        :param con: SSH connection (or console) with ``run_command()``
        :returns:   list of dicts, one per virtual interface
        '''
        log.info("Discovering ibmveth/ibmvnic interfaces …")

        # Collect all interface names from ip link show
        ip_out = con.run_command("ip link show", timeout=30)
        ip_raw = "\n".join(ip_out)
        log.debug("ip link show output:\n%s", ip_raw)

        # Match lines like "2: eth0: <FLAGS> mtu …"
        iface_names = re.findall(r'^\d+:\s+(\S+):', ip_raw, re.MULTILINE)
        iface_names = [n.rstrip(':') for n in iface_names if n != 'lo']

        virtual_ifaces = []
        for name in iface_names:
            # Check driver via ethtool -i
            try:
                ethtool_out = con.run_command(
                    "ethtool -i {}".format(name), timeout=20)
            except CommandFailed:
                log.debug("ethtool -i %s failed – skipping", name)
                continue

            ethtool_raw = "\n".join(ethtool_out)
            driver_match = re.search(r'^driver:\s+(\S+)', ethtool_raw,
                                     re.MULTILINE)
            if not driver_match:
                continue
            driver = driver_match.group(1)
            if driver not in _VIRTUAL_DRIVERS:
                continue

            # MAC address from ip link show
            mac = self._get_mac_for_iface(con, name)

            # IP address (best-effort)
            ip_addr = self._get_ip_for_iface(con, name)

            record = {
                'name':   name,
                'driver': driver,
                'mac':    mac,
                'ip':     ip_addr,
            }
            log.info(
                "Virtual interface found: name=%-10s driver=%-8s "
                "mac=%s ip=%s",
                name, driver, mac, ip_addr or '<none>'
            )
            virtual_ifaces.append(record)

        log.info("Total virtual interfaces discovered: %d", len(virtual_ifaces))
        if not virtual_ifaces:
            self.fail(
                "No ibmveth/ibmvnic interfaces found on the LPAR. "
                "Verify that virtual ethernet adapters are assigned in HMC."
            )
        return virtual_ifaces

    def _get_mac_for_iface(self, con, name):
        '''
        Return the MAC address of ``name`` as a lowercase colon-separated
        string, e.g. ``aa:bb:cc:dd:ee:ff``.

        :param con:  SSH connection / console
        :param name: interface name string
        :returns:    str MAC or empty string on failure
        '''
        try:
            out = con.run_command(
                "cat /sys/class/net/{}/address".format(name), timeout=10)
            return out[-1].strip().lower()
        except CommandFailed:
            log.debug("Could not read MAC for %s via sysfs", name)

        # Fallback: ip link show <name>
        try:
            out = con.run_command("ip link show {}".format(name), timeout=10)
            raw = "\n".join(out)
            m = re.search(r'link/ether\s+([0-9a-f:]+)', raw)
            if m:
                return m.group(1).lower()
        except CommandFailed:
            pass

        log.warning("Unable to determine MAC for interface '%s'", name)
        return ''

    def _get_ip_for_iface(self, con, name):
        '''
        Return the first assigned IP address (v4 or v6) for ``name``, or
        ``None`` if the interface is not configured.

        :param con:  SSH connection / console
        :param name: interface name string
        :returns:    str IP address or None
        '''
        try:
            out = con.run_command(
                "ip addr show {}".format(name), timeout=10)
            raw = "\n".join(out)
            # Prefer inet (IPv4)
            m4 = re.search(r'\binet\s+(\S+)', raw)
            if m4:
                return m4.group(1).split('/')[0]
            m6 = re.search(r'\binet6\s+(\S+)', raw)
            if m6:
                return m6.group(1).split('/')[0]
        except CommandFailed:
            pass
        return None

    def _install_kernel(self, con, distro):
        '''
        Install ``target_kernel_version`` using the distro package manager.

        The kernel package name is constructed per-distro convention:

        - RHEL  : ``kernel-<version>``  installed with ``yum install -y``
        - SLES  : ``kernel-default-<version>``  installed with
                  ``zypper --non-interactive install -y``
        - Ubuntu: ``linux-image-<version>``  installed with
                  ``apt-get install -y``

        The distro ID is cross-checked against
        :meth:`~common.OpTestUtil.OpTestUtil.get_distro_details` so that
        the same ``ID`` key that the rest of op-test uses is authoritative.

        :param con:    SSH connection with run_command()
        :param distro: str, 'rhel' | 'sles' | 'ubuntu'
        :raises:       OpTestError on install failure
        '''
        ver = self.target_kernel_version
        log.info("Installing kernel version: %s", ver)
        distro_id = self.util.get_distro_details().get('ID', [distro])[0].strip('"')

        if distro_id == 'rhel':
            pkg = "kernel-{}".format(ver)
            cmd = "yum install -y {}".format(pkg)
        elif distro_id in ('sles', 'suse', 'opensuse-leap', 'opensuse-tumbleweed'):
            pkg = "kernel-default-{}".format(ver)
            cmd = "zypper --non-interactive install -y {}".format(pkg)
        elif distro_id in ('ubuntu', 'debian'):
            pkg = "linux-image-{}".format(ver)
            cmd = "DEBIAN_FRONTEND=noninteractive apt-get install -y {}".format(pkg)
        else:
            raise OpTestError(
                "Unsupported distro ID '{}' for kernel install. "
                "Expected rhel, sles, or ubuntu.".format(distro_id))

        log.info("Running install command: %s", cmd)
        try:
            con.run_command(cmd, timeout=self.kernel_install_timeout)
        except CommandFailed as cf:
            raise OpTestError(
                "Kernel package install failed for '{}': {}".format(pkg, cf))
        log.info("Kernel package '%s' installed successfully", pkg)

    def _set_default_kernel(self, con, distro):
        '''
        Set the newly installed kernel as the default boot entry.

        Uses ``grubby --set-default`` on RHEL/Ubuntu and
        ``grub2-set-default`` on SLES.

        :param con:    SSH connection with run_command()
        :param distro: str, 'rhel' | 'sles' | 'ubuntu'
        '''
        ver = self.target_kernel_version
        log.info("Setting default boot kernel to: %s", ver)

        if distro in ('rhel', 'ubuntu'):
            cmd = "grubby --set-default /boot/vmlinu*-{}".format(ver)
        else:
            cmd = "grub2-set-default /boot/vmlinu*-{}".format(ver)

        try:
            con.run_command(cmd, timeout=60)
            log.info("Default boot entry set to kernel %s", ver)
        except CommandFailed as cf:
            raise OpTestError(
                "Failed to set default kernel '{}': {}".format(ver, cf))
        try:
            con.run_command(
                "grub2-mkconfig --output=/boot/grub2/grub.cfg", timeout=60)
            log.info("grub2-mkconfig completed")
        except CommandFailed:
            log.debug("grub2-mkconfig failed or not available – continuing")

    def _reboot_and_wait(self):
        '''
        Power the LPAR off and back on via HMC, then wait until the system
        reaches ``OpSystemState.OS``.

        **Why not ``goto_state(OFF) → goto_state(OS)``?**

        ``goto_state(OS)`` from ``OpSystemState.OFF`` ultimately calls
        ``OpTestLPARSystem.sys_power_on()`` → ``hmc.poweron_lpar()`` →
        ``hmc.ssh.run_command("chsysstate … -o on")`` with the default SSH
        timeout (60 s).  The HMC ``chsysstate -o on`` command accepts the
        request and returns only *after* the LPAR reaches ``Running`` — which
        for a full boot can take several minutes — so the 60-second timeout
        fires and raises ``CommandFailed`` with exit code -1 before
        ``wait_lpar_state`` ever runs.

        The correct pattern used throughout op-test HMC tests
        (e.g. ``OpTestDKGSB``, ``OpTestLPM``) is:

        1. ``cv_HMC.poweroff_lpar()``  – issues ``chsysstate … -o shutdown
           --immed`` *and* polls ``wait_lpar_state(NOT_ACTIVE)`` internally.
        2. ``cv_HMC.poweron_lpar()``   – issues ``chsysstate … -o on`` *and*
           polls ``wait_lpar_state(RUNNING)`` (up to 120×25 s = 50 min).
        3. ``cv_SYSTEM.goto_state(OS)`` – from ``BOOTING``/``Running`` the
           state machine just opens the HMC console and sets up the prompt
           without calling ``sys_power_on()`` again.
        '''
        log.info("Initiating HMC-managed power-off / power-on reboot cycle …")

        # Close the console PTY so the HMC can deactivate the terminal
        try:
            self.console.close()
        except Exception as exc:
            log.debug("Console close raised (ignored): %s", exc)

        # Step A – power off via HMC (polls NOT_ACTIVE internally)
        log.info("Powering off LPAR via HMC …")
        self.cv_HMC.poweroff_lpar()
        log.info("LPAR is Not Activated (OFF)")

        # Step B – power on via HMC (polls RUNNING internally, up to ~50 min)
        log.info("Powering on LPAR via HMC …")
        self.cv_HMC.poweron_lpar()
        log.info("LPAR reached Running state via HMC")

        # Step C – tell op-test state machine to set up the OS console session.
        # The LPAR is already Running so goto_state(OS) only opens the HMC
        # console and waits for login — it does NOT re-call sys_power_on().
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.info("LPAR OS console ready")

        # Let udev and network interfaces settle after the full boot
        time.sleep(_POST_BOOT_SETTLE)

    def _verify_running_kernel(self):
        '''
        Confirm that the running kernel matches ``target_kernel_version``.

        Uses :meth:`~common.OpTestHost.OpTestHost.host_get_kernel_version`
        which runs ``uname -a | awk {print $3}`` and returns the version
        token — the same helper used throughout op-test to query kernel
        version after a boot.  No SSH connection object is needed; the
        method uses ``self.cv_HOST`` directly.

        :raises: AssertionError (via self.fail()) on mismatch
        '''
        # host_get_kernel_version() returns the $3 field of uname -a,
        # i.e. the kernel release string (same as uname -r).
        running = (self.cv_HOST.host_get_kernel_version() or "").strip()
        log.info("Running kernel after upgrade: %s", running)

        # Build the set of acceptable version strings to match against the
        # running kernel.  Two candidates are needed:
        #
        #   1. target as-is — works for RHEL where uname -r contains the
        #      full version, e.g.  5.14.0-427.31.1.el9_4
        #
        #   2. SLES flavour form — on SLES, uname -r appends '-default' and
        #      drops the trailing RPM release counter (.N), e.g.:
        #        conf:   6.4.0-150700.53.52.1.ppc64le  (after normalisation)
        #                → target_kernel_version = 6.4.0-150700.53.52.1
        #        uname:  6.4.0-150700.53.52-default
        #      Strip the trailing integer-only release field and append
        #      '-default' to form the SLES candidate.
        candidates = [str(self.target_kernel_version)]
        sles_base = re.sub(r'\.\d+$', '', str(self.target_kernel_version))
        if sles_base != self.target_kernel_version:
            candidates.append("{}-default".format(sles_base))
        log.debug("Kernel version match candidates: %s", candidates)

        if not any(c in running for c in candidates):
            self.fail(
                "Kernel upgrade verification failed: none of the expected "
                "version strings {} were found in host_get_kernel_version() "
                "output '{}'. The system may have booted an unexpected "
                "kernel.".format(candidates, running)
            )
        log.info("Kernel upgrade confirmed: running %s", running)

    def _verify_interfaces_post_boot(self, con, pre_ifaces):
        '''
        Check that every interface recorded before the upgrade is still
        present with the same name, MAC address, and IP address.

        :param con:        SSH connection with run_command()
        :param pre_ifaces: list of dicts from :meth:`_discover_virtual_interfaces`
        '''
        log.info("Re-discovering virtual interfaces after upgrade …")
        post_ifaces = self._discover_virtual_interfaces(con)

        # Build a lookup by interface name for fast access
        post_by_name = {i['name']: i for i in post_ifaces}

        failures = []
        for pre in pre_ifaces:
            name = pre['name']
            if name not in post_by_name:
                failures.append(
                    "Interface '{}' (driver={}, mac={}) is MISSING after "
                    "kernel upgrade".format(name, pre['driver'], pre['mac'])
                )
                continue

            post = post_by_name[name]
            if pre['mac'] and post['mac'] and pre['mac'] != post['mac']:
                failures.append(
                    "Interface '{}' MAC address changed: "
                    "pre='{}' post='{}'".format(name, pre['mac'], post['mac'])
                )
            else:
                log.info("Interface '%s' MAC address intact: %s",
                         name, post['mac'])
            if pre['ip'] is not None:
                if post['ip'] != pre['ip']:
                    failures.append(
                        "Interface '{}' IP address changed: "
                        "pre='{}' post='{}'".format(
                            name, pre['ip'], post['ip'])
                    )
                else:
                    log.info("Interface '%s' IP address intact: %s",
                             name, post['ip'])

        if failures:
            msg = (
                "Network interface integrity check FAILED after kernel "
                "upgrade to '{}':\n  {}".format(
                    self.target_kernel_version, "\n  ".join(failures))
            )
            log.error(msg)
            self.fail(msg)

        log.info(
            "All %d virtual interface(s) intact after kernel upgrade",
            len(pre_ifaces)
        )

    # ------------------------------------------------------------------
    # Main test steps (called by runTest in the concrete class)
    # ------------------------------------------------------------------

    def step1_snapshot_interfaces(self):
        '''
        Step 1: Connect via SSH and capture a snapshot of all ibmveth/ibmvnic
        interfaces, their driver, MAC, and IP address.

        :returns: (con, pre_ifaces, distro) tuple
        '''
        log.info("=== Step 1: Pre-upgrade interface snapshot ===")
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        con = self._get_ssh()

        distro = self._distro_name()
        log.info("Detected Linux distribution: %s", distro)

        # Use OpTestHost.host_get_kernel_version() (uname -a | awk {print $3})
        # – the standard op-test way to read the running kernel version.
        running_before = self.cv_HOST.host_get_kernel_version().strip()
        log.info("Current running kernel: %s", running_before)

        pre_ifaces = self._discover_virtual_interfaces(con)
        log.info("Pre-upgrade snapshot complete – %d virtual interface(s) "
                 "recorded", len(pre_ifaces))
        for iface in pre_ifaces:
            log.info(
                "  %-12s  driver=%-8s  mac=%s  ip=%s",
                iface['name'], iface['driver'],
                iface['mac'], iface['ip'] or '<none>'
            )
        return con, pre_ifaces, distro

    def step2_upgrade_kernel(self, con, distro):
        '''
        Step 2: Install the target kernel package and set it as default.

        :param con:    active SSH connection
        :param distro: str, 'rhel' | 'sles' | 'ubuntu'
        '''
        log.info("=== Step 2: Kernel upgrade to '%s' ===",
                 self.target_kernel_version)
        self._install_kernel(con, distro)
        self._set_default_kernel(con, distro)
        log.info("Kernel upgrade preparation complete")

    def step3_reboot(self):
        '''
        Step 3: Power-cycle the LPAR and wait for OS state.
        '''
        log.info("=== Step 3: Rebooting LPAR ===")
        self._reboot_and_wait()
        log.info("LPAR rebooted and reached OS state")

    def step4_verify(self, pre_ifaces):
        '''
        Step 4: Verify the running kernel and interface integrity post-reboot.

        Kernel check uses :meth:`~common.OpTestHost.OpTestHost.host_get_kernel_version`
        (no SSH connection object needed – it uses ``self.cv_HOST`` directly).
        Interface re-discovery uses a fresh SSH connection via
        :meth:`~common.OpTestHost.OpTestHost.get_ssh_connection`.

        :param pre_ifaces: list of dicts from step1
        '''
        log.info("=== Step 4: Post-upgrade verification ===")
        self._verify_running_kernel()
        con = self._get_ssh()
        self._verify_interfaces_post_boot(con, pre_ifaces)
        log.info("Post-upgrade verification complete")

class VirtualKernelUpgradeTest(OpTestVirtualKernelUpgrade, unittest.TestCase):
    '''
    End-to-end test: upgrade the kernel on a PowerVM LPAR and verify that
    ibmveth and ibmvnic interfaces retain their names, MACs, and IPs.

    Steps
    -----
    1. Snapshot pre-upgrade interface state (names, driver, MAC, IP).
    2. Install ``target_kernel_version`` via the distro package manager and
       set it as the default grub boot entry.
    3. Power-cycle the LPAR (OFF → OS via goto_state).
    4. Confirm ``uname -r`` matches the upgraded version; re-enumerate
       interfaces and assert names/MACs/IPs are unchanged.

    Usage::

        ./op-test --config-file virtual_kernel_upgrade.conf \\
                  --run testcases.OpTestVirtualKernelUpgrade.VirtualKernelUpgradeTest
    '''

    def runTest(self):
        '''
        Execute the complete virtual kernel upgrade test sequence.
        '''
        log.info(
            "Starting VirtualKernelUpgradeTest "
            "(target kernel: %s)", self.target_kernel_version
        )

        # Step 1 – snapshot
        con, pre_ifaces, distro = self.step1_snapshot_interfaces()

        # Step 2 – install and configure new kernel
        self.step2_upgrade_kernel(con, distro)

        # Step 3 – reboot
        self.step3_reboot()

        # Step 4 – verify
        self.step4_verify(pre_ifaces)

        log.info(
            "SUCCESS: VirtualKernelUpgradeTest PASSED – "
            "kernel upgraded to '%s', all %d virtual interface(s) intact",
            self.target_kernel_version, len(pre_ifaces)
        )
