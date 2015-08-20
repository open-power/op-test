This repository provides a collection of tools that enable automated testing of
OpenPower systems.  The directories are as follows:

- TBD - flash: Tools to upgrade firmware on your BMC
- TBD - boot: Tools to test the booting of your OpenPower system
- ci: Tools to incorporate your OpenPower system into a continuous integration
      environment
- bvt: XML based build verification tool test suite that can be used to run
       existing (and create new) build verification tests
- common: Common python library used by all other tools

Please note that this is very basic now.  Our example below will reboot the BMC
and then validate a boot of the system.

The ability to update the image is broken due to the BMC removing the rsync
tool.  This issue is being worked, for now the pnor udpate has to be
manually done.

### Requirements ###

This framework runs on most Linux based systems.  You need python 2.7 or greater.
You also need expect and pexpect available.

### Examples ###

**Flash**

**Boot**

**BVT**

Run the op-ci-basic-bvt.xml which will update (TBD) the PNOR image on the BMC and
validate a boot of the system.

    ./run-op-bvt --bmcip <bmc ip> --bmcuser <bmc userid> --bmcpwd <bmc passwd> --usernameipmi <ipmi login> --passwordipmi <ipmi passwd> --cfgfiledir "../ci/source/" --imagedir <dir of pnor image> --imagename palmetto.pnor --fverbose <dir/file for debug> ./op-ci-basic-bvt.xml

**CI**

### Notes ###

- Code Update does not work currently, you need to flash the HPM you want to test.
- You need to have the bvt directory in your PATH


### TODO ###

- Should have the BVT tool call the common library directly (instead of going through CI)
- Should make the common code more generic to support alternative BMC's
- Should have bvt call the python code more directly (remove op-ci-bmc-run)
- Should use perl built-in's where available instead of using system() call
- Standardize on just expect or pexepect
