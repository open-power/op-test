#!/usr/bin/python2
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

# Let's boot some Installers!

import unittest
import time
import pexpect

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common import OpTestInstallUtil


class MyIPfromHost(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.util = OpTestUtil()

    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.system.sys_get_ipmi_console()
        self.system.host_console_unique_prompt()
        my_ip = self.system.get_my_ip_from_host_perspective()
        print "# FOUND MY IP: %s" % my_ip


class InstallUbuntu(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.conf = conf
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.util = OpTestUtil()
        self.bmc_type = conf.args.bmc_type
        if not (self.conf.args.os_repo or self.conf.args.os_cdrom):
            self.fail("Provide installation media for installation with --os-repo or --os-cdrom")
        if "qemu" not in self.bmc_type and not (self.conf.args.host_ip and self.conf.args.host_gateway and self.conf.args.host_dns and self.conf.args.host_submask and self.conf.args.host_mac):
            self.fail("Provide host network details refer, --host-{ip,gateway,dns,submask,mac}")
        if not (self.conf.args.host_user and self.conf.args.host_password):
            self.fail("Provide host user details refer, --host-{user,password}")
        if not self.host.get_scratch_disk():
            self.fail("Provide proper host disk to install refer, --host-scratch-disk")

    def select_petitboot_item(self, item):
        self.system.goto_state(OpSystemState.PETITBOOT)
        rawc = self.c.get_console()
        r = None
        while r != 0:
            time.sleep(0.2)
            r = rawc.expect(['\*.*\s+' + item, '\*.*\s+', pexpect.TIMEOUT],
                            timeout=1)
            if r == 0:
                break
            rawc.send("\x1b[A")
            rawc.expect('')
            rawc.sendcontrol('l')

    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        # Set the install paths
        base_path = "osimages/ubuntu"
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
                       'url=http://%s:%s/preseed.cfg' % (self.host.get_scratch_disk(),
                                                         my_ip, port))

        if not self.conf.args.host_dns in [None, ""]:
            kernel_args = kernel_args + ' netcfg/disable_autoconfig=true '
            kernel_args = kernel_args + 'netcfg/get_nameservers=%s ' % self.conf.args.host_dns
            kernel_args = kernel_args + 'netcfg/get_ipaddress=%s ' % self.host.ip
            kernel_args = kernel_args + 'netcfg/get_netmask=%s ' % self.conf.args.host_submask
            kernel_args = kernel_args + 'netcfg/get_gateway=%s ' % self.conf.args.host_gateway

        self.c = self.system.sys_get_ipmi_console()
        self.system.host_console_unique_prompt()
        if "qemu" in self.bmc_type:
            kernel_args = kernel_args + ' netcfg/choose_interface=auto '
            # For Qemu, we boot from CDROM, so let's use petitboot!
            self.select_petitboot_item('Install Ubuntu Server')
            rawc = self.c.get_console()
            rawc.send('e')
            # In future, we should implement a method like this:
            #  self.petitboot_select_field('Boot arguments:')
            # But, in the meantime:
            rawc.send('\t\t\t\t')  # FIXME :)
            rawc.send('\b\b\b\b')  # remove ' ---'
            rawc.send('\b\b\b\b\b')  # remove 'quiet'
            rawc.send(kernel_args)
            rawc.send('\t')
            rawc.sendline('')
            rawc.sendline('')
        else:
            kernel_args = kernel_args + ' netcfg/choose_interface=%s BOOTIF=01-%s' % (self.conf.args.host_mac,
                                                                                      '-'.join(self.conf.args.host_mac.split(':')))

            cmd = "[ -f %s ]&& rm -f %s;[ -f %s ] && rm -f %s;true" % (vmlinux,
                                                                       vmlinux,
                                                                       initrd,
                                                                       initrd)
            self.c.run_command(cmd)
            self.c.run_command("wget http://%s:%s/%s" % (my_ip, port, vmlinux))
            self.c.run_command("wget http://%s:%s/%s" % (my_ip, port, initrd))
            self.c.run_command("kexec -i %s -c \"%s\" %s -l" % (initrd,
                                                                kernel_args,
                                                                vmlinux))
            rawc = self.c.get_console()
            rawc.sendline("kexec -e")

        # Do things
        rawc.expect('Sent SIGKILL to all processes', timeout=60)
        r = rawc.expect(['Loading additional components','Configure the keyboard'], timeout=300)
        if r == 1:
            print "# Preseed isn't perfect when it comes to keyboard selection. Urgh"
            rawc.expect('Go Back')
            time.sleep(2)
            rawc.send("\r\n")
            rawc.expect(['Keyboard layout'])
            rawc.expect(['activates buttons'])
            time.sleep(2)
            rawc.sendline("\r\n")
            rawc.expect(['Loading additional components'], timeout=300)

        r = 0
        while r == 0:
            r = rawc.expect(['udeb', 'Setting up the clock', 'Detecting hardware'], timeout=300)

        rawc.expect('Partitions formatting', timeout=600)
        rawc.expect('Installing the base system', timeout=300)
        r = None
        while r != 0:
            r = rawc.expect(['Finishing the installation',
                             'Select and install software',
                             'Preparing', 'Configuring',
                             'Cleaning up'
                             'Retrieving', 'Installing',
                             'boot loader',
                             'Running'], timeout=600)
        rawc.expect('Requesting system reboot', timeout=300)
        self.system.set_state(OpSystemState.IPLing)
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        OpIU.stop_server()
        OpIU.set_bootable_disk(self.host.get_scratch_disk())
        self.system.goto_state(OpSystemState.OFF)
        self.system.goto_state(OpSystemState.OS)
        con = self.system.sys_get_ipmi_console()
        self.system.host_console_login()
        self.system.host_console_unique_prompt()
        con.run_command("uname -a")
        con.run_command("cat /etc/os-release")
        self.host.host_gather_opal_msg_log()
        self.host.host_gather_kernel_log()
