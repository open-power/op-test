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
URL = "http://SET.THIS.TO.SOMETHING"

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


    def assertPhysicalPresence(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)

        self.cv_BMC.image_transfer("test_binaries/physicalPresence.bin")
        self.cv_BMC.run_command("cp /tmp/physicalPresence.bin /usr/local/share/pnor/ATTR_TMP")
        self.cv_BMC.run_command("echo '0 0x283a 0x15000000' > /var/lib/obmc/cfam_overrides")
        self.cv_BMC.run_command("echo '0 0x283F 0x20000000' >> /var/lib/obmc/cfam_overrides")

        self.cv_IPMI.ipmitool.run("raw 0x04 0x30 0xE8 0x00 0x40 0x00 0x00 0x00 0x00 0x00 0x00 0x00")
        output = self.cv_IPMI.ipmitool.run("raw 0x04 0x2D 0xE8")
        self.assertTrue("40 40 00 00" in output)
        
        self.cv_SYSTEM.sys_power_on()

        raw_pty = self.cv_SYSTEM.console.get_console()

        raw_pty.expect("Opened Physical Presence Detection Window", timeout=120)
        raw_pty.expect("System Will Power Off and Wait For Manual Power On", timeout=30)
        raw_pty.expect("shutdown complete", timeout=30)

        # Shut itself off, turn it back on
        # Need to turn it on by the BMC for some reason?
        self.cv_BMC.run_command("obmcutil power on")

        # This is apparently needed because otherwise op-test can't determine
        # the state of the machine?
        self.cv_SYSTEM.sys_check_host_status()

        self.checkSecureBootEnabled(enabled=False, physical=True)
        self.checkKeysEnrolled(enrolled=False)


    def addSecureBootKeys(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        self.getTestData()

        for k in ["PK", "KEK", "db", "dbx"]:
            con.run_command("cat /tmp/{0}.auth > /sys/firmware/secvar/vars/{0}/update".format(k))

        # System needs to power fully off to process keys on next reboot
        # need to stall because otherwise it just blows on through on its own
        # hopefully one of these two actually powers it off
        self.cv_SYSTEM.sys_power_off()
        time.sleep(10)
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)  
        time.sleep(10)

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
        # start clean
        self.assertPhysicalPresence()

        # add secure boot keys
        self.addSecureBootKeys()

        # attempt to securely boot test kernels
        self.checkKexecKernels()

        # clean up after 
        self.assertPhysicalPresence()
