#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestBMC.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015
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
# IBM_PROLOG_END_TAG

'''
OpTestBMC
---------

BMC package which contains all BMC related interfaces/function.

This class encapsulates all function which deals with the BMC in OpenPower
systems
'''

import sys
import time
import pexpect
import os.path
import subprocess

from OpTestIPMI import OpTestIPMI
from OpTestSSH import OpTestSSH
from OpTestUtil import OpTestUtil
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestWeb import OpTestWeb
from Exceptions import CommandFailed, SSHSessionDisconnected

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestBMC():
    '''
    The main object for communicating with a BMC and taking actions with it.
    '''
    def __init__(self, ip=None, username=None, password=None,
                 logfile=sys.stdout, ipmi=None, rest=None,
                 web=None, check_ssh_keys=False, known_hosts_file=None):
        self.cv_bmcIP = ip
        self.cv_bmcUser = username
        self.cv_bmcPasswd = password
        self.cv_IPMI = ipmi
        self.rest = rest
        self.cv_WEB = web
        self.logfile = logfile
        self.check_ssh_keys = check_ssh_keys
        self.known_hosts_file = known_hosts_file
        self.ssh = OpTestSSH(ip, username, password, logfile, prompt=None,
                block_setup_term=0, check_ssh_keys=check_ssh_keys, known_hosts_file=known_hosts_file)
        # OpTestUtil instance is NOT conf's
        self.util = OpTestUtil()

    def set_system(self, system):
        self.ssh.set_system(system)

    def bmc_host(self):
        return self.cv_bmcIP

    def get_ipmi(self):
        '''
        Get an object that can be used to do things over IPMI
        '''
        return self.cv_IPMI

    def get_rest_api(self):
        '''
        OpenBMC specific REST API.
        '''
        return self.rest

    def get_host_console(self):
        return self.cv_IPMI.get_host_console()

    def run_command(self, command, timeout=60, retry=0):
        '''
        Run a command on the BMC itself.
        '''
        return self.ssh.run_command(command, timeout, retry)

    ##
    # @brief 
    #
    # @return BMC_CONST.FW_SUCCESS on success and
    #         raise OpTestError on failure
    #
    def reboot(self):
        '''
        This function issues the reboot command on the BMC console.  It then
        pings the BMC until it responds, which presumably means that it is done
        rebooting.

        :raises: :class:`common.OpTestError`
        '''
        retries = 0
        try:
            self.ssh.run_command('reboot')
        except SSHSessionDisconnected as e:
            pass
        except CommandFailed as e:
            pass
        self.ssh.close()
        log.info('Sent reboot command now waiting for reboot to complete...')
        # Wait for BMC to go down.
        self.util.ping_fail_check(self.cv_bmcIP)
        # Wait for BMC to ping back.
        self.util.PingFunc(self.cv_bmcIP, totalSleepTime=BMC_CONST.PING_RETRY_POWERCYCLE)
        # Ping the system until it reboots
        while True:
            try:
                subprocess.check_call(["ping", self.cv_bmcIP, "-c1"])
                break
            except subprocess.CalledProcessError as e:
                log.debug("Ping return code: ", e.returncode, "retrying...")
                retries += 1
                time.sleep(10)

            if retries > 10:
                l_msg = "Error. BMC is not responding to pings"
                log.error(l_msg)
                raise OpTestError(l_msg)

            log.info('BMC reboot complete.')

        return BMC_CONST.FW_SUCCESS

    def image_transfer(self, i_imageName, copy_as=None):
        '''
        This function copies the given image to the BMC /tmp dir.

        :param i_imageName: Local file to copy across
        :param copy_as: file name to copy to (in /tmp)
        :returns: Exit code of scp or rsync process
        '''
        img_path = i_imageName
        ssh_opts = ' -o PubkeyAuthentication=no '
        if not self.check_ssh_keys:
            ssh_opts = ssh_opts + ' -o StrictHostKeyChecking=no'
        elif self.known_hosts_file:
            ssh_opts = ssh_opts + ' -o UserKnownHostsFile=' + self.known_hosts_file

        rsync_cmd = 'rsync -P -v -e "ssh -k' + ssh_opts + '" %s %s@%s:/tmp' % (img_path, self.cv_bmcUser, self.cv_bmcIP)
        if copy_as:
            rsync_cmd = rsync_cmd + '/' + copy_as

        log.debug(rsync_cmd)
        rsync = pexpect.spawn(rsync_cmd)
        rsync.logfile = OpTestLogger.FileLikeLogger(log)
        r = rsync.expect(['assword: ', 'total size is', 'error while loading shared lib', pexpect.EOF], timeout=1800)
        if r == 0:
            rsync.sendline(self.cv_bmcPasswd)
            r = rsync.expect(['assword: ', 'total size is', 'error while loading shared lib', pexpect.EOF], timeout=1800)

        if r == 2:
            # On AMI BMCs that are missing libacl.so.1 for rsync,
            # we have to fall back to "scp"...
            # which is actually SSH+dd because there's no scp
            # This is notable for Palmetto
            log.debug("Falling back to SCP")
            if copy_as is None:
                copy_as = os.path.basename(img_path)
            scp_cmd = "bash -c \"sshpass -p {} ssh".format(self.cv_bmcPasswd) + ssh_opts + ' -o LogLevel=quiet'
            scp_cmd = scp_cmd + " {}@{} dd of=/tmp/{} < {}\"".format(self.cv_bmcUser, self.cv_bmcIP,copy_as,img_path)
            log.debug(scp_cmd)
            scp = pexpect.spawn(scp_cmd, timeout=120)
            scp.expect(pexpect.EOF)
            scp.wait()
            scp.close()
            chmod_cmd = "sshpass -p {} ssh {} {}@{} chmod +x /tmp/{}".format(self.cv_bmcPasswd, ssh_opts, self.cv_bmcUser, self.cv_bmcIP, copy_as)
            log.debug(chmod_cmd)
            chmod = pexpect.spawn(chmod_cmd)
            chmod.expect(pexpect.EOF)
            chmod.wait()
            chmod.close()
            return scp.exitstatus
        else:
            rsync.expect(pexpect.EOF)
            rsync.close()
            return rsync.exitstatus


    def pnor_img_flash_ami(self, i_pflash_dir, i_imageName):
        '''
        This function flashes the PNOR image using pflash tool,
        And this function will work based on the assumption that pflash
        tool available in i_pflash_dir. Depending on the BMC type (and even
        *version* of BMC firmware) we may have had to copy over pflash
        ourselves.

        :param i_pflash_dir: directory where pflash tool is present.
        :type i_pflash_dir: str
        :param i_imageName: Name of the image file.
                            e.g. `firestone.pnor` or `firestone_update.pnor`
        :type i_imageName: str

        :returns: pflash command return code
        '''
        cmd = i_pflash_dir + '/pflash -e -f -p /tmp/%s' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def pnor_img_flash_openbmc(self, i_imageName):
        '''
        on openbmc systems pflash tool available
        '''
        cmd = 'pflash -E -f -p /tmp/%s' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def skiboot_img_flash_ami(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /tmp/%s -e -f -P PAYLOAD' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def skiroot_img_flash_ami(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /tmp/%s -e -f -P BOOTKERNEL' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def flash_part_ami(self, i_pflash_dir, i_imageName, i_partName):
        cmd = i_pflash_dir + '/pflash -p /tmp/%s -e -f -P %s' % (i_imageName, i_partName)
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def skiboot_img_flash_openbmc(self, i_imageName):
        cmd = 'pflash -p /tmp/%s -e -f -P PAYLOAD' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def skiroot_img_flash_openbmc(self, i_imageName):
        cmd = 'pflash -p /tmp/%s -e -f -P BOOTKERNEL' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def flash_part_openbmc(self, i_imageName, i_partName):
        cmd = 'pflash -p /tmp/%s -e -f -P %s' % (i_imageName, i_partName)
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def validate_pflash_tool(self, i_dir=""):
        '''
        This function validates presence of pflash tool, which will be
        used for pnor image flash

        :param i_dir: directory where pflash tool should be present.
        :returns: True/False
        '''
        i_dir = os.path.join(i_dir, "pflash")
        try:
            l_res = self.ssh.run_command("which %s" % i_dir)
        except CommandFailed:
            l_msg = "# pflash tool is not available on BMC"
            log.error(l_msg)
            return False
        return True

    def has_inband_bootdev(self):
        return True

    def has_os_boot_sensor(self):
        return True

    def has_host_status_sensor(self):
        return True

    def has_occ_active_sensor(self):
        return True

    def supports_ipmi_dcmi(self):
        return True

    def has_ipmi_sel(self):
        return True

class OpTestSMC(OpTestBMC):

    def has_os_boot_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False

    def supports_ipmi_dcmi(self):
        return True

    def image_transfer(self,i_imageName, copy_as=None):

        img_path = i_imageName
        rsync_cmd = 'rsync -av %s rsync://%s/files/' % (img_path, self.cv_bmcIP)
        if copy_as:
            rsync_cmd = rsync_cmd + '/' + copy_as
        log.debug(rsync_cmd)
        rsync = pexpect.spawn(rsync_cmd)
        rsync.logfile = OpTestLogger.FileLikeLogger(log)
        rsync.expect(pexpect.EOF, timeout=300)
        rsync.close()
        return rsync.exitstatus

    def skiboot_img_flash_smc(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /tmp/rsync_file/%s -e -f -P PAYLOAD' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def skiroot_img_flash_smc(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /tmp/rsync_file/%s -e -f -P BOOTKERNEL' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def flash_part_smc(self, i_pflash_dir, i_imageName, i_partName):
        cmd = i_pflash_dir + '/pflash -p /tmp/rsync_file/%s -e -f -P %s' % (i_imageName, i_partName)
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def pnor_img_flash_smc(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -e -f -p /tmp/rsync_file/%s' % i_imageName
        rc = self.ssh.run_command(cmd, timeout=1800)
        return rc

    def validate_pflash_tool(self, i_dir=""):
        i_dir = os.path.join(i_dir, "pflash")
        # Supermicro BMC busybox doesn't have inbuilt which command
        cmd = "ls %s" % i_dir
        try:
            l_res = self.ssh.run_command(cmd)
        except CommandFailed:
            l_msg = "# pflash tool is not available on BMC"
            log.error(l_msg)
            return False
        return True
