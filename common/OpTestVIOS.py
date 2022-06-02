#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2022
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
#

import os
import re
import time

import common
from common.Exceptions import CommandFailed
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestVIOS():


    def __init__(self, vios_name, vios_ip, vios_username, vios_password, conf=None):
        self.name = vios_name
        self.host = vios_ip
        self.user = vios_username
        self.passwd = vios_password
        self.ssh = common.OpTestSSH.OpTestSSH(vios_ip, vios_username, vios_password)
        self.conf = conf

    def set_system(self, system):
        self.ssh.set_system(system)

    def gather_logs(self, list_of_commands=[], output_dir=None):
        if not output_dir:
            output_dir = "Vios_Logs_%s" % (time.asctime(time.localtime())).replace(" ", "_")
        output_dir = os.path.join(self.conf.host().results_dir, output_dir, self.name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        default_commands = ['cat /proc/version', 'ioslevel', 'errlog', 'snap']
        list_of_commands.extend(default_commands)

        try:
            for cmd in set(list_of_commands):
                output = "\n".join(self.run_command(r"%s" % cmd, timeout=600))
                filename = "%s.log" % '-'.join((re.sub(r'[^a-zA-Z0-9]', ' ', cmd)).split())
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'w') as f:
                    f.write(output)
            snap_backup_filename = time.strftime("%d_%m_%Y_%H_%M_%S") + "_snap.pax.Z"
            self.run_command("mv snap.pax.Z %s" % snap_backup_filename)
            log.warn("Please collect the snap logs. snap.pax.Z renamed to %s." % snap_backup_filename)
            return True
        except CommandFailed as cmd_failed:
            raise cmd_failed

    def run_command(self, cmd, timeout=60):
        return self.ssh.run_command(cmd, timeout)
