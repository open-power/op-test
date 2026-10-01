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
OpTestUdevRulesPersistency: Verify the network interface names set are
persistent across reboot
------------------------------------------------------------------------------

This test verifies that the network interface names set using Udev rules
persist across system reboots.

The test supports two modes, controlled by the conf file parameter
``persistant_for_virtual_device``:

  False (default) — Physical / direct-attached interface mode
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Two rules are written to the udev rules file:

    Rule 1 (net1) — matched by PCI bus ID:
      SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{dev_id}=="0x0",
      ATTR{type}=="1", KERNEL=="?*", ATTR{dev_port}=="0",
      KERNELS=="<pci_bus_id>", NAME="net1"

    Rule 2 (net2) — matched by MAC address:
      SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
      ATTR{address}=="<mac_address>", KERNEL=="?*", NAME="net2"

  Both test_interface_pcibusid and test_interface_mac must be supplied and
  must refer to two *different* interfaces.

  Post-reboot validation:
    - net1 exists; ethtool -i net1 bus-info matches test_interface_pcibusid.
    - net2 exists; ip addr show net2 MAC matches test_interface_mac.

  True — Virtual device mode
  ~~~~~~~~~~~~~~~~~~~~~~~~~~
  Only the MAC-address rule is written (PCI bus ID is irrelevant for vNICs):

    SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
    ATTR{address}=="<mac_address>", KERNEL=="?*", NAME="net2"

  Only test_interface_mac needs to be supplied.
  test_interface_pcibusid is ignored even if present.

  Post-reboot validation:
    - net2 exists; ip addr show net2 MAC matches test_interface_mac.
    - The PCI bus ID step is skipped entirely.

Configuration Parameters:
---------------------------
The following parameters can be passed via the conf file:

persistant_for_virtual_device : True  → virtual-device mode (MAC rule only)
                                False → physical mode (PCI + MAC rules)
                                Default: False
test_interface_pcibusid       : PCI bus ID for the KERNELS rule (physical mode)
                                (e.g. 0014:01:00.0)
test_interface_mac            : MAC address for the ATTR{address} rule
                                (e.g. 04:3f:72:a9:37:29)

Usage Examples:
--------------
# Physical / direct-attached mode (default):
./op-test --config-file persistent_udev_rules_io_RHEL.conf \\
--run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest

# Virtual device mode:
# Add to conf file:  persistant_for_virtual_device = True
./op-test --config-file persistent_udev_rules_vnic.conf \\
--run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest

