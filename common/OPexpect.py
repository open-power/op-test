#!/usr/bin/python2
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2017
# [+] International Business Machines Corp.
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

"""
The OPexpect module is a wrapper around the standard Python pexpect module
that will *always* look for certain error conditions for OpenPOWER machines.

This is to enable op-test test cases to fail *quickly* in the event of errors
such as kernel panics, RCU stalls, machine checks, firmware crashes etc.

In the event of error, the failure_callback function will be called, which
typically will be set up to set the machine state to UNKNOWN, so that when
the next test starts executing, we re-IPL the system to get back to a clean
slate.

When developing test cases, use OPexpect over pexpect. If you *intend* for
certain error conditions to occur, you can catch the exceptions that OPexpect
throws.
"""

import pexpect
from Exceptions import *
import OpTestSystem


class spawn(pexpect.spawn):
    def __init__(self, command, args=[], maxread=8000,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 ignore_sighup=False, echo=True, preexec_fn=None,
                 encoding=None, codec_errors='strict', dimensions=None,
                 failure_callback=None, failure_callback_data=None):
        self.command = command
        self.failure_callback = failure_callback
        self.failure_callback_data = failure_callback_data
        super(spawn, self).__init__(command, args=args,
                                    maxread=maxread,
                                    searchwindowsize=searchwindowsize,
                                    logfile=logfile,
                                    cwd=cwd, env=env,
                                    ignore_sighup=ignore_sighup)

    def set_system(self, system):
        self.op_test_system = system
        return

    def expect(self, pattern, timeout=-1, searchwindowsize=-1, async=False):
        op_patterns = ["qemu: could find kernel",
                       "INFO: rcu_sched self-detected stall on CPU",
                       "kernel BUG at",
                       "Kernel panic",
                       "Watchdog .* Hard LOCKUP",
                       "Oops: Kernel access of bad area",
                       "\[[0-9. ]+,0\] Assert fail:",
                       "\[[0-9. ]+,[0-9]\] Unexpected exception",
                       "OPAL: Reboot requested due to Platform error."
        ]

        patterns = list(op_patterns) # we want a *copy*
        if isinstance(pattern, list):
            patterns = patterns + pattern
        else:
            patterns.append(pattern)

        r = super(spawn,self).expect(patterns,
                                     timeout=timeout,
                                     searchwindowsize=searchwindowsize)

        if r in [pexpect.EOF, pexpect.TIMEOUT]:
            return r

        if r == 0:
            raise CommandFailed(self.command, patterns[r], -1)

        state = None

        if r in [1,2,3,4,5,6,7,8]:
            # We set the system state to UNKNOWN as we want to have a path
            # to recover and run the next test, which is going to be to IPL
            # the box again.
            # We do this via a callback rather than any other method as that's
            # just a *lot* easier with current code structure
            if self.failure_callback:
                state = self.failure_callback(self.failure_callback_data)
        if r in [1,2,3,4,5]:
            log = self.after
            l = 0

            while l is not pexpect.TIMEOUT:
                l = super(spawn,self).expect(["INFO: rcu_sched self-detected stall on CPU",
                                              ":mon>",
                                              "Rebooting in \d+ seconds",
                                              "Kernel panic - not syncing: Hard LOCKUP"],
                                             timeout=10)
                log = log + self.before + self.after
                if l in [1,2,3]:
                    # We know we have the end of the error message, so let's stop here.
                    break

            if r == 1:
                raise KernelSoftLockup(state, log)
            if r == 2:
                raise KernelBug(state, log)
            if r == 3:
                raise KernelPanic(state, log)
            if r == 4:
                raise KernelHardLockup(state, log)
            if r == 5:
                raise KernelOOPS(state, log)

        if r in [6,7]:
            l = 0
            log = self.after
            l = super(spawn,self).expect("boot_entry.*\r\n", timeout=10)
            log = log + self.before + self.after
            if r == 6:
                raise SkibootAssert(state, log)
            if r == 7:
                raise SkibootException(state, log)

        if r in [8]:
            # Reboot due to Platform error
            # Let's attempt to capture Hostboot output
            log = self.before + self.after
            try:
                l = super(spawn,self).expect("================================================",
                                             timeout=120)
                log = log + self.before + self.after
                l = super(spawn,self).expect("Error reported by", timeout=10)
                log = log + self.before + self.after
                l = super(spawn,self).expect("================================================",
                                             timeout=60)
                log = log + self.before + self.after
                l = super(spawn,self).expect("ISTEP", timeout=20)
                log = log + self.before + self.after
            except pexpect.TIMEOUT as t:
                pass
            raise PlatformError(state, log)

        return r - len(op_patterns)
