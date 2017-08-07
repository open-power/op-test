#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestInbandUsbInterface.py $
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

#  @package OpTestInbandUsbInterface
#  Test the inband ipmi{USB Interface} fucntionality package for OpenPower platform.
#
#  This class will test the functionality of following commands
#  1. bmc, channel, chassis, dcmi, echo, event, exec, firewall, fru, lan
#     mc, pef, power, raw, sdr, sel, sensor, session, user

import time
import subprocess
import re
import commands
import sys

from common.OpTestConstants import OpTestConstants as BMC_CONST
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from testcases.OpTestInbandIPMI import BasicInbandIPMI, OpTestInbandIPMI, ExperimentalInbandIPMI
from testcases.OpTestInbandIPMI import SkirootBasicInbandIPMI, SkirootFullInbandIPMI

def experimental_suite():
    return unittest.defaultTestLoader.loadTestsFromModule(ExperimentalInbandUSB)

def basic_suite():
    return unittest.defaultTestLoader.loadTestsFromModule(BasicInbandUSB)

def full_suite():
    return unittest.defaultTestLoader.loadTestsFromModule(InbandUSB)

def skiroot_full_suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(SkirootInbandUSB)

conf = OpTestConfiguration.conf

class BasicInbandUSB(BasicInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_USB):
        self.bmc_type = conf.args.bmc_type
        if "FSP" in self.bmc_type:
            self.skipTest("OP BMC specific")
        if "OpenBMC" in self.bmc_type:
            self.skipTest("OpenBMC doesn't support inband IPMI over USB")
        super(BasicInbandUSB, self).setUp(ipmi_method=ipmi_method)

class InbandUSB(OpTestInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_USB):
        self.bmc_type = conf.args.bmc_type
        if "FSP" in self.bmc_type:
            self.skipTest("OP BMC specific")
        if "OpenBMC" in self.bmc_type:
            self.skipTest("OpenBMC doesn't support inband IPMI over USB")
        super(InbandUSB, self).setUp(ipmi_method=ipmi_method)

class SkirootBasicInbandUSB(SkirootBasicInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_USB):
        self.bmc_type = conf.args.bmc_type
        if "FSP" in self.bmc_type:
            self.skipTest("OP BMC specific")
        if "OpenBMC" in self.bmc_type:
            self.skipTest("OpenBMC doesn't support inband IPMI over USB")
        super(SkirootBasicInbandUSB, self).setUp(ipmi_method=ipmi_method)

class SkirootInbandUSB(SkirootFullInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_USB):
        self.bmc_type = conf.args.bmc_type
        if "FSP" in self.bmc_type:
            self.skipTest("OP BMC specific")
        if "OpenBMC" in self.bmc_type:
            self.skipTest("OpenBMC doesn't support inband IPMI over USB")
        super(SkirootInbandUSB, self).setUp(ipmi_method=ipmi_method)

class ExperimentalInbandUSB(ExperimentalInbandIPMI):
    def setUp(self, ipmi_method=BMC_CONST.IPMITOOL_USB):
        self.bmc_type = conf.args.bmc_type
        if "FSP" in self.bmc_type:
            self.skipTest("OP BMC specific")
        if "OpenBMC" in self.bmc_type:
            self.skipTest("OpenBMC doesn't support inband IPMI over USB")
        super(ExperimentalInbandUSB, self).setUp(ipmi_method=ipmi_method)
