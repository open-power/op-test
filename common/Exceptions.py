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

class CommandFailed(Exception):
    def __init__(self, command, output, exitcode):
        self.command = command
        self.output = output
        self.exitcode = exitcode

    def __str__(self):
        return "Command '%s' exited with %d.\nOutput:\n%s" % (self.command, self.exitcode, self.output)

class BMCDisconnected(Exception):
    def __init__(self, notice):
        self.notice = notice
    def __str__(self):
        return "BMC disconnected due to '%s'" % self.notice

class NoKernelConfig(Exception):
    def __init__(self, kernel, path):
        self.kernel = kernel
        self.path = path
    def __str__(self):
        return "kernel config for %s not found, looked for %s" % (self.kernel, self.path)

class KernelModuleNotLoaded(Exception):
    def __init__(self, module):
        self.module = module
    def __str__(self):
        return "Kernel module %s not loaded" % (self.module)

class KernelConfigNotSet(Exception):
    def __init__(self, opt):
        self.opt = opt
    def __str__(self):
        return "Kernel config %s not present" % (self.opt)

class KernelSoftLockup(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Soft lockup (machine in state %s): %s" % (self.state, self.log)

class KernelHardLockup(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hard lockup (machine in state %s): %s" % (self.state, self.log)

class KernelBug(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel bug in state %s: %s" % (self.state, self.log)

class SkibootAssert(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hit skiboot assert in state %s: %s" % (self.state, self.log)

class SkibootException(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hit skiboot unexpected exception in state %s: %s" % (self.state, self.log)

class KernelPanic(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel panic in state %s: %s" % (self.state, self.log)

class PlatformError(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Platform error at state %s. Log: %s" % (self.state, self.log)
