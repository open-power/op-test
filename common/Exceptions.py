#!/usr/bin/env python2
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

When subclassing Exceptions be aware to use 'message' as the
embedded variable so that e.message can be retrieved and
searched for filtering if desired in future use cases.

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
        return "Command '{}' exited with '{}'.\nOutput\n{}".format(
            self.command, self.exitcode, self.output)


class SSHSessionDisconnected(Exception):
    '''
    SSH session/console was disconnected unexpectedly. e.g. it may have crashed
    '''
    def __init__(self, notice):
        self.notice = notice

    def __str__(self):
        return "SSH session/console disconnected due to '{}'".format(
            self.notice)


class BMCDisconnected(Exception):
    '''
    BMC Cosnole was disconnected unexpectedly. e.g. it may have crashed
    '''
    def __init__(self, notice):
        self.notice = notice

    def __str__(self):
        return "BMC console disconnected due to '{}'".format(
            self.notice)


class NoKernelConfig(Exception):
    '''
    We needed to grep host kernel config for a config option, but could not
    find the needed config file
    '''
    def __init__(self, kernel, path):
        self.kernel = kernel
        self.path = path

    def __str__(self):
        return "kernel config for {} not found, looked for {}".format(
            self.kernel, self.path)


class KernelModuleNotLoaded(Exception):
    '''
    Kernel module needed to run test wasn't loaded
    '''
    def __init__(self, module):
        self.module = module

    def __str__(self):
        return "Kernel module '{}' not loaded".format(
            self.module)


class KernelConfigNotSet(Exception):
    '''
    A kernel config option needed by the test was not set for the running
    kernel.
    '''
    def __init__(self, opt):
        self.opt = opt

    def __str__(self):
        return "Kernel config '{}' not present".format(
            self.opt)


class KernelSoftLockup(Exception):
    '''
    We caught a soft lockup. Mostly this will mean we need to fail the test
    and reboot.
    Some test cases may *intentionally* cause these, so they can catch them
    and act appropriately.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Soft lockup (machine in state '{}'): {}".format(
            self.state, self.log)


class KernelHardLockup(Exception):
    '''
    We detected a hard lockup from the running kernel.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Hard lockup (machine in state '{}'): {}".format(
            self.state, self.log)


class KernelOOPS(Exception):
    '''
    We detected a kernel OOPS. Mostly this will mean we need to fail the test
    and reboot.
    Some test cases may *intentionally* cause these, so they can catch them
    and act appropriately.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Kernel OOPS (machine in state '{}'): {}".format(
            self.state, self.log)


class KernelKdump(Exception):
    '''
    We observe a Kdump kernel booting after a kernel crash, to dump vmcore
    for debug.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Kernel Kdump (machine in state '{}'): {}".format(
            self.state, self.log)


class KernelCrashUnknown(Exception):
    '''
    Kernel crashed but it didn't reach the end failure condition
    (i.e a timeout occured)
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Kernel crash unknown state (machine in state '{}'): {}".format(
            self.state, self.log)


class KernelBug(Exception):
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Kernel bug in state '{}': {}".format(
            self.state, self.log)


class SkibootAssert(Exception):
    '''
    We detected an assert from OPAL (skiboot) firmware.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Hit skiboot assert in state '{}': {}".format(
            self.state, self.log)


class SkibootException(Exception):
    '''
    We detected an exception from OPAL (skiboot) firmware.
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Hit skiboot unexpected exception in state '{}': {}".format(
            self.state, self.log)


class KernelPanic(Exception):
    '''
    Kernel got panic due to high seveirty conditions
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Kernel panic in state '{}': {}".format(
            self.state, self.log)


class PlatformError(Exception):
    '''
    We detected a system reboot due to platform error (i.e checkstop,
    machine check, MCE, etc)
    '''
    def __init__(self, state, log):
        self.log = log
        self.state = state

    def __str__(self):
        return "Platform error at state '{}'. Log: {}".format(
            self.state, self.log)


class HostbootShutdown(Exception):
    '''
    We detected that Hostboot got an IPMI shutdown request.
    '''
    def __str__(self):
        return "Detected hostboot got IPMI shutdown request"


class UnexpectedCase(Exception):
    '''
    We detected something we should not have.
    '''
    def __init__(self, **kwargs):
        default_vals = {'state': None, 'message': None}
        self.kwargs = {}
        for key in default_vals:
            if key not in list(kwargs.keys()):
                self.kwargs[key] = default_vals[key]
            else:
                self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something unexpected happened in State=\"{}\"'
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(
                    self.kwargs['state'], self.kwargs['message']))


class WaitForIt(Exception):
    '''
    We need special handling per case so give back desired data.
    '''
    def __init__(self, **kwargs):
        default_vals = {'expect_dict': None, 'reconnect_count': 0}
        self.kwargs = {}
        for key in default_vals:
            if key not in list(kwargs.keys()):
                self.kwargs[key] = default_vals[key]
            else:
                self.kwargs[key] = kwargs[key]

    def __str__(self):
        return ('Waiting for "{}" did not succeed, check the loop_max if '
                'needing to wait longer (number of reconnect attempts '
                'were {})'.format(self.kwargs['expect_dict'],
                                  self.kwargs['reconnect_count']))


