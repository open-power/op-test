#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestFlash.py $
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

#  @package OpTestFlash
#  Firmware flash tests for OpenPower testing.
#
#  This class contains the OpenPower Firmware flashing scripts for
#  AMI platforms 
#
#   PNOR Flash Update
#   Lid Updates(Currently skiboot lid) TODO: Add skiroot lid support
#   Out-of-band HPM Update
#   In-band HPM Update
# 
#  pre-requistes pflash tool should be in /tmp directory of BMC busy box
#


import os
import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.OpTestConstants import OpTestConstants as BMC_CONST


class OpTestFlashBase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_BMC = conf.bmc()
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.platform = conf.platform()
        self.bmc_type = conf.args.bmc_type

    def validate_side_activated(self):
        l_bmc_side, l_pnor_side = self.cv_IPMI.ipmi_get_side_activated()
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_bmc_side, "BMC: Primary side is not active")
        # TODO force setting of primary side to BIOS Golden side sensor
        self.assertIn(BMC_CONST.PRIMARY_SIDE, l_pnor_side, "PNOR: Primary side is not active")

    def get_pnor_level(self):
        rc = self.cv_IPMI.ipmi_get_PNOR_level()
        print rc


class PNORFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.pnor_name = conf.args.host_pnor
        self.pnor_path = os.path.join(self.images_dir, self.pnor_name)
        self.assertNotEqual(os.path.exists(self.pnor_path), 0,
            "PNOR image %s not doesn't exist" % self.pnor_path)
        super(PNORFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC PNOR Flash test")
        self.cv_BMC.validate_pflash_tool("/tmp")
        self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        self.cv_BMC.pnor_img_transfer(self.images_dir, self.pnor_name)
        self.cv_BMC.pnor_img_flash("/tmp", self.pnor_name)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class SkibootLidFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.lid_name = conf.args.host_lid
        self.lid_path = os.path.join(self.images_dir, self.lid_name)
        self.assertNotEqual(os.path.exists(self.lid_path), 0,
            "Skiboot lid %s not doesn't exist" % self.lid_path)
        super(SkibootLidFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC Skiboot lid flash test")
        self.cv_BMC.validate_pflash_tool("/tmp")
        self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.sys_sdr_clear()
        self.cv_BMC.pnor_img_transfer(self.images_dir, self.lid_name)
        self.cv_BMC.skiboot_img_flash("/tmp", self.lid_name)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()

class OOBHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.hpm_name = conf.args.host_hpm
        self.hpm_path = os.path.join(self.images_dir, self.hpm_name)
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
            "HPM File %s not doesn't exist" % self.hpm_path)
        super(OOBHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC Out-of-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_IPMI.ipmi_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()


class InbandHpmFLASH(OpTestFlashBase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.images_dir = conf.args.firmware_images
        self.hpm_name = conf.args.host_hpm
        self.hpm_path = os.path.join(self.images_dir, self.hpm_name)
        self.assertNotEqual(os.path.exists(self.hpm_path), 0,
            "HPM File %s not doesn't exist" % self.hpm_path)
        super(InbandHpmFLASH, self).setUp()

    def runTest(self):
        if "AMI" not in self.bmc_type:
            self.skipTest("OP AMI BMC In-band firmware Update test")
        self.cv_SYSTEM.sys_sdr_clear()
        self.validate_side_activated()
        self.cv_HOST.host_code_update(self.hpm_path, str(BMC_CONST.BMC_FWANDPNOR_IMAGE_UPDATE))
        self.cv_SYSTEM.goto_state(OpSystemState.OFF)
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.validate_side_activated()
        self.cv_SYSTEM.sys_sel_check()
