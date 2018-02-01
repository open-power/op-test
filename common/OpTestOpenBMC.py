#!/usr/bin/python2
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
import json

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
from common import OPexpect
import OpTestSystem

class FailedCurlInvocation(Exception):
    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return "CURL invocation '%s' failed\nOutput:\n%s" % (self.command, self.output)


class ConsoleState():
    DISCONNECTED = 0
    CONNECTED = 1

def set_system_to_UNKNOWN(system):
    s = system.get_state()
    system.set_state(OpTestSystem.OpSystemState.UNKNOWN)
    return s

class HostConsole():
    def __init__(self, host, username, password, logfile=sys.stdout, port=22):
        self.state = ConsoleState.DISCONNECTED
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.logfile = logfile
        self.system = None

    def set_system(self, system):
        self.system = system

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
        solChild = OPexpect.spawn(cmd,logfile=self.logfile,
                                  failure_callback=set_system_to_UNKNOWN,
                                  failure_callback_data=self.system)
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
        rc = None
        output = None
        exitcode = None
        try:
            rc = console.expect(["\[console-pexpect\]#$"], timeout)
            output = console.before
            console.sendline("echo $?")
            console.expect("\n") # from us
            rc = console.expect(["\[console-pexpect\]#$"], timeout)
            exitcode = int(console.before)
        except pexpect.TIMEOUT as e:
            print e
            print "# TIMEOUT waiting for command to finish."
            print "# Attempting to control-c"
            try:
                console.sendcontrol('c')
                rc = console.expect(["\[console-pexpect\]#$"], 10)
                if rc == 0:
                    raise CommandFailed(command, "TIMEOUT", -1)
            except pexpect.TIMEOUT:
                print "# Timeout trying to kill timed-out command."
                print "# Failing current command and attempting to continue"
                self.terminate()
                raise CommandFailed("ssh -p 2222", "timeout", -1)
            raise e

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
        self.logresult = True

    def feed_data(self, dbus_object=None, action=None,
                  operation=None, command=None,
                  data=None, header=None, upload_file=None, remote_name=None):
        self.object = dbus_object
        self.action = action
        self.operation = operation # 'r-read, w-write, rw-read/write'
        self.command = command
        self.data = data
        self.header = self.custom_header(header)
        self.upload_file = upload_file
        self.remote_file = remote_name

    def binary_name(self):
        return self.binary

    # -H, --header LINE   Pass custom header LINE to server (H)'
    def custom_header(self, header=None):
        if not header:
            self.header = " \'Content-Type: application/json\' "
        else:
            self.header = header
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
        args = " -s"
        args += " %s " % self.get_cookies()
        args += " -k "
        # -J, --remote-header-name  Use the header-provided filename (H)
        #  -O, --remote-name   Write output to a file named as the remote file
        if self.remote_file:
            args += " -O -J "
        if self.header:
            args += " -H %s " % self.header
        if self.data:
            args += " -d %s " % self.http_post_data()
        if self.upload_file:
            args += " -T %s " % self.upload_file
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
    Get Current Host Power State:
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -X GET -d '{"data":
    []}' https://bmc/xyz/openbmc_project/state/host0/attr/CurrentHost
    '''
    def get_power_state(self):
        data = '\'{"data" : []}\''
        obj = '/xyz/openbmc_project/state/host0/attr/CurrentHostState'
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
    power soft server:
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data": "xyz.openbmc_project.State.Chassis.Transition.Off"}'
    https://bmc/xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition
    '''
    def power_soft(self):
        data = '\'{"data" : \"xyz.openbmc_project.State.Chassis.Transition.Off\"}\''
        obj = "xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    power off server:
    https://bmc/xyz/openbmc_project/state/chassis0/attr/RequestedHostTransition
    https://bmc/xyz/openbmc_project/state/host0/attr/RequestedHostTransition
    '''
    def power_off(self):
        data = '\'{\"data\" : \"xyz.openbmc_project.State.Chassis.Transition.Off\"}\''
        obj = "/xyz/openbmc_project/state/chassis0/attr/RequestedPowerTransition"
        try:
            self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
            self.curl.run()
        except FailedCurlInvocation as f:
            print "# Ignoring failure powering off chassis, trying powering off host"
            pass
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
        sels = []
        data = self.list_sel()
        data = json.loads(data)
        for k in data['data']:
            print repr(k)
            m = re.match(r"/xyz/openbmc_project/logging/entry/(\d{1,})$", k)
            if m:
                sels.append(m.group(1))
        print repr(sels)
        return sels

    def clear_sel_by_id(self):
        print "Clearing SEL entries by id"
        list = self.get_sel_ids()
        for id in list:
            data = '\'{"data" : []}\''
            obj = "/xyz/openbmc_project/logging/entry/%s/action/Delete" % id
            self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", data=data)
            self.curl.run()
    def verify_clear_sel(self):
        print "Check if SEL has really zero entries or not"
        list = []
        list = self.get_sel_ids()
        if not list:
            return True
        return False

    '''
    clear SEL : Clearing complete SEL
    curl -b cjar -k -H "Content-Type: application/json" -X POST \
    -d '{"data" : []}' \
    https://bmc/xyz/openbmc_project/logging/action/DeleteAll
    '''
    def clear_sel(self):
        data = '\'{"data" : []}\''
        obj = "/xyz/openbmc_project/logging/action/DeleteAll"
        try:
            self.curl.feed_data(dbus_object=obj, operation='r', command="POST", data=data)
            self.curl.run()
        except FailedCurlInvocation as f:
            print "# Ignoring failure clearing SELs, not all OpenBMC builds support this yet"
            pass

    '''
    get current boot device info
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -d '{"data" : []}' -X GET
    https://bmc/xyz/openbmc_project/control/host0/boot/attr/bootmode
    '''
    def get_current_bootdev(self):
        data = '\'{"data" : []}\''
        obj = "/xyz/openbmc_project/control/host0/boot/attr/bootmode"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET", data=data)
        self.curl.run()

    '''
    set boot device to setup
    curl -c cjar -b cjar -k -H "Content-Type: application/json"
    -d "{"data": \"xyz.openbmc_project.Control.Boot.Mode.Modes.Setup\"}" -X PUT
    https://bmc/xyz/openbmc_project/control/host0/boot/attr/bootmode
    '''
    def set_bootdev_to_setup(self):
        data = '\'{"data": \"xyz.openbmc_project.Control.Boot.Mode.Modes.Setup\"}\''
        obj = "/xyz/openbmc_project/control/host0/boot/attr/bootmode"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    set boot device to regular/default
    curl -c cjar -b cjar -k -H "Content-Type: application/json"
    -d "{"data": \"xyz.openbmc_project.Control.Boot.Mode.Modes.Regular\"}" -X PUT
    https://bmc/xyz/openbmc_project/control/host0/boot/attr/bootmode
    '''
    def set_bootdev_to_none(self):
        data = '\'{"data": \"xyz.openbmc_project.Control.Boot.Mode.Modes.Regular\"}\''
        obj = "/xyz/openbmc_project/control/host0/boot/attr/bootmode"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    '''
    get boot progress info
    curl -c cjar -b cjar -k -H "Content-Type: application/json" -d
    '{"data": [ ] }' -X GET
    https://bmc//xyz/openbmc_project/state/host0/attr/BootProgress
    '''
    def get_boot_progress(self):
        data = '\'{"data" : []}\''
        obj = "/xyz/openbmc_project/state/host0/attr/BootProgress"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET", data=data)
        self.curl.run()

    '''
    Wait for OpenBMC Host state
    This is only on more modern OpenBMC builds.
    If unsupported, return None and fall back to old method.
    We can't just continue to use the old method until it disappears as
    it is actively broken (always returns Off).
    NOTE: The whole BMC:CHassis:Host mapping is completely undocumented and
    undiscoverable. At some point, this may change from 0,0,0 and one of each and
    everything is going to be a steaming pile of fail.
    '''
    def wait_for_host_state(self, target_state, host=0, timeout=10):
        data = '\'{"data" : []}\''
        obj = "/xyz/openbmc_project/state/host%d" % host
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        timeout = time.time() + 60*timeout
        target_state = "xyz.openbmc_project.State.Host.HostState.%s" % target_state
        while True:
            output = self.curl.run()
            result = json.loads(output)
            print repr(result)
            if result.get('data') is None or result.get('data').get('CurrentHostState') is None:
                return None
            state = result['data']['CurrentHostState']
            print "System state: %s (target %s)" % (state, target_state)
            if state == target_state:
                break
            if time.time() > timeout:
                raise OpTestError("Timeout waiting for host state to become %s" % target_state)
            time.sleep(5)
        return True

    def wait_for_standby(self, timeout=10):
        r = self.wait_for_host_state("Off", timeout=timeout)
        if r is None:
            print "Falling back to old BootProgress"
            return old_wait_for_standby(timeout)

    def wait_for_runtime(self, timeout=10):
        r = self.wait_for_host_state("Running", timeout=timeout)
        if r is None:
            print "Falling back to old BootProgress"
            return old_wait_for_standby(timeout)

    '''
    Boot progress
    curl   -b cjar   -k  -H  'Content-Type: application/json'   -d '{"data": [ ] }'
    -X GET https://bmc//xyz/openbmc_project/state/host0/attr/BootProgress
    '''
    def old_wait_for_runtime(self, timeout=10):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/sensors/host/BootProgress"
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        timeout = time.time() + 60*timeout
        while True:
            output = self.curl.run()
            result = json.loads(output)
            print repr(result)
            state = result['data']['value']
            print "System state: %s" % state
            if state == 'FW Progress, Starting OS':
                print "System FW booted to runtime: IPL finished"
                break
            if time.time() > timeout:
                l_msg = "IPL timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)
        return True

    def old_wait_for_standby(self, timeout=10):
        data = '\'{"data" : []}\''
        obj = "/org/openbmc/sensors/host/BootProgress"
        self.curl.feed_data(dbus_object=obj, operation='r', command="GET", data=data)
        timeout = time.time() + 60*timeout
        while True:
            output = self.curl.run()
            result = json.loads(output)
            print repr(result)
            state = result['data']['value']
            print "System state: %s" % state
            if state == 'Off':
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
        # Wait for BMC to go down.
        self.util.ping_fail_check(self.hostname)
        # Wait for BMC to ping back.
        self.util.PingFunc(self.hostname, BMC_CONST.PING_RETRY_FOR_STABILITY)
        # Wait for BMC ready state.
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
            except FailedCurlInvocation as cf:
                output = cf.output
            if '"data": "xyz.openbmc_project.State.BMC.BMCState.Ready"' in output:
                print "BMC is UP & Ready"
                break
            if time.time() > timeout:
                l_msg = "BMC Ready timeout"
                print l_msg
                raise OpTestError(l_msg)
            time.sleep(5)
        return True

    def get_list_of_image_ids(self):
        obj = "/xyz/openbmc_project/software/"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET")
        output = self.curl.run()
        r = json.loads(output)
        print repr(r)
        ids = []
        for k in r['data']:
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
                i = self.image_data(m.group(1))
                if i['data'].get('Purpose') is not None:
                    ids.append(m.group(1))

        print "List of images id's: %s" % ids
        return ids

    def image_data(self, id):
        obj = "/xyz/openbmc_project/software/%s" % id
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET")
        return json.loads(self.curl.run())

    """
    Upload a image
    curl   -b cjar  -c cjar   -k  -H  'Content-Type: application/octet-stream'   -T witherspoon.pnor.squashfs.tar
    -X POST https://bmc//upload/image
    """
    def upload_image(self, image):
        header = " \'Content-Type: application/octet-stream\' "
        obj = "/upload/image"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", header=header, upload_file=image)
        self.curl.run()

    # priority 0 -primary (Boot side of the image)
    def get_image_priority(self, id):
        output = self.image_data(id)
        print repr(output)
        return output['data']['Priority']

    def image_ready_for_activation(self, id, timeout=10):
        timeout = time.time() + 60*timeout
        while True:
            output = self.image_data(id)
            print repr(output)
            if output['data']['Activation'] == "xyz.openbmc_project.Software.Activation.Activations.Ready":
                print "Image upload is successful & Ready for activation"
                break
            if time.time() > timeout:
                raise OpTestError("Image is not ready for activation/Timeout happened")
            time.sleep(5)
        return True

    """
    Activate a image
    curl -b cjar -k -H "Content-Type: application/json" -X PUT
    -d '{"data":"xyz.openbmc_project.Software.Activation.RequestedActivations.Active"}'
    https://bmc/xyz/openbmc_project/software/<image id>/attr/RequestedActivation
    """
    def activate_image(self, id):
        obj = "/xyz/openbmc_project/software/%s/attr/RequestedActivation" % id
        data =  '\'{\"data\":\"xyz.openbmc_project.Software.Activation.RequestedActivations.Active\"}\''
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        self.curl.run()

    """
    Delete a image
    curl -b cjar -k -H "Content-Type: application/json" -X DELETE

    https://bmc/xyz/openbmc_project/software/<image id>/attr/RequestedActivation
    """
    def delete_image(self, id):
        obj = "/xyz/openbmc_project/software/%s" % id
        self.curl.feed_data(dbus_object=obj, operation='rw', command="DELETE")
        self.curl.run()

    def wait_for_image_active_complete(self, id, timeout=10):
        timeout = time.time() + 60*timeout
        while True:
            output = self.image_data(id)
            if output['data']['Activation'] == 'xyz.openbmc_project.Software.Activation.Activations.Activating':
                print "Image activation is in progress"
            if output['data']['Activation'] == 'xyz.openbmc_project.Software.Activation.Activations.Active':
                print "Image activated successfully, Good to go for power on...."
                break
            if output['data']['Activation'] == 'xyz.openbmc_project.Software.Activation.Activations.Failed':
                print "Image activation failed. Good luck."
                return False
            if time.time() > timeout:
                raise OpTestError("Image is failed to activate/Timeout happened")
            time.sleep(5)
        return True

    def host_image_ids(self):
        l = self.get_list_of_image_ids()
        for id in l[:]:
            i = self.image_data(id)
            # Here, we assume that if we don't have 'Purpose' it's something special
            # like the 'active' or (new) 'functional'.
            # Adriana has promised me that this is safe.
            print repr(i)
            if i['data'].get('Purpose') != 'xyz.openbmc_project.Software.Version.VersionPurpose.Host':
                l.remove(id)
        print "Host Image IDS: %s" % repr(l)
        return l

    def bmc_image_ids(self):
        l = self.get_list_of_image_ids()
        for id in l[:]:
            i = self.image_data(id)
            # Here, we assume that if we don't have 'Purpose' it's something special
            # like the 'active' or (new) 'functional'.
            # Adriana has promised me that this is safe.
            print repr(i)
            if i['data'].get('Purpose') != 'xyz.openbmc_project.Software.Version.VersionPurpose.BMC':
                l.remove(id)
        print "BMC Image IDS: %s" % repr(l)
        return l

    """
    Listing available Dumps:
    $ curl -c cjar -b cjar -k https://$BMC_IP/xyz/openbmc_project/dump/list
    """
    def list_available_dumps(self):
        obj = "/xyz/openbmc_project/dump/list"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET")
        return self.curl.run()


    def get_dump_ids(self):
        dump_ids = []
        output = self.list_available_dumps()
        data = json.loads(output)
        print repr(data)
        for k in data['data']:
            print repr(k)
            m = re.match(r"/xyz/openbmc_project/dump/entry/(\d{1,})$", k)
            if m:
                dump_ids.append(m.group(1))
        print repr(dump_ids)
        return dump_ids

    """
    Down Load Dump:
    $ curl -O -J -c cjar -b cjar -k -X GET https://$BMC_IP/download/dump/$ID
    """
    def download_dump(self, dump_id):
        obj = "/download/dump/%s" % dump_id
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET", remote_name=True)
        self.curl.run()

    """
    Delete dump.
    $ curl -c cjar -b cjar -k -H "Content-Type: application/json" -d "{\"data\": []}"
      -X POST  https://$BMC_IP/xyz/openbmc_project/dump/entry/3/action/Delete
    """
    def delete_dump(self, dump_id):
        obj = "/xyz/openbmc_project/dump/entry/%s/action/Delete" % dump_id
        data = '\'{"data" : []}\''
        self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", data=data)
        self.curl.run()

    def delete_all_dumps(self):
        ids = self.get_dump_ids()
        for id in ids:
            self.delete_dump(id)

    """
    Create new Dump:
    $ curl -c cjar -b cjar -k -H "Content-Type: application/json" -d "{\"data\": []}"
       -X POST  https://$BMC_IP/xyz/openbmc_project/dump/action/CreateDump
    """
    def create_new_dump(self):
        obj = "/xyz/openbmc_project/dump/action/CreateDump"
        data = '\'{"data" : []}\''
        self.curl.feed_data(dbus_object=obj, operation='rw', command="POST", data=data)
        dump_capture = False
        try:
            output = self.curl.run()
            dump_capture = True
        except FailedCurlInvocation as cf:
            output = cf.output
        data = json.loads(output)
        if dump_capture:
            print "OpenBMC Dump capture was successful"
            return data['data']
        print repr(data['data'].get('exception'))
        if data['data']['exception'] == "DBusException('Dump not captured due to a cap.',)":
            print "Dumps are exceeded in the system, trying to delete existing ones"
            self.delete_all_dumps()
            output = self.curl.run()
            data = json.loads(output)
            return data['data']

    def wait_for_dump_finish(self, dump_id):
        for i in range(20):
            ids = self.get_dump_ids()
            if str(dump_id) in ids:
                print "Dump %s is ready to download/offload" % str(dump_id)
                return True
            time.sleep(5)
        else:
            return False

    def software_enumerate(self):
        obj = "/xyz/openbmc_project/software"
        self.curl.feed_data(dbus_object=obj, operation='rw', command="GET")
        return json.loads(self.curl.run())

    # Returns True  - if field mode enabled.
    #         False - if it is disabled.
    def has_field_mode_set(self):
        data = self.software_enumerate()
        print repr(data)
        val = data['data'].get('FieldModeEnabled')
        if int(val) == 1:
            return True
        return False

    """
    Set field mode : 1 - enables it
    curl -b cjar -k -H 'Content-Type: application/json' -X PUT -d '{"data":0}'
    https://bmcip/xyz/openbmc_project/software/attr/FieldModeEnabled
    """
    def set_field_mode(self, mode):
        obj = "/xyz/openbmc_project/software/attr/FieldModeEnabled"
        data = '\'{"data" : %s}\'' % int(mode)
        self.curl.feed_data(dbus_object=obj, operation='rw', command="PUT", data=data)
        return json.loads(self.curl.run())


