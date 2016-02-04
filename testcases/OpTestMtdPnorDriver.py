#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/testcases/OpTestMtdPnorDriver.py $
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

# @package OpTestMtdPnorDriver
#  Test MTD PNOR Driver package for OpenPower testing.
#
#  This class will test the functionality of following
#   This test has mainly to view open power's PNOR flash contents in an x86 machine
#   using fcp utility. The corresponding pnor file is taking from /dev/mtd0.
#
import time
import subprocess
import re
import commands

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestLpar import OpTestLpar
from common.OpTestUtil import OpTestUtil


class OpTestMtdPnorDriver():
    ## Initialize this object and also getting the lpar login credentials to use by scp utility
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
        self.lpar_user = i_lparuser
        self.lpar_ip = i_lparip
        self.lpar_Passwd = i_lparPasswd

    ##
    # @brief  This function has following test steps
    #         1. Get lpar information(OS and Kernel information)
    #         2. Load the mtd module based on config value
    #         3. Check /dev/mtd0 character device file existence on lpar
    #         4. Copying the contents of the flash in a file /tmp/pnor
    #         5. Getting the /tmp/pnor file into local x86 machine using scp utility
    #         6. Remove existing /tmp/ffs directory and
    #            Clone latest ffs git repository in local x86 working machine
    #         7. Compile ffs repository to get fcp utility
    #         8. Check existence of fcp utility in ffs repository, after compiling
    #         9. Get the PNOR flash contents on an x86 machine using fcp utility
    #
    # @return BMC_CONST.FW_SUCCESS-success or raise OpTestError-fail
    #
    def testMtdPnorDriver(self):

        # Get OS level
        l_oslevel = self.cv_LPAR.lpar_get_OS_Level()

        # Get Kernel Version
        l_kernel = self.cv_LPAR.lpar_get_kernel_version()

        # loading mtd module based on config option
        l_config = "CONFIG_MTD_POWERNV_FLASH"
        l_module = "mtd"
        self.cv_LPAR.lpar_load_module_based_on_config(l_kernel, l_config, l_module)

        # Check /dev/mtd0 file existence on lpar
        l_cmd = "ls -l /dev/mtd0; echo $?"
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            print "/dev/mtd0 character device file exists on lpar"
        else:
            l_msg = "/dev/mtd0 character device file doesn't exist on lpar"
            print l_msg
            raise OpTestError(l_msg)

        # Copying the contents of the PNOR flash in a file /tmp/pnor
        l_file = "/tmp/pnor"
        l_cmd = "cat /dev/mtd0 > %s; echo $?" % l_file
        l_res = self.cv_LPAR.lpar_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            print "Fetched PNOR data from /dev/mtd0 into temp file /tmp/pnor"
        else:
            l_msg = "Fetching PNOR data is failed from /dev/mtd0 into temp file /tmp/pnor"
            print l_msg
            raise OpTestError(l_msg)

        # Getting the /tmp/pnor file into local x86 machine
        l_path = "/tmp/"
        self.util.copyFilesToDest(l_path, self.lpar_user, self.lpar_ip, l_file, self.lpar_Passwd, "2", BMC_CONST.SCP_TO_LOCAL)
        l_list =  commands.getstatusoutput("ls -l %s; echo $?" % l_path)
        print l_list

        l_workdir = "/tmp/ffs"
        # Remove existing /tmp/ffs directory
        l_res = commands.getstatusoutput("rm -rf %s" % l_workdir)
        print l_res

        # Clone latest ffs git repository in local x86 working machine
        l_cmd = "git clone   https://github.com/open-power/ffs/ %s" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        print l_res
        if int(l_res[0]) == 0:
            print "Cloning of ffs repository is successfull"
        else:
            l_msg = "Cloning ffs repository is failed"
            print l_msg
            raise OpTestError(l_msg)

        # Compile ffs repository to get fcp utility
        l_cmd = "cd %s/; make" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        print l_res
        if int(l_res[0]) == 0:
            print "Compiling fcp utility is successfull"
        else:
            l_msg = "Compiling fcp utility is failed"
            print l_msg
            raise OpTestError(l_msg)

        # Check existence of fcp utility in ffs repository, after compiling.
        l_cmd = "test -f %s/fcp/x86/fcp" % l_workdir
        l_res = commands.getstatusoutput(l_cmd)
        print l_res
        if int(l_res[0]) == 0:
            print "Compiling fcp utility is successfull"
        else:
            l_msg = "Compiling fcp utility is failed"
            print l_msg
            raise OpTestError(l_msg)

        # Check the PNOR flash contents on an x86 machine using fcp utility
        l_cmd = "%s/fcp/x86/fcp -o 0x0 -L %s" % (l_workdir, l_file)
        l_res = commands.getstatusoutput(l_cmd)
        print l_res[1]
        if int(l_res[0]) == 0:
            print "Getting PNOR data successfull using fcp utility"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Getting the PNOR data using fcp utility failed"
            print l_msg
            raise OpTestError(l_msg)
