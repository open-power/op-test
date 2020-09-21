import unittest
import os, time

import OpTestConfiguration

from common.OpTestSystem import OpSystemState
from common.OpTestInstallUtil import InstallUtil

"""
THE PLAN:

 - assert physical presence
   - clears any existing keys
   - gets the machine in a known state without secureboot
 - enroll a set of PK, KEK, db
   - pregenerated, use secvar sysfs interface
 - reboot, and ensure secure boot is now enabled
 - fail to regular kexec an unsigned kernel
 - fail to load an unsigned kernel
 - fail to load a dbx'd kernel
 - fail to load a signed kernel with unenrolled key
 - successfully load a signed kernel
 - assert physical presence
   - ensure machine is in a non-secure boot state
"""

"""
Generating physicalPresence.bin:
 Create an attribute override file with the following contents (not including leading spaces):

  CLEAR
  target = k0:s0:
  ATTR_BOOT_FLAGS 0x15000000 CONST
  ATTR_PHYS_PRES_FAKE_ASSERT 0x01 CONST
  # ATTR_PHYS_PRES_REQUEST_OPEN_WINDOW 0x01 CONST

 Go to your op-build's <op-build>//build/hostboot-<commit#>/obj/genfiles directory
 From that directory run the following:

  ./attributeOverride -d <path_to_attribute_override_text_file_from_above>

 If it is successful, then an attrOverride.bin file will be created in that directory
"""

"""
Generating oskeys.tar:
 Keys were generated via the makefile in https://git.kernel.org/pub/scm/linux/kernel/git/jejb/efitools.git.
 Running make (along with building the tools) generates and assembles a set of openssl keys, ESLs, and signed auth files.
 Only the auth files are included in the tarball.


Generating oskernels.tar:
 kernel-unsigned   - very stripped down kernel built with minimal config options. no signature
 kernel-signed     - same kernel as above, signed with the db present in oskeys.tar
 kernel-unenrolled - same kernel, signed with another generated key that is NOT in oskeys.tar
 kernel-dbx        - same kconfig, but adjusted version name. signed with the same db key. hash present in oskeys.tar's dbx

Signing kernels:
 Kernels are signed with the `sign-file` utility in the linux source tree, like so:
  ./scripts/sign-file sha256 db.key db.crt vmlinuz kernel-signed

"""


