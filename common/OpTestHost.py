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


    ##
    #   @brief This method executes the command(i_cmd) on the host using a ssh session
    #
    #   @param i_cmd: @type string: Command to be executed on host through a ssh session
    #   @return command output if command execution is successful else raises OpTestError
    #
    def _ssh_execute(self, i_cmd):

        l_host = self.ip
        l_user = self.user
        l_pwd = self.passwd

        l_output = ''
        ssh_ver = '-2'

        # Flush everything out prior to forking
        sys.stdout.flush()

        # Connect the child controlling terminal to a pseudo-terminal
        try:
            pid, fd = pty.fork()
        except OSError as e:
                # Explicit chain of errors
            l_msg = "Got OSError attempting to fork a pty session for ssh."
            raise OpTestError(l_msg)

        if pid == 0:
            # In child process.  Issue attempt ssh connection to remote host

            arglist = ('/usr/bin/ssh -o StrictHostKeyChecking=no',
                       l_host, ssh_ver, '-k', '-l', l_user, i_cmd)

            try:
                os.execv('/usr/bin/ssh', arglist)
            except Exception as e:
                # Explicit chain of errors
                l_msg = "Can not spawn os.execv for ssh."
                print l_msg
                raise OpTestError(l_msg)

        else:
            # In parent process
            # Polling child process for output
            poll = select.poll()
            poll.register(fd, select.POLLIN)

            start_time = time.time()
            # time.sleep(1)
            while True:
                try:
                    evt = poll.poll()
                    x = os.read(fd, 1024)
                    #print "ssh x= " + x
                    end_time = time.time()
                    if(end_time - start_time > 1500):
                        if(i_cmd.__contains__('updlic') or i_cmd.__contains__('update_flash')):
                            continue
                        else:
                            l_msg = "Timeout occured/SSH request " \
                                    "un-responded even after 25 minutes"
                            print l_msg
                            raise OpTestError(l_msg)

                    if(x.__contains__('(yes/no)')):
                        l_res = "yes\r\n"
                        os.write(fd, l_res)
                    if(x.__contains__('s password:')):
                        x = ''
                        os.write(fd, l_pwd + '\r\n')
                    if(x.__contains__('Password:')):
                        x = ''
                        os.write(fd, l_pwd + '\r\n')
                    if(x.__contains__('password')):
                        response = l_pwd + "\r\n"
                        os.write(fd, response)
                    if(x.__contains__('yes')):
                        response = '1' + "\r\n"
                        os.write(fd, response)
                    if(x.__contains__('Connection refused')):
                        print x
                        raise OpTestError(x)
                    if(x.__contains__('Received disconnect from')):
                        self.ssh_ver = '-1'
                    if(x.__contains__('Connection closed by')):
                        print (x)
                        raise OpTestError(x)
                    if(x.__contains__("WARNING: POSSIBLE DNS SPOOFING DETECTED")):
                        print (x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED")):
                        print (x)
                        raise OpTestError("Its a RSA key problem : \n" + x)
                    if(x.__contains__("Permission denied")):
                        l_msg = "Wrong Login or Password(" + l_user + "/" + l_pwd + ") :" + x
                        print (l_msg)
                        raise OpTestError(l_msg)
                    if(x.__contains__("Rebooting") or \
                       (x.__contains__("rebooting the system"))):
                        l_output = l_output + x
                        raise OpTestError(l_output)
                    if(x.__contains__("Connection timed out")):
                        l_msg = "Connection timed out/" + \
                            l_host + " is not pingable"
                        print (x)
                        raise OpTestError(l_msg)
                    if(x.__contains__("could not connect to CLI daemon")):
                        print(x)
                        raise OpTestError("Director server is not up/running("
                                          "Do smstop then smstart to restart)")
                    if((x.__contains__("Error:")) and (i_cmd.__contains__('rmsys'))):
                        print(x)
                        raise OpTestError("Error removing:" + l_host)
                    if((x.__contains__("Bad owner or permissions on /root/.ssh/config"))):
                        print(x)
                        raise OpTestError("Bad owner or permissions on /root/.ssh/config,"
                                          "Try 'chmod -R 600 /root/.ssh' & retry operation")

                    l_output = l_output + x
                    # time.sleep(1)
                except OSError:
                    break
        if l_output.__contains__("Name or service not known"):
            reason = 'SSH Failed for :' + l_host + \
                "\n Please provide a valid Hostname"
            print reason
            raise OpTestError(reason)

        # Gather child process status to freeup zombie and
        # Close child file descriptor before return
        if (fd):
            os.waitpid(pid, 0)
            os.close(fd)
        return l_output

    ##
    # @brief Get and Record Ubunto OS level
    #
    # @return l_oslevel @type string: OS level of the host provided
    #         or raise OpTestError
    #
    def host_get_OS_Level(self):

        l_oslevel = self._ssh_execute(BMC_CONST.BMC_GET_OS_RELEASE)
        print l_oslevel
        return l_oslevel


    ##
    # @brief Executes a command on the os of the bmc to protect network setting
    #
    # @return OpTestError if failed
    #
    def host_protect_network_setting(self):
        try:
            l_rc = self._ssh_execute(BMC_CONST.OS_PRESERVE_NETWORK)
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
        l_rc = self._ssh_execute(BMC_CONST.HOST_COLD_RESET)

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
            l_rc = self._ssh_execute(l_cmd)
            print l_rc
            self._ssh_execute("rm -rf /tmp/" + i_image.rsplit("/", 1)[1])
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

    ##
    # @brief It will run linux command(i_cmd) on host using private interface _ssh_execute()
    #        making this interface is public
    #
    # @param i_cmd @type string: linux command
    #
    # @return command output if command execution is successful else raises OpTestError
    #
    def host_run_command(self, i_cmd):
        try:
            l_res = self._ssh_execute(i_cmd)
        except:
            l_msg = "Command execution on host failed"
            print l_msg
            print sys.exc_info()
            raise OpTestError(l_msg)
        print l_res
        return l_res

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

        l_res = commands.getstatusoutput("date +%Y%m%d_%H%M")
        l_logFile = "Opal_msglog_%s.log" % l_res[1]
        fn = self.cv_ffdcDir + "/" + l_logFile
        with open(fn, 'w') as f:
            f.write(l_data)
        return BMC_CONST.FW_SUCCESS

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
        l_kernel = self._ssh_execute("uname -a | awk {'print $3'}")
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
        l_res = self._ssh_execute("test -e %s; echo $?" % l_file)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Config file is available"
        else:
            l_msg = "Config file %s is not available on host" % l_file
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "cat %s | grep -i -w --color=never %s" % (l_file, i_config)
        print l_cmd
        l_res = self._ssh_execute(l_cmd)
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
            l_res = self._ssh_execute("dpkg -S `which %s`" % i_cmd)
            return l_res
        else:
            l_cmd = "rpm -qf `which %s`" % i_cmd
            l_res = self._ssh_execute(l_cmd)
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
            l_rc = self._ssh_execute("modprobe ibmpowernv; echo $?")
            l_rc = l_rc.replace("\r\n", "")
            if int(l_rc) == 0:
                cmd = "lsmod | grep -i ibmpowernv"
                response = self._ssh_execute(cmd)
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
        self._ssh_execute("rm -rf %s" % i_dir)
        self._ssh_execute("mkdir %s" % i_dir)
        try:
            print l_cmd
            res = self._ssh_execute(l_cmd)
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
            return self._ssh_execute(BMC_CONST.OS_READ_MSGLOG_CORE)
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
            l_rc = self._ssh_execute(BMC_CONST.SUDO_COMMAND + i_xscom_dir + BMC_CONST.OS_GETSCOM_LIST)
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

        l_rc = self._ssh_execute(BMC_CONST.SUDO_COMMAND + i_gard_dir + BMC_CONST.CLEAR_GARD_CMD)

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
            return self._ssh_execute(BMC_CONST.SUDO_COMMAND + i_gard_dir + BMC_CONST.LIST_GARD_CMD)
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
            self._ssh_execute(BMC_CONST.SUDO_COMMAND + "sh -c 'for i in " + \
                              BMC_CONST.CPU_IDLEMODE_STATE1 + "; do echo " + \
                              i_cpu_state  + " > $i; done'")
            self._ssh_execute(BMC_CONST.SUDO_COMMAND + "sh -c 'for i in " + \
                              BMC_CONST.CPU_IDLEMODE_STATE2 + "; do echo " + \
                              i_cpu_state  + " > $i; done'")
            return BMC_CONST.FW_SUCCESS
        except:
            l_errmsg = "Could not enable/disable cpu idle states"
            print l_errmsg
            raise OpTestError(l_errmsg)

    ##
    # @brief It will get the linux kernel version on host
    #
    # @return l_kernel @type string: kernel version of the host provided
    #         or raise OpTestError
    #
    def host_get_kernel_version(self):
        l_kernel = self._ssh_execute("uname -a | awk {'print $3'}")
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
        l_res = self._ssh_execute("test -e %s; echo $?" % l_file)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Config file is available"
        else:
            l_msg = "Config file %s is not available on host" % l_file
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "cat %s | grep -i -w --color=never %s" % (l_file, i_config)
        print l_cmd
        l_res = self._ssh_execute(l_cmd)
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
            l_res = self._ssh_execute("dpkg -S `which %s`" % i_cmd)
            return l_res
        else:
            l_cmd = "rpm -qf `which %s`" % i_cmd
            l_res = self._ssh_execute(l_cmd)
            l_pkg = l_res.replace("\r\n", "")
            print l_pkg
            return l_pkg

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
            l_rc = self._ssh_execute("modprobe ibmpowernv; echo $?")
            l_rc = l_rc.replace("\r\n", "")
            if int(l_rc) == 0:
                cmd = "lsmod | grep -i ibmpowernv"
                response = self._ssh_execute(cmd)
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
        self._ssh_execute("rm -rf %s" % i_dir)
        self._ssh_execute("mkdir %s" % i_dir)
        try:
            print l_cmd
            res = self._ssh_execute(l_cmd)
            print res
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning linux git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

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
                l_msg = "Not able to get at24 info"
                raise OpTestError(l_msg)
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
            l_msg = "Not able to get list of eeprom chip addresses through sysfs interface"
            print l_msg
            raise OpTestError(l_msg)
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
    # @brief Check that host has a CAPI FPGA card
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_has_capi_fpga_card(self):
        l_cmd = "lspci -d \"1014:0477\""
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        print l_res
        if (l_res.__contains__('IBM Device 0477')):
            l_msg = "Host has a CAPI FPGA card"
            print l_msg
        else:
            l_msg = "Host has no CAPI FPGA card"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Clone latest cxl-tests git repository in i_dir directory
    #
    # @param i_dir @type string: directory where cxl-tests will be cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_clone_cxl_tests(self, i_dir):
        l_msg = "https://github.com/ibm-capi/cxl-tests.git"
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
            l_msg = "Cloning cxl-tests git repository is failed"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Build cxl-tests (and libcxl) in the cxl-test directory which was cloned in i_dir directory
    #
    # @param i_dir @type string: directory where cxl-tests source was cloned
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_build_cxl_tests(self, i_dir):
        l_cmd = "cd %s; make" % i_dir
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_cmd = "test -x %s/libcxl/libcxl.so; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable library libcxl.so is available"
        else:
            l_msg = "libcxl.so lib file is not present after make"
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "test -x %s/libcxl_tests; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary libcxl_tests is available"
        else:
            l_msg = "libcxl_tests bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)
        l_cmd = "test -x %s/memcpy_afu_ctx; echo $?" % i_dir
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.replace("\r\n", "")
        if int(l_res) == 0:
            print "Executable binary memcpy_afu_ctx is available"
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "memcpy_afu_ctx bin file is not present after make"
            print l_msg
            raise OpTestError(l_msg)

    ##
    # @brief Check that an executable file is available on host
    #
    # @param i_dir @type string: directory that contains the binary file
    #
    # @param i_file @type string: binary file name
    #
    # @return True or False
    #
    def host_check_binary(self, i_dir, i_file):
        l_cmd = "test -x %s/%s; echo $?" % (i_dir, i_file)
        print l_cmd
        l_res = self.host_run_command(l_cmd)
        l_res = l_res.splitlines()
        if int(l_res[-1]) == 0:
            l_msg = "Executable file %s/%s is available" % (i_dir, i_file)
            print l_msg
            return True

        l_msg = "Executable file %s/%s is not present" % (i_dir, i_file)
        print l_msg
        return False

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
