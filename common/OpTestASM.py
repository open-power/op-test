#!/usr/bin/env python3
# encoding=utf8
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestASM.py $
#
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
# IBM_PROLOG_END_TAG

'''
OpTestASM: Advanced System Management (FSP Web UI)
--------------------------------------------------

This class can contains common functions which are useful for
FSP ASM Web page. Some functionality is only accessible through
the FSP Web UI (such as progress codes), so we scrape it.
'''

import time
import subprocess
import os
import pexpect
import sys
import subprocess

from .OpTestConstants import OpTestConstants as BMC_CONST
from .OpTestError import OpTestError

import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
import re
import ssl


class OpTestASM:
    def __init__(self, i_fspIP, i_fspUser, i_fspPasswd):
        self.host_name = i_fspIP
        self.user_name = i_fspUser
        self.password = i_fspPasswd
        self.url = "https://%s/cgi-bin/cgi?" % self.host_name
        self.cj = http.cookiejar.CookieJar()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
        opener.addheaders = [('User-agent', 'LTCTest')]
        opener.add_handler(urllib.request.HTTPCookieProcessor(self.cj))
        urllib.request.install_opener(opener)
        self.setforms()

    def setforms(self):
        if "FW860" in self.ver():
            self.hrdwr = 'p8'
            self.frms = {'pwr':       '59',
                         'dbg':       '78',
                         'immpwroff': '32'}
        else:
            self.hrdwr = 'p7'
            self.frms = {'pwr':       '60',
                         'dbg':       '79',
                         'immpwroff': '33'}

    def getcsrf(self, form):
        while True:
            try:
                myurl = urllib.request.urlopen(self.url+form, timeout=10)
            except urllib.error.URLError:
                time.sleep(2)
                continue
            break
        out = myurl.read().decode("utf-8")
        if 'CSRF_TOKEN' in out:
            return re.findall('CSRF_TOKEN.*value=\'(.*)\'', out)[0]
        else:
            return '0'

    def getpage(self, form):
        myurl = urllib.request.urlopen(self.url+form, timeout=60)
        return myurl.read().decode("utf-8")

    def submit(self, form, param):
        param['CSRF_TOKEN'] = self.getcsrf(form)
        data = urllib.parse.urlencode(param).encode("utf-8")
        req = urllib.request.Request(self.url+form, data)

        return urllib.request.urlopen(req)

    def login(self):
        if not len(self.cj) == 0:
            return True
        param = {'user':      self.user_name,
                 'password':  self.password,
                 'login':     'Log in',
                 'lang':      '0',
                 'CSRF_TOKEN': ''}
        form = "form=2"
        resp = self.submit(form, param)

        count = 0
        while count < 2:
            if not len(self.cj) == 0:
                break

            # the login can quietly fail because the FSP has 'too many users' logged in,
            # even though it actually doesn't.  let's check to see if this is the case
            # by trying a request.
            if "Too many users" in self.getpage("form=2"):
                raise OpTestError("FSP reports 'Too many users', FSP needs power cycle")

            time.sleep(10)
            self.submit(form, param)
            msg = "Login failed with user:{0} and password:{1}".format(
                self.user_name, self.password)
            print(msg)
            count += 1
        if count == 2:
            print(msg)
            return False
        return True

    def logout(self):
        param = {'submit':     'Log out',
                 'CSRF_TOKEN': ''}
        form = "form=1"
        self.submit(form, param)

    def ver(self):
        form = "form=1"
        return self.getpage(form)

    def execommand(self, cmd):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form':       '16',
                 'exe':        'Execute',
                 'CSRF_TOKEN': '',
                 'cmd':        cmd}
        form = "form=16&frm=0"
        self.submit(form, param)

    def disablefirewall(self):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        self.execommand('iptables -F')
        self.logout()

    def clearlogs(self):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form':  '30',
                 'clear': "Clear all error/event log entries",
                 'CSRF_TOKEN': ''}
        form = "form=30"
        self.submit(form, param)
        self.logout()

    def powerstat(self):
        form = "form=%s" % self.frms['pwr']
        return self.getpage(form)

    def start_debugvtty_session(self, partitionId='0', sessionId='0',
                                sessionTimeout='600'):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form': '81',
                 'p': partitionId,
                 's': sessionId,
                 't': sessionTimeout,
                 'Save settings': 'Save settings',
                 'CSRF_TOKEN': ''}
        form = "form=81"
        self.submit(form, param)
        self.logout()

    def enable_err_injct_policy(self):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form':  '56',
                 'p':      '1',
                 'submit': 'Save settings',
                 'CSRF_TOKEN': ''}
        form = "form=56"
        self.submit(form, param)
        self.logout()

    def configure_hugepages(self, no_hp):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form':  '71',
                 'submit': 'Save settings',
                 'CSRF_TOKEN': '',
                 'smps_pg_cnt': no_hp}
        form = "form=71"
        self.submit(form, param)
        self.logout()

    def configure_enlarged_io(self, ioec1):
        if not self.login():
            raise OpTestError("Failed to login ASM page")
        param = {'form':  '47',
                 'submit': 'Save settings',
                 'CSRF_TOKEN': '',
                 'ioec_enable': 'on',
                 'ioec1': ioec1}
        form = "form=47"
        self.submit(form, param)
        self.logout()
