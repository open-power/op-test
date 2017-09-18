#!/usr/bin/python
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

## @package OpTestBMC
#  BMC package which contains all BMC related interfaces/function
#
#  This class encapsulates all function which deals with the BMC in OpenPower
#  systems

import sys
import time
import pexpect
import os.path
try:
    import pxssh
except ImportError:
    from pexpect import pxssh
import subprocess
from OpTestIPMI import OpTestIPMI
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestWeb import OpTestWeb
from Exceptions import CommandFailed

class SSHConnectionState():
    DISCONNECTED = 0
    CONNECTED = 1

class OpTestBMC():
    def __init__(self, ip=None, username=None, password=None, i_ffdcDir=None, ipmi=None, rest=None, web=None, bmctype=None):
        self.cv_bmcIP = ip
        self.cv_bmcUser = username
        self.cv_bmcPasswd = password
        self.cv_ffdcDir = i_ffdcDir
        self.cv_IPMI = ipmi
        self.rest = rest
        self.cv_WEB = web
        self.bmctype = bmctype
        self.state = SSHConnectionState.DISCONNECTED

    def bmc_host(self):
        return self.cv_bmcIP

    def get_ipmi(self):
        return self.cv_IPMI

    def get_rest_api(self):
        return self.rest

    def get_host_console(self):
        return self.cv_IPMI.get_host_console()

    def new_pxssh(self):
        # pxssh has a nice 'echo=False' mode, but only
        # on more recent distros, so we can't use it :(
        p = pxssh.pxssh()
        # Work-around for old pxssh not having options= parameter
        p.SSH_OPTS = p.SSH_OPTS + " -o 'StrictHostKeyChecking=no'"
        p.SSH_OPTS = p.SSH_OPTS + " -o 'UserKnownHostsFile /dev/null' "
        p.force_password = True
        p.logfile = sys.stdout
        p.PROMPT = '# '
        self.pxssh = p
        return p

    def terminate(self):
        if self.state == SSHConnectionState.CONNECTED:
            self.pxssh.terminate()
            self.state = SSHConnectionState.DISCONNECTED

    def connect(self):
        if self.state == SSHConnectionState.CONNECTED:
            self.pxssh.terminate()
            self.state = SSHConnectionState.DISCONNECTED

        print "#SSH CONNECT"
        p = self.new_pxssh()
        p.login(self.cv_bmcIP, self.cv_bmcUser, self.cv_bmcPasswd, auto_prompt_reset=False)
        p.sendline()
        p.prompt(timeout=60)
        p.sendcontrol('l')
        p.expect(r'.+#')
        p.sendline('PS1=[PEXPECT]\#')
        p.expect("\n") # from us, because echo
        l_rc = p.expect("\[PEXPECT\]#$")
        if l_rc == 0:
            print "Shell prompt changed"
        else:
            raise Exception("Failed during change of shell prompt")
        self.state = SSHConnectionState.CONNECTED


    def get_console(self):
        if self.state == SSHConnectionState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.pxssh.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(2)
            self.connect()
            count += 1
            if count > 120:
                raise Exception("Cannot login via SSH")

        return self.pxssh

    def run_command(self, command, timeout=300):
        c = self.get_console()
        c.sendline(command)
        c.expect("\n") # from us
        c.expect("\[PEXPECT\]#$", timeout=timeout)
        output = c.before.splitlines()
        c.sendline("echo $?")
        c.expect("\[PEXPECT\]#$", timeout=timeout)
        exitcode = int(''.join(c.before.splitlines()[1:]))
        if exitcode != 0:
            raise CommandFailed(command, output, exitcode)
        return output

    # This command just runs and returns the ouput & ignores the failure
    def run_command_ignore_fail(self, command, timeout=60):
        try:
            output = self.run_command(command, timeout)
        except CommandFailed as cf:
            output = cf.output
        return output


    ##
    # @brief This function issues the reboot command on the BMC console.  It then
    #    pings the BMC until it responds, which presumably means that it is done
    #    rebooting.  It returns the number of failed pings.  The caller should make
    #    returned value is greater than 1
    #
    # @return BMC_CONST.FW_SUCCESS on success and
    #         raise OpTestError on failure
    #
    def reboot(self):

        retries = 0
        try:
            self.run_command('reboot')
        except pexpect.EOF:
            pass
        print 'Sent reboot command now waiting for reboot to complete...'
        time.sleep(10)
        '''  Ping the system until it reboots  '''
        while True:
            try:
                subprocess.check_call(["ping", self.cv_bmcIP, "-c1"])
                break
            except subprocess.CalledProcessError as e:
                print "Ping return code: ", e.returncode, "retrying..."
                retries += 1
                time.sleep(10)

            if retries > 10:
                l_msg = "Error. BMC is not responding to pings"
                print l_msg
                raise OpTestError(l_msg)

        print 'BMC reboot complete.'

        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function copies the given image to the BMC dest dir(default=/tmp)
    #
    # @return the rsync command return code
    #
    def image_transfer(self,i_imageName, copy_as=None, to_dir="/tmp"):

        img_path = i_imageName
        if self.bmctype == "AMI":
            if self.cv_IPMI.is_supermicro():
                rsync_cmd = "rsync -av %s rsync://%s%s/" % (img_path, self.cv_bmcIP, to_dir)
                if copy_as:
                    rsync_cmd = rsync_cmd + '/' + copy_as
                print rsync_cmd
                rsync = pexpect.spawn(rsync_cmd)
                rsync.logfile = sys.stdout
                rsync.expect(pexpect.EOF, timeout=300)
                rsync.close()
                return rsync.exitstatus
        rsync_cmd = 'rsync -P -v -e "ssh -k -o StrictHostKeyChecking=no" %s %s@%s:%s' % (img_path, self.cv_bmcUser, self.cv_bmcIP, to_dir)
        if copy_as:
            rsync_cmd = rsync_cmd + '/' + copy_as

        print rsync_cmd
        rsync = pexpect.spawn(rsync_cmd)
        rsync.logfile = sys.stdout
        rsync.expect('assword: ')
        rsync.sendline(self.cv_bmcPasswd)
        rsync.expect('total size is', timeout=1800)
        rsync.expect(pexpect.EOF)
        rsync.close()
        return rsync.exitstatus


    ##
    # @brief This function flashes the PNOR image using pflash tool,
    #        And this function will work based on the assumption that pflash
    #        tool available in i_pflash_dir.(user need to mount pflash tool
    #        as pflash tool removed from BMC)
    #
    # @param i_pflash_dir @type string: directory where pflash tool is present.
    # @param i_imageName @type string: Name of the image file
    #                         Ex: firestone.pnor or firestone_update.pnor
    #        Ex:/tmp/pflash -e -f -p /tmp/firestone_update.pnor
    #           /tmp/pflash -e -f -p /tmp/firestone.pnor
    #
    #       Note: -E removed, it will erase entire pnor chip irrespective of
    #             type of image( *.pnor or *_update.pnor).
    #             -e will erase flash area only based on the type of image.
    #
    # @return pflash command return code
    #
    def pnor_img_flash_ami(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -e -f -p /tmp/%s' % i_imageName
        rc = self.run_command(cmd, timeout=1800)
        return rc

    # on openbmc systems pflash tool available
    def pnor_img_flash_openbmc(self, i_imageName):
        cmd = 'pflash -E -f -p /tmp/%s' % i_imageName
        rc = self.run_command(cmd, timeout=1800)
        return rc

    def skiboot_img_flash_ami(self, i_pflash_dir, i_payload_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /%s/%s -e -f -P PAYLOAD' % (i_payload_dir, i_imageName)
        rc = self.run_command(cmd, timeout=1800)
        return rc

    def skiroot_img_flash_ami(self, i_pflash_dir, i_bootkernel_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -p /%s/%s -e -f -P BOOTKERNEL' % (i_bootkernel_dir, i_imageName)
        rc = self.run_command(cmd, timeout=1800)
        return rc

    def skiboot_img_flash_openbmc(self, i_imageName):
        cmd = 'pflash -p /tmp/%s -e -f -P PAYLOAD' % i_imageName
        rc = self.run_command(cmd, timeout=1800)
        return rc

    def skiroot_img_flash_openbmc(self, i_imageName):
        cmd = 'pflash -p /tmp/%s -e -f -P BOOTKERNEL' % i_imageName
        rc = self.run_command(cmd, timeout=1800)
        return rc

    ##
    # @brief This function validates presence of pflash tool, which will be
    #        used for pnor image flash
    #
    # @param i_dir @type string: directory where pflash tool should be present.
    #
    # @return BMC_CONST.FW_SUCCESS if pflash tool is available or raise OpTestError
    #
    def validate_pflash_tool(self, i_dir=""):
        i_dir = os.path.join(i_dir, "pflash")
        cmd = "which %s" % i_dir
        # Supermicro BMC busybox doesn't have inbuilt which command
        if self.bmctype == "AMI" and self.cv_IPMI.is_supermicro():
            cmd = "ls %s" % i_dir
        try:
            l_res = self.run_command(cmd)
        except CommandFailed:
            l_msg = "# pflash tool is not available on BMC"
            print l_msg
            return False
        return True
