#!/usr/bin/python
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

## @package OpTestASM
#  This class can contains common functions which are useful for 
#  FSP ASM Web page

import time
import subprocess
import os
import pexpect
import sys
import commands

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError

import cookielib
import urllib
import urllib2
import re
import ssl
# Work around issues with python < 2.7.9
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

class OpTestASM:

    def __init__(self, i_fspIP, i_fspUser, i_fspPasswd, i_ffdcDir=None):
        self.host_name = i_fspIP
        self.user_name = i_fspUser
        self.password = i_fspPasswd
        self.url = "https://%s/cgi-bin/cgi?" % self.host_name
        self.cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        opener.addheaders = [('User-agent', 'LTCTest')]
        urllib2.install_opener(opener)
        hrdwr = ''
        frms = {}
        self.setforms()
   
    def setforms(self):
        if "FW860" in self.ver(): 
            self.hrdwr='p8'    
            self.frms={'pwr':'59','dbg':'78','immpwroff':'32'}
        else: 
            self.hrdwr='p7'    
            self.frms={'pwr':'60','dbg':'79','immpwroff':'33'}


    def getcsrf(self, form):
        while True:
            try:
                myurl = urllib2.urlopen(self.url+form, timeout = 10)  
            except urllib2.URLError, e:
                time.sleep(2)
                continue
            break
        out=myurl.read()
        if 'CSRF_TOKEN' in out:
            return re.findall('CSRF_TOKEN.*value=\'(.*)\'',out)[0]
        else :
            return '0'

    def getpage(self, form):
        while True:
            try:
                myurl = urllib2.urlopen(self.url+form, timeout = 60)  
            except (urllib2.URLError,ssl.SSLError):
                time.sleep(2)
                continue
            break
        return myurl.read()
        #return myurl

    def submit(self,form, param):
        param['CSRF_TOKEN'] = self.getcsrf(form)
        data = urllib.urlencode(param)
        req = urllib2.Request(self.url+form, data)

        return urllib2.urlopen(req)
        #resp = urllib2.urlopen(req)
        #contents = resp.read()

    def login(self):
        if not len(self.cj) == 0:
            return True
        param = {'user':self.user_name,'password':self.password,'login':'Log in','lang':'0','CSRF_TOKEN':''}
        form = "form=2"
        out=self.submit(form, param)

        count = 0
        while count < 2:
            if not len(self.cj) == 0:
                break
            time.sleep(10)
            self.submit(form,param)
            msg = "Login Failed with user:%s and password:%s" % (self.user_name, self.password)
            print msg
            count += 1
        if count == 2:
            print msg
            return False
        return True


    def logout(self):
        param = {'submit':'Log out', 'CSRF_TOKEN':''}
        form = "form=1"
        self.submit(form, param)

    def ver(self):
        form = "form=1"
        return self.getpage(form)

    def execommand(self, cmd):
        param={'form':'16', 'exe':'Execute', 'CSRF_TOKEN':'', 'cmd':cmd}
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
        param={'form':'30', 'clear':"Clear all error/event log entries", 'CSRF_TOKEN':''}
        form = "form=30"
        self.submit(form, param)
        self.logout()

    def powerstat(self):
        form = "form=%s" % self.frms['pwr']
        return self.getpage(form)
