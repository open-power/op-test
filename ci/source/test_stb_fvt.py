#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/test_stb_fvt.py $
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

import os
import sys
import op_stb_fvt

def test_config_check():
    assert op_stb_fvt.test_init() == 0

def test_stb_reboot():
    assert op_stb_fvt.test_stb_reboot() == 0

def test_verify_secure_boot_in_opal(self):
    assert op_stb_fvt.test_verify_secure_boot_in_opal() == 0

def test_verify_trusted_boot_in_opal(self):
    assert op_stb_fvt.test_verify_trusted_boot_in_opal() == 0

def test_cross_check_stb(self):
    assert op_stb_fvt.cross_check_stb() == 0
