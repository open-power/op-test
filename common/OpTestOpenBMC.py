#!/usr/bin/python
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
import pexpect
import subprocess

try:
    import pxssh
except ImportError:
    from pexpect import pxssh
from OpTestIPMI import OpTestIPMI
from OpTestUtil import OpTestUtil
from OpTestBMC import OpTestBMC
from Exceptions import CommandFailed
from common.OpTestError import OpTestError
from OpTestConstants import OpTestConstants as BMC_CONST

class FailedCurlInvocation(Exception):
    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return "CURL invocation '%s' failed\nOutput:\n%s" % (self.command, self.output)


class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

class HostConsole():
    def __init__(self, host, username, password, port=22):
        self.state = ConsoleState.DISCONNECTED
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def terminate(self):
        if self.state == ConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

    def close(self):
        if self.state == ConsoleState.DISCONNECTED:
            return
        try:
            self.sol.send("\r")
            self.sol.send('~.')
            self.sol.expect(pexpect.EOF)
            self.sol.close()
        except pexpect.ExceptionPexpect:
            raise "HostConsole: failed to close OpenBMC host console"
        self.sol.terminate()
        self.state = ConsoleState.DISCONNECTED

    def connect(self):
        if self.state == ConsoleState.CONNECTED:
            self.sol.terminate()
            self.state = ConsoleState.DISCONNECTED

        print "#OpenBMC Console CONNECT"

        cmd = ("sshpass -p %s " % (self.password)
               + " ssh -q"
               + " -o'RSAAuthentication=no' -o 'PubkeyAuthentication=no'"
               + " -o 'StrictHostKeyChecking=no'"
               + " -o 'UserKnownHostsFile=/dev/null' "
               + " -p %s" % str(self.port)
               + " -l %s %s" % (self.username, self.host)
           )
        print cmd
        solChild = pexpect.spawn(cmd,logfile=sys.stdout)
        self.state = ConsoleState.CONNECTED
        self.sol = solChild
        return solChild

    def get_console(self):
        if self.state == ConsoleState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.sol.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(1)
            self.connect()
            count += 1
            if count > 120:
                raise "IPMI: not able to get sol console"

        return self.sol

    def run_command(self, command, timeout=60):
        console = self.get_console()
        console.sendline(command)
        console.expect("\n") # from us
        rc = console.expect(["\[console-pexpect\]#$",pexpect.TIMEOUT], timeout)
        output = console.before

        console.sendline("echo $?")
        console.expect("\n") # from us
        rc = console.expect(["\[console-pexpect\]#$",pexpect.TIMEOUT], timeout)
        exitcode = int(console.before)

        if rc == 0:
            res = output
            res = res.splitlines()
            if exitcode != 0:
                raise CommandFailed(command, res, exitcode)
            return res
        else:
            res = console.before
            res = res.split(command)
            return res[-1].splitlines()

    # This command just runs and returns the ouput & ignores the failure
    # A straight copy of what's in OpTestIPMI
    def run_command_ignore_fail(self, command, timeout=60):
        try:
            output = self.run_command(command, timeout)
        except CommandFailed as cf:
            output = cf.output
        return output

