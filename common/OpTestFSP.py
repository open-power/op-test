#!/usr/bin/env python2
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

'''
OpTestFSP: talk to the FSP
--------------------------

This class can contains common functions which are useful for
FSP platforms, mostly things that execute shell commands on
the FSP itself. There is (currently) no differentiation between
commands that require the NFS mount and ones that don't, we
assume (and check for) the NFS mount.
'''

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


class OpTestFSP():
    '''
    Contains most of the common methods to interface with FSP.
    '''

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

    def fsp_get_console(self):
        '''
        Get FSP telnet console
        '''
        print "Disabling the firewall before running any FSP commands"
        self.cv_ASM.disablefirewall()
        self.fspc = TConnection(self.host_name, self.user_name, self.password, self.prompt)
        self.fspc.login()
        self.fsp_name = self.fspc.run_command("hostname")
        print "Established Connection with FSP: {0} ".format(self.fsp_name)

    def fsp_run_command(self, command):
        '''
        Execute and return the output of an FSP command
        '''
        res = self.fspc.run_command(command)
        return res

    def reboot(self):
        '''
        Currently a no-op. FSP "reset-reload" (i.e. reboot) tests
        are covered in the fspresetReload test, as the process for
        rebooting an FSP isn't a simple 'reboot' (because reasons).
        '''
        pass
        return True

    def get_progress_code(self):
        '''
        Get IPL progress code
        '''
        tmp = self.fspc.run_command("ls /opt/p1/srci/curripl")
        tmp = tmp.split('.')
        if len(tmp) == 3:
            return tmp[2]
        else:
            return str(tmp)

    def is_sys_powered_on(self):
        '''
        Check for system runtime state.
        Returns True if runtime, else False.
        '''
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        if state == 'runtime':
            return True
        else:
            return False

    def is_sys_standby(self):
        '''
        Check for system standby state.
        Returns True if system is in standby state else False.
        '''
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        if state == 'standby':
            return True
        else:
            return False

    def get_sys_status(self):
        '''
        Get current system status (same as 'smgr mfgState' on FSP).
        '''
        state = self.fspc.run_command("smgr mfgState")
        state = state.rstrip('\n')
        return state

    def get_opal_console_log(self):
        '''
        Get OPAL log from in memory console (using getmemproc on FSP).
        '''
        if self.is_sys_powered_on() > 0:
            output = self.fspc.run_command("getmemproc 31000000 40000 -fb /tmp/con && cat /tmp/con")
        else:
            output=''
        return output

    def clear_fsp_errors(self):
        '''
        Clear all FSP errors: error logs, gards, fipsdumps, and sysdumps.
        '''
        #clear errl logs
        self.fspc.run_command("errl -p")
        #clear gard
        self.fspc.run_command("gard --clr all")

        #clear fipsdump
        self.fspc.run_command("fipsdump -i")

        #clear sysdump
        self.fspc.run_command("sysdump -idall")
        return True

    def power_off_sys(self):
        '''
        Power off the system and wait for standby state.
        Returns True if successfully powered off, False if for some
        reason we failed to power off the system.
        '''
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

    def power_on_sys(self):
        '''
        Power on the system and wait for system to reach runtime in
        OPAL mode (will switch HypMode before IPL if needed).
        Returns True if we reach Runtime state, False otherwise.
        '''
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

    def fsp_reset(self):
        '''
        FSP Tool Reset.
        '''
        print "Issuing fsp Reset...."
        self.fspc.issue_forget("smgr toolReset")
        print "FSP reset Done, Hope POWER comes back :) "

    def mount_exists(self):
        '''
        Checks for NFS mount on FSP. Returns True/False.
        '''
        print "Checking for NFS mount..."
        res = self.fspc.run_command("which putmemproc;echo $?")
        if int(res[-1]) == 0:
            print "NFS mount available in FSP"
            return True
        else:
            print "NFS mount is not available in FSP"
            return False

    def wait_for_standby(self, timeout=10):
        '''
        Wait for system standby state. Returns 0 on success,
        throws exception on error.
        '''
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

    def wait_for_ipling(self, timeout=10):
        '''
        Wait for system to reach ipling state.
        Throws exception on error.
        '''
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

    def wait_for_runtime(self, timeout=10):
        '''
        Wait for system to reach runtime. Throws exception on error.
        '''
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

    def trigger_system_dump(self):
        '''
        Trigger a system dump from FSP, by writing a magic value to a memory
        location looked at by OPAL.
        '''
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

    def wait_for_systemdump_to_finish(self):
        '''
        Wait for a system dump to finish. Throws exception on error/timeout.
        '''
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

    def trigger_fipsdump_in_fsp(self):
        '''
        Initiate a FIPS dump (fsp dump). Returns (name of dump, size of dump).
        '''
        print "FSP: Running the command 'fipsdump -u'"
        state = self.fspc.run_command("fipsdump -u")
        time.sleep(60)
        dumpname = self.fspc.run_command("fipsdump -l | sed 's/\ .*//'")
        print "fipsdump name : %s" % dumpname
        size_fsp = self.fspc.run_command("fipsdump -l | awk '{print $2}'")
        return dumpname, size_fsp

    def list_all_fipsdumps_in_fsp(self):
        '''
        List all FSP dumps (FIPS dumps) on FSP
        '''
        print "FSP: List all fipsdumps"
        cmd = "fipsdump -l"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    def clear_all_fipsdumps_in_fsp(self):
        '''
        Clear all FIPS dumps
        '''
        cmd = "fipsdump -i"
        print "FSP: Clearing all the fipsdump's in fsp"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    def generate_error_log_from_fsp(self):
        '''
        Generate a sample error log from fsp.
        Returns True on success or raises exception on error.
        '''
        cmd = "errl -C --comp=0x4400 --etype=021 --refcode=04390 --sev=0x20 --commit=0x2000;echo $?"
        print "FSP: Generating error log using errl command"
        print "FSP: Running the command %s on fsp" % cmd
        res = self.fspc.run_command(cmd)
        if res == "0":
            print "FSP: error log generated successfully"
            return True
        else:
            raise OpTestError("FSP: Failure in error log generation from FSP")

    def list_all_errorlogs_in_fsp(self):
        '''
        List all error logs on FSP.
        '''
        print "FSP: List all error logs"
        cmd = "errl -l"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res

    def clear_errorlogs_in_fsp(self):
        '''
        Clear all error logs from fsp. Throws exception on error.
        '''
        cmd = "errl -p"
        print "Running the command %s on FSP" % cmd
        res = self.fspc.run_command(cmd)
        print res
        if "ERRL repository purged all entries successfully" in res:
            print "FSP: Error logs are cleared successfully"
            return True
        else:
            raise OpTestError("FSP: Error logs are not getting cleared in FSP")

    def get_raw_mtm(self):
        '''
        Get MTM (Machine Type Model) from FSP from FSP registry.
        '''
        self.fsp_MTM = self.fspc.run_command("registry -r svpd/Raw_MachineTypeModel")
        return self.fsp_MTM

    def fsp_issue_power_on(self):
        '''
        Issue Power On for system from FSP (IPL type 0x01).
        '''
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

    def supports_ipmi_dcmi(self):
        return True
