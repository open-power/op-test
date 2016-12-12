#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestSTB.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2016
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
#from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost

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
        #self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
        #                          i_ffdcDir, i_hostip, i_hostuser, i_hostPasswd)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd, i_bmcIP)
        # Collecting OPAL message logs
        self.l_data = self.cv_HOST.host_run_command(BMC_CONST.OPAL_MSG_LOG)
        self.l_rc = self.find_stb_support()
        if self.l_rc:
            # No need to run further tests exit gracefully
            sys.exit()

    ##
    # @brief This function finds the lines containing given string @i_str
    # from a file data @i_data.
    # @i_data contains OPAL message logs
    # @i_str contains string to be found ex: Secure boot
    # Returns @l_data which contains @i_str line found
    #
    def string_get(self, i_data, i_str):
        for l_line in i_data.splitlines():
            # If there are any empty lines escape them
            if not l_line:
                continue
            # Looking for the string i_str in current line
            if i_str in l_line:
                # Removes the time stamp ex: [    4.195376870,5]
                l_group = re.search(BMC_CONST.RE_TIMESTAMP, l_line)
                if l_group is not None:
                    l_data = l_group.groups()[0]
                    return l_data
        # If string not found retrun None
        return None

    ##
    # @brief This function finds given strings @i_enable or @i_disable
    # from a line @i_line.
    # @i_line contains required message line from OPAL message log
    # @i_enable contains string to be found ex: on
    # @i_disable contains string to be found ex: off
    # Returns either enabled @i_enable or disabled @i_disable string
    #
    def status_finder(self, i_line, i_enable, i_disable):
        #for mode in self.i_generator:
        if i_enable in i_line.rstrip(BMC_CONST.NEWLINE):
            return i_enable
        else:
            return i_disable

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
    # If the SSR value not found/can't read returns '0'
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
        else:
            return "0"

    ##
    # @brief This function uses Security Switch Register (SSR) information and
    # finds out whether Secure boot mode bit is 'on' or 'off'.
    # Returns whether Secure boot mode is 'on' i.e. SECURE_MODE_ON
    # or 'off' i.e. SECURE_MODE_OFF
    #
    def hw_sb_support(self):
        l_hw_sb_value = self.read_hw_stb_support()
        l_sb_bv = l_hw_sb_value & BMC_CONST.SB_MASK
        if BMC_CONST.SB_MASK == l_sb_bv:
            print BMC_CONST.SECURE_MODE_ON
            return BMC_CONST.SECURE_MODE_ON
        else:
            print BMC_CONST.SECURE_MODE_OFF
            return BMC_CONST.SECURE_MODE_OFF

    ##
    # @brief This function uses Security Switch Register (SSR) information and
    # finds out whether Trusted boot mode bit is 'on' or 'off'.
    # Returns whether Trusted boot mode is 'on' i.e. TRUSTED_MODE_ON
    # or 'off' i.e. TRUSTED_MODE_OFF
    #
    def hw_tb_support(self):
        l_hw_tb_value = self.read_hw_stb_support()
        l_tb_bv = l_hw_tb_value & BMC_CONST.TB_MASK
        if BMC_CONST.TB_MASK == l_tb_bv:
            print BMC_CONST.TRUSTED_MODE_ON
            return BMC_CONST.TRUSTED_MODE_ON
        else:
            print BMC_CONST.TRUSTED_MODE_OFF
            return BMC_CONST.TRUSTED_MODE_OFF

    ##
    # @brief This function collects Secure boot mode information from OPAL
    # messagelog and if found determines whether it is 'on' or 'off'.
    # Returns SECURE_MODE_ON for Secure boot mode 'on'
    # Returns SECURE_MODE_OFF for Secure boot mode 'off'
    # Raises OpTestError when no information found
    #
    def secure_boot_mode(self):
        l_secure_mode = self.string_get(self.l_data,
                                        BMC_CONST.SECURE_MODE)
        if l_secure_mode:
            l_secure_mode_status = self.status_finder(l_secure_mode,
                                                      BMC_CONST.ON,
                                                      BMC_CONST.OFF)
            if l_secure_mode_status == BMC_CONST.ON:
                print BMC_CONST.SECURE_MODE_ON
                return BMC_CONST.SECURE_MODE_ON
            elif l_secure_mode_status == BMC_CONST.OFF:
                print BMC_CONST.SECURE_MODE_OFF
                return BMC_CONST.SECURE_MODE_OFF
        else:
            l_msg = "Secure mode enable/disable status not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function collects Trusted boot mode information from OPAL
    # messagelog and if found determines whether it is 'on' or 'off'.
    # Returns TRUSTED_MODE_ON for Trusted boot mode 'on'
    # Returns TRUSTED_MODE_OFF for Trusted boot mode 'off'
    # Raises OpTestError when no information found
    #
    def trusted_boot_mode(self):
        l_trusted_mode = self.string_get(self.l_data,
                                         BMC_CONST.TRUSTED_MODE)
        if l_trusted_mode:
            l_trusted_mode_status = self.status_finder(l_trusted_mode,
                                                       BMC_CONST.ON,
                                                       BMC_CONST.OFF)
            if l_trusted_mode_status == BMC_CONST.ON:
                print BMC_CONST.TRUSTED_MODE_ON
                return BMC_CONST.TRUSTED_MODE_ON
            elif l_trusted_mode_status == BMC_CONST.OFF:
                print BMC_CONST.TRUSTED_MODE_OFF
                return BMC_CONST.TRUSTED_MODE_OFF
        else:
            l_msg = "Trusted mode enable/disable status not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP measured information from OPAL
    # messagelog and if found determines whether it is 'measured' or
    # 'not measured'.
    # Returns CAPP_PAR_MEASURED for CAPP partition measured
    # Returns CAPP_PAR_NOT_MEASURED for CAPP partition not measured
    # Raises OpTestError when no information found
    #
    def capp_measured(self):
        l_capp_measured = self.string_get(self.l_data,
                                          BMC_CONST.CAPP_MEASURED)
        l_capp_not_measured = self.string_get(self.l_data,
                                              BMC_CONST.TB_SKIPPED)
        if l_capp_measured:
            print BMC_CONST.CAPP_PAR_MEASURED
            return BMC_CONST.CAPP_PAR_MEASURED
        elif l_capp_not_measured:
            print BMC_CONST.CAPP_PAR_NOT_MEASURED
            return BMC_CONST.CAPP_PAR_NOT_MEASURED

        l_msg = "CAPP partition measured details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects BOOTKERNEL measured information from OPAL
    # messagelog and if found determines whether it is 'measured' or
    # 'not measured'.
    # Returns BOOTKERNEL_PAR_MEASURED for BOOTKERNEL partition measured
    # Returns BOOTKERNEL_PAR_NOT_MEASURED for BOOTKERNEL partition not measured
    # Raises OpTestError when no information found
    #
    def bootkernel_measured(self):
        l_bk_measured = self.string_get(self.l_data,
                                        BMC_CONST.BOOTKERNEL_MEASURED)
        l_bk_not_measured = self.string_get(self.l_data,
                                            BMC_CONST.TB_SKIPPED)
        if l_bk_measured:
            print BMC_CONST.BOOTKERNEL_PAR_MEASURED
            return BMC_CONST.BOOTKERNEL_PAR_MEASURED
        elif l_bk_not_measured:
            print BMC_CONST.BOOTKERNEL_PAR_NOT_MEASURED
            return BMC_CONST.BOOTKERNEL_PAR_NOT_MEASURED

        l_msg =  "BOOTKERNEL partition measured details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP verified information from OPAL
    # messagelog and if found determines whether it is 'verified' or
    # 'not verified'.
    # Returns CAPP_PAR_VERIFIED for CAPP partition verified
    # Returns CAPP_PAR_NOT_VERIFIED for CAPP partition not verified
    # Raises OpTestError when no information found
    #
    def capp_verified(self):
        l_capp_verified = self.string_get(self.l_data,
                                          BMC_CONST.CAPP_VERIFIED)
        l_capp_not_verified = self.string_get(self.l_data,
                                              BMC_CONST.SB_SKIPPED)
        if l_capp_verified:
            print BMC_CONST.CAPP_PAR_VERIFIED
            return BMC_CONST.CAPP_PAR_VERIFIED
        elif l_capp_not_verified:
            print BMC_CONST.CAPP_PAR_NOT_VERIFIED
            return BMC_CONST.CAPP_PAR_NOT_VERIFIED

        l_msg = "CAPP partition verify details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects BOOTKERNEL verified information from OPAL
    # messagelog and if found determines whether it is 'verified' or
    # 'not verified'.
    # Returns BOOTKERNEL_PAR_VERIFIED for BOOTKERNEL partition verified
    # Returns BOOTKERNEL_PAR_NOT_VERIFIED for BOOTKERNEL partition not verified
    # Raises OpTestError when no information found
    #
    def bootkernel_verified(self):
        l_bk_verified = self.string_get(self.l_data,
                                        BMC_CONST.BOOTKERNEL_VERIFIED)
        l_bk_not_verified = self.string_get(self.l_data,
                                            BMC_CONST.SB_SKIPPED)
        if l_bk_verified:
            print BMC_CONST.BOOTKERNEL_PAR_VERIFIED
            return BMC_CONST.BOOTKERNEL_PAR_VERIFIED
        elif l_bk_not_verified:
            print BMC_CONST.BOOTKERNEL_PAR_NOT_VERIFIED
            return BMC_CONST.BOOTKERNEL_PAR_NOT_VERIFIED

        l_msg = "BOOTKERNEL partition verify details not seen"
        raise OpTestError(l_msg)

    ##
    # @brief This function collects CAPP loaded information from OPAL
    # messagelog and if found determines whether it is 'loaded' or
    # 'not loaded'.
    # Returns CAPP_PAR_LOADED for CAPP partition loaded
    # Returns CAPP_PAR_NOT_LOADED for CAPP partition not loaded
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
                print BMC_CONST.CAPP_PAR_LOADED
                return BMC_CONST.CAPP_PAR_LOADED
            elif l_capp_loaded_status == BMC_CONST.NOT_LOADED:
                print BMC_CONST.CAPP_PAR_NOT_LOADED
                return BMC_CONST.CAPP_PAR_NOT_LOADED
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
    # Returns BOOTKERNEL_PAR_LOADED for BOOTKERNEL partition loaded
    # Returns BOOTKERNEL_PAR_NOT_LOADED for BOOTKERNEL partition not loaded
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
                print BMC_CONST.BOOTKERNEL_PAR_LOADED
                return BMC_CONST.BOOTKERNEL_PAR_LOADED
            elif l_bk_loaded_status == BMC_CONST.NOT_LOADED:
                print BMC_CONST.BOOTKERNEL_PAR_NOT_LOADED
                return BMC_CONST.BOOTKERNEL_PAR_NOT_LOADED
            else:
                print "BOOTKERNEL partition loaded related error occured"
                return BMC_CONST.FW_FAILED
        else:
            l_msg = "BOOTKERNEL partition loaded details not seen"
            raise OpTestError(l_msg)

    ##
    # @brief This function checks for the device-tree node of Trusted boot
    # Returns FW_SUCCESS when TB_DT_ENTRY found
    # Returns FW_FAILED when TB_DT_ENTRY not found
    #
    def proc_tb_verify(self):
        l_cmd = "test -f %s; echo $?" % BMC_CONST.TB_DT_ENTRY
        l_out = self.cv_HOST.host_run_command(l_cmd)
        l_out = l_out.strip("\n\r")
        if int(l_out) == 0:
            print "Trusted Boot device-tree file exists"
            return BMC_CONST.FW_SUCCESS
        else:
            print "No Trusted Boot device-tree file exists"
            return BMC_CONST.FW_FAILED

    ##
    # @brief This function checks for the device-tree node of Secure boot
    # Returns FW_SUCCESS when SB_DT_ENTRY found
    # Returns FW_FAILED when SB_DT_ENTRY not found
    #
    def proc_sb_verify(self):
        l_cmd = "test -f %s; echo $?" % BMC_CONST.SB_DT_ENTRY
        l_out = self.cv_HOST.host_run_command(l_cmd)
        l_out = l_out.strip("\n\r")
        if int(l_out) == 0:
            print "Secure Boot device-tree file exists"
            return BMC_CONST.FW_SUCCESS
        else:
            print "No Secure Boot device-tree file exists"
            return BMC_CONST.FW_FAILED

    ##
    # @brief This function cross verifies the output from hw_sb_support function
    # which reads Secure boot value from SSR value and secure_boot_mode function
    # which reads Secure boot value from OPAL messagelog
    # When both the values are not same then raises OpTestError
    #
    def cross_check_hw_opal_sb(self):
        if self.hw_sb_support() == self.secure_boot_mode():
            print "For Secure boot Both SSR value and OPAL are in sync"
        else:
            l_msg = "For Secure boot Both SSR value and OPAL are NOT in sync"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function cross verifies the output from hw_tb_support function
    # which reads Trusted boot value from SSR value and trusted_boot_mode
    # function, which reads Trusted boot value from OPAL messagelog
    # When both the values are not same then raises OpTestError
    #
    def cross_check_hw_opal_tb(self):
        if self.hw_tb_support() == self.trusted_boot_mode():
            print "For Trusted boot Both hw and opal are in sync"
        else:
            l_msg = "For Trusted boot Both hw and opal are not in sync"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function cross verifies the output from different functions,
    # namely capp_measured, bootkernel_measured,
    # capp_verified, bootkernel_verified,
    # capp_loaded, bootkernel_loaded,
    # And the above values are cross checked with the Secure and Trusted boot
    # modes. As given below.
    #
    # When Secureboot is ON, Trustedboot is ON
    # Partitions are Verified, Measured, Loaded
    #
    # When Secureboot if OFF, Trustedboot is ON
    # Partitions are NOT Verified, Measured, Loaded
    #
    # When Secureboot is ON, Trustedboot is OFF
    # Partitions are Verified, NOT Measured, Loaded
    #
    # When secureboot is OFF, trustedboot is OFF
    # Partitions are NOT Verified, NOT Measured, Loaded
    #
    # In the case of mismatches raises OpTestError
    #
    def cross_check_stb(self):

        l_sb_mode = self.secure_boot_mode()
        l_tb_mode = self.trusted_boot_mode()
        l_capp_measured = self.capp_measured()
        l_bk_measured = self.bootkernel_measured()
        l_capp_verified = self.capp_verified()
        l_bk_verified = self.bootkernel_verified()
        l_capp_loaded = self.capp_loaded()
        l_bootkernel_loaded = self.bootkernel_loaded()

        if l_sb_mode == BMC_CONST.SECURE_MODE_ON and \
           l_tb_mode == BMC_CONST.TRUSTED_MODE_ON:

            print "-" * 40
            print "Secure mode ON and Trusted mode ON"
            l_error = 0
            if l_capp_measured != BMC_CONST.CAPP_PAR_MEASURED:
                l_error = 1
            elif l_bk_measured != BMC_CONST.BOOTKERNEL_PAR_MEASURED:
                l_error = 1
            elif l_capp_verified != BMC_CONST.CAPP_PAR_VERIFIED:
                l_error = 1
            elif l_bk_verified != BMC_CONST.BOOTKERNEL_PAR_VERIFIED:
                l_error = 1
            elif l_capp_loaded != BMC_CONST.CAPP_PAR_LOADED:
                l_error = 1
            elif l_bootkernel_loaded != BMC_CONST.BOOTKERNEL_PAR_LOADED:
                l_error = 1

            print l_capp_measured
            print l_bk_measured
            print l_capp_verified
            print l_bk_verified
            print l_capp_loaded
            print l_bootkernel_loaded
            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == BMC_CONST.SECURE_MODE_OFF and \
           l_tb_mode == BMC_CONST.TRUSTED_MODE_ON:

            print "-" * 40
            print "Secure mode OFF and Trusted mode ON"
            l_error = 0
            if l_capp_measured != BMC_CONST.CAPP_PAR_MEASURED:
                l_error = 1
            elif l_bk_measured != BMC_CONST.BOOTKERNEL_PAR_MEASURED:
                l_error = 1
            elif l_capp_verified == BMC_CONST.CAPP_PAR_VERIFIED:
                l_error = 1
            elif l_bk_verified == BMC_CONST.BOOTKERNEL_PAR_VERIFIED:
                l_error = 1
            elif l_capp_loaded != BMC_CONST.CAPP_PAR_LOADED:
                l_error = 1
            elif l_bootkernel_loaded != BMC_CONST.BOOTKERNEL_PAR_LOADED:
                l_error = 1

            print l_capp_measured
            print l_bk_measured
            print l_capp_verified
            print l_bk_verified
            print l_capp_loaded
            print l_bootkernel_loaded
            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == BMC_CONST.SECURE_MODE_ON and \
           l_tb_mode == BMC_CONST.TRUSTED_MODE_OFF:

            print "-" * 40
            print "Secure mode ON and Trusted mode OFF"
            l_error = 0
            if l_capp_measured == BMC_CONST.CAPP_PAR_MEASURED:
                l_error = 1
            elif l_bk_measured == BMC_CONST.BOOTKERNEL_PAR_MEASURED:
                l_error = 1
            elif l_capp_verified != BMC_CONST.CAPP_PAR_VERIFIED:
                l_error = 1
            elif l_bk_verified != BMC_CONST.BOOTKERNEL_PAR_VERIFIED:
                l_error = 1
            elif l_capp_loaded != BMC_CONST.CAPP_PAR_LOADED:
                l_error = 1
            elif l_bootkernel_loaded != BMC_CONST.BOOTKERNEL_PAR_LOADED:
                l_error = 1

            print l_capp_measured
            print l_bk_measured
            print l_capp_verified
            print l_bk_verified
            print l_capp_loaded
            print l_bootkernel_loaded
            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"

        if l_sb_mode == BMC_CONST.SECURE_MODE_OFF and \
           l_tb_mode == BMC_CONST.TRUSTED_MODE_OFF:

            print "-" * 40
            print "Secure mode OFF and Trusted mode OFF"
            l_error = 0
            if l_capp_measured == BMC_CONST.CAPP_PAR_MEASURED:
                l_error = 1
            elif l_bk_measured == BMC_CONST.BOOTKERNEL_PAR_MEASURED:
                l_error = 1
            elif l_capp_verified == BMC_CONST.CAPP_PAR_VERIFIED:
                l_error = 1
            elif l_bk_verified == BMC_CONST.BOOTKERNEL_PAR_VERIFIED:
                l_error = 1
            elif l_capp_loaded != BMC_CONST.CAPP_PAR_LOADED:
                l_error = 1
            elif l_bootkernel_loaded != BMC_CONST.BOOTKERNEL_PAR_LOADED:
                l_error = 1

            print l_capp_measured
            print l_bk_measured
            print l_capp_verified
            print l_bk_verified
            print l_capp_loaded
            print l_bootkernel_loaded
            print "-" * 40

            if l_error == 1:
                l_msg = "Fail: Some thing went wrong"
                raise OpTestError(l_msg)
            else:
                print "Success: Output is as exptected"
