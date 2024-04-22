#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
# [+] International Business Machines Corp.
# Author: Tasmiya Nalatwad <tasmiya@linux.vnet.ibm.com>
#
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# IBM_PROLOG_END_TAG

"""
HtxBootme Test

The test case is to run HTX workload and start bootme test.
When the Bootme is set to ON the Lpar goes to reboot everytime after 30 minutes
of time interval. And the reboot cycle continues.
After every reboot the HTX workload must continue without any error.
The cycle continues until the bootme is set to off.
"""

import unittest
import os
import re
import time
import sys
import subprocess
import paramiko
import itertools
from datetime import datetime

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse

import OpTestConfiguration
import OpTestLogger
from common.OpTestSSH import OpTestSSH
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestSOL import OpSOLMonitorThread
from common.OpTestInstallUtil import InstallUtil

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestHtxBootmeIO():
    def setUp(self):
        """
        Setup
        """
        self.conf = OpTestConfiguration.conf
        self.util = OpTestUtil(OpTestConfiguration.conf)
        self.cv_HOST = self.conf.host()
        self.cv_SYSTEM = self.conf.system()
        self.console = self.cv_SYSTEM.console
        self.console_thread = OpSOLMonitorThread(1, "console")
        self.console_thread.start()
        self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
        res = self.con.run_command('uname -a')
        if 'ppc64' not in res[-1]:
            self.fail("Platform does not support HTX tests")

        self.host_password = self.conf.args.host_password
        self.mdt_file = self.conf.args.mdt_file
        self.time_limit = int(self.conf.args.time_limit)
        self.boot_count = int(self.conf.args.boot_count)
        self.htx_rpm_link=self.conf.args.htx_rpm_link
        
        if not self.execute_remote_command('test -e {}'.format(path)):
            log.debug("MDT file %s not found due to config" % self.mdt_file)

        self.host_distro_name = self.util.distro_name()
        self.host_distro_version = self.util.get_distro_version().split(".")[0]

    def install_latest_htx_rpm(self):
        """
        Search for the latest htx-version for the intended distro and
        install the same.
        """
        if not self.current_test_case == "HtxBootme_NicDevices":
            distro_pattern = "%s%s" % (
                self.host_distro_name, self.host_distro_version)
            try:
                temp_string = subprocess.run(
                              "curl --silent %s" % (self.htx_rpm_link),
                              shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=30)
                temp_string = temp_string.stdout.decode('utf-8')
            except subprocess.TimeoutExpired:
                print("Command timed out")
            except Exception as e:
                print(f"An error occurred: {e}")
            matching_htx_versions = re.findall(
                r"(?<=\>)htx\w*[-]\d*[-]\w*[.]\w*[.]\w*", str(temp_string))
            distro_specific_htx_versions = [
                htx_rpm for htx_rpm in matching_htx_versions
                if distro_pattern in htx_rpm]
            distro_specific_htx_versions.sort(reverse=True)
            self.latest_htx_rpm = distro_specific_htx_versions[0]
            cmd_wget = ('wget %s%s --no-check-certificate'
                        % (self.htx_rpm_link,
                           self.latest_htx_rpm))
            cmd_install = ('rpm -ivh %s --force' % self.latest_htx_rpm)
            if "ERROR:" in self.con.run_command(cmd_wget, timeout=180) or "error:" in self.con.run_command(cmd_install, timeout=180):
                self.fail("Installion of rpm failed")

    def setup_htx(self):
        """
        Builds HTX
        """
        packages = ['git', 'gcc', 'make', 'wget']
        if self.host_distro_name in ['centos', 'fedora', 'rhel', 'redhat']:
            packages.extend(['gcc-c++', 'ncurses-devel', 'tar'])
        elif self.host_distro_name == "Ubuntu":
            packages.extend(['libncurses5', 'g++', 'ncurses-dev',
                             'libncurses-dev', 'tar', 'wget'])
        elif self.host_distro_name == 'SuSE':
            packages.extend(['libncurses6', 'gcc-c++',
                            'ncurses-devel', 'tar', 'wget'])
        else:
            self.fail("Test not supported in  %s" % self.host_distro_name)
        if self.host_distro_name == 'rhel':
            self.installer = "yum install"
        elif self.host_distro_name == 'sles':
            self.installer = "zypper install"
        log.debug("Installing packages")
        for pkg in packages:
            self.con.run_command("%s %s -y" % (self.installer, pkg))

        ins_htx = self.con.run_command_ignore_fail('rpm -qa | grep htx')
        if ins_htx:
            for rpm in ins_htx:
                self.con.run_command_ignore_fail("rpm -e %s" % rpm, timeout=30)
                log.debug("Deleted old htx rpm package from host")
                if self.execute_remote_command('test -e {}'.format('/usr/lpp/htx')):
                    if not self.execute_remote_command('rm -rf {}'.format('/usr/lpp/htx')):
                        self.fail("Failed to delete the file at /usr/lpp/htx")
        if self.current_test_case == "HtxBootme_NicDevices":
            peer_ins_htx = self.ssh.run_command_ignore_fail('rpm -qa | grep htx')
            if peer_ins_htx:
                for rpm in peer_ins_htx:
                    self.ssh.run_command_ignore_fail(('rpm -e %s' % rpm), timeout=180)
                    log.debug("Deleted old htx rpm package from peer")
        self.install_latest_htx_rpm()

    def runTest(self):
        """
        Execute 'HTX' with appropriate parameters.
        """
        self.setup_htx()
        self.start_htx_run()
        self.htx_check()
        self.htx_bootme_test()
        self.stop_htx_bootme()
        self.htx_stop()
        self.teardown()

    def start_htx_run(self):
        """
        Starting htx test.
        """
        if not self.current_test_case == "HtxBootme_NicDevices":
            log.debug("Creating the HTX mdt files")
            self.con.run_command('htxcmdline -createmdt')

    def htx_check(self):
        """
        Checks if HTX is running, and if no errors.
        """
        log.debug("HTX Error logs")
        file_size = self.check_remote_file_size_command('wc -c {}'.format("/tmp/htx/htxerr"))
        file_size = int(file_size.split()[0])
        if file_size != 0:
            self.fail("check errorlogs for exact error and failure")
        cmd = 'htxcmdline -query  -mdt %s' % self.mdt_file
        res = self.con.run_command(cmd)
        time.sleep(60)

    def htx_bootme_test(self):
        """
        Starting bootme on htx.
        """
        log.debug("Running bootme command on htx")
        self.con.run_command('htxcmdline -bootme on')

        total_wait_time = 1800
        for i in itertools.count():
            if not self.is_system_online():
                break

        for i in range(self.boot_count):
            start_time = time.time()
            if not self.wait_for_reboot_completion(self.cv_HOST.ip):
                log.debug("Failed to confirm system reboot within the timeout period. Check the system manually.")
                break
            time.sleep(15)
            self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            time.sleep(10)
            for j in range(5):
                cmd = 'htxcmdline -query  -mdt %s' % self.mdt_file
                res = self.con.run_command_ignore_fail(cmd, timeout=60)
                if ("/usr/lpp/htx/mdt/") in res[2]:
                    break
                else:
                    time.sleep(10)
                    log.debug("Mdt start is still in progress")
            self.con.run_command(cmd)
            htxerr_file = self.check_remote_file_size_command('wc -c {}'.format("/tmp/htx/htxerr"))
            if int(htxerr_file.split()[0]) != 0:
                self.fail("check error logs for exact error and failure")
            log.info("Reboot cycle %s completed successfully" % (i+1))
            reboot_time = time.time() - start_time
            remaining_wait_time = total_wait_time - reboot_time
            if remaining_wait_time > 0 and i < (self.boot_count-1):
                log.info("Waiting for next reboot cycle")
                time.sleep(remaining_wait_time)
        log.info("Htx Bootme test is completed")

    def is_system_online(self):
        """
        This function pings to the host ip and checks system's availability.
        
        :return: True if the system is pinging.
                 False if system is not pinging.
        """
        cmd = ["ping", "-c 2", self.cv_HOST.ip]
        i_try = 3
        while(i_try != 0):
            ping = subprocess.Popen(cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    universal_newlines=True,
                                    encoding='utf-8')
            stdout_value, stderr_value = ping.communicate()
            if(stdout_value.__contains__("2 received")):
                return True
            else:
                time.sleep(2)
                i_try -= 1
        return False

    def check_remote_file_size_command(self, command):
        """
        Creates a new SSH client connection, executes a command,
        and then closes the connection.

        :param command: Command to execute on the remote machine.
        :return: Command output as a string. 
                 or Returns Execption error msg if there was an error.
        """
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.cv_HOST.ip, 22, self.cv_HOST.user, self.host_password)
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode().strip()
            client.close()
            return output
        except Exception as e:
            print(f"An error occurred: {e}")
            return e

    def wait_for_reboot_completion(self, ip_addr, timeout=500):
        """
        Wait for the system to become available after reboot.
        """
        interval=30
        time.sleep(interval)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_system_online():
                print("System is back online!")
                return True
            time.sleep(interval)
        return False

    def stop_htx_bootme(self):
        """
        Stopping the htx bootme
        """
        res = self.con.run_command('htxcmdline -bootme off')
        if "bootme off is completed successfully" not in res[4]:
            if "bootme is already off" not in res[4]:
                self.fail("Fail to off htx bootme")

    def htx_stop(self):
        """
        Shutdown the mdt file and the htx daemon and set SMT to original value
        Stop the HTX Run
        """
        if self.current_test_case == "HtxBootme_BlockDevice":
            if self.is_block_device_active() is True:
                log.debug("suspending active block_devices")
                self.suspend_all_block_device()

        log.debug("shutting down the %s ", self.mdt_file)
        cmd_shutdown = 'htxcmdline -shutdown -mdt %s' % self.mdt_file
        self.con.run_command(cmd_shutdown)

        cmd = '/usr/lpp/htx/etc/scripts/htx.d status'
        daemon_state = self.con.run_command(cmd)
        if 'running' in daemon_state[-1]:
            self.con.run_command('/usr/lpp/htx/etc/scripts/htxd_shutdown')

        if self.current_test_case == "HtxBootme_NicDevices":
            log.debug("shutting down the %s on peer", self.mdt_file)
            self.ssh.run_command(cmd_shutdown)
            self.ip_restore_host()
            self.ip_restore_peer()

    def teardown(self):
        """
        close the session to the console
        """
        self.console_thread.console_terminate()

