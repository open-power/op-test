#!/usr/bin/python
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/common/OpTestHost.py $
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

## @package OpTestHost
#  Host package which contains all functions related to HOST communication
#
#  This class encapsulates all function which deals with the Host
#  in OpenPower systems

import sys
import os
import string
import time
import random
import subprocess
import re
import telnetlib
import socket
import select
import pty
import pexpect
import commands
try:
    import pxssh
except ImportError:
    from pexpect import pxssh


from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestUtil import OpTestUtil

class SSHConnectionState():
    DISCONNECTED = 0
    CONNECTED = 1

class SSHConnection():
    def __init__(self, ip=None, username=None, password=None):
        self.ip = ip
        self.username = username
        self.password = password
        self.state = SSHConnectionState.DISCONNECTED
        # pxssh has a nice 'echo=False' mode, but only
        # on more recent distros, so we can't use it :(
        p = pxssh.pxssh()
        # Work-around for old pxssh not having options= parameter
        p.SSH_OPTS = p.SSH_OPTS + " -o 'StrictHostKeyChecking=no'"
        p.SSH_OPTS = p.SSH_OPTS + " -o 'UserKnownHostsFile /dev/null' "
        p.force_password = True
        p.logfile = sys.stdout
        self.pxssh = p

    def terminate(self):
        if self.state == SSHConnectionState.CONNECTED:
            self.pxssh.terminate()
            self.state = SSHConnectionState.DISCONNECTED


    def connect(self):
        if self.state == SSHConnectionState.CONNECTED:
            self.pxssh.terminate()
            self.state = SSHConnectionState.DISCONNECTED

        print "#SSH CONNECT"
        p = self.pxssh
        p.login(self.ip, self.username, self.password)
        p.sendline()
        p.prompt(timeout=60)
        # Ubuntu likes to be "helpful" and alias grep to
        # include color, which isn't helpful at all. So let's
        # go back to absolutely no messing around with the shell
        p.sendline('exec bash --norc --noprofile')
        p.set_unique_prompt()
        self.state = SSHConnectionState.CONNECTED


    def get_console(self):
        if self.state == SSHConnectionState.DISCONNECTED:
            self.connect()

        count = 0
        while (not self.pxssh.isalive()):
            print '# Reconnecting'
            if (count > 0):
                time.sleep(2)
            self.connect()
            count += 1
            if count > 120:
                raise Exception("Cannot login via SSH")

        return self.pxssh

    def run_command(self, command, timeout=300):
        c = self.get_console()
        c.sendline(command)
        c.prompt(timeout)
        # We manually remove the echo of the command
        return '\n'.join(c.before.split('\n')[1:])


