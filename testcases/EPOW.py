#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/EPOW.py $
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

#  @package EPOW.py
#  This module tests the EPOW feature incase of FSP systems
#  1. EPOW3Random ---->Simulate random EPOW3 temperature to check whether 
#                       OPAL notify EPOW notification to Host OS. Once Host
#                       gets notified Host should do a graceful shutdown.
#  2. EPOW3LOW ------->Simualate temperatures less than EPOW3 threshold
#                      and check whether Host OS is alive or not.

import time
import subprocess
import commands
import re
import sys
import pexpect
import random

from common.OpTestConstants import OpTestConstants as BMC_CONST
from common.OpTestError import OpTestError

import unittest
import OpTestConfiguration
from common.OpTestSystem import OpSystemState

class EPOWBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.cv_FSP = conf.bmc()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type
        self.util = self.cv_SYSTEM.util
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)


    def get_epow_limits(self):
        fsp_MTM = self.cv_FSP.get_raw_mtm()
        matchObj = re.search("-\d{2}.", fsp_MTM)
        if matchObj:
            x = matchObj.group()
            y = x[1:3]
        var = y[1] + "s" + y[0] + "u"
        file = '/opt/fips/components/engd/power_management_tul_%s.def' % (var)

        # Check for Nebs enable\disable
        cmd = "registry -l svpd/NebsEnabled | sed -n '2p' | awk {'print $1'}"
        rc = self.cv_FSP.fspc.run_command(cmd)
        if int(rc) == 0:
            cmd = "cat %s | grep -i -e 'EPOW' -e 'CRITICAL' | head -n 6" % file
        else:
            cmd = "cat %s | grep -i -e 'EPOW' -e 'CRITICAL' | tail -n 6" % file

        # Checking for file existence
        rc = self.cv_FSP.fspc.run_command("test -f %s" % file)
        print "The def file for this machine is available"
        limits = self.cv_FSP.fspc.run_command(cmd)
        print limits
        cmd = cmd + "| cut -d '#' -f 1"
        limits = self.cv_FSP.fspc.run_command(cmd)
        dic = {}
        for i in range(len(limits)):
            pair = ((limits[i]).replace(" ", "")).replace("\t", "")
            l_pair = pair.split("=")
            dic[l_pair[0]] = l_pair[1]
        return dic

    def get_ambient_temp_ipmi(self):
        res = self.cv_IPMI.ipmitool.run('sdr list')
        print res
        temp = r"Inlet Temp       \| (\d{2,})"
        searchObj = re.search(temp, res)
        if searchObj:
            ambient_temp = searchObj.group(1)
            return ambient_temp
        else:
            raise OpTestError("IPMI: failed to read Inlet temperature")

    def get_cmd_for_temp(self, temp):
        val_d = temp * 4
        val_h = (str(hex(val_d))).replace('0x', '')
        cmd = 'echo "0000D000A0220004000700%s" | spif -' % val_h
        print cmd
        return cmd

    def check_graceful_shutdown(self, console):
        try:
            rc = console.expect_exact(["reboot: Power down", "Power down"], timeout=120)
            if rc == 0 or rc == 1:
                res = console.before
                print console.after
                print "System got graceful shutdown"
        except pexpect.TIMEOUT, e:
            print "System is in active state"
            print console.before

    def get_epow_list_temps(self):
        self.limits = self.get_epow_limits()
        print self.limits
        EPOW3 = self.limits['EPOW3']
        CRITICAL = self.limits['CRITICAL']
        EPOW3_RESET = self.limits['EPOW3_RESET']
        CRITICAL_RESET = self.limits['CRITICAL_RESET']
        l = []
        for temp in range(int(EPOW3), int(CRITICAL)):
            l.append(temp)
            return l
        return None

    def get_temp_for_param(self, param):
        return self.limits[param]

