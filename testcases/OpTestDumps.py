#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestDumps.py $
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

#  @package OpTestDumps
#  Different dumps for fsp platforms
#  fipsdump
#  system dump

import time
import subprocess
import re

from common.OpTestFSP import OpTestFSP
from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError
from common.OpTestHost import OpTestHost
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpTestSystem


class OpTestDumps():
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
    def __init__(self, i_fspIP, i_fspUser, i_fspPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, 
                 i_hostip=None, i_hostuser=None, i_hostPasswd=None):
        self.cv_FSP = OpTestFSP(i_fspIP, i_fspUser, i_fspPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_fspIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_HOST = OpTestHost(i_hostip, i_hostuser, i_hostPasswd,i_fspIP, i_ffdcDir)
        self.util = OpTestUtil()


    ##
    # @brief This function tests system dump functionality
    #        1. Boot the system to runtime(Atleast to petitboot)
    #        2. Trigger system dump from FSP
    #        3. Wait for dump to finish & IPL to reach runtime
    #        4. Check for system dump files in host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_system_dump(self):
        self.cv_HOST.host_check_command("opal-dump-parse")
        self.cv_HOST.host_run_command("rm -rf /var/log/dump/SYSDUMP* \r")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        print self.cv_FSP.fsp_run_command("smgr mfgState")
        self.cv_FSP.clear_fsp_errors()
        self.cv_FSP.power_off_sys()
        self.cv_FSP.power_on_sys()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_FSP.trigger_system_dump()
        self.cv_FSP.wait_for_systemdump_to_finish()
        self.cv_FSP.wait_for_runtime()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        time.sleep(BMC_CONST.HOST_BRINGUP_TIME)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.cv_HOST.host_run_command("ls /var/log/dump")
        res = self.cv_HOST.host_run_command("opal-dump-parse -l /var/log/dump/SYSDUMP*")
        print res
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_run_command("dmesg")
        if "Opal" in res:
            print "sysdump test completed successfully"
        else:
            raise OpTestError("sysdump test failed in dumping Opal-log section")


    ##
    # @brief This function tests fipsdump functionality
    #        1. Generate from FSP & verify against host data
    #        2. Generate from Host & verify against fsp data
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def test_fipsdump(self):
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        self.cv_FSP.list_all_fipsdumps_in_fsp()
        self.cv_FSP.clear_all_fipsdumps_in_fsp()
        self.cv_HOST.host_clear_all_dumps()
        # Check the status of opal_errd daemon.
        if self.cv_HOST.host_get_status_of_opal_errd_daemon():
            print "Opal_errd daemon is running"
        else:
            raise OpTestError("Opal_errd daemon is not running in host OS")
        count = 0
        while(count < 10):
            print "=========================================Iteration : %d=========================================" % count
            print "==================================fipsdump initiation from FSP================================="
            dumpname, size = self.cv_FSP.trigger_fipsdump_in_fsp()
            self.verify_fipsdump(dumpname, size)
            count += 1

            print "==================================fipsdump initiation from HOST================================"
            dumpname, size = self.fipsdump_initiate_from_host()
            self.verify_fipsdump(dumpname, size)
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_run_command("dmesg")
        print "fipsdump test executed successfully"

    def fipsdump_initiate_from_host(self):
        dumpname = self.cv_FSP.fsp_run_command("fipsdump -l | sed 's/\ .*//'")
        self.cv_HOST.host_run_command('echo 1 > /sys/firmware/opal/dump/initiate_dump')
        time.sleep(60)
        new_dumpname = self.cv_FSP.fsp_run_command("fipsdump -l | sed 's/\ .*//'")
        if dumpname != new_dumpname:
            print 'New dump %s generated, when initiated from host ' % new_dumpname
            res = self.cv_HOST.host_run_command('ls /var/log/dump')
            if res.__contains__(new_dumpname):
                print "fips dump transfered to host"
            else:
                raise OpTestError("fips dump file transfer to host is failed when initiates from host")
        else:
            raise OpTestError('fpsdump initation from host failed to initiate')
        size_fsp = self.cv_FSP.fsp_run_command("fipsdump -l | awk '{print $2}'")
        return new_dumpname, size_fsp

    def verify_fipsdump(self, dumpname, size_fsp):
        res = self.cv_HOST.host_run_command('ls /var/log/dump')
        if res.__contains__(dumpname):
            print "FSP dump generated"
        else:
            raise OpTestError("FSP Dump file transfer to host is failed when initiates from fsp")
        cmd = "ls /var/log/dump/%s -l| awk '{print $5}'" % dumpname
        size_host = (self.cv_HOST.host_run_command(cmd)).strip()
        if size_fsp.__contains__(size_host):
            print "Total size of FSP dump file transfered to host from fsp"
        else:
            raise OpTestError("Total size of FSP dump file is not transfered to host from fsp")
