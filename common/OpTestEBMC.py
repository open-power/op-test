#!/usr/bin/env python3
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


import time
import requests

from .Exceptions import HTTPCheck
from .OpTestConstants import OpTestConstants as BMC_CONST

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class EBMCHostManagement():
    '''
    EBMCHostManagement Class
    EBMC methods to manage the Host
    '''

    def __init__(self, conf=None,
                 ip=None,
                 username=None,
                 password=None):
        self.conf = conf
        self.util = conf.util
        self.hostname = ip
        self.username = username
        self.password = password
        self.util.PingFunc(
            self.hostname, totalSleepTime=BMC_CONST.PING_RETRY_FOR_STABILITY)
        if self.conf.util_bmc_server is None:
            self.conf.util.setup(config='REST')
        r = self.conf.util_bmc_server.login()
        self.wait_for_bmc_runtime()

    def get_power_state(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Current Host Power State
        GET   redfish/v1/Systems/system/
        '''
        uri = '/redfish/v1/Systems/system/'
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('PowerState')

    def get_host_state(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Host State
        GET
        /redfish/v1/Systems/system/
        '''
        uri = '/redfish/v1/Systems/system/'
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('BootProgress').get("LastState")

    def get_bmc_state(self):
        '''
        Get BMC State
        '''
        # caller drives retry
        uri = "/redfish/v1/Managers/bmc"
        r = self.conf.util_bmc_server.get(uri=uri)
        if r.status_code != requests.codes.ok:
            problem = "[{}] Description={}".format(r.json().get(
                'message'), "".join(r.json().get('data').get('State')))
            raise HTTPCheck(
                message="HTTP problem getting CurrentBMCState {}".format(problem))
        return r.json().get('Status').get('State')

    def wait_bmc(self, key=None, value_target=None, token=None, minutes=10):
        '''
        Wait on BMC
        Given a token, target, key wait for a match
        '''
        # handles data as a dictionary or string
        if key is None:
            return False
        timeout = time.time() + 60*minutes
        while True:
            r = self.conf.util_bmc_server.get(uri=token, minutes=minutes)
            if type(r.json().get(key[0])) == type(dict()):
                if key[1] is None:
                    for key, value in r.json().get(key[0]):
                        if r.json().get(key[0]).get(key) == value_target:
                            break
                else:
                    if r.json().get(key[0]).get(key[1]) == value_target:
                        break
            else:
                if value_target in r.json().get(key[0]):
                    break
            if time.time() > timeout:
                log.warning("We timed out waiting for \"{}\", we waited {} minutes for \"{}\"".format(
                    token, minutes, value_target))
                raise HTTPCheck(message="HTTP problem getting \"{}\", we waited {} minutes for \"{}\"".format(
                    token, minutes, value_target))
            time.sleep(5)
        return True

    def wait_for_bmc_runtime(self, timeout=10):
        '''
        Wait for BMC Runtime
        '''
        status = self.wait_bmc(token="/redfish/v1/Managers/bmc",
                               value_target="Enabled",
                               key=['Status', 'State'],
                               minutes=timeout)
        return status