class EPOW3Random(EPOWBase):

    ##
    # @brief This testcase tests the EPOW feature
    #        1. It will gather EPOW limits 
    #        2. We will choose some random EPOW temp(test_temp) in b/w those limits
    #        3. Simulate that temperature(test_temp)
    #        4. Verify graceful shutdown happened or not
    #        5. Once system reaches standby, simulate the ambient temp
    #           to EPOW3_RESET temperature(reset_temp) to bring back the system.
    #        6. Bring back the system again to runtime.
    #        If user faces any problem in bringing the system UP please run below
    #        command "smgr toolReset"
    # 
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP specific OPAL EPOW Test.")
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        console.run_command("uname -a")
        # Range of EPOW temperatures from EPOW3 to CRITICAL
        temp_list = self.get_epow_list_temps()
        test_temp = int(random.choice(temp_list))
        print temp_list, test_temp
        print "===================================EPOW3_RANDOM:%i======================================" % test_temp
        print "*********************Testing EPOW3 at Random EPOW Temperature**************************"
        temp_prev = self.get_ambient_temp_ipmi()
        print "Current ambient temp: %s " % temp_prev
        print "Current system status: %s" % self.cv_FSP.get_sys_status()
        cmd = self.get_cmd_for_temp(test_temp)
        print "Simulating the Ambient Temp: %s" % test_temp
        print "Running the command on FSP: %s" % cmd
        self.cv_FSP.fspc.run_command(cmd)
        self.check_graceful_shutdown(console.sol)
        self.cv_FSP.wait_for_standby()
        temp_current = self.get_ambient_temp_ipmi()
        print "Current ambient temp: %s " % temp_current
        self.assertEqual(int(temp_current), int(test_temp),
            "EPOW3 is working, looks like temp simulated is slightly different")
        print "EPOW3 is successfull"
        self.cv_FSP.wait_for_standby()
        # simulate EPOW3 reset temperature to bring back the system
        reset_temp = self.get_temp_for_param('EPOW3_RESET')
        cmd = self.get_cmd_for_temp(int(reset_temp))
        print "Issuing the EPOW3 reset temp to bring back the system up"
        print "Simulating the Ambient Temp: %s" % reset_temp
        print "Running the command on FSP: %s" % cmd
        res = self.cv_FSP.fspc.run_command(cmd)
        print res
        temp_current = self.get_ambient_temp_ipmi()
        print "Current ambient temp: %s " % temp_current
        self.assertEqual(int(temp_current), int(reset_temp),
            "Temperature simulated is not equal to EPOW3_RESET")
        print "EPOW3 RESET Done: Temperature simulated to EPOW3_RESET"
        # Power on the system after issuing EPOW3 RESET
        self.cv_FSP.power_on_sys()
        self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)

class EPOW3LOW(EPOWBase):

    ##
    # @brief This test case will follow below procedure.
    #       1. Based on Nebsenabled will get EPOW limits from FSP using def file present 
    #          in /opt/fips/components/engd/. Different systems have different EPOW limits.
    #       2. Test EPOW3_LOW---> Will test temperatures lower than EPOW3 temperature,
    #           a. From FSP it simulate to lesser ambient temperatures than EPOW3 temperature
    #           b. In this case system should be alive and it should not cause system shut-down.
    #        If user faces any problem in bringing the system UP please run below
    #        command "smgr toolReset" in fsp console
    # 
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def runTest(self):
        if "FSP" not in self.bmc_type:
            self.skipTest("FSP specific OPAL EPOW Test.")
        console = self.cv_SYSTEM.sys_get_ipmi_console()
        self.cv_SYSTEM.host_console_login()
        self.cv_SYSTEM.host_console_unique_prompt()
        # Range of EPOW temperatures from EPOW3 to CRITICAL
        temp_list = self.get_epow_list_temps()
        print temp_list
        # Testing ambient temperatures lower than EPOW3, system should be alive
        EPOW3 = self.get_temp_for_param('EPOW3')
        temp_2 = int(EPOW3)-2
        temp_1 = int(EPOW3)-1
        for test_temp in [temp_1, temp_2]:
            print "===============================EPOW3_LOW:%i==================================" % test_temp
            print "*********Testing ambient temperatures lower than EPOW3, system should be alive***********"
            temp_prev = self.get_ambient_temp_ipmi()
            print "Current ambient temp: %s " % temp_prev
            cmd = self.get_cmd_for_temp(test_temp)
            print "Simulating the Ambient Temp: %s" % test_temp
            print "Running the command on FSP: %s" % cmd
            res = self.cv_FSP.fspc.run_command(cmd)
            print res
            # Monitor the system status for any chanages from runtime
            tries = 10
            for i in range(1, tries+1):
                state = self.cv_FSP.get_sys_status()
                print "Current system status: %s" % state
                self.assertEqual(state, 'runtime',
                        "EPOW3_LOW is failing at this temp: %s" % test_temp)
                time.sleep(6)
            self.util.PingFunc(self.cv_HOST.ip, BMC_CONST.PING_RETRY_POWERCYCLE)
            temp_current = self.get_ambient_temp_ipmi()
            print "Current ambient temp: %s " % temp_current
            self.assertEqual(int(temp_current), int(test_temp),
                "EPOW3_LOW is working, looks like temp simulated is different")

def suite():
    s = unittest.TestSuite()
    s.addTest(EPOW3LOW())
    s.addTest(EPOW3Random())
    #TODO: s.addTest(EPOW3CRITICAL())
    return s
