#!/usr/bin/env python2
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

'''
Test Cronus
-----------

Tests a bunch of Cronus

'''

import os
import time
from datetime import datetime
import subprocess
import traceback

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import UnexpectedCase

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class Cronus(unittest.TestCase):
    '''
    Cronus Class
    --run-suite cronus
    --run testcases.testCronus.Runtime
    --run testcases.testCronus.HostOff
    or run the individual tests

    SPECIAL NOTE: Cronus commands need the host powered on,
    the HostOff class is left here as a test aide.

    You need to have installed Cronus (on op-test box) prior to attempting to run this test.

    External Portal: https://www-355.ibm.com/systems/power/openpower/systemTools.xhtml

    Internal Portals:
    https://rchgsa.ibm.com/gsa/rchgsa/projects/o/optk/delivery/labtools/p9/latest/ub1604/
    https://rchgsa.ibm.com/gsa/rchgsa/projects/o/optk/delivery/labtools/p9/latest/ub1804/
    https://rchgsa.ibm.com/gsa/rchgsa/projects/o/optk/delivery/labtools/p9/latest/deb9/
    https://rchgsa.ibm.com/gsa/rchgsa/projects/o/optk/delivery/labtools/p9/latest/fc29/
    https://rchgsa.ibm.com/gsa/rchgsa/projects/o/optk/delivery/labtools/p9/latest/el7/
    Docs: /gsa/rchgsa/projects/o/optk/delivery/labtools/p9/docs/

    Example for Ubuntu 16.04, download and install:
    opltk-common_20181218-1.ub1604_amd64.deb
    opltk-p9-cronus-p9_20181218-1.ub1604_amd64.deb
    opltk-p9-cronus-p9-ibmsys_20181218-1.ub1604_amd64.deb
    opltk-p9-cronus-shared_20181218-1.ub1604_amd64.deb
    opltk-p9-ecmd_20181218-1.ub1604_amd64.deb
    opltk-p9-crondump_20181218-1.ub1604_amd64.deb

    To manually run some commands to checkout your install:
    (when running op-test this is all automated for you)

    source /etc/profile.d/openpower.sh  (done in shell login after install, logg out/in, so this is optional)
    ecmdsetup auto cro p9 dev
    ecmdtargetsetup -n "debs_wsbmc012" -env hw -sc "k0:eth:9.3.21.43" -bmc "k0:eth:9.3.21.43" -bmcid "k0:root" -bmcpw "k0:0penBmc"
    target debs_wsbmc012
    setupsp
    crodetcnfg witherspoon (Witherspoon is the only one supported so far)
    ecmdquery chips -dc
    getcfam pu 1007 -all
    crondump -o /tmp -f ~/op-test-framework/HDCT.txt

    '''
    @classmethod
    def setUpClass(cls):
        cls.conf = OpTestConfiguration.conf
        if "OpenBMC" not in cls.conf.args.bmc_type:
            # kick out early so setUp can skipTest
            log.debug("Skipping setUpClass so setUp instance can "
                      "skiptest without having to power cycle, etc")
            return
        cls.cv_SYSTEM = cls.conf.system()
        cls.cv_BMC = cls.conf.bmc()
        cls.rest = cls.conf.system().rest

        try:
            if cls.desired == OpSystemState.OFF:
                cls.cv_SYSTEM.goto_state(OpSystemState.OFF)
            else:
                cls.cv_SYSTEM.goto_state(OpSystemState.OS)
        except Exception as e:
            log.debug(
                "Unable to find cls.desired, probably a test code problem, Exception={}".format(e))
            cls.cv_SYSTEM.goto_state(OpSystemState.OS)

    def setUp(self):
        # skipTest needs an instance of the class, so this is as early as we can catch
        if "OpenBMC" not in self.conf.args.bmc_type:
            log.debug("Skipping test={}, currently only OpenBMC supported "
                      "for running Cronus".format(self._testMethodName))
            self.skipTest("Skipping test={}, currently only OpenBMC supported "
                          "for running Cronus".format(self._testMethodName))


