#!/usr/bin/env python3
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
# OpTest Install Utils
#

import shutil
import urllib.request
import urllib.error
import urllib.parse
import os
import threading
import socketserver
import http.server
import http.server
import cgi
import subprocess
import time
from .Exceptions import CommandFailed, UnexpectedCase
import OpTestConfiguration

from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

BASE_PATH = ""
INITRD = ""
VMLINUX = ""
KS = ""
DISK = ""
USERNAME = ""
PASSWORD = ""
REPO = ""
BOOTPATH = ""

uploaded_files = {}


class InstallUtil():
    def __init__(self, base_path="", initrd="", vmlinux="",
                 ks="", boot_path="", repo=""):
        global BASE_PATH
        global INITRD
        global VMLINUX
        global KS
        global DISK
        global USERNAME
        global PASSWORD
        global BOOTPATH
        global REPO
        global PROXY
        self.conf = OpTestConfiguration.conf
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.server = ""
        self.repo = self.conf.args.os_repo
        REPO = self.repo
        DISK = self.cv_HOST.get_scratch_disk()
        USERNAME = self.cv_HOST.username()
        PASSWORD = self.cv_HOST.password()
        BOOTPATH = boot_path
        BASE_PATH = base_path
        INITRD = initrd
        VMLINUX = vmlinux
        PROXY = self.cv_HOST.get_proxy()
        KS = ks

    def wait_for_network(self):
        retry = 6
        while retry > 0:
            try:
                self.cv_SYSTEM.console.run_command("ifconfig -a", retry=5)
                return True
            except CommandFailed as cf:
                log.debug("wait_for_network CommandFailed={}".format(cf))
                if cf.exitcode is 1:
                    time.sleep(5)
                    retry = retry - 1
                    pass
                else:
                    log.debug("wait_for_network ELSE raise cf={}".format(cf))
                    raise cf

    def ping_network(self):
        retry = 6
        while retry > 0:
            try:
                ip = self.conf.args.host_gateway
                log.debug("ping_network ip={}".format(ip))
                if ip in [None, ""]:
                    ip = self.cv_SYSTEM.get_my_ip_from_host_perspective()
                    log.debug("ping_network tried to get new ip={}".format(ip))
                cmd = "ping %s -c 1" % ip
                log.debug("ping_network retry=50, use this to gauge if network problems, "
                          " compare with run_command logging to help figure out whats wrong")
                output = self.cv_SYSTEM.console.run_command(cmd, retry=50)
                log.debug("ping_network output={}".format(output))
                return True
            except CommandFailed as cf:
                log.debug("ping_network Exception={}".format(cf))
                if retry == 1:
                    log.debug("ping_network raise cf={}".format(cf))
                    raise cf
                if cf.exitcode is 1:
                    time.sleep(5)
                    retry = retry - 1
                    log.debug(
                        "ping_network Exception path, retry={}".format(retry))
                    pass
                else:
                    log.debug(
                        "ping_network Exception path ELSE, raise cf={}".format(cf))
                    raise cf

    def assign_ip_petitboot(self):
        """
        Assign host ip in petitboot
        """
        # Lets reduce timeout in petitboot
        self.cv_SYSTEM.console.run_command(
            "nvram --update-config petitboot,timeout=10", retry=5)
        # this will not work without these
        if not self.conf.args.host_mac \
                or not self.conf.args.host_submask \
                or not self.conf.args.host_gateway \
                or not self.conf.args.host_dns:
            my_msg = ("We need host_mac/host_submask/host_gateway/host_dns provided"
                      " on command line args or via configuration files.")
            noconfig_exception = UnexpectedCase(
                state="assign_ip_petitboot config", message=my_msg)
            raise noconfig_exception
        cmd = (
            "ip addr|grep -B1 -i %s |grep BROADCAST|awk -F ':' '{print $2}'" % (self.conf.args.host_mac))
        log.debug("ip addr cmd={}".format(cmd, type(cmd)))
        iface = self.cv_SYSTEM.console.run_command(cmd, retry=5)
        log.debug("iface={} type={} len={}".format(
            iface, type(iface), len(iface)))
        if len(iface) >= 1:
            iface = self.cv_SYSTEM.console.run_command(cmd)[0].strip()
        else:
            my_msg = ("We did NOT get interface back from query, UNABLE to proceed with trying to "
                      "setup the IP, check that Petitboot or Host OS is configured properly.")
            noface_exception = UnexpectedCase(
                state="assign_ip_petitboot interface", message=my_msg)
            raise noiface_exception
        cmd = ("ifconfig %s %s netmask %s" %
               (iface, self.cv_HOST.ip, self.conf.args.host_submask))
        log.debug("ifconfig cmd={}".format(cmd))
        self.cv_SYSTEM.console.run_command(cmd, retry=5)
        cmd = ("route add default gateway %s" % self.conf.args.host_gateway)
        log.debug("route cmd={}".format(cmd))
        self.cv_SYSTEM.console.run_command_ignore_fail(cmd)
        cmd = ("echo 'nameserver %s' > /etc/resolv.conf" %
               self.conf.args.host_dns)
        log.debug("nameserver cmd={}".format(cmd))
        self.cv_SYSTEM.console.run_command(cmd, retry=5)

    def configure_host_ip(self):
        self.wait_for_network()
        # Check if ip is assigned in petitboot
        try:
            self.ping_network()
        except CommandFailed as cf:
            log.debug("configure_host_ip CommandFailed={}".format(cf))
            try:
                self.assign_ip_petitboot()
                self.ping_network()
            except Exception as e:
                log.debug("configure_host_ip Exception={}".format(e))
                my_msg = "We failed to setup Petitboot or Host IP, check that the IP's are configured and any other configuration parms"
                noconfig_exception = UnexpectedCase(
                    state="configure_host_ip", message=my_msg)
                raise noconfig_exception

    def get_server_ip(self):
        """
        Get IP of server where test runs
        """
        my_ip = ""
        try:
            self.configure_host_ip()
        except Exception as e:
            my_msg = "Exception trying configure_host_ip, e={}".format(e)
            configure_exception = UnexpectedCase(
                state="get_server_ip", message=my_msg)
            raise configure_exception
        retry = 30
        while retry > 0:
            try:
                my_ip = self.cv_SYSTEM.get_my_ip_from_host_perspective()
                log.debug("get_server_ip my_ip={}".format(my_ip))
                if not my_ip:
                    my_msg = "We were not able to get IP from Petitboot or Host, check that the IP is configured"
                    noip_exception = UnexpectedCase(
                        state="get_server_ip", message=my_msg)
                    raise noip_exception
                output = self.cv_SYSTEM.console.run_command(
                    "ping {} -c 1".format(my_ip), retry=5)
                log.debug("get_server_ip output={}".format(output))
                break
            except CommandFailed as cf:
                log.debug("get_server_ip CommandFailed cf={}".format(cf))
                if cf.exitcode is 1:
                    time.sleep(1)
                    retry = retry - 1
                    pass
                else:
                    log.debug("get_server_ip Exception={}".format(cf))
                    raise cf

        return my_ip

    def get_uploaded_file(self, name):
        return uploaded_files.get(name)

    def start_server(self, server_ip):
        """
        Start local http server
        """
        HOST, PORT = "0.0.0.0", 0
        global REPO
        self.server = ThreadedHTTPServer((HOST, PORT), ThreadedHTTPHandler)
        ip, port = self.server.server_address
        if not REPO:
            REPO = "http://%s:%s/repo" % (server_ip, port)
        print(("# Listening on %s:%s" % (ip, port)))
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(("# Server running in thread:", server_thread.name))
        return port

    def stop_server(self):
        """
        Stops local http server
        """
        self.server.shutdown()
        self.server.server_close()
        return

    def setup_repo(self, cdrom):
        """
        Sets up repo from given cdrom.
        Check if given cdrom is url or file
        if url, download in the BASE_PATH and
        mount to repo folder

        :params cdrom: OS cdrom path local or remote
        """
        repo_path = os.path.join(BASE_PATH, 'repo')
        abs_repo_path = os.path.abspath(repo_path)
        # Clear already mount repo
        if os.path.ismount(repo_path):
            status, output = subprocess.getstatusoutput(
                "umount %s" % abs_repo_path)
            if status != 0:
                print(("failed to unmount", abs_repo_path))
                return ""
        elif os.path.isdir(repo_path):
            shutil.rmtree(repo_path)
        else:
            pass
        if not os.path.isdir(repo_path):
            os.makedirs(abs_repo_path)

        if os.path.isfile(cdrom):
            cdrom_path = cdrom
        else:
            cdrom_url = urllib.request.urlopen(cdrom)
            if not cdrom_url:
                print(("Unknown cdrom path %s" % cdrom))
                return ""
            with open(os.path.join(BASE_PATH, "iso"), 'wb') as f:
                f.write(cdrom_url.read())
            cdrom_path = os.path.join(BASE_PATH, "iso")
        cmd = "mount -t iso9660 -o loop %s %s" % (cdrom_path, abs_repo_path)
        status, output = subprocess.getstatusoutput(cmd)
        if status != 0:
            print(("Failed to mount iso %s on %s\n %s", (cdrom, abs_repo_path,
                                                         output)))
            return ""
        return abs_repo_path

    def extract_install_files(self, repo_path):
        """
        extract the install file from given repo path

        :params repo_path: os repo path either local or remote
        """
        vmlinux_src = os.path.join(repo_path, BOOTPATH, VMLINUX)
        initrd_src = os.path.join(repo_path, BOOTPATH, INITRD)
        vmlinux_dst = os.path.join(BASE_PATH, VMLINUX)
        initrd_dst = os.path.join(BASE_PATH, INITRD)
        # let us make sure, no old vmlinux, initrd
        if os.path.isfile(vmlinux_dst):
            os.remove(vmlinux_dst)
        if os.path.isfile(initrd_dst):
            os.remove(initrd_dst)

        if os.path.isdir(repo_path):
            try:
                shutil.copyfile(vmlinux_src, vmlinux_dst)
                shutil.copyfile(initrd_src, initrd_dst)
            except Exception:
                return False
        else:
            vmlinux_file = urllib.request.urlopen(vmlinux_src)
            initrd_file = urllib.request.urlopen(initrd_src)
            if not (vmlinux_file and initrd_file):
                print(("Unknown repo path %s, %s" % (vmlinux_src, initrd_src)))
                return False
            try:
                with open(vmlinux_dst, 'wb') as f:
                    f.write(vmlinux_file.read())
                with open(initrd_dst, 'wb') as f:
                    f.write(initrd_file.read())
            except Exception:
                return False
        return True

    def set_bootable_disk(self, disk):
        """
        Sets the given disk as default bootable entry in petitboot
        """
        self.cv_SYSTEM.sys_set_bootdev_no_override()
        # FIXME: wait till the device(disk) discovery in petitboot
        time.sleep(60)
        cmd = 'blkid %s*' % disk
        output = self.cv_SYSTEM.console.run_command(cmd)
        uuid = output[0].split(':')[1].split('=')[1].replace("\"", "")
        cmd = 'nvram --update-config "auto-boot?=true"'
        output = self.cv_SYSTEM.console.run_command(cmd)
        cmd = 'nvram --update-config petitboot,bootdevs=uuid:%s' % uuid
        output = self.cv_SYSTEM.console.run_command(cmd)
        cmd = 'nvram --print-config'
        output = self.cv_SYSTEM.console.run_command(cmd)
        return

    def get_boot_cfg(self):
        """
        Find bootloader cfg file path of host.

        :return: bootloader cfg file path, empty string if no cfg file found.
        """
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        bootloader_cfg = [
            '/boot/grub/grub.conf',
            '/boot/grub2/grub.cfg',
            '/etc/grub.conf',
            '/etc/grub2.cfg',
            '/boot/etc/yaboot.conf',
            '/etc/default/grub'
        ]
        cfg_path = ''
        for path in bootloader_cfg:
            cmd = "test -f %s" % path
            try:
                con.run_command(cmd)
                cfg_path = path
            except CommandFailed:
                continue
        return cfg_path

    def check_kernel_cmdline(self, args="", remove_args=""):
        """
        Method to check whether args are already exists or not in /proc/cmdline

        :param args: arguments to be checked whether already exists or to add
        :param remove_args: arguments to be checked whether it doesn't exists
                            or to remove.

        :return: required arguments to be added/removed of type str
        """
        req_args = ""
        req_remove_args = ""
        check_cmd = "cat /proc/cmdline"
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        try:
            check_output = con.run_command(check_cmd, timeout=60)[0].split()
            for each_arg in args.split():
                if each_arg not in check_output:
                    req_args += "%s " % each_arg
            for each_arg in remove_args.split():
                if each_arg in check_output:
                    req_remove_args += "%s " % each_arg
        except CommandFailed as Err:
            print(("Failed to get kernel commandline using %s: %s" %
                   (Err.command, Err.output)))
        return req_args.strip(), req_remove_args.strip()

    def update_kernel_cmdline(self, args="", remove_args="", reboot=True):
        """
        Update default Kernel cmdline arguments

        :param args: Kernel option to be included
        :param remove_args: Kernel option to be removed
        :param reboot: whether to reboot the host or not

        :return: True on success and False on failure
        """
        output = ""
        con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        req_args, req_remove_args = self.check_kernel_cmdline(args,
                                                              remove_args)
        try:
            con.run_command("grubby --help", timeout=60)
            cmd = 'grubby --update-kernel=`grubby --default-kernel` '
            if req_args:
                cmd += '--args="%s" ' % req_args
            if req_remove_args:
                cmd += '--remove-args="%s"' % req_remove_args
            try:
                con.run_command(cmd)
            except CommandFailed as Err:
                print(("Failed to update kernel commandline using %s: %s" %
                       (Err.command, Err.output)))
                return False
        # If grubby is not available fallback by changing grub file
        except CommandFailed:
            grub_key = "GRUB_CMDLINE_LINUX_DEFAULT"
            boot_cfg = self.get_boot_cfg()
            cmd = "grep %s %s" % (grub_key, boot_cfg)
            try:
                output = con.run_command(cmd, timeout=60)[0].replace("\"", "")
                output = output.split("GRUB_CMDLINE_LINUX_DEFAULT=")[-1].strip()
                if req_args:
                    output += " %s" % req_args
                if req_remove_args:
                    for each_arg in req_remove_args.split():
                        output = output.replace(each_arg, "")
            except CommandFailed as Err:
                print(("Failed to get the kernel commandline - %s: %s" %
                       (Err.command, Err.output)))
                return False
            if req_args or req_remove_args:
                try:
                    cmd = "sed -i 's/%s=.*/%s=\"%s\"/g' %s" % (grub_key, grub_key,
                                                               output, boot_cfg)
                    con.run_command(cmd, timeout=60)
                    con.run_command("update-grub")
                except CommandFailed as Err:
                    print(("Failed to update kernel commandline - %s: %s" %
                           (Err.command, Err.output)))
                    return False
        if reboot and (req_args or req_remove_args):
            # Reboot the host for the kernel command to reflect
            self.cv_SYSTEM.goto_state(OpSystemState.OFF)
            self.cv_SYSTEM.goto_state(OpSystemState.OS)

            # check for added/removed args in /proc/cmdline
            req_args, req_remove_args = self.check_kernel_cmdline(args,
                                                                  remove_args)
            if req_args:
                print(("Failed to add arg %s in the cmdline %s" %
                       (args, output)))
                return False
            if req_remove_args:
                print(("Failed to remove arg %s in the cmdline %s" %
                       (remove_args, output)))
                return False
        return True


class ThreadedHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_HEAD(self):
        # FIXME: Local repo unable to handle http request while installation
        # Avoid using cdrom if your kickstart file needs repo, if installation
        # just needs vmlinx and initrd from cdrom, cdrom still can be used.
        if "repo" in self.path:
            self.path = BASE_PATH + self.path
            f = self.send_head()
            if f:
                f.close()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

    def do_GET(self):
        if "repo" in self.path:
            self.path = BASE_PATH + self.path
            f = self.send_head()
            if f:
                try:
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            print(("# Webserver was asked for: ", self.path))
            if self.path == "/%s" % VMLINUX:
                f = open("%s/%s" % (BASE_PATH, VMLINUX), "rb")
                d = f.read()
                self.wfile.write(d)
                f.close()
                return
            elif self.path == "/%s" % INITRD:
                f = open("%s/%s" % (BASE_PATH, INITRD), "rb")
                d = f.read()
                self.wfile.write(d)
                f.close()
                return
            elif self.path == "/%s" % KS:
                f = open("%s/%s" % (BASE_PATH, KS), "rb")
                d = f.read().decode()
                if "hostos" in BASE_PATH:
                    ps = d.format(REPO, PROXY, PASSWORD, DISK, DISK, DISK)
                elif "rhel" in BASE_PATH:
                    ps = d.format(REPO, PROXY, PASSWORD, DISK, DISK, DISK)
                elif "ubuntu" in BASE_PATH:
                    user = USERNAME
                    if user == 'root':
                        user = 'ubuntu'

                    packages = "openssh-server build-essential lvm2 ethtool "
                    packages += "nfs-common ssh ksh lsvpd nfs-kernel-server iprutils procinfo "
                    packages += "sg3-utils lsscsi libaio-dev libtime-hires-perl "
                    packages += "acpid tgt openjdk-8* zip git automake python "
                    packages += "expect gcc g++ gdb "
                    packages += "python-dev p7zip python-stevedore python-setuptools "
                    packages += "libvirt-dev numactl libosinfo-1.0-0 python-pip "
                    packages += "linux-tools-common linux-tools-generic lm-sensors "
                    packages += "ipmitool i2c-tools pciutils opal-prd opal-utils "
                    packages += "device-tree-compiler fwts stress"

                    ps = d.format("openpower", "example.com",
                                  PROXY, PASSWORD, PASSWORD, user, PASSWORD, PASSWORD, DISK, packages)
                else:
                    print("unknown distro")
                self.wfile.write(ps.encode())
                return
            else:
                self.send_response(404)
                return

    def do_POST(self):
        path = os.path.normpath(self.path)
        path = path[1:]
        path_elements = path.split('/')

        print("INCOMING")
        print((repr(path)))
        print((repr(path_elements)))

        if path_elements[0] != "upload":
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST",
                     "CONTENT_TYPE": self.headers['Content-Type']})

        uploaded_files[form["file"].filename] = form["file"].value

        self.wfile.write("Success")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass
