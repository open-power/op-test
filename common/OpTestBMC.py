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
try:
    import pxssh
except ImportError:
    from pexpect import pxssh
import subprocess
from OpTestIPMI import OpTestIPMI
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestWeb import OpTestWeb

class OpTestBMC():
    def __init__(self, ip=None, username=None, password=None, i_ffdcDir=None, ipmi=None, web=None):
        self.cv_bmcIP = ip
        self.cv_bmcUser = username
        self.cv_bmcPasswd = password
        self.cv_ffdcDir = i_ffdcDir
        self.cv_IPMI = ipmi
        self.cv_WEB = web


    def bmc_host(self):
        return self.cv_bmcIP

    ##
    # @brief This function runs a command on the BMC
    #
    # @param logFile: File where the command output will be written.
    #        All command output files are placed in the FFDC directory as configured
    #        in the config file.
    # @param timeout @type int: Command timeout in seconds. If not specified, the
    #        default timeout value is 60 seconds.
    #
    # @return int -- the return code, 0: success,
    #                or raises: OpTestError
    #
    def _cmd_run(self, cmdStr, timeout=60, logFile=None):

        ''' Add -k to the SSH options '''
        hostname = self.cv_bmcIP + " -k"

        try:
            p = pxssh.pxssh()

            # Work-around for old pxssh not having options= parameter
            p.SSH_OPTS = p.SSH_OPTS + " -o 'StrictHostKeyChecking=no'"
            p.SSH_OPTS = p.SSH_OPTS + " -o 'UserKnownHostsFile /dev/null' "
            p.force_password = True

            p.logfile = sys.stdout
            p.PROMPT = '# '

            ''' login but do not try to change the prompt since the AMI bmc
                busybox does support it '''

            # http://superuser.com/questions/839878/how-to-solve-python-bug-without-root-permission
            p.login(hostname, self.cv_bmcUser, self.cv_bmcPasswd, login_timeout=timeout, auto_prompt_reset=False)
            p.sendline()
            p.prompt(timeout=60)
            print 'At BMC %s prompt...' % self.cv_bmcIP

            p.sendline(cmdStr)
            p.prompt(timeout=timeout)

            ''' if optional argument is set, save command output to file '''

            if logFile is not None and self.cv_ffdcDir is not None:
                fn = self.cv_ffdcDir + "/" + logFile
                with open(fn, 'w') as f:
                    f.write(p.before)

            p.sendline('echo $?')
            index = p.expect(['0', '1', pexpect.TIMEOUT])
        except IOError as hell:
            raise hell

        if index == 0:
            rc = 0
        elif index == 1:
            l_msg = "Command not on BMC or failed"
            print l_msg
            raise OpTestError(l_msg)
        elif index == 2:
            l_msg = 'Non-zero return code detected, command failed'
            print l_msg
            raise OpTestError(l_msg)
            #rc = p.before

        return rc

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
        self._cmd_run('reboot', logFile='bmc_reboot.log')
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
    # @brief This function copies the PNOR image to the BMC /tmp dir
    #
    # @return the rsync command return code
    #
    def pnor_img_transfer(self,i_imageDir,i_imageName):

        pnor_path = i_imageDir + i_imageName
        rsync_cmd = 'rsync -v -e "ssh -k" %s %s@%s:/tmp' % (pnor_path,
                                                            self.cv_bmcUser,
                                                            self.cv_bmcIP)

        print rsync_cmd
        rsync = pexpect.spawn(rsync_cmd)
        rsync.logfile = sys.stdout
        rsync.expect('assword: ')
        rsync.sendline(self.cv_bmcPasswd)
        rsync.expect('total size is', timeout=150)
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
    def pnor_img_flash(self, i_pflash_dir, i_imageName):
        cmd = i_pflash_dir + '/pflash -e -f -p /tmp/%s' % i_imageName
        rc = self._cmd_run(cmd, timeout=1800, logFile='pflash.log')
        return rc

    ##
    # @brief This function validates presence of pflash tool, which will be
    #        used for pnor image flash
    #
    # @param i_dir @type string: directory where pflash tool should be present.
    #
    # @return BMC_CONST.FW_SUCCESS if pflash tool is available or raise OpTestError
    #
    def validate_pflash_tool(self, i_dir):
        l_cmd = "which " + i_dir + "/pflash"
        try:
            l_res = self._cmd_run(l_cmd)
        except OpTestError:
            l_msg = "Either pflash tool is not available in BMC or Command execution failed"
            print l_msg
            raise OpTestError(l_msg)
        if l_res == BMC_CONST.FW_SUCCESS:
            print "pflash tool is available on the BMC"
            return BMC_CONST.FW_SUCCESS

