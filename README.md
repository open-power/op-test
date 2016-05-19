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

You will also need (recent) ipmiutil - 1.8.15 or above should be adequate.

### Preparation ###

**Machine Configuration**

Copy the bvt/op-machines-example.xml file and use its layout (specified
in bvt/op-machines.xsd) to specify the machines in your test lab.

The machines.xml should be kept *private* as it will contain passwords
for machines.

**Known good firmware**

It's good to supply known good firmware so that if everything goes horribly
wrong running the regression tests, the test suite can attempt to un-brick
the machine with known good firmware.

This is useful in a lab environment where the machines are shared.

**Firmware to test**

Firmware to test can either already be on the target machine, or can be
flashed by the test harness.

Put firmware in firmware-to-test/platform/

For example, for ibm,garrison platform, firmware-to-test/ibm,garrison/ would
be the directory to place the firmware for a Garrison machine. In this case,
it would be the garrison.pnor and/or HPM files.

### Running the tests ###

    ./run --machines machines.xml --machine my-openpower-box

### Notes ###

- You need to have the bvt directory in your PATH


### TODO ###

- Should have the BVT tool call the common library directly (instead of going through CI)
- Should make the common code more generic to support alternative BMC's
- Should have bvt call the python code more directly (remove op-ci-bmc-run)
- Should use perl built-in's where available instead of using system() call
- Standardize on just expect or pexepect
