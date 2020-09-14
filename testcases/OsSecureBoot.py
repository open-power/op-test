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
 - successfully load a signed kernel
 - assert physical presence
   - ensure machine is in a non-secure boot state


"""

# Location of the oskernels.tar and oskeys.tar test data files
# These belong somewhere else, possibly in the code tree?
# using a temporary link to the github page, this should probably be something more reliable
URL = "https://github.com/erichte-ibm/op-test/raw/erichte-ibm/os-secure-boot-squashed/test_binaries"

class OsSecureBoot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.OpIU = InstallUtil()


    def getTestData(self, data="keys"):
        con = self.cv_SYSTEM.console
        self.OpIU.configure_host_ip()

        fil = "os{}.tar".format(data)
        url = URL + "/" + fil

        con.run_command("wget {0} -O /tmp/{1}".format(url, fil))
        con.run_command("tar xf /tmp/{} -C /tmp/".format(fil))


    def checkKeysEnrolled(self, enrolled=True):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        assertfunc = self.assertFalse if enrolled else self.assertTrue

        for k in ["PK", "KEK", "db", "dbx"]:
            # Size should return a nonzero ascii value when enrolled
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            assertfunc("0" in output)

            # Data should contain something
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            assertfunc("0" in output)


    def checkSecureBootEnabled(self, enabled=True, physical=False):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        con.run_command("test {} -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing"
            .format("" if enabled else "!"))

        if physical:
            con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/physical-presence-asserted")
            con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/clear-os-keys")


    def checkFirmwareSupport(self):
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

        self.checkSecureBootEnabled(enabled=False, physical=True)
        self.checkKeysEnrolled(enrolled=False)


    def addSecureBootKeys(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        self.getTestData()

        for k in ["PK", "KEK", "db", "dbx"]:
            con.run_command("cat /tmp/{0}.auth > /sys/firmware/secvar/vars/{0}/update".format(k))

        # System needs to power fully off to process keys on next reboot
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)  
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        self.checkSecureBootEnabled(enabled=True)
        self.checkKeysEnrolled(enrolled=True)


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
        
        # Succeed good kernel
        output = con.run_command("kexec -s /tmp/kernel-signed")
        self.assertFalse("Permission denied" in "".join(output)) # may not be needed, command should fail


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