'''

import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

UDEV_RULES_FILE = "/etc/udev/rules.d/70-persistent-net.rules"
IFACE_KERNELS = "net1"
IFACE_MAC = "net2"


class OpTestUdevRulesPersistency(unittest.TestCase):
    '''
    Base test class for udev rules network interface name persistency.
    '''

    @classmethod
    def setUpClass(cls):
        """
        Read configuration and resolve required CLI parameters.

        Raises:
            unittest.SkipTest: if required parameters for the selected mode
                               are not provided.
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
        cls.pci_bus_id = conf.args.test_interface_pcibusid
        cls.mac_address = conf.args.test_interface_mac

        # Determine mode: virtual device (MAC-only) vs physical (PCI + MAC).
        raw = getattr(conf.args, 'persistant_for_virtual_device', None)
        if isinstance(raw, str):
            cls.virtual_device_mode = raw.strip().lower() == 'true'
        else:
            cls.virtual_device_mode = bool(raw)

        log.info(
            "persistant_for_virtual_device=%s → %s mode",
            raw,
            "virtual-device (MAC only)" if cls.virtual_device_mode
            else "physical (PCI + MAC)",
        )

        # MAC address is always required.
        if not cls.mac_address:
            raise unittest.SkipTest(
                "Required parameter test_interface_mac not provided. "
                "Pass the MAC address via test_interface_mac."
            )

        # PCI bus ID is only required in physical mode.
        if not cls.virtual_device_mode and not cls.pci_bus_id:
            raise unittest.SkipTest(
                "Required parameter test_interface_pcibusid not provided "
                "for physical mode. Pass the PCI bus ID via "
                "test_interface_pcibusid, or set "
                "persistant_for_virtual_device = True for virtual-device mode."
            )

    def setUp(self):
        """
        Ensure the system console is got before each test method.
        """
        self.console = self.cv_SYSTEM.console
        self._console_obj = self.cv_SYSTEM.console  # keep a ref for close()

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def create_udev_rules_file(self):
        """
        Step 1: Write /etc/udev/rules.d/70-persistent-net.rules.

        Physical mode  (persistant_for_virtual_device=False):
            Two rules — Rule 1 matched by PCI bus ID (→ net1),
                        Rule 2 matched by MAC address (→ net2).

        Virtual-device mode (persistant_for_virtual_device=True):
            One rule  — matched by MAC address only (→ net2).
            PCI bus ID rule is skipped entirely.
        """
        log.info("Step 1: Creating udev rules file %s", UDEV_RULES_FILE)

        rule_mac = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{address}}=="{mac}", KERNEL=="?*", NAME="{iface}"'
        ).format(mac=self.mac_address, iface=IFACE_MAC)

        if self.virtual_device_mode:
            # Virtual-device mode: MAC-address rule only.
            log.info(
                "Virtual-device mode: writing MAC-address rule only (→ %s)",
                IFACE_MAC,
            )
            write_cmd = (
                "printf '%s\\n' '{rule}' > {path}"
            ).format(rule=rule_mac, path=UDEV_RULES_FILE)
        else:
            # Physical mode: PCI bus ID rule + MAC-address rule.
            log.info(
                "Physical mode: writing PCI rule (→ %s) and MAC rule (→ %s)",
                IFACE_KERNELS, IFACE_MAC,
            )
            rule_kernels = (
                'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
                'ATTR{{dev_id}}=="0x0", ATTR{{type}}=="1", KERNEL=="?*", '
                'ATTR{{dev_port}}=="0", KERNELS=="{pci}", NAME="{iface}"'
            ).format(pci=self.pci_bus_id, iface=IFACE_KERNELS)
            write_cmd = (
                "printf '%s\\n%s\\n' "
                "'{rule1}' "
                "'{rule2}' "
                "> {path}"
            ).format(rule1=rule_kernels, rule2=rule_mac, path=UDEV_RULES_FILE)

        self.console.run_command(write_cmd, timeout=30)

        # Verify the file was written correctly.
        output = self.console.run_command(
            "cat {}".format(UDEV_RULES_FILE), timeout=60
        )
        log.info("Udev rules file content:\n%s", "\n".join(output))

        if not self.virtual_device_mode and self.pci_bus_id not in str(output):
            self.fail(
                "PCI bus ID '{}' not found in written udev rules file".format(
                    self.pci_bus_id
                )
            )
        if self.mac_address not in str(output):
            self.fail(
                "MAC address '{}' not found in written udev rules file".format(
                    self.mac_address
                )
            )
        log.info("Udev rules file created and verified successfully")

    def reboot_system(self):
        """
        Step 2: Power the system off and then back on to OS.
        """
        log.info("Step 2: Rebooting the system (power off/on cycle)")
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

    def verify_interface_existence(self):
        """
        Step 3: Confirm that the expected interfaces appear after reboot.

        Physical mode       : verifies both net1 and net2.
        Virtual-device mode : verifies net2 only (net1 is never created).
        """
        ifaces_to_check = (
            (IFACE_MAC,) if self.virtual_device_mode
            else (IFACE_KERNELS, IFACE_MAC)
        )
        log.info(
            "Step 3: Verifying that interface(s) %s exist",
            ", ".join("'{}'".format(i) for i in ifaces_to_check),
        )
        output = self.console.run_command("ip link show", timeout=30)
        iface_list = "\n".join(output)
        log.info("Network interfaces present:\n%s", iface_list)

        for iface in ifaces_to_check:
            if iface not in iface_list:
                self.fail(
                    "Interface '{}' not found after reboot. "
                    "Udev rule may not have applied correctly.".format(iface)
                )
            log.info("Interface '%s' confirmed present", iface)

    def validate_pci_bus_match(self):
        """
        Step 4a: Verify that the PCI bus ID set in KERNELS matches the
        bus-info reported by ethtool -i for eth0.
        """
        log.info(
            "Step 4a: Validating PCI bus ID for interface '%s'",
            IFACE_KERNELS
        )
        output = self.console.run_command(
            "ethtool -i {}".format(IFACE_KERNELS), timeout=30
        )
        ethtool_out = "\n".join(output)
        log.info("ethtool -i %s output:\n%s", IFACE_KERNELS, ethtool_out)

        if self.pci_bus_id not in ethtool_out:
            self.fail(
                "PCI bus ID '{}' not found in ethtool -i {} output.\n"
                "ethtool output: {}".format(
                    self.pci_bus_id, IFACE_KERNELS, ethtool_out
                )
            )
        log.info(
            "PCI bus ID '%s' confirmed for interface '%s'",
            self.pci_bus_id, IFACE_KERNELS
        )

    def validate_mac_address_match(self):
        """
        Step 4b: Verify that the MAC address set in ATTR{address} matches
        the link/ether address reported by ip addr show for eth1.
        """
        log.info(
            "Step 4b: Validating MAC address for interface '%s'",
            IFACE_MAC
        )
        output = self.console.run_command(
            "ip addr show {}".format(IFACE_MAC), timeout=30
        )
        ip_out = "\n".join(output)
        log.info("ip addr show %s output:\n%s", IFACE_MAC, ip_out)

        if self.mac_address.lower() not in ip_out.lower():
            self.fail(
                "MAC address '{}' not found in ip addr show {} output.\n"
                "ip addr output: {}".format(
                    self.mac_address, IFACE_MAC, ip_out
                )
            )
        log.info(
            "MAC address '%s' confirmed for interface '%s'",
            self.mac_address, IFACE_MAC
        )

    def cleanup(self):
        """
        Remove the udev rules file created during the test.
        """
        log.info("Cleaning up: removing %s", UDEV_RULES_FILE)
        self.console.run_command(
            "rm -f {}".format(UDEV_RULES_FILE), timeout=30
        )
        log.info("Cleanup completed")


class UdevRulesPersistencyTest(OpTestUdevRulesPersistency, unittest.TestCase):
    '''
    End-to-end test for udev-based network interface name persistency.

    Physical mode  (persistant_for_virtual_device=False, default):
      - Creates both a PCI bus ID rule (→ net1) and a MAC rule (→ net2).
      - Verifies net1 and net2 exist after reboot.
      - Validates ethtool -i net1 bus-info matches test_interface_pcibusid.
      - Validates ip addr show net2 MAC matches test_interface_mac.

    Virtual-device mode (persistant_for_virtual_device=True):
      - Creates only the MAC-address rule (→ net2); PCI rule is skipped.
      - Verifies net2 exists after reboot.
      - Validates ip addr show net2 MAC matches test_interface_mac.
      - PCI bus ID validation step is skipped entirely.

    Usage:
        # Physical mode (default):
        ./op-test --config-file
          persistent_udev_rules_io_RHEL10_2_dedicated.conf \\
          --run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest

        # Virtual-device mode (add to conf: persistant_for_virtual_device=True):
        ./op-test --config-file persistent_udev_rules_vnic.conf \\
          --run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest
    '''

    def runTest(self):
        """
        Execute the complete udev rules persistency test sequence.

        Physical mode  : create (PCI + MAC rules) → reboot → verify both
                         interfaces → validate PCI → validate MAC → cleanup.
        Virtual mode   : create (MAC rule only)    → reboot → verify net2
                         only → validate MAC → cleanup.
                         (validate_pci_bus_match is skipped)
        """
        log.info("Starting udev rules persistency test")
        log.info(
            "  Mode                 : %s",
            "virtual-device (MAC only)" if self.virtual_device_mode
            else "physical (PCI + MAC)",
        )
        if not self.virtual_device_mode:
            log.info("  KERNELS (PCI bus ID) : %s", self.pci_bus_id)
        log.info("  ATTR{address} (MAC)  : %s", self.mac_address)

        self.create_udev_rules_file()
        self.reboot_system()
        self.verify_interface_existence()
        if not self.virtual_device_mode:
            self.validate_pci_bus_match()
        self.validate_mac_address_match()
        self.cleanup()

        log.info("SUCCESS: Udev rules persistency test completed successfully")
