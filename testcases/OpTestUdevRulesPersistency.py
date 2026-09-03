#!/usr/bin/env python3
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

'''
OpTestUdevRulesPersistency: Verify the network interface names set using Udev
rules are persistent across reboot — supports both PCI (physical) adapters and
ibmvnic / ibmveth virtual adapters.

==============================================================================
PCI / Physical Adapter Mode
==============================================================================
Requires both test_interface_pcibusid and test_interface_mac in the conf file.

Test Steps:
1. Create /etc/udev/rules.d/70-persistent-net.rules with two rules:

   SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{dev_id}=="0x0",
   ATTR{type}=="1", KERNEL=="?*", ATTR{dev_port}=="0",
   KERNELS=="<pci_bus_id>", NAME="net1"

   SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
   ATTR{address}=="<mac_address>", KERNEL=="?*", NAME="net2"

2. Reboot the system (power off/on cycle).

3. Verify that net1 and net2 exist as network interfaces after reboot.

4. Validate:
   - The PCI bus ID in KERNELS matches bus-info from ethtool -i net1.
   - The MAC address in ATTR{address} matches ip addr show net2.

==============================================================================
Virtual Adapter Mode (ibmvnic / ibmveth)
==============================================================================
Used when test_interface_pcibusid is absent or empty (e.g. for virtual
adapters backed by ibmvnic or ibmveth where there is no PCI bus ID).
Both ibmvnic and ibmveth expose the same sysfs attributes (ATTR{dev_id},
ATTR{type}) so a single udev rule pattern covers both driver types.
Requires only test_interface_mac (the MAC address of the virtual
interface) in the conf file.

Test Steps:
1. Create /etc/udev/rules.d/70-persistent-net.rules with one rule:

   SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
   ATTR{address}=="<mac_address>", ATTR{dev_id}=="0x0",
   ATTR{type}=="1", NAME="virt_net1"

2. Reboot the system (power off/on cycle).

3. Verify that virt_net1 exists as a network interface after reboot.

4. Validate:
   - The MAC address in ATTR{address} matches ip addr show virt_net1.

==============================================================================
Configuration Parameters
==============================================================================

  PCI mode (both required):
    test_interface_pcibusid  : PCI bus ID for the KERNELS rule
                               (e.g. 0014:01:00.0)
    test_interface_mac       : MAC address for the ATTR{address} rule
                               (e.g. 04:3f:72:a9:37:29)

  Virtual adapter mode (ibmvnic / ibmveth — required):
    test_interface_mac       : MAC address of the virtual adapter
                               (e.g. ba:70:ca:ca:88:01)

Usage Examples:
---------------
# PCI / physical adapter mode:
./op-test --config-file persistent_udev_rules_pci.conf \
--run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest

# Virtual adapter mode (ibmvnic / ibmveth):
./op-test --config-file persistent_udev_rules_vnic.conf \
--run testcases.OpTestUdevRulesPersistency.VirtualUdevRulesPersistencyTest

'''

import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

UDEV_RULES_FILE = "/etc/udev/rules.d/70-persistent-net.rules"

IFACE_KERNELS = "net1"      
IFACE_MAC     = "net2"       
IFACE_VIRTNIC = "virt_net1"  # renamed interface: ibmvnic / ibmveth virtual adapter

