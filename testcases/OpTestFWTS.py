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
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                 i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()


    ##
    # @brief This function just brings the system to host OS.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_system_reboot(self):
        print "Testing FWTS: Booting system to OS"
        print "Performing a IPMI Power OFF Operation"
        # Perform a IPMI Power OFF Operation(Immediate Shutdown)
        self.cv_IPMI.ipmi_power_off()
        if int(self.cv_SYSTEM.sys_wait_for_standby_state(BMC_CONST.SYSTEM_STANDBY_STATE_DELAY)) == BMC_CONST.FW_SUCCESS:
            print "System is in standby/Soft-off state"
        else:
            l_msg = "System failed to reach standby/Soft-off state"
            raise OpTestError(l_msg)

        self.cv_IPMI.ipmi_power_on()
        self.cv_SYSTEM.sys_check_host_status()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_IPMI.clear_ssh_keys(self.cv_HOST.ip)

        print "Gathering the OPAL msg logs"
        self.cv_HOST.host_gather_opal_msg_log()
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function will cover following test steps
    #        1. It will get the OS level installed on power platform
    #        2. It will check for kernel version installed on the Open Power Machine
    #        3. It will check for ipmitool command existence and ipmitool package
    #        4. Load the necessary ipmi modules based on config values
    #        5. Check for python module pyparsing existence on test machine which
    #           is actually required to genrate fwts olog.json file from skiboot source
    #        6. It will check for necessary packages existence which are required to
    #           use fwts source
    #        7. Clone both skiboot and fwts source codes.
    #        8. Generate olog.json file and build fwts tool
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_init(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()
        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Checking for ipmitool command and package
        self.cv_HOST.host_check_command("ipmitool")

        l_pkg = self.cv_HOST.host_check_pkg_for_utility(l_oslevel, "ipmitool")
        print "Installed package: %s" % l_pkg

        # loading below ipmi modules based on config option
        # ipmi_devintf, ipmi_powernv and ipmi_masghandler
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_DEVICE_INTERFACE,
                                                      BMC_CONST.IPMI_DEV_INTF)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_POWERNV,
                                                      BMC_CONST.IPMI_POWERNV)
        self.cv_HOST.host_load_module_based_on_config(l_kernel, BMC_CONST.CONFIG_IPMI_HANDLER,
                                                      BMC_CONST.IPMI_MSG_HANDLER)

        # Check the necessary packages are available to build fwts tool
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "autoconf")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "automake")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "libglib2.0-dev")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "libtool")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "libpcre3-dev")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "libjson0-dev")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "flex")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "bison")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "dkms")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "libfdt-dev")
        self.cv_HOST.host_check_pkg_availability(l_oslevel, "device-tree-compiler")

        # Do the necessary setup clone skiboot,fwts and build olog.json and fwts tool
        self.cv_HOST.host_clone_skiboot_source(BMC_CONST.SKIBOOT_WORKING_DIR)
        self.cv_HOST.host_generate_fwts_olog_json(BMC_CONST.SKIBOOT_WORKING_DIR)
        self.cv_HOST.host_clone_fwts_source(BMC_CONST.FWTS_WORKING_DIR)
        self.cv_HOST.host_build_fwts_tool(BMC_CONST.FWTS_WORKING_DIR)


    ##
    # @brief This function will execute FWTS:bmc_info test
    #        BMC Info
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_bmc_info(self):
        print "FWTS: executing bmc_info test"
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_REMOVE_EXISTING_RESULTS_LOG)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_BMC_INFO)
        self.read_results_log()
        if int(l_res[-1]):
            l_msg = "FWTS: bmc_info test failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function will execute FWTS:prd_info test
    #        OPAL Processor Recovery Diagnostics Info
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_prd_info(self):
        print "FWTS: Running prd_info test"
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_REMOVE_EXISTING_RESULTS_LOG)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_PRD_INFO)
        self.read_results_log()
        if int(l_res[-1]):
            l_msg = "FWTS prd_info test failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function will execute FWTS:olog test
    #        Run OLOG scan and analysis checks.
    #        This test will execute below command
    #        fwts olog -j /root/skiboot/
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_olog(self):
        print "FWTS: Running olog test"
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_REMOVE_EXISTING_RESULTS_LOG)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_OLOG + BMC_CONST.SKIBOOT_WORKING_DIR + ";echo $?")
        self.read_results_log()
        if int(l_res[-1]):
            l_msg = "FWTS olog test failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function will execute FWTS:oops test
    #        Scan kernel log for Oopses.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_oops(self):
        print "FWTS: Running oops test"
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_REMOVE_EXISTING_RESULTS_LOG)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_OOPS)
        self.read_results_log()
        if int(l_res[-1]):
            l_msg = "FWTS oops test failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will execute FWTS:mtd_info test
    #        OPAL MTD Info
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_mtd_info(self):
        print "FWTS: Running mtd_info test"
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_IPMI.ipmi_host_login(l_con)
        self.cv_IPMI.ipmi_host_set_unique_prompt(l_con)
        self.cv_IPMI.run_host_cmd_on_ipmi_console("uname -a")
        self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_REMOVE_EXISTING_RESULTS_LOG)
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_OOPS)
        self.read_results_log()
        if int(l_res[-1]):
            l_msg = "FWTS mtd_info test failed"
            raise OpTestError(l_msg)
        self.cv_IPMI.ipmi_close_console(l_con)
        return BMC_CONST.FW_SUCCESS


    ##
    # @brief This function will just print results.log file for further analysis.
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def read_results_log(self):
        print "\nFWTS: Printing test results"
        l_res = self.cv_IPMI.run_host_cmd_on_ipmi_console(BMC_CONST.HOST_FWTS_RESULTS_LOG)
        if int(l_res[-1]):
            l_msg = "\nFWTS: unable to get results log file"
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS
