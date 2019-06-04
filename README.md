## OpenPower Test Framework ##

This repository provides a collection of tools that enable automated testing of
OpenPower systems. The op-test suite is designed to test a machine
largely out of band - that is, it is designed for tests that do things like
power cycle the machine, test booting different configurations. As part of
the op-test, we may run tests on the host itself (such as fwts
and HTX)

The end goal is to have a collection of tests that can be run against any
OpenPower system to validate it's function. The tests are automation/jenkins
ready.

For full documentation, visit http://open-power.github.io/op-test/

### Quick Start ###

OVERVIEW - Clone op-test on some linux box, like your laptop.

git clone https://github.com/open-power/op-test

Prepare the OpenPower system with needed software packages and build the
needed tools (see below Target System Requirements).

Run something (see below Running the tests).

### Requirements ###

This framework runs on most Linux based systems.

You need python 3.4 or greater and also needs below modules to be installed

    pip install pexpect importlib ptyprocess requests pysocks

    Optionally:  pip install unittest-xml-reporting unittest2
    For XML output: sudo apt-get install python3-xmlrunner

    For qemu: sudo apt-get install qemu-utils

You will also need below packages to be installed

        sshpass and (recent) ipmitool - 1.8.15 or above should be adequate.

You will need to run the test suite on a machine that has access to both
the BMC and the host of the machine(s) you're testing.

### Preparation ###

The target system will need to have a Host OS that can boot.
The Host OS will need to have several things installed on it.

This is a one time setup for the Host OS.  If you reinstall the
Host OS then these steps will need to be completed again to
prepare the Host OS for tests.

### Target System Requirements ###

A basic Linux install is assumed.

You **MUST** have `fwts` installed. To do this:

    sudo apt-get install software-properties-common
    sudo add-apt-repository ppa:firmware-testing-team/ppa-fwts-stable
    sudo apt-get update
    sudo apt-get install fwts

FWTS for RHEL-like systems will need to clone FWTS and build.

After cloning FWTS see the README for pre-reqs and how-to,
be sure to 'make install' after building to get the proper
paths setup.

git clone git://kernel.ubuntu.com/hwe/fwts.git

It must also have (package names for Debian/Ubuntu systems):

    linux-tools-common linux-tools-generic lm-sensors ipmitool i2c-tools
    pciutils opal-prd opal-utils device-tree-compiler

On RHEL-like systems, package names are:

    lm_sensors ipmitool i2c-tools pciutils kernel-tools dtc

On the Host OS, you will need to clone the skiboot source and then
build the following latest utilities.

    On the Host OS clone the skiboot source:
    git clone https://github.com/open-power/skiboot

    Then:
    cd skiboot/external/xscom-utils
    make
    sudo make install
    cd ../gard
    make
    sudo make install
    cd ../pflash
    make
    sudo make install

### Running the tests ###

    ./op-test -h

Gets you help on what you can run. You will need to (at a minimum) provide
BMC and host login information. For example, to run the default test suite:

    ./op-test --bmc-type AMI             \
              --bmc-ip bmc.example.com   \
              --bmc-username sysadmin    \
              --bmc-password superuser   \
              --bmc-usernameipmi ADMIN   \
              --bmc-passwordipmi admin   \
              --host-ip host.example.com \
              --host-user root           \
              --host-password 1234       \
              --host-lspci host.example.com-lspci.txt

The default test suite will then run.

To get a list of test suites:

    ./op-test --bmc-type AMI --list-suites

You cun run one or more suites by using the `--run-suite` command line option.
For example, you can choose to run tests that are only at the petitboot
command line. By default, the test runner doesn't know what state the machine
is in, so will attempt to turn everything off to get it into a known state.
You can override this initial state with the `--machine-state` parameter.
You can also run individual tests by using the `--run` option.

For example:

      ./op-test --bmc-type AMI                          \
                --bmc-ip bmc.example.com                \
                --bmc-username sysadmin                 \
                --bmc-password superuser                \
                --bmc-usernameipmi ADMIN                \
                --bmc-passwordipmi admin                \
                --host-ip host.example.com              \
                --host-user root                        \
                --host-password 1234                    \
                --host-lspci host.example.com-lspci.txt \
                --machine-state PETITBOOT_SHELL         \
                --run testcases.OpTestPCI.OpTestPCISkiroot

The above will assume the machine is sitting at the petitboot prompt
and will run the OpTestPCISkiroot test.

### Configuration Files ###

You can save arguments to `op-test` in a configuration file.
The `~/.op-test-framework.conf` file is always read, and you can
specify another with `--config-file`.

For example:

    [op-test]
    bmc_type=OpenBMC
    bmc_ip=w39
    bmc_username=root
    bmc_password=0penBmc
    host_ip=w39l
    host_user=ubuntu
    host_password=abc123

### Flashing Firmware ###

In addition to running tests, you can flash firmware before running
the tests. You can also only flash firmware (``--only-flash``).

      ./op-test --bmc-type FSP  ........ \
            --host-img-url http://example.com/images/firenze/b0628b_1726.861/SIGNED/01SV860_103_056.img \
            --flash-skiboot ~/skiboot/skiboot.lid --flash-kernel zImage.epapr \
            --flash-initramfs rootfs.cpio.xz

      ./op-test --bmc-type OpenBMC  ........ \
            --flash-skiboot ~/skiboot/skiboot.lid.xz

Flashing is BMC dependent, so new platforms may not support it.

The ``--host-img-url`` option for FSP systems uses ``update_flash`` from
the petitboot shell to update the firmware image. If additional ``--flash``
options are given, these are flashed *after* the FSP firmware image.
