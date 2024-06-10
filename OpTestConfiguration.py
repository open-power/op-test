
# This implements all the configuration needs for running a test
# It includes command line argument parsing and keeping a set
# of OpTestSystem and similar objects around for tests to use.

import common
from common.OpTestBMC import OpTestBMC, OpTestSMC
from common.OpTestFSP import OpTestFSP
from common.OpTestOpenBMC import OpTestOpenBMC
from common.OpTestEBMC import OpTestEBMC
from common.OpTestQemu import OpTestQemu
from common.OpTestMambo import OpTestMambo
from common.OpTestSystem import OpSystemState
import common.OpTestSystem
import common.OpTestHost
from common.OpTestIPMI import OpTestIPMI, OpTestSMCIPMI
from common.OpTestHMC import OpTestHMC
from common.OpTestOpenBMC import HostManagement
from common.OpTestEBMC import EBMCHostManagement
from common.OpTestWeb import OpTestWeb
from common.OpTestUtil import OpTestUtil
from common.OpTestCronus import OpTestCronus
from common.Exceptions import HostLocker, AES, ParameterCheck, OpExit
from common.OpTestConstants import OpTestConstants as BMC_CONST
import atexit
import argparse
import time
import traceback
from datetime import datetime
import subprocess
import sys
import configparser
import errno
import OpTestLogger
import logging

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
import stat
import addons

optAddons = dict()  # Store all addons found.  We'll loop through it a couple time below
# Look at the top level of the addons for any directories and load their Setup modules

qemu_default = "qemu-system-ppc64"
mambo_default = "/opt/ibm/systemsim-p9/run/p9/power9"
mambo_initial_run_script = "skiboot.tcl"
mambo_autorun = "1"
mambo_timeout_factor = 2

# HostLocker credentials need to be in Notes Web section ('comment' section of JSON)
# bmc_type:XXXX
# bmc_username:
# bmc_usernameipmi:
# bmc_password:
# bmc_passwordipmi:
# bmc_ip:<BMC IP>
# host_password:YYYYY
# host_ip:<system ip address>


default_val = {
    'hostlocker': None,
    'hostlocker_server': '',
    'hostlocker_base_url': '/hostlock/api/v1',
    'hostlocker_user': None,
    'hostlocker_locktime': 'never',
    'hostlocker_keep_lock': False,
    'hostlocker_proxy': 'socks5h://localhost:1080',
    'hostlocker_no_proxy_ips': ['10.61.0.0/17', '10.61.128.0/17'],
    'aes': None,
    'aes_server': 'aes server',
    'aes_base_url': '/pse_ct_dashboard/aes/rest',
    'aes_user': None,
    'locker_wait': None,
    'aes_add_locktime': 0,
    'aes_rel_on_expire': True,
    'aes_keep_lock': False,
    'aes_proxy': None,
    'aes_no_proxy_ips': None,
    'bmc_type': 'OpenBMC',
    'bmc_username': 'YYY',
    'bmc_usernameipmi': 'ZZZZ',
    'bmc_password': 'ZZZZ',
    'bmc_passwordipmi': 'XXXX',
    'bmc_ip': None,
    'host_user': 'yyyy',
    'host_password': 'YYYY',
    'host_ip': None,
    'secvar_payload_url': 'https://github.com/erichte-ibm/op-test/raw/erichte-ibm/os-secure-boot-squashed/test_binaries',
}

default_val_fsp = {
    'bmc_type': 'FSP',
    'bmc_username': 'dev',
    'bmc_usernameipmi': 'ZZZZ',
    'bmc_password': 'YYYY',
    'bmc_passwordipmi': 'ZZZZ',
}

default_val_ami = {
    'bmc_type': 'AMI',
    'host_user': 'YYYY',
    'bmc_usernameipmi': 'ZZZZ',
    'bmc_password': 'YYYY',
    'bmc_passwordipmi': 'XXXX',
}

default_val_smc = {
    'bmc_type': 'SMC',
    'host_user': 'YYYY',
    'bmc_usernameipmi': 'YYYY',
    'bmc_password': 'XXXX',
    'bmc_passwordipmi': 'XXXX',
}

default_val_qemu = {
    'bmc_type': 'qemu',
    # typical KVM Host IP
    # see OpTestQemu.py
    'host_ip': '10.0.2.15',
    # typical VM skiroot IP
    # see OpTestQemu.py
}

default_val_mambo = {
    'bmc_type': 'mambo',
}

