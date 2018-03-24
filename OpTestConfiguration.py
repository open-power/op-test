
# This implements all the configuration needs for running a test
# It includes command line argument parsing and keeping a set
# of OpTestSystem and similar objects around for tests to use.

import common
from common.OpTestBMC import OpTestBMC, OpTestSMC
from common.OpTestFSP import OpTestFSP
from common.OpTestOpenBMC import OpTestOpenBMC
from common.OpTestQemu import OpTestQemu
from common.OpTestSystem import OpTestSystem, OpSystemState, OpTestFSPSystem, OpTestOpenBMCSystem, OpTestQemuSystem
from common.OpTestHost import OpTestHost
from common.OpTestIPMI import OpTestIPMI, OpTestSMCIPMI
from common.OpTestOpenBMC import HostManagement
from common.OpTestWeb import OpTestWeb
import argparse
import time
import subprocess
import sys
import ConfigParser

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

qemu_default = "qemu-system-ppc64"

def get_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-c", "--config-file", help="Configuration File",
                        metavar="FILE")
    tgroup = parser.add_argument_group('Test',
                                       'Tests to run')
    tgroup.add_argument("--list-suites", action='store_true',
                        help="List available suites to run")
    tgroup.add_argument("--run-suite", action='append',
                        help="Run a test suite(s)")
    tgroup.add_argument("--run", action='append',
                        help="Run individual tests")
    tgroup.add_argument("--quiet", action='store_true', default=False,
                        help="Don't splat lots of things to the console")

    parser.add_argument("--machine-state", help="Current machine state",
                        choices=['UNKNOWN', 'OFF', 'PETITBOOT',
                                 'PETITBOOT_SHELL', 'OS'])

    # Options to set the output directory and suffix on the output
    parser.add_argument("-o", "--output", help="Output directory for test reports.  Can also be set via OP_TEST_OUTPUT env variable.")
    parser.add_argument("--suffix", help="Suffix to add to all reports.  Default is current time.")

    bmcgroup = parser.add_argument_group('BMC',
                                         'Options for Service Processor')
    # The default supported BMC choices in --bmc-type
    bmcChoices = ['AMI', 'SMC', 'FSP', 'OpenBMC', 'qemu']
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
    bmcgroup.add_argument("--smc-presshipmicmd")
    bmcgroup.add_argument("--qemu-binary", default=qemu_default,
                          help="[QEMU Only] qemu simulator binary")

    hostgroup = parser.add_argument_group('Host', 'Installed OS information')
    hostgroup.add_argument("--host-ip", help="Host address")
    hostgroup.add_argument("--host-user", help="SSH username for Host")
    hostgroup.add_argument("--host-password", help="SSH password for Host")
    hostgroup.add_argument("--host-lspci", help="Known 'lspci -n -m' for host")
    hostgroup.add_argument("--host-scratch-disk", help="A block device we can erase", default="")
    hostgroup.add_argument("--host-prompt", default="#",
                           help="Prompt for Host SSH session")

    hostinstgroup = parser.add_argument_group('Host OS Install', 'Options for installing an OS on the Host')
    hostinstgroup.add_argument("--host-gateway", help="Host Gateway", default="")
    hostinstgroup.add_argument("--host-submask", help="Host Subnet Mask", default="255.255.255.0")
    hostinstgroup.add_argument("--host-mac",
                               help="Host Mac address (used by OS installer to set up OS on the host)",
                               default="")
    hostinstgroup.add_argument("--host-dns",
                               help="Host DNS Servers (used by OS installer to set up OS on the host)",
                               default="")
    hostinstgroup.add_argument("--proxy", default="", help="proxy for the Host to access the internet. "
                               "Only needed for tests that install an OS")


    hostgroup.add_argument("--platform",
                           help="Platform (used for EnergyScale tests)",
                           choices=['unknown','habanero','firestone','garrison','firenze','p9dsu'])

    osgroup = parser.add_argument_group('OS Images', 'OS Images to boot/install')
    osgroup.add_argument("--os-cdrom", help="OS CD/DVD install image", default="")
    osgroup.add_argument("--os-repo", help="OS repo", default="")
    imagegroup = parser.add_argument_group('Images', 'Firmware LIDs/images to flash')
    imagegroup.add_argument("--bmc-image", help="BMC image to flash(*.tar in OpenBMC, *.bin in SMC)")
    imagegroup.add_argument("--host-pnor", help="PNOR image to flash")
    imagegroup.add_argument("--host-hpm", help="HPM image to flash")
    imagegroup.add_argument("--host-img-url", help="URL to Host Firmware image to flash on FSP systems (Must be URL accessible petitboot shell on the host)")
    imagegroup.add_argument("--flash-skiboot",
                            help="skiboot to use/flash. Depending on platform, may need to be xz compressed")
    imagegroup.add_argument("--flash-kernel",
                            help="petitboot zImage.epapr to use/flash.")
    imagegroup.add_argument("--flash-initramfs",
                            help="petitboot rootfs to use/flash. Not all platforms support this option")
    imagegroup.add_argument("--flash-part", nargs=2, metavar=("PART name", "bin file"), action='append',
                            help="PNOR partition to flash, Ex: --flash-part OCC occ.bin")
    imagegroup.add_argument("--noflash","--no-flash", action='store_true', default=False,
                            help="Even if images are specified, don't flash them")
    imagegroup.add_argument("--only-flash", action='store_true', default=False,
                            help="Only flash, don't run any tests (even if specified)")
    imagegroup.add_argument("--pflash",
                            help="pflash to copy to BMC (if needed)")
    imagegroup.add_argument("--pupdate",
                            help="pupdate to flash PNOR for Supermicro systems")

    stbgroup = parser.add_argument_group('STB', 'Secure and Trusted boot parameters')
    stbgroup.add_argument("--un-signed-pnor", help="Unsigned or improperly signed PNOR")
    stbgroup.add_argument("--signed-pnor", help="Properly signed PNOR image(devel)")
    stbgroup.add_argument("--key-transition-pnor", help="Key transition PNOR image")
    stbgroup.add_argument("--test-container", nargs=2, metavar=("PART name", "bin file"), action='append',
                            help="PNOR partition container to flash, Ex: --flash-part CAPP capp_unsigned.bin")
    stbgroup.add_argument("--secure-mode", action='store_true', default=False, help="Secureboot mode")
    stbgroup.add_argument("--trusted-mode", action='store_true', default=False, help="Trustedboot mode")

    return parser


