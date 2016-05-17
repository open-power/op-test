#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestSwitchEndianSyscall.py $
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
#     changes in other endian. By calling switch_endian sys call,
#     should not effect register and memory space.
#  2. This functionality is implemented in linux git repository
#     /linux/tools/testing/selftests/powerpc/switch_endian
#  3. In this test, will clone latest linux git repository and make required
#     files. At the end will execute switch_endian_test executable file.

import time
import subprocess
import re

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil


class OpTestSwitchEndianSyscall():
    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_hostIP The IP address of the HOST
    # @param i_hostuser The userid to log into the HOST
    # @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd,i_bmcIP)
        self.util = OpTestUtil()

    ##
    # @brief  If git and gcc commands are availble on host, this function will clone linux
    #         git repository and check for switch_endian_test directory and make
    #         the required files. And finally execute bin file switch_endian_test.
    #
    # @return BMC_CONST.FW_SUCCESS-success or BMC_CONST.FW_FAILED-fail
    #
    def testSwitchEndianSysCall(self):

        # Get OS level
        self.cv_HOST.host_get_OS_Level()

        # Check whether git and gcc commands are available on host
        self.cv_HOST.host_check_command("git")
        self.cv_HOST.host_check_command("gcc")

        # Clone latest linux git repository into l_dir
        l_dir = "/tmp/linux"
        self.cv_HOST.host_clone_linux_source(l_dir)

        # Check for switch_endian test directory.
        self.check_dir_exists(l_dir)

        # make the required files
        self.make_test(l_dir)

        # Run the switch_endian sys call test once
        l_rc = self.run_once(l_dir)
        if int(l_rc) == 1:
            print "Switch endian sys call test got succesful"
            return BMC_CONST.FW_SUCCESS
        else:
            print "Switch endian sys call test failed"
            return BMC_CONST.FW_FAILED

    ##
    # @brief  It will check for existence of switch_endian directory in the cloned repository
    #
    # @param i_dir @type string: linux source directory
    #
    # @return 1-success or raise OpTestError
    #
    def check_dir_exists(self, i_dir):
        l_dir = '%s/tools/testing/selftests/powerpc/switch_endian' % i_dir
        l_cmd = "test -d %s; echo $?" % l_dir
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        print l_res
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Switch endian test directory exists"
            return 1
        else:
            l_msg = "Switch endian directory is not present"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief  It will prepare for executable bin files using make command
    #         At the end it will check for bin file switch_endian_test and
    #         will throw an exception in case of missing bin file after make
    #
    # @param i_dir @type string: linux source directory
    #
    # @return 1-success or raise OpTestError
    #
    def make_test(self, i_dir):
        l_cmd = "cd %s/tools/testing/selftests/powerpc/switch_endian;\
                 make;" % i_dir
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_cmd = "test -f %s/tools/testing/selftests/powerpc/switch_endian/switch_endian_test; echo $?" % i_dir
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary switch_endian_test is available"
            return 1
        else:
            l_msg = "Switch_endian_test bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function will run executable file switch_endian_test and
    #        check for switch_endian() sys call functionality
    #
    # @param i_dir @type string: linux source directory
    #
    # @return 1-success ; 0-fail
    #
    def run_once(self, i_dir):
        l_cmd = "cd %s/tools/testing/selftests/powerpc/switch_endian/;\
                 ./switch_endian_test" % i_dir
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        if (l_res.__contains__('success: switch_endian_test')):
            return 1
        else:
            return 0
