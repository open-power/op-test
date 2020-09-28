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
  NOTE: these tools will currently only build on x86
 Running make generates and assembles a set of openssl keys, ESLs, and signed auth files following the
  commands below.
 Only the auth files are included in the tarball.

 Generating keys (PK example):
  openssl req -new -x509 -newkey rsa:2048 -subj "/CN=PK/" -keyout PK.key -out PK.crt -days 3650 -nodes -sha256

 Generating ESLs (PK example):
  cert-to-efi-sig-list PK.crt PK.esl

 Generating Auths:
  sign-efi-sig-list -k PK.key -c PK.crt PK PK.esl PK.auth
  sign-efi-sig-list -k PK.key -c PK.crt KEK KEK.esl KEK.auth
  sign-efi-sig-list -k KEK.key -c KEK.crt db db.esl db.auth
  sign-efi-sig-list -k KEK.key -c KEK.crt dbx dbx.esl dbx.auth

 NOTE: dbx.esl is currently generated using a soon-to-be-released internal tool, and will be integrated in this test/documentation
 Normally, dbx.esl would be generated with hash-to-efi-sig-list, however that tool has a dependency on PECOFF which
  is not compatible with POWER.
 NOTE: newPK is signed by the PK to test updating the PK, and deletePK is an empty file signed by newPK
  to test the removal of a PK, which exits secure boot enforcement mode.


Generating oskernels.tar:
 kernel-unsigned   - very stripped down kernel built with minimal config options. no signature
 kernel-signed     - same kernel as above, signed with the db present in oskeys.tar
 kernel-unenrolled - same kernel, signed with another generated key that is NOT in oskeys.tar
 kernel-dbx        - same kconfig, but adjusted version name. signed with the same db key. hash present in oskeys.tar's dbx

Signing kernels:
 Kernels are signed with the `sign-file` utility in the linux source tree, like so:
  ./scripts/sign-file sha256 db.key db.crt vmlinuz kernel-signed