class HtxBootme_AllMdt(OpTestHtxBootmeIO, unittest.TestCase):
    """
    This Test case is to test Htx bootme on all mdt files mdt.all
    """

    def setUp(self):
        super(HtxBootme_AllMdt, self).setUp()

        self.current_test_case="HtxBootme_AllMdt"
        self.time_unit = self.conf.args.time_unit
        if self.time_unit == 'm':
            self.time_limit = self.time_limit * 60
        elif self.time_unit == 'h':
            self.time_limit = self.time_limit * 3600
        else:
            self.fail(
                "running time unit is not proper, please pass as 'm' or 'h' ")

    def start_htx_run(self):
        super(HtxBootme_AllMdt, self).start_htx_run()

        log.debug("selecting the mdt file")
        cmd = "htxcmdline -select -mdt %s" % self.mdt_file
        self.con.run_command(cmd, timeout=30)

        log.debug("Activating the %s", self.mdt_file)
        cmd = "htxcmdline -activate -mdt %s" % self.mdt_file
        self.con.run_command(cmd)

        log.debug("Running the HTX ")
        cmd = "htxcmdline -run  -mdt %s" % self.mdt_file
        self.con.run_command(cmd)

class HtxBootme_BlockDevice(OpTestHtxBootmeIO, unittest.TestCase):
    """
    The Test case is to run Htx on BLock Devices mdt.hd
    """
    def setUp(self):
        super(HtxBootme_BlockDevice, self).setUp()

        self.current_test_case="HtxBootme_BlockDevice"
        self.mdt_file = self.conf.args.mdt_file
        self.block_devices = self.conf.args.htx_disks
        self.all = self.conf.args.all

        if not self.all and self.block_devices is None:
            self.fail("Needs the block devices to run the HTX")
        if self.all:
            self.block_device = ""
        else:
            self.block_device = []
            for dev in self.block_devices.split():
                dev_path = self.get_absolute_disk_path(dev)
                dev_base = self.execute_remote_command('basename $(realpath {})'.format(dev_path))
                if 'dm' in dev_base:
                    dev_base = self.get_mpath_from_dm(dev_base)
                self.block_device.append(dev_base)
            self.block_device = " ".join(self.block_device)

    def start_htx_run(self):
        super(HtxBootme_BlockDevice, self).start_htx_run()

        path = "/usr/lpp/htx/mdt/%s" % self.mdt_file
        if self.execute_remote_command('test -e {}'.format(path)):
            self.fail(f"MDT file {self.mdt_file} not found")

        log.debug("selecting the mdt file ")
        cmd = f"htxcmdline -select -mdt {self.mdt_file}"
        self.con.run_command(cmd)

        if not self.all:
            if self.is_block_device_in_mdt() is False:
                self.fail(f"Block devices {self.block_device} are not available"
                          f"in {self.mdt_file}")

        self.suspend_all_block_device()

        log.debug(f"Activating the {self.block_device}")
        cmd = f"htxcmdline -activate {self.block_device} -mdt {self.mdt_file}"
        self.con.run_command(cmd)
        if not self.all:
            if self.is_block_device_active() is False:
                self.fail("Block devices failed to activate")

        log.debug(f"Running the HTX on {self.block_device}")
        cmd = f"htxcmdline -run -mdt {self.mdt_file}"
        self.con.run_command(cmd)

    def is_block_device_in_mdt(self):
        """
        verifies the presence of given block devices in selected mdt file
        """
        log.debug(
            f"checking if the given block_devices are present in {self.mdt_file}")
        cmd = f"htxcmdline -query -mdt {self.mdt_file}"
        output = self.con.run_command(cmd)
        device = []
        for dev in self.block_device.split(" "):
            if dev not in output:
                device.append(dev)
        if device:
            log.debug(
                f"block_devices {device} are not avalable in {self.mdt_file} ")
        log.debug(
            f"BLOCK DEVICES {self.block_device} ARE AVAILABLE {self.mdt_file}")
        return True

    def suspend_all_block_device(self):
        """
        Suspend the Block devices, if active.
        """
        log.debug("suspending block_devices if any running")
        cmd = f"htxcmdline -suspend all  -mdt {self.mdt_file}"
        self.con.run_command(cmd)

    def is_block_device_active(self):
        """
        Verifies whether the block devices are active or not
        """
        log.debug("checking whether all block_devices are active ot not")
        cmd = f"htxcmdline -query {self.block_device} -mdt {self.mdt_file}"
        output = self.con.run_command(cmd)
        device_list = self.block_device.split(" ")
        active_devices = []
        for line in output:
            for dev in device_list:
                if dev in line and "ACTIVE" in line:
                    active_devices.append(dev)
        non_active_device = list(set(device_list) - set(active_devices))
        if non_active_device:
            return False
        log.debug(f"BLOCK DEVICES {self.block_device} ARE ACTIVE")
        return True

    def get_mpath_from_dm(self, dm_id):
        """
        Get the mpath name for given device mapper id

        :param dev_mapper: Input device mapper dm-x
        :return: mpath name like mpathx
        :rtype: str
        """
        cmd = "multipathd show maps format '%d %n'"
        try:
            mpaths = self.con.run_command(cmd)
        except process.CmdError as ex:
            raise MPException(f"Multipathd Command Failed : {ex} ")
        for mpath in mpaths:
            if dm_id in mpath:
                return mpath.split()[1]

    def get_all_disk_paths(self):
        """
        Returns all available disk names and alias on this  system

        This will get all the sysfs disks name entries by its device
        node name, by-uuid, by-id and by-path, irrespective of any
        platform and device type

        :returns: a list of all disk path names
        :rtype: list of str
        """
        disk_list = abs_path = []
        for path in [
            "/dev",
            "/dev/mapper",
            "/dev/disk/by-id",
            "/dev/disk/by-path",
            "/dev/disk/by-uuid",
            "/dev/disk/by-partuuid",
            "/dev/disk/by-partlabel",
        ]:
            if self.execute_remote_command('test -e {}'.format(path)):
                directory = self.execute_remote_command('ls -l {}'.format(path))
                for device in directory:
                    abs_path.append(path +  '/' + device)
                disk_list.extend(abs_path)
        return disk_list

    def get_absolute_disk_path(self, device):
        """
        Returns absolute device path of given disk

        This will get actual disks path of given device, it can take
        node name, by-uuid, by-id and by-path, irrespective of any
        platform and device type

        :param device: disk name or disk alias names sda or scsi-xxx
        :type device: str

        :returns: the device absolute path name
        :rtype: bool
        """
        if not self.execute_remote_command('test -e {}'.format(device)):
            for dev_path in self.get_all_disk_paths():
                dev_base = self.execute_remote_command('basename $(realpath {})'.format(dev_path))
                if device == dev_base:
                    return dev_path
        return device

