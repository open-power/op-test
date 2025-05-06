#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestUtil.py $
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

import sys
import os
import datetime
import time
import pwd
import string
import subprocess
import random
import re
import telnetlib
import socket
import select
import time
import pty
import pexpect
import subprocess
import requests
import traceback
from requests.adapters import HTTPAdapter
from http.client import HTTPConnection
import urllib3  # setUpChildLogger enables integrated logging with op-test
import json
import tempfile

from common.OpTestSSH import OpTestSSH

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestSysinfo():

    def __init__(self):
        pass

    def get_OSconfig(self, pty, prompt):
        # Collect config related data from the OS
        try:
            print("########### OS Sysinfo ########")
            pty.sendline("date")  
            pty.sendline("hostname")
            pty.sendline("cat /etc/os-release | grep PRETTY_NAME ")
            pty.sendline("uname -r")
            pty.sendline("lsmcode")
            pty.sendline("lparstat -i ")
            pty.sendline("cat /proc/cpuinfo")
            pty.sendline("lsmem | grep \"Memory block size\"")
        except CommandFailed as cf:
            raise cf

    def get_HMCconfig(self, pty, prompt):
        # Collect config data from HMC
        try:
            print("########### HMC Sysinfo ########")
            pty.sendline("date")
            pty.sendline("hostname")
            pty.sendline("lshmv -V")
        except CommandFailed as cf:
            raise cf