"""


# Variable data after enrollment (located in /sys/firmware/secvar/vars/<variable name>/data should
#  be in the ESL format, WITHOUT the signed update auth header.
# These hashes are of the ESL data prior to signing the data as an update, and should match the
#  post-enrollment data
# Future work: generate the full set of key/crt->ESL->auth data as part of this test, and
#  calculate the expected hashes from the generated ESL rather than hardcoding them here.
esl_hashes = {
    "PK":    "91f15df8fc8f80bd0a1bbf2c77a5c5a16d2b189dd6f14d7b7c1e274fedd53f47",
    "KEK":   "1b6e26663bbd4bbb2b44af9e36d14258cdf700428f04388b0c689696450a9544",
    "db":    "480b652075d7b52ce07577631444848fb1231d6e4da9394e6adbe734795a7eb2",
    "dbx":   "2310745cd7756d9bfd8cacf0935a27a7bd1d2f1b1783da03902b5598a0928da6",
    "newPK": "9a1d186c08c18887b68fadd81be48bca06dd007fa214dfcdb0f4195b5aff996c",
}

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


    # Assert physical presence remotely to remove any currently installed OS secure boot keys
    #  NOTE: This is NOT something an end-user should expect to do, there is a different process
    #   for a physical presence assertion that actually requires physical access on production machines
    #  This is included in the test to make sure the machine is in a clean initial state, and also
    #   to ensure that skiboot handles physical presence key clear reset requests properly.
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

        # The rest of this function applies to the physical presence assertion of a production machine,
        #  and should behave the same way.

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

        # After a physical presence, the firmware should NOT be enforcing secure boot as there should be
        #  no PK (or other secure boot keys)
        con.run_command("test ! -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")

        # After a physical presence clear, there should be device tree entries indicating that
        #  1. a physical presence was asserted, and
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/physical-presence-asserted")
        #  2. what request was made, in this case clearing of os secureboot keys
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/clear-os-keys")

        # As mentioned before, no keys should be enrolled, double check to make sure each is empty
        for k in ["PK", "KEK", "db", "dbx"]:
            # Size should be ascii "0" for each, as each should be empty
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            self.assertTrue("0" in output)

            # Data should not contain anything
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            self.assertTrue("0" in output)


    # Enroll keys to enable secure boot
    #  Keys are generated ahead of time, following the process outlined at the top of this file
    #  See: "Generating oskeys.tar"
    def addSecureBootKeys(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        # Fetch the pregenerated test data containing the signed update files
        #  Future work: generate these test files are part of the test case (dependent on efitools/secvarctl)
        self.getTestData()

        # Enqueue the PK update first, will enter secure mode and enforce signature
        #  checking for the remaining updates below
        con.run_command("cat /tmp/PK.auth > /sys/firmware/secvar/vars/PK/update")

        # Enqueue the KEK update
        con.run_command("cat /tmp/KEK.auth > /sys/firmware/secvar/vars/KEK/update")

        # Enqueue the db update, this contains the key needed for validating signed kernels
        con.run_command("cat /tmp/db.auth > /sys/firmware/secvar/vars/db/update")

        # Enqueue the dbx update, contains a list of denylisted kernel hashes
        con.run_command("cat /tmp/dbx.auth > /sys/firmware/secvar/vars/dbx/update")

        # System needs to power fully off to process keys on next reboot
        #  Key updates are only processed as skiboot initializes
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)  
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        # If all key updates were processed successfully, then we should have entered secure mode
        #  This device tree entry is created if a PK is present, and forces skiroot to only kexec
        #  properly signed kernels with a key in the db variable.
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")

        # Loop through and double check that all the variables now contain data
        for k in ["PK", "KEK", "db", "dbx"]:
            # Size should return a nonzero ascii value when enrolled
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            self.assertFalse("0" in output)

            # Data should contain the ESL data as generated before
            #  NOTE: this is NOT the same as the .auth data, the auth header and signature are removed
            #  as part of processing the update
            # Future work: compare the /data field against the generated ESL data
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            self.assertFalse("0" in output)

            # Check the integrity of the data by hashing and comparing against an expected hash
            # See top of the file for how these hashes were calculated
            output = con.run_command("sha256sum /sys/firmware/secvar/vars/{}/data".format(k))
            # output is of the form ["<hash> <filename>"], so extract just the hash value to compare
            output = output[0].split(" ")[0]
            self.assertTrue(esl_hashes[k] == output)


    # Attempt to kexec load a set of kernels to ensure secure mode is enforced correctly
    def checkKexecKernels(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        con = self.cv_SYSTEM.console

        # Obtain pregenerated test kernels, see top of file for how these were generated
        self.getTestData(data="kernels")

        # Fail regular kexec_load, syscall should be disabled by skiroot when enforcing secure boot
        #  Petitboot should automatically use avoid using this syscall when applicable
        output = con.run_command_ignore_fail("kexec -l /tmp/kernel-unsigned")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail using kexec_file_load with an unsigned kernel
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-unsigned")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail loading a kernel whose hash is in the dbx denylist
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-dbx")
        self.assertTrue("Permission denied" in "".join(output))

        # Fail loading a properly signed kernel with key that is NOT enrolled in the db
        #  Future work: enroll the key used to sign this kernel and try again
        output = con.run_command_ignore_fail("kexec -s /tmp/kernel-unenrolled")
        self.assertTrue("Permission denied" in "".join(output))

        # Successfully kexec_file_load a kernel signed with a key in the db
        output = con.run_command("kexec -s /tmp/kernel-signed")

    # To replace the PK, sign a new PK esl with the previous PK
    #  Replacing the PK will not change the secure enforcing status, nor will
    #  it remove the other variables
    # To delete the PK, sign an empty file with the PK. The update processing
    #  logic will interpret this as a deletion.
    #  NOTE: removing the PK DISABLES OS secure boot enforcement, but will NOT
    #   clear your other variables.
    def replaceAndDeletePK(self):
        con = self.cv_SYSTEM.console

        # Obtain tarball containing a replacement PK
        self.getTestData(data="keys")

        # Enqueue an update to the PK
        #  New PK updates must be signed with the previous PK
        con.run_command("cat /tmp/newPK.auth > /sys/firmware/secvar/vars/PK/update")

        # Reboot the system to process the update
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        # Confirm we are still enforcing secure boot
        con.run_command("test -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")

        # Check that the new PK is enrolled now
        output = con.run_command("sha256sum /sys/firmware/secvar/vars/PK/data")
        output = output[0].split(" ")[0]
        self.assertTrue(esl_hashes["newPK"] == output)

        # Obtain tarball containing a PK deletion update
        self.getTestData(data="keys")

        # Enqueue a deletion update to the PK
        #  This update is a signed empty file, which is interpreted as a deletion action
        con.run_command("cat /tmp/deletePK.auth > /sys/firmware/secvar/vars/PK/update")

        # Reboot the system to process the update
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        # Secure boot enforcement should now be DISABLED
        con.run_command("test ! -f /sys/firmware/devicetree/base/ibm,secureboot/os-secureboot-enforcing")

        # PK size should be empty now
        output = con.run_command("cat /sys/firmware/secvar/vars/PK/size")
        self.assertTrue("0" in output)

        # PK data should not contain any data
        output = con.run_command("cat /sys/firmware/secvar/vars/PK/data | wc -c")
        self.assertTrue("0" in output)

        # Loop through and double check that all the other variables still contain their data
        # This is the same logic as in .addSecureBootKeys()
        for k in ["KEK", "db", "dbx"]:
            output = con.run_command("cat /sys/firmware/secvar/vars/{}/size".format(k))
            self.assertFalse("0" in output)

            output = con.run_command("cat /sys/firmware/secvar/vars/{}/data | wc -c".format(k))
            self.assertFalse("0" in output)

            output = con.run_command("sha256sum /sys/firmware/secvar/vars/{}/data".format(k))
            output = output[0].split(" ")[0]
            self.assertTrue(esl_hashes[k] == output)


    def runTest(self):
        # skip test if the machine firmware doesn't support secure variables
        self.checkFirmwareSupport()

        # clean up any previous physical presence attempt
        self.cleanPhysicalPresence()

        # start in a clean secure boot state
        self.assertPhysicalPresence()
        self.cleanPhysicalPresence()

        # add secure boot keys
        self.addSecureBootKeys()

        # attempt to securely boot test kernels
        self.checkKexecKernels()

        # replace PK, delete PK
        self.replaceAndDeletePK()

        # clean up after, and ensure keys are properly cleared
        self.assertPhysicalPresence()
        self.cleanPhysicalPresence()