class CurlTool():
    def __init__(self, binary="curl",
                 ip=None, username=None, password=None):
        self.ip = ip
        self.username = username
        self.password = password
        self.binary = binary
        self.logresult = False

    def feed_data(self, dbus_object=None, action=None,
                  operation=None, command=None,
                  data=None, header=None):
        self.object = dbus_object
        self.action = action
        self.operation = operation # 'r-read, w-write, rw-read/write'
        self.command = command
        self.data = data
        self.header = self.custom_header()

    def binary_name(self):
        return self.binary

    # -H, --header LINE   Pass custom header LINE to server (H)'
    def custom_header(self):
        self.header = " \'Content-Type: application/json\' "
        return self.header

    def http_post_data(self):
        '''
        Example data formats
        data = '\'{"data": [ "root", "0penBmc" ] }\''
        data = '\'{"data" : []}\''
        '''
        return self.data

    # -b, --cookie STRING/FILE  Read cookies from STRING/FILE (H)
    def read_cookie(self):
        self.cookies = ' -b cjar '
        return self.cookies

    # -c, --cookie-jar FILE  Write cookies to FILE after operation (H)
    def write_cookie(self):
        self.cookies = ' -c cjar '
        return self.cookies

    def get_cookies(self):
        if self.operation == 'r':
            return self.read_cookie()
        elif self.operation == 'w':
            return self.write_cookie()
        elif self.operation == 'rw':
            cookies = self.read_cookie() + self.write_cookie()
            return cookies
        else:
            raise Exception("Invalid operation")

    def request_command(self):
        if not self.command:
            # default is GET command
            self.command = "GET"
        return self.command

    def dbus_interface(self):
        s = 'https://%s/' % self.ip
        if self.object:
            s += '/%s' % (self.object)
        if self.action:
            s += '/%s' % (self.action)
        return s

    def arguments(self):
        args = " "
        args += " %s " % self.get_cookies()
        args += " -k "
        if self.header:
            args += " -H %s " % self.custom_header()
        if self.data:
            args += " -d %s " % self.http_post_data()
        if self.command:
            args += " -X %s " % self.request_command()
        args += self.dbus_interface()
        return args

    def run(self, background=False, cmdprefix=None):
        if cmdprefix:
            cmd = cmdprefix + self.binary + self.arguments() + cmd
        else:
            cmd = self.binary + self.arguments()
        print cmd
        if background:
            try:
                child = subprocess.Popen(cmd, shell=True)
            except:
                l_msg = "Curl Command Failed"
                print l_msg
                raise OpTestError(l_msg)
            return child
        else:
            # TODO - need python 2.7
            # output = check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            try:
                cmd = subprocess.Popen(cmd, stderr=subprocess.STDOUT,
                                       stdout=subprocess.PIPE, shell=True)
            except Exception as e:
                l_msg = "Curl Command Failed"
                print l_msg
                print str(e)
                raise OpTestError(l_msg)
            output = cmd.communicate()[0]
            if self.logresult:
                print output
            if '"status": "error"' in output:
                print output
                raise FailedCurlInvocation(cmd, output)
            return output

    def log_result(self):
        self.logresult = True

