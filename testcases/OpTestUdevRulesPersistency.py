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

Test Steps:
1. Create a Udev rules file /etc/udev/rules.d/70-persistent-net.rules in the
   Host OS with the following format:

   SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{dev_id}=="0x0",
   ATTR{type}=="1", KERNEL=="?*", ATTR{dev_port}=="0",
   KERNELS=="<pci_bus_id>", NAME="net1"

   SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
   ATTR{address}=="<mac_address>", KERNEL=="?*", NAME="net2"

   where KERNELS and ATTR{address} are supplied via test_interface_pcibusid and
   test_interface_mac conf file parameters.

2. Reboot the system (power off/on cycle).

3. Verify that the interface names declared in the Udev rules file (NAME="net1"
   and NAME="net2") exist as network interfaces on the rebooted system.

4. Validate that:
   - The PCI bus ID set in KERNELS matches the bus-info reported by
     ethtool -i net1.
   - The MAC address set in ATTR{address} matches the link/ether address
     reported by ip addr show net2.

Configuration Parameters:
---------------------------
The following parameters can be passed via the conf file:

test_interface_pcibusid   : PCI bus information for the first rule
                            (e.g. 0014:01:00.0)
test_interface_mac        : MAC address of the adapter for the second rule
                            (e.g. 04:3f:72:a9:37:29)

Usage Examples:
--------------
# Run with required parameters:
./op-test --config-file persistent_udev_rules_io_RHEL.conf \\
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
            unittest.SkipTest: if either test_interface_pcibusid
                               or test_interface_mac is not provided.
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

        if not cls.pci_bus_id:
            raise unittest.SkipTest(
                "Required parameter --KERNELS not provided. "
                "Pass the PCI bus ID via test_interface_pcibusid."
            )
        if not cls.mac_address:
            raise unittest.SkipTest(
                "Required parameter --ATTR-address not provided. "
                "Pass the MAC address via test_interface_mac."
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
        Step 1: Write /etc/udev/rules.d/70-persistent-net.rules with two
        rules — one matched by PCI bus ID (KERNELS) and one matched by MAC
        address (ATTR{address}).
        """
        log.info("Step 1: Creating udev rules file %s", UDEV_RULES_FILE)

        rule_kernels = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{dev_id}}=="0x0", ATTR{{type}}=="1", KERNEL=="?*", '
            'ATTR{{dev_port}}=="0", KERNELS=="{pci}", NAME="{iface}"'
        ).format(pci=self.pci_bus_id, iface=IFACE_KERNELS)

        rule_mac = (
            'SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", '
            'ATTR{{address}}=="{mac}", KERNEL=="?*", NAME="{iface}"'
        ).format(mac=self.mac_address, iface=IFACE_MAC)

        # Write both rules atomically via a here-doc so that special
        # characters in the rule strings are preserved correctly.
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

        if self.pci_bus_id not in str(output):
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
        Step 3: Confirm that both eth0 and eth1 appear in the system's
        network interface list after the reboot.
        """
        log.info(
            "Step 3: Verifying that interfaces '%s' and '%s' exist",
            IFACE_KERNELS, IFACE_MAC
        )
        output = self.console.run_command("ip link show", timeout=30)
        iface_list = "\n".join(output)
        log.info("Network interfaces present:\n%s", iface_list)

        for iface in (IFACE_KERNELS, IFACE_MAC):
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
        self.cv_HOST.host_run_command('reboot')
        self.cv_HOST.host_run_command('uname -a')
        self.console = self.cv_SYSTEM.console
        log.info("Cleanup completed")


class UdevRulesPersistencyTest(OpTestUdevRulesPersistency, unittest.TestCase):
    '''
    End-to-end test for udev-based network interface name persistency.

    Creates a udev rules file, reboots the system, then verifies that:
      - Both interface names (eth0, eth1) are active after reboot.
      - The PCI bus ID in KERNELS matches ethtool -i net1 bus-info.
      - The MAC address in ATTR{address} matches ip addr show net2.

    Usage:
        ./op-test --config-file
          persistent_udev_rules_io_RHEL10_2_dedicated.conf \\
          --run testcases.OpTestUdevRulesPersistency.UdevRulesPersistencyTest
    '''

    def runTest(self):
        """
        Execute the complete udev rules persistency test sequence.
        """
        log.info("Starting udev rules persistency test")
        log.info("  KERNELS (PCI bus ID) : %s", self.pci_bus_id)
        log.info("  ATTR{address} (MAC)  : %s", self.mac_address)

        self.create_udev_rules_file()
        self.reboot_system()
        self.verify_interface_existence()
        self.validate_pci_bus_match()
        self.validate_mac_address_match()
        self.cleanup()

        log.info("SUCCESS: Udev rules persistency test completed successfully")
