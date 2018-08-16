#!/usr/bin/env python2
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2017
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

#  Different dumps for fsp platforms
#  fipsdump
#  system dump
#      host_dump_boottime --> Trigger dump when kernel boots(either Petitboot or OS kernel)
#      host_dump_runtime  --> Trigger dump when system is in OS or already booted to OS
#      nmi_dump           --> Trigger system dump by sending NMI interrupts to processors
#

import time
import subprocess
import re

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestDumps():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.util = self.cv_SYSTEM.util
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()

    def trigger_dump(self):
        if self.test == "nmi_dump":
            self.cv_IPMI.ipmi_power_diag()
        elif "host_dump" in self.test:
            self.cv_FSP.trigger_system_dump()
        else:
            raise Exception("Unknown test type")

    def fipsdump_initiate_from_host(self):
        dumpname = self.cv_FSP.fsp_run_command("fipsdump -l | sed 's/\ .*//'")
        self.cv_HOST.host_run_command('echo 1 > /sys/firmware/opal/dump/initiate_dump')
        dumping = False
        # Wait for fips dump to finish
        tries = 36
        i = 0
        for i in range(1, tries+1):
            if i == 1:
                res = self.cv_FSP.fsp_run_command("fipsdump -l")
            else: 
                time.sleep(5)
                res = self.cv_FSP.fsp_run_command("fipsdump -l")
            if "Dump In Progress" in res:
                dumping = True
                continue
            if dumping and "Dump Was Invalidated" in res:
                break
            time.sleep(5)
        # Dump not started case
        self.assertTrue(dumping,
            "fipsdump initation from host failed to initiate")

        # Timeout case(Usually it is taking less than one minute(around 40s))
        self.assertNotEqual(i, tries, "FipS dump taking more than 3 mins")
        new_dumpname = self.cv_FSP.fsp_run_command("fipsdump -l | sed 's/\ .*//'")
        self.assertNotEqual(dumpname, new_dumpname,
            "fipsdump initation from host failed to initiate")

        # Wait for fipsdump to transfer to host
        tries = 20
        for j in range(1, tries):
            time.sleep(4)
            res = self.cv_HOST.host_run_command('ls /var/log/dump')
            if '\n'.join(res).__contains__(new_dumpname):
                log.debug("fips dump transfered to host")
                break
        self.assertIn(new_dumpname, res,
            "fips dump file transfer to host is failed when initiates from host")
        size_fsp = self.cv_FSP.fsp_run_command("fipsdump -l | awk '{print $2}'")
        return new_dumpname, size_fsp

    def verify_fipsdump(self, dumpname, size_fsp):
        tries = 20
        for j in range(1, tries):
            time.sleep(5)
            res = self.cv_HOST.host_run_command('ls /var/log/dump')
            if '\n'.join(res).__contains__(dumpname):
                log.debug("FipS dump transfered to Host")
                break
        self.assertIn(dumpname, '\n'.join(res),
            "fips dump file transfer to host is failed when initiates from host")
        cmd = "ls /var/log/dump/%s -l| awk '{print $5}'" % dumpname
        size_host = '\n'.join((self.cv_HOST.host_run_command(cmd))).strip()
        if size_fsp.__contains__(size_host):
            log.debug("Total size of FSP dump file transfered to host from fsp")
        else:
            raise OpTestError("Total size of FSP dump file is not transfered to host from fsp")


