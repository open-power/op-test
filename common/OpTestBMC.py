#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestBMC.py $
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
import pxssh
import pexpect
import subprocess
from OpTestIPMI import OpTestIPMI

class OpTestBMC():


    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,i_ffdcDir=None):
        self.cv_bmcIP = i_bmcIP
        self.cv_bmcUser = i_bmcUser
        self.cv_bmcPasswd = i_bmcPasswd
        self.cv_ffdcDir = i_ffdcDir
        self.cv_IPMI = OpTestIPMI(i_bmcIP,i_bmcUser,i_bmcPasswd,i_ffdcDir)

    def _cmd_run(self, cmdStr, timeout=30, logFile=None):
        """This function runs a command on the BMC.

        :param logFile: File where the command output will be written.
            All command output files are placed in the FFDC directory as configured
            in the config file.
        :type logFile: str.
        :param timeout: Command timeout in seconds. If not specified, the
            default timeout value is 30 seconds.
        :type timeout: int.
        :returns: int -- the return code, 0: success, 1: error
        :raises: pexect timeout, eof

        """

        ''' Add -k to the SSH options '''

        hostname = self.cv_bmcIP + " -k"

        p = pxssh.pxssh()
        p.logfile = sys.stdout
        p.PROMPT = '# '

        ''' login but do not try to change the prompt since the AMI bmc
            busybox does support it '''

        # http://superuser.com/questions/839878/how-to-solve-python-bug-without-root-permission
        p.login(hostname, self.cv_bmcUser, self.cv_bmcPasswd, auto_prompt_reset=False)
        p.sendline()
        p.prompt()
        print 'At BMC %s prompt...' % self.cv_bmcIP

        p.sendline(cmdStr)
        p.prompt(timeout=timeout)

        ''' if optional argument is set, save command output to file '''

        if logFile is not None:
            fn = self.cv_ffdcDir + "/" + logFile
            with open(fn, 'w') as f:
                f.write(p.before)

        p.sendline('echo $?')
        index = p.expect(['0', pexpect.TIMEOUT])
        if index == 0:
            rc = 0
        if index == 1:
            print 'Non-zero return code detected, command failed'
            rc = p.before

        return rc


    def reboot(self):
        """This function issues the reboot command on the BMC console.  It then
        pings the BMC until it responds, which presumably means that it is done
        rebooting.  It returns the number of failed pings.  The caller should make
        returned value is greater than 1

        :returns: int -- 0 on success, non-zero on failure

        """
        retries = 0
        self._cmd_run('reboot', logFile='bmc_reboot.log')
        print 'Sent reboot command now waiting for reboot to complete...'
        time.sleep(30)
        '''  Ping the system until it reboots  '''
        while True:
            try:
                subprocess.check_call(["ping", self.cv_bmcIP, "-c1"])
                break
            except subprocess.CalledProcessError as e:
                print "Ping return code: ", e.returncode, "retrying..."
                retries += 1
                time.sleep(30)

            if retries > 5:
                print "Error. BMC is not reponding to pings"
                return -1

        print 'BMC reboot complete.'

        return 0


    def pnor_img_transfer(self,i_imageDir,i_imageName):
        """This function copies the PNOR image to the BMC /tmp dir.

        :returns: int -- the rsync command return code
        """
        pnor_path = i_imageDir + i_imageName
        rsync_cmd = 'rsync -v -e "ssh -k" %s %s@%s:/tmp' % (pnor_path,
                                                            self.cv_bmcUser,
                                                            self.cv_bmcIP)
        print rsync_cmd
        rsync = pexpect.spawn(rsync_cmd)
        rsync.logfile = sys.stdout
        rsync.expect('assword: ')
        rsync.sendline(self.cv_bmcPasswd)
        rsync.expect('total size is', timeout=60)
        rsync.expect(pexpect.EOF)
        rsync.close()
        return rsync.exitstatus


    def pnor_img_flash(self,i_imageName):
        """This function flashes the PNOR image.

        :returns: int -- the pflash command return code
        """
        cmd = '/usr/local/bin/pflash -E -f -p /tmp/%s' % i_imageName
        rc = self._cmd_run(cmd, timeout=180, logFile='pflash.log')
        return rc