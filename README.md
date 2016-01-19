This repository provides a collection of tools that enable automated testing of
OpenPower systems.  The directories are as follows:

- ci: Tools to incorporate your OpenPower system into a continuous integration
      environment
- bvt: XML based build verification tool test suite that can be used to run
       existing (and create new) build verification tests
- testcases: Location to put testcases which require logic not suitable for a bvt
- common: Common python library used by all other tools


### Requirements ###

This framework runs on most Linux based systems.  You need python 2.7 or greater.
You also need expect and pexpect available.

### Examples ###


**BVT**

Run the op-ci-basic-bvt.xml which will update the BMC and PNOR images on the BMC, validate the partition comes up, and also validate a variety of reboots and IPMI commands.

    ./run-op-bvt --bmcip <bmc ip> --bmcuser <bmc userid> --bmcpwd <bmc passwd> --usernameipmi <ipmi login> --passwordipmi <ipmi passwd> --cfgfiledir "../ci/source/" --imagedir <dir of pnor image> --imagename palmetto.pnor --fverbose <dir/file for debug> ./op-ci-basic-bvt.xml

**CI**

### Notes ###

- Code Update works using the IPMITOOL.
- You need to have the bvt directory in your PATH


### TODO ###

- Should have the BVT tool call the common library directly (instead of going through CI)
- Should make the common code more generic to support alternative BMC's
- Should have bvt call the python code more directly (remove op-ci-bmc-run)
- Should use perl built-in's where available instead of using system() call
- Standardize on just expect or pexepect
