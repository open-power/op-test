#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-auto-test/ci/source/op_opal_fvt.py $
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


def _config_read():
    """ returns bmc system and test config options """
    bmcConfig = ConfigParser.RawConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'op_ci_tools.cfg')
    print configFile
    bmcConfig.read(configFile)
    return dict(bmcConfig.items('bmc')), dict(bmcConfig.items('test')), dict(bmcConfig.items('lpar'))

''' Read the configuration settings into global space so they can be used by
    other functions '''

bmcCfg, testCfg, lparCfg = _config_read()
opTestSensors = OpTestSensors(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg['usernameipmi'],
                              bmcCfg['passwordipmi'],
                              testCfg['ffdcdir'], lparCfg['lparip'],
                              lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestSwitchEndianSyscall = OpTestSwitchEndianSyscall(bmcCfg['ip'],
                                                      bmcCfg['username'],
                                                      bmcCfg['password'],
                                                      bmcCfg['usernameipmi'],
                                                      bmcCfg['passwordipmi'],
                                                      testCfg['ffdcdir'],
                                                      lparCfg['lparip'],
                                                      lparCfg['lparuser'],
                                                      lparCfg['lparpasswd'])

opTestRTCdriver = OpTestRTCdriver(bmcCfg['ip'],
                                  bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg['usernameipmi'],
                                  bmcCfg['passwordipmi'],
                                  testCfg['ffdcdir'],
                                  lparCfg['lparip'],
                                  lparCfg['lparuser'],
                                  lparCfg['lparpasswd'])

opTestAt24driver = OpTestAt24driver(bmcCfg['ip'], bmcCfg['username'],
                                    bmcCfg['password'],
                                    bmcCfg['usernameipmi'],
                                    bmcCfg['passwordipmi'],
                                    testCfg['ffdcdir'], lparCfg['lparip'],
                                    lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestI2Cdriver = OpTestI2Cdriver(bmcCfg['ip'], bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg['usernameipmi'],
                                  bmcCfg['passwordipmi'],
                                  testCfg['ffdcdir'], lparCfg['lparip'],
                                  lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestHeartbeat = OpTestHeartbeat(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg['usernameipmi'],
                              bmcCfg['passwordipmi'],
                              testCfg['ffdcdir'], lparCfg['lparip'],
                              lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestMtdPnorDriver = OpTestMtdPnorDriver(bmcCfg['ip'], bmcCfg['username'],
                                          bmcCfg['password'],
                                          bmcCfg['usernameipmi'],
                                          bmcCfg['passwordipmi'],
                                          testCfg['ffdcdir'], lparCfg['lparip'],
                                          lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestInbandIPMI = OpTestInbandIPMI(bmcCfg['ip'], bmcCfg['username'],
                              bmcCfg['password'],
                              bmcCfg['usernameipmi'],
                              bmcCfg['passwordipmi'],
                              testCfg['ffdcdir'], lparCfg['lparip'],
                              lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestHMIHandling = OpTestHMIHandling(bmcCfg['ip'], bmcCfg['username'],
                                          bmcCfg['password'],
                                          bmcCfg['usernameipmi'],
                                          bmcCfg['passwordipmi'],
                                          testCfg['ffdcdir'], lparCfg['lparip'],
                                          lparCfg['lparuser'], lparCfg['lparpasswd'])

opTestPrdDriver = OpTestPrdDriver(bmcCfg['ip'], bmcCfg['username'],
                                  bmcCfg['password'],
                                  bmcCfg['usernameipmi'],
                                  bmcCfg['passwordipmi'],
                                  testCfg['ffdcdir'], lparCfg['lparip'],
                                  lparCfg['lparuser'], lparCfg['lparpasswd'])


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
    return opTestInbandIPMI.test_ipmi_inband_functionality()


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