class HostManagement():
    def __init__(self, ip=None, username=None, password=None):
        self.hostname = ip
        self.username = username
        self.password = password
        self.curl = CurlTool(ip=ip,
                             username=username,
                             password=password)
        self.util = OpTestUtil()
        self.login()

    '''
    curl -c cjar -k -X POST -H "Content-Type: application/json" \
    -d '{"data": [ "root", "0penBmc" ] }' https://bmc/login
    '''
    def login(self):
        data = '\'{"data": [ "root", "0penBmc" ] }\''
        self.curl.feed_data(dbus_object="/login", operation='w', command="POST", data=data)
        self.curl.run()

    '''
    Logout:
    curl -c cjar -b cjar -k -X POST -H "Content-Type: application/json" \
    -d '{"data": [ ] }' \
    https://bmc/logout
    '''
    def logout(self):
        data = '\'{"data" : []}\''
        self.curl.feed_data(dbus_object="/logout", operation='rw', command="POST", data=data)
        self.curl.run()

    '''
    Inventory enumerate:
    /xyz/openbmc_project/inventory
    curl -b cjar -k https://bmc/xyz/openbmc_project/inventory/enumerate
    '''
    def get_inventory(self):
        self.curl.feed_data(dbus_object="/xyz/openbmc_project/inventory/enumerate", operation="r")
        self.curl.run()

    def sensors(self):
        self.curl.feed_data(dbus_object="/xyz/openbmc_project/sensors/enumerate", operation="r")
        self.curl.run()

    '''
    Get Chassis Power State:
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -X GET -d '{"data":
    []}' https://bmc/xyz/openbmc_project/state/chassis0/attr/CurrentPowerState
    '''
    def get_power_state(self):
        data = '\'{"data" : []}\''
        obj = '/xyz/openbmc_project/state/chassis0/attr/CurrentPowerState'
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET", data=data)
        self.curl.run()

    '''
    Get Host State:
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -X GET -d '{"data":
    []}' https://bmc/xyz/openbmc_project/state/host0/attr/CurrentHostState
    '''
    def get_host_state(self):
        data = '\'{"data" : []}\''
        obj = '/xyz/openbmc_project/state/host0/attr/CurrentHostState'
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET", data=data)
        self.curl.run()

    '''
    Reboot server gracefully:
    curl -c cjar b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data": "xyz.openbmc_project.State.Host.Transition.Reboot"}'
    https://bmc/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
    '''
    def soft_reboot(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.Host.Transition.Reboot\"}\''
        obj = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    Reboot server Immediately:
    curl -c cjar b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data": "xyz.openbmc_project.State.Host.Transition.Reboot"}'
    https://bmc/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
    '''
    def hard_reboot(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.Host.Transition.Reboot\"}\''
        obj = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    power soft server: Not yet implemented (TODO)
    curl -c cjar b cjar -k -H "Content-Type: application/json" -X POST -d '{"data":
    []}' https://bmc/org/openbmc/control/chassis0/action/softPowerOff
    '''
    def power_soft(self):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/control/chassis0/action/softPowerOff"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", data=data)
        self.curl.run()

    '''
    power off server:
    curl -c cjar b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data": "xyz.openbmc_project.State.Host.Transition.Off"}'
    https://bmc/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
    '''
    def power_off(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.Host.Transition.Off\"}\''
        obj = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    power on server:
    curl -c cjar b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data": "xyz.openbmc_project.State.Host.Transition.On"}'
    https://bmc/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
    '''
    def power_on(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.Host.Transition.On\"}\''
        obj = "/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    List SEL
    curl -b cjar -k -H "Content-Type: application/json" -X GET \
    -d '{"data" : []}' \
    https://bmc/xyz/openbmc_project/logging/enumerate
    '''
    def list_sel(self):
        print "List of SEL entries"
        data = '\'{"data" : []}\''
        obj = "/xyz/openbmc_project/logging/enumerate"
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        return self.curl.run()

    def get_sel_ids(self):
        list = []
        data = self.list_sel()
        list = re.findall(r"/xyz/openbmc_project/logging/entry/(\d{1,})", str(data))
        if list:
            print "SEL entries list by ID: %s" % list
        return list

    def clear_sel_by_id(self):
        print "Clearing SEL entries by id"
        list = self.get_sel_ids()
        for id in list:
            data = '\'{"data" : []}\''
            obj = "/xyz/openbmc_project/logging/entry/%s/action/Delete" % id
            self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", data=data)
            self.curl.run()

    '''
    clear SEL : Clearing complete SEL is not yet implemented (TODO)
    curl -b cjar -k -H "Content-Type: application/json" -X POST \
    -d '{"data" : []}' \
    https://bmc/org/openbmc/records/events/action/clear
    '''
    def clear_sel(self):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/records/events/action/clear"
        try:
            self.curl.feed_data(dbus_object=obj, operation='r', command="POST", data=data)
            self.curl.run()
        except FailedCurlInvocation as f:
            print "# Ignoring failure clearing SELs, not all OpenBMC builds support this yet"
            pass

    '''
    set boot device to setup
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -d "{\"data\": \"Setup\"}" -X PUT
    https://bmc/org/openbmc/settings/host0/attr/boot_flags
    '''
    def set_bootdev_to_setup(self):
        data = '\'{"data": \"Setup\"}\''
        obj = "/org/openbmc/settings/host0/attr/boot_flags"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    set boot device to default
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -d "{\"data\": \"Default\"}" -X PUT
    https://bmc/org/openbmc/settings/host0/attr/boot_flags
    '''
    def set_bootdev_to_none(self):
        data = '\'{\"data\": \"Default\"}\''
        obj = "/org/openbmc/settings/host0/attr/boot_flags"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()


    '''
    Boot progress
    curl   -b cjar   -k  -H  'Content-Type: application/json'   -d '{"data": [ ] }'
    -X GET https://bmc//org/openbmc/sensors/host/BootProgress
    '''
    def wait_for_runtime(self, timeout=10):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/sensors/host/BootProgress"
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        timeout = time.time() + 60*timeout
        while True:
            output = self.curl.run()
            obj = re.search('"value": "(.*?)"', output)
            if obj:
                print "System state: %s" % obj.group(1)
            if "FW Progress, Starting OS" in output:
                print "System FW booted to runtime: IPL finished"
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)
        return True

    def wait_for_standby(self, timeout=10):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/sensors/host/BootProgress"
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        timeout = time.time() + 60*timeout
        while True:
            output = self.curl.run()
            obj = re.search('"value": "(.*?)"', output)
            if obj:
                print "System state: %s" % obj.group(1)
            if '"value": "Off"' in output:
                print "System reached standby state"
                break
            if time.time() > timeout:
                l_msg = "Standby timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)
        return True

    '''
    BMC reset
    curl -c cjar -b cjar -k -H "Content-Type: application/json"
    -d "{\"data\" : \"xyz.openbmc_project.State.BMC.Transition.Reboot\"}" -X PUT
    https://bmc/xyz/openbmc_project/state/bmc0/attr/RequestedBMCTransition
    '''
    def bmc_reset(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.BMC.Transition.Reboot\"}\''
        obj = "/xyz/openbmc_project/state/bmc0/attr/RequestedBMCTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()
        time.sleep(10)
        self.util.PingFunc(self.hostname, BMC_CONST.PING_RETRY_FOR_STABILITY)
        time.sleep(5) # Need some stablity here
        self.login()
        self.wait_for_bmc_runtime()

    def get_bmc_state(self):
        obj = "/xyz/openbmc_project/state/bmc0/attr/CurrentBMCState"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET")
        return self.curl.run()

    def wait_for_bmc_runtime(self, timeout=10):
        timeout = time.time() + 60*timeout
        output = ""
        while True:
            if '"description": "Login required"' in output:
                self.login()
            try:
                output = self.get_bmc_state()
            except:
                pass
            if '"data": "xyz.openbmc_project.State.BMC.BMCState.Ready"' in output:
                print "BMC is UP & Ready"
                break
            if time.time() > timeout:
                l_msg = "BMC Ready timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)
        return True

class OpTestOpenBMC():
    def __init__(self, ip=None, username=None, password=None, ipmi=None, rest_api=None):
        self.hostname = ip
        self.username = username
        self.password = password
        self.ipmi = ipmi
        self.rest_api = rest_api
        # We kind of hack our way into pxssh by setting original_prompt
        # to also be \n, which appears to fool it enough to allow us
        # continue.
        self.console = HostConsole(ip, username, password, port=2200)
        self.bmc = OpTestBMC(ip=self.hostname,
                            username=self.username,
                            password=self.password)


    def reboot(self):
        self.bmc.reboot()
        # After a BMC reboot REST API needs login again
        self.rest_api.login()

    def image_transfer(self, i_imageName):
        self.bmc.image_transfer(i_imageName)

    def pnor_img_flash_openbmc(self, pnor_name):
        self.bmc.pnor_img_flash_openbmc(pnor_name)

    def skiboot_img_flash_openbmc(self, lid_name):
        self.bmc.skiboot_img_flash_openbmc(lid_name)

    def skiroot_img_flash_openbmc(self, lid_name):
        self.bmc.skiroot_img_flash_openbmc(lid_name)

    def bmc_host(self):
        return self.hostname

    def get_ipmi(self):
        return self.ipmi

    def get_host_console(self):
        return self.console

    def get_rest_api(self):
        return self.rest_api