class OpTestUdevRulesPersistency(unittest.TestCase):
    '''
    Base test class for udev rules network interface name persistency.
    Provides shared helpers used by both PCI and virtual adapter sub-classes.
    '''

    @classmethod
    def setUpClass(cls):
        """
        Read configuration and resolve CLI/conf-file parameters common to
        all modes (PCI, ibmvnic, ibmveth).

        Raises:
            unittest.SkipTest: if bmc_type is not FSP_PHYP or EBMC_PHYP.
        """
        conf = OpTestConfiguration.conf
        cls.cv_SYSTEM = conf.system()
        cls.cv_HOST = conf.host()
        cls.bmc_type = conf.args.bmc_type

        if cls.bmc_type not in ["FSP_PHYP", "EBMC_PHYP"]:
            raise unittest.SkipTest(
                "This test is only supported on LPAR (FSP_PHYP or EBMC_PHYP)")

        cls.hmc_user = conf.args.hmc_username
        cls.hmc_password = conf.args.hmc_password
        cls.hmc_ip = conf.args.hmc_ip
        cls.lpar_name = conf.args.lpar_name
        cls.system_name = conf.args.system_name
        cls.lpar_prof = conf.args.lpar_prof
        cls.pci_bus_id  = getattr(conf.args, 'test_interface_pcibusid', None) or ""
        cls.mac_address = getattr(conf.args, 'test_interface_mac', None) or ""
        cls.virt_mac = cls.mac_address

    def setUp(self):
        """
        Ensure a fresh console reference is available before each test method.
        """
        self.console = self.cv_SYSTEM.console
        self._console_obj = self.cv_SYSTEM.console

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _reboot_system(self):
        """
        Power the system off and then back on to OS, then wait for udev
        to settle before returning.
        """
        log.info("Rebooting the system (power off/on cycle)")
        log.info("Closing console PTY before shutdown")
        try:
            self._console_obj.close()
        except Exception as e:
            log.debug("Console close raised (ignored): %s", e)
        time.sleep(30)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        log.info("System booted successfully after reboot")
        self._console_obj.close()
        self.console = self.cv_SYSTEM.console
        # Allow udev to settle after boot.
        time.sleep(30)

    def _verify_interfaces_exist(self, *iface_names):
        """
        Confirm that every interface name in *iface_names appears in the
        output of ``ip link show``.
        """
        log.info("Verifying that interfaces %s exist", list(iface_names))
        output = self.console.run_command("ip link show", timeout=30)
        iface_list = "\n".join(output)
        log.info("Network interfaces present:\n%s", iface_list)

        for iface in iface_names:
            if iface not in iface_list:
                self.fail(
                    "Interface '{}' not found after reboot. "
                    "Udev rule may not have applied correctly.".format(iface)
                )
            log.info("Interface '%s' confirmed present", iface)

    def _validate_mac_on_iface(self, iface, mac):
        """
        Verify that *mac* appears in ``ip addr show <iface>`` output.
        """
        log.info("Validating MAC address for interface '%s'", iface)
        output = self.console.run_command(
            "ip addr show {}".format(iface), timeout=30
        )
        ip_out = "\n".join(output)
        log.info("ip addr show %s output:\n%s", iface, ip_out)

        if mac.lower() not in ip_out.lower():
            self.fail(
                "MAC address '{}' not found in 'ip addr show {}' output.\n"
                "ip addr output: {}".format(mac, iface, ip_out)
            )
        log.info("MAC address '%s' confirmed for interface '%s'", mac, iface)

    def _validate_pci_bus_on_iface(self, iface, pci_bus_id):
        """
        Verify that *pci_bus_id* appears in the bus-info line of
        ``ethtool -i <iface>`` output.
        """
        log.info(
            "Validating PCI bus ID '%s' for interface '%s'",
            pci_bus_id, iface
        )
        output = self.console.run_command(
            "ethtool -i {}".format(iface), timeout=30
        )
        ethtool_out = "\n".join(output)
        log.info("ethtool -i %s output:\n%s", iface, ethtool_out)

        if pci_bus_id not in ethtool_out:
            self.fail(
                "PCI bus ID '{}' not found in 'ethtool -i {}' output.\n"
                "ethtool output: {}".format(pci_bus_id, iface, ethtool_out)
            )
        log.info(
            "PCI bus ID '%s' confirmed for interface '%s'", pci_bus_id, iface
        )

    def _remove_udev_rules_file(self):
        """Remove the udev rules file written during the test."""
        log.info("Removing udev rules file %s", UDEV_RULES_FILE)
        self.console.run_command(
            "rm -f {}".format(UDEV_RULES_FILE), timeout=30
        )


# ---------------------------------------------------------------------------
# PCI / Physical Adapter Test
# ---------------------------------------------------------------------------

