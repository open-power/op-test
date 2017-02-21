
# This implements all the configuration needs for running a test
# It includes command line argument parsing and keeping a set
# of OpTestSystem and similar objects around for tests to use.

import common
from common.OpTestBMC import OpTestBMC
from common.OpTestSystem import OpTestSystem, OpSystemState
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
                              choices=['AMI','FSP'],
                              help="Type of service processor")
        bmcgroup.add_argument("--bmc-ip", help="BMC address")
        bmcgroup.add_argument("--bmc-username", help="SSH username for BMC")
        bmcgroup.add_argument("--bmc-password", help="SSH password for BMC")
        bmcgroup.add_argument("--bmc-usernameipmi", help="IPMI username for BMC")
        bmcgroup.add_argument("--bmc-passwordipmi", help="IPMI password for BMC")
        bmcgroup.add_argument("--bmc-prompt", default="#",
                              help="Prompt for BMC ssh session")

        hostgroup = parser.add_argument_group('Host', 'Installed OS information')
        hostgroup.add_argument("--host-ip", help="Host address")
        hostgroup.add_argument("--host-user", help="SSH username for Host")
        hostgroup.add_argument("--host-password", help="SSH password for Host")
        hostgroup.add_argument("--host-lspci", help="Known 'lspci -n -m' for host")
        hostgroup.add_argument("--host-prompt", default="#",
                               help="Prompt for Host SSH session")

        hostgroup.add_argument("--platform",
                               help="Platform (used for EnergyScale tests)",
                               choices=['habanero','firestone','garrison'])

        ffdcgroup = parser.add_argument_group('FFDC', 'First Failure Data Capture')
        ffdcgroup.add_argument("--ffdcdir", help="FFDC directory")

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
        bmc = OpTestBMC(ip=self.args.bmc_ip,
                             username=self.args.bmc_username,
                             password=self.args.bmc_password)
        self.op_system = OpTestSystem(
            i_bmcUserIpmi=self.args.bmc_usernameipmi,
            i_bmcPasswdIpmi=self.args.bmc_passwordipmi,
            i_ffdcDir=self.args.ffdcdir,
            i_hostip=self.args.host_ip,
            i_hostuser=self.args.host_user,
            i_hostPasswd=self.args.host_password,
            state=self.startState,
            bmc=bmc
        )

        return

    def bmc(self):
        return self.op_system.bmc()
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
