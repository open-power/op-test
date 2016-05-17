#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/test_op_firmware_component_update.py $
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
import op_firmware_component_update

def test_validate_host():
    assert op_firmware_component_update.validate_host() == 0

def test_outofband_fw_update_hpm():
    assert op_firmware_component_update.outofband_fw_update_hpm() == 0

def test_outofband_pnor_update_hpm():
    assert op_firmware_component_update.outofband_pnor_update_hpm() == 0

def test_inband_fw_update_hpm():
    assert op_firmware_component_update.inband_fw_update_hpm() == 0

def test_inband_pnor_update_hpm():
    assert op_firmware_component_update.inband_pnor_update_hpm() == 0

