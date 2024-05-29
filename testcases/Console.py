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
#

'''
Console tests
-------------

A bunch of really simple console tests that have managed to break *every*
BMC implementation we've ever thrown it at. Since we're highly reliant
on the BMC providing a reliable host console, if these tests fail at all,
then we're likely going to get spurious failures elsewhere in the test suite.
'''

import unittest
import pexpect
import time

import OpTestConfiguration
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed
import common.OpTestMambo as OpTestMambo
import common.OpTestQemu as OpTestQemu

import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class Console():
    '''
    Run the full class of Console tests

    --run testcases.Console

    '''
    bs = 1024
    count = 8

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_BMC = conf.bmc()
        self.cv_SYSTEM = conf.system()
        self.util = conf.util

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.cv_BMC.get_host_console()
        adjustment = 3  # mambo echo now disabled in initial setup
        bs = self.bs
        count = self.count
        self.assertTrue((bs * count) % 16 == 0,
                        "Bug in test writer. Must be multiple of 16 bytes: "
                        "bs {} count {} / 16 = {}".format(bs, count,
                                                          (bs * count) % 16))
        try:
            # timeout is longer to trace if the console *ever* comes back
            zeros = console.run_command(
                "dd if=/dev/zero bs={} count={}|hexdump -C -v".format(bs,
                                                                      count),
                timeout=240)
        except CommandFailed as cf:
            if cf.exitcode == 0:
                pass
            else:
                raise cf
        expected = adjustment + (count * bs) / 16
        if len(zeros) != expected:
            log.debug("bad len(zeros)={}".format(len(zeros)))
            log.debug("expected={}".format(expected))
            for i in range(len(zeros)):
                log.debug("bad line {}={}".format(i, zeros[i]))
        self.assertTrue(len(zeros) == expected,
                        "Unexpected length of zeros {} != {}, check the debug log for details"
                        .format(len(zeros), expected))

class Console8k(Console, unittest.TestCase):
    '''
    hexdump 8kb of zeros and check we get all the lines of hexdump output on
    the console.

    --run testcases.Console.Console8k

    '''
    bs = 1024
    count = 8

class Console16k(Console, unittest.TestCase):
    '''
    hexdump 16kb of zeros and check we get all the lines of hexdump output on
    the console.

    --run testcases.Console.Console16k

    '''
    bs = 1024
    count = 16

class Console32k(Console, unittest.TestCase):
    '''
    hexdump 32kb of zeros and check we get all the lines of hexdump output on
    the console. The idea is that console buffers on BMCs are likely to be less
    than 32kb, so we'll be able to catch any silent wrapping of it.

    --run testcases.Console.Console32k

    '''
    bs = 1024
    count = 32

class ControlC(unittest.TestCase):
    '''
    Start a process that does a bunch of console output, and then try and
    'control-c' it to stop the process and get a prompt back.

    --run testcases.Console.ControlC

    '''
    CONTROL = 'c'
    COUNTER = 5
    bad_connections = 0

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_BMC = conf.bmc()
        self.cv_SYSTEM = conf.system()
        self.util = conf.util
        self.prompt = self.util.build_prompt()

    def cleanup(self):
        pass

    def runTest(self):
        self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
        console = self.cv_BMC.get_host_console()
        if (isinstance(self.cv_BMC, OpTestMambo.OpTestMambo)):
            raise unittest.SkipTest("Mambo so skipping Control-C/Z tests")
        for i in range(1, self.COUNTER+1):
            # we run the date command here to smoke test that something
            # didn't mess up the run_command interface, this assures
            # us the ctrl-x tests are not leaving the environment tainted
            output = console.run_command_ignore_fail("date", timeout=10)
            if "TIMEOUT" in output:
                log.debug("Control-{} test encountered a problem with running a command, "
                          " this will be added to the threshold tolerances"
                          .format(self.CONTROL))
                self.bad_connections += 1
            # we need a new pty each time since we clobber it later
            raw_pty = console.get_console()
            # we use the sendline, not run_command to test out ctrl-c
            # run_command uses ctrl-c to recover, so that will not work here
            # if ctrl-c fails, we have to power off
            # log the timings of when the commands happen to see if any issues
            log.debug("Control-C/Z sendline find /")
            raw_pty.sendline("find /")
            # https://github.com/open-power/boston-openpower/issues/1413
            time.sleep(2)
            log.debug("Control-C/Z sendcontrol {}".format(self.CONTROL))
            raw_pty.sendcontrol(self.CONTROL)
            # control-z will stop the process, but it will later give pexpect.EOF
            # the timeout needs to be long enough so the pty spawn object has time
            # to figure out the sockets are dead, we've seen like 40-50 secs
            log.debug("Control-C/Z back from sendcontrol {}".format(self.CONTROL))
            # We're using an oversized timeout due to LTC Bug 186797 (OpenBMC)
            rc = raw_pty.expect([self.prompt, pexpect.TIMEOUT, pexpect.EOF], timeout=180)
            log.debug("Control-C/Z rc={}".format(rc))
            log.debug("Control-C/Z before={}".format(raw_pty.before))
            log.debug("Control-C/Z after={}".format(raw_pty.after))
            if rc == 1:
                log.warning("Unable to Control-{} the running command, "
                            "we were in loop {} of {}, we will have to power off to try to recover,"
                            " this will be added to the threshold tolerances"
                            .format(self.CONTROL, i, self.COUNTER))
                self.cv_SYSTEM.set_state(OpSystemState.UNKNOWN_BAD)
                # we have to power off in case this is the last test,
                # otherwise it leaves the system bad for the next test run
                self.cv_SYSTEM.goto_state(OpSystemState.OFF)
                self.cv_SYSTEM.goto_state(OpSystemState.PETITBOOT_SHELL)
                self.bad_connections += 1
            if rc == 2:
                log.debug("Control-{} caused an EOF running the command, this should fix itself"
                          .format(self.CONTROL))
            # we use info to output to the user watching
            log.info("Console Control-{} Completed LOOP={} Total will be={}, bad_connections={}"
                .format(self.CONTROL, i, self.COUNTER, self.bad_connections))
            # ctrl-c to the pty spawn object closes down the sockets
            # explicitly close the term object to allow the follow-on run_command's to succeed
            if not (isinstance(self.cv_BMC, OpTestQemu.OpTestQemu)):
                log.debug("Control-C/Z CLOSING console")
                console.close()
            if self.bad_connections > 3:
                self.fail("Control-{} tests, "
                          "we were in loop {} of {}, we reached the threshold of bad_connections={}"
                          .format(self.CONTROL, i, self.COUNTER, self.bad_connections))
            self.cleanup()

class ControlZ(ControlC):
    '''
    Run a console output heavy task, try to control-z it, then kill it,
    the try_recover logic in OpTestUtil should recover the prompt

    --run testcases.Console.ControlZ

    '''
    CONTROL = 'z'
    COUNTER = 5

    def cleanup(self):
        console = self.cv_BMC.get_host_console()
        # why this changed from earlier revisions
        # it seems that after the control z stops the process,
        # then when the kill command gets sent, but gets EOF before completion
        # we previously ignored the failure and then subsequently
        # got a new pty object and then we fg'd the still pending
        # stopped job, the one we just control z'd
        # on who knows what old pty object that died (this really messes with
        # pexpect, it even fg something else ? (spins and never advances),
        # could never kill op-test, would have to kill -9 op-test by PID
        # so catch the failed kill and try to recover
        #/proc/165/task/165/ns
        #/proc/165/task/165/ns/mnt
        #^Z[1]+  Stopped                    find /
        #[console-expect]#kill %1
        #Error sending SOL data: FAIL
        #SOL session closed by BMC
        #^M~.
        #~.[SOL Session operational.  Use ~? for help]
        #fg
        #find /
        #/proc/165/task/165/net
        #/proc/165/task/165/net/arp

        log.debug("Control-C/Z cleanup")
        try:
            console.run_command("kill %1")
            log.debug("Control-C/Z cleanup succeeded")
        except Exception as e:
            log.debug("Control-C/Z cleanup problem, some unexpected results may follow")
            log.debug("Control-C/Z cleanup Exception={}".format(e))
            time.sleep(2)
            # try one last time
            try:
                console.run_command("kill %1")
                log.debug("Control-C/Z Exception kill succeeded")
            except Exception as e:
                log.debug("Control-C/Z 2nd Exception={}".format(e))
                console.run_command_ignore_fail("kill %1")
                log.debug("Control-C/Z 2 Exception kill succeeded")
        # TODO: It seems busybox jobs does not properly clear the killed job
        # from the jobs output, but yet the process is gone and fg shows
        # it is terminated
        kill_output = console.run_command_ignore_fail("jobs -p")
        log.debug("Control-C/Z jobs kill_output={}".format(kill_output))
        # make sure they are gone
        for i in range(len(kill_output)):
            console.run_command_ignore_fail("kill -9 {}".format(kill_output[i]))
        fg_output = console.run_command_ignore_fail("fg")
        log.debug("Control-C/Z jobs fg_output={}".format(fg_output))

def suite():
    s = unittest.TestSuite()
    s.addTest(Console32k())
    s.addTest(ControlZ())
    s.addTest(ControlC())
    return s