class OpTestOpenBMC():
    def __init__(self, ip=None, username=None, password=None, ipmi=None, rest_api=None, logfile=sys.stdout):
        self.hostname = ip
        self.username = username
        self.password = password
        self.ipmi = ipmi
        self.rest_api = rest_api
        self.has_vpnor = None
        self.logfile = logfile
        # We kind of hack our way into pxssh by setting original_prompt
        # to also be \n, which appears to fool it enough to allow us
        # continue.
        self.console = HostConsole(ip, username, password, port=2200, logfile=self.logfile)
        self.bmc = OpTestBMC(ip=self.hostname,
                            username=self.username,
                            password=self.password)

    def set_system(self, system):
        self.console.set_system(system)

    def has_new_pnor_code_update(self):
        if self.has_vpnor is not None:
            return self.has_vpnor
        list = self.rest_api.get_list_of_image_ids()
        for id in list:
            i = self.rest_api.image_data(id)
            if i['data'].get('Purpose') == 'xyz.openbmc_project.Software.Version.VersionPurpose.Host':
                print "Host image"
                self.has_vpnor = True
                return True
        print "# Checking for pflash os BMC to determine update method"
        self.has_vpnor = not self.bmc.validate_pflash_tool()
        return self.has_vpnor

    def reboot(self):
        self.bmc.reboot()
        # After a BMC reboot, wait for it to reach ready state
        self.rest_api.wait_for_bmc_runtime()

    def image_transfer(self, i_imageName):
        self.bmc.image_transfer(i_imageName)

    def pnor_img_flash_openbmc(self, pnor_name):
        self.bmc.pnor_img_flash_openbmc(pnor_name)

    def skiboot_img_flash_openbmc(self, lid_name):
        if not self.has_new_pnor_code_update():
            self.bmc.skiboot_img_flash_openbmc(lid_name)
        else:
            # don't ask. There appears to be a bug where we need to be 4k aligned.
            self.bmc.run_command("dd if=/dev/zero of=/dev/stdout bs=1M count=1 | tr '\\000' '\\377' > /tmp/ones")
            self.bmc.run_command("cat /tmp/%s /tmp/ones > /tmp/padded" % lid_name)
            self.bmc.run_command("dd if=/tmp/padded of=/usr/local/share/pnor/PAYLOAD bs=1M count=1")
            #self.bmc.run_command("mv /tmp/%s /usr/local/share/pnor/PAYLOAD" % lid_name, timeout=60)

    def skiroot_img_flash_openbmc(self, lid_name):
        if not self.has_new_pnor_code_update():
            self.bmc.skiroot_img_flash_openbmc(lid_name)
        else:
            # don't ask. There appears to be a bug where we need to be 4k aligned.
            self.bmc.run_command("dd if=/dev/zero of=/dev/stdout bs=16M count=1 | tr '\\000' '\\377' > /tmp/ones")
            self.bmc.run_command("cat /tmp/%s /tmp/ones > /tmp/padded" % lid_name)
            self.bmc.run_command("dd if=/tmp/padded of=/usr/local/share/pnor/BOOTKERNEL bs=16M count=1")
            #self.bmc.run_command("mv /tmp/%s /usr/local/share/pnor/BOOTKERNEL" % lid_name, timeout=60)

    def clear_field_mode(self):
        self.bmc.run_command("fw_setenv fieldmode")
        self.bmc.run_command("systemctl unmask usr-local.mount")
        self.reboot()

    def bmc_host(self):
        return self.hostname

    def get_ipmi(self):
        return self.ipmi

    def get_host_console(self):
        return self.console

    def get_rest_api(self):
        return self.rest_api

    def run_command(self, command, timeout=10):
        return self.bmc.run_command(command, timeout)

    def has_inband_bootdev(self):
        return False

    def has_os_boot_sensor(self):
        return False

    def has_host_status_sensor(self):
        return False

    def has_occ_active_sensor(self):
        return False
