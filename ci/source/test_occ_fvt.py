#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/test_occ_fvt.py $
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
import op_occ_fvt


def test_config_check():
    assert op_occ_fvt.test_init() == 0


def test_energy_scale_at_standby_state():
    assert op_occ_fvt.test_energy_scale_at_standby_state() == 0


def test_energy_scale_at_runtime_state():
    assert op_occ_fvt.test_energy_scale_at_runtime_state() == 0


def test_dcmi_at_standby_and_runtime_states():
    assert op_occ_fvt.test_dcmi_at_standby_and_runtime_states() == 0


def test_occ_reset_functionality():
    assert op_occ_fvt.test_occ_reset_functionality() == 0


def test_occ_enable_disable_functionality():
    assert op_occ_fvt.test_occ_enable_disable_functionality() == 0