class Runtime(Cronus, unittest.TestCase):
    '''
    Runtime Class performs tests with Host On
    HostOff Class will turn the Host Off
    --run testcases.testCronus.Runtime
    --run testcases.testCronus.HostOff
    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OS
        super(Runtime, cls).setUpClass()

    def test_query_chips(self):
        '''
        Cronus ecmdquery chips
        --run testcases.testCronus.Runtime.test_query_chips
        --run testcases.testCronus.HostOff.test_query_chips
        '''
        command = "ecmdquery chips -dc"
        try:
            output = self.conf.util.cronus_run_command(
                command=command, minutes=1)
        except Exception as e:
            log.warning("Problem with cronus_run_command='{}', Exception={}"
                        .format(command, e))
            raise unittest.SkipTest("Cronus problem, skipping")

    def test_getcfam(self):
        '''
        Cronus getcfam
        --run testcases.testCronus.Runtime.test_getcfam
        --run testcases.testCronus.HostOff.test_getcfam
        '''
        command = "getcfam pu 1007 -all"
        try:
            output = self.conf.util.cronus_run_command(
                command=command, minutes=1)
        except Exception as e:
            log.warning("Problem with cronus_run_command='{}', Exception={}"
                        .format(command, e))
            raise unittest.SkipTest("Cronus problem, skipping")

    def test_crondump(self):
        '''
        Cronus crondump
        --run testcases.testCronus.Runtime.test_crondump
        --run testcases.testCronus.HostOff.test_crondump

        The default HDCT /opt/openpower/p9/crondump/HDCT_P9 will stop clocks
        on the processor requiring clearing the GARD, e.g. for Witherspoon
        On the BMC: rm /media/pnor-prsv/GUARD
        Word is that the collection time may vary from 2-10 hours (beware).

        If using the HDCT.txt provided in op-test the stopclocks/ring collection
        is NOT performed, so you can collect without needing to clear the GARD.
        '''

        if self.conf.args.cronus_dump_directory is None:
            crondump_dir = self.conf.logdir
        else:
            crondump_dir = self.conf.args.cronus_dump_directory
            if (not os.path.exists(crondump_dir)):
                os.makedirs(crondump_dir)
        if not os.access(crondump_dir, os.X_OK | os.W_OK):
            log.error("Cronus problem accessing cronus-dump-directory, "
                      "check for WRITE permissions on '{}'"
                      .format(crondump_dir))
            self.assertTrue(False, "Cronus problem accessing "
                            "cronus-dump-directory, check for WRITE permissions on '{}'"
                            .format(crondump_dir))
        cronus_datetime = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        log.debug("crondump output will be '{}/scanoutlog.{}.{}'"
                  .format(crondump_dir,
                          self.conf.args.cronus_dump_suffix,
                          cronus_datetime))
        command = ("crondump -o {} -f {} -N {}.{}"
                   .format(crondump_dir,
                           self.conf.args.cronus_hdct,
                           self.conf.args.cronus_dump_suffix,
                           cronus_datetime))
        try:
            output = self.conf.util.cronus_run_command(
                command=command, minutes=5)
        except Exception as e:
            log.warning("Problem with cronus_run_command='{}', Exception={}"
                        .format(command, e))
            log.warning("crondump output will be '{}/scanoutlog.{}.{}'"
                        .format(crondump_dir,
                                self.conf.args.cronus_dump_suffix,
                                cronus_datetime))
            raise unittest.SkipTest("Cronus problem, skipping")


class HostOff(Runtime):
    '''
    Runtime Class performs tests with Host On
    HostOff Class will turn the Host Off
    --run testcases.testCronus.Runtime
    --run testcases.testCronus.HostOff

    SPECIAL NOTE: Cronus commands need the host powered on,
    the HostOff class is left here as a test aide.

    '''
    @classmethod
    def setUpClass(cls):
        cls.desired = OpSystemState.OFF
        super(Runtime, cls).setUpClass()


def host_off_suite():
    # run with Host powered OFF
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(HostOff))
    return s


def runtime_suite():
    # run with Host powered ON
    s = unittest.TestSuite()
    s.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(Runtime))
    return s
