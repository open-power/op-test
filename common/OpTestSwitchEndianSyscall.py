#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestSwitchEndianSyscall.py $
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

# @package OpTestSwitchEndianSyscall
#  Switch endian system call package for OpenPower testing.
#
#  This class will test the functionality of following.
#  1. It will test switch_endian() system call by executing the registers
#     changes in other endian. By calling switch_endian should not effect.
#  2. This functionality is implemented in linux git repository
#     /linux/tools/testing/selftests/powerpc/switch_endian
#  3. In this test, will clone latest linux git repository and make required
#     files. At the end will execute switch_endian_test executable file.

import time
import subprocess
import re

from OpTestBMC import OpTestBMC
from OpTestIPMI import OpTestIPMI
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestLpar import OpTestLpar
from OpTestUtil import OpTestUtil


class OpTestSwitchEndianSyscall():
            # Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

    def testSwitchEndianSysCall(self):
        # This function will perform below steps one by one.

        # Get OS level
        self.cv_LPAR.lpar_get_OS_Level()

        # Clone latest linux git repository
        self.clone_linux_source()

        # Check for switch_endian test directory.
        self.check_dir_exists()

        # make the required files
        self.make_test()

        # Run the switch_endian sys call test once
        l_rc = self.run_once()
        if int(l_rc) == 1:
            print "Switch endian sys call test got succesful"
            return BMC_CONST.FW_SUCCESS
        else:
            print "Switch endian sys call test failed"
            return BMC_CONST.FW_FAILED

    def clone_linux_source(self):
        # It will clone latest linux git repository in /tmp directory
        msg = 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git'
        cmd = "git clone %s /tmp/linux" % msg
        self.cv_LPAR._ssh_execute("rm -rf /tmp/linux")
        self.cv_LPAR._ssh_execute("mkdir /tmp/linux")
        try:
            print cmd
            res = self.cv_LPAR._ssh_execute(cmd)
            print res
        except:
            l_msg = "Cloning linux git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

    def check_dir_exists(self):
        # It will check for switch_endian directory in the cloned repository
        # It will raise exception incase of missing directory
        dir = '/tmp/linux/tools/testing/selftests/powerpc/switch_endian'
        cmd = "test -d %s; echo $?" % dir
        print cmd
        res = self.cv_LPAR._ssh_execute(cmd)
        print res
        if (res.__contains__(str(0))):
            print "Switch endian test directory exists"
            return 1
        else:
            l_msg = "Switch endian directory is not present"
            print l_msg
            raise OpTestError(l_msg)

    def make_test(self):
        # It will prepare for executable bin files using make command
        # At the end it will check for bin file switch_endian_test and
        # will throw an exception in case of missing bin file after make
        cmd = "cd /tmp/linux/tools/testing/selftests/powerpc/switch_endian;\
                 make;"
        print cmd
        res = self.cv_LPAR._ssh_execute(cmd)
        print res
        cmd = "test -f /tmp/linux/tools/testing/selftests/powerpc/switch_endian/switch_endian_test; echo $?"
        res = self.cv_LPAR._ssh_execute(cmd)
        print res
        if (res.__contains__(str(0))):
            print "Executable binary switch_endian_test is available"
            return 1
        else:
            l_msg = "Switch_endian_test bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    def run_once(self):
        # This function will run executable file switch_endian_test and
        # check for switch_endian() sys call functionality
        cmd = "cd /tmp/linux/tools/testing/selftests/powerpc/switch_endian/;\
                 ./switch_endian_test"
        print cmd
        res = self.cv_LPAR._ssh_execute(cmd)
        print res
        if (res.__contains__('success: switch_endian_test')):
            return 1
        else:
            return 0
