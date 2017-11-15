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

#
# OPexpect
# A wrapper around pexpect, but expects a bunch of common failures
# so that each expect call doesn't have to watch out for them.
# Things like OPAL asserts, kernel crashes, RCU stalls etc.
#

import pexpect
from Exceptions import *
import OpTestSystem

class spawn(pexpect.spawn):
    def __init__(self, command, args=[], timeout=30, maxread=2000,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 ignore_sighup=False, echo=True, preexec_fn=None,
                 encoding=None, codec_errors='strict', dimensions=None,
                 op_test_system=None):
        self.command = command
        self.op_test_system = op_test_system
        super(spawn, self).__init__(command, args=args, timeout=timeout,
                                    maxread=maxread,
                                    searchwindowsize=searchwindowsize,
                                    logfile=logfile,
                                    cwd=cwd, env=env,
                                    ignore_sighup=ignore_sighup)

    def expect(self, pattern, timeout=-1, searchwindowsize=-1, async=False):
        op_patterns = ["qemu: could find kernel",
                       "INFO: rcu_sched self-detected stall on CPU",
                       "kernel BUG at",
                       "Kernel panic",
                       "\[[0-9. ]+,0\] Assert fail:",
                       "\[[0-9. ]+,[0-9]\] Unexpected exception",
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

        if r in [1,2,3,4,5]:
            # We set the system state to UNKNOWN as we want to have a path
            # to recover and run the next test, which is going to be to IPL
            # the box again.
            # This code path isn't really hooked up yet though...
            state = None
            if self.op_test_system is not None:
                state = self.op_test_system.get_state()
                self.op_test_system.set_state(OpTestSystem.OpSystemState.UNKNOWN)
        if r in [1,2,3]:
            log = self.after
            l = 0

            while l is not pexpect.TIMEOUT:
                l = super(spawn,self).expect(["INFO: rcu_sched self-detected stall on CPU",
                                             ":mon>",
                                             "Rebooting in \d+ seconds"],
                                             timeout=10)
                log = log + self.before + self.after
                if l in [1,2]:
                    # We know we have the end of the error message, so let's stop here.
                    break

            if r == 1:
                raise KernelSoftLockup(state, log)
            if r == 2:
                raise KernelBug(state, log)
            if r == 3:
                raise KernelPanic(state, log)

        if r in [4,5]:
            l = 0
            log = self.after
            l = super(spawn,self).expect("boot_entry.*\r\n", timeout=10)
            log = log + self.before + self.after
            if r == 4:
                raise SkibootAssert(state, log)
            if r == 5:
                raise SkibootException(state, log)

        return r - len(op_patterns)
