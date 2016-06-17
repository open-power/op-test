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


def test_ipmi_inband_functionality():
    assert op_opal_fvt.test_ipmi_inband_functionality() == 0


def test_hmi_proc_recv_done():
    assert op_opal_fvt.test_hmi_proc_recv_done() == 0


def test_hmi_proc_recv_error_masked():
    assert op_opal_fvt.test_hmi_proc_recv_error_masked() == 0


def test_hmi_malfunction_alert():
    assert op_opal_fvt.test_hmi_malfunction_alert() == 0


def test_hmi_hypervisor_resource_error():
    assert op_opal_fvt.test_hmi_hypervisor_resource_error() == 0


def test_clearing_gard_entries():
    assert op_opal_fvt.clear_gard_entries() == 0


def test_prd_driver():
    assert op_opal_fvt.test_prd_driver() == 0


def test_tfmr_errors():
    assert op_opal_fvt.test_tfmr_errors() == 0


def test_tod_errors():
    assert op_opal_fvt.test_tod_errors() == 0


def test_ipmi_lock_mode():
    assert op_opal_fvt.test_ipmi_lock_mode() == 0


def test_ipmi_power_control():
    assert op_opal_fvt.test_ipmi_power_control() == 0


def test_oob_ipmi():
    assert op_opal_fvt.test_oob_ipmi() == 0


def test_mc_cold_reset_boot_sequence():
    assert op_opal_fvt.test_mc_cold_reset_boot_sequence() == 0


def test_mc_warm_reset_boot_sequence():
    assert op_opal_fvt.test_mc_warm_reset_boot_sequence() == 0


def test_system_power_restore_policy_always_on():
    assert op_opal_fvt.test_system_power_restore_policy_always_on() == 0


def test_system_power_restore_policy_always_off():
    assert op_opal_fvt.test_system_power_restore_policy_always_off() == 0


def test_system_power_restore_policy_previous():
    assert op_opal_fvt.test_system_power_restore_policy_previous() == 0