default_templates = {
    # lower case insensitive lookup used later
    'openbmc': default_val,
    'fsp': default_val_fsp,
    'ami': default_val_ami,
    'smc': default_val_smc,
    'qemu': default_val_qemu,
    'mambo': default_val_mambo,
}


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
    tgroup.add_argument("--list-tests", action='store_true',
                        help="List each test that would have been run")
    tgroup.add_argument("--list-all-tests", action='store_true',
                        help="List all defined tests")
    tgroup.add_argument("--run-suite", action='append',
                        help="Run a test suite(s)")
    tgroup.add_argument("--run", action='append',
                        help="Run individual tests")
    tgroup.add_argument("-f", "--failfast", action='store_true',
                        help="Stop on first failure")
    tgroup.add_argument("--quiet", action='store_true', default=False,
                        help="Don't splat lots of things to the console")

    parser.add_argument("--machine-state", help="Current machine state",
                        choices=['UNKNOWN', 'UNKNOWN_BAD', 'OFF', 'PETITBOOT',
                                 'PETITBOOT_SHELL', 'OS'])

    # Options to set the output directory and suffix on the output
    parser.add_argument(
        "-o", "--output", help="Output directory for test reports.  Can also be set via OP_TEST_OUTPUT env variable.")
    parser.add_argument(
        "-l", "--logdir", help="Output directory for log files.  Can also be set via OP_TEST_LOGDIR env variable.")
    parser.add_argument(
        "--suffix", help="Suffix to add to all reports.  Default is current time.")

    lockgroup = parser.add_mutually_exclusive_group()
    lockgroup.add_argument("--hostlocker", metavar="HOST_NAME",
                           help="Hostlocker host name to checkout, see HOSTLOCKER GROUP below for more options")
    lockgroup.add_argument("--aes", nargs='+', metavar="ENV_NAME|Q|L|U",
                           help="AES environment name to checkout or Q|L|U for query|lock|unlock of AES environment, refine by adding --aes-search-args, see AES GROUP below for more options")

    hostlockergroup = parser.add_argument_group('HOSTLOCKER GROUP',
                                                'Options for HostLocker (see above optional arguments --hostlocker, mutually exclusive with --aes)')
    hostlockergroup.add_argument(
        "--hostlocker-user", help="UID login for HostLocker, uses OS UID if not specified, you must have logged in at least once via the web prior to running")
    hostlockergroup.add_argument(
        "--hostlocker-server", help="Override URL for HostLocker Server")
    hostlockergroup.add_argument(
        "--hostlocker-base-url", help="Override Base URL for HostLocker")
    hostlockergroup.add_argument(
        "--hostlocker-locktime", help="Time duration (see web for formats) to lock the host, never is the default, it will unlock post test")
    hostlockergroup.add_argument("--hostlocker-keep-lock", default=False,
                                 help="Release the lock once the test finishes, defaults to False to always release the lock post test")
    hostlockergroup.add_argument(
        "--hostlocker-proxy", help="socks5 proxy server setup, defaults to use localhost port 1080, you must have the SSH tunnel open during tests")
    hostlockergroup.add_argument(
        "--hostlocker-no-proxy-ips", help="Allows dynamic determination if you are on proxy network then no proxy will be used")

    aesgroup = parser.add_argument_group('AES GROUP',
                                         'Options for AES (see above optional arguments --aes, mutually exclusive with --hostlocker)')
    aesgroup.add_argument("--aes-search-args", nargs='+', help='AES allowable, match done by regex '
                          + 'like --aes-search-args Environment_Name=wl2, run --aes Q for more info')
    aesgroup.add_argument(
        "--aes-user", help="UID login for AES, uses OS UID if not specified, you must have logged in at least once via the web prior to running")
    aesgroup.add_argument("--aes-server", help="Override URL for AES Server")
    aesgroup.add_argument("--aes-base-url", help="Override Base URL for AES")
    aesgroup.add_argument("--aes-rel-on-expire", default=True,
                          help="AES setting related to aes-add-locktime when making the initial reservation, defaults to True, does not affect already existing reservations")
    aesgroup.add_argument("--aes-keep-lock", default=False,
                          help="Release the AES reservation once the test finishes, defaults to False to always release the reservation post test")
    aesgroup.add_argument("--locker-wait", type=int, default=0,
                          help="Time in minutes to try for the lock, default does not retry")
    aesgroup.add_argument("--aes-add-locktime", default=0, help="Time in hours (float value) of how long to reserve the environment, reservation defaults to never expire but will release the environment post test, if a reservation already exists for UID then extra time will be attempted to be added, this does NOT work on NEVER expiring reservations, be sure to add --aes-keep-lock or else the reservation will be given up after the test, use --aes L option to manage directly and --aes U option to manage directly without running a test")
    aesgroup.add_argument(
        "--aes-proxy", help="socks5 proxy server setup, defaults to use localhost port 1080, you must have the SSH tunnel open during tests")
    aesgroup.add_argument(
        "--aes-no-proxy-ips", help="Allows dynamic determination if you are on proxy network then no proxy will be used")

    bmcgroup = parser.add_argument_group('BMC',
                                         'Options for Service Processor')
    # The default supported BMC choices in --bmc-type
    bmcChoices = ['AMI', 'SMC', 'FSP', 'FSP_PHYP',
                  'OpenBMC', 'EBMC_PHYP', 'qemu', 'mambo']
    # Loop through any addons let it append the extra bmcChoices
    for opt in optAddons:
        bmcChoices = optAddons[opt].addBMCType(bmcChoices)
    bmcgroup.add_argument("--bmc-type",
                          choices=bmcChoices,
                          help="Type of service processor")
    bmcgroup.add_argument("--bmc-ip", help="BMC address")
    bmcgroup.add_argument("--bmc-mac", help="BMC MAC address")
    bmcgroup.add_argument("--bmc-username", help="SSH username for BMC")
    bmcgroup.add_argument("--bmc-password", help="SSH password for BMC")
    bmcgroup.add_argument("--bmc-usernameipmi", help="IPMI username for BMC")
    bmcgroup.add_argument("--bmc-passwordipmi", help="IPMI password for BMC")
    bmcgroup.add_argument("--bmc-prompt", default="#",
                          help="Prompt for BMC ssh session")
    bmcgroup.add_argument("--smc-presshipmicmd")
    bmcgroup.add_argument("--qemu-binary", default=qemu_default,
                          help="[QEMU Only] qemu simulator binary")
    bmcgroup.add_argument("--mambo-binary", default=mambo_default,
                          help="[Mambo Only] mambo simulator binary, defaults to /opt/ibm/systemsim-p9/run/p9/power9")
    bmcgroup.add_argument("--mambo-initial-run-script", default=mambo_initial_run_script,
                          help="[Mambo Only] mambo simulator initial run script, defaults to skiboot.tcl")
    bmcgroup.add_argument("--mambo-autorun", default=mambo_autorun,
                          help="[Mambo Only] mambo autorun, defaults to '1' to autorun")
    bmcgroup.add_argument("--mambo-timeout-factor", default=mambo_timeout_factor,
                          help="[Mambo Only] factor to multiply all timeouts by, defaults to 2")

    hostgroup = parser.add_argument_group('Host', 'Installed OS information')
    hostgroup.add_argument("--host-ip", help="Host address")
    hostgroup.add_argument("--host-user", help="SSH username for Host")
    hostgroup.add_argument("--host-password", help="SSH password for Host")
    hostgroup.add_argument("--host-serial-console-command",
                           help="Command to get serial console for host."
                           "Used instead of IPMI SoL. Useful for buggy BMCs.")

    hostgroup.add_argument("--host-lspci", help="Known 'lspci -n -m' for host")
    hostgroup.add_argument("--host-scratch-disk",
                           help="A block device we can erase", default="")
    hostgroup.add_argument("--qemu-scratch-disk",
                           help="A block device for qemu", default=None)
    hostgroup.add_argument("--host-prompt", default="#",
                           help="Prompt for Host SSH session")

    hostinstgroup = parser.add_argument_group(
        'Host OS Install', 'Options for installing an OS on the Host')
    hostinstgroup.add_argument(
        "--host-name", help="Host name", default="localhost")
    hostinstgroup.add_argument(
        "--host-gateway", help="Host Gateway", default="")
    hostinstgroup.add_argument(
        "--host-submask", help="Host Subnet Mask", default="255.255.255.0")
    hostinstgroup.add_argument("--host-mac",
                               help="Host Mac address (used by OS installer to set up OS on the host)",
                               default="")
    hostinstgroup.add_argument("--host-dns",
                               help="Host DNS Servers (used by OS installer to set up OS on the host)",
                               default="")
    hostinstgroup.add_argument("--proxy", default="", help="proxy for the Host to access the internet. "
                               "Only needed for tests that install an OS")

    hostcmdgroup = parser.add_argument_group(
        'Host Run Commands', 'Options for Running custom commands on the Host')
    hostcmdgroup.add_argument("--host-cmd", help="Command to run", default="")
    hostcmdgroup.add_argument(
        "--host-cmd-file", help="Commands to run from file", default="")
    hostcmdgroup.add_argument(
        "--host-cmd-timeout", help="Timeout for command", type=int, default=1000)
    hostcmdgroup.add_argument("--host-cmd-resultpath",
                              help="Result path from host", default="")
    hostcmdgroup.add_argument("--machine-config",
                              help="lpar configuration values, "
                                   "Ex: 1. --machine-config={\"lpar\":\"cpu=dedicated,vtpm=1,vpmem=1,nx_gzip\", \"cec\": \"lmb=2048\"}"
                                   "    2. --machine-config={ \"cec\": \"lmb=2048\"}"
                                   "    3. --machine-config={\"lpar\":\"cpu=shared\"}")

    hostgroup.add_argument("--platform",
                           help="Platform (used for EnergyScale tests)",
                           choices=['unknown', 'habanero', 'firestone', 'garrison', 'firenze', 'p9dsu', 'witherspoon', 'mihawk'])

    osgroup = parser.add_argument_group(
        'OS Images', 'OS Images to boot/install')
    osgroup.add_argument(
        "--os-cdrom", help="OS CD/DVD install image", default=None)
    osgroup.add_argument("--os-repo", help="OS repo", default="")
    osgroup.add_argument("--no-os-reinstall",
                         help="If set, don't run OS Install test",
                         action='store_true', default=False)

    gitgroup = parser.add_argument_group(
        'git repo', 'Git repository details for upstream kernel install/boot')
    gitgroup.add_argument(
        "--git-repo", help="Kernel git repository", default=None)
    gitgroup.add_argument(
        "--git-repo-reference", help="Kernel git repository reference for fast cloning", default=None)    
    gitgroup.add_argument("--git-repoconfigpath",
                          help="Kernel config file to be used", default=None)
    gitgroup.add_argument(
        "--git-repoconfig", help="Kernel config to be used", default="ppc64le_defconfig")
    gitgroup.add_argument(
        "--git-branch", help="git branch to be used", default="master")
    gitgroup.add_argument(
        "--git-home", help="home path for git repository", default="/home/ci")
    gitgroup.add_argument(
        "--git-patch", help="patch to be applied on top of the git repository", default=None)
    gitgroup.add_argument(
        "--use-kexec", help="Use kexec to boot to new kernel", action='store_true', default=False)
    gitgroup.add_argument("--append-kernel-cmdline",
                          help="Append kernel commandline while booting with kexec", default=None)
    gitgroup.add_argument(
        "--use-reboot", help="Use reboot command replacing a hard power off/on", action='store_true', default=False)
    gitgroup.add_argument("--bad-commit",
                          help="first identified bad commit version in the git tree", default=None)
    gitgroup.add_argument("--good-commit",
                          help="last identified good commit version in the git tree", default=None)
    gitgroup.add_argument("--bisect-script",
                          help="bisect test script that classifies the commit as good or bad", default=None)
    gitgroup.add_argument("--bisect-category",
                          help="bisect category (build, test)", default=None)

    imagegroup = parser.add_argument_group(
        'Images', 'Firmware LIDs/images to flash')
    imagegroup.add_argument(
        "--bmc-image", help="BMC image to flash(*.tar in OpenBMC, *.bin in SMC)")
    imagegroup.add_argument("--host-pnor", help="PNOR image to flash")
    imagegroup.add_argument("--host-hpm", help="HPM image to flash")
    imagegroup.add_argument(
        "--host-img-url", help="URL to Host Firmware image to flash on FSP systems (Must be URL accessible petitboot shell on the host)")
    imagegroup.add_argument("--flash-skiboot",
                            help="skiboot to use/flash. Depending on platform, may need to be xz compressed")
    imagegroup.add_argument("--flash-kernel",
                            help="petitboot zImage.epapr to use/flash.")
    imagegroup.add_argument("--flash-initramfs",
                            help="petitboot rootfs to use/flash. Not all platforms support this option")
    imagegroup.add_argument("--flash-part", nargs=2, metavar=("PART name", "bin file"), action='append',
                            help="PNOR partition to flash, Ex: --flash-part OCC occ.bin")
    imagegroup.add_argument("--noflash", "--no-flash", action='store_true', default=False,
                            help="Even if images are specified, don't flash them")
    imagegroup.add_argument("--only-flash", action='store_true', default=False,
                            help="Only flash, don't run any tests (even if specified)")
    imagegroup.add_argument("--pflash",
                            help="pflash to copy to BMC (if needed)")
    imagegroup.add_argument("--pupdate",
                            help="pupdate to flash PNOR for Supermicro systems")
    imagegroup.add_argument("--pdbg",
                            help="pdbg binary to be executed on BMC")

    stbgroup = parser.add_argument_group(
        'STB', 'Secure and Trusted boot parameters')
    stbgroup.add_argument("--un-signed-pnor",
                          help="Unsigned or improperly signed PNOR")
    stbgroup.add_argument(
        "--signed-pnor", help="Properly signed PNOR image(imprint)")
    stbgroup.add_argument(
        "--signed-to-pnor", help="Properly signed PNOR image(imprint or production)")
    stbgroup.add_argument("--key-transition-pnor",
                          help="Key transition PNOR image")
    stbgroup.add_argument("--test-container", nargs=2, metavar=("PART name", "bin file"), action='append',
                          help="PNOR partition container to flash, Ex: --test-container CAPP capp_unsigned.bin")
    stbgroup.add_argument("--secure-mode", action='store_true',
                          default=False, help="Secureboot mode")
    stbgroup.add_argument("--trusted-mode", action='store_true',
                          default=False, help="Trustedboot mode")
    kernelcmdgroup = parser.add_argument_group("Kernel cmdline options",
                                               "add/remove kernel commandline arguments")
    kernelcmdgroup.add_argument("--add-kernel-args",
                                help="Kernel commandline option to be added",
                                default="")
    kernelcmdgroup.add_argument("--remove-kernel-args",
                                help="Kernel commandline option to be removed",
                                default="")
    kdumpgroup = parser.add_argument_group("Kdump group",
                                           "Ipaddress username and password of remote server")
    kdumpgroup.add_argument("--dump-server-ip",
                            help="IP address of remote server where dump will be stored",
                            default="")
    kdumpgroup.add_argument("--dump-server-pw",
                            help="Password of remote server where dump will be stored",
                            default="")
    kdumpgroup.add_argument("--dump-path",
                            help="Directory path of remote server where dump will be stored",
                            default="/var/crash")
    cronusgroup = parser.add_argument_group("Cronus", "Cronus Config options")
    cronusgroup.add_argument(
        "--cronus-release", default="auto", help="Cronus Release")
    cronusgroup.add_argument(
        "--cronus-product", default="p9", help="Cronus Product")
    cronusgroup.add_argument("--cronus-system-type",
                             default="witherspoon", help="Cronus System Type")
    cronusgroup.add_argument("--cronus-code-level",
                             default="dev", help="Cronus Code Level")
