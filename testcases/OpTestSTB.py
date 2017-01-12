#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSTB.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
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

# @package OpTestSTB
#  Secure and Trusted Boot testing on OpenPower Systems
#
#  This class will test the functionality of Secure and Trusted
#  boot.
#  The following tests does the functional verification of the following
#  features namely,
#  Read Security Switch Register (SSR) for Secure and Trusted modes
#  Read OPAL message logs for Secureboot and Trustedboot modes
#  Crosscheck SSR values with the OPAL values
#  Check Coherent Accelerator Processor Proxy (CAPP) partition for
#      . Measure
#      . Verify
#      . Load
#  Check Boot Kernel partition for
#      . Measure
#      . Verify
#      . Load
#  Cross check CAPP and BootKernel partition values with Secure and Trusted boot
#  modes.

import time
import subprocess
import re
import sys

from common.OpTestBMC import OpTestBMC
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestSystem import OpTestSystem

class OpTestSTB():
    ## Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    #  @param i_hostIP The IP address of the HOST
    #  @param i_hostuser The userid to log into the HOST
    #  @param i_hostPasswd The password of the userid to log into the HOST with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_hostip=None,
                 i_hostuser=None, i_hostPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        self.cv_SYSTEM = OpTestSystem(i_bmcIP, i_bmcUser, i_bmcPasswd,
                         i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir, i_hostip,
                         i_hostuser, i_hostPasswd)
        # Collecting OPAL message logs
        self.l_data = self.cv_HOST.host_run_command(BMC_CONST.OPAL_MSG_LOG)
        self.l_rc = self.find_stb_support()
        if self.l_rc:
            # No need to run further tests exit gracefully
            sys.exit()

    ##
    # @brief This function finds the lines containing given string @i_str
    # from a file data @i_data.
    # @param i_data contains OPAL message logs
    # @param i_str contains string to be found ex: Secure boot
    # Returns @l_data which contains @i_str line found
    # Returns None if string not found
    #
    def string_get(self, i_data, i_str):
        for l_line in i_data.splitlines():
            # Skip empty lines
            if not l_line:
                continue
            # Looking for the string i_str in current line
            if i_str in l_line:
                # Removes the time stamp ex: [    4.195376870,5]
                l_group = re.search(BMC_CONST.RE_TIMESTAMP, l_line)
                if l_group is not None:
                    l_data = l_group.groups()[0]
                    return l_data
        return None

    ##
    # @brief This function finds given strings @i_enable or @i_disable
    # from a line @i_line.
    # @param i_line contains required message line from OPAL message log
    # @param i_enable contains string to be found ex: on
    # @param i_disable contains string to be found ex: off
    # Returns either enabled @i_enable or disabled @i_disable string
    #
    def status_finder(self, i_line, i_enable, i_disable):
        #for mode in self.i_generator:
        if i_enable in i_line.rstrip(BMC_CONST.NEWLINE):
            return i_enable
        else:
            return i_disable

    ##
    # @brief This function call the reboot function from OpTestSystem
    # Returns BMC_CONST.FW_SUCCESS on success else raises error with
    # proper error reason.
    def stb_reboot(self):
        self.cv_SYSTEM.sys_hard_reboot()

    ##
    # @brief This function finds whether Secure and Trusted boot disabled
    # information is there in OPAL message log.
    # Returns either FW_FAILED or FW_SUCCESS based on the current support.
    #
    def find_stb_support(self):
        l_stb_not_support = self.string_get(self.l_data,
                                            BMC_CONST.STB_NOT_SUPPORTED)
        if l_stb_not_support:
            print BMC_CONST.STB_NOT_SUPPORTED
            print "No need to run further tests. Bailing out..."
            return BMC_CONST.FW_FAILED
        else:
            print "Run further tests ..."
            return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function reads Security Switch Register (SSR)
    # of hardware for Secure and Trusted boot mode state
    # This function compiles skiboot and with the help of 'getscom' binary
    # reads from SSR.
    # Returns @l_res, which contains register value in integer
    #
    def read_hw_stb_support(self):
        # Check whether git and gcc commands are available on the host
        self.cv_HOST.host_check_command("git")
        self.cv_HOST.host_check_command("gcc")

        # It will clone skiboot source repository
        l_dir = BMC_CONST.CLONE_SKIBOOT_DIR
        self.cv_HOST.host_clone_skiboot_source(l_dir)
        # Compile the necessary tools xscom-utils and gard utility
        self.cv_HOST.host_compile_xscom_utilities(l_dir)

        # Reading Security Switch Register for Secure boot values
        l_cmd = "cd %s/external/xscom-utils/; ./getscom pu 10005" % l_dir
        # Expected values
        # cd38000000000000 - Secure and Trusted mode Enabled
        # 0000000000000000 - Secure and Trusted mode Disabled
        l_res = self.cv_HOST.host_run_command(l_cmd)
        l_res = "0x" + l_res.replace("\r\n","")
        l_res = int(l_res, 16)
        if l_res:
            return l_res

    ##
    # @brief This function uses Security Switch Register (SSR) information and
    # finds out whether Secure boot mode bit is 'on' or 'off'.
    # Returns True when Secure boot mode is 'on' i.e. SECURE_MODE_ON
    # Returns False when Secure boot mode is 'off' i.e. SECURE_MODE_OFF
    #
    def hw_get_sb_mode(self):
        l_hw_sb_value = self.read_hw_stb_support()
        l_sb_bv = l_hw_sb_value & BMC_CONST.SB_MASK
        if l_sb_bv == BMC_CONST.SB_MASK:
            print BMC_CONST.SECURE_MODE_ON
            return True
        else:
            print BMC_CONST.SECURE_MODE_OFF
            return False

    ##
    # @brief This function uses Security Switch Register (SSR) information and
    # finds out whether Trusted boot mode bit is 'on' or 'off'.
    # Returns True when Trusted boot mode is 'on' i.e. TRUSTED_MODE_ON
    # Returns False when Trusted boot mode is 'off' i.e. TRUSTED_MODE_OFF
    #
    def hw_get_tb_mode(self):
        l_hw_tb_value = self.read_hw_stb_support()
        l_tb_bv = l_hw_tb_value & BMC_CONST.TB_MASK
        if l_tb_bv == BMC_CONST.TB_MASK:
            print BMC_CONST.TRUSTED_MODE_ON
            return True
        else:
            print BMC_CONST.TRUSTED_MODE_OFF
            return False

    ##
    # @brief This function collects Secure boot mode information from OPAL
    # messagelog and if found determines whether it is 'on' or 'off'.
    # Returns True for Secure boot mode 'on'
    # Returns False for Secure boot mode 'off'
    # Raises OpTestError when no information found
    #
    def opal_get_secure_boot_mode(self):
        l_secure_mode = self.string_get(self.l_data,
                                        BMC_CONST.SECURE_MODE)
        if l_secure_mode:
            l_secure_mode_status = self.status_finder(l_secure_mode,
                                                      BMC_CONST.ON,
                                                      BMC_CONST.OFF)
            if l_secure_mode_status == BMC_CONST.ON:
                print BMC_CONST.SECURE_MODE_ON
                return True
            elif l_secure_mode_status == BMC_CONST.OFF:
                print BMC_CONST.SECURE_MODE_OFF
                return False
        else:
            l_msg = "Secure mode enable/disable status not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function collects Trusted boot mode information from OPAL
    # messagelog and if found determines whether it is 'on' or 'off'.
    # Returns True for Trusted boot mode 'on'
    # Returns False for Trusted boot mode 'off'
    # Raises OpTestError when no information found
    #
    def opal_get_trusted_boot_mode(self):
        l_trusted_mode = self.string_get(self.l_data,
                                         BMC_CONST.TRUSTED_MODE)
        if l_trusted_mode:
            l_trusted_mode_status = self.status_finder(l_trusted_mode,
                                                       BMC_CONST.ON,
                                                       BMC_CONST.OFF)
            if l_trusted_mode_status == BMC_CONST.ON:
                print BMC_CONST.TRUSTED_MODE_ON
                return True
            elif l_trusted_mode_status == BMC_CONST.OFF:
                print BMC_CONST.TRUSTED_MODE_OFF
                return False
        else:
            l_msg = "Trusted mode enable/disable status not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP measured information from OPAL
    # messagelog and if found determines whether it is 'measured' or
    # 'not measured'.
    # Returns True for CAPP partition measured
    # Returns False for CAPP partition not measured
    # Raises OpTestError when no information found
    #
    def opal_get_capp_measured_info(self):
        l_capp_measured = self.string_get(self.l_data,
                                          BMC_CONST.CAPP_MEASURED)
        l_capp_not_measured = self.string_get(self.l_data,
                                              BMC_CONST.TB_SKIPPED)
        if l_capp_measured:
            print BMC_CONST.CAPP_PART_MEASURED
            return True
        elif l_capp_not_measured:
            print BMC_CONST.CAPP_PART_NOT_MEASURED
            return False

        l_msg = "CAPP partition measured details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects BOOTKERNEL measured information from OPAL
    # messagelog and if found determines whether it is 'measured' or
    # 'not measured'.
    # Returns True for BOOTKERNEL partition measured
    # Returns False for BOOTKERNEL partition not measured
    # Raises OpTestError when no information found
    #
    def opal_get_bootkernel_measure_info(self):
        l_bk_measured = self.string_get(self.l_data,
                                        BMC_CONST.BOOTKERNEL_MEASURED)
        l_bk_not_measured = self.string_get(self.l_data,
                                            BMC_CONST.TB_SKIPPED)
        if l_bk_measured:
            print BMC_CONST.BOOTKERNEL_PART_MEASURED
            return True
        elif l_bk_not_measured:
            print BMC_CONST.BOOTKERNEL_PART_NOT_MEASURED
            return False

        l_msg =  "BOOTKERNEL partition measured details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP verified information from OPAL
    # messagelog and if found determines whether it is 'verified' or
    # 'not verified'.
    # Returns True for CAPP partition verified
    # Returns False for CAPP partition not verified
    # Raises OpTestError when no information found
    #
    def capp_verified(self):
        l_capp_verified = self.string_get(self.l_data,
                                          BMC_CONST.CAPP_VERIFIED)
        l_capp_not_verified = self.string_get(self.l_data,
                                              BMC_CONST.SB_SKIPPED)
        if l_capp_verified:
            print BMC_CONST.CAPP_PART_VERIFIED
            return True
        elif l_capp_not_verified:
            print BMC_CONST.CAPP_PART_NOT_VERIFIED
            return False

        l_msg = "CAPP partition verify details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects BOOTKERNEL verified information from OPAL
    # messagelog and if found determines whether it is 'verified' or
    # 'not verified'.
    # Returns True for BOOTKERNEL partition verified
    # Returns False for BOOTKERNEL partition not verified
    # Raises OpTestError when no information found
    #
    def bootkernel_verified(self):
        l_bk_verified = self.string_get(self.l_data,
                                        BMC_CONST.BOOTKERNEL_VERIFIED)
        l_bk_not_verified = self.string_get(self.l_data,
                                            BMC_CONST.SB_SKIPPED)
        if l_bk_verified:
            print BMC_CONST.BOOTKERNEL_PART_VERIFIED
            return True
        elif l_bk_not_verified:
            print BMC_CONST.BOOTKERNEL_PART_NOT_VERIFIED
            return False

        l_msg = "BOOTKERNEL partition verify details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP loaded information from OPAL
    # messagelog and if found determines whether it is 'loaded' or
    # 'not loaded'.
    # Returns True for CAPP partition loaded
    # Returns False for CAPP partition not loaded
    # Raises OpTestError when no information found
    #
    def capp_loaded(self):
        l_capp_loaded = self.string_get(self.l_data,
                                        BMC_CONST.CAPP_LOADED)
        if l_capp_loaded:
            l_capp_loaded_status = self.status_finder(l_capp_loaded,
                                                      BMC_CONST.LOADED,
                                                      BMC_CONST.NOT_LOADED)
            if l_capp_loaded_status == BMC_CONST.LOADED:
                print BMC_CONST.CAPP_PART_LOADED
                return True
            elif l_capp_loaded_status == BMC_CONST.NOT_LOADED:
                print BMC_CONST.CAPP_PART_NOT_LOADED
                return False
            else:
                print "CAPP partition loaded related error occured"
                return BMC_CONST.FW_FAILED
        else:
            l_msg = "CAPP partition loaded details not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function collects BOOTKERNEL loaded information from OPAL
    # messagelog and if found determines whether it is 'loaded' or
    # 'loaded'.
    # Returns True for BOOTKERNEL partition loaded
    # Returns False for BOOTKERNEL partition not loaded
    # Raises OpTestError when no information found
    #
    def bootkernel_loaded(self):
        l_bk_loaded = self.string_get(self.l_data,
                                      BMC_CONST.BOOTKERNEL_LOADED)
        if l_bk_loaded:
            l_bk_loaded_status = self.status_finder(l_bk_loaded,
                                                    BMC_CONST.LOADED,
                                                    BMC_CONST.NOT_LOADED)
            if l_bk_loaded_status == BMC_CONST.LOADED:
                print BMC_CONST.BOOTKERNEL_PART_LOADED
                return True
            elif l_bk_loaded_status == BMC_CONST.NOT_LOADED:
                print BMC_CONST.BOOTKERNEL_PART_NOT_LOADED
                return False
            else:
                print "BOOTKERNEL partition loaded related error occured"
                return BMC_CONST.FW_FAILED
        else:
            l_msg = "BOOTKERNEL partition loaded details not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function checks for the device-tree node of Trusted boot
    # Returns True when TB_DT_ENTRY found
    # Returns Fail when TB_DT_ENTRY not found
    #
    def verify_tb_dt_node(self):
        return self.cv_HOST.host_dt_prop_exists(BMC_CONST.DT_ROOT, BMC_CONST.TB_DT_ENTRY)

    ##
    # @brief This function checks for the device-tree node of Secure boot
    # Returns True when SB_DT_ENTRY found
    # Returns False when SB_DT_ENTRY not found
    #
    def verify_sb_dt_node(self):
        return self.cv_HOST.host_dt_prop_exists(BMC_CONST.DT_ROOT, BMC_CONST.SB_DT_ENTRY)

    ##
    # @brief This function verifies the output from different functions and validates
    # the functionality
    # 1. Verify for ibm,secureboot device tree node. If not exists then quit further run
    # 2. Verify Secure boot compatibility mode
    # 3. Verify Secure boot mode enabled and the device tree entry exists 
    #
    def verify_secure_boot_in_opal(self):
        # Check the existence of Device tree node
        dt_dir_exists = self.cv_HOST.host_dt_dir_exists(BMC_CONST.DT_ROOT, BMC_CONST.STB_DT_DIR)
        if not dt_dir_exists:
            l_msg = "Secure boot Device Tree node '%s' doesn't exist. Not running further tests." % BMC_CONST.STB_DT_DIR
            print l_msg
            return

        # get the secure boot mode to verify
        secure_boot_mode = self.hw_get_sb_mode()

        # Get the compatible property of Secure Boot
        sb_version = self.cv_HOST.host_get_secureboot_version(BMC_CONST.DT_ROOT, BMC_CONST.STB_DT_DIR)

        if sb_version == str(BMC_CONST.P8_SB_VERSION):
            # Check SSR value and OPAL value are having same secure boot mode setting.
            if secure_boot_mode == self.opal_get_secure_boot_mode():
                # If Secure mode is ON check the secure-enabled flag existence
                if secure_boot_mode:
                    if not self.verify_sb_dt_node():
                        raise OpTestError("Bug: STB: Secure mode is ON but secure-enabled property didn't exist")
                # If Secure mode is OFF check for non-existence of secure-enabled flag
                else:
                    if self.verify_sb_dt_node():
                        raise OpTestError("Bug: STB: Secure mode is OFF but secure-enabled flag exists")
                print "STB: Secure mode is properly configured in Hardware, OPAL & Device Tree"
            else:
                raise OpTestError("Bug: Invalid Secure mode configuration in Hardware, OPAL & Device Tree")
        else:
            raise OpTestError("New STB version found: Add code to enable the same.")

    ##
    # @brief This function verifies the output from different functions and validates
    # the functionality
    # 1. Verify for ibm,secureboot device tree node. If not exists then quit further run
    # 2. Verify Secure boot compatibility mode
    # 3. Verify Trusted boot mode enabled and the device tree entry exists
    #
    def verify_trusted_boot_in_opal(self):
        # Check the existence of Device tree node
        dt_dir_exists = self.cv_HOST.host_dt_dir_exists(BMC_CONST.DT_ROOT, BMC_CONST.STB_DT_DIR)
        if not dt_dir_exists:
            l_msg = "Secure boot Device Tree node '%s' doesn't exist. Not running further tests." % BMC_CONST.STB_DT_DIR
            print l_msg
            return

        # get the trusted boot mode to verify
        trusted_boot_mode = self.hw_get_tb_mode()

        # Get the compatible property of Secure Boot
        sb_version = self.cv_HOST.host_get_secureboot_version(BMC_CONST.DT_ROOT, BMC_CONST.STB_DT_DIR)

        if sb_version == BMC_CONST.P8_SB_VERSION:
            # Check SSR value and OPAL value are having same secure boot mode setting.
            if trusted_boot_mode == self.opal_get_trusted_boot_mode():
                # If Trusted mode is ON check the trusted-enabled flag existence
                if trusted_boot_mode:
                    if not self.verify_tb_dt_node():
                        raise OpTestError("Bug: STB: Trusted mode is ON but trusted-enabled property didn't exist")
                # If Trusted mode is OFF check for non-existence of trusted-enabled flag
                else:
                    if self.verify_sb_dt_node():
                        raise OpTestError("Bug: STB: Trusted mode is OFF but trusted-enabled flag exists")
                print "STB: Truted mode is properly configured in Hardware, OPAL & Device Tree"
            else:
                raise OpTestError("Bug: Invalid Trusted mode configuration in Hardware, OPAL & Device Tree")
        else:
            raise OpTestError("New STB version found: Add code to enable the same.")

    ##
    # @brief This function cross verifies the output from different functions,
    # namely opal_get_capp_measured_info, bootkernel_measured,
    # capp_verified, bootkernel_verified,
    # capp_loaded, bootkernel_loaded,
    # And the above values are cross checked with the Secure and Trusted boot
    # modes. As given below.
    #
    # When Secureboot is ON, Trustedboot is ON
    # Partitions are Measured, Verified, Loaded
    #
    # When Secureboot if OFF, Trustedboot is ON
    # Partitions are Measured, NOT Verified, Loaded
    #
    # When Secureboot is ON, Trustedboot is OFF
    # Partitions are NOT Measured, Verified, Loaded
    #
    # When secureboot is OFF, trustedboot is OFF
    # Partitions are NOT Measured, NOT Verified, Loaded
    #
    # In the case of any mismatche raise OpTestError
    #
    def cross_check_stb(self):

        l_sb_mode = self.opal_get_secure_boot_mode()
        l_tb_mode = self.opal_get_trusted_boot_mode()
        l_capp_measured = self.opal_get_capp_measured_info()
        l_bk_measured = self.opal_get_bootkernel_measure_info()
        l_capp_verified = self.capp_verified()
        l_bk_verified = self.bootkernel_verified()
        l_capp_loaded = self.capp_loaded()
        l_bootkernel_loaded = self.bootkernel_loaded()

        if l_sb_mode == True and \
           l_tb_mode == True:

            print "-" * 40
            print "Secure mode ON and Trusted mode ON"
            l_error = 0
            if l_capp_measured != True:
                l_error = 1
            elif l_bk_measured != True:
                l_error = 1
            elif l_capp_verified != True:
                l_error = 1
            elif l_bk_verified != True:
                l_error = 1
            elif l_capp_loaded != True:
                l_error = 1
            elif l_bootkernel_loaded != True:
                l_error = 1

            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == False and \
           l_tb_mode == True:

            print "-" * 40
            print "Secure mode OFF and Trusted mode ON"
            l_error = 0
            if l_capp_measured != True:
                l_error = 1
            elif l_bk_measured != True:
                l_error = 1
            elif l_capp_verified == False:
                l_error = 1
            elif l_bk_verified == False:
                l_error = 1
            elif l_capp_loaded != True:
                l_error = 1
            elif l_bootkernel_loaded != True:
                l_error = 1

            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == True and \
           l_tb_mode == False:

            print "-" * 40
            print "Secure mode ON and Trusted mode OFF"
            l_error = 0
            if l_capp_measured == False:
                l_error = 1
            elif l_bk_measured == False:
                l_error = 1
            elif l_capp_verified != True:
                l_error = 1
            elif l_bk_verified != True:
                l_error = 1
            elif l_capp_loaded != True:
                l_error = 1
            elif l_bootkernel_loaded != True:
                l_error = 1

            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == False and \
           l_tb_mode == False:

            print "-" * 40
            print "Secure mode OFF and Trusted mode OFF"
            l_error = 0
            if l_capp_measured == False:
                l_error = 1
            elif l_bk_measured == False:
                l_error = 1
            elif l_capp_verified == False:
                l_error = 1
            elif l_bk_verified == False:
                l_error = 1
            elif l_capp_loaded != True:
                l_error = 1
            elif l_bootkernel_loaded != True:
                l_error = 1

            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"
