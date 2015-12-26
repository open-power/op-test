#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/common/OpTestSensors.py $
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

#  @package OpTestSensors
#  Sensors package for OpenPower testing.
#
#  This class will test the functionality of following drivers
#  1. Hardware monitoring sensors(hwmon driver) using sensors utility

import time
import subprocess
import re

from OpTestBMC import OpTestBMC
from OpTestIPMI import OpTestIPMI
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestLpar import OpTestLpar
from OpTestUtil import OpTestUtil


class OpTestSensors():
    #  Initialize this object
    #  @param i_bmcIP The IP address of the BMC
    #  @param i_bmcUser The userid to log into the BMC with
    #  @param i_bmcPasswd The password of the userid to log into the BMC with
    #  @param i_bmcUserIpmi The userid to issue the BMC IPMI commands with
    #  @param i_bmcPasswdIpmi The password of BMC IPMI userid
    #  @param i_ffdcDir Optional param to indicate where to write FFDC
    #
    # "Only required for inband tests" else Default = None
    # @param i_lparIP The IP address of the LPAR
    # @param i_lparuser The userid to log into the LPAR
    # @param i_lparPasswd The password of the userid to log into the LPAR with
    #
    def __init__(self, i_bmcIP, i_bmcUser, i_bmcPasswd,
                 i_bmcUserIpmi, i_bmcPasswdIpmi, i_ffdcDir=None, i_lparip=None,
                 i_lparuser=None, i_lparPasswd=None):
        self.cv_BMC = OpTestBMC(i_bmcIP, i_bmcUser, i_bmcPasswd, i_ffdcDir)
        self.cv_IPMI = OpTestIPMI(i_bmcIP, i_bmcUserIpmi, i_bmcPasswdIpmi,
                                  i_ffdcDir)
        self.cv_LPAR = OpTestLpar(i_lparip, i_lparuser, i_lparPasswd)
        self.util = OpTestUtil()

    def test_hwmon_driver(self):
        # This function will cover following
        # 1. It will check for kernel config option CONFIG_SENSORS_IBMPOWERNV
        # 2. It will load ibmpowernv driver only on powernv platform
        # 3. It will check for sensors command existence and lm_sensors package
        # 4. start the lm_sensors service and detect any sensor chips
        #    using sensors-detect.
        # 5. At the end it will test sensors command functionality
        #    with different options

        # Get OS level
        OS = self.cv_LPAR.lpar_get_OS_Level()

        # Checking for sensors config option CONFIG_SENSORS_IBMPOWERNV
        kernel = self.cv_LPAR._ssh_execute("uname -a | awk {'print $3'}")
        kernel = kernel.replace("\r\n", "")
        print kernel
        cmd = "cat /boot/config-%s | grep -i SENSORS_IBMPOWERNV" % kernel
        print cmd
        try:
            res = self.cv_LPAR._ssh_execute(cmd)
            print res
        except:
            l_msg = "Getting Config file is failed"
            print l_msg
            raise OpTestError(l_msg)

        try:
            val = ((res.split("=")[1]).replace("\r\n", ""))
            if val == "y":
                print "Driver build into kernel itself"
            else:
                print "Driver will be built as module"
        except:
            print val
            l_msg = "config option is not set,exiting..."
            print l_msg
            raise OpTestError(l_msg)

        # Loading ibmpowernv driver only on powernv platform
        if "PowerKVM" not in OS:
            l_rc = self.cv_LPAR._ssh_execute("modprobe ibmpowernv; echo $?")
            if int(l_rc) == 0:
                cmd = "lsmod | grep -i ibmpowernv"
                response = self.cv_LPAR._ssh_execute(cmd)
                if "ibmpowernv" not in response:
                    l_msg = "ibmpowernv module is not loaded, exiting"
                    raise OpTestError(l_msg)
                else:
                    print "ibmpowernv module is loaded"
                print cmd
                print response
            else:
                l_msg = "modprobe failed while loading ibmpowernv,exiting..."
                print l_msg
                raise OpTestError(l_msg)
        else:
            pass

        # Checking for sensors command and lm_sensors package
        response = self.cv_LPAR._ssh_execute("sensors")
        matchObj = re.search(r"command not found", response)
        if matchObj:
            l_msg = "sensors not working, install lm_sensors package"
            print l_msg
            raise OpTestError(l_msg)
        else:
            pkg = self.cv_LPAR._ssh_execute("rpm -qf /bin/sensors")
            print "Installed package:%s" % pkg
        print response

        try:
            # Start the lm_sensors service
            cmd = "/bin/systemctl stop  lm_sensors.service"
            self.cv_LPAR._ssh_execute(cmd)
            cmd = "/bin/systemctl start  lm_sensors.service"
            self.cv_LPAR._ssh_execute(cmd)
            cmd = "/bin/systemctl status  lm_sensors.service"
            res = self.cv_LPAR._ssh_execute(cmd)
            print res

            # To detect different sensor chips and modules
            res = self.cv_LPAR._ssh_execute("yes | sensors-detect")
            print res
        except:
            l_msg = "loading lm_sensors service failed"
            print l_msg
            raise OpTestError(l_msg)

        # Checking sensors command functionality with different options
        output = self.cv_LPAR._ssh_execute("sensors; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR._ssh_execute("sensors -f; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -f not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR._ssh_execute("sensors -A; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -A not working,exiting...."
            raise OpTestError(l_msg)
        print output
        output = self.cv_LPAR._ssh_execute("sensors -u; echo $?")
        response = output.splitlines()
        if int(response[-1]):
            l_msg = "sensors -u not working,exiting...."
            raise OpTestError(l_msg)
        print output
        return BMC_CONST.FW_SUCCESS