#    cronusgroup.add_argument("--cronus-hdct", default="/opt/openpower/p9/crondump/HDCT_P9", help="Cronus Hardware Dump Content Table file")
    cronusgroup.add_argument("--cronus-hdct", default="HDCT.txt",
                             help="Cronus Hardware Dump Content Table file")
    cronusgroup.add_argument("--cronus-dump-directory",
                             default=None, help="Cronus dump file directory")
    cronusgroup.add_argument("--cronus-dump-suffix",
                             default="optest", help="Cronus dump file suffix")
    cronusgroup.add_argument("--cronus-smart-path", action='store_true',
                             default=False, help="Cronus path added after /usr/bin")
    hmcgroup = parser.add_argument_group('HMC',
                                         'HMC CLI commands')
    hmcgroup.add_argument("--hmc-ip", help="HMC address")
    hmcgroup.add_argument("--hmc-username", help="SSH username for HMC")
    hmcgroup.add_argument("--hmc-password", help="SSH password for HMC")
    hmcgroup.add_argument(
        "--system-name", help="Managed system/server name in HMC", default=None)
    hmcgroup.add_argument(
        "--lpar-name", help="Lpar name as provided in HMC", default=None)
    hmcgroup.add_argument(
        "--lpar-prof", help="Lpar profile provided in HMC", default=None)
    hmcgroup.add_argument(
        "--lpar-vios", help="Lpar VIOS to boot before other LPARS", default=None)
    hmcgroup.add_argument(
        "--target-system-name", help="Target managed system/server name in HMC", default=None)
    hmcgroup.add_argument(
        "--target-lpar-name", help="Target lpar name in target managed system", default=None)

    misc_group = parser.add_argument_group("Misc")
    misc_group.add_argument("--check-ssh-keys", action='store_true', default=False,
                            help="Check remote host keys when using SSH (auto-yes on new)")
    misc_group.add_argument("--known-hosts-file",
                            help="Specify a custom known_hosts file")
    misc_group.add_argument("--accept-unknown-args", default=False, action='store_true',
                            help="Don't exit if we find unknown command line arguments")
    misc_group.add_argument("--secvar-payload-url",
                            help="Specify a URL for the secvar test data payload")
    misc_group.add_argument("--bisect-flag",
                            help="Specify if bisection is to be done or not")

    return parser


