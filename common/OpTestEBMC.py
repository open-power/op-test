#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2022
# [+] International Business Machines Corp.
#
#Author: Praveen K Pandey <praveen@linux.vnet.ibm.com>
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


import os
import time
import requests
import json
import sys

from .OpTestSSH import OpTestSSH
from .OpTestBMC import OpTestBMC
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
 
    def set_attribute_redfish(self, uri, attribute_name, attribute_value):
        """
        Changing any attribute value using Redfish API
        
        :param uri: redfish uri at which the attribute can be updated
        :param attribute_name: Should be same as attribute name in redfish
        :param attribute_value: Value want be be updated for attribute
        """
        auth_token = self.generate_ssl_auth_token(ip_add=self.conf.args.bmc_ip)
        content_type = "-H 'Content-Type: application/json'"
        rest_server = "https://{}{}".format(self.conf.args.bmc_ip, uri)
        attribute_param = '\'{"Attributes":{'+'{}:{}'.format(attribute_name, attribute_value)+'}}\''
        curl_command = "curl -k -H"+" 'X-Auth-Token: "+auth_token+"' "+content_type+f" -X PATCH {rest_server} "+f"-d {attribute_param}"
        log.info("Command to set attribut: "+curl_command)
        try:
            output = os.system(curl_command)
            return output
        except CommandFailed as cf:
            return cf.output

    def generate_ssl_auth_token(self, ip_add = None):
        """
        Generates ssl key then returns the ssl key
        """
        payload = {
            "username": self.conf.args.bmc_username,
            "password": self.conf.args.bmc_password
        }
        uri = f"https://{ip_add}/redfish/v1/SessionService/Sessions"
        creds = '{"UserName":\"'+ self.conf.args.bmc_username + '","Password":\"' + self.conf.args.bmc_password + '"}'
        file_name = "/tmp/headers-"+time.strftime("%Y%m%d%H%M%S")+".txt"
        sess_cmd = 'curl -k -H "Content-Type: application/json" -X POST -D '+file_name+" "+uri+' -d '+"\'"+creds+"\'"
        os.system(sess_cmd)
        auth_file = open(file_name)
        token = auth_file.read()
        token = [line for line in token.split("\n") if "X-Auth-Token" in line][0].split(":")[1].strip()
        if token:
            return token
        else:
            log.info("Token not found in response")
            return None

    def get_bios_attribute_value(self, bios_attribute=None, minutes=BMC_CONST.HTTP_RETRY):
        """
        Get BIOS current attribute value using redfish api
        """
        uri = "/redfish/v1/Systems/system/Bios"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get("Attributes").get(bios_attribute)

    def set_bios_attribute(self, bios_attribute=None, bios_attribute_val=None):
        '''
        Set BMC BIOS attribute to provided value
        '''
        uri = '/redfish/v1/Systems/system/Bios/Settings'
        return self.set_attribute_redfish(uri=uri,
                                          attribute_name='"'+bios_attribute+'"',
                                          attribute_value=bios_attribute_val)

    def configure_enlarged_io(self, iocapacity):
        """
        Calling set IO Enlarge capacity if provided value is not same as current value
        """
        cur_iocapacity = self.get_current_ioadapter_enlarged_capacity()
        log.info("Setting up ioenlarge capacity")
        log.info("Current ioenlarge capacity value:"+str(cur_iocapacity))
        if cur_iocapacity != iocapacity:
            self.set_ioenlarge_capacity(iocapacity)
        else:
            log.info("Provided IO Enlarge capacity value is same as current value, Exiting...")

    def get_current_ioadapter_enlarged_capacity(self):
        """
        Get ioadapter enlarged capcity value
        """
        log.debug("=====Get current IOAdapter Enlarge Capacity=====")
        return self.get_bios_attribute_value(
                bios_attribute="hb_ioadapter_enlarged_capacity_current"
            )

    def set_ioenlarge_capacity(self, iocapacity):
        """
        Set ioadapter enlarged capcity value
        """
        log.debug("=====Set IOAdapter Enlarge Capacity=====")
        self.set_bios_attribute(
                        bios_attribute="hb_ioadapter_enlarged_capacity",
                        bios_attribute_val=iocapacity
                )



class OpTestEBMC():

    def __init__(self, ip=None, username=None, password=None, ipmi=None,
                 rest_api=None, hmc=None, logfile=sys.stdout,
                 check_ssh_keys=False, known_hosts_file=None):
        self.hostname = ip
        self.username = username
        self.password = password
        self.ipmi = ipmi
        self.hmc = hmc
        self.rest_api = rest_api
        self.has_vpnor = None
        self.logfile = logfile

        self.console = OpTestSSH(ip, username, password, port=2200,
                                 logfile=self.logfile, check_ssh_keys=check_ssh_keys,
                                 known_hosts_file=known_hosts_file)

        self.bmc = OpTestBMC(ip=self.hostname,
                             username=self.username,
                             password=self.password,
                             logfile=self.logfile,
                             check_ssh_keys=check_ssh_keys,
                             known_hosts_file=known_hosts_file)

    def set_system(self, system):
        self.console.set_system(system)
        self.bmc.set_system(system)

    def bmc_host(self):
        return self.hostname

    def get_ipmi(self):
        return self.ipmi

    def get_hmc(self):
        return self.hmc

    def get_host_console(self):
        if self.hmc:
            return self.hmc.get_host_console()
        else:
            return self.console

    def get_rest_api(self):
        return self.rest_api

    def run_command(self, command, timeout=10, retry=0):
        return self.bmc.run_command(command, timeout, retry)
