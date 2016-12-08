#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
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

#  @package OpTestCAPI
#  CAPI tests for OpenPower testing.
#
#  This class will test the functionality of CAPI
#
#  Prerequisites:
#  1. Host must have a CAPI FPGA card
#  2. CAPI card must have been flashed with memcpy AFU
#
#  Extra timebase sync tests prerequisite:
#  3. PSL must support timebase sync

from common.OpTestBMC import OpTestBMC
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpTestSystem

class OpTestCAPI():
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
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        self.util = OpTestUtil()

    ##
    # @brief This function covers the following test steps:
    #        1. Check that host has a CAPI FPGA card
    #        2. Check for os level and get kernel version
    #        3. Load the cxl module if required
    #        4. Check that the device files afu0.0m and afu0.0s exist
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_cxl_device_file(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Check that host has a CAPI FPGA card
        self.cv_HOST.host_has_capi_fpga_card()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Check device files /dev/cxl/afu0.0{m,s} existence
        l_cmd = "ls -l /dev/cxl/afu0.0{m,s}; echo $?"
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            print "cxl device file tests pass"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "cxl device file tests fail"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function covers the following test steps
    #        1. Check that host has a CAPI FPGA card
    #        2. Check for os level and get kernel version
    #        3. Load the cxl module if required
    #        4. Clone an build cxl-tests (along with libcxl)
    #        5. Test the sysfs abi with libcxl_tests
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_sysfs_abi(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Check that host has a CAPI FPGA card
        self.cv_HOST.host_has_capi_fpga_card()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "libcxl_tests") != True or
            self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run sysfs abi tests
        l_exec = "libcxl_tests >/tmp/libcxl_tests.log"
        l_cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s; echo $?" % (l_dir, l_exec)
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            l_msg = "sysfs abi libcxl_tests pass"
            print l_msg
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "sysfs abi libcxl_tests have failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function covers the following test steps:
    #        1. Check that host has a CAPI FPGA card
    #        2. Check for os level and get kernel version
    #        3. Load the cxl module if required
    #        4. Clone an build cxl-tests (along with libcxl)
    #        5. Test the memcpy AFU with memcpy_afu_ctx
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_memcpy_afu(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Check that host has a CAPI FPGA card
        self.cv_HOST.host_has_capi_fpga_card()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
            self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run memcpy afu tests
        l_exec = "memcpy_afu_ctx -p1 -l1 >/tmp/memcpy_afu_ctx.log"
        l_cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s; echo $?" % (l_dir, l_exec)
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            l_msg = "memcpy_afu_ctx tests pass"
            print l_msg
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "memcpy_afu_ctx tests fail"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function covers the following test steps:
    #        1. Check that host has a CAPI FPGA card
    #        2. Check for os level and get kernel version
    #        3. Load the cxl module if required
    #        If the card PSL supports timebase sync:
    #                5. Clone an build cxl-tests (along with libcxl)
    #           6. Verify timebase sync with memcpy_afu_ctx -t
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_timebase_sync(self):
        self.cv_SYSTEM.sys_bmc_power_on_validate_host()

        # Check that host has a CAPI FPGA card
        self.cv_HOST.host_has_capi_fpga_card()

        # Get OS level
        l_oslevel = self.cv_HOST.host_get_OS_Level()

        # Get kernel version
        l_kernel = self.cv_HOST.host_get_kernel_version()

        # Load module cxl based on config option
        l_config = "CONFIG_CXL"
        l_module = "cxl"
        self.cv_HOST.host_load_module_based_on_config(l_kernel, l_config, l_module)
        # Check PSL timebase sync support
        l_cmd = "grep -q -w 1 /sys/class/cxl/card0/psl_timebase_synced; echo $?"
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) != 0:
            l_msg = "PSL does not support timebase sync; skipping test"
            print l_msg
            return BMC_CONST.FW_SUCCESS

        # Check that cxl-tests binary and library are available
        # If not, clone and build cxl-tests (along with libcxl)
        l_dir = "/tmp/cxl-tests"
        if (self.cv_HOST.host_check_binary(l_dir, "memcpy_afu_ctx") != True or
            self.cv_HOST.host_check_binary(l_dir, "libcxl/libcxl.so") != True):
            self.cv_HOST.host_clone_cxl_tests(l_dir)
            self.cv_HOST.host_build_cxl_tests(l_dir)

        # Run timebase sync tests
        l_exec = "memcpy_afu_ctx -t -p1 -l1 >/tmp/memcpy_afu_ctx-t.log"
        l_cmd = "cd %s && LD_LIBRARY_PATH=libcxl ./%s; echo $?" % (l_dir, l_exec)
        print l_cmd
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            l_msg = "memcpy_afu_ctx -t tests pass"
            print l_msg
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "memcpy_afu_ctx -t tests fail"
            print l_msg
            raise OpTestError(l_msg)