class OpTestConfiguration():
    def __init__(self):
        # initialize OpTestUtil with this object the OpTestConfiguration
        self.util = OpTestUtil(self)
        # initialize OpTestCronus with this object the OpTestConfiguration
        self.cronus = OpTestCronus(self)
        self.args = []
        self.remaining_args = []
        self.basedir = os.path.abspath(os.path.dirname(__file__))
        self.signal_ready = False  # indicator for properly initialized
        self.atexit_ready = False  # indicator for properly initialized
        self.aes_print_helpers = True  # Need state for locker_wait
        self.dump = True  # Need state for cleanup
        self.lock_dict = {'res_id': None,
                          'name': None,
                          'Group_Name': None,
                          'envs': [],
                          }

        self.util_server = None  # Hostlocker or AES
        self.util_bmc_server = None  # OpenBMC REST Server
        atexit.register(self.cleanup)  # allows cleanup handler to run (OpExit)
        self.firmware_versions = None
        self.nvram_debug_opts = None

        for dirname in (next(os.walk(os.path.join(self.basedir, 'addons')))[1]):
            if dirname == "__pycache__":
                continue
            optAddons[dirname] = importlib.import_module(
                "addons." + dirname + ".OpTest" + dirname + "Setup")

        return

    def cleanup(self):
        if self.atexit_ready:
            # calling cleanup before args initialized pointless
            # attribute errors thrown in cleanup, e.g. ./op-test -h
            self.util.cleanup()

    def parse_config_file(self, filename, optional=False):
        config = configparser.ConfigParser()

        if not os.access(filename, os.R_OK):
            if optional:
                return {}
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), filename)

        config.read(filename)

        if config.has_section('op-test'):
            d = dict(config.items('op-test'))
        else:
            msg = "{} is missing an an [op-test] section header".format(
                filename)
            raise configparser.NoSectionError(msg)

        return dict(config.items('op-test'))

    def parse_args(self, argv=None):
        conf_parser = argparse.ArgumentParser(add_help=False)
        conf_parser.add_argument("-c", "--config-file", metavar="FILE")
        config_args, _ = conf_parser.parse_known_args(argv)

        userfile = os.path.expanduser("~/.op-test-framework.conf")
        self.defaults = self.parse_config_file(userfile, True)

        # parse specified config file
        if config_args.config_file:
            cfg = self.parse_config_file(config_args.config_file)
            self.defaults.update(cfg)

        parser = get_parser()
        parser.set_defaults(**self.defaults)

        # don't parse argv[0]
        self.args, self.remaining_args = parser.parse_known_args(argv[1:])

        # we use parse_known_args() and generate our own usage because the number
        # of args makes the default usage string... unwieldy
        if len(self.remaining_args) > 0 and not self.args.accept_unknown_args:
            raise Exception("Unknown command line argument(s): {}"
                            .format(str(self.remaining_args)))

        args_dict = vars(self.args)

        # if we have a bmc_type we start with appropriate template
        if args_dict.get('bmc_type') is not None:
            dict_merge = default_templates.get(
                args_dict.get('bmc_type').lower())
            if dict_merge is not None:
                # overlays dict merge on top of default_val
                default_val.update(dict_merge)

        for key in default_val:
            if args_dict.get(key) is None:
                args_dict[key] = default_val[key]

        # Some quick sanity checking
        if self.args.known_hosts_file and not self.args.check_ssh_keys:
            parser.error("--known-hosts-file requires --check-ssh-keys")

        # FIXME: Passing machine_state doesn't work at all with qemu or mambo
        if self.args.machine_state == None:
            if self.args.bmc_type in ['qemu', 'mambo']:
                # Force UNKNOWN_BAD so that we don't try to setup the console early
                self.startState = OpSystemState.UNKNOWN_BAD
            else:
                self.startState = OpSystemState.UNKNOWN
        else:
            stateMap = {'UNKNOWN':          OpSystemState.UNKNOWN,
                        'UNKNOWN_BAD':      OpSystemState.UNKNOWN_BAD,
                        'OFF':              OpSystemState.OFF,
                        'PETITBOOT':        OpSystemState.PETITBOOT,
                        'PETITBOOT_SHELL':  OpSystemState.PETITBOOT_SHELL,
                        'OS':               OpSystemState.OS
                        }
            self.startState = stateMap[self.args.machine_state]
        return self.args, self.remaining_args

    def do_testing_setup(self):
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
            outdir = os.path.join(self.basedir, "test-reports")

        self.outsuffix = "test-run-%s" % self.get_suffix()
        outdir = os.path.join(outdir, self.outsuffix)

        # Normalize the path to fully qualified and create if not there
        self.output = os.path.abspath(outdir)
        if (not os.path.exists(self.output)):
            os.makedirs(self.output)

        if (self.args.logdir):
            logdir = self.args.logdir
        elif ("OP_TEST_LOGDIR" in os.environ):
            logdir = os.environ["OP_TEST_LOGDIR"]
        else:
            logdir = self.output

        self.logdir = os.path.abspath(logdir)
        if (not os.path.exists(self.logdir)):
            os.makedirs(self.logdir)

        print(("Logs in: {}".format(self.logdir)))

        OpTestLogger.optest_logger_glob.logdir = self.logdir

        # Grab the suffix, if not given use current time
        self.outsuffix = self.get_suffix()

        # set up where all the logs go
        logfile = os.path.join(self.output, "%s.log" % self.outsuffix)

        logcmd = "tee %s" % (logfile)
        # we use 'cat -v' to convert control characters
        # to something that won't affect the user's terminal
        if self.args.quiet:
            logcmd = logcmd + "> /dev/null"
            # save sh_level for later refresh loggers
            OpTestLogger.optest_logger_glob.sh_level = logging.ERROR
            OpTestLogger.optest_logger_glob.sh.setLevel(logging.ERROR)
        else:
            logcmd = logcmd + "| sed -u -e 's/\\r$//g'|cat -v"
            # save sh_level for later refresh loggers
            OpTestLogger.optest_logger_glob.sh_level = logging.INFO
            OpTestLogger.optest_logger_glob.sh.setLevel(logging.INFO)

        OpTestLogger.optest_logger_glob.setUpLoggerFile(
            datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+'.main.log')
        OpTestLogger.optest_logger_glob.setUpLoggerDebugFile(
            datetime.utcnow().strftime("%Y%m%d%H%M%S%f")+'.debug.log')
        OpTestLogger.optest_logger_glob.optest_logger.info(
            'TestCase Log files: {}/*'.format(self.output))
        OpTestLogger.optest_logger_glob.optest_logger.info(
            'StreamHandler setup {}'.format('quiet' if self.args.quiet else 'normal'))

        self.logfile_proc = subprocess.Popen(logcmd,
                                             stdin=subprocess.PIPE,
                                             stderr=sys.stderr,
                                             stdout=sys.stdout,
                                             shell=True,
                                             universal_newlines=True,
                                             encoding='utf-8')
        self.logfile = self.logfile_proc.stdin

        # we have enough setup to allow
        # signal handler cleanup to run
        self.signal_ready = True
        # atexit viable for cleanup to run
        self.atexit_ready = True
        # now that we have loggers, dump conf file to help debug later
        OpTestLogger.optest_logger_glob.optest_logger.debug(
            "conf file defaults={}".format(self.defaults))
        cmd = "git describe --always"
        try:
            git_output = subprocess.check_output(cmd.split())
            # log for triage of how dated the repo is
            OpTestLogger.optest_logger_glob.optest_logger.debug(
                "op-test-framework git level = {}".format(git_output))
        except Exception as e:
            OpTestLogger.optest_logger_glob.optest_logger.debug(
                "Unable to get git describe")

        # MTU Check here post handler and logging setup
        try:
            self.util.PingMTUCheck(
                self.args.bmc_ip, totalSleepTime=BMC_CONST.PING_RETRY_FOR_STABILITY)
        except Exception as e:
            OpTestLogger.optest_logger_glob.optest_logger.warning(
                "Check that the BMC is healthy, maybe the Broadcom bug, Exception={}".format(e))

        # setup AES and Hostlocker configs after the logging is setup
        locker_timeout = time.time() + 60*self.args.locker_wait
        locker_code = errno.ETIME  # 62
        locker_message = ("OpTestSystem waited {} minutes but was unable"
                          " to lock environment/host requested,"
                          " either pick another environment/host or increase "
                          "--locker-wait, try --aes q with options for "
                          "--aes-search-args to view availability, or as"
                          " appropriate for your hostlocker"
                          .format(self.args.locker_wait))
        locker_exit_exception = OpExit(message=locker_message,
                                       code=locker_code)
        while True:
            try:
                rollup_flag = False
                self.util.check_lockers()
                break
            except Exception as e:
                OpTestLogger.optest_logger_glob.optest_logger.debug(
                    "locker_wait Exception={}".format(e))
                if "unable to lock" in e.message:
                    self.aes_print_helpers = False
                    # SystemExit exception needs message to print
                    rollup_message = locker_exit_exception.message
                    rollup_exception = locker_exit_exception
                else:
                    rollup_message = e.message
                    rollup_exception = e
                    rollup_flag = True  # bubble exception out
                if time.time() > locker_timeout or rollup_flag:
                    # if not "unable to lock" we bubble up underlying exception
                    OpTestLogger.optest_logger_glob.optest_logger.warning(
                        "{}".format(rollup_message))
                    raise rollup_exception
                else:
                    OpTestLogger.optest_logger_glob.optest_logger.info(
                        "OpTestSystem waiting for requested environment/host"
                        " total time to wait is {} minutes, we will check"
                        " every minute"
                        .format(self.args.locker_wait))
                    time.sleep(60)

    def get_suffix(self):
        # Grab the suffix, if not given use current time
        if (self.args.suffix):
            outsuffix = self.args.suffix
        else:
            outsuffix = time.strftime("%Y%m%d%H%M%S")
        return outsuffix

    def objs(self):
        if self.args.list_suites or self.args.list_tests:
            return

        # check to see if bmc_ip even pings to validate configuration parms
        try:
            self.util.PingFunc(
                self.args.bmc_ip, totalSleepTime=BMC_CONST.PING_RETRY_FOR_STABILITY)
        except Exception as e:
            # we are trying to catch sooner rather than later
            # if we have reservations that need cleaned up
            # otherwise we would have to try/except for cleanup
            # in lots of places
            # testcases.HelloWorld in CI fails if we throw this
            # raise only if we have reservations to cleanup
            if self.args.hostlocker is not None \
                    or self.args.aes is not None \
                    or self.args.aes_search_args is not None:
                self.util.cleanup()
                raise ParameterCheck(message="OpTestSystem PingFunc fails to "
                                     "ping '{}', check your configuration and setup, see "
                                     "Exception details: {}".format(self.args.bmc_ip, e))

        try:
            host = common.OpTestHost.OpTestHost(self.args.host_ip,
                                                self.args.host_user,
                                                self.args.host_password,
                                                self.args.bmc_ip,
                                                self.output,
                                                scratch_disk=self.args.host_scratch_disk,
                                                proxy=self.args.proxy,
                                                logfile=self.logfile,
                                                check_ssh_keys=self.args.check_ssh_keys,
                                                known_hosts_file=self.args.known_hosts_file,
                                                conf=self)
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
                                      host_console_command=self.args.host_serial_console_command,
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
                self.op_system = common.OpTestSystem.OpTestSystem(
                    state=self.startState,
                    bmc=bmc,
                    host=host,
                    conf=self,
                )
                ipmi.set_system(self.op_system)
                bmc.set_system(self.op_system)
            elif self.args.bmc_type in ['FSP']:
                ipmi = OpTestIPMI(self.args.bmc_ip,
                                  None,  # FSP does not use UID
                                  self.args.bmc_passwordipmi,
                                  host=host,
                                  logfile=self.logfile)
                bmc = OpTestFSP(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password,
                                ipmi=ipmi,
                                prompt=self.args.fsp_prompt if hasattr(
                                    self.args, 'fsp_prompt') else "$",
                                )
                self.op_system = common.OpTestSystem.OpTestFSPSystem(
                    state=self.startState,
                    bmc=bmc,
                    host=host,
                    conf=self,
                )
                ipmi.set_system(self.op_system)
            elif self.args.bmc_type in ['FSP_PHYP']:
                host = common.OpTestHost.OpTestLPAR(self.args.host_ip,
                                                    self.args.host_user,
                                                    self.args.host_password,
                                                    self.args.bmc_ip,
                                                    self.output,
                                                    scratch_disk=self.args.host_scratch_disk,
                                                    proxy=self.args.proxy,
                                                    logfile=self.logfile,
                                                    check_ssh_keys=self.args.check_ssh_keys,
                                                    known_hosts_file=self.args.known_hosts_file,
                                                    conf=self)
                hmc = None
                if all(v is not None for v in [self.args.hmc_ip, self.args.hmc_username, self.args.hmc_password,
                                               self.args.system_name, self.args.lpar_name]):
                    hmc = OpTestHMC(self.args.hmc_ip,
                                    self.args.hmc_username,
                                    self.args.hmc_password,
                                    managed_system=self.args.system_name,
                                    tgt_managed_system=self.args.target_system_name,
                                    lpar_name=self.args.lpar_name,
                                    tgt_lpar=self.args.target_lpar_name,
                                    lpar_vios=self.args.lpar_vios,
                                    lpar_prof=self.args.lpar_prof,
                                    lpar_user=self.args.host_user,
                                    lpar_password=self.args.host_password,
                                    logfile=self.logfile
                                    )
                else:
                    raise Exception(
                        "HMC IP, username and password is required")
                bmc = OpTestFSP(self.args.bmc_ip,
                                self.args.bmc_username,
                                self.args.bmc_password,
                                hmc=hmc,
                                prompt=self.args.fsp_prompt if hasattr(
                                    self.args, 'fsp_prompt') else "$",
                                )
                self.op_system = common.OpTestSystem.OpTestLPARSystem(
                    state=self.startState,
                    bmc=bmc,
                    host=host,
                    conf=self,
                )
                hmc.set_system(self.op_system)
            elif self.args.bmc_type in ['OpenBMC']:
                ipmi = OpTestIPMI(self.args.bmc_ip,
                                  self.args.bmc_usernameipmi,
                                  self.args.bmc_passwordipmi,
                                  host=host,
                                  logfile=self.logfile)
                rest_api = HostManagement(conf=self,
                                          ip=self.args.bmc_ip,
                                          username=self.args.bmc_username,
                                          password=self.args.bmc_password)
                bmc = OpTestOpenBMC(ip=self.args.bmc_ip,
                                    username=self.args.bmc_username,
                                    password=self.args.bmc_password,
                                    ipmi=ipmi,
                                    rest_api=rest_api,
                                    logfile=self.logfile,
                                    check_ssh_keys=self.args.check_ssh_keys,
                                    known_hosts_file=self.args.known_hosts_file)
                self.op_system = common.OpTestSystem.OpTestOpenBMCSystem(
                    host=host,
                    bmc=bmc,
                    state=self.startState,
                    conf=self,
                )
                bmc.set_system(self.op_system)
            elif self.args.bmc_type in ['EBMC_PHYP']:
                host = common.OpTestHost.OpTestLPAR(self.args.host_ip,
                                                    self.args.host_user,
                                                    self.args.host_password,
                                                    self.args.bmc_ip,
                                                    self.output,
                                                    scratch_disk=self.args.host_scratch_disk,
                                                    proxy=self.args.proxy,
                                                    logfile=self.logfile,
                                                    check_ssh_keys=self.args.check_ssh_keys,
                                                    known_hosts_file=self.args.known_hosts_file,
                                                    conf=self)
                hmc = None
                if all(v is not None for v in [self.args.hmc_ip, self.args.hmc_username, self.args.hmc_password,
                                               self.args.system_name, self.args.lpar_name]):
                    hmc = OpTestHMC(self.args.hmc_ip,
                                    self.args.hmc_username,
                                    self.args.hmc_password,
                                    managed_system=self.args.system_name,
                                    tgt_managed_system=self.args.target_system_name,
                                    lpar_name=self.args.lpar_name,
                                    lpar_vios=self.args.lpar_vios,
                                    lpar_prof=self.args.lpar_prof,
                                    lpar_user=self.args.host_user,
                                    lpar_password=self.args.host_password,
                                    logfile=self.logfile
                                    )
                rest_api = EBMCHostManagement(conf=self,
                                              ip=self.args.bmc_ip,
                                              username=self.args.bmc_username,
                                              password=self.args.bmc_password)
                bmc = OpTestEBMC(ip=self.args.bmc_ip,
                                 username=self.args.bmc_username,
                                 password=self.args.bmc_password,
                                 hmc=hmc,
                                 rest_api=rest_api,
                                 logfile=self.logfile,
                                 check_ssh_keys=self.args.check_ssh_keys,
                                 known_hosts_file=self.args.known_hosts_file)
                self.op_system = common.OpTestSystem.OpTestLPARSystem(
                    state=self.startState,
                    bmc=bmc,
                    bmc_type=self.args.bmc_type,
                    host=host,
                    conf=self,
                )
                # For EBMC type of systems the implementation here is:
                # By default the EBMC system will be phyp mode i.e the console object returns lpar console
                # In case if someone wants to run bmc commands than the system is set to BMC mode i.e
                # only BMC details (no hmc) have provided as input if user wants to run bmc commands over ssh
                # so at any point of time the test can use either phyp or bmc mode, and not both
                if hmc:
                    hmc.set_system(self.op_system)
                else:
                    bmc.set_system(self.op_system)

            elif self.args.bmc_type in ['qemu']:
                print((repr(self.args)))
                bmc = OpTestQemu(conf=self,
                                 qemu_binary=self.args.qemu_binary,
                                 pnor=self.args.host_pnor,
                                 skiboot=self.args.flash_skiboot,
                                 kernel=self.args.flash_kernel,
                                 initramfs=self.args.flash_initramfs,
                                 cdrom=self.args.os_cdrom,
                                 logfile=self.logfile)
                self.op_system = common.OpTestSystem.OpTestQemuSystem(host=host,
                                                                      bmc=bmc,
                                                                      state=self.startState,
                                                                      conf=self,
                                                                      )
                bmc.set_system(self.op_system)
            elif self.args.bmc_type in ['mambo']:
                if not (os.stat(self.args.mambo_binary).st_mode & stat.S_IXOTH):
                    raise ParameterCheck(message="Check that the file exists with X permissions mambo-binary={}"
                                         .format(self.args.mambo_binary))
                if self.args.flash_skiboot is None \
                        or not os.access(self.args.flash_skiboot, os.R_OK):
                    raise ParameterCheck(message="Check that the file exists with R permissions flash-skiboot={}"
                                         .format(self.args.flash_skiboot))
                if self.args.flash_kernel is None \
                        or not os.access(self.args.flash_kernel, os.R_OK):
                    raise ParameterCheck(message="Check that the file exists with R permissions flash-kernel={}"
                                         .format(self.args.flash_kernel))
                bmc = OpTestMambo(mambo_binary=self.args.mambo_binary,
                                  mambo_initial_run_script=self.args.mambo_initial_run_script,
                                  mambo_autorun=self.args.mambo_autorun,
                                  skiboot=self.args.flash_skiboot,
                                  kernel=self.args.flash_kernel,
                                  initramfs=self.args.flash_initramfs,
                                  timeout_factor=self.args.mambo_timeout_factor,
                                  logfile=self.logfile)
                self.op_system = common.OpTestSystem.OpTestMamboSystem(host=host,
                                                                       bmc=bmc,
                                                                       state=self.startState,
                                                                       conf=self,
                                                                       )
                bmc.set_system(self.op_system)

            # Check that the bmc_type exists in our loaded addons then create our objects
            elif self.args.bmc_type in optAddons:
                (bmc, self.op_system) = optAddons[self.args.bmc_type].createSystem(
                    self, host)
            else:
                self.util.cleanup()
                raise Exception("Unsupported BMC Type '{}', check your "
                                "upper/lower cases for bmc_type and verify "
                                "any credentials used from HostLocker or "
                                "AES Version (see aes_get_creds "
                                "version_mappings)".format(self.args.bmc_type))

            host.set_system(self.op_system)
            return
        except Exception as e:
            traceback.print_exc()
            self.util.cleanup()
            raise e

    def bmc(self):
        return self.op_system.bmc

    def hmc(self):
        return self.op_system.hmc

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
