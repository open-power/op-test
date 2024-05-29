#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2018
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
IPL Params
----------

This test verifies certain fw features are enabled/disabled during
IPL time as per expectation. These features will control run time
enablement of certain components.
'''

import unittest

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

import common.OpTestMambo as OpTestMambo
import common.OpTestQemu as OpTestQemu

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class IplParams():
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_HOST = conf.host()
        self.cv_IPMI = conf.ipmi()
        self.cv_SYSTEM = conf.system()

    def get_params_table(self):
        # P9 Nimbus DD2.3
        # this is HDAT Risk Level=4, which hostboot translates for OpenPOWER
        # if NOT /proc/device-tree/ipl-params/sys-params/elevated-risk-level, use table 0
        # hostboot src/usr/hdat/hdatiplparms.H
        p9_dd2_3_rl0_params = {}
        p9_dd2_3_rl0_params["enable"] = [
                                         "tm-suspend-mode",
                                         "inst-spec-barrier-ori31,31,0",
                                         "inst-l1d-flush-trig2",
                                         "fw-l1d-thread-split",
                                         "fw-count-cache-flush-bcctr2,0,0",
                                         "speculation-policy-favor-security",
                                         "needs-l1d-flush-msr-hv-1-to-0",
                                         "needs-l1d-flush-msr-pr-0-to-1",
                                         "needs-spec-barrier-for-bound-checks",
                                         "needs-count-cache-flush-on-context-switch",
                                         ]
        p9_dd2_3_rl0_params["disable"] = [
                                          "fw-bcctrl-serialized",
                                          "inst-l1d-flush-ori30,30,0",
                                          "fw-branch-hints-honored",
                                          "inst-thread-reconfig-control-trig0-1",
                                          "fw-count-cache-disabled",
                                          "fw-ltptr-serialized",
                                          "user-mode-branch-speculation",
                                          "needs-pmu-restricted",
                                         ]
        # P9 Nimbus DD2.3
        # this is HDAT Risk Level=5, which hostboot translates for OpenPOWER
        # if /proc/device-tree/ipl-params/sys-params/elevated-risk-level, use table 1
        # hostboot src/usr/hdat/hdatiplparms.H
        p9_dd2_3_rl1_params = {}
        p9_dd2_3_rl1_params["enable"] = [
                                         "tm-suspend-mode",
                                        ]
        p9_dd2_3_rl1_params["disable"] = [
                                          "inst-spec-barrier-ori31,31,0",
                                          "inst-l1d-flush-trig2",
                                          "fw-l1d-thread-split",
                                          "fw-count-cache-flush-bcctr2,0,0",
                                          "speculation-policy-favor-security",
                                          "needs-l1d-flush-msr-hv-1-to-0",
                                          "needs-l1d-flush-msr-pr-0-to-1",
                                          "needs-spec-barrier-for-bound-checks",
                                          "needs-count-cache-flush-on-context-switch",
                                          "fw-bcctrl-serialized",
                                          "inst-l1d-flush-ori30,30,0",
                                          "fw-branch-hints-honored",
                                          "inst-thread-reconfig-control-trig0-1",
                                          "fw-count-cache-disabled",
                                          "fw-ltptr-serialized",
                                          "user-mode-branch-speculation",
                                          "needs-pmu-restricted",
                                         ]
        # P9 DD2.2 Risk level 0 fw feature table(System boots always with default risk level 0)
        p9_dd2_2_rl0_params = {}
        p9_dd2_2_rl0_params["enable"] = [
                                         "fw-count-cache-disabled",
                                         "fw-l1d-thread-split",
                                         "inst-l1d-flush-trig2",
                                         "inst-spec-barrier-ori31,31,0",
                                         "needs-l1d-flush-msr-hv-1-to-0",
                                         "needs-l1d-flush-msr-pr-0-to-1",
                                         "needs-spec-barrier-for-bound-checks",
                                         "speculation-policy-favor-security",
                                         "tm-suspend-mode",
                                         "fw-branch-hints-honored",
                                         ]
        p9_dd2_2_rl0_params["disable"] = [
                                          "inst-l1d-flush-ori30,30,0",
                                          "fw-bcctrl-serialized",
                                          "inst-thread-reconfig-control-trig0-1",
                                          "fw-ltptr-serialized",
                                          "user-mode-branch-speculation",
                                         ]
        # P9 DD2.2 Risk level 1 fw feature table
        p9_dd2_2_rl1_params = {}
        p9_dd2_2_rl1_params["enable"] = [
                                         "fw-l1d-thread-split",
                                         "fw-bcctrl-serialized",
                                         "inst-l1d-flush-trig2",
                                         "inst-spec-barrier-ori31,31,0",
                                         "needs-l1d-flush-msr-hv-1-to-0",
                                         "needs-l1d-flush-msr-pr-0-to-1",
                                         "needs-spec-barrier-for-bound-checks",
                                         "speculation-policy-favor-security",
                                         "tm-suspend-mode",
                                         "fw-branch-hints-honored",
                                         "user-mode-branch-speculation"
                                         ]
        p9_dd2_2_rl1_params["disable"] = [
                                          "fw-count-cache-disabled",
                                          "inst-l1d-flush-ori30,30,0",
                                          "inst-thread-reconfig-control-trig0-1",
                                          "fw-ltptr-serialized"]

        table_0 = {
            '2.2'    : p9_dd2_2_rl0_params,
            '2.3'    : p9_dd2_3_rl0_params,
        }
        table_1 = {
            '2.2'    : p9_dd2_2_rl1_params,
            '2.3'    : p9_dd2_3_rl1_params,
        }

        # P8 fw-feature table
        p8_params = {}
        p8_params["enable"] = [
                               "inst-l1d-flush-ori30,30,0",
                               "fw-count-cache-disabled",
                               "inst-spec-barrier-ori31,31,0",
                               "needs-l1d-flush-msr-hv-1-to-0",
                               "needs-l1d-flush-msr-pr-0-to-1",
                               "needs-spec-barrier-for-bound-checks",
                               "speculation-policy-favor-security",
                               "tm-suspend-mode",
                               "fw-branch-hints-honored"
                               ]
        p8_params["disable"] = [
                               "fw-bcctrl-serialized",
                               "inst-thread-reconfig-control-trig0-1",
                               "fw-ltptr-serialized",
                               "inst-l1d-flush-trig2",
                               "fw-l1d-thread-split",
                               "user-mode-branch-speculation"
                               ]

        self.cpu = ''.join(self.c.run_command(
            "grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))
        if self.cpu in ["POWER9", "POWER9P"]:
            self.revision = ''.join(self.c.run_command(
                "grep '^revision' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/ (.*)//;'"))
            log.debug("self.cpu={} self.revision={}".format(self.cpu, self.revision))
            if self.revision not in ["2.2", "2.3"]:
                return {}
            rl = 0
            try:
                self.c.run_command(
                    "ls --color=never /proc/device-tree/ipl-params/sys-params/elevated-risk-level")
                rl = 1
            except CommandFailed:
                log.debug("NO /proc/device-tree/ipl-params/sys-params/elevated-risk-level found, proceeding with default risk level comparisons")
                rl = 0

            if rl == 0:
                return table_0[self.revision]
            elif rl == 1:
                return table_1[self.revision]
            else:
                return {}
        elif self.cpu in ["POWER8", "POWER8E"]:
            return p8_params
        else:
            log.error(
                "CPU %s doesn't have the supported fw-feature set" % self.cpu)
            return {}

    def file_exists(self, path):
        try:
            self.c.run_command(
                "ls --color=never /proc/device-tree/ibm,opal/fw-features/%s" % path)
            exist = True
        except CommandFailed:
            exist = False
        return exist

    def test_feature_enable(self):
        self.setup_test()
        params = self.get_params_table()
        log.debug(
            "List of features which are expected to be in enabled state\n{}".format(params))
        if not params:
            # skip the test if the processor is not GA level (for such cases as op910 supports only dd2.1)
            log.warning("Skipping IplParams test, we did not get ANY params to compare against, fw-feature set table not found or processor not supported")
            raise unittest.SkipTest(
                "Skipping IplParams test, we did not get ANY params to compare against, fw-feature set table not found or processor not supported")

        fail_params = {}
        fail_params["enable"] = []
        fail_params["not-found"] = []

        # Verify the params feature to be enabled
        for param in params["enable"]:
            path = "%s/enabled" % param
            if not self.file_exists(path):
                path = "%s/disabled" % param
                if self.file_exists(path):
                    fail_params["enable"].append(param)
                else:
                    fail_params["not-found"].append(param)
        if fail_params["enable"] or fail_params["not-found"]:
            message = "fw-feature expected to be enabled,\n\tdisabled list: %s\n\tnot-found list: %s" % (
                fail_params["enable"], fail_params["not-found"])
            self.assertTrue(False, message)

    def test_feature_disable(self):
        self.setup_test()
        params = self.get_params_table()
        log.debug(
            "List of features which are expected to be in disabled state\n{}".format(params))
        if not params:
            # skip the test if the processor is not GA level (for such cases as op910 supports only dd2.1)
            log.warning("Skipping IplParams test, we did not get ANY params to compare against, fw-feature set table not found or processor not supported")
            raise unittest.SkipTest(
                "Skipping IplParams test, we did not get ANY params to compare against, fw-feature set table not found or processor not supported")

        fail_params = {}
        fail_params["disable"] = []
        fail_params["not-found"] = []

        # Verify the params feature to be disabled
        for param in params["disable"]:
            path = "%s/disabled" % param
            if not self.file_exists(path):
                path = "%s/enabled" % param
                if self.file_exists(path):
                    fail_params["disable"].append(param)
                else:
                    fail_params["not-found"].append(param)

        if fail_params["disable"] or fail_params["not-found"]:
            message = "fw-feature expected to be disabled,\n\tenabled list: %s,\n\tnot-found list: %s" % (
                fail_params["disable"], fail_params["not-found"])
            self.assertTrue(False, message)


class Skiroot(IplParams, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.c = self.cv_SYSTEM.console
        if (isinstance(self.cv_SYSTEM.console, OpTestQemu.QemuConsole)) \
                or (isinstance(self.cv_SYSTEM.console, OpTestMambo.MamboConsole)):
            raise unittest.SkipTest("QEMU/Mambo running so skipping tests")


class Host(IplParams, unittest.TestCase):
    def setup_test(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.c = self.cv_HOST.get_ssh_connection()
        if (isinstance(self.cv_SYSTEM.console, OpTestQemu.QemuConsole)) \
                or (isinstance(self.cv_SYSTEM.console, OpTestMambo.MamboConsole)):
            raise unittest.SkipTest("QEMU/Mambo running so skipping tests")
