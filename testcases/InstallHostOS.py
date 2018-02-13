#!/usr/bin/python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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


import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common import OpTestInstallUtil


class InstallHostOS(unittest.TestCase):
    def setUp(self):
        self.conf = OpTestConfiguration.conf
        self.host = self.conf.host()
        self.ipmi = self.conf.ipmi()
        self.system = self.conf.system()
        self.bmc = self.conf.bmc()
        self.util = OpTestUtil()
        self.bmc_type = self.conf.args.bmc_type
        if not (self.conf.args.os_repo or self.conf.args.os_cdrom):
            self.fail("Provide installation media for installation, --os-repo is missing")
        if not (self.conf.args.host_gateway and self.conf.args.host_dns and self.conf.args.host_submask and self.conf.args.host_mac):
            self.fail("Provide host network details refer, --host-{gateway,dns,submask,mac}")
        if not self.conf.args.host_scratch_disk:
            self.fail("Provide proper host disk to install refer, --host-scratch-disk")

    def runTest(self):
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        # Local path to keep install files
        base_path = "osimages/hostos"
        # relative path from repo where vmlinux and initrd is present
        boot_path = "ppc/ppc64"
        vmlinux = "vmlinuz"
        initrd = "initrd.img"
        ks = "hostos.ks"
        OpIU = OpTestInstallUtil.InstallUtil(base_path=base_path,
                                             vmlinux=vmlinux,
                                             initrd=initrd,
                                             ks=ks,
                                             boot_path=boot_path)
        my_ip = OpIU.get_server_ip()
        if not my_ip:
            self.fail("Unable to get the ip from host")

        if self.conf.args.os_cdrom and not self.conf.args.os_repo:
            repo = OpIU.setup_repo(self.conf.args.os_cdrom)
        if self.conf.args.os_repo:
            repo = self.conf.args.os_repo
        if not repo:
            self.fail("No valid repo to start installation")
        if not OpIU.extract_install_files(repo):
            self.fail("Unable to download install files")

        OpIU.extract_install_files(repo)

        # start our web server
        port = OpIU.start_server(my_ip)

        if "qemu" not in self.bmc_type:
            ks_url = 'http://%s:%s/%s' % (my_ip, port, ks)
            kernel_args = "ifname=net0:%s ip=%s::%s:%s:%s:net0:none nameserver=%s inst.ks=%s" % (self.conf.args.host_mac,
                                                                                                 self.host.ip,
                                                                                                 self.conf.args.host_gateway,
                                                                                                 self.conf.args.host_submask,
                                                                                                 self.host.hostname(),
                                                                                                 self.conf.args.host_dns,
                                                                                                 ks_url)
            self.c = self.system.sys_get_ipmi_console()
            self.system.host_console_unique_prompt()
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
        else:
            pass
        # Do things
        rawc = self.c.get_console()
        rawc.expect('opal: OPAL detected', timeout=60)
        r = None
        while r != 0:
            r = rawc.expect(['Running post-installation scripts',
                             'Starting installer',
                             'Setting up the installation environment',
                             'Starting package installation process',
                             'Performing post-installation setup tasks',
                             'Configuring installed system'], timeout=1500)
        rawc.expect('reboot: Restarting system', timeout=300)
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
