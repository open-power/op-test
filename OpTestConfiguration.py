
# This implements all the configuration needs for running a test
# It includes command line argument parsing and keeping a set
# of OpTestSystem and similar objects around for tests to use.

import common
from common.OpTestBMC import OpTestBMC
from common.OpTestFSP import OpTestFSP
from common.OpTestOpenBMC import OpTestOpenBMC
from common.OpTestQemu import OpTestQemu
from common.OpTestSystem import OpTestSystem, OpSystemState, OpTestFSPSystem, OpTestOpenBMCSystem, OpTestQemuSystem
from common.OpTestHost import OpTestHost
from common.OpTestIPMI import OpTestIPMI
from common.OpTestOpenBMC import HostManagement
from common.OpTestWeb import OpTestWeb
import argparse
import time

# Look at the addons dir for any additional OpTest supported types
# If new type was called Kona, the layout would be as follows
# op-test-framework/addons/Kona/
#                              /OpTestKona.py
#                              /OpTestKonaSystem.py
#                              /OpTestKonaSetup.py
#
# OpTestKona and OpTestKonaSystem follow the same format the other supported type modules
# OpTestKonaSetup is unique for the addons and contains 2 helper functions:
# addBMCType - used to populate the choices list for --bmc-type
# createSystem - does creation of bmc and op_system objects

import importlib
import os
import addons
optAddons = dict() # Store all addons found.  We'll loop through it a couple time below
# Look at the top level of the addons for any directories and load their Setup modules
for dir in (os.walk('addons').next()[1]):
    optAddons[dir] = importlib.import_module("addons." + dir + ".OpTest" + dir + "Setup")