class OpTestHost():

    ##
    # @brief Initialize this object
    #
    # @param i_hostip @type string: IP Address of the host
    # @param i_hostuser @type string: Userid to log into the host
    # @param i_hostpasswd @type string: Password of the userid to log into the host
    # @param i_bmcip @type string: IP Address of the bmc
    # @param i_ffdcDir @type string:specifies the directory under which to save all FFDC data
    #
    def __init__(self, i_hostip, i_hostuser, i_hostpasswd, i_bmcip, i_ffdcDir=None):
        self.ip = i_hostip
        self.user = i_hostuser
        self.passwd = i_hostpasswd
        self.util = OpTestUtil()
        self.bmcip = i_bmcip
        self.cv_ffdcDir = i_ffdcDir
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        self.results_dir = self.cv_ffdcDir
        self.ssh = SSHConnection(i_hostip, i_hostuser, i_hostpasswd)

    def hostname(self):
        return self.ip

    def username(self):
        return self.user

    def password(self):
        return self.passwd

    def get_ssh_connection(self):
        return self.ssh

    ##
    # @brief Get and Record Ubunto OS level
    #
    # @return l_oslevel @type string: OS level of the host provided
    #         or raise OpTestError
    #
    def host_get_OS_Level(self):
        l_oslevel = self.ssh.run_command(BMC_CONST.BMC_GET_OS_RELEASE, timeout=60)
        print l_oslevel
        return l_oslevel


    ##
    # @brief Executes a command on the os of the bmc to protect network setting
    #
    # @return OpTestError if failed
    #
    def host_protect_network_setting(self):
        try:
            l_rc = self.ssh.run_command(BMC_CONST.OS_PRESERVE_NETWORK, timeout=60)
        except:
            l_errmsg = "Can't preserve network setting"
            print l_errmsg
            raise OpTestError(l_errmsg)

    ##
    # @brief Performs a cold reset onto the host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_cold_reset(self):

        print ("Applying Cold reset on host.")
        l_rc = self.ssh.run_command(BMC_CONST.HOST_COLD_RESET, timeout=60)

        # TODO: enable once defect SW331585 is fixed
        '''if BMC_CONST.BMC_PASS_COLD_RESET in l_rc:
            print l_rc
            time.sleep(BMC_CONST.BMC_COLD_RESET_DELAY)
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Cold reset Failed"
            print l_msg
            raise OpTestError(l_msg)'''

        self.util.PingFunc(self.bmcip, BMC_CONST.PING_RETRY_FOR_STABILITY)


    ##
    # @brief Flashes image using ipmitool
    #
    # @param i_image @type string: hpm file including location
    # @param i_imagecomponent @type string: component to be
    #        update from the hpm file BMC_CONST.BMC_FW_IMAGE_UPDATE
    #        or BMC_CONST.BMC_PNOR_IMAGE
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_code_update(self, i_image, imagecomponent):

        # Copy the hpm file to the tmp folder in the host
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying hpm file to host failed"
            print l_msg
            raise OpTestError(l_msg)

        #self.host_protect_network_setting() #writing to host is not stable
        l_cmd = "\necho y | ipmitool -I usb " + BMC_CONST.BMC_HPM_UPDATE + "/tmp/" \
                + i_image.rsplit("/", 1)[-1] + " " + imagecomponent
        print l_cmd
        try:
            l_rc = self.ssh.run_command(l_cmd, timeout=1500)
            print l_rc
            self.ssh.run_command("rm -rf /tmp/" + i_image.rsplit("/", 1)[1],timeout=120)
        except subprocess.CalledProcessError:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

        if(l_rc.__contains__("Firmware upgrade procedure successful")):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Code Update Failed"
            print l_msg
            raise OpTestError(l_msg)

    def host_run_command(self, i_cmd, timeout=1500):
        return self.ssh.run_command(i_cmd, timeout)

    ##
    # @brief It will gather OPAL Message logs and store the copy in a logfile
    #        which will be stored in FFDC dir.
    #
    # @return BMC_CONST.FW_SUCCESS  or raise OpTestError
    #
    def host_gather_opal_msg_log(self):
        try:
            l_data = self.host_run_command(BMC_CONST.OPAL_MSG_LOG)
        except OpTestError:
            l_msg = "Failed to gather OPAL message logs"
            raise OpTestError(l_msg)

        if not self.results_dir:
            print l_data
            return

        l_res = (time.asctime(time.localtime())).replace(" ", "_")
        l_logFile = "Opal_msglog_%s.log" % l_res
        fn = os.path.join(self.results_dir, l_logFile)
        print fn
        with open(fn, 'w') as f:
            f.write(l_data)


    ##
    # @brief Check if one or more binaries are present on host
    #
    # @param i_cmd @type string: binaries to check for
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_check_command(self, *i_cmd):
        l_cmd = 'which ' + ' '.join(i_cmd) + '; echo $?'
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.splitlines()

        if (int(l_res[-1]) == 0):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "host_check_command: (%s) not present on host. output of '%s': %s" % (','.join(i_cmd), l_cmd, '\n'.join(l_res))
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief It will get the linux kernel version on host
    #
    # @return l_kernel @type string: kernel version of the host provided
    #         or raise OpTestError
    #
    def host_get_kernel_version(self):
        l_kernel = self.ssh.run_command("uname -a | awk {'print $3'}", timeout=60)
        l_kernel = l_kernel.replace("\r\n", "")
        print l_kernel
        return l_kernel

    ##
    # @brief This function will checks first for config file for a given kernel version on host,
    #        if available then check for config option value and return that value
    #            whether it is y or m...etc.
    #        sample config option values:
    #        CONFIG_CRYPTO_ZLIB=m
    #        CONFIG_CRYPTO_LZO=y
    #        # CONFIG_CRYPTO_842 is not set
    #
    #
    # @param i_kernel @type string: kernel version
    # @param i_config @type string: Which config option want to check in config file
    #                               Ex:CONFIG_SENSORS_IBMPOWERNV
    #
    # @return l_val @type string: It will return config option value y or m,
    #                             or raise OpTestError if config file is not available on host
    #                             or raise OpTestError if config option is not set in file.
    #
    def host_check_config(self, i_kernel, i_config):
        l_file = "/boot/config-%s" % i_kernel
        l_res = self.ssh.run_command("test -e %s; echo $?" % l_file, timeout=60)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Config file is available"
        else:
            l_msg = "Config file %s is not available on host" % l_file
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "cat %s | grep -i --color=never %s" % (l_file, i_config)
        print l_cmd
        l_res = self.ssh.run_command(l_cmd, timeout=60)
        print l_res
        try:
            l_val = ((l_res.split("=")[1]).replace("\r\n", ""))
        except:
            print l_val
            l_msg = "config option is not set,exiting..."
            print l_msg
            raise OpTestError(l_msg)
        return l_val

    ##
    # @brief It will return installed package name for given linux command(i_cmd) on host
    #
    # @param i_cmd @type string: linux command
    # @param i_oslevel @type string: OS level
    #
    # @return l_pkg @type string: installed package on host
    #
    def host_check_pkg_for_utility(self, i_oslevel, i_cmd):
        if 'Ubuntu' in i_oslevel:
            l_res = self.ssh.run_command("dpkg -S `which %s`" % i_cmd, timeout=60)
            return l_res
        else:
            l_cmd = "rpm -qf `which %s`" % i_cmd
            l_res = self.ssh_run_command(l_cmd, timeout=60)
            l_pkg = l_res.replace("\r\n", "")
            print l_pkg
            return l_pkg

    ##
    # @brief It will check whether a package is installed in a host OS
    #
    # @param i_oslevel @type string: OS level
    # @param i_package @type string: package name
    #
    # @return BMC_CONST.FW_SUCCESS if package is available
    #         raise OpTestError if package is not available
    #
    def host_check_pkg_availability(self, i_oslevel, i_package):
        if 'Ubuntu' in i_oslevel:
            l_res = self.host_run_command("dpkg -l %s;echo $?" % i_package)
        else:
            l_cmd = "rpm -qa | grep -i %s" % i_package
            l_res = self.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if (int(l_res[-1]) == 0):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Package %s is not there in host OS" % i_package
            raise OpTestError(l_msg)

    ##
    # @brief This function loads ibmpowernv driver only on powernv platform
    #        and also this function works only in root user mode
    #
    # @param i_oslevel @type string: OS level
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_load_ibmpowernv(self, i_oslevel):
        if "PowerKVM" not in i_oslevel:
            l_rc = self.ssh.run_command("modprobe ibmpowernv; echo $?",timeout=60)
            l_rc = l_rc.replace("\r\n", "")
            if int(l_rc) == 0:
                cmd = "lsmod | grep -i ibmpowernv"
                response = self.ssh.run_command(cmd, timeout=60)
                if "ibmpowernv" not in response:
                    l_msg = "ibmpowernv module is not loaded, exiting"
                    raise OpTestError(l_msg)
                else:
                    print "ibmpowernv module is loaded"
                print cmd
                print response
                return BMC_CONST.FW_SUCCESS
            else:
                l_msg = "modprobe failed while loading ibmpowernv,exiting..."
                print l_msg
                raise OpTestError(l_msg)
        else:
            return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function restarts the lm_sensors service on host using systemctl utility
    #        systemctl utility is not present in ubuntu, This function will work in remaining all
    #        other OS'es i.e redhat, sles and PowerKVM
    #
    # @param i_oslevel @type string: OS level
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_start_lm_sensor_svc(self, i_oslevel):
        if 'Ubuntu' in i_oslevel:
            pass
        else:
            try:
                # Start the lm_sensors service
                cmd = "/bin/systemctl stop  lm_sensors.service"
                self.host_run_command(cmd)
                cmd = "/bin/systemctl start  lm_sensors.service"
                self.host_run_command(cmd)
                cmd = "/bin/systemctl status  lm_sensors.service"
                res = self.host_run_command(cmd)
                return BMC_CONST.FW_SUCCESS
            except:
                l_msg = "loading lm_sensors service failed"
                print l_msg
                raise OpTestError(l_msg)

    ##
    # @brief It will clone latest linux git repository in i_dir directory
    #
    # @param i_dir @type string: directory where linux source will be cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_clone_linux_source(self, i_dir):
        l_msg = 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git'
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.ssh.run_command("rm -rf %s" % i_dir, timeout=300)
        self.ssh.run_command("mkdir %s" % i_dir, timeout=60)
        try:
            print l_cmd
            res = self.ssh.run_command(l_cmd, timeout=1500)
            print res
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning linux git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief reads msglog for getting Chip and Core information
    #
    # @return @type string: Chip and Core information
    #        else raise OpTestError
    def host_read_msglog_core(self):
        try:
            return self.ssh.run_command(BMC_CONST.OS_READ_MSGLOG_CORE, timeout=60)
        except:
            l_errmsg = "Can't get msglog data"
            print l_errmsg
            raise OpTestError(l_errmsg)

    ##
    # @brief reads getscom data
    # example:
    # Chip ID  | Rev   | Chip type
    # ---------|-------|--------
    # 80000005 | DD2.0 | Centaur memory buffer
    # 80000004 | DD2.0 | Centaur memory buffer
    # 00000000 | DD2.0 | P8 (Venice) processor
    #
    # @param i_xscom_dir @type string: directory where getscom is installed
    #
    # @return @type string: getscom data
    #        else raise OpTestError
    def host_read_getscom_data(self, i_xscom_dir):
        try:
            l_rc = self.ssh.run_command(BMC_CONST.SUDO_COMMAND + i_xscom_dir + BMC_CONST.OS_GETSCOM_LIST, timeout=60)
        except OpTestError as e:
            l_errmsg = "Can't get getscom data"
            print l_errmsg
            raise OpTestError(l_errmsg)

        if("command not found" in l_rc):
            l_errmsg = "Failed to locate getscom. Make sure it is installed in dir: " + i_xscom_dir
            print l_errmsg
            raise OpTestError(l_errmsg)

        return l_rc


    ##
    # @brief injects error using getscom
    #
    # @param i_xscom_dir @type string: directory where putscom is installed
    # param i_error @type string: error to be injected including the location
    #
    # @return output generated after executing putscom command or else raise OpTestError
    #
    def host_putscom(self, i_xscom_dir, i_error):

        print('Injecting Error.')
        l_rc = self._execute_no_return(BMC_CONST.SUDO_COMMAND + i_xscom_dir + BMC_CONST.OS_PUTSCOM_ERROR + i_error)

    ##
    # @brief Clears the gard records
    #
    # @param i_gard_dir @type string: directory where putscom is installed
    #
    # @return BMC_CONST.FW_SUCCESS or else raise OpTestError
    #
    def host_clear_gard_records(self, i_gard_dir):

        l_rc = self.ssh.run_command(BMC_CONST.SUDO_COMMAND + i_gard_dir + BMC_CONST.CLEAR_GARD_CMD, timeout=60)

        if(BMC_CONST.GARD_CLEAR_SUCCESSFUL not in l_rc):
            l_msg = l_rc + '. Failed to clear gard'
            print l_msg
            raise OpTestError(l_msg)

        # Check to make sure no gard records were left
        l_result = self.host_list_gard_records(i_gard_dir)
        if(BMC_CONST.NO_GARD_RECORDS not in l_result):
            l_msg = l_rc + '. Gard records still found after clearing them'
            print l_msg
            raise OpTestError(l_msg)

        return BMC_CONST.FW_SUCCESS


    ##
    # @brief Lists all gard records
    #
    # @param i_gard_dir @type string: directory where putscom is installed
    #
    # @return gard records or else raise OpTestError
    #
    def host_list_gard_records(self, i_gard_dir):
        try:
            return self.ssh.run_command(BMC_CONST.SUDO_COMMAND + i_gard_dir + BMC_CONST.LIST_GARD_CMD, timeout=60)
        except:
            l_errmsg = "Can't clear gard records"
            print l_errmsg
            raise OpTestError(l_errmsg)


    ##
    # @brief  Execute a command on the targeted host but don't expect
    #             any return data.
    #
    # @param     i_cmd: @type str: command to be executed
    # @param     i_timeout: @type int:
    #
    # @return   BMC_CONST.FW_SUCCESS or else raise OpTestError
    #
    def _execute_no_return(self, i_cmd, i_timeout=60):

        print('Executing command: ' + i_cmd)
        try:
            p = pxssh.pxssh()
            p.login(self.ip, self.user, self.passwd)
            p.sendline()
            p.prompt()
            p.sendline(i_cmd)
            p.prompt(i_timeout)
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Failed to execute command: " + i_cmd
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief enable/disable cpu states
    #
    # @param i_cpu_state @type string: BMC_CONST.CPU_ENABLE_STATE/
    #                                  BMC_CONST.CPU_DISABLE_STATE
    #
    # @return BMC_CONST.FW_SUCCESS or OpTestError
    #
    def host_disable_enable_cpu_states(self, i_cpu_state):
        try:
            self.ssh.run_command(BMC_CONST.SUDO_COMMAND + "sh -c 'for i in " + \
                              BMC_CONST.CPU_IDLEMODE_STATE1 + "; do echo " + \
                              i_cpu_state  + " > $i; done'", timeout=60)
            self.ssh.run_command(BMC_CONST.SUDO_COMMAND + "sh -c 'for i in " + \
                              BMC_CONST.CPU_IDLEMODE_STATE2 + "; do echo " + \
                              i_cpu_state  + " > $i; done'", timeout=60)
            return BMC_CONST.FW_SUCCESS
        except:
            l_errmsg = "Could not enable/disable cpu idle states"
            print l_errmsg
            raise OpTestError(l_errmsg)

    ##
    # @brief This function will checks first for config file for a given kernel version on host,
    #        if available then check for config option value and return that value
    #            whether it is y or m...etc.
    #        sample config option values:
    #        CONFIG_CRYPTO_ZLIB=m
    #        CONFIG_CRYPTO_LZO=y
    #        # CONFIG_CRYPTO_842 is not set
    #
    #
    # @param i_kernel @type string: kernel version
    # @param i_config @type string: Which config option want to check in config file
    #                               Ex:CONFIG_SENSORS_IBMPOWERNV
    #
    # @return l_val @type string: It will return config option value y or m,
    #                             or raise OpTestError if config file is not available on host
    #                             or raise OpTestError if config option is not set in file.
    #
    def host_check_config(self, i_kernel, i_config):
        l_file = "/boot/config-%s" % i_kernel
        l_res = self.ssh.run_command("test -e %s; echo $?" % l_file, timeout=60)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Config file is available"
        else:
            l_msg = "Config file %s is not available on host" % l_file
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "cat %s | grep -i --color=never %s" % (l_file, i_config)
        print l_cmd
        l_res = self.ssh.run_command(l_cmd, timeout=60)
        print l_res
        try:
            l_val = ((l_res.split("=")[1]).replace("\r\n", ""))
        except:
            print l_val
            l_msg = "config option is not set,exiting..."
            print l_msg
            raise OpTestError(l_msg)
        return l_val

    ##
    # @brief It will load the module using modprobe and verify whether it is loaded or not
    #
    # @param i_module @type string: module name, which we want to load on host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_load_module(self, i_module):
        l_res = self.host_run_command("modprobe %s; echo $?" % i_module)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            pass
        else:
            l_msg = "Error in loading the module %s, modprobe failed" % i_module
            print l_msg
            raise OpTestError(l_msg)
        l_res = self.host_run_command("lsmod | grep -i --color=never %s" % i_module)
        if l_res.__contains__(i_module):
            print "%s module is loaded" % i_module
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = " %s module is not loaded" % i_module
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function will read real time clock(RTC) time using hwclock utility
    #
    # @return l_res @type string: return hwclock value if command execution successfull
    #           else raise OpTestError
    #
    def host_read_hwclock(self):
        print "Reading the hwclock"
        l_res = self.host_run_command("hwclock -r;echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return l_res
        else:
            l_msg = "Reading the hwclock failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function will read system time using date utility (This will be mantained by kernel)
    #
    # @return l_res @type string: return system time value if command execution successfull
    #           else raise OpTestError
    #
    def host_read_systime(self):
        print "Reading system time using date utility"
        l_res = self.host_run_command("date;echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return l_res
        else:
            l_msg = "Reading the system time failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function will set hwclock time using the --date option
    #        format should be "2015-01-01 12:12:12"
    #
    # @param i_time @type string: this is the time for setting the hwclock
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_set_hwclock_time(self, i_time):
        print "Setting the hwclock time to %s" % i_time
        l_res = self.host_run_command("hwclock --set --date \'%s\';echo $?" % i_time)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Setting the hwclock failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function will load driver module on host based on the config option
    #        if config value m: built as a module
    #                        y: driver built into kernel itself
    #        else   raises OpTestError
    #
    # @param i_kernel @type string: kernel version to get config file
    #        i_config @type string: config option to check in config file
    #        i_module @type string: driver module to load on host based on config value
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_load_module_based_on_config(self, i_kernel, i_config, i_module):
        l_val = self.host_check_config(i_kernel, i_config)
        if l_val == 'm':
            self.host_load_module(i_module)
        elif l_val == 'y':
            print "Driver built into kernel itself"
        else:
            l_msg = "Config value is changed"
            print l_msg
            raise OpTestError(l_msg)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function will return the list of installed i2c buses on host in two formats
    #        list-by number Ex: ["0","1","2",....]
    #        list-by-name  Ex: ["i2c-0","i2c-1","i2c-2"....]
    #
    # @return l_list @type list: list of i2c buses by number
    #         l_list1 @type list: list of i2c buses by name
    #         or raise OpTestError if not able to get list of i2c buses
    #
    def host_get_list_of_i2c_buses(self):
        l_res = self.host_run_command("i2cdetect -l;echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            pass
        else:
            l_msg = "Not able to get list of i2c buses"
            print l_msg
            raise OpTestError(l_msg)
        l_res = self.host_run_command("i2cdetect -l | awk '{print $1}'")
        l_res = l_res.splitlines()
        # list by number Ex: ["0","1","2",....]
        l_list = []
        # list by name Ex: ["i2c-0","i2c-1"...]
        l_list1 = []
        for l_bus in l_res:
            matchObj = re.search("(i2c)-(\d{1,})", l_bus)
            if matchObj:
                l_list.append(matchObj.group(2))
                l_list1.append(l_bus)
            else:
                pass
        return l_list, l_list1

    ##
    # @brief This function will get information of EEPROM chips attached to the i2c buses
    #
    # @return l_res @type string: return EEPROM chips information
    #           else raise OpTestError
    #
    def host_get_info_of_eeprom_chips(self):
        print "Getting the information of EEPROM chips"
        l_res = self.host_run_command("dmesg | grep -i --color=never at24")
        if l_res.__contains__("at24"):
            pass
        else:
            l_res = self.host_run_command("dmesg -C")
            self.host_run_command("rmmod at24")
            self.host_load_module("at24")
            l_res = self.host_run_command("dmesg | grep -i --color=never at24")
            if l_res.__contains__("at24"):
                pass
            else:
                return None
        return l_res

    ##
    # @brief It will return list with elements having pairs of eeprom chip addresses and
    #        corresponding i2c bus where the chip is attached. This information is getting
    #        through sysfs interface. format is ["0 0x50","0 0x51","1 0x51","1 0x52"....]
    #
    # @return l_chips @type list: list having pairs of i2c bus number and eeprom chip address.
    #           else raise OpTestError
    #
    def host_get_list_of_eeprom_chips(self):
        l_res = self.host_run_command("find /sys/ -name eeprom;echo $?")
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            pass
        else:
            return None
        l_chips = []
        for l_line in l_res:
            if l_line.__contains__("eeprom"):
                matchObj = re.search("/(\d{1,}-\d{4})/eeprom", l_line)
                if matchObj:
                    l_line = matchObj.group(1)
                    i_args = (l_line.replace("-", " "))
                    print i_args
                else:
                    continue
                i_args = re.sub(" 00", " 0x", i_args)
                l_chips.append(i_args)
                print i_args
        return l_chips

    ##
    # @brief The hexdump utility is used to display the specified files.
    #        This function will display in both ASCII+hexadecimal format.
    #
    # @param i_dev @type string: this is the file used as a input to hexdump for display info
    #                            Example file:"/sys/devices/platform/3fc0000000000.xscom:i2cm@a0000:i2c-bus@1/i2c-3/3-0050/eeprom"
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    #
    def host_hexdump(self, i_dev):
        l_res = self.host_run_command("hexdump -C %s;echo $?" % i_dev)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "hexdump failed for device %s" % i_dev
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief It will clone latest skiboot git repository in i_dir directory
    #
    # @param i_dir @type string: directory where skiboot source will be cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_clone_skiboot_source(self, i_dir):
        l_msg = 'https://github.com/open-power/skiboot.git/'
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.host_run_command("git config --global http.sslverify false")
        self.host_run_command("rm -rf %s" % i_dir)
        self.host_run_command("mkdir %s" % i_dir)
        try:
            print l_cmd
            l_res = self.host_run_command(l_cmd)
            print l_res
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning skiboot git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief It will compile xscom-utils in the skiboot directory which was cloned in i_dir directory
    #
    # @param i_dir @type string: directory where skiboot source was cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_compile_xscom_utilities(self, i_dir):
        l_cmd = "cd %s/external/xscom-utils; make;" % i_dir
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_cmd = "test -f %s/external/xscom-utils/getscom; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary getscom is available"
        else:
            l_msg = "getscom bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "test -f %s/external/xscom-utils/putscom; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary putscom is available"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "putscom bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief It will compile gard utility in the skiboot directory which was cloned in i_dir directory
    #
    # @param i_dir @type string: directory where skiboot source was cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_compile_gard_utility(self, i_dir):
        l_cmd = "cd %s/external/gard; make;" % i_dir
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_cmd = "test -f %s/external/gard/gard; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary gard is available"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "gard bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function generates olog.json file from skiboot which is used for
    #        fwts olog test: Run OLOG scan and analysis checks.
    #
    # @param i_dir @type string: directory where skiboot source was cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_generate_fwts_olog_json(self, i_dir):
        l_cmd = "%s/external/fwts/generate-fwts-olog %s/ -o %s/olog.json" % (i_dir, i_dir, i_dir)
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_cmd = "test -f %s/olog.json; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "olog.json is available in working directory %s" % i_dir
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "olog.json file is failed to create from skiboot"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief It will clone latest fwts git repository in i_dir directory
    #
    # @param i_dir @type string: directory where fwts source will be cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_clone_fwts_source(self, i_dir):
        l_msg = 'git://kernel.ubuntu.com/hwe/fwts.git'
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.host_run_command("git config --global http.sslverify false")
        self.host_run_command("rm -rf %s" % i_dir)
        self.host_run_command("mkdir %s" % i_dir)
        try:
            print l_cmd
            l_res = self.host_run_command(l_cmd)
            print l_res
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning fwts git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to build fwts tool in the fwts directory
    #        which was cloned in i_dir directory
    #
    # @param i_dir @type string: directory where fwts source was cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_build_fwts_tool(self, i_dir):
        l_cmd = "cd %s/;autoreconf -ivf;./configure; make;" % i_dir
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_cmd = "test -f %s/src/fwts; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        print l_res
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary fwts is available"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "fwts bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief This function is used to get detected pci devices in different user/machine readable formats
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_list_pci_devices(self):
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES1)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES2)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES3)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES4)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES5)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_DEVICES6)
        self.host_run_command(BMC_CONST.HOST_LIST_PCI_SYSFS_DEVICES)

    ##
    # @brief This function is used to get more pci devices info in verbose mode
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_get_pci_verbose_info(self):
        l_res = self.host_run_command(BMC_CONST.HOST_LIST_PCI_VERBOSE)
        return l_res

    ##
    # @brief This function is used to get minimum usb devices info
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_list_usb_devices(self):
        self.host_run_command(BMC_CONST.HOST_LIST_USB_DEVICES1)
        self.host_run_command(BMC_CONST.HOST_LIST_USB_DEVICES2)
        self.host_run_command(BMC_CONST.HOST_LIST_USB_DEVICES3)

    ##
    # @brief This function enable only a single core
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_enable_single_core(self):
        self.host_run_command("ppc64_cpu --cores-on=1")

    ##
    # @brief This function is used to get list of PCI PHB domains.
    #
    # @return self.pci_domains list of PHB domains @type list or raise OpTestError
    #
    def host_get_list_of_pci_domains(self):
        self.pci_domains = []
        self.host_run_command("lspci -mm")
        res = self.host_run_command('lspci -mm | cut -d":" -f1 | sort | uniq')
        res = res.splitlines()
        for domain in res:
            if not domain:
                continue
            if len(domain) != 4:
                domain = ''.join(("00", domain))
            domain = 'PCI' + domain
            if not self.pci_domains.__contains__(domain):
                self.pci_domains.append(domain)
        print self.pci_domains
        return self.pci_domains

    ##
    # @brief This function is used to get the PHB domain of root port where
    #        the filesystem is mounted(We need to skip this in EEH tests as recovery
    #        will fail on this domain is expected)
    #
    # @return boot_domain root PHB @type string or raise OpTestError
    #
    def host_get_root_phb(self):
        cmd = "df -h /boot | awk 'END {print $1}'"
        res = self.host_run_command(cmd)
        boot_disk = res.split("/dev/")[1]
        boot_disk = boot_disk.replace("\r\n", "")
        cmd  = "ls -l /dev/disk/by-path/ | grep %s | awk '{print $(NF-2)}'" % boot_disk
        res = self.host_run_command(cmd)
        matchObj = re.search(r"\d{4}(?!\d)", res, re.S)
        if not matchObj:
            raise OpTestError("Not able to find out root phb domain")
        boot_domain = 'PCI' + matchObj.group(0)
        return  boot_domain

    ##
    # @brief It will gather kernel dmesg logs and store the copy in a logfile
    #        which will be stored in results dir.
    #
    # @return BMC_CONST.FW_SUCCESS  or raise OpTestError
    #
    def host_gather_kernel_log(self):
        try:
            l_data = self.host_run_command("dmesg")
        except OpTestError:
            l_msg = "Failed to gather kernel dmesg log"
            raise OpTestError(l_msg)
        if not self.results_dir:
            print l_data
            return
        l_res = (time.asctime(time.localtime())).replace(" ", "_")
        l_logFile = "Kernel_dmesg_log_%s.log" % l_res
        fn = os.path.join(self.results_dir, l_logFile)
        print fn
        with open(fn, 'w') as f:
            f.write(l_data)
        return BMC_CONST.FW_SUCCESS

    ##
    # @brief This function starts opal_errd daemon
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_start_opal_errd_daemon(self):
        self.host_run_command("systemctl start opal_errd")

    ##
    # @brief This function stops opal_errd daemon
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_stop_opal_errd_daemon(self):
        self.host_run_command("systemctl stop opal_errd")

    ##
    # @brief This function gets the status of opal_errd daemon
    #
    # @return True/False: if opal_errd run/not run or throws exception
    #                     if not able to get status
    #
    def host_get_status_of_opal_errd_daemon(self):
        res = self.host_run_command("ps -ef | grep -v grep | grep opal_errd | wc -l")
        print res
        if res.strip() == "0":
            print "Opal_errd daemon is not running"
            return False
        elif res.strip() == "1":
            print "Opal_errd daemon is running"
            return True
        else:
            raise OpTestError("Not able to get status of opal errd daemon")

    ##
    # @brief This function lists all error logs in host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_list_all_errorlogs(self):
        self.host_run_command("opal-elog-parse -l")


    ##
    # @brief This function lists all service action logs in host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_list_all_service_action_logs(self):
        self.host_run_command("opal-elog-parse -s")

    ##
    # @brief This function gets the number of error logs
    #
    # @return res or raise OpTestError
    #
    def host_get_number_of_errorlogs(self):
        res = self.host_run_command("ls %s | wc -l" % BMC_CONST.OPAL_ELOG_DIR)
        print res
        return res

    ##
    # @brief This function clears/acknowledges all error logs in host
    #
    # @return True on success or raise OpTestError
    #
    def host_clear_error_logs(self):
        self.host_run_command("rm -f %s/*" % BMC_CONST.OPAL_ELOG_DIR)
        res = self.host_run_command("ls %s -1 --color=never" % BMC_CONST.OPAL_ELOG_SYSFS_DIR)
        print res
        res = res.splitlines()
        for entry in res:
            entry = entry.strip()
            if entry == '':
                continue
            self.host_run_command("echo 1 > %s/%s/acknowledge" % (BMC_CONST.OPAL_ELOG_SYSFS_DIR, entry))
        return True
    ##
    # @brief This function clears/acknowledges all dumps in host
    #
    # @return True on success or raise OpTestError
    #
    def host_clear_all_dumps(self):
        self.host_run_command("rm -f %s/*" % BMC_CONST.OPAL_DUMP_DIR)
        res = self.host_run_command("ls %s -1 --color=never" % BMC_CONST.OPAL_DUMP_SYSFS_DIR)
        res = res.splitlines()
        for entry in res:
            entry = entry.strip()
            if (entry == "initiate_dump") or (entry == ''):
                continue
            else:
                self.host_run_command("echo 1 > %s/%s/acknowledge" % (BMC_CONST.OPAL_DUMP_SYSFS_DIR, entry))
        return True

    # @brief This function disables kdump service
    #
    # @param os_level: string output of /etc/os-release
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_disable_kdump_service(self, os_level):
        if "Ubuntu" in os_level:
            self.host_run_command("systemctl stop kdump-tools.service")
            self.host_run_command("systemctl status kdump-tools.service")
        else:
            self.host_run_command("systemctl stop kdump.service")
            self.host_run_command("systemctl status kdump.service")

    ##
    # @brief This function disables kdump service
    #
    # @param os_level: string output of /etc/os-release
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_enable_kdump_service(self, os_level):
        if "Ubuntu" in os_level:
            self.host_run_command("systemctl stop kdump-tools.service")
            self.host_run_command("systemctl start kdump-tools.service")
            self.host_run_command("systemctl status kdump-tools.service")
        else:
            self.host_run_command("systemctl stop kdump.service")
            self.host_run_command("systemctl start kdump.service")
            self.host_run_command("service status kdump.service")

