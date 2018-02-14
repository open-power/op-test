#!/usr/bin/python2
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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
import socket
import threading
import SocketServer
import BaseHTTPServer
import subprocess

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

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
        self.host = conf.host()
        self.ipmi = conf.ipmi()
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.util = OpTestUtil()
        self.bmc_type = conf.args.bmc_type

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
        self.c = self.system.sys_get_ipmi_console()
        self.system.host_console_unique_prompt()

        retry = 30
        while retry > 0:
            try:
                self.c.run_command("ifconfig -a")
                break
            except CommandFailed as cf:
                if cf.exitcode is 1:
                    time.sleep(1)
                    retry = retry - 1
                    pass
                else:
                    raise cf

        retry = 30
        while retry > 0:
            try:
                my_ip = self.system.get_my_ip_from_host_perspective()
                self.c.run_command("ping %s -c 1" % my_ip)
                break
            except CommandFailed as cf:
                if cf.exitcode is 1:
                    time.sleep(1)
                    retry = retry - 1
                    pass
                else:
                    raise cf

        scratch_disk_size = self.host.get_scratch_disk_size(self.c)

        # start our web server
        HOST, PORT = "0.0.0.0", 0
        server = ThreadedHTTPServer((HOST, PORT), ThreadedHTTPHandler)
        ip, port = server.server_address
        print "# Listening on %s:%s" % (ip,port)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print "# Server running in thread:",server_thread.name

        my_ip = self.system.get_my_ip_from_host_perspective()
        #self.c.run_command("wget -O- http://%s:%s" % (my_ip, port))
        #time.sleep(10)

        kernel_args = (' auto=true priority=critical interface=auto '
                       'debian-installer/locale=en_US '
                       'console-setup/ask_detect=false '
                       'console-setup/layoutcode=us '
                       'netcfg/get_hostname=ubuntu '
                       'netcfg/get_domain=example.com '
                       'netcfg/link_wait_timeout=60 '
                       'preseed/url=http://%s:%s/preseed.cfg' % (my_ip, port))

        if "qemu" in self.bmc_type:
            kernel_args = kernel_args + ' netcfg/choose_interface=auto '
            # For Qemu, we boot from CDROM, so let's use petitboot!
            self.select_petitboot_item('Install Ubuntu Server')
            rawc = self.c.get_console()
            rawc.send('e')
            # In future, we should implement a method like this:
            #  self.petitboot_select_field('Boot arguments:')
            # But, in the meantime:
            rawc.send('\t\t\t\t') # FIXME :)
            rawc.send('\b\b\b\b') # remove ' ---'
            rawc.send('\b\b\b\b\b') #remove 'quiet'
            rawc.send(kernel_args)
            rawc.send('\t')
            rawc.sendline('')
            rawc.sendline('')
        else:
            # With a "Normal" BMC rather than a simulator,
            # we need to go and grab things from the network to netboot

            # We also need to work around an Ubuntu/Debian installer bug:
            # https://bugs.launchpad.net/ubuntu/+source/netcfg/+bug/713385
            arp = subprocess.check_output(['arp', self.host.hostname()]).split('\n')[1]
            arp = arp.split()
            host_mac_addr = arp[2]
            print "# Found host mac addr %s", host_mac_addr
            kernel_args = kernel_args + ' netcfg/choose_interface=%s ' % host_mac_addr

            self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
            self.c.run_command("wget http://%s:%s/ubuntu/vmlinux" % (my_ip, port))
            self.c.run_command("wget http://%s:%s/ubuntu/initrd.gz" % (my_ip, port))
            self.c.run_command("kexec -i initrd.gz -c \"%s\" vmlinux -l" % kernel_args)
            self.c.get_console().send("kexec -e\n")

        self.system.wait_for_kexec()

        # Do things
        rawc = self.c.get_console()
        rawc.expect('Network autoconfiguration has succeeded',timeout=300)
        rawc.expect('Loading additional components',timeout=300)
        rawc.expect('Setting up the clock',timeout=300)
        rawc.expect('Detecting hardware',timeout=300)
        rawc.expect('Partitions formatting',timeout=300)
        rawc.expect('Installing the base system',timeout=300)
        r = None
        while r != 0:
            r = rawc.expect(['Finishing the installation',
                             'Select and install software',
                             'Preparing', 'Configuring',
                             'Cleaning up'
                             'Retrieving','Installing',
                             'boot loader',
                             'Running'], timeout=300)
        rawc.expect('Requesting system reboot', timeout=300)
        self.system.set_state(OpSystemState.IPLing)
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        server.shutdown()
        server.server_close()

class ThreadedHTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    UBUNTU_PRESEED = """#Ubuntu Preseed for op-test
# Preseeding only locale sets language, country and locale.
d-i debian-installer/locale string en_US
# Keyboard selection.
# Disable automatic (interactive) keymap detection.
d-i console-setup/ask_detect boolean false
d-i console-setup/layoutcode string us
d-i netcfg/get_hostname string {}
d-i netcfg/get_domain string {}
d-i netcfg/choose_interface select auto
d-i netcfg/link_wait_timeout string 20

d-i keyboard-configuration/xkb-keymap select us
# If you select ftp, the mirror/country string does not need to be set.
#d-i mirror/protocol string ftp
d-i mirror/country string manual
d-i mirror/http/hostname string ports.ubuntu.com
d-i mirror/http/directory string /
d-i mirror/http/proxy string {}

# Alternatively: by default, the installer uses CC.archive.ubuntu.com where
# CC is the ISO-3166-2 code for the selected country. You can preseed this
# so that it does so without asking.
#d-i mirror/http/mirror select CC.archive.ubuntu.com

# Suite to install.
#d-i mirror/suite string xenial
# Suite to use for loading installer components (optional).
#d-i mirror/udeb/suite string xenial
# Components to use for loading installer components (optional).
#d-i mirror/udeb/components multiselect main, restricted

# Skip creation of a root account (normal user account will be able to
# use sudo). The default is false; preseed this to true if you want to set
# a root password.
#d-i passwd/root-login boolean false
# Alternatively, to skip creation of a normal user account.
#d-i passwd/make-user boolean false

# Root password, either in clear text
d-i passwd/root-password password {}
d-i passwd/root-password-again password {}
# or encrypted using a crypt(3)  hash.
#d-i passwd/root-password-crypted password [crypt(3) hash]

# To create a normal user account.
d-i passwd/user-fullname string Ubuntu User
d-i passwd/username string {}
# Normal user's password, either in clear text
d-i passwd/user-password password {}
d-i passwd/user-password-again password {}
# or encrypted using a crypt(3) hash.
#d-i passwd/user-password-crypted password [crypt(3) hash]
# Create the first user with the specified UID instead of the default.
#d-i passwd/user-uid string 1010
# The installer will warn about weak passwords. If you are sure you know
# what you're doing and want to override it, uncomment this.
d-i user-setup/allow-password-weak boolean true

# The user account will be added to some standard initial groups. To
# override that, use this.
#d-i passwd/user-default-groups string audio cdrom video

# Set to true if you want to encrypt the first user's home directory.
d-i user-setup/encrypt-home boolean false

# Controls whether or not the hardware clock is set to UTC.
d-i clock-setup/utc boolean true

# You may set this to any valid setting for $TZ; see the contents of
# /usr/share/zoneinfo/ for valid values.
d-i time/zone string US/Eastern

# Controls whether to use NTP to set the clock during the install
d-i clock-setup/ntp boolean true
# NTP server to use. The default is almost always fine here.
#d-i clock-setup/ntp-server string ntp.example.com

# Alternatively, you may specify a disk to partition. If the system has only
# one disk the installer will default to using that, but otherwise the device
# name must be given in traditional, non-devfs format (so e.g. /dev/sda
# and not e.g. /dev/discs/disc0/disc).
# For example, to use the first SCSI/SATA hard disk:
d-i partman-auto/disk string {}
# In addition, you'll need to specify the method to use.
# The presently available methods are:
# - regular: use the usual partition types for your architecture
# - lvm:     use LVM to partition the disk
# - crypto:  use LVM within an encrypted partition
d-i partman-auto/method string regular

# If one of the disks that are going to be automatically partitioned
# contains an old LVM configuration, the user will normally receive a
# warning. This can be preseeded away...
d-i partman-lvm/device_remove_lvm boolean true
# The same applies to pre-existing software RAID array:
d-i partman-md/device_remove_md boolean true
# And the same goes for the confirmation to write the lvm partitions.
d-i partman-lvm/confirm boolean true
d-i partman-lvm/confirm_nooverwrite boolean true

# You can choose one of the three predefined partitioning recipes:
# - atomic: all files in one partition
# - home:   separate /home partition
# - multi:  separate /home, /var, and /tmp partitions
#d-i partman-auto/choose_recipe select atomic
#d-i partman/default_filesystem string ext4

d-i partman-auto/expert_recipe string                         \
      root ::                                                 \
              8 1 8 prep                                      \
              $primary{{ }}                                   \
              $bootable{{ }}                                  \
              method{{ prep }}                                \
              .                                               \
              500 10000 {} ext4                               \
                      method{{ format }} format{{ }}          \
                      use_filesystem{{ }} filesystem{{ ext4 }} \
                      label {{ {} }} mountpoint{{ / }}        \
              .                                               \
              100% 512 64000 linux-swap                       \
                      method{{ swap }} format{{ }}            \

# This makes partman automatically partition without confirmation, provided
# that you told it what to do using one of the methods above.
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# You can choose to install restricted and universe software, or to install
# software from the backports repository.
d-i apt-setup/restricted boolean true
d-i apt-setup/universe boolean true

# Individual additional packages to install
d-i pkgsel/include string {}

# Avoid that last message about the install being complete.
d-i finish-install/reboot_in_progress note
"""
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        conf = OpTestConfiguration.conf
        host = conf.host()
        packages_to_install = "linux-tools-common linux-tools-generic lm-sensors ipmitool i2c-tools pciutils opal-prd opal-utils"

        print "# Webserver was asked for: ", self.path
        if self.path == "/ubuntu/vmlinux":
            f = open("osimages/ubuntu/vmlinux", "r")
            d = f.read()
            self.wfile.write(d)
            f.close()
            return

        if self.path == "/ubuntu/initrd.gz":
            f = open("osimages/ubuntu/initrd.gz", "r")
            d = f.read()
            self.wfile.write(d)
            f.close()
            return

        host_username = host.username()
        if host_username == "root":
            host_username = "ubuntu"

        ps = self.UBUNTU_PRESEED.format("openpower","example.com",
                                        host.get_proxy(),
                                        host.password(), host.password(),
                                        host_username,
                                        host.password(), host.password(),
                                        host.get_scratch_disk(),
                                        int((host.get_scratch_disk_size()/(1024*1024))/2),
                                        "op-test-ubuntu-root",
                                        packages_to_install)
        self.wfile.write(ps)

class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass
