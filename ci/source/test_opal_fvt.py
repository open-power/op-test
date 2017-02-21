#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/test_opal_fvt.py $
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


def test_list_pci_device_info():
    assert op_opal_fvt.test_list_pci_device_info() == 0


def test_sensors():
    assert op_opal_fvt.test_sensors() == 0


def test_switchendian_syscall():
    assert op_opal_fvt.test_switch_endian_syscall() == 0


def test_ipmi_heartbeat():
    assert op_opal_fvt.test_ipmi_heartbeat() == 0


def test_rtc_driver():
    assert op_opal_fvt.test_real_time_clock() == 0


def test_i2c_driver():
    assert op_opal_fvt.test_i2c_driver() == 0


def test_mtdpnor_driver():
    assert op_opal_fvt.test_mtd_pnor_driver() == 0


def test_ipmi_inband_functionality():
    assert op_opal_fvt.test_ipmi_inband_functionality() == 0


def test_prd_driver():
    assert op_opal_fvt.test_prd_driver() == 0

def test_ipmi_lock_mode():
    assert op_opal_fvt.test_ipmi_lock_mode() == 0


def test_ipmi_power_control():
    assert op_opal_fvt.test_ipmi_power_control() == 0


def test_ipmi_inband_usb_interface():
    assert op_opal_fvt.test_ipmi_inband_usb_interface() == 0


def test_oob_ipmi():
    assert op_opal_fvt.test_oob_ipmi() == 0


def test_mc_cold_reset_boot_sequence():
    assert op_opal_fvt.test_mc_cold_reset_boot_sequence() == 0


def test_mc_warm_reset_boot_sequence():
    assert op_opal_fvt.test_mc_warm_reset_boot_sequence() == 0


def test_fan_control_enable_functionality():
    assert op_opal_fvt.test_fan_control_enable_functionality() == 0


def test_fan_control_disable_functionality():
    assert op_opal_fvt.test_fan_control_disable_functionality() == 0


def test_system_power_restore_policy_always_on():
    assert op_opal_fvt.test_system_power_restore_policy_always_on() == 0


def test_system_power_restore_policy_always_off():
    assert op_opal_fvt.test_system_power_restore_policy_always_off() == 0


def test_system_power_restore_policy_previous():
    assert op_opal_fvt.test_system_power_restore_policy_previous() == 0


def test_nvram_ipmi_reprovision():
    assert op_opal_fvt.test_nvram_ipmi_reprovision() == 0


def test_gard_ipmi_reprovision():
    assert op_opal_fvt.test_gard_ipmi_reprovision() == 0


def test_bmc_cold_reset_effects():
    assert op_opal_fvt.test_bmc_cold_reset_effects() == 0
