#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/test_stb_fvt.py $
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
import op_stb_fvt


def test_config_check():
    assert op_stb_fvt.test_init() == 0

def test_stb_support():
    assert op_stb_fvt.test_stb_support() == 0

def test_hw_sb_support(self):
    assert op_stb_fvt.hw_sb_support() == 0

def test_hw_tb_support(self):
    assert op_stb_fvt.hw_tb_support() == 0

def test_secure_boot_mode(self):
    assert op_stb_fvt.secure_boot_mode() == 0

def test_trusted_boot_mode(self):
    assert op_stb_fvt.trusted_boot_mode() == 0

def test_capp_measured(self):
    assert op_stb_fvt.capp_measured() == 0

def test_bootkernel_measured(self):
    assert op_stb_fvt.bootkernel_measured() == 0

def test_capp_verified(self):
    assert op_stb_fvt.capp_verified() == 0

def test_bootkernel_verified(self):
    assert op_stb_fvt.bootkernel_verified() == 0

def test_capp_loaded(self):
    assert op_stb_fvt.capp_loaded() == 0

def test_bootkernel_loaded(self):
    assert op_stb_fvt.bootkernel_loaded() == 0

def test_proc_sb_verify(self):
    assert op_stb_fvt.proc_sb_verify() == 0

def test_proc_tb_verify(self):
    assert op_stb_fvt.proc_tb_verify() == 0

def test_cross_check_hw_opal_sb(self):
    assert op_stb_fvt.cross_check_hw_opal_sb() == 0

def test_cross_check_hw_opal_tb(self):
    assert op_stb_fvt.cross_check_hw_opal_tb() == 0

def test_cross_check_stb(self):
    assert op_stb_fvt.cross_check_stb() == 0
