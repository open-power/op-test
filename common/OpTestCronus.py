#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestCronus.py $
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
import subprocess
import traceback
import socket

from .Exceptions import UnexpectedCase
from .OpTestSystem import OpSystemState

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

match_list = ["CRONUS_HOME",
              "OPTKROOT",
              "ECMD_DLL_FILE",
              "ECMD_EXE",
              "ECMD_ARCH",
              "ECMD_TARGET",
              "ECMD_PRODUCT",
              "LD_LIBRARY_PATH",
              "ECMD_PATH",
              "ECMD_PLUGIN",
              "ECMD_RELEASE",
              "ECMDPERLBIN",
              "PERL5LIB",
              "PYTHONPATH",
              "PATH",
              "LABCPU",
              "LABTS",
              "SBE_TOOLS_PATH",
              ]


class OpTestCronus():
    '''
    OpTestCronus Class for Cronus Setup and Environment Persistance

    See testcases/testCronus.py for Cronus Install and Setup
    '''

    def __init__(self, conf=None):
        self.conf = conf
        self.env_ready = False  # too early to know if system supports cronus
        self.cronus_ready = False  # flag to indicate setup complete
        self.cv_SYSTEM = None  # flag to show if we have a system yet
        self.capable = False
        self.current_target = None
        self.cronus_env = None

    def dump_env(self):
        for xs in sorted(match_list):
            log.debug("os.environ[{}]={}".format(xs, os.environ[xs]))

    def setup(self):
        self.cv_SYSTEM = self.conf.system()  # we hope its not still too early
        # test no op_system
        self.capable = self.cv_SYSTEM.cronus_capable()
        if not self.cv_SYSTEM.cronus_capable():
            log.debug("System is NOT cronus_capable={}".format(
                self.cv_SYSTEM.cronus_capable()))
            # safeguards
            self.env_ready = False
            self.cronus_ready = False
            return
        # rc=139 is a segfault (-11)
        log.debug("gethostbyname starts '{}'".format(self.conf.args.bmc_ip))
        just_ip = socket.gethostbyname(self.conf.args.bmc_ip)
        log.debug("gethostbyname ends '{}'".format(just_ip))
        proposed_target = just_ip + "_optest_target"
        ecmdtargetsetup_string = ("ecmdtargetsetup -n \"{}\" "
                                  "-env hw -sc \"k0:eth:{}\" "
                                  "-bmc \"k0:eth:{}\" "
                                  "-bmcid \"k0:{}\" "
                                  "-bmcpw \"k0:{}\""
                                  .format(proposed_target,
                                          just_ip,
                                          just_ip,
                                          self.conf.args.bmc_username,
                                          self.conf.args.bmc_password))
        try:
            op_cronus_login = "/etc/profile.d/openpower.sh"
            self.cronus_env = os.path.join(self.conf.logdir, "cronus.env")
            if not os.path.isfile(op_cronus_login):
                log.warning("NO Cronus installed, check the system")
                return
        except Exception as e:
            log.warning("Cronus setup problem check the installation,"
                        " Exception={}".format(e))
        try:
            source_string = ("source {} && "
                             "ecmdsetup auto cro {} {} && "
                             "printenv >{}"
                             .format(op_cronus_login,
                                     self.conf.args.cronus_product,
                                     self.conf.args.cronus_code_level,
                                     self.cronus_env))
            command = "source"
            stdout_value = self.conf.util.cronus_subcommand(
                command=source_string, minutes=2)
            log.debug("source stdout='{}'".format(stdout_value))

            if not os.path.isfile(self.cronus_env):
                log.error("NO Cronus environment "
                          "data captured, this is a problem")
                raise UnexpectedCase(message="NO Cronus environment "
                                     "data captured, this is a problem")
            ecmd_dict = {}
            with open(self.cronus_env) as f:
                for line in f:
                    new_line = line.split("=")
                    for xs in match_list:
                        if xs == new_line[0]:
                            if len(new_line) >= 2:
                                ecmd_dict[new_line[0]] = new_line[1].rstrip()
            log.debug("ECMD's len(match_list)={} len(ecmd_dict)={}, "
                      "these may not match"
                      .format(len(match_list), len(ecmd_dict)))
            for k, v in sorted(ecmd_dict.items()):
                log.debug("ecmd_dict[{}]={}".format(k, ecmd_dict[k]))
                os.environ[k] = ecmd_dict[k]

            self.env_ready = True
            log.debug(
                "cronus setup setting self.env_ready={}".format(self.env_ready))

        except subprocess.CalledProcessError as e:
            tb = traceback.format_exc()
            raise UnexpectedCase(message="Cronus environment issue rc={} "
                                 "output={} traceback={}"
                                 .format(e.returncode, e.output, tb))
        except Exception as e:
            tb = traceback.format_exc()
            raise UnexpectedCase(message="Cronus environment issue "
                                 "Exception={} traceback={}"
                                 .format(e, tb))

        try:
            command = "ecmdtargetsetup"
            stdout_value = self.conf.util.cronus_subcommand(
                command=ecmdtargetsetup_string, minutes=2)
            log.debug("ecmdtargetsetup stdout='{}'".format(stdout_value))

            target_string = "target {}".format(proposed_target)
            command = "target"
            stdout_value = self.conf.util.cronus_subcommand(
                command=target_string, minutes=2)
            log.debug("target stdout='{}'".format(stdout_value))

            self.current_target = proposed_target
            log.debug("ECMD_TARGET={}".format(self.current_target))
            # need to manually update the environment to persist
            os.environ['ECMD_TARGET'] = self.current_target

            command = "setupsp"
            stdout_value = self.conf.util.cronus_subcommand(
                command=command, minutes=2)
            log.debug("target stdout='{}'".format(stdout_value))

            if self.cv_SYSTEM.get_state() not in [OpSystemState.OFF]:
                command = "crodetcnfg"
                crodetcnfg_string = ("crodetcnfg {}"
                                     .format(self.conf.args.cronus_system_type))
                stdout_value = self.conf.util.cronus_subcommand(
                    command=crodetcnfg_string, minutes=2)
                log.debug("crodetcnfg stdout='{}'".format(stdout_value))
                self.cronus_ready = True
                log.debug("cronus_ready={}".format(self.cronus_ready))
            else:
                log.warning("Cronus problem setting up, we need the "
                            "System powered ON and it is OFF")
                raise UnexpectedCase(state=self.cv_SYSTEM.get_state(),
                                     message=("Cronus setup problem, we need"
                                              " the System powered ON and it is OFF"))
        except subprocess.CalledProcessError as e:
            tb = traceback.format_exc()
            raise UnexpectedCase(message="Cronus setup issue rc={} output={}"
                                 " traceback={}"
                                 .format(e.returncode, e.output, tb))
        except Exception as e:
            tb = traceback.format_exc()
            raise UnexpectedCase(message="Cronus setup issue Exception={}"
                                 " traceback={}".format(e, tb))