class HtxBootme_NicDevices(OpTestHtxBootmeIO, unittest.TestCase):
    """
    The Test case is to run htx bootme on Network device net.mdt
    """
    def setUp(self):
        super(HtxBootme_NicDevices, self).setUp()

        self.current_test_case="HtxBootme_NicDevices"
        self.host_intfs = []
        self.peer_ip = self.conf.args.peer_public_ip
        self.peer_user = self.conf.args.peer_user
        self.peer_password = self.conf.args.peer_password
        devices = self.conf.args.htx_host_interfaces
        if devices:
            interfaces = self.execute_remote_command('ls /sys/class/net')
        for device in devices.split(" "):
            if device in interfaces:
                self.host_intfs.append(device)
            else:
                self.fail("Please check the network device")
        self.peer_intfs = self.conf.args.peer_interfaces.split(" ")
        self.mdt_file = self.conf.args.mdt_file
        self.query_cmd = "htxcmdline -query -mdt %s" % self.mdt_file

        self.ssh = OpTestSSH(self.peer_ip, self.peer_user, self.peer_password)
        self.ssh.set_system(self.conf.system())

        # Flush out the ip addresses on host and peer before starting the test
        self.ip_restore_host()
        self.ip_restore_peer()

        # Get distro details of peer lpar
        self.get_peer_distro()
        self.get_peer_distro_version()

    def get_peer_distro(self):
        """
        Get the distro name that is installed on peer lpar
        """
        res = self.ssh.run_command("cat /etc/os-release")
        if "Ubuntu" in res[0] or "Ubuntu" in res[1]:
            self.peer_distro = "ubuntu"
        elif 'Red Hat' in res[0] or 'Red Hat' in res[1]:
            self.peer_distro = "rhel"
        elif 'SLES' in res[0] or 'SLES' in res[1]:
            self.peer_distro = "sles"
        else:
            self.peer_distro = "unknown"

    def get_peer_distro_version(self):
        """
        Get the distro version that is installed on peer lpar
        """
        res = self.ssh.run_command("cat /etc/os-release")
        for line in res:
            if 'VERSION_ID' in line:
                self.peer_distro_version = line.split('=')[1].strip('"').split('.')[0]

    def update_host_peer_names(self):
        """Update hostname & IP of both Host & Peer in /etc/hosts on both machines."""

        res = self.ssh_host.run_command("nslookup %s" % self.host_ip)
        self.host_name = re.search(r'name = (.+)\.', res[0]).group(1)
        res = self.ssh.run_command("nslookup %s" % self.peer_ip)
        self.peer_name = re.search(r'name = (.+)\.', res[0]).group(1)

        self.hosts_file = "/etc/hosts"

        log.info("Updating hostname of both Host & Peer in %s file", self.hosts_file)

        self.delete_unwanted_entries()

        # Update for Host
        existing_entries_host = set(self.ssh_host.run_command(f"cat {self.hosts_file}"))
        for ip, name in [(self.host_ip, self.host_name)]:
            line = f"{ip} {name}"
            if line not in existing_entries_host:
                log.info("Adding missing entry on Host: %s", line)
                self.ssh_host.run_command(f'echo "{line}" | sudo tee -a {self.hosts_file}')
            else:
                log.info("Entry exists on Host: %s", line)
        
        # Update for Peer
        existing_entries_peer = set(self.ssh.run_command(f"cat {self.hosts_file}"))
        for ip, name in [(self.peer_ip, self.peer_name)]:
            line = f"{ip} {name}"
            if line not in existing_entries_peer:
                log.info("Adding missing entry on Peer: %s", line)
                self.ssh.run_command(f'echo "{line}" | sudo tee -a {self.hosts_file}')
            else:
                log.info("Entry exists on Peer: %s", line)

    def delete_unwanted_entries(self):
        """Deletes entries from /etc/hosts that match 'netXX.XX' pattern based on host and peer IPs."""
        host_last_two = ".".join(self.host_ip.split(".")[-2:])
        peer_last_two = ".".join(self.peer_ip.split(".")[-2:])

        pattern_host = rf"net{host_last_two}"
        pattern_peer = rf"net{peer_last_two}"

        sed_command = f"sudo sed -i.bak -E '/{pattern_host}/d; /{pattern_peer}/d' {self.hosts_file}"

        # Run on host
        log.debug("Running on Host: %s" % sed_command)
        self.ssh_host.run_command(sed_command)

        # Run on peer
        log.debug("Running on Peer: %s" %sed_command)
        self.ssh.run_command(sed_command)

        log.info("Deletion complete.") 
       
    def htx_configure_net(self):
        """
        The function is to setup network topology for htx run
        on both host and peer.
        The build_net multisystem <hostname/IP> command
        configures the netwrok interfaces on both host and peer Lpars with
        some random net_ids and check pingum and also
        starts the htx deamon for net.mdt
        There is no need to explicitly start the htx deamon, create/select
        and activate for net.mdt
        """
        log.debug("Setting up the Network configuration on Host and Peer")

        cmd = "build_net multisystem %s" % self.peer_ip

        # try up to 3 times if the command fails to set the network interfaces
        for i in range(3):
            output = self.con.run_command(cmd, timeout=180)
            if "All networks ping Ok" in output:
                log.debug("Htx configuration was successful on host and peer")
                break
        output = self.con.run_command('pingum')
        if "All networks ping Ok" not in output:
            self.fail("Failed to set htx configuration on host and peer")

    def start_htx_run(self):
        super(HtxBootme_NicDevices, self).start_htx_run()

        self.htx_configure_net()
        log.debug("Running the HTX for %s on Host", self.mdt_file)
        cmd = "htxcmdline -run -mdt %s" % self.mdt_file
        self.con.run_command(cmd)

        log.debug("Running the HTX for %s on Peer", self.mdt_file)
        self.ssh.run_command(cmd)

    def install_latest_htx_rpm(self):
        super(HtxBootme_NicDevices, self).install_latest_htx_rpm()

        if self.host_distro_name == "SuSE":
            self.host_distro_name = "sles"
        elif self.peer_distro == "SuSE":
            self.peer_distro = "sles"
        host_distro_pattern = "%s%s" % (
                                        self.host_distro_name,
                                        self.host_distro_version)
        peer_distro_pattern = "%s%s" % (
                                        self.peer_distro,
                                        self.peer_distro_version)
        patterns = [host_distro_pattern, peer_distro_pattern]
        for pattern in patterns:
            temp_string = subprocess.run(
                          "curl --silent %s" % (self.htx_rpm_link),
                          shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=30)
            matching_htx_versions = re.findall(
                r"(?<=\>)htx\w*[-]\d*[-]\w*[.]\w*[.]\w*", str(temp_string))
            distro_specific_htx_versions = [htx_rpm
                                            for htx_rpm
                                            in matching_htx_versions
                                            if pattern in htx_rpm]
            distro_specific_htx_versions.sort(reverse=True)
            self.latest_htx_rpm = distro_specific_htx_versions[0]

            cmd_wget = ('wget %s%s --no-check-certificate'
                        % (self.htx_rpm_link,
                           self.latest_htx_rpm))
            cmd_install = ('rpm -ivh %s --force' % self.latest_htx_rpm)
            if host_distro_pattern == peer_distro_pattern:
                if "ERROR:" in self.con.run_command(cmd_wget, timeout=180) or "error:" in self.con.run_command(cmd_install, timeout=180):
                    self.fail("Installion of rpm failed")
                if "ERROR:" in self.ssh.run_command(cmd_wget, timeout=180) or "error:" in self.ssh.run_command(cmd_install, timeout=180):
                    self.fail("Unable to install the package %s %s"
                              " on peer machine" % (self.htx_rpm_link,
                                                    self.latest_htx_rpm))
                break

            if pattern == host_distro_pattern:
                if "ERROR:" in self.con.run_command(cmd_wget, timeout=180) or "error:" in self.con.run_command(cmd_install, timeout=180):
                    self.fail("Installion of rpm failed")

            if pattern == peer_distro_pattern:
                if "ERROR:" in self.ssh.run_command(cmd_wget, timeout=180) or "error:" in self.ssh.run_command(cmd_install, timeout=180):
                    self.fail("Unable to install the package %s %s"
                              " on peer machine" % (self.htx_rpm_link,
                                                    self.latest_htx_rpm))

    def ip_restore_host(self):
        '''
        restoring ip for host
        '''
        for interface in self.host_intfs:
            cmd = "ip addr flush %s" % interface
            self.con.run_command(cmd)
            cmd = "ip link set dev %s up" % interface
            self.con.run_command(cmd)

    def ip_restore_peer(self):
        '''
        config ip for peer
        '''
        for interface in self.peer_intfs:
            cmd = "ip addr flush %s" % interface
            self.ssh.run_command(cmd)
            cmd = "ip link set dev %s up" % interface
            self.ssh.run_command(cmd)

