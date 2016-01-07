#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/test_op_outofband_firmware_update.py $
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
import op_outofband_firmware_update

def test_get_PNOR_level():
    assert op_outofband_firmware_update.get_PNOR_level() == 0

def test_get_side_activated():
    assert op_outofband_firmware_update.get_side_activated() == 0

def test_cold_reset():
    assert op_outofband_firmware_update.cold_reset() == 0

def test_preserve_network_setting():
    assert op_outofband_firmware_update.preserve_network_setting() == 0

def test_code_update():
    assert op_outofband_firmware_update.code_update() == 0

