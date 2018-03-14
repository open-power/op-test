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

'''
op-test Exceptions
------------------

These exceptions are used throughout op-test to help testing error
conditions as well as failing tests when unexpected errors occur.
'''

class CommandFailed(Exception):
    '''
    Running a command (BMC or Host) failed with non-zero exit code.
    '''
    def __init__(self, command, output, exitcode):
        self.command = command
        self.output = output
        self.exitcode = exitcode

    def __str__(self):
        return "Command '%s' exited with %d.\nOutput:\n%s" % (self.command, self.exitcode, self.output)

class BMCDisconnected(Exception):
    '''
    BMC Cosnole was disconnected unexpectedly. e.g. it may have crashed
    '''
    def __init__(self, notice):
        self.notice = notice
    def __str__(self):
        return "BMC console disconnected due to '%s'" % self.notice

class NoKernelConfig(Exception):
    '''
    We needed to grep host kernel config for a config option, but could not
    find the needed config file
    '''
    def __init__(self, kernel, path):
        self.kernel = kernel
        self.path = path
    def __str__(self):
        return "kernel config for %s not found, looked for %s" % (self.kernel, self.path)

class KernelModuleNotLoaded(Exception):
    '''
    Kernel module needed to run test wasn't loaded
    '''
    def __init__(self, module):
        self.module = module
    def __str__(self):
        return "Kernel module %s not loaded" % (self.module)

class KernelConfigNotSet(Exception):
    '''
    A kernel config option needed by the test was not set for the running
    kernel.
    '''
    def __init__(self, opt):
        self.opt = opt
    def __str__(self):
        return "Kernel config %s not present" % (self.opt)

class KernelSoftLockup(Exception):
    '''
    We caught a soft lockup. Mostly this will mean we need to fail the test and reboot.
    Some test cases may *intentionally* cause these, so they can catch them and act
    appropriately.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Soft lockup (machine in state %s): %s" % (self.state, self.log)

class KernelHardLockup(Exception):
    '''
    We detected a hard lockup from the running kernel.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hard lockup (machine in state %s): %s" % (self.state, self.log)

class KernelOOPS(Exception):
    '''
    We detected a kernel OOPS. Mostly this will mean we need to fail the test and reboot.
    Some test cases may *intentionally* cause these, so they can catch them and act
    appropriately.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel OOPS (machine in state %s): %s" % (self.state, self.log)

class KernelKdump(Exception):
    '''
    We observe a Kdump kernel booting after a kernel crash, to dump vmcore for debug.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel Kdump (machine in state %s): %s" % (self.state, self.log)

class KernelCrashUnknown(Exception):
    '''
    Kernel crashed but it didn't reach the end failure condition(i.e a timeout occured)
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel crash unknown state (machine in state %s): %s" % (self.state, self.log)

class KernelBug(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel bug in state %s: %s" % (self.state, self.log)

class SkibootAssert(Exception):
    '''
    We detected an assert from OPAL (skiboot) firmware.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hit skiboot assert in state %s: %s" % (self.state, self.log)

class SkibootException(Exception):
    '''
    We detected an exception from OPAL (skiboot) firmware.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Hit skiboot unexpected exception in state %s: %s" % (self.state, self.log)

class KernelPanic(Exception):
    '''
    Kernel got panic due to high seveirty conditions
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Kernel panic in state %s: %s" % (self.state, self.log)

class PlatformError(Exception):
    '''
    We detected a system reboot due to platform error(i.e checkstop, machine check, MCE, etc)
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state
    def __str__(self):
        return "Platform error at state %s. Log: %s" % (self.state, self.log)
