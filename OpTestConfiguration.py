
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

        bmcgroup = parser.add_argument_group('BMC',
                                             'Options for Service Processor')
        bmcgroup.add_argument("--bmc-type",
                              choices=['AMI','FSP', 'OpenBMC', 'qemu'],
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
        bmcgroup.add_argument("--skiboot", default="skiboot.lid",
                              help="[QEMU Only] skiboot.lid")
        bmcgroup.add_argument("--kernel", default="zImage.epapr",
                              help="[QEMU Only] petitboot zImage.epapr")
        bmcgroup.add_argument("--initramfs", default="rootfs.cpio.xz",
                              help="[QEMU Only] petitboot rootfs")

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
        imagegroup.add_argument("--firmware-images", help="Firmware images directory")
        imagegroup.add_argument("--host-pnor", help="PNOR image to flash")
        imagegroup.add_argument("--host-lid", help="Skiboot LID to flash")
        imagegroup.add_argument("--host-hpm", help="HPM image to flash")

        self.args , self.remaining_args = parser.parse_known_args(argv)
        stateMap = { 'UNKNOWN' : OpSystemState.UNKNOWN,
                     'OFF' : OpSystemState.OFF,
                     'PETITBOOT' : OpSystemState.PETITBOOT,
                     'PETITBOOT_SHELL' : OpSystemState.PETITBOOT_SHELL,
                     'OS' : OpSystemState.OS
                 }

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
                             self.args.skiboot,
                             self.args.kernel,
                             self.args.initramfs)
            self.op_system = OpTestQemuSystem(host=host, bmc=bmc)
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