class UdevRulesPersistencyTest(OpTestUdevRulesPersistency, unittest.TestCase):
    '''
    End-to-end test for udev-based network interface name persistency on
    PCI / physical adapters.

    Creates two udev rules (one KERNELS/PCI-bus-ID match, one MAC-address
    match), reboots the system, then verifies that:
      - Both interface names (net1, net2) are active after reboot.
      - The PCI bus ID in KERNELS matches ethtool -i net1 bus-info.
      - The MAC address in ATTR{address} matches ip addr show net2.

    Required conf-file parameters:
      test_interface_pcibusid  : PCI bus ID  (e.g. 0014:01:00.0)
      test_interface_mac       : MAC address (e.g. 04:3f:72:a9:37:29)

    Usage:
        ./op-test --config-file persistent_udev_rules_pci.conf \
          --run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest
    '''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if not cls.pci_bus_id:
            raise unittest.SkipTest(
                "Required parameter test_interface_pcibusid not provided. "
                "Pass the PCI bus ID via test_interface_pcibusid in the conf "
                "file. For ibmvnic/ibmveth adapters use VirtualUdevRulesPersistencyTest."
            )
        if not cls.mac_address:
            raise unittest.SkipTest(
                "Required parameter test_interface_mac not provided. "
                "Pass the MAC address via test_interface_mac in the conf file."
            )

    # ------------------------------------------------------------------
    # Step helpers (PCI mode)
    # ------------------------------------------------------------------

    def create_udev_rules_file(self):
        """
        Step 1: Write the udev rules file with two rules — one matched
        by PCI bus ID (KERNELS) and one matched by MAC address (ATTR{address}).
        """
        log.info("Step 1: Creating udev rules file %s (PCI mode)", UDEV_RULES_FILE)

        rule_kernels = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{dev_id}}=="0x0", ATTR{{type}}=="1", KERNEL=="?*", '
            'ATTR{{dev_port}}=="0", KERNELS=="{pci}", NAME="{iface}"'
        ).format(pci=self.pci_bus_id, iface=IFACE_KERNELS)

        rule_mac = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{address}}=="{mac}", KERNEL=="?*", NAME="{iface}"'
        ).format(mac=self.mac_address, iface=IFACE_MAC)

        write_cmd = (
            "printf '%s\\n%s\\n' "
            "'{rule1}' "
            "'{rule2}' "
            "> {path}"
        ).format(rule1=rule_kernels, rule2=rule_mac, path=UDEV_RULES_FILE)
        self.console.run_command(write_cmd, timeout=30)

        output = self.console.run_command(
            "cat {}".format(UDEV_RULES_FILE), timeout=60
        )
        file_content = "\n".join(output)
        log.info("Udev rules file content:\n%s", file_content)

        if self.pci_bus_id not in file_content:
            self.fail(
                "PCI bus ID '{}' not found in written udev rules file".format(
                    self.pci_bus_id
                )
            )
        if self.mac_address not in file_content:
            self.fail(
                "MAC address '{}' not found in written udev rules file".format(
                    self.mac_address
                )
            )
        log.info("Udev rules file (PCI mode) created and verified successfully")

    def reboot_system(self):
        """Step 2: Power the system off and back on."""
        log.info("Step 2: Rebooting the system")
        self._reboot_system()

    def verify_interface_existence(self):
        """Step 3: Confirm that net1 and net2 appear after reboot."""
        log.info("Step 3: Verifying interface existence")
        self._verify_interfaces_exist(IFACE_KERNELS, IFACE_MAC)

    def validate_pci_bus_match(self):
        """Step 4a: Verify PCI bus ID matches ethtool -i net1 bus-info."""
        log.info("Step 4a: Validating PCI bus ID for '%s'", IFACE_KERNELS)
        self._validate_pci_bus_on_iface(IFACE_KERNELS, self.pci_bus_id)

    def validate_mac_address_match(self):
        """Step 4b: Verify MAC address matches ip addr show net2."""
        log.info("Step 4b: Validating MAC address for '%s'", IFACE_MAC)
        self._validate_mac_on_iface(IFACE_MAC, self.mac_address)

    def cleanup(self):
        """Remove the udev rules file and do a final reboot to restore names."""
        log.info("Cleanup: removing udev rules file")
        self._remove_udev_rules_file()
        self.cv_HOST.host_run_command('reboot')
        self.cv_HOST.host_run_command('uname -a')
        self.console = self.cv_SYSTEM.console
        log.info("Cleanup completed")

    def runTest(self):
        """Execute the complete PCI udev rules persistency test sequence."""
        log.info("Starting udev rules persistency test (PCI mode)")
        log.info("  KERNELS (PCI bus ID) : %s", self.pci_bus_id)
        log.info("  ATTR{address} (MAC)  : %s", self.mac_address)

        self.create_udev_rules_file()
        self.reboot_system()
        self.verify_interface_existence()
        self.validate_pci_bus_match()
        self.validate_mac_address_match()
        self.cleanup()

        log.info("SUCCESS: PCI udev rules persistency test completed")


# ---------------------------------------------------------------------------
# Virtual Adapter Test (ibmvnic / ibmveth)
# ---------------------------------------------------------------------------

