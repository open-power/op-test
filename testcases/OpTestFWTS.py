#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestFWTS.py $
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

#  @package OpTestFWTS.py
#  This package will execute and test Firmware Test Suite tests.
#
#   bmc_info    BMC Info
#   prd_info    Run OLOG(OPAL Log) scan and analysis checks.
#   mtd_info    OPAL MTD Info
#   oops        Scan kernel log for Oopses.
#   olog        OPAL Processor Recovery Diagnostics Info
#
#   FWTS Configuration/Installation process steps:
#   Currently fwts tool installed from distro released one, doesn't contain all the
#   tests implemented for power systems. In order to execute and work above fwts tests user need to
#   follow below steps to build from the source.
#   1. Clone fwts source:
#       git clone git://kernel.ubuntu.com/hwe/fwts.git
#
#   2. Install dependencies:
#       sudo apt-get install autoconf automake libglib2.0-dev libtool libpcre3-dev libjson0-dev flex bison dkms libfdt-dev
#
#   3. Build and install:
#       autoreconf -ivf
#       ./configure
#       make
#
#   4. Export the tool(fwts binary) into current path
#       export PATH=(path_to_fwts_binary):$PATH
#
#   5. In order to work olog test, user need to generate olog.json file from skiboot code into below directory
#       git clone https://github.com/open-power/skiboot
#       cd ~/skiboot/external/fwts
#       ./generate-fwts-olog
#       sudo fwts olog -j /root/skiboot/external/fwts/
#
#   All the above steps are for manual execution, This OpTestFWTS package removes the above all
#   dependencies and user needs to do just installation of below packages.
#   sudo apt-get install autoconf automake libglib2.0-dev libtool libpcre3-dev libjson0-dev flex bison dkms libfdt-dev
#   python module pyparsing --> which is required for generating olog.json file
#


import time
import subprocess
import re
import sys
import os

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem
from common.OpTestUtil import OpTestUtil


class OpTestFWTS():
    ##  Initialize this object
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
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, host=self.cv_HOST)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                 i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()
        self.user = i_hostuser
        self.ip = i_hostip
        self.passwd = i_hostPasswd


    ##
    # @brief This function just brings the system to host OS.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_system_reboot(self):
        print "Testing FWTS: Booting system to OS"
        self.cv_SYSTEM.sys_hard_reboot()
        self.cv_IPMI.clear_ssh_keys(self.cv_HOST.ip)

        print "Gathering the OPAL msg logs"
        self.cv_HOST.host_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function just executes the fwts_execution.sh on host OS
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_fwts(self):
        l_oslevel = self.cv_HOST.host_get_OS_Level()
        if not "Ubuntu" in l_oslevel:
            return
        # Copy the fwts execution file to the tmp folder in the host
        base_path = (os.path.dirname(os.path.abspath(__file__))).split('testcases')[0]
        fwts_script = base_path + "/testcases/fwts_execution.sh"
        try:
            self.util.copyFilesToDest(fwts_script, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying fwts file to host failed"
            print l_msg
            raise OpTestError(l_msg)

        l_res = self.cv_HOST.host_run_command("/tmp/fwts_execution.sh")
        print l_res

