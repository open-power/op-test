#!/usr/bin/python2
# encoding=utf8
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestFSP.py $
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

## @package OpTestFSP
#  This class can contains common functions which are useful for 
#  FSP platforms

import time
import subprocess
import os
import pexpect
import sys
import commands

from OpTestTConnection import TConnection
from OpTestASM import OpTestASM
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError

Possible_Hyp_value = {'01': 'PowerVM', '03': 'PowerKVM'}
Possible_Sys_State = {'terminated':0, 'standby':1, 'prestandby':2, 'ipling':3, 'runtime':4}

#Contains most of the common methods to interface with FSP.
class OpTestFSP():

    ##
    # @brief Initialize this object
    #
    # @param i_fspIP @type string: IP Address of the FSP
    # @param i_fspUser @type string: Userid to log into the FSP
    # @param i_fspPasswd @type string: Password of the userid to log into the FSP
    #
    def __init__(self, i_fspIP, i_fspUser, i_fspPasswd, ipmi=None, rest=None):
        self.host_name = i_fspIP
        self.user_name = i_fspUser
        self.password = i_fspPasswd
        self.prompt = "$"
        self.cv_ASM = OpTestASM(i_fspIP, i_fspUser, i_fspPasswd)
        self.cv_IPMI = ipmi
        self.rest = rest

    def bmc_host(self):
        return self.cv_ASM.host_name

    def get_ipmi(self):
        return self.cv_IPMI

    def get_rest_api(self):
        return self.rest

    def get_host_console(self):
        return self.cv_IPMI.get_host_console()

    ##
    # @brief Get FSP telnet console
    #
    def fsp_get_console(self):
        print "Disabling the firewall before running any FSP commands"
        self.cv_ASM.disablefirewall()
        self.fspc = TConnection(self.host_name, self.user_name, self.password, self.prompt)
        self.fspc.login()
        self.fsp_name = self.fspc.run_command("hostname")
        print "Established Connection with FSP: {0} ".format(self.fsp_name)

    ##
    # @brief Execute and return the output of an FSP command
    #
    # @param command @type string: Command to execute in FSP
    #
    # @returns res @type string: output of command
    #
    def fsp_run_command(self, command):
        res = self.fspc.run_command(command)
        return res

    def reboot(self):
        pass # fsp rr tests are covered in fspresetReload test
        return True

    ##
    # @brief Get IPL progress codes
    # @returns string: ipl progress code
    #
    def get_progress_code(self):
        tmp = self.fspc.run_command("ls /opt/p1/srci/curripl")
        tmp = tmp.split('.')
        if len(tmp) == 3:
            return tmp[2]
        else:
            return str(tmp)

    ##
    # @brief Check for system runtime state
    # @returns True if system is in runtime else False
    #
    def is_sys_powered_on(self):
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        if state == 'runtime':
            return True
        else:
            return False
    ##
    # @brief Check for system standby state
    # @returns True if system is in standby state else False
    #
    def is_sys_standby(self):
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        if state == 'standby':
            return True
        else:
            return False

    ##
    # @brief Get current system status
    # @returns string: current system state
    #
    def get_sys_status(self):
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        return state

    ##
    # @brief Get OPAL log from in memory console
    # @returns string: opal log or empty
    #
    def get_opal_console_log(self):
        if self.is_sys_powered_on() > 0:
            output = self.fspc.run_command("getmemproc 31000000 40000 -fb /tmp/con && cat /tmp/con")
        else:
            output=''
        return output

    ##
    # @brief Clear all fsp errors
    # @returns True if all commands executed.
    #
    def clear_fsp_errors(self):
        #clear errl logs
        self.fspc.run_command("errl -p")
        #clear gard
        self.fspc.run_command("gard --clr all")

        #clear fipsdump
        self.fspc.run_command("fipsdump -i")

        #clear sysdump
        self.fspc.run_command("sysdump -idall")
        return True

    ##
    # @brief Power off the system and wait for standby state
    # @returns True: If system reached to standby state
    #          False:If system fails to reach standby.
    #
    def power_off_sys(self):
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        if state == 'standby':
            return True
        elif state == 'runtime' or state == 'ipling':
            print "Powering off, current state: "+state
            output = self.fspc.run_command("panlexec -f 8")
            output = output.rstrip('\n')
            if output.find("success"):
                print "Waiting for system to reach standby..."
                while not self.is_sys_standby():
                    time.sleep(5)
                print "Powered OFF"
                return True
            else:
                print "Power OFF failed"
                print output
                return False
        else:
            return False

    ##
    # @brief Power on the system & wait for system to reach runtime
    # @returns True: If system reaches to runtime state
    #          False:If system fails to reach runtime
    #
    def power_on_sys(self):
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        time_me = 0
        if state == 'standby':
            # just make sure we are booting in OPAL mode
            if self.fspc.run_command("registry -Hr menu/HypMode") != '03':
                print "Not in OPAL mode, switching to OPAL Hypervisor mode"
                self.fspc.run_command("registry -Hw menu/HypMode 03")
            print "Powering on the system: " + state
            output = self.fspc.run_command("plckIPLRequest 0x01")
            output = output.rstrip('\n')
            if output.find("success"):
                print "Waiting for system to reach runtime..."
                while not self.is_sys_powered_on():
                    print "Current system state: {0}, progress code: {1} ".format(self.get_sys_status(), self.get_progress_code())
                    time_me += 5
                    if time_me > 1200:
                        print "System not yet runtime even after 20minutes?"
                        print "Lets consider this as failed case and return"
                        return False
                    else:
                        time.sleep(5)
                print "PowerOn Successful"
                print "System at runtime and current progress code: "+self.get_progress_code()
                return True
            else:
                print "Poweron Failed"
                print "Last know Progress code:"+self.get_progress_code()
                print output
                return False

        elif state == 'runtime':
            return False
        elif state == 'terminated':
            return False
        elif state == 'prestandby':
            return False
        else:
            return False

    ##
    # @brief Issue fsp reset
    #
    def fsp_reset(self):
        print "Issuing fsp Reset...."
        self.fspc.issue_forget("smgr toolReset")
        print "FSP reset Done, Hope POWER comes back :) "

    ##
    # @brief Check for nfs mount exists in fsp.
    # @returns True : if nfs mount exist
    #          False: if doesn't exist
    #
    def mount_exists(self):
        print "Checking for NFS mount..."
        res = self.fspc.run_command("which putmemproc;echo $?")
        if int(res[-1]) == 0:
            print "NFS mount available in FSP"
            return True
        else:
            print "NFS mount is not available in FSP"
            return False
    ##
    # @brief Wait for system standby state
    # @returns 0 on success or throws exception
    #
    def wait_for_standby(self, timeout=10):
        timeout = time.time() + 60*timeout
        while True:
            if self.is_sys_standby():
                print "Current system status: %s" % self.get_sys_status()
                print "Current progress code: %s" % self.get_progress_code()
                break
            print "Current system status: %s" % self.get_sys_status()
            print "Current progress code: %s" % self.get_progress_code()
            if time.time() > timeout:
                l_msg = "Standby timeout"
                raise OpTestError(l_msg)
            time.sleep(BMC_CONST.SHORT_WAIT_STANDBY_DELAY)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief Wait for system to reach ipling state
    # @returns 0 on success or throws exception
    #
    def wait_for_ipling(self, timeout=10):
        timeout = time.time() + 60*timeout
        while True:
            if self.get_sys_status() == "ipling":
                print "Current system status: %s" % self.get_sys_status()
                print "Current progress code: %s" % self.get_progress_code()
                break
            print "Current system status: %s" % self.get_sys_status()
            print "Current progress code: %s" % self.get_progress_code()
            if time.time() > timeout:
                l_msg = "IPL timeout"
                raise OpTestError(l_msg)
            time.sleep(5)
        return BMC_CONST.FW_SUCCESS

    def wait_for_dump_to_start(self):
        count = 0
        # Dump maximum can start in one minute(So lets wait for 3 mins)
        while count < 3:
            if self.get_sys_status() == "dumping":
                return True
            count += 1
            time.sleep(60)
        else:
            print "Current system status: %s" % self.get_sys_status()
            print "Current progress code: %s" % self.get_progress_code()
            raise OpTestError("System dump not started even after 3 minutes")


    ##
    # @brief Wait for system to reach runtime
    # @returns 0 on success or throws exception
    #
    def wait_for_runtime(self, timeout=10):
        timeout = time.time() + 60*timeout
        while True:
            if self.is_sys_powered_on():
                print "Current system status: %s" % self.get_sys_status()
                print "Current progress code: %s" % self.get_progress_code()
                break
            print "Current system status: %s" % self.get_sys_status()
            print "Current progress code: %s" % self.get_progress_code()
            if time.time() > timeout:
                l_msg = "IPL timeout"
                raise OpTestError(l_msg)
            time.sleep(5)
        return BMC_CONST.FW_SUCCESS

    def enable_system_dump(self):
        print "Enabling the system dump policy"
        self.fspc.run_command("sysdump -sp enableSys")
        res = self.fspc.run_command("sysdump -vp")
        if "System dumps             Enabled       Enabled" in res:
            print "System dump policy enabled successfully"
            return True
        raise OpTestError("Failed to enable system dump policy")

    ##
    # @brief Trigger system dump from fsp
    # @returns True on success or raises exception
    #
    def trigger_system_dump(self):
        if self.mount_exists():
            state = self.fspc.run_command("putmemproc 300000f8 0xdeadbeef")
            state = state.strip('\n')
            print 'Status of the putmemproc command %s' % state
            if 'k0:n0:s0:p00' in state:
                print "Successfully triggered the sysdump from FSP"
                return True
            else:
                raise OpTestError("FSP failed to trigger system dump")
        else:
            raise OpTestError("Check LCB nfs mount point and retry")

    ##
    # @brief Wait for system dump to finish
    # @returns True on success or throws exception
    #
    def wait_for_systemdump_to_finish(self):
        self.wait_for_dump_to_start()
        # If dump starts then wait for finish it
        count = 0
        while count < 30:
            res = self.fspc.run_command("sysdump -qall")
            if 'extractable' in res:
                print "Sysdump is available completely and extractable."
                break
            print "Dumping is still in progress"
            time.sleep(60)
            count += 1
        else:
            raise OpTestError("Even after a wait of 30 mins system dump is not available!")
        return True

    ##
    # @brief Initiate fipsdump
    # @returns dumpname: name of new dump
    #          size_fsp: size of the dump
    #
    def trigger_fipsdump_in_fsp(self):
        print "FSP: Running the command 'fipsdump -u'"
        state = self.fspc.run_command("fipsdump -u")
        time.sleep(60)
        dumpname = self.fspc.run_command("fipsdump -l | sed 's/\ .*//'")
        print "fipsdump name : %s" % dumpname
        size_fsp = self.fspc.run_command("fipsdump -l | awk '{print $2}'")
        return dumpname, size_fsp

    ##
    # @brief List all fipsdumps in fsp
    #
    def list_all_fipsdumps_in_fsp(self):
        print "FSP: List all fipsdumps"
        cmd = "fipsdump -l"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    ##
    # @brief Clear all fipsdumps in fsp
    # 
    def clear_all_fipsdumps_in_fsp(self):
        cmd = "fipsdump -i"
        print "FSP: Clearing all the fipsdump's in fsp"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    ##
    # @brief Generate a sample error log from fsp
    # @returns True on success or raises exception
    #
    def generate_error_log_from_fsp(self):
        cmd = "errl -C --comp=0x4400 --etype=021 --refcode=04390 --sev=0x20 --commit=0x2000;echo $?"
        print "FSP: Generating error log using errl command"
        print "FSP: Running the command %s on fsp" % cmd
        res = self.fspc.run_command(cmd)
        if res == "0":
            print "FSP: error log generated successfully"
            return True
        else:
            raise OpTestError("FSP: Failure in error log generation from FSP")

    ##
    # @brief List all error logs from fsp
    # 
    def list_all_errorlogs_in_fsp(self):
        print "FSP: List all error logs"
        cmd = "errl -l"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    ##
    # @brief Clear all error logs from fsp
    # @returns True on success or raises exception
    #
    def clear_errorlogs_in_fsp(self):
        cmd = "errl -p"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res
        if "ERRL repository purged all entries successfully" in res:
            print "FSP: Error logs are cleared successfully"
            return True
        else:
            raise OpTestError("FSP: Error logs are not getting cleared in FSP")

    ##
    # @brief Get machine type model from fsp
    # @returns string or raises exception
    #
    def get_raw_mtm(self):
        self.fsp_MTM = self.fspc.run_command("registry -r svpd/Raw_MachineTypeModel")
        return self.fsp_MTM

    ##
    # @brief Power on system from fsp
    # @returns None or raises exception
    #
    def fsp_issue_power_on(self):
        print "PowerOn Machine"
        output = self.fspc.run_command("plckIPLRequest 0x01")
        if "SUCCESS" in output:
            return
        else:
            raise OpTestError("Failed to power on the machine from FSP")

    def has_inband_bootdev(self):
        return True

    def has_os_boot_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False
