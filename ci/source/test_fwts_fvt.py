#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/test_fwts_fvt.py $
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
import op_fwts_fvt


def test_config_check():
    assert op_fwts_fvt.test_init() == 0


def test_system_reboot():
    assert op_fwts_fvt.test_system_reboot() == 0


def test_pre_init():
    assert op_fwts_fvt.test_pre_init() == 0


def test_bmc_info():
    assert op_fwts_fvt.test_bmc_info() == 0


def test_prd_info():
    assert op_fwts_fvt.test_prd_info() == 0


def test_oops():
    assert op_fwts_fvt.test_oops() == 0


def test_olog():
    assert op_fwts_fvt.test_olog() == 0
