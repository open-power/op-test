#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/test_opal_fvt.py $
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
import op_opal_fvt

def test_config_check():
    assert op_opal_fvt.test_init() == 0

def test_sensors():
    assert op_opal_fvt.test_sensors() == 0

def test_switchendian_syscall():
    assert op_opal_fvt.test_switch_endian_syscall() == 0

def test_ipmi_heartbeat():
    assert op_opal_fvt.test_ipmi_heartbeat() == 0

def test_rtc_driver():
    assert op_opal_fvt.test_real_time_clock() == 0

def test_at24_driver():
    assert op_opal_fvt.test_at24_driver() == 0

def test_i2c_driver():
    assert op_opal_fvt.test_i2c_driver() == 0

def test_mtdpnor_driver():
    assert op_opal_fvt.test_mtd_pnor_driver() == 0