class OpTestConfiguration():
    def __init__(self):
        self.args = []
        self.remaining_args = []
        for dir in (os.walk('addons').next()[1]):
            optAddons[dir] = importlib.import_module("addons." + dir + ".OpTest" + dir + "Setup")

        return

    def parse_args(self, argv=None):
        conf_parser = argparse.ArgumentParser(add_help=False)

        # We have two parsers so we have correct --help, we need -c in both
        conf_parser.add_argument("-c", "--config-file", help="Configuration File",
                                 metavar="FILE")

        args , remaining_args = conf_parser.parse_known_args(argv)
        defaults = {}
        config = ConfigParser.SafeConfigParser()
        if args.config_file:
            config.read([args.config_file])
        config.read([os.path.expanduser("~/.op-test-framework.conf")])
        try:
            defaults = dict(config.items('op-test'))
        except ConfigParser.NoSectionError:
            pass

        parser = get_parser()
        parser.set_defaults(**defaults)

        if defaults.get('qemu_binary'):
            qemu_default = defaults['qemu_binary']


        parser.add_argument("--check-ssh-keys", action='store_true', default=False,
                                help="Check remote host keys when using SSH (auto-yes on new)")
        parser.add_argument("--known-hosts-file",
                                help="Specify a custom known_hosts file")

        self.args , self.remaining_args = parser.parse_known_args(remaining_args)
        stateMap = { 'UNKNOWN' : OpSystemState.UNKNOWN,
                     'OFF' : OpSystemState.OFF,
                     'PETITBOOT' : OpSystemState.PETITBOOT,
                     'PETITBOOT_SHELL' : OpSystemState.PETITBOOT_SHELL,
                     'OS' : OpSystemState.OS
                 }

        # Some quick sanity checking
        if self.args.known_hosts_file and not self.args.check_ssh_keys:
            parser.error("--known-hosts-file requires --check-ssh-keys")

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

        # set up where all the logs go
        logfile = os.path.join(self.output,"%s.log" % self.outsuffix)
        print "Log file: %s" % logfile
        logcmd = "tee %s" % (logfile)
        # we use 'cat -v' to convert control characters
        # to something that won't affect the user's terminal
        if self.args.quiet:
            logcmd = logcmd + "> /dev/null"
        else:
            logcmd = logcmd + "| sed -u -e 's/\\r$//g'|cat -v"

        print "logcmd: %s" % logcmd
        self.logfile_proc = subprocess.Popen(logcmd,
                                             stdin=subprocess.PIPE,
                                             stderr=sys.stderr,
                                             stdout=sys.stdout,
                                             shell=True)
        print repr(self.logfile_proc)
        self.logfile = self.logfile_proc.stdin

        if self.args.machine_state == None:
            self.startState = OpSystemState.UNKNOWN
        else:
            self.startState = stateMap[self.args.machine_state]
        return self.args, self.remaining_args

    def objs(self):
        host = OpTestHost(self.args.host_ip,
                          self.args.host_user,
                          self.args.host_password,
                          self.args.bmc_ip,
                          self.output,
                          scratch_disk=self.args.host_scratch_disk,
                          proxy=self.args.proxy,
                          logfile=self.logfile,
                          check_ssh_keys=self.args.check_ssh_keys,
                          known_hosts_file=self.args.known_hosts_file)
        if self.args.bmc_type in ['AMI', 'SMC']:
            web = OpTestWeb(self.args.bmc_ip,
                            self.args.bmc_usernameipmi,
                            self.args.bmc_passwordipmi)
            bmc = None
            if self.args.bmc_type in ['AMI']:
                ipmi = OpTestIPMI(self.args.bmc_ip,
                                  self.args.bmc_usernameipmi,
                                  self.args.bmc_passwordipmi,
                                  host=host,
                                  logfile=self.logfile,
                )

                bmc = OpTestBMC(ip=self.args.bmc_ip,
                                username=self.args.bmc_username,
                                password=self.args.bmc_password,
                                logfile=self.logfile,
                                ipmi=ipmi,
                                web=web,
                                check_ssh_keys=self.args.check_ssh_keys,
                                known_hosts_file=self.args.known_hosts_file
                )
            elif self.args.bmc_type in ['SMC']:
                ipmi = OpTestSMCIPMI(self.args.bmc_ip,
                                  self.args.bmc_usernameipmi,
                                  self.args.bmc_passwordipmi,
                                  logfile=self.logfile,
                                  host=host,
                )
                bmc = OpTestSMC(ip=self.args.bmc_ip,
                                username=self.args.bmc_username,
                                password=self.args.bmc_password,
                                ipmi=ipmi,
                                web=web,
                                check_ssh_keys=self.args.check_ssh_keys,
                                known_hosts_file=self.args.known_hosts_file
                )
            self.op_system = OpTestSystem(
                state=self.startState,
                bmc=bmc,
                host=host,
            )
            ipmi.set_system(self.op_system)
        elif self.args.bmc_type in ['FSP']:
            ipmi = OpTestIPMI(self.args.bmc_ip,
                              self.args.bmc_usernameipmi,
                              self.args.bmc_passwordipmi,
                              host=host,
                              logfile=self.logfile)
            bmc = OpTestFSP(self.args.bmc_ip,
                            self.args.bmc_username,
                            self.args.bmc_password,
                            ipmi=ipmi,
            )
            self.op_system = OpTestFSPSystem(
                state=self.startState,
                bmc=bmc,
                host=host,
            )
            ipmi.set_system(self.op_system)
        elif self.args.bmc_type in ['OpenBMC']:
            ipmi = OpTestIPMI(self.args.bmc_ip,
                              self.args.bmc_usernameipmi,
                              self.args.bmc_passwordipmi,
                              host=host,
                              logfile=self.logfile)
            rest_api = HostManagement(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password)
            bmc = OpTestOpenBMC(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password,
                                logfile=self.logfile,
                                ipmi=ipmi, rest_api=rest_api,
                                check_ssh_keys=self.args.check_ssh_keys,
                                known_hosts_file=self.args.known_hosts_file)
            self.op_system = OpTestOpenBMCSystem(
                host=host,
                bmc=bmc,
                state=self.startState,
            )
            bmc.set_system(self.op_system)
        elif self.args.bmc_type in ['qemu']:
            print repr(self.args)
            bmc = OpTestQemu(self.args.qemu_binary,
                             self.args.flash_skiboot,
                             self.args.flash_kernel,
                             self.args.flash_initramfs,
                             ubuntu_cdrom=self.args.ubuntu_cdrom,
                             logfile=self.logfile)
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
