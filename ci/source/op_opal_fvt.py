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
from testcases.OpTestMtdPnorDriver import OpTestMtdPnorDriver
from testcases.OpTestInbandIPMI import OpTestInbandIPMI
from testcases.OpTestPrdDriver import OpTestPrdDriver
from testcases.OpTestInbandUsbInterface import OpTestInbandUsbInterface
from testcases.OpTestOOBIPMI import OpTestOOBIPMI
from testcases.OpTestSystemBootSequence import OpTestSystemBootSequence
from testcases.OpTestMCColdResetEffects import OpTestMCColdResetEffects
from testcases.OpTestNVRAM import OpTestNVRAM
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


opTestPrdDriver = OpTestPrdDriver(bmcCfg['ip'], bmcCfg['username'],
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

opTestNVRAM = OpTestNVRAM(bmcCfg['ip'], bmcCfg['username'],
                          bmcCfg['password'],
                          bmcCfg.get('usernameipmi'),
                          bmcCfg.get('passwordipmi'),
                          testCfg['ffdcdir'], hostCfg['hostip'],
                          hostCfg['hostuser'], hostCfg['hostpasswd'])

#opTestDumps = OpTestDumps(bmcCfg['ip'], bmcCfg['username'],
#                          bmcCfg['password'],
#                          bmcCfg.get('usernameipmi'),
#                          bmcCfg.get('passwordipmi'),
#                          testCfg['ffdcdir'], hostCfg['hostip'],
#                          hostCfg['hostuser'], hostCfg['hostpasswd'])

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

def test_prd_driver():
    """This function tests PRD-processor runtime diagnostic functionality
        returns: int 0-success, raises exception-error
    """
    return opTestPrdDriver.testPrdDriver()

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


def test_bmc_cold_reset_effects():
    """This function tests BMC Cold reset versus host FW functionality
        returns: int 0-success, raises exception-error
    """
    return opTestMCColdResetEffects.test_bmc_cold_reset_effects()


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
import ci.source.op_outofband_firmware_update as op_outofband_firmware_update
import ci.source.op_firmware_component_update as op_firmware_component_update
import ci.source.op_bmc_web_update as op_bmc_web_update

reload(sys)
sys.setdefaultencoding('utf8')

class PetitbootEnvironmentTests(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

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

    def test_fan_control_enable_functionality(self):
        opTestOOBIPMI.test_fan_control_algorithm_2(opTestOOBIPMI)

    def test_fan_control_disable_functionality(self):
        opTestOOBIPMI.test_fan_control_algorithm_1(opTestOOBIPMI)

class OpalDrivers(unittest.TestCase):
    def setUp(self):
        bmcCfg, testCfg, hostCfg = _config_read()
        test_init()

    def test_prd_driver(self):
        opTestPrdDriver.testPrdDriver()

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
