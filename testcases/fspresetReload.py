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

#  @package fspresetReload
#  FSP initiated reset
#  Host initiated reset
#   Once reset is done, verify host-fsp firmware interfaces

import time
import subprocess
import re

from common.OpTestIPMI import OpTestIPMI
from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

class fspresetReload(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_FSP = self.cv_SYSTEM.bmc
        self.cv_HOST = conf.host()
        self.util = self.cv_SYSTEM.util
        self.bmc_type = conf.args.bmc_type
        self.cv_SYSTEM.goto_state(OpSystemState.OS)

    def tearDown(self):
        self.cv_HOST.host_gather_opal_msg_log()
        self.cv_HOST.host_gather_kernel_log()

    def number_of_resets(self):
        return 1

    # FSP initiated reset(FIR)
    def trigger_fir(self):
        cmd = "smgr resetReload"
        print "Running the cmd %s on FSP" % cmd
        self.cv_FSP.fspc.issue_forget(cmd)

    # Host initiated reset(HIR)
    def trigger_hir(self):
        cmd = "putmemproc 300000f8 0x00000000deadbeef"
        print "Running the cmd %s on FSP" % cmd
        self.cv_FSP.fspc.issue_forget(cmd)

    # Surveilance ACK timeout initiated reset(HIR)
    def trigger_sir(self):
        cmd = "ps aux | grep -i survserver | head -1 | awk {'print $2'}"
        print "Running the cmd %s on FSP" % cmd
        res = self.cv_FSP.fsp_run_command(cmd)
        cmd = "kill -9 %s" % res.rstrip('\n')
        print "Running the cmd %s on FSP" % cmd
        self.cv_FSP.fspc.issue_forget(cmd)

    def trigger_rr(self):
        if self.test == "fir":
            self.trigger_fir()
        elif self.test == "hir":
            self.trigger_hir()
        elif self.test == "sir":
            self.trigger_sir()
        else:
            raise Exception("Unknown fsp rr test type")

    def wait_for_fsp_ping(self):
        self.util.PingFunc(self.cv_FSP.host_name, BMC_CONST.PING_RETRY_POWERCYCLE)

    # Wait for psi link active
    def check_psi_link_active(self):
        tries = 120
        for i in range(0, tries):
            if self.look_for_in_opal_log("Found active link!"):
                return True
            time.sleep(5)
        return False

    # check the surveilance b/w opal and fsp
    def check_for_surveillance(self):
        tries = 20
        for i in range(0, tries):
            if self.look_for_in_opal_log("Received heartbeat acknowledge from FSP"):
                return True
            time.sleep(6)
        return False

    # check for inband ipmi interface
    def check_for_inbandipmi(self):
        try:
            self.cv_HOST.host_run_command("ipmitool sensor list")
        except CommandFailed as cf:
            print str(cf)
            return False
        return True

    # check for in-band sensors
    def check_for_sensors(self):
        try:
            self.cv_HOST.host_run_command("sensors")
        except CommandFailed as cf:
            print str(cf)
            return False
        return True

    # check for nvram interface
    def check_for_nvram(self):
        try:
            self.cv_HOST.host_run_command("nvram --update-config test-cfg-rr=test-value")
        except CommandFailed as cf:
            print str(cf)
            return False
        try:
            output = self.cv_HOST.host_run_command("nvram --print-config")
        except CommandFailed as cf:
            print str(cf)
            return False
        if "test-cfg-rr=test-value" in ' '.join(output):
            return True
        return False

    # check for sol console, whether we are able to use or not
    def check_for_sol_console(self):
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        l_con = self.cv_SYSTEM.sys_get_ipmi_console()
        r = l_con.run_command("echo 'Hello World'")
        self.assertIn("Hello World", r)
        try:
            r = l_con.run_command("false")
        except CommandFailed as r:
            self.assertEqual(r.exitcode, 1)

    # check RTC TOD read/write interface
    def check_for_rtc(self):
        try:
            self.cv_HOST.host_read_hwclock()
            self.cv_HOST.host_set_hwclock_time("2015-01-01 10:10:10")
        except CommandFailed as cf:
            print str(cf)
            return False
        return True

    # Check all these fsp-host interfaces are working fine after fsp rr
    def check_for_fsp_host_interfaces(self):
        self.assertTrue(self.check_psi_link_active(), "PSI Link is not active after fsp rr")
        self.assertTrue(self.check_for_surveillance(), "Surveilance failed after fsp rr")
        self.assertTrue(self.check_for_rtc(), "Set/Read HW Clock failed after fsp rr")
        self.assertTrue(self.check_for_inbandipmi(), "inband ipmi interface failed after fsp rr")
        self.assertTrue(self.check_for_sensors(), "inband sensors failed after fsp rr")
        self.assertTrue(self.check_for_nvram(), "nvram interface failed after fsp rr")
        try:
            self.check_for_sol_console()
        except:
            pass


    def look_for_in_opal_log(self, pattern):
        try:
            output = self.cv_HOST.host_run_command("cat /sys/firmware/opal/msglog | diff - /tmp/opal_msglog")
        except CommandFailed as cf:
            if cf.exitcode == 1:
                output = cf.output
        for line in output:
            if len(line) and (line.find(pattern) > 0 ):
                return True
        return False

    def prepare_opal_log(self):
        self.cv_HOST.host_run_command("cat /sys/firmware/opal/msglog > /tmp/opal_msglog")

    def gather_opal_errors(self):
        cmd = "cat /sys/firmware/opal/msglog | diff - /tmp/opal_msglog | grep ',[0-4]\]'"
        try:
            output = self.cv_HOST.host_run_command(cmd)
        except CommandFailed as cf:
            if cf.exitcode == 1:
                print cf.output

class resetReload(fspresetReload):

    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP Platform OPAL specific fsp resetreload tests")
        self.cv_FSP.fsp_get_console()
        if not self.cv_FSP.mount_exists():
            raise OpTestError("Please mount NFS and re-try the test")
        self.set_up()
        self.cv_HOST.host_check_command("nvram","ipmitool","sensors","hwclock")
        self.cv_FSP.clear_fsp_errors()
        self.cv_SYSTEM.load_ipmi_drivers(True)
        for i in range(0, self.number_of_resets()):
            print "====================FSP R&R iteration %d=====================" % i
            self.prepare_opal_log()
            self.trigger_rr()
            # Let fsp goes down
            time.sleep(20)
            self.wait_for_fsp_ping()
            time.sleep(10)
            self.cv_FSP.fsp_get_console()
            self.cv_FSP.wait_for_runtime()
            self.check_for_fsp_host_interfaces()
            self.cv_FSP.list_all_errorlogs_in_fsp()
            self.gather_opal_errors()

class FIR(resetReload):
    def set_up(self):
        self.test = "fir"

class HIR(resetReload):
    def set_up(self):
        self.test = "hir"

class SIR(resetReload):
    def set_up(self):
        self.test = "sir"

class FIRTorture(FIR):
    def number_of_resets(self):
        return 20

class HIRTorture(HIR):
    def number_of_resets(self):
        return 20

class SIRTorture(SIR):
    def number_of_resets(self):
        return 20

def suite():
    s = unittest.TestSuite()
    s.addTest(FIR())
    s.addTest(HIR())
    return s

def torture_suite():
    s = unittest.TestSuite()
    s.addTest(FIRTorture())
    s.addTest(HIRTorture())
    s.addTest(SIRTorture())
    return s