class OpTestConfiguration():
    def __init__(self):
        self.args = []
        self.remaining_args = []
        return

    def parse_args(self, argv=None):
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        tgroup = parser.add_argument_group('Test',
                                           'Tests to run')
        tgroup.add_argument("--list-suites", action='store_true',
                            help="List available suites to run")
        tgroup.add_argument("--run-suite", action='append',
                            help="Run a test suite(s)")
        tgroup.add_argument("--run", action='append',
                            help="Run individual tests")

        parser.add_argument("--machine-state", help="Current machine state",
                            choices=['UNKNOWN', 'OFF', 'PETITBOOT',
                                     'PETITBOOT_SHELL', 'OS'])

        # Options to set the output directory and suffix on the output
        parser.add_argument("-o", "--output", help="Output directory for test reports.  Can also be set via OP_TEST_OUTPUT env variable.")
        parser.add_argument("--suffix", help="Suffix to add to all reports.  Default is current time.")

        bmcgroup = parser.add_argument_group('BMC',
                                             'Options for Service Processor')
        # The default supported BMC choices in --bmc-type
        bmcChoices = ['AMI','FSP', 'OpenBMC', 'qemu']
        # Loop through any addons let it append the extra bmcChoices
        for opt in optAddons:
            bmcChoices = optAddons[opt].addBMCType(bmcChoices)
        bmcgroup.add_argument("--bmc-type",
                              choices=bmcChoices,
                              help="Type of service processor")
        bmcgroup.add_argument("--bmc-ip", help="BMC address")
        bmcgroup.add_argument("--bmc-username", help="SSH username for BMC")
        bmcgroup.add_argument("--bmc-password", help="SSH password for BMC")
        bmcgroup.add_argument("--bmc-usernameipmi", help="IPMI username for BMC")
        bmcgroup.add_argument("--bmc-passwordipmi", help="IPMI password for BMC")
        bmcgroup.add_argument("--bmc-prompt", default="#",
                              help="Prompt for BMC ssh session")
        bmcgroup.add_argument("--qemu-binary", default="qemu-system-ppc64",
                              help="[QEMU Only] qemu simulator binary")

        hostgroup = parser.add_argument_group('Host', 'Installed OS information')
        hostgroup.add_argument("--host-ip", help="Host address")
        hostgroup.add_argument("--host-user", help="SSH username for Host")
        hostgroup.add_argument("--host-password", help="SSH password for Host")
        hostgroup.add_argument("--host-lspci", help="Known 'lspci -n -m' for host")
        hostgroup.add_argument("--host-prompt", default="#",
                               help="Prompt for Host SSH session")

        hostgroup.add_argument("--platform",
                               help="Platform (used for EnergyScale tests)",
                               choices=['unknown','habanero','firestone','garrison','firenze'])

        ffdcgroup = parser.add_argument_group('FFDC', 'First Failure Data Capture')
        ffdcgroup.add_argument("--ffdcdir", help="FFDC directory")

        imagegroup = parser.add_argument_group('Images', 'Firmware LIDs/images to flash')
        imagegroup.add_argument("--host-pnor", help="PNOR image to flash")
        imagegroup.add_argument("--host-hpm", help="HPM image to flash")
        imagegroup.add_argument("--host-img-url", help="URL to Host Firmware image to flash on FSP systems (Must be URL accessible petitboot shell on the host)")
        imagegroup.add_argument("--flash-skiboot",
                              help="skiboot to use/flash. Depending on platform, may need to be xz compressed")
        imagegroup.add_argument("--flash-kernel",
                              help="petitboot zImage.epapr to use/flash.")
        imagegroup.add_argument("--flash-initramfs",
                              help="petitboot rootfs to use/flash. Not all platforms support this option")
        imagegroup.add_argument("--noflash", action='store_true', default=False,
                                help="Even if images are specified, don't flash them")
        imagegroup.add_argument("--only-flash", action='store_true', default=False,
                                help="Only flash, don't run any tests (even if specified)")
        imagegroup.add_argument("--pflash",
                                help="pflash to copy to BMC (if needed)")

        self.args , self.remaining_args = parser.parse_known_args(argv)
        stateMap = { 'UNKNOWN' : OpSystemState.UNKNOWN,
                     'OFF' : OpSystemState.OFF,
                     'PETITBOOT' : OpSystemState.PETITBOOT,
                     'PETITBOOT_SHELL' : OpSystemState.PETITBOOT_SHELL,
                     'OS' : OpSystemState.OS
                 }

        # Setup some defaults for the output options
        # Order of precedence
        # 1. cmdline arg
        # 2. env variable
        # 3. default path
        if (self.args.output):
            outdir = self.args.output
        elif ("OP_TEST_OUTPUT" in os.environ):
            outdir = os.environ["OP_TEST_OUTPUT"]
        else:
            outdir = "test-reports"

        # Normalize the path to fully qualified and create if not there
        self.output = os.path.abspath(outdir)
        if (not os.path.exists(self.output)):
            os.makedirs(self.output)

        # Grab the suffix, if not given use current time
        if (self.args.suffix):
            self.outsuffix = self.args.suffix
        else:
            self.outsuffix = time.strftime("%Y%m%d%H%M%S")

        if self.args.machine_state == None:
            self.startState = OpSystemState.UNKNOWN
        else:
            self.startState = stateMap[self.args.machine_state]
        return self.args, self.remaining_args

    def objs(self):
        host = OpTestHost(self.args.host_ip,
                          self.args.host_user,
                          self.args.host_password,
                          self.args.bmc_ip)
        if self.args.bmc_type in ['AMI']:
            ipmi = OpTestIPMI(self.args.bmc_ip,
                              self.args.bmc_usernameipmi,
                              self.args.bmc_passwordipmi,
                              self.args.ffdcdir, host=host)
            web = OpTestWeb(self.args.bmc_ip,
                            self.args.bmc_usernameipmi,
                            self.args.bmc_passwordipmi)
            bmc = OpTestBMC(ip=self.args.bmc_ip,
                            username=self.args.bmc_username,
                            password=self.args.bmc_password,
                            ipmi=ipmi,
                            web=web,
            )
            self.op_system = OpTestSystem(
                i_ffdcDir=self.args.ffdcdir,
                state=self.startState,
                bmc=bmc,
                host=host,
            )
        elif self.args.bmc_type in ['FSP']:
            ipmi = OpTestIPMI(self.args.bmc_ip,
                              self.args.bmc_usernameipmi,
                              self.args.bmc_passwordipmi,
                              self.args.ffdcdir, host=host)
            bmc = OpTestFSP(self.args.bmc_ip,
                            self.args.bmc_username,
                            self.args.bmc_password,
                            ipmi=ipmi,
            )
            self.op_system = OpTestFSPSystem(
                i_ffdcDir=self.args.ffdcdir,
                state=self.startState,
                bmc=bmc,
                host=host,
            )
        elif self.args.bmc_type in ['OpenBMC']:
            ipmi = OpTestIPMI(self.args.bmc_ip,
                              self.args.bmc_usernameipmi,
                              self.args.bmc_passwordipmi,
                              self.args.ffdcdir, host=host)
            rest_api = HostManagement(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password)
            bmc = OpTestOpenBMC(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password,
                                ipmi=ipmi, rest_api=rest_api)
            self.op_system = OpTestOpenBMCSystem(
                host=host,
                bmc=bmc,
                state=self.startState,
            )
        elif self.args.bmc_type in ['qemu']:
            print repr(self.args)
            bmc = OpTestQemu(self.args.qemu_binary,
                             self.args.flash_skiboot,
                             self.args.flash_kernel,
                             self.args.flash_initramfs)
            self.op_system = OpTestQemuSystem(host=host, bmc=bmc)
        # Check that the bmc_type exists in our loaded addons then create our objects
        elif self.args.bmc_type in optAddons:
            (bmc, self.op_system) = optAddons[self.args.bmc_type].createSystem(self, host)
        else:
            raise Exception("Unsupported BMC Type")

        return

    def bmc(self):
        return self.op_system.bmc
    def system(self):
        return self.op_system
    def host(self):
        return self.op_system.host()
    def ipmi(self):
        return self.op_system.ipmi()

    def lspci_file(self):
        return self.args.host_lspci

    def platform(self):
        return self.args.platform

global conf
conf = OpTestConfiguration()