class OsSecureBoot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.OpIU = InstallUtil()
        self.URL = conf.args.secvar_payload_url
        self.bmc_type = conf.args.bmc_type


    def getTestData(self, data="keys"):
        con = self.cv_SYSTEM.console
        self.OpIU.configure_host_ip()

        fil = "os{}.tar".format(data)
        url = self.URL + "/" + fil

        con.run_command("wget {0} -O /tmp/{1}".format(url, fil))
        con.run_command("tar xf /tmp/{} -C /tmp/".format(fil))


    def checkFirmwareSupport(self):
        if "OpenBMC" not in self.bmc_type:
            self.skipTest("Test only applies for OpenBMC-based machines")

        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        output = con.run_command_ignore_fail("test -d /sys/firmware/devicetree/base/ibm,opal/secvar || echo no")
        if "no" in "".join(output):
            self.skipTest("Skiboot does not support secure variables")

        output = con.run_command_ignore_fail("test -d /sys/firmware/secvar || echo no")
        if "no" in "".join(output):
            self.skipTest("Skiroot does not support the secure variables sysfs interface")

        # We only support one backend for now, skip if using an unknown backend
        # NOTE: This file must exist if the previous checks pass, fail the test if not present
        output = con.run_command("cat /sys/firmware/secvar/format")
        if "ibm,edk2-compat-v1" not in "".join(output):
            self.skipTest("Test case only supports the 'ibm,edk2-compat-v1' backend")


    def cleanPhysicalPresence(self):
        self.cv_BMC.run_command("rm -f /usr/local/share/pnor/ATTR_TMP")
        self.cv_BMC.run_command("rm -f /var/lib/obmc/cfam_overrides")

        # Unset the Key Clear Request sensor
        self.cv_IPMI.ipmitool.run("raw 0x04 0x30 0xE8 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00")

        # Reboot to be super sure
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)


    def assertPhysicalPresence(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        # This file was generated using the settings detailed at the top of this file
        # It should be sufficient for any version of hostboot after these attributes were added
        # This might break if something changes about these attributes, or if these attributes are not
        # used on a later platform.
        # NOTE: This override will NOT work on production firmware
        self.cv_BMC.image_transfer("test_binaries/physicalPresence.bin")
        self.cv_BMC.run_command("cp /tmp/physicalPresence.bin /usr/local/share/pnor/ATTR_TMP")

        # Disable security settings on development images, to allow remote physical presence assertion
        self.cv_BMC.run_command("echo '0 0x283a 0x15000000' > /var/lib/obmc/cfam_overrides")
        self.cv_BMC.run_command("echo '0 0x283F 0x20000000' >> /var/lib/obmc/cfam_overrides")

        # The "ClearHostSecurityKeys" sensor is used on the OpenBMC to keep track of any Key Clear Request.
        # During the (re-)IPL, the values will be sent to Hostboot for processing.
        # This sets the sensor value to 0x40, which indicates KEY_CLEAR_OS_KEYS
        self.cv_IPMI.ipmitool.run("raw 0x04 0x30 0xE8 0x00 0x40 0x00 0x00 0x00 0x00 0x00 0x00 0x00")

        # Read back the sensor value.
        # Expected Output is 4 bytes: where the first byte (ZZ) is the sensor value: ZZ 40 00 00
        output = self.cv_IPMI.ipmitool.run("raw 0x04 0x2D 0xE8")
        self.assertTrue("40 40 00 00" in output)
        
        # Special case, powering on this way since there is no appropriate state
        #  for the opened physical presence window
        self.cv_SYSTEM.sys_power_on()

        raw_pty = self.cv_SYSTEM.console.get_console()

        # Check for expected hostboot log output for a success physical presence assertion
        raw_pty.expect("Opened Physical Presence Detection Window", timeout=120)
        raw_pty.expect("System Will Power Off and Wait For Manual Power On", timeout=30)
        raw_pty.expect("shutdown complete", timeout=30)

        # Machine is off now, can resume using the state machine
        self.cv_SYSTEM.set_state(OpSystemState.OFF)

        # Turn it back on to complete the process
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        con = self.cv_SYSTEM.console
        con.run_command("test ! -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/physical-presence-asserted")
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/clear-os-keys")

        for k in ["PK", "KEK", "db", "dbx"]:
            # No keys should be enrolled, so size should be ascii "0" for each
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            self.assertTrue("0" in output)

            # Data should not contain anything
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            self.assertTrue("0" in output)


    def addSecureBootKeys(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        self.getTestData()

        for k in ["PK", "KEK", "db", "dbx"]:
            con.run_command("cat /tmp/{0}.auth > /sys/firmware/secvar/vars/{0}/update".format(k))

        # System needs to power fully off to process keys on next reboot
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)  
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")

        for k in ["PK", "KEK", "db", "dbx"]:
            # Size should return a nonzero ascii value when enrolled
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            self.assertFalse("0" in output)

            # Data should contain something
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            self.assertFalse("0" in output)


    def checkKexecKernels(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        self.getTestData(data="kernels")

        # Fail regular kexec_load
        output = con.run_command_ignore_fail("kexec -l /tmp/kernel-unsigned")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail unsigned kernel
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-unsigned")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail dbx kernel
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-dbx")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail signed kernel with unenrolled key
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-unenrolled")
        self.assertTrue("Permission denied" in "".join(output))
        
        # Succeed good kernel
        output = con.run_command("kexec -s /tmp/kernel-signed")


    def runTest(self):
        # skip test if the machine firmware doesn't support secure variables
        self.checkFirmwareSupport()

        # clean up any previous physical presence attempt
        self.cleanPhysicalPresence()

        # start in a clean secure boot state
        self.assertPhysicalPresence()

        # add secure boot keys
        self.addSecureBootKeys()

        # attempt to securely boot test kernels
        self.checkKexecKernels()

        # clean up after, and ensure keys are properly cleared
        self.assertPhysicalPresence()
        self.cleanPhysicalPresence()
