#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2018
# [+] International Business Machines Corp.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#

'''
Install Ubuntu
--------------

Installs Ubuntu on the host.

The idea behind this test is to both set up an OS suitable to run `op-test`
against and check our backwards compatibility with installation media.
'''

import unittest
import time
import pexpect
import os

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common import OpTestInstallUtil

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class MyIPfromHost(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console
        my_ip = self.cv_SYSTEM.get_my_ip_from_host_perspective()
        print(("# FOUND MY IP: %s" % my_ip))


class InstallUbuntu(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.conf = conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.bmc_type = conf.args.bmc_type
        if not (self.conf.args.os_repo or self.conf.args.os_cdrom):
            self.fail(
                "Provide installation media for installation with --os-repo or --os-cdrom")
        if "qemu" not in self.bmc_type and not (self.conf.args.host_ip and self.conf.args.host_gateway and self.conf.args.host_dns and self.conf.args.host_submask and self.conf.args.host_mac):
            self.fail(
                "Provide host network details refer, --host-{ip,gateway,dns,submask,mac}")
        if not (self.conf.args.host_user and self.conf.args.host_password):
            self.fail(
                "Provide host user details refer, --host-{user,password}")
        if not self.cv_HOST.get_scratch_disk():
            self.fail(
                "Provide proper host disk to install refer, --host-scratch-disk")

    def select_petitboot_item(self, item):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT)
        raw_pty = self.c.get_console()
        r = None
        while r != 0:
            time.sleep(0.2)
            r = raw_pty.expect(['\*.*\s+' + item, '\*.*\s+', pexpect.TIMEOUT],
                               timeout=1)
            if r == 0:
                break
            raw_pty.send("\x1b[A")
            raw_pty.expect('')
            raw_pty.sendcontrol('l')

    def runTest(self):
        if self.conf.args.no_os_reinstall:
            self.skipTest(
                "--no-os-reinstall set, not trying to run install OS test")
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)

        # Set the install paths
        base_path = os.path.join(self.conf.basedir, "osimages", "ubuntu")
        boot_path = "ubuntu-installer/ppc64el"
        vmlinux = "vmlinux"
        initrd = "initrd.gz"
        ks = "preseed.cfg"
        OpIU = OpTestInstallUtil.InstallUtil(base_path=base_path,
                                             vmlinux=vmlinux,
                                             initrd=initrd,
                                             ks=ks,
                                             boot_path=boot_path)
        my_ip = OpIU.get_server_ip()
        if not my_ip:
            self.fail("unable to get the ip from host")

        if "qemu" not in self.bmc_type:
            if self.conf.args.os_cdrom and not self.conf.args.os_repo:
                repo = OpIU.setup_repo(self.conf.args.os_cdrom)
            if self.conf.args.os_repo:
                repo = self.conf.args.os_repo
            if not repo:
                self.fail("No valid repo to start installation")
            if not OpIU.extract_install_files(repo):
                self.fail("Unable to download install files")

        # start our web server
        port = OpIU.start_server(my_ip)

        if "qemu" not in self.bmc_type and not self.conf.args.os_repo:
            repo = 'http://%s:%s/repo' % (my_ip, port)

        kernel_args = (' auto console=hvc0 '
                       'interface=auto '
                       'localechooser/languagelist=en '
                       'debian-installer/country=US '
                       'debian-installer/locale=en_US '
                       'console-setup/ask_detect=false '
                       'console-setup/layoutcode=us '
                       'netcfg/get_hostname=ubuntu '
                       'netcfg/get_domain=example.com '
                       'netcfg/link_wait_timeout=60 '
                       'partman-auto/disk=%s '
                       'locale=en_US '
                       'url=http://%s:%s/preseed.cfg' % (self.cv_HOST.get_scratch_disk(),
                                                         my_ip, port))

        if not self.conf.args.host_dns in [None, ""]:
            kernel_args = kernel_args + ' netcfg/disable_autoconfig=true '
            kernel_args = kernel_args + 'netcfg/get_nameservers=%s ' % self.conf.args.host_dns
            kernel_args = kernel_args + 'netcfg/get_ipaddress=%s ' % self.cv_HOST.ip
            kernel_args = kernel_args + 'netcfg/get_netmask=%s ' % self.conf.args.host_submask
            kernel_args = kernel_args + 'netcfg/get_gateway=%s ' % self.conf.args.host_gateway

        if not self.conf.args.proxy in [None, ""]:
            kernel_args = kernel_args + \
                'mirror/http/proxy={} '.format(self.conf.args.proxy)

        self.c = self.cv_SYSTEM.console
        if "qemu" in self.bmc_type:
            kernel_args = kernel_args + ' netcfg/choose_interface=auto '
            # For Qemu, we boot from CDROM, so let's use petitboot!
            self.select_petitboot_item('Install Ubuntu Server')
            raw_pty = self.c.get_console()
            raw_pty.send('e')
            # In future, we should implement a method like this:
            #  self.petitboot_select_field('Boot arguments:')
            # But, in the meantime:
            raw_pty.send('\t\t\t\t')  # FIXME :)
            raw_pty.send('\b\b\b\b')  # remove ' ---'
            raw_pty.send('\b\b\b\b\b')  # remove 'quiet'
            raw_pty.send(kernel_args)
            raw_pty.send('\t')
            raw_pty.sendline('')
            raw_pty.sendline('')
        else:
            kernel_args = kernel_args + ' netcfg/choose_interface=%s BOOTIF=01-%s' % (self.conf.args.host_mac,
                                                                                      '-'.join(self.conf.args.host_mac.split(':')))

            cmd = "[ -f %s ]&& rm -f %s;[ -f %s ] && rm -f %s;true" % (vmlinux,
                                                                       vmlinux,
                                                                       initrd,
                                                                       initrd)
            self.c.run_command(cmd)
            try:
                log.debug("Install OPEN marker for wget vmlinux")
                self.c.run_command("wget http://%s:%s/%s" %
                                   (my_ip, port, vmlinux), timeout=300)
                log.debug("Install CLOSE marker for wget vmlinux")
                log.debug("Install OPEN marker for wget initrd")
                self.c.run_command("wget http://%s:%s/%s" %
                                   (my_ip, port, initrd), timeout=300)
                log.debug("Install CLOSE marker for wget initrd")
                log.debug("Install OPEN marker for kexec")
                self.c.run_command("kexec -i %s -c \"%s\" %s -l" % (initrd,
                                                                    kernel_args,
                                                                    vmlinux), timeout=300)
                log.debug("Install CLOSE marker for kexec")
            except Exception as e:
                log.debug("wget or kexec Exception={}".format(e))
            raw_pty = self.c.get_console()
            raw_pty.sendline("kexec -e")

        # Do things
        raw_pty.expect(['Sent SIGKILL to all processes', 'Starting new kernel'],
                       timeout=60)
        log.debug("Install OPEN marker for Loading Configure")
        log.debug(
            "There sometimes are timing issues with Host OS networking coming live concurrently, just retry")
        log.debug(
            "Symptoms seen are failure to download preseed.cfg from op-test box, etc.")
        r = raw_pty.expect(['Loading additional components',
                            'Configure the keyboard', pexpect.TIMEOUT, pexpect.EOF], timeout=300)
        log.debug("Install CLOSE marker for Loading Configure")
        log.debug("r={}".format(r))
        log.debug("raw_pty.before={}".format(raw_pty.before))
        log.debug("raw_pty.after={}".format(raw_pty.after))
        if r == 1:
            print("# Preseed isn't perfect when it comes to keyboard selection. Urgh")
            raw_pty.expect('Go Back')
            time.sleep(2)
            raw_pty.send("\r\n")
            raw_pty.expect(['Keyboard layout'])
            raw_pty.expect(['activates buttons'])
            time.sleep(2)
            raw_pty.sendline("\r\n")
            raw_pty.expect(['Loading additional components'], timeout=300)

        r = 0
        while r == 0:
            r = raw_pty.expect(
                ['udeb', 'Setting up the clock', 'Detecting hardware'], timeout=300)

        log.debug("Install OPEN marker for Partitions formatting")
        raw_pty.expect('Partitions formatting', timeout=600)
        log.debug("Install CLOSE marker for Partitions formatting")
        log.debug("Install OPEN marker for Installing the base system")
        raw_pty.expect('Installing the base system', timeout=300)
        log.debug("Install CLOSE marker for Installing the base system")
        r = None
        while r != 0:
            # FIXME: looping forever isn't ideal
            # But we do want to ensure forward progress
            # and not just timeout on a slow network
            r = raw_pty.expect(['Finishing the installation',
                                'Select and install software',
                                'Preparing', 'Configuring',
                                'Cleaning up'
                                'Retrieving', 'Installing',
                                'boot loader',
                                'Running',
                                pexpect.TIMEOUT], timeout=1000)

        log.debug("Install OPEN marker for Requesting system reboot")
        raw_pty.expect('Requesting system reboot', timeout=300)
        log.debug("Install CLOSE marker for Requesting system reboot")
        self.cv_SYSTEM.set_state(OpSystemState.IPLing)
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        OpIU.stop_server()
        OpIU.set_bootable_disk(self.cv_HOST.get_scratch_disk())
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        con = self.cv_SYSTEM.console
        # sometimes coming back up we need a few attempts
        con.run_command("uname -a", retry=5)
        con.run_command("cat /etc/os-release", retry=5)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()
