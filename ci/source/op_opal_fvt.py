#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/ci/source/op_opal_fvt.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2015,2016
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
"""
.. module:: op_opal_fvt
    :platform: Unix
    :synopsis: This module contains functional verification test functions
               for OPAL firmware. Corresponding source files for new OPAL
               features will be adding in testcases directory

.. moduleauthor:: Pridhiviraj Paidipeddi <ppaidipe@in.ibm.com>

"""
import sys
import os

# Get path to base directory and append to path to get common modules
full_path = os.path.dirname(os.path.abspath(__file__))
full_path = full_path.split('ci')[0]

sys.path.append(full_path)
import ConfigParser

from common.OpTestConstants import OpTestConstants as BMC_CONST
from testcases.OpTestSensors import OpTestSensors
from testcases.OpTestSwitchEndianSyscall import OpTestSwitchEndianSyscall
from testcases.OpTestHeartbeat import OpTestHeartbeat
from testcases.OpTestRTCdriver import OpTestRTCdriver
from testcases.OpTestAt24driver import OpTestAt24driver
from testcases.OpTestI2Cdriver import OpTestI2Cdriver
from testcases.OpTestMtdPnorDriver import OpTestMtdPnorDriver
from testcases.OpTestInbandIPMI import OpTestInbandIPMI
from testcases.OpTestHMIHandling import OpTestHMIHandling
from testcases.OpTestPrdDriver import OpTestPrdDriver
from testcases.OpTestIPMILockMode import OpTestIPMILockMode
from testcases.OpTestIPMIPowerControl import OpTestIPMIPowerControl
from testcases.OpTestInbandUsbInterface import OpTestInbandUsbInterface
from testcases.OpTestOOBIPMI import OpTestOOBIPMI
from testcases.OpTestSystemBootSequence import OpTestSystemBootSequence
from testcases.OpTestIPMIReprovision import OpTestIPMIReprovision
from testcases.OpTestDropbearSafety import OpTestDropbearSafety
from testcases.OpTestMCColdResetEffects import OpTestMCColdResetEffects
from testcases.OpTestPCI import OpTestPCI
from testcases.OpTestFastReboot import OpTestFastReboot
from testcases.OpTestNVRAM import OpTestNVRAM
from testcases.OpTestEEH import OpTestEEH
from testcases.OpTestDumps import OpTestDumps
from testcases.OpTestKernel import OpTestKernel

def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('host'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, hostCfg = _config_read()

opTestSensors = OpTestSensors(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg.get('usernameipmi'),
                              bmcCfg.get('passwordipmi'),
                              testCfg['ffdcdir'], hostCfg['hostip'],
                              hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestMCColdResetEffects = OpTestMCColdResetEffects(bmcCfg['ip'], bmcCfg['username'],
                                                    bmcCfg['password'],
                                                    bmcCfg.get('usernameipmi'),
                                                    bmcCfg.get('passwordipmi'),
                                                    testCfg['ffdcdir'], hostCfg['hostip'],
                                                    hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestSwitchEndianSyscall = OpTestSwitchEndianSyscall(bmcCfg['ip'],
                                                      bmcCfg['username'],
                                                      bmcCfg['password'],
                                                      bmcCfg.get('usernameipmi'),
                                                      bmcCfg.get('passwordipmi'),
                                                      testCfg['ffdcdir'],
                                                      hostCfg['hostip'],
                                                      hostCfg['hostuser'],
                                                      hostCfg['hostpasswd'])

opTestRTCdriver = OpTestRTCdriver(bmcCfg['ip'],
                                  bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg.get('usernameipmi'),
                                  bmcCfg.get('passwordipmi'),
                                  testCfg['ffdcdir'],
                                  hostCfg['hostip'],
                                  hostCfg['hostuser'],
                                  hostCfg['hostpasswd'])

opTestAt24driver = OpTestAt24driver(bmcCfg['ip'], bmcCfg['username'],
                                    bmcCfg['password'],
                                    bmcCfg.get('usernameipmi'),
                                    bmcCfg.get('passwordipmi'),
                                    testCfg['ffdcdir'], hostCfg['hostip'],
                                    hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestI2Cdriver = OpTestI2Cdriver(bmcCfg['ip'], bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg.get('usernameipmi'),
                                  bmcCfg.get('passwordipmi'),
                                  testCfg['ffdcdir'], hostCfg['hostip'],
                                  hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestHeartbeat = OpTestHeartbeat(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg.get('usernameipmi'),
                              bmcCfg.get('passwordipmi'),
                              testCfg['ffdcdir'], hostCfg['hostip'],
                              hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestMtdPnorDriver = OpTestMtdPnorDriver(bmcCfg['ip'], bmcCfg['username'],
                                          bmcCfg['password'],
                                          bmcCfg.get('usernameipmi'),
                                          bmcCfg.get('passwordipmi'),
                                          testCfg['ffdcdir'], hostCfg['hostip'],
                                          hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestInbandIPMI = OpTestInbandIPMI(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg.get('usernameipmi'),
                              bmcCfg.get('passwordipmi'),
                              testCfg['ffdcdir'], hostCfg['hostip'],
                              hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestHMIHandling = OpTestHMIHandling(bmcCfg['ip'], bmcCfg['username'],
                                          bmcCfg['password'],
                                          bmcCfg.get('usernameipmi'),
                                          bmcCfg.get('passwordipmi'),
                                          testCfg['ffdcdir'], hostCfg['hostip'],
                                          hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestPrdDriver = OpTestPrdDriver(bmcCfg['ip'], bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg.get('usernameipmi'),
                                  bmcCfg.get('passwordipmi'),
                                  testCfg['ffdcdir'], hostCfg['hostip'],
                                  hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestIPMILockMode = OpTestIPMILockMode(bmcCfg['ip'], bmcCfg['username'],
                                        bmcCfg['password'],
                                        bmcCfg.get('usernameipmi'),
                                        bmcCfg.get('passwordipmi'),
                                        testCfg['ffdcdir'], hostCfg['hostip'],
                                        hostCfg['hostuser'], hostCfg['hostpasswd'])


opTestIPMIPowerControl = OpTestIPMIPowerControl(bmcCfg['ip'], bmcCfg['username'],
                                        bmcCfg['password'],
                                        bmcCfg.get('usernameipmi'),
                                        bmcCfg.get('passwordipmi'),
                                        testCfg['ffdcdir'], hostCfg['hostip'],
                                        hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestInbandUsbInterface = OpTestInbandUsbInterface(bmcCfg['ip'], bmcCfg['username'],
                                                    bmcCfg['password'],
                                                    bmcCfg.get('usernameipmi'),
                                                    bmcCfg.get('passwordipmi'),
                                                    testCfg['ffdcdir'], hostCfg['hostip'],
                                                    hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestOOBIPMI = OpTestOOBIPMI(bmcCfg['ip'], bmcCfg['username'],
                                        bmcCfg['password'],
                                        bmcCfg.get('usernameipmi'),
                                        bmcCfg.get('passwordipmi'),
                                        testCfg['ffdcdir'], hostCfg['hostip'],
                                        hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestSystemBootSequence = OpTestSystemBootSequence(bmcCfg['ip'], bmcCfg['username'],
                                                    bmcCfg['password'],
                                                    bmcCfg.get('usernameipmi'),
                                                    bmcCfg.get('passwordipmi'),
                                                    testCfg['ffdcdir'], hostCfg['hostip'],
                                                    hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestIPMIReprovision = OpTestIPMIReprovision(bmcCfg['ip'], bmcCfg['username'],
                                              bmcCfg['password'],
                                              bmcCfg.get('usernameipmi'),
                                              bmcCfg.get('passwordipmi'),
                                              testCfg['ffdcdir'], hostCfg['hostip'],
                                              hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestDropbearSafety = OpTestDropbearSafety(bmcCfg['ip'], bmcCfg['username'],
                                            bmcCfg['password'],
                                            bmcCfg.get('usernameipmi'),
                                            bmcCfg.get('passwordipmi'),
                                            testCfg['ffdcdir'], hostCfg['hostip'],
                                            hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestPCI = OpTestPCI(bmcCfg['ip'], bmcCfg['username'],
                      bmcCfg['password'],
                      bmcCfg.get('usernameipmi'),
                      bmcCfg.get('passwordipmi'),
                      testCfg['ffdcdir'], hostCfg['hostip'],
                      hostCfg['hostuser'], hostCfg['hostpasswd'], hostCfg['lspci'])

opTestFastReboot = OpTestFastReboot(bmcCfg['ip'], bmcCfg['username'],
                      bmcCfg['password'],
                      bmcCfg.get('usernameipmi'),
                      bmcCfg.get('passwordipmi'),
                      testCfg['ffdcdir'], hostCfg['hostip'],
                      hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestNVRAM = OpTestNVRAM(bmcCfg['ip'], bmcCfg['username'],
                          bmcCfg['password'],
                          bmcCfg.get('usernameipmi'),
                          bmcCfg.get('passwordipmi'),
                          testCfg['ffdcdir'], hostCfg['hostip'],
                          hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestEEH = OpTestEEH(bmcCfg['ip'], bmcCfg['username'],
                      bmcCfg['password'],
                      bmcCfg.get('usernameipmi'),
                      bmcCfg.get('passwordipmi'),
                      testCfg['ffdcdir'], hostCfg['hostip'],
                      hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestDumps = OpTestDumps(bmcCfg['ip'], bmcCfg['username'],
                          bmcCfg['password'],
                          bmcCfg.get('usernameipmi'),
                          bmcCfg.get('passwordipmi'),
                          testCfg['ffdcdir'], hostCfg['hostip'],
                          hostCfg['hostuser'], hostCfg['hostpasswd'])

opTestKernel = OpTestKernel(bmcCfg['ip'], bmcCfg['username'],
                            bmcCfg['password'],
                            bmcCfg.get('usernameipmi'),
                            bmcCfg.get('passwordipmi'),
                            testCfg['ffdcdir'], hostCfg['hostip'],
                            hostCfg['hostuser'], hostCfg['hostpasswd'])

def test_init():
    """This function validates the test config before running other functions
    """

    ''' create FFDC dir if it does not exist '''
    ffdcDir = testCfg['ffdcdir']
    if not os.path.exists(os.path.dirname(ffdcDir)):
        os.makedirs(os.path.dirname(ffdcDir))

    return 0


def test_sensors():
    """This function tests the hwmon driver for hardware monitoring sensors
    using sensors utility
    returns: int 0-success, raises exception-error
    """
    return opTestSensors.test_hwmon_driver()


def test_switch_endian_syscall():
    """This function executes the switch_endian() sys call test which is
    implemented in /linux/tools/testing/selftests/powerpc/switch_endian
    git  repository
    returns: int 0: success, 1: error
    """
    return opTestSwitchEndianSyscall.testSwitchEndianSysCall()


def test_ipmi_heartbeat():
    """This function tests whether the kopald service is running in platform OS
    returns: int 0-success, raises exception-error
    """
    return opTestHeartbeat.test_kopald_service()


def test_real_time_clock():
    """This function tests Real Time Clock driver functionalites using hwclock utility
    returns: int 0-success, raises exception-error
    """
    return opTestRTCdriver.test_RTC_driver()


def test_at24_driver():
    """This function tests Atmel EEPROM 24(AT24) driver functionalites
    returns: int 0-success, raises exception-error
    """
    return opTestAt24driver.testAt24driver()


def test_i2c_driver():
    """This function tests I2C driver capabilites using i2c-tools
    returns: int 0-success, raises exception-error
    """
    return opTestI2Cdriver.testI2Cdriver()


def test_mtd_pnor_driver():
    """This function tests MTD PNOR driver using fcp utility to get PNOR flash contents in an x86 machine
    returns: int 0-success, raises exception-error
    """
    return opTestMtdPnorDriver.testMtdPnorDriver()


def test_ipmi_inband_functionality():
    """This function tests whether the kopald service is running in platform OS
    returns: int 0-success, raises exception-error
    """
    return opTestInbandIPMI.test_ipmi_inband_open_interface()


def test_hmi_proc_recv_done():
    """This function tests HMI recoverable error: processor recovery done
    returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_PROC_RECV_DONE)


def test_hmi_proc_recv_error_masked():
    """This function tests HMI recoverable error: proc_recv_error_masked
    returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_PROC_RECV_ERROR_MASKED)


def clear_gard_entries():
    """This function reboots the system and then clears any hardware gards through gard utility.
    And finally reboots the system again to stable point.
    returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.clearGardEntries()


def test_hmi_malfunction_alert():
    """This function tests HMI Malfunction alert: Core checkstop functionality
    returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_MALFUNCTION_ALERT)


def test_hmi_hypervisor_resource_error():
    """This function tests HMI: Hypervisor resource error functionality
        returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR)


def test_prd_driver():
    """This function tests PRD-processor runtime diagnostic functionality
        returns: int 0-success, raises exception-error
    """
    return opTestPrdDriver.testPrdDriver()


def test_tfmr_errors():
    """This function tests timer facility related error injections
        returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.TFMR_ERRORS)


def test_tod_errors():
    """This function tests chip TOD error injections
        returns: int 0-success, raises exception-error
    """
    return opTestHMIHandling.testHMIHandling(BMC_CONST.TOD_ERRORS)


def test_ipmi_lock_mode():
    """This function tests IPMI lock mode functionality
        returns: int 0-success, raises exception-error
    """
    return opTestIPMILockMode.test_ipmi_lock_mode()


def test_ipmi_power_control():
    """This function tests IPMI Power Control Operations
        returns: int 0-success, raises exception-error
    """
    return opTestIPMIPowerControl.testIPMIPowerControl()


def test_ipmi_inband_usb_interface():
    """This function tests inband ipmi through USB interface(BT)
    returns: int 0-success, raises exception-error
    """
    return opTestInbandUsbInterface.test_ipmi_inband_usb_interface()


def test_oob_ipmi():
    """This function tests Out-of-band IPMI functionality
        returns: int 0-success, raises exception-error
    """
    return opTestOOBIPMI.test_oob_ipmi()


def test_mc_cold_reset_boot_sequence():
    """This function tests MC Cold reset boot sequence
        returns: int 0-success, raises exception-error
    """
    return opTestSystemBootSequence.testMcColdResetBootSequence()


def test_mc_warm_reset_boot_sequence():
    """This function tests MC Warm reset boot sequence
        returns: int 0-success, raises exception-error
    """
    return opTestSystemBootSequence.testMcWarmResetBootSequence()


def test_fan_control_enable_functionality():
    """This function tests Fan control enable functionality
        returns: int 0-success, raises exception-error
    """
    return opTestOOBIPMI.test_fan_control_algorithm_2(opTestOOBIPMI)


def test_fan_control_disable_functionality():
    """This function tests Fan control disable functionality
        returns: int 0-success, raises exception-error
    """
    return opTestOOBIPMI.test_fan_control_algorithm_1(opTestOOBIPMI)


def test_system_power_restore_policy_always_on():
    """This function tests System Power Policy always-on
        returns: int 0-success, raises exception-error
    """
    return opTestSystemBootSequence.testSystemPowerPolicyOn()


def test_system_power_restore_policy_always_off():
    """This function tests System Power Policy always-off
        returns: int 0-success, raises exception-error
    """
    return opTestSystemBootSequence.testSystemPowerPolicyOff()


def test_system_power_restore_policy_previous():
    """This function tests System Power Policy previous
        returns: int 0-success, raises exception-error
    """
    return opTestSystemBootSequence.testSystemPowerPolicyPrevious()


def test_nvram_ipmi_reprovision():
    """This function tests NVRAM Partition-IPMI Reprovision.
        returns: int 0-success, raises exception-error
    """
    return opTestIPMIReprovision.test_nvram_ipmi_reprovision()


def test_gard_ipmi_reprovision():
    """This function tests GARD Partition-IPMI Reprovision
        returns: int 0-success, raises exception-error
    """
    return opTestIPMIReprovision.test_gard_ipmi_reprovision()


def test_dropbear_safety():
    """This function tests for Dropbear. They are very dangerous and may attack
       at any time. We must deal with them.
        returns: int 0-success, raises exception-error
    """
    return opTestDropbearSafety.test_dropbear_running()


def test_bmc_cold_reset_effects():
    """This function tests BMC Cold reset versus host FW functionality
        returns: int 0-success, raises exception-error
    """
    return opTestMCColdResetEffects.test_bmc_cold_reset_effects()


def test_list_pci_device_info():
    """This function just tests detected pci devices at petitboot and host OS
        known good output data
        returns: int 0-success, raises exception-error
    """
    return opTestPCI.test_host_pci_devices_info()


import os
import unittest
import xmlrunner
import sys

import ConfigParser
from common.OpTestSystem import OpTestSystem
from common.OpTestError import OpTestError
from common.OpTestConstants import OpTestConstants as BMC_CONST
import ci.source.op_inbound_hpm as op_inbound_hpm
import ci.source.op_occ_fvt as op_occ_fvt
import ci.source.op_fwts_fvt as op_fwts_fvt
import ci.source.op_outofband_firmware_update as op_outofband_firmware_update
import ci.source.op_firmware_component_update as op_firmware_component_update
import ci.source.op_bmc_web_update as op_bmc_web_update

reload(sys)
sys.setdefaultencoding('utf8')

class OpalPCI(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_pci_device_presence(self):
        test_list_pci_device_info()

class PetitbootEnvironmentTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_dropbear_not_running(self):
        opTestDropbearSafety.test_dropbear_running()

class FastResetTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_opal_fast_reboot(self):
        opTestFastReboot.test_opal_fast_reboot()

class OpalNVRAM(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_nvram_configuration(self):
        opTestNVRAM.test_nvram_configuration()

class BMCvsHostTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_bmc_cold_reset_effects(self):
        opTestMCColdResetEffects.test_bmc_cold_reset_effects()

class OpalIPMI(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_oob_ipmi(self):
        opTestOOBIPMI.test_oob_ipmi()

    def test_ipmi_inband_usb_interface(self):
        opTestInbandUsbInterface.test_ipmi_inband_usb_interface()

    def test_ipmi_inband_open_interface(self):
        opTestInbandIPMI.test_ipmi_inband_open_interface()

    def test_ipmi_power_control(self):
        opTestIPMIPowerControl.testIPMIPowerControl()

    def test_ipmi_lock_mode(self):
        opTestIPMILockMode.test_ipmi_lock_mode()

    def test_ipmi_heartbeat(self):
        opTestHeartbeat.test_kopald_service()

    def test_fan_control_enable_functionality(self):
        opTestOOBIPMI.test_fan_control_algorithm_2(opTestOOBIPMI)

    def test_fan_control_disable_functionality(self):
        opTestOOBIPMI.test_fan_control_algorithm_1(opTestOOBIPMI)

class OpalHMI(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_tfmr_errors(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.TFMR_ERRORS)

    def test_tod_errors(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.TOD_ERRORS)

    def test_tod_errors_on_single_core(self):
        opTestHMIHandling.host_enable_single_core()
        opTestHMIHandling.testHMIHandling(BMC_CONST.TOD_ERRORS)

    def test_hmi_proc_recv_done(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_PROC_RECV_DONE)

    def test_hmi_proc_recv_error_masked(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_PROC_RECV_ERROR_MASKED)

    def test_hmi_malfunction_alert(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_MALFUNCTION_ALERT)

    def test_hmi_hypervisor_resource_error(self):
        opTestHMIHandling.testHMIHandling(BMC_CONST.HMI_HYPERVISOR_RESOURCE_ERROR)

    def test_clear_gard_entries(self):
        opTestHMIHandling.clearGardEntries()

class OpalDrivers(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_prd_driver(self):
        opTestPrdDriver.testPrdDriver()

    def test_i2c_driver(self):
        opTestI2Cdriver.testI2Cdriver()

    def test_at24_driver(self):
        opTestAt24driver.testAt24driver()

    def test_real_time_clock(self):
        opTestRTCdriver.test_RTC_driver()

    def test_sensors(self):
        opTestSensors.test_hwmon_driver()

    def test_mtd_pnor_driver(self):
        opTestMtdPnorDriver.testMtdPnorDriver()

    def test_switch_endian_syscall(self):
        opTestSwitchEndianSyscall.testSwitchEndianSysCall()

class OpalBootTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_mc_cold_reset_boot_sequence(self):
        opTestSystemBootSequence.testMcColdResetBootSequence()

    def test_mc_warm_reset_boot_sequence(self):
        opTestSystemBootSequence.testMcWarmResetBootSequence()

    def test_system_power_restore_policy_previous(self):
        opTestSystemBootSequence.testSystemPowerPolicyPrevious()

    def test_system_power_restore_policy_always_on(self):
        opTestSystemBootSequence.testSystemPowerPolicyOn()

    def test_system_power_restore_policy_always_off(self):
        opTestSystemBootSequence.testSystemPowerPolicyOff()

class OpalReprovisionTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_nvram_ipmi_reprovision(self):
        opTestIPMIReprovision.test_nvram_ipmi_reprovision()

    def test_gard_ipmi_reprovision(self):
        opTestIPMIReprovision.test_gard_ipmi_reprovision()

class OpalEEH(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_basic_fenced_phb(self):
        opTestEEH.test_basic_fenced_phb()

    def test_max_fenced_phb(self):
        opTestEEH.test_max_fenced_phb()

    def test_basic_frozen_pe(self):
        opTestEEH.test_basic_frozen_pe()

class OpalFSPTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_system_dump(self):
        opTestDumps.test_system_dump()

    def test_fipsdump(self):
        opTestDumps.test_fipsdump()

class OpalKernelCrashTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_kernel_crash_kdump_disable(self):
        opTestKernel.test_kernel_crash_kdump_disable()

    def test_kernel_crash_kdump_enable(self):
        opTestKernel.test_kernel_crash_kdump_enable()

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='%s/test-reports' % full_path))
