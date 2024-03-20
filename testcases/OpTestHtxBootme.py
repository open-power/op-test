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

            if "error:" in self.con.run_command('rpm -ivh --nodeps %s%s '
                              '--force' % (self.htx_rpm_link, self.latest_htx_rpm
                              ), timeout=180):
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
            self.fail("Test not supported in  %s" % host_distro_name)
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
            self.con = self.cv_SYSTEM.cv_HOST.get_ssh_connection()
            time.sleep(10)
            for j in range(5):
                cmd = 'htxcmdline -query  -mdt %s' % self.mdt_file
                res = self.con.run_command_ignore_fail(cmd, timeout=60)
                if ("/usr/lpp/htx/mdt/mdt.all") in res[2]:
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
        cmd = 'htxcmdline -shutdown -mdt %s' % self.mdt_file
        self.con.run_command(cmd)

        cmd = '/usr/lpp/htx/etc/scripts/htx.d status'
        daemon_state = self.con.run_command(cmd)
        if 'running' in daemon_state[-1]:
            self.con.run_command('/usr/lpp/htx/etc/scripts/htxd_shutdown')

        if self.current_test_case == "HtxBootme_NicDevices":
            self.ip_restore_host()
            self.ip_restore_peer()

    def teardown(self):
        """
        close the session to the console
        """
        if self.console_thread.isAlive():
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
