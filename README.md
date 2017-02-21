## OpenPower Test Framework ##

This repository provides a collection of tools that enable automated testing of
OpenPower systems. The op-test-framework suite is designed to test a machine
largely out of band - that is, it is designed for tests that do things like
power cycle the machine, test booting different configurations. As part of
the op-test-framework, we may run tests on the host itself (such as fwts
and HTX)

The end goal is to have a collection of tests that can be run against any
OpenPower system to validate it's function. The tests are automation/jenkins
ready.

### Requirements ###

This framework runs on most Linux based systems.

You need python 2.7 or greater.

You will also need (recent) ipmiutil - 1.8.15 or above should be adequate.

You will need to run the test suite on a machine that has access to both
the BMC and the host of the machine(s) you're testing.

### Preparation ###

The target system will need to have an OS that can boot. That OS will
need to have several things installed on it.

A TODO item is to document what that is.

### Target System Requirements ###

A basic Linux install is assumed.

You **MUST** have `fwts` installed. To do this:

    sudo apt-get install software-properties-common
    sudo add-apt-repository ppa:firmware-testing-team/ppa-fwts-stable
    sudo apt-get update
    sudo apt-get install fwts

It must also have:

    linux-tools-common linux-tools-generic

### Running the tests ###

    ./op-test -h

Gets you help on what you can run. You will need to (at a minimum) provide
BMC and host login information. For example, to run the default test suite:

    ./op-test --bmc-ip bmc.example.com   \
    	      --bmc-username sysadmin    \
	      --bmc-password superuser   \
	      --bmc-usernameipmi ADMIN   \
	      --bmc-passwordipmi admin   \
	      --host-ip host.example.com \
	      --host-user root		 \
	      --host-password 1234	 \
	      --host-lspci host.example.com-lspci.txt

The default test suite will then run.

To get a list of test suites:

    ./op-test --list-suites

You cun run one or more suites by using the `--run-suite` command line option.
For example, you can choose to run tests that are only at the petitboot
command line. By default, the test runner doesn't know what state the machine
is in, so will attempt to turn everything off to get it into a known state.
You can override this initial state with the `--machine-state` parameter.
You can also run individual tests by using the `--run` option.

For example:

      ./op-test --bmc-ip bmc.example.com \
      		--bmc-username sysadmin  \
		--bmc-password superuser \
		--bmc-usernameipmi ADMIN \
		--bmc-passwordipmi admin \
		--host-ip host.example.com \
		--host-user root 	   \
		--host-password 1234	   \
		--host-lspci host.example.com-lspci.txt \
		--machine-state PETITBOOT_SHELL \
		--run testcases.OpTestPCI.OpTestPCISkiroot

The above will assume the machine is sitting at the petitboot prompt
and will run the OpTestPCISkiroot test.

