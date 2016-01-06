#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/test_op_ci.py $
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

import os
import sys
#from op_ci_bmc import bmc_reboot
#full_path = os.path.abspath(os.path.dirname(sys.argv[0])).split('ci')[0]
#sys.path.append(full_path)
#import op_ci_bmc
# Fixture
import op_ci_bmc

def test_config_check():
    assert op_ci_bmc.test_init() == 0

def test_ipmi_power_off():
    assert op_ci_bmc.ipmi_power_off() == 0

def test_ipmi_power_soft():
    assert op_ci_bmc.ipmi_power_soft() == 0

def test_ipmi_warm_reset():
    assert op_ci_bmc.ipmi_warm_reset() == 0

def test_bmc_reboot():
    assert op_ci_bmc.bmc_reboot() == 0

def test_ipmi_sdr_clear():
    assert op_ci_bmc.ipmi_sdr_clear() == 0

def test_pnor_img_transfer():
    assert op_ci_bmc.pnor_img_transfer() == 0

def test_pnor_img_flash():
    assert op_ci_bmc.pnor_img_flash() == 0

def test_ipmi_power_on():
    assert op_ci_bmc.ipmi_power_on() == 0

def test_wait_for_working_state():
    assert op_ci_bmc.ipl_wait_for_working_state() == 0

def test_ipmi_sel_check():
    assert op_ci_bmc.ipmi_sel_check() == 0

def test_validate_lpar():
    assert op_ci_bmc.validate_lpar() == 0

def test_outofband_fwandpnor_update_hpm():
    assert op_ci_bmc.outofband_fwandpnor_update_hpm() == 0