class VirtualUdevRulesPersistency(OpTestUdevRulesPersistency):
    '''
    Base class adding virtual-adapter step helpers for udev rules persistency
    tests on ibmvnic and ibmveth interfaces.

    Both ibmvnic and ibmveth are PowerVM virtual adapter drivers that expose
    the same sysfs attributes — ATTR{dev_id} and ATTR{type} — so a single
    udev rule pattern covers both driver types without any driver-specific
    branching.  There is no PCI bus ID for either driver.

    The udev rule matches on MAC address (ATTR{address}) using the generic
    DRIVERS=="?*" pattern, tightened with ATTR{dev_id} and ATTR{type}:

        SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
        ATTR{address}=="<virt_mac>", ATTR{dev_id}=="0x0",
        ATTR{type}=="1", NAME="virt_net1"
    '''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if not cls.virt_mac:
            raise unittest.SkipTest(
                "Required parameter test_interface_mac not provided. "
                "Pass the virtual adapter MAC address via test_interface_mac "
                "in the conf file."
            )

    # ------------------------------------------------------------------
    # Step helpers (virtual adapter mode — ibmvnic / ibmveth)
    # ------------------------------------------------------------------

    def create_udev_rules_file_virtnic(self):
        """
        Step 1: Write a udev rules file with a single virtual-adapter rule
        that matches on ATTR{address}==<mac_address>, ATTR{dev_id}=="0x0",
        ATTR{type}=="1".  Works for both ibmvnic and ibmveth drivers since
        both expose the same sysfs attributes.
        The matched interface is renamed to IFACE_VIRTNIC ("virt_net1").
        """
        log.info(
            "Step 1: Creating udev rules file %s (virtual adapter mode)",
            UDEV_RULES_FILE
        )

        rule_virtnic = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{address}}=="{mac}", ATTR{{dev_id}}=="0x0", '
            'ATTR{{type}}=="1", NAME="{iface}"'
        ).format(mac=self.virt_mac, iface=IFACE_VIRTNIC)

        write_cmd = (
            "printf '%s\\n' '{rule}' > {path}"
        ).format(rule=rule_virtnic, path=UDEV_RULES_FILE)
        self.console.run_command(write_cmd, timeout=30)

        output = self.console.run_command(
            "cat {}".format(UDEV_RULES_FILE), timeout=60
        )
        file_content = "\n".join(output)
        log.info("Udev rules file content:\n%s", file_content)

        if self.virt_mac not in file_content:
            self.fail(
                "Virtual adapter MAC address '{}' not found in written udev "
                "rules file".format(self.virt_mac)
            )
        log.info(
            "Udev rules file (virtual adapter mode) created and verified "
            "successfully"
        )

    def reboot_system(self):
        """Step 2: Power the system off and back on."""
        log.info("Step 2: Rebooting the system (virtual adapter mode)")
        self._reboot_system()

    def verify_virtnic_interface_existence(self):
        """
        Step 3: Confirm that the virtual adapter interface (virt_net1) exists
        after reboot.  Applies to both ibmvnic and ibmveth backed interfaces.
        """
        log.info(
            "Step 3: Verifying that virtual adapter interface '%s' exists",
            IFACE_VIRTNIC
        )
        self._verify_interfaces_exist(IFACE_VIRTNIC)

    def validate_virtnic_mac_match(self):
        """
        Step 4a: Verify the MAC address in ATTR{address} matches the
        link/ether address reported by ip addr show virt_net1.
        Validates correctly for both ibmvnic and ibmveth interfaces.
        """
        log.info(
            "Step 4a: Validating virtual adapter MAC address for '%s'",
            IFACE_VIRTNIC
        )
        self._validate_mac_on_iface(IFACE_VIRTNIC, self.virt_mac)

    def cleanup_virtnic(self):
        """
        Remove the udev rules file and do a final reboot so the interface
        name reverts to its default kernel-assigned name (e.g. eth0, env3).
        """
        log.info("Cleanup (virtual adapter mode): removing udev rules file")
        self._remove_udev_rules_file()
        self.cv_HOST.host_run_command('reboot')
        self.cv_HOST.host_run_command('uname -a')
        self.console = self.cv_SYSTEM.console
        log.info("Cleanup (virtual adapter mode) completed")


class VirtualUdevRulesPersistencyTest(VirtualUdevRulesPersistency, unittest.TestCase):
    '''
    End-to-end test for udev-based network interface name persistency on
    ibmvnic and ibmveth virtual adapters.

    Both ibmvnic and ibmveth interfaces have no PCI bus ID.  The udev rule
    matches on MAC address with ATTR{dev_id} and ATTR{type} qualifiers, using
    the generic DRIVERS=="?*" pattern — which covers both driver types since
    they expose identical sysfs attributes.

    Creates the udev rule, reboots the system, then verifies that:
      - The interface "virt_net1" is active after reboot.
      - The MAC address in ATTR{address} matches ip addr show virt_net1.

    Required conf-file parameter:
      test_interface_mac       : MAC address of the ibmvnic or ibmveth adapter
                                 (e.g. ba:70:ca:ca:88:01)

    Usage:
        ./op-test --config-file persistent_udev_rules_vnic.conf \
          --run testcases.OpTestUdevRulesPersistency.VirtualUdevRulesPersistencyTest
    '''

    def runTest(self):
        """
        Execute the complete virtual adapter udev rules persistency test
        sequence.  Covers both ibmvnic and ibmveth interface types.
        """
        log.info("Starting udev rules persistency test (virtual adapter mode)")
        log.info("  ATTR{address} (virtual adapter MAC) : %s", self.virt_mac)
        log.info("  Renamed interface name              : %s", IFACE_VIRTNIC)

        self.create_udev_rules_file_virtnic()
        self.reboot_system()
        self.verify_virtnic_interface_existence()
        self.validate_virtnic_mac_match()
        self.cleanup_virtnic()

        log.info(
            "SUCCESS: virtual adapter udev rules persistency test completed "
            "successfully"
        )