class RecoverFailed(Exception):
    '''
    We tried to recover and did not succeed.
    '''
    def __init__(self, **kwargs):
        default_vals = {'before': None, 'after': None, 'msg': None}
        self.kwargs = {}
        for key in default_vals:
            if key not in list(kwargs.keys()):
                self.kwargs[key] = default_vals[key]
            else:
                self.kwargs[key] = kwargs[key]

    def __str__(self):
        return ('Unable to get the proper prompt, probably just retry'
                ' review the following for more details\n'
                'Expect Before Buffer=\"{}\"\nExpect After Buffer=\"{}\"'
                '\nMessage=\"{}\"'.format(self.kwargs['before'],
                                          self.kwargs['after'],
                                          self.kwargs['msg']))


class UnknownStateTransition(Exception):
    '''
    We tried to transition to UNKNOWN, something happened.
    '''
    def __init__(self, **kwargs):
        default_vals = {'state': None, 'message': None}
        self.kwargs = {}
        for key in default_vals:
            if key not in list(kwargs.keys()):
                self.kwargs[key] = default_vals[key]
            else:
                self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something happened system state=\"{}\" and we '
                'transitioned to UNKNOWN state. '
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(self.kwargs['state'],
                                        self.kwargs['message']))


class HostLocker(Exception):
    '''
    We tried to setup with HostLocker and something happened.
    '''
    def __init__(self, **kwargs):
        default_vals = {'message': None}
        self.kwargs = {}
        for key in default_vals:
          if key not in list(kwargs.keys()):
            self.kwargs[key] = default_vals[key]
          else:
            self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something happened setting up HostLocker. '
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(self.kwargs['message']))


class HTTPCheck(Exception):
    '''
    HTTP Server related and something happened.
    '''
    def __init__(self, **kwargs):
        default_vals = {'message': None}
        self.kwargs = {}
        for key in default_vals:
          if key not in list(kwargs.keys()):
            self.kwargs[key] = default_vals[key]
          else:
            self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something happened with the HTTP Server. '
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(self.kwargs['message']))

class OpExit(SystemExit):
    '''
    We are exiting and want to set an exit code.
    SystemExit will bubble up and out.
    Callers must use atexit to register cleanup
    atexit.register(self.__del__)
    def __del__(self):
        self.util.cleanup()
    '''
    def __init__(self, **kwargs):
        default_vals = {'message': None, 'code': 0}
        self.kwargs = {}
        for key in default_vals:
          if key not in list(kwargs.keys()):
            self.kwargs[key] = default_vals[key]
          else:
            self.kwargs[key] = kwargs[key]

        self.code = self.kwargs['code']
        self.message =  self.kwargs['message']

class AES(Exception):
    '''
    We tried to setup with Automated Environment Sharing (AES)
    and something happened.
    '''
    def __init__(self, **kwargs):
        default_vals = {'message': None}
        self.kwargs = {}
        for key in default_vals:
          if key not in list(kwargs.keys()):
            self.kwargs[key] = default_vals[key]
          else:
            self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something happened setting up Automated '
                'Environment Sharing (AES). '
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(self.kwargs['message']))


class ParameterCheck(Exception):
    '''
    We think something is not properly setup.
    '''
    def __init__(self, **kwargs):
        default_vals = {'message': None}
        self.kwargs = {}
        for key in default_vals:
          if key not in list(kwargs.keys()):
            self.kwargs[key] = default_vals[key]
          else:
            self.kwargs[key] = kwargs[key]

        self.message = kwargs['message']

    def __str__(self):
        return ('Something does not appear to be configured'
                ' or setup properly. '
                ' Review the following for more details\n'
                'Message=\"{}\"'.format(self.kwargs['message']))


class StoppingSystem(Exception):
    '''
    We have either set the system to stop for some condition or reached the
    kill_cord limit and stopping.
    '''
    def __str__(self):
        return "System has either set the stop flag for some condition or "\
            "reached the kill_cord limit on trying to continue, check that "\
            "your system is operational"


class ConsoleSettings(Exception):
    '''
    We need special handling per case so give back desired data.
    '''
    def __init__(self, **kwargs):
        default_vals = {'before': None, 'after': None, 'msg': None}
        self.kwargs = {}
        for key in default_vals:
            if key not in list(kwargs.keys()):
                self.kwargs[key] = default_vals[key]
            else:
                self.kwargs[key] = kwargs[key]

    def __str__(self):
        return ("Setting the prompt or logging in for the console was not "
                "successful, check credentials and review the following"
                " for more details\nExpect Before Buffer=\"{}\"\n"
                "Expect After Buffer=\"{}\" \nMessage=\"{}\""
                "".format(self.kwargs['before'],
                          self.kwargs['after'],
                          self.kwargs['msg']))
