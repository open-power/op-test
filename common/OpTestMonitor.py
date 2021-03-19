#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2019
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
Monitor library
---------------------
This adds a support to add user defined monitors
'''

import re
import os
import time
import threading

import OpTestConfiguration
from .OpTestSystem import OpSystemState
from .Exceptions import CommandFailed

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class monitorThread(threading.Thread):
    def __init__(self, cmd):
        threading.Thread.__init__(self)
        self.env = cmd['env']
        self.cmd = cmd['cmd']
        self.freq = int(cmd['freq'])
        self.name = cmd['name'] if cmd['name'] else self.cmd.replace(' ', '_')
        self.pattern = cmd["pattern"] if cmd["pattern"] else "*"
        self._stop_event = threading.Event()
        self.conf = OpTestConfiguration.conf
        # TODO: consider adding all monitor output into seperate folder
        self.host = self.conf.host()
        self.system = self.conf.system()
        self.console = None
        if self.env == 'sut':
            try:
                self.console = self.host.get_new_ssh_connection(self.name)
            except Exception as err:
                # might not be yet in OS state
                pass
        elif self.env == 'server':
            pass
        elif self.env == 'bmc':
            pass
        else:
            log.warning("Unknown env given to run monitors, give either sut to"
                        "run inside host or server to run ipmi commands")

    def run(self):
        log.info("Starting monitor %s" % self.name)
        self.executed = False
        pat = re.compile(r"%s" % self.pattern)
        self.monitor_output = os.path.join(self.conf.output, self.name)
        fd = open(self.monitor_output, "w+")
        while True:
            if self.freq > 0:
                if self.env == 'sut':
                    if self.system.state != OpSystemState.OS:
                        continue
                    if self.console:
                        try:
                            output = self.console.run_command(self.cmd)
                            parsed_out = pat.findall('\n'.join(output))
                            if parsed_out:
                                fd.write(str(parsed_out[0]))
                                fd.write('\n')
                        except CommandFailed as cf:
                            log.warning('Monitor cmd failed to run %s', self.cmd)
                    else:
                        # try to reconnect
                        log.warning('Reconnecting SSH console...')
                        self.console = self.host.get_new_ssh_connection(self.name)

                elif self.env == 'server':
                    # TODO:
                    log.warning("Yet to implement")
                    break
                elif self.env == 'bmc':
                    # TODO:
                    log.warning("Yet to implement")
                    break
                time.sleep(self.freq)
                if self.is_stopped():
                    fd.close()
                    break

            else:
                if not self.executed:
                    # FIXME: NEED add support for running long run cmds
                    if self.env == 'sut':
                        if self.system.state != OpSystemState.OS:
                            continue
                        if self.console:
                            try:
                                output = self.console.run_command(self.cmd)
                            except CommandFailed as cf:
                                log.warning('Monitor cmd failed to run %s', self.cmd)
                        else:
                            self.console = self.host.get_new_ssh_connection(self.name)
                            try:
                                output = self.console.run_command(self.cmd)
                                parsed_out = pat.findall('\n'.join(output))
                                if parsed_out:
                                    fd.write(str(parsed_out[0]))
                            except CommandFailed as cf:
                                log.warning('Monitor cmd failed to run %s', self.cmd)
                    elif self.env == 'server':
                        # TODO:
                        log.warning("Yet to implement")
                        break
                    elif self.env == 'bmc':
                        # TODO:
                        log.warning("Yet to implement")
                        break
                    self.executed = True
                if self.is_stopped():
                    fd.close()
                    break

    def stop(self):
        log.info("Stopping monitor %s", self.name)
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()

    def wait(self, delaysec=5):
        self._stop_event.wait(delaysec)


class Monitors(object):
    def __init__(self, monitor_cmd_path=None, monitor_cmd=None):
        """
        Monitor class to create monitor threads
        params: monitor_cmd_path: file with monitor information,by default it
                                   will use the 'monitors' file kept in basepath
        params: monitor_cmd: dict type optional monitor, if given will take the
                              precedence over monitor_cmd_path argument,
                              can be used inside testcase, E:g:-
                              {'cmd': vmstat,
                               'freq': 2,
                               'env': 'sut',
                               'name': 'vmstat-1'}
        """
        self.conf = OpTestConfiguration.conf
        self.path = monitor_cmd_path if monitor_cmd_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'monitors')
        if not os.path.isfile(self.path):
            log.warning("Check the monitor command path, given path is not valid: %s", self.path)
        self.monitors = []
        # Optional and if given takes precedence
        if monitor_cmd:
            self.monitors.append(monitor_cmd)
        else:
            self.monitors = self.parse_monitors()
        self.host = self.conf.host()
        self.system = self.conf.system()
        self.monitorthreads = []

    def parse_monitors(self):
        monitor_content = []
        monitor_list = []
        monitor = {'cmd': None,
                   'freq': 0,
                   'env': 'sut',
                   'name': None,
                   'pattern': None}
        temp = monitor.copy()
        try:
            with open(self.path) as monitor_obj:
                monitor_content = [line.strip('\n') for line in monitor_obj.readlines()]
        except Exception as err:
            log.warning("Error reading monitor cmd file")
            pass
        else:
            for item in monitor_content:
                if item.startswith("#"):
                    continue
                try:
                    temp['cmd'] = item.split(',')[0]
                    temp['freq'] = int(item.split(',')[1])
                    temp['env'] = item.split(',')[2]
                    temp['name'] = item.split(',')[3]
                    temp['pattern'] = item.split(',')[4]
                except IndexError:
                    pass
                monitor_list.append(temp.copy())
                temp = monitor.copy()
        finally:
            return monitor_list

    def create_monitor_threads(self):
        monitor_threads = []
        for prof in self.monitors:
            self.monitorthreads.append(monitorThread(prof))
        return self.monitorthreads

    def run(self):
        self.create_monitor_threads()
        for thread in self.monitorthreads:
            thread.start()

    def stop(self):
        for thread in self.monitorthreads:
            thread.stop()

    def join(self):
        for thread in self.monitorthreads:
            thread.join()
