## OpenPower Test Framework ##

This repository provides a collection of tools that enable automated testing of
OpenPower systems.  

The end goals is to have a collection of build verification tests (bvt) that can be run against any OpenPower system to validate it's function.  The tests are automation/jenkins ready. The tests cover basic functionality like software updates and low level firmware features, all the way up to OS and OPAL functional tests.  

The **common** directory is where we abstract the OpenPower system interfaces.  It provides the generic API's (and detailed implementations) of interfaces required by the test cases.

The **bvt** directory is where the test executions are defined.  These tests are xml based.  They may call into the common to run the tests directly or they may call into the **testcases** directory for tests that require more logic.

The ci directory is left over from some legacy continuous integration work.  The BVT's currently use CI as a pass through to execute the tests.  We have a TODO to remove the CI function eventually.



### Requirements ###

This framework runs on most Linux based systems.  You need python 2.7 or greater.
You also need expect and pexpect available.
And also below perl modules are required in order to run this framework.
on fedora: sudo yum install perl-XML-LibXML-Common
on ubuntu: sudo aptitude install libxml-libxml-perl

### Examples ###


**BVT**

Run the op-ci-basic-bvt.xml which will update the BMC and PNOR images on the BMC, validate the partition comes up, and also validate a variety of reboots and IPMI commands.

    ./run-op-bvt --bmcip <bmc ip> --bmcuser <bmc userid> --bmcpwd <bmc passwd> --usernameipmi <ipmi login> --passwordipmi <ipmi passwd> --cfgfiledir "../ci/source/" --imagedir <dir of pnor image> --imagename palmetto.pnor ./op-ci-basic-bvt.xml

### Notes ###

- Code Update works using the IPMITOOL.
- You need to have the bvt directory in your PATH


### TODO ###

- Should have the BVT tool call the common library directly (instead of going through CI)
- Should make the common code more generic to support alternative BMC's
- Should have bvt call the python code more directly (remove op-ci-bmc-run)
- Should use perl built-in's where available instead of using system() call
- Standardize on just expect or pexepect