class SYSTEM_DUMP(OpTestDumps, unittest.TestCase):

    ##
    # @brief This function tests system dump functionality
    #        1. Boot the system to runtime(Atleast to petitboot)
    #        2. Trigger system dump from FSP
    #        3. Wait for dump to finish & IPL to reach runtime
    #        4. Check for system dump files in host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific dump tests")
        self.cv_HOST.host_check_command("opal-dump-parse")
        self.cv_HOST.host_run_command("rm -rf /var/log/dump/SYSDUMP*")
        self.cv_HOST.host_run_command("rm -rf /var/log/dump/Opal-log*")
        self.cv_HOST.host_run_command("rm -rf /var/log/dump/HostBoot-Runtime-log*")
        self.cv_HOST.host_run_command("rm -rf /var/log/dump/printk*")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        self.set_up()
        state = self.cv_FSP.fsp_run_command("smgr mfgState")
        log.debug(state)
        self.cv_FSP.enable_system_dump()
        self.cv_FSP.clear_fsp_errors()
        if "host_dump_boottime" in self.test:
            self.cv_FSP.power_off_sys()
            self.cv_FSP.power_on_sys()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        self.trigger_dump()
        self.cv_FSP.wait_for_systemdump_to_finish()
        self.cv_FSP.wait_for_runtime()
        console = self.cv_SYSTEM.console.get_console()
        console.sendline()
        console.expect("login:", timeout=600)
        console.close()
        self.cv_HOST.ssh.close()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
        res = self.cv_HOST.host_run_command("ls /var/log/dump")
        log.debug(res)
        res = self.cv_HOST.host_run_command("opal-dump-parse -l /var/log/dump/SYSDUMP*")
        log.debug(res)
        self.assertIn("Opal", '\n'.join(res), "sysdump test failed in dumping Opal-log section")
        self.assertIn("HostBoot-Runtime-log", '\n'.join(res), "sysdump test failed in dumping HBRT section")
        self.assertIn("printk", '\n'.join(res), "sysdump test failed in dumping printk section")
        self.cv_HOST.host_run_command("cd /var/log/dump/")
        self.cv_HOST.host_run_command("opal-dump-parse -s 1 /var/log/dump/SYSDUMP*")
        self.cv_HOST.host_run_command("cat Opal-log*")
        self.cv_HOST.host_run_command("opal-dump-parse -s 2  /var/log/dump/SYSDUMP*")
        self.cv_HOST.host_run_command("cat HostBoot-Runtime-log*")
        self.cv_HOST.host_run_command("opal-dump-parse -s 128 /var/log/dump/SYSDUMP*")
        self.cv_HOST.host_run_command("cat printk*")


class FIPS_DUMP(OpTestDumps, unittest.TestCase):

    ##
    # @brief This function tests fipsdump functionality
    #        1. Generate from FSP & verify against host data
    #        2. Generate from Host & verify against fsp data
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific dump tests")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and retry the test")

        self.cv_FSP.list_all_fipsdumps_in_fsp()
        self.cv_FSP.clear_all_fipsdumps_in_fsp()
        self.cv_HOST.host_clear_all_dumps()
        # Check the status of opal_errd daemon.
        if self.cv_HOST.host_get_status_of_opal_errd_daemon():
            log.debug("Opal_errd daemon is running")
        else:
            raise OpTestError("Opal_errd daemon is not running in host OS")
        count = 0
        while(count < 2):
            log.debug("===========================Iteration : %d===============================" % count)
            log.debug("======================fipsdump initiation from FSP=========================")
            dumpname, size = self.cv_FSP.trigger_fipsdump_in_fsp()
            self.verify_fipsdump(dumpname, size)
            count += 1

            log.debug("========================fipsdump initiation from HOST============================")
            dumpname, size = self.fipsdump_initiate_from_host()
            self.verify_fipsdump(dumpname, size)

class HOST_DUMP_BOOTTIME(SYSTEM_DUMP):

    def set_up(self):
        self.test = "host_dump_boottime"

class HOST_DUMP_RUNTIME(SYSTEM_DUMP):

    def set_up(self):
        self.test = "host_dump_runtime"


class NMI_DIAG_DUMP(SYSTEM_DUMP):

    def set_up(self):
        self.test = "nmi_dump"

def suite():
    s = unittest.TestSuite()
    s.addTest(FIPS_DUMP())
    s.addTest(HOST_DUMP_RUNTIME())
    s.addTest(NMI_DIAG_DUMP())
    s.addTest(HOST_DUMP_BOOTTIME())
    return s
