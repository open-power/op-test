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

import re
import sys
import time
import datetime
import pexpect
import subprocess
import json
import requests
import cgi
import os

from .OpTestSSH import OpTestSSH
from .OpTestBMC import OpTestBMC
from .Exceptions import HTTPCheck
from .Exceptions import CommandFailed
from .OpTestConstants import OpTestConstants as BMC_CONST
from . import OpTestSystem

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class HostManagement():
    '''
    HostManagement Class
    OpenBMC methods to manage the Host
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

    def get_inventory(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Inventory Enumerate
        GET
        https://bmcip/xyz/openbmc_project/inventory/enumerate
        '''
        uri = "/xyz/openbmc_project/inventory/enumerate"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('data')

    def sensors(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Sensor Enumerate
        GET
        https://bmcip/xyz/openbmc_project/sensors/enumerate
        '''
        uri = "/xyz/openbmc_project/sensors/enumerate"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('data')

    def get_power_state(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Current Host Power State
        GET
        https://bmcip/xyz/openbmc_project/state/host0/attr/CurrentHost
        '''
        uri = '/xyz/openbmc_project/state/host0/attr/CurrentHostState'
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('data')

    def get_host_state(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Host State
        GET
        https://bmcip/xyz/openbmc_project/state/host0/attr/CurrentHostState
        '''
        uri = '/xyz/openbmc_project/state/host0/attr/CurrentHostState'
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('data')

    def soft_reboot(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Reboot Server Gracefully
        PUT
        https://bmcip/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
        "data": "xyz.openbmc_project.State.Host.Transition.Reboot"
        '''
        uri = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        payload = {"data": "xyz.openbmc_project.State.Host.Transition.Reboot"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def hard_reboot(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Reboot Server Immediately
        PUT
        https://bmcip/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
        "data": "xyz.openbmc_project.State.Host.Transition.Reboot"
        '''
        uri = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        payload = {"data": "xyz.openbmc_project.State.Host.Transition.Reboot"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def power_soft(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Power Soft Server
        PUT
        https://bmcip/xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition
        "data": "xyz.openbmc_project.State.Chassis.Transition.Off"
        '''
        uri = "xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition"
        payload = {"data": "xyz.openbmc_project.State.Chassis.Transition.Off"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def power_off(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Power Off Server
        PUT
        https://bmcip/xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition
        "data": "xyz.openbmc_project.State.Chassis.Transition.Off"
        '''
        uri = "/xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition"
        payload = {"data": "xyz.openbmc_project.State.Chassis.Transition.Off"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def power_on(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Power On Server
        PUT
        https://bmcip/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
        "data": "xyz.openbmc_project.State.Host.Transition.On"
        '''
        uri = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        payload = {"data": "xyz.openbmc_project.State.Host.Transition.On"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def list_sel(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        List SEL
        GET
        https://bmcip/xyz/openbmc_project/logging/enumerate
        "data" : []
        '''
        log.debug("List of SEL entries")
        payload = {"data": []}
        uri = "/xyz/openbmc_project/logging/enumerate"
        r = self.conf.util_bmc_server.get(
            uri=uri, json=payload, minutes=minutes)
        return r.json()

    def pull_ids(self, sels=None):
        '''
        Pull SEL IDs
        '''
        id_list = []
        sel_dict = {}
        for key in sels:
            m = re.match(r"/xyz/openbmc_project/logging/entry/(\d{1,})$", key)
            if m:
                id_list.append(str(sels.get(key).get('Id')))
                sel_dict[str(sels.get(key).get('Id'))] = key
        id_list.sort()
        # sample id_list ['81', '82', '83', '84']
        return id_list, sel_dict

    def get_sel_ids(self, dump=False, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Build a sorted id_list from the SELs and also
        build a list of dictionary items containing the
        SEL and ESEL information

        :param dump: Set to True if a printed output is desired.
        :type dump: Boolean
        '''
        sels = []
        dict_list = []
        json_data = self.list_sel(minutes=minutes)
        log.debug("json_data={}".format(json_data))
        id_list, sel_dict = self.pull_ids(sels=json_data['data'])

        # sample sel_dict.get(j)=/xyz/openbmc_project/logging/entry/78
        for j in id_list:
            dict_item = {}
            dict_item['Id'] = str(json_data['data'][sel_dict.get(j)].get('Id'))
            dict_item['Timestamp'] = datetime.datetime.fromtimestamp(int(str(
                json_data['data'][sel_dict.get(j)].get('Timestamp')))/1000).strftime("%Y-%m-%d %H:%M:%S")
            dict_item['Message'] = json_data['data'][sel_dict.get(j)].get(
                'Message')
            dict_item['Description'] = json_data['data'][sel_dict.get(j)].get(
                'Description')
            dict_item['Severity'] = json_data['data'][sel_dict.get(j)].get(
                'Severity').split('.')[-1]
            dict_item['Resolved'] = json_data['data'][sel_dict.get(j)].get(
                'Resolved')
            dict_item['EventID'] = json_data['data'][sel_dict.get(j)].get(
                'EventID')
            add_data = json_data['data'][sel_dict.get(j)]['AdditionalData']
            for i in range(len(add_data)):
                if ("ESEL" in add_data[i]):
                    dict_item['esel'] = add_data[i].strip().split('=')[
                        1].replace(" ", "")
                if ("PROCEDURE" in add_data[i]):
                    dict_item['Procedure'] = str(add_data[i].split('=')[1])
            dict_list.append(dict_item)

        # we leave this to print to stdout to allow piping to appropriate logfile or console
        # TODO: When PR #361 merges collapse this and convert using OpTestUtil methods
        if dump:
            print(
                "\n----------------------------------------------------------------------")
            print("SELs")
            print(
                "----------------------------------------------------------------------")
            if len(id_list) == 0:
                print("SEL has no entries")
            for k in dict_list:
                print(("Id          : {}".format(k.get('Id'))))
                print(("Message     : {}".format(k.get('Message'))))
                print(("Description : {}".format(k.get('Description'))))
                print(("Timestamp   : {}".format(k.get('Timestamp'))))
                print(("Severity    : {}".format(k.get('Severity'))))
                print(("Resolved    : {}".format(k.get('Resolved'))))
                if k.get('EventID') is not None:
                    print(("EventID     : {}".format(k.get('EventID'))))
                if k.get('Procedure') is not None:
                    print(("Procedure   : {}".format(k.get('Procedure'))))
                if k.get('esel') is not None:
                    print(("ESEL        : characters={}\n".format(
                        len(k.get('esel')))))
                    print(
                        "Ruler        : 0123456789012345678901234567890123456789012345678901234567890123")
                    print(
                        "-------------------------------------------------------------------------------")
                    for j in range(0, len(k.get('esel')), 64):
                        print(("{:06d}-{:06d}: {}".format(j,
                                                          j+63, k.get('esel')[j:j+64])))
                else:
                    print("ESEL        : None")
                print("\n")
            print(
                "----------------------------------------------------------------------")
        # sample id_list ['81', '82', '83', '84']
        log.debug("id_list={}".format(id_list))
        log.debug("dict_list={}".format(dict_list))
        return id_list, dict_list

    def convert_esels_to_list(self, id_list=None, dict_list=None):
        esel_list = []
        esel_list.append("\n----------------------------------------------------------------------")
        esel_list.append("SELs")
        esel_list.append("----------------------------------------------------------------------")
        if len(id_list) == 0:
            esel_list.append("SEL has no entries")
        for k in dict_list:
            esel_list.append("Id          : {}".format(k.get('Id')))
            esel_list.append("Message     : {}".format(k.get('Message')))
            esel_list.append("Description : {}".format(k.get('Description')))
            esel_list.append("Timestamp   : {}".format(k.get('Timestamp')))
            esel_list.append("Severity    : {}".format(k.get('Severity')))
            esel_list.append("Resolved    : {}".format(k.get('Resolved')))
            if k.get('EventID') is not None:
                esel_list.append("EventID     : {}".format(k.get('EventID')))
            if k.get('Procedure') is not None:
                esel_list.append("Procedure   : {}".format(k.get('Procedure')))
            if k.get('esel') is not None:
                esel_list.append("ESEL        : characters={}\n".format(len(k.get('esel'))))
                esel_list.append("Ruler        : 0123456789012345678901234567890123456789012345678901234567890123")
                esel_list.append("-------------------------------------------------------------------------------")
                for j in range(0, len(k.get('esel')), 64):
                    esel_list.append("{:06d}-{:06d}: {}".format(j, j+63, k.get('esel')[j:j+64]))
            else:
                esel_list.append("ESEL        : None")
            esel_list.append("\n")
        esel_list.append("----------------------------------------------------------------------")
        return esel_list

    def clear_sel_by_id(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Clear SEL by ID
        POST
        https://bmcip/xyz/openbmc_project/logging/entry/<id>/action/Delete
        "data" : []
        '''
        log.debug("Clearing SEL entries by id")
        list, dict_list = self.get_sel_ids(minutes=minutes)
        log.debug("list={}".format(list))
        log.debug("dict_list={}".format(dict_list))
        for id in list:
            uri = "/xyz/openbmc_project/logging/entry/{}/action/Delete".format(
                id)
            payload = {"data": []}
            r = self.conf.util_bmc_server.post(
                uri=uri, json=payload, minutes=minutes)

    def verify_clear_sel(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Verify SEL is Cleared
        '''
        log.debug("Check if SEL really has zero entries")
        list = []
        list, dict_list = self.get_sel_ids(minutes=minutes)
        log.debug("list={}".format(list))
        log.debug("dict_list={}".format(dict_list))
        if not list:
            return True
        return False

    def clear_sel(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Clear ALL SELs
        POST
        https://bmcip/xyz/openbmc_project/logging/action/DeleteAll
        "data" : []
        '''
        log.debug("Clearing ALL SELs DeleteAll")
        uri = "/xyz/openbmc_project/logging/action/DeleteAll"
        payload = {"data": []}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)

    def get_current_bootdev(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Current Boot Device Info
        GET
        https://bmcip/xyz/openbmc_project/control/host0/boot/one_time/

        GET
        https://bmcip/xyz/openbmc_project/control/host0/boot
        '''
        uri = "/xyz/openbmc_project/control/host0/boot/one_time"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        json_data = r.json().get('data')
        if (json_data.get('Enabled') == 0):
            uri = "/xyz/openbmc_project/control/host0/boot"
            r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
            json_data = r.json().get('data')
        bootmode = ""
        if "Setup" in json_data.get('BootMode'):
            bootmode = "Setup"
        elif "Regular" in json_data.get('BootMode'):
            bootmode = "Regular"
        return bootmode

    def set_bootdev_to_setup(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Temporarily set boot device to setup (should clear itself once reaches runtime)
        PUT
        https://bmcip/xyz/openbmc_project/control/host0/boot/one_time/attr/BootMode
        "data": "xyz.openbmc_project.Control.Boot.Mode.Modes.Setup"

        https://bmcip/xyz/openbmc_project/control/host0/boot/one_time/attr/Enabled
        "data": 1
        '''
        uri = "/xyz/openbmc_project/control/host0/boot/one_time/attr/BootMode"
        payload = {"data": "xyz.openbmc_project.Control.Boot.Mode.Modes.Setup"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

        uri = "/xyz/openbmc_project/control/host0/boot/one_time/attr/Enabled"
        payload = {"data": 1}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def set_bootdev_to_none(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Set boot device to regular/default (clear any overrides)
        PUT
        https://bmcip/xyz/openbmc_project/control/host0/boot/attr/BootMode
        "data": "xyz.openbmc_project.Control.Boot.Mode.Modes.Regular"

        https://bmcip/xyz/openbmc_project/control/host0/boot/one_time/attr/Enabled
        "data": 0
        '''
        uri = "/xyz/openbmc_project/control/host0/boot/attr/BootMode"
        payload = {"data": "xyz.openbmc_project.Control.Boot.Mode.Modes.Regular"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

        uri = "/xyz/openbmc_project/control/host0/boot/one_time/attr/Enabled"
        payload = {"data": 0}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def get_boot_progress(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Boot Progress Info
        GET
        https://bmcip//xyz/openbmc_project/state/host0/attr/BootProgress
        '''
        uri = "/xyz/openbmc_project/state/host0/attr/BootProgress"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r.json().get('data')

    def wait_for_host_state(self, target_state, host=0, minutes=10):
        '''
        Wait for OpenBMC Host state
        GET
        https://bmcip//xyz/openbmc_project/state/host0
        "data" : []
        '''
        status = self.wait_bmc(token="/xyz/openbmc_project/state/host{}".format(host),
                               key="CurrentHostState",
                               value_target="xyz.openbmc_project.State.Host.HostState.{}".format(
                                   target_state),
                               minutes=minutes)
        return status

    def wait_for_standby(self, timeout=10):
        '''
        Wait for Standby
        '''
        r = self.wait_for_host_state("Off", minutes=timeout)

    def wait_for_runtime(self, timeout=10):
        '''
        Wait for Runtime
        '''
        r = self.wait_for_host_state("Running", minutes=timeout)

    def bmc_reset(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        BMC reset
        PUT
        https://bmcip/xyz/openbmc_project/state/bmc0/attr/RequestedBMCTransition
        "data" : "xyz.openbmc_project.State.BMC.Transition.Reboot"
        '''
        uri = "/xyz/openbmc_project/state/bmc0/attr/RequestedBMCTransition"
        payload = {"data": "xyz.openbmc_project.State.BMC.Transition.Reboot"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)
        # Wait for BMC to go down.
        self.util.ping_fail_check(self.hostname)
        # Wait for BMC to ping back.
        self.util.PingFunc(
            self.hostname, totalSleepTime=BMC_CONST.PING_RETRY_POWERCYCLE)
        # Wait for BMC ready state.
        self.wait_for_bmc_runtime()

    def get_bmc_state(self):
        '''
        Get BMC State
        '''
        # caller drives retry
        uri = "/xyz/openbmc_project/state/bmc0/attr/CurrentBMCState"
        r = self.conf.util_bmc_server.get(uri=uri)
        if r.status_code != requests.codes.ok:
            problem = "[{}] Description={}".format(r.json().get(
                'message'), "".join(r.json().get('data').get('description')))
            raise HTTPCheck(
                message="HTTP problem getting CurrentBMCState {}".format(problem))
        return r.json().get('data')

    def wait_bmc(self, key=None, value_target=None, token=None, minutes=10):
        '''
        Wait on BMC
        Given a token, target, key wait for a match
        '''
        # handles data as a dictionary or string
        timeout = time.time() + 60*minutes
        while True:
            r = self.conf.util_bmc_server.get(uri=token, minutes=minutes)
            if type(r.json().get('data')) == type(dict()):
                if key is None:
                    for key, value in r.json().get('data'):
                        if r.json().get('data').get(key) == value_target:
                            break
                else:
                    if r.json().get('data').get(key) == value_target:
                        break
            else:
                if value_target in r.json().get('data'):
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
        status = self.wait_bmc(token="/xyz/openbmc_project/state/bmc0/attr/CurrentBMCState",
                               value_target="xyz.openbmc_project.State.BMC.BMCState.Ready",
                               minutes=timeout)
        return status

    def get_list_of_image_ids(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get list of image IDs
        GET
        https://bmcip/xyz/openbmc_project/software
        '''
        uri = "/xyz/openbmc_project/software/"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        log.debug("Image IDs={}".format(r.json()))
        ids = []
        for k in r.json().get('data'):
            log.debug("Image Data Info k={}".format(k))
            m = re.match(r'/xyz/openbmc_project/software/(.*)', k)
            # According to the OpenBMC docs, Image ID can be
            # Implementation defined, and thus, the word 'active'
            # would be a valid ID.
            # Except that it isn't. The documentation is lies.
            # It seems that 'active' is special.
            # There is no documentation as to what other
            # strings are special, or could become special.
            # So, HACK HACK HACK around it. :(
            # https://github.com/openbmc/phosphor-dbus-interfaces/tree/55d03ca/xyz/openbmc_project/Software#image-identifier
            # This is getting insane, it's not just 'active'
            # It's 'functional' as well. Or some other things.
            # So, we assume that if we don't have 'Purpose' it's something special
            # like the 'active' or (new) 'functional'.
            # Adriana has promised me that this is safe into the future.
            if m:
                log.debug("Image Data Info ID={}: {}".format(m.group(1), k))
                i = self.image_data(m.group(1))
                if i['data'].get('Purpose') is not None:
                    ids.append(m.group(1))

        log.debug("List of images id's: {}".format(ids))
        return ids

    def image_data(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Image Info By ID
        GET
        https://bmcip/xyz/openbmc_project/software/id
        '''
        uri = "/xyz/openbmc_project/software/{}".format(id)
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        log.debug("Image ID={} Data={}".format(id, r.json()))
        return r.json()

    def upload_image(self, image, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Upload an image, OpenBMC imposes validation on files uploaded
        POST
        https://bmcip/upload/image
        "file" : file-like-object
        '''
        with open(image, 'rb') as fileload:
            uri = "/upload/image"
            octet_hdr = {'Content-Type': 'application/octet-stream'}
            r = self.conf.util_bmc_server.post(uri=uri,
                                               headers=octet_hdr,
                                               data=fileload)
            if r.status_code != 200:
                print((r.headers))
                print((r.text))
                print(r)

    def get_image_priority(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Image Priority - 0=primary, boot side of the image
        '''
        json_data = self.image_data(id, minutes=minutes)
        log.debug("Image Data: {}".format(json_data))
        # we use the strings below for easy grepping of debug logs
        log.debug("Image Data Info ID: {}".format(id))
        log.debug("Image Data Info Priority: {}".format(json_data.get('data').get('Priority')))
        log.debug("Image Data Info Purpose: {}".format(json_data.get('data').get('Purpose')))
        log.debug("Image Data Info Version: {}".format(json_data.get('data').get('Version')))
        return json_data.get('data').get('Priority')

    def set_image_priority(self, id, level, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Set Image Priority
        PUT
        https://bmcip/xyz/openbmc_project/software/<id>/attr/Priority
        "data" : 0
        '''
        # xyz.openbmc_project.Software.RedundancyPriority Priority y 0
        uri = "/xyz/openbmc_project/software/{}/attr/Priority".format(id)
        payload = {"data" : int(level)}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def image_ready_for_activation(self, id, timeout=10):
        '''
        Image Activation Ready
        IS THIS USED ?  CAN IT BE REMOVED ?
        '''
        timeout = time.time() + 60*timeout
        while True:
            json_data = self.image_data(id, minutes=BMC_CONST.HTTP_RETRY)
            log.debug("Image JSON : {}".format(json_data))
            if json_data.get('data').get('Activation') \
                    == "xyz.openbmc_project.Software.Activation.Activations.Ready":
                log.debug("Image upload is successful & Ready for activation")
                break
            if time.time() > timeout:
                raise HTTPCheck(
                    message="Image is not ready for activation/Timeout happened")
            time.sleep(5)
        return True

    def activate_image(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Activate An Image
        PUT
        https://bmcip/xyz/openbmc_project/software/<image id>/attr/RequestedActivation
        "data": "xyz.openbmc_project.Software.Activation.RequestedActivations.Active"
        '''
        uri = "/xyz/openbmc_project/software/{}/attr/RequestedActivation".format(
            id)
        payload = {
            "data": "xyz.openbmc_project.Software.Activation.RequestedActivations.Active"}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def delete_image(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Delete An Image
        POST
        https://bmcip/xyz/openbmc_project/software/<id>/action/delete
        "data" : []
        '''
        try:
            # First, we try the "new" method, as of at least ibm-v2.0-0-r26.1-0-gfb7714a
            uri = "/xyz/openbmc_project/software/{}/action/delete".format(id)
            payload = {"data": []}
            r = self.conf.util_bmc_server.post(
                uri=uri, json=payload, minutes=minutes)
        except Exception as e:
            # Try falling back to the old method (everything prior? who knows)
            uri = "/xyz/openbmc_project/software/{}".format(id)
            payload = {"data": []}
            r = self.conf.util_bmc_server.delete(
                uri=uri, json=payload, minutes=minutes)

    def wait_for_image_active_complete(self, id, timeout=10):
        '''
        Wait For Image Active Complete
        '''
        timeout = time.time() + 60*timeout
        while True:
            json_data = self.image_data(id, minutes=BMC_CONST.HTTP_RETRY)
            if json_data.get('data').get('Activation') \
                    == "xyz.openbmc_project.Software.Activation.Activations.Activating":
                log.info("Image activation is in progress")
            if json_data.get('data').get('Activation') \
                    == "xyz.openbmc_project.Software.Activation.Activations.Active":
                log.info(
                    "Image activated successfully, Good to go for power on....")
                break
            if json_data.get('data').get('Activation') \
                    == "xyz.openbmc_project.Software.Activation.Activations.Failed":
                log.error("Image activation failed. Try --run testcases.testRestAPI.HostOff.test_field_mode_enable_disable, which leaves field mode disabled.")
                log.warning("Bug reported SW461922 : OP930:FVT: Software Field mode disable operation does not throw error or warning, future this will not work")
                log.warning("You need to factory reset the BMC which requires re-setting BMC IP's (BMC serial connection needed due to loss of networking")
                log.warning("Alternate methods are via BMC busctl commands")
                return False
            if time.time() > timeout:
                raise HTTPCheck(
                    message="Image is failed to activate/Timeout happened")
            time.sleep(5)
        return True

    def host_image_ids(self):
        '''
        Get List of Host Image IDs
        '''
        return self.image_ids(purpose='xyz.openbmc_project.Software.Version.VersionPurpose.Host')

    def bmc_image_ids(self):
        '''
        Get List of BMC Image IDs
        '''
        return self.image_ids(purpose='xyz.openbmc_project.Software.Version.VersionPurpose.BMC')

    def image_ids(self, purpose=None, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get List of Image IDs
        '''
        l = self.get_list_of_image_ids(minutes=minutes)
        for id in l[:]:
            i = self.image_data(id, minutes=minutes)
            # Here, we assume that if we don't have 'Purpose' it's something special
            # like the 'active' or (new) 'functional'.
            # Adriana has promised me that this is safe.
            log.debug("Image Data Info ID: {}".format(i))
            if i['data'].get('Purpose') != purpose:
                log.debug("Removing Image ID: {} "
                          "Purpose={} does not match purpose={}"
                          .format(id, i.get('data').get('Purpose'), purpose))
                l.remove(id)
        log.debug("ALL Image IDs: {} purpose={}".format(l, purpose))
        return l

    def list_available_dumps(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Listing available Dumps:
        GET
        https://bmcip/xyz/openbmc_project/dump/list
        '''
        uri = "/xyz/openbmc_project/dump/list"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r

    def get_dump_ids(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get Dump IDs
        '''
        dump_ids = []
        r = self.list_available_dumps(minutes=BMC_CONST.HTTP_RETRY)
        log.debug("Dump IDs: {}".format(r.json()))
        for k in r.json().get('data'):
            log.debug("k={}".format(k))
            m = re.match(r"/xyz/openbmc_project/dump/entry/(\d{1,})$", k)
            if m:
                dump_ids.append(m.group(1))
        log.debug("Dump IDs: {}".format(dump_ids))
        return dump_ids

    def download_dump(self, dump_id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Download Dump
        GET
        https://bmcip/download/dump/<id>
        '''
        uri = "/download/dump/{}".format(dump_id)
        r = self.conf.util_bmc_server.get(
            uri=uri, stream=True, minutes=minutes)
        value, params = cgi.parse_header(r.headers.get('Content-Disposition'))
        with open(os.path.join(self.conf.logdir, params.get('filename')), 'wb') as f:
            f.write(r.content)

    def delete_dump(self, dump_id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Delete dump
        POST
        https://bmcip/xyz/openbmc_project/dump/entry/<dump_id>/action/Delete
        '''
        uri = "/xyz/openbmc_project/dump/entry/{}/action/Delete".format(
            dump_id)
        payload = {"data": []}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)
        return r

    def delete_all_dumps(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Delete all Dumps
        '''
        ids = self.get_dump_ids()
        for id in ids:
            self.delete_dump(id, minutes=BMC_CONST.HTTP_RETRY)
            log.debug("Deleting Dump ID={}".format(id))

    def create_new_dump(self, minutes=None):
        '''
        Create new Dump
        POST
        https://bmcip/xyz/openbmc_project/dump/action/CreateDump
        "data" : []
        '''
        uri = "/xyz/openbmc_project/dump/action/CreateDump"
        payload = {"data": []}
        try:
            r = self.conf.util_bmc_server.post(
                uri=uri, json=payload, minutes=minutes)
            log.info("OpenBMC Dump capture was successful")
            return r.json().get('data')
        except Exception as e:
            log.debug("Create Dump Exception={}".format(e))
            log.info(
                "Dumps are exceeded in the system, trying to delete existing ones")
            self.delete_all_dumps()
            r = self.conf.util_bmc_server.post(
                uri=uri, json=payload, minutes=minutes)
            log.info("RETRY ATTEMPT OpenBMC Dump capture was successful")
            return r.json().get('data')

    def wait_for_dump_finish(self, dump_id, counter=30):
        '''
        Wait for Dump to Finish
        '''
        for i in range(counter):
            ids = self.get_dump_ids()
            if str(dump_id) in ids:
                log.debug(
                    "Dump ID={} is ready to download/offload".format(dump_id))
                return True
            time.sleep(5)
        else:
            return False

    def software_enumerate(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Software Enumerate
        GET
        https://bmcip/xyz/openbmc_project/software
        '''
        uri = "/xyz/openbmc_project/software"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        return r

    def has_field_mode_set(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Field Mode Enabled : 0=disabled 1=enabled
        '''
        r = self.software_enumerate(minutes=minutes)
        try:
            if int(r.json().get('data').get('FieldModeEnabled')) == 1:
                log.debug("has_field_mode_set=1")
                return True
            else:
                log.debug("has_field_mode_set NOT True")
        except Exception as e:
            log.debug(
                "Unable to get FieldModeEnabled so returning False, Exception={}".format(e))
        return False

    def set_field_mode(self, mode, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Set field mode : 0=disable 1=enable
        PUT
        https://bmcip/xyz/openbmc_project/software/attr/FieldModeEnabled
        "data": 0
        '''
        uri = "/xyz/openbmc_project/software/attr/FieldModeEnabled"
        payload = {"data": int(mode)}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)
        log.debug("set_field_mode={}".format(r))

    def validate_functional_bootside(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Functional Boot Side Validation for both BMC and PNOR
        GET
        https://bmcip/xyz/openbmc_project/software/functional
        {
            "data": {
            "endpoints": [
            "/xyz/openbmc_project/software/061c4bdb",
            "/xyz/openbmc_project/software/608e9ebe"
            ]
        }
        '''
        uri = "/xyz/openbmc_project/software/functional"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        log.debug("Functional Boot Side Validation: r.text={}".format(r.text))
        if id in r.text:
            return True
        return False

    def is_image_already_active(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Check if Image is Active
        '''
        json_data = self.image_data(id, minutes=minutes)
        if json_data.get('data').get('Activation') \
                == "xyz.openbmc_project.Software.Activation.Activations.Active":
            return True
        return False

    def get_occ_ids(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        GET
        https://bmcip/org/open_power/control/enumerate
        '''
        uri = "/org/open_power/control/enumerate"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        occ_ids = []
        for k in r.json().get('data'):
            log.debug("k={}".format(k))
            m = re.match(r"/org/open_power/control/occ(\d{1,})$", k)
            if m:
                occ_ids.append(m.group(1))
        log.debug("OCC IDs: {}".format(occ_ids))
        return occ_ids

    def is_occ_active(self, id, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Get state of OCC's
        GET
        https://bmcip/org/open_power/control/occ0
        '''
        uri = "/org/open_power/control/occ{}".format(id)
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        if r.json().get('data').get('OccActive') == 1:
            log.debug("# OCC{} is active".format(id))
            return True
        log.debug("# OCC{} is not active".format(id))
        return False

    def enable_power_cap(self, enable, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Enable Power Cap : 0=disabled by default 1=enabled
        PUT
        https://bmcip/xyz/openbmc_project/control/host0/power_cap/attr/PowerCapEnable
        "data" : 0
        '''
        uri = "/xyz/openbmc_project/control/host0/power_cap/attr/PowerCapEnable"
        payload = {"data": int(enable)}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def power_cap_enable(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Enables the Power Cap
        '''
        self.enable_power_cap("1")

    def power_cap_disable(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Disables the Power Cap
        '''
        self.enable_power_cap("0")

    def get_power_cap_settings(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        GET
        https://bmcip/xyz/openbmc_project/control/host0/power_cap
        '''
        uri = "/xyz/openbmc_project/control/host0/power_cap"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        PowerCapEnable = r.json().get('data').get('PowerCapEnable')
        PowerCap = r.json().get('data').get('PowerCap')
        return PowerCapEnable, PowerCap

    def clear_gard_records(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        POST
        https://bmcip/org/open_power/control/gard/action/Reset
        '''
        uri = "/org/open_power/control/gard/action/Reset"
        payload = {"data": []}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)

    def factory_reset_software(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        POST
        https://bmcip/xyz/openbmc_project/software/action/Reset
        "data": []"
        '''
        uri = "/xyz/openbmc_project/software/action/Reset"
        payload = {"data": []}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)

    def factory_reset_network(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        POST
        https://bmcip/xyz/openbmc_project/network/action/Reset
        "data": []"
        '''
        uri = "/xyz/openbmc_project/network/action/Reset"
        payload = {"data": []}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)

    def update_root_password(self, password, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Update Root Password
        POST
        https://bmcip/xyz/openbmc_project/user/root/action/SetPassword
        "data" : ["abc123"]
        '''
        uri = "/xyz/openbmc_project/user/root/action/SetPassword"
        payload = {"data": [str(password)]}
        r = self.conf.util_bmc_server.post(
            uri=uri, json=payload, minutes=minutes)

    def is_tpm_enabled(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        TPM Enablement Check 0=TPMEnable cleared 1=TPMEnable set
        GET
        https://bmcip/xyz/openbmc_project/control/host0/TPMEnable
        '''
        uri = "/xyz/openbmc_project/control/host0/TPMEnable"
        r = self.conf.util_bmc_server.get(uri=uri, minutes=minutes)
        if r.json().get('data').get('TPMEnable') == 1:
            log.debug("# TPMEnable is set")
            return True
        log.debug("# TPMEnable is cleared")
        return False

    def configure_tpm_enable(self, bit, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Configure TPM Enable - 0=disable 1=enable
        PUT
        https://bmcip/xyz/openbmc_project/control/host0/TPMEnable/attr/TPMEnable
        "data" : 1
        '''
        uri = "/xyz/openbmc_project/control/host0/TPMEnable/attr/TPMEnable"
        payload = {"data": int(bit)}
        r = self.conf.util_bmc_server.put(
            uri=uri, json=payload, minutes=minutes)

    def enable_tpm(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Enable TPM
        '''
        self.configure_tpm_enable(1)

    def disable_tpm(self, minutes=BMC_CONST.HTTP_RETRY):
        '''
        Disable TPM
        '''
        self.configure_tpm_enable(0)


class OpTestOpenBMC():
    def __init__(self, ip=None, username=None, password=None, ipmi=None,
                 rest_api=None, logfile=sys.stdout,
                 check_ssh_keys=False, known_hosts_file=None):
        self.hostname = ip
        self.username = username
        self.password = password
        self.ipmi = ipmi
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

    def query_vpnor(self, minutes=BMC_CONST.HTTP_RETRY):
        if self.has_vpnor is not None:
            return self.has_vpnor

        # As of June 2020, we came to the determination that:
        # * Both VPNOR and non-VPNOR OpenBMCs can answer with an inventory of Host
        #   images (using Redfish APIs)
        # * Both VPNOR and non-VPNOR OpenBMCs can have that above list empty
        # * So the only reliable way of checking for VPNOR capability is to check
        #   for 'pflash' presence in the BMC, since OpenBMC should be bundling it
        #   ONLY on systems that are NOT capable of VPNOR:

        self.has_vpnor = not self.bmc.validate_pflash_tool()

        log.debug("System is " + ("" if self.has_vpnor else "NOT") + " VPNOR-capable")
        return self.has_vpnor

    def reboot(self):
        self.bmc.reboot()
        # After a BMC reboot, wait for it to reach ready state
        self.rest_api.wait_for_bmc_runtime()

    def reboot_nowait(self):
        # Reboot BMC but do not wait for it to come back
        self.bmc.reboot_nowait()

    def image_transfer(self, i_imageName, copy_as=None):
        self.bmc.image_transfer(i_imageName, copy_as=copy_as)

    def pnor_img_flash_openbmc(self, pnor_name):
        self.bmc.pnor_img_flash_openbmc(pnor_name)

    def skiboot_img_flash_openbmc(self, lid_name):
        if not self.query_vpnor():
            log.debug("We do NOT have vpnor, so calling old pflash")
            self.bmc.skiboot_img_flash_openbmc(lid_name)
        else:
            # don't ask. There appears to be a bug where we need to be 4k aligned.
            self.bmc.run_command(
                "dd if=/dev/zero of=/dev/stdout bs=1M count=1 | tr '\\000' '\\377' > /tmp/ones")
            self.bmc.run_command(
                "cat /tmp/%s /tmp/ones > /tmp/padded" % lid_name)
            self.bmc.run_command(
                "dd if=/tmp/padded of=/usr/local/share/pnor/PAYLOAD bs=1M count=1")
            #self.bmc.run_command("mv /tmp/%s /usr/local/share/pnor/PAYLOAD" % lid_name, timeout=60)

    def skiroot_img_flash_openbmc(self, lid_name):
        if not self.query_vpnor():
            self.bmc.skiroot_img_flash_openbmc(lid_name)
        else:
            # don't ask. There appears to be a bug where we need to be 4k aligned.
            #self.bmc.run_command("dd if=/dev/zero of=/dev/stdout bs=16M count=1 | tr '\\000' '\\377' > /tmp/ones")
            #self.bmc.run_command("cat /tmp/%s /tmp/ones > /tmp/padded" % lid_name)
            try:
                # seems the success on following command gives echo $?=1
                #self.bmc.run_command("dd if=/tmp/padded of=/usr/local/share/pnor/BOOTKERNEL bs=16M count=1")
                self.bmc.run_command("rm -f /usr/local/share/pnor/BOOTKERNEL", timeout=60)
                self.bmc.run_command("ln -s /tmp/{} /usr/local/share/pnor/BOOTKERNEL".format(lid_name), timeout=60)
            except CommandFailed as e:
                log.warning("FLASHING CommandFailed, check that this is ok for your setup")

    def flash_part_openbmc(self, lid_name, part_name):
        if not self.query_vpnor():
            self.bmc.flash_part_openbmc(lid_name, part_name)
        else:
            self.bmc.run_command(
                "mv /tmp/%s /usr/local/share/pnor/%s" % (lid_name, part_name), timeout=60)

    def clear_field_mode(self):
        self.bmc.run_command("fw_setenv fieldmode")
        self.bmc.run_command("systemctl unmask usr-local.mount")
        log.info("clear_field_mode rebooting the BMC")
        self.reboot()

    def bmc_host(self):
        return self.hostname

    def get_ipmi(self):
        return self.ipmi

    def get_host_console(self):
        return self.console

    def get_rest_api(self):
        return self.rest_api

    def run_command(self, command, timeout=10, retry=0):
        return self.bmc.run_command(command, timeout, retry)

    def has_inband_bootdev(self):
        return False

    def has_os_boot_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False

    def has_ipmi_sel(self):
        return False

    def supports_ipmi_dcmi(self):
        return False
