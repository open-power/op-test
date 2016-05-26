## OpenPower Test Framework ##

This repository provides a collection of tools that enable automated testing of
OpenPower systems. The op-test-framework suite is designed to test a machine
largely out of band - that is, it is designed for tests that do things like
power cycle the machine, test booting different configurations. As part of
the op-test-framework, we may run tests on the host itself (such as fwts
and HTX)

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

You will need to run the test suite on a machine that has access to both
the BMC and the host of the machine(s) you're testing.

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

The identifier 'my-openpower-box' is the name attribute of the Machine
specified in the machines.xml file.

You can get more information about invoking the tests with:

    ./run --help

By default, we will run the op-ci-basic-bvt.xml (in bvt/) test suite.
To run a different suite, use the --suite paramater.

### Test Suites ###

You can run the following suites:

* op-ci-basic-bvt.xml : Firmware code update(HPM Based upgradation), IPL and IPMI power control commands
* op-opal-ci-bvt.xml:  Flash PNOR FW and IPL
* op-firmware-component-update-bvt.xml : For Out-of-band FW upgrade(using hpm upgrade)
* op-inbound-basic-bvt.xml :  For in-band FW upgrade(hpm upgrade)
* op-opal-fvt-bvt.xml : For OPAL Functional tests

### Notes ###

- You need to have the bvt directory in your PATH


### TODO ###

- Should have the BVT tool call the common library directly (instead of going through CI)
- Should make the common code more generic to support alternative BMC's
- Should have bvt call the python code more directly (remove op-ci-bmc-run)
- Standardize on just expect or pexepect
