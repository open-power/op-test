#!/usr/bin/python2
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

from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestUtil import OpTestUtil
from OpTestSSH import OpTestSSH
from Exceptions import CommandFailed, NoKernelConfig, KernelModuleNotLoaded, KernelConfigNotSet

class OpTestHost():

    ##
    # @brief Initialize this object
    #
    # @param i_hostip @type string: IP Address of the host
    # @param i_hostuser @type string: Userid to log into the host
    # @param i_hostpasswd @type string: Password of the userid to log into the host
    # @param i_bmcip @type string: IP Address of the bmc
    #
    def __init__(self, i_hostip, i_hostuser, i_hostpasswd, i_bmcip, i_results_dir,
                 scratch_disk="", proxy="", logfile=sys.stdout,
                 check_ssh_keys=False, known_hosts_file=None):
        self.ip = i_hostip
        self.user = i_hostuser
        self.passwd = i_hostpasswd
        self.util = OpTestUtil()
        self.bmcip = i_bmcip
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        self.results_dir = i_results_dir
        self.logfile = logfile
        self.ssh = OpTestSSH(i_hostip, i_hostuser, i_hostpasswd,
                logfile=self.logfile, check_ssh_keys=check_ssh_keys,
                known_hosts_file=known_hosts_file, use_default_bash=True)
        self.scratch_disk = scratch_disk
        self.proxy = proxy
        self.scratch_disk_size = None

    def hostname(self):
        return self.ip

    def username(self):
        return self.user

    def password(self):
        return self.passwd


    def get_scratch_disk(self):
        return self.scratch_disk

    def get_scratch_disk_size(self, console=None):
        if self.scratch_disk_size is not None:
            return self.scratch_disk_size
        if console is None:
            raise Exception("You need to call get_scratch_disk_size() with a console first")
        console.run_command("stty cols 300")
        dev_sdX = console.run_command("readlink -f %s" % self.get_scratch_disk())
        dev_sdX = dev_sdX[0].replace("/dev/","")
        scratch_disk_size = console.run_command("cat /sys/block/%s/size" % dev_sdX)
        # Use the (undocumented) /size sysfs property of nr 512byte sectors
        self.scratch_disk_size = int(scratch_disk_size[0])*512


    def get_proxy(self):
        return self.proxy

    def get_ssh_connection(self):
        return self.ssh

    ##
    # @brief Get and Record Ubunto OS level
    #
    # @return l_oslevel @type string: OS level of the host provided
    #         or raise OpTestError
    #
    def host_get_OS_Level(self):
        l_oslevel = self.ssh.run_command("cat /etc/os-release", timeout=60)
        return '\n'.join(l_oslevel)


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
    #
    # @return BMC_CONST.FW_SUCCESS  or raise OpTestError
    #
    def host_gather_opal_msg_log(self):
        try:
            l_data = '\n'.join(self.host_run_command(BMC_CONST.OPAL_MSG_LOG))
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
        l_cmd = 'which ' + ' '.join(i_cmd)
        print l_cmd
        try:
            l_res = self.host_run_command(l_cmd)
        except CommandFailed as c:
            l_msg = "host_check_command: (%s) not present on host. output of '%s': %s" % (','.join(i_cmd), l_cmd, '\n'.join(c.output))
            print l_msg
            raise OpTestError(l_msg)

        return True

    ##
    # @brief It will get the linux kernel version on host
    #
    # @return l_kernel @type string: kernel version of the host provided
    #         or raise OpTestError
    #
    def host_get_kernel_version(self):
        l_kernel = self.ssh.run_command("uname -a | awk {'print $3'}", timeout=60)
        l_kernel = ''.join(l_kernel)
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
        try:
            l_res = self.ssh.run_command("test -e %s" % l_file, timeout=60)
        except CommandFailed as c:
            raise NoKernelConfig(i_kernel, l_file)

        print "Config file is available"
        l_cmd = "cat %s" % (l_file)
        l_res = self.ssh.run_command(l_cmd, timeout=60)
        config_opts = {}
        for o in l_res:
            m = re.match('# (.*) is not set', o)
            if m:
                config_opts[m.group(0)]='n'
            else:
                if '=' in o:
                    opt, val = o.split("=")
                    config_opts[opt] = val

        if config_opts.get(i_config) not in ["y","m"]:
                raise KernelConfigNotSet(i_config)

        return config_opts[i_config]

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
            return ''.join(self.ssh.run_command("dpkg -S `which %s`" % i_cmd, timeout=60))
        else:
            l_cmd = "rpm -qf `which %s`" % i_cmd
            return ''.join(self.ssh.run_command(l_cmd, timeout=60))

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
            o = self.ssh.run_command("modprobe ibmpowernv",timeout=60)
            cmd = "lsmod | grep -i ibmpowernv"
            response = self.ssh.run_command(cmd, timeout=60)
            if "ibmpowernv" not in ''.join(response):
                l_msg = "ibmpowernv module is not loaded, exiting"
                raise OpTestError(l_msg)
            else:
                print "ibmpowernv module is loaded"
            print cmd
            print response
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
        l_cmd = "git clone --depth=1 %s %s" % (l_msg, i_dir)
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
        l_rc = self.ssh.run_command_ignore_fail(BMC_CONST.SUDO_COMMAND + i_xscom_dir + BMC_CONST.OS_PUTSCOM_ERROR + i_error)

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
    # @brief It will load the module using modprobe and verify whether it is loaded or not
    #
    # @param i_module @type string: module name, which we want to load on host
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_load_module(self, i_module):
        try:
            l_res = self.host_run_command("modprobe %s" % i_module)
        except CommandFailed as c:
            l_msg = "Error in loading the module %s, modprobe failed: %s" % (i_module,str(c))
            raise OpTestError(l_msg)
        l_res = self.host_run_command("lsmod | grep -i --color=never %s" % i_module)
        if re.search(i_module, ''.join(l_res)):
            print "%s module is loaded" % i_module
            return BMC_CONST.FW_SUCCESS
        else:
            raise KernelModuleNotLoaded(i_module)

    ##
    # @brief This function will read real time clock(RTC) time using hwclock utility
    #
    # @return l_res @type string: return hwclock value if command execution successfull
    #           else raise OpTestError
    #
    def host_read_hwclock(self):
        print "Reading the hwclock"
        self.host_run_command("hwclock -r;echo $?")

    ##
    # @brief This function will read system time using date utility (This will be mantained by kernel)
    #
    # @return l_res @type string: return system time value if command execution successfull
    #           else raise OpTestError
    #
    def host_read_systime(self):
        print "Reading system time using date utility"
        l_res = self.host_run_command("date")
        return l_res

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
        self.host_run_command("hwclock --set --date \'%s\'" % i_time)

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
        elif l_val == 'n':
            raise KernelConfigNotSet(i_config)


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
        boot_disk = ''.join(res).split("/dev/")[1]
        boot_disk = boot_disk.replace("\r\n", "")
        cmd  = "ls -l /dev/disk/by-path/ | grep %s | awk '{print $(NF-2)}'" % boot_disk
        res = self.host_run_command(cmd)
        matchObj = re.search(r"\d{4}(?!\d)", '\n'.join(res), re.S)
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
            l_data = '\n'.join(self.host_run_command("dmesg"))
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
        if res[0].strip() == "0":
            print "Opal_errd daemon is not running"
            return False
        elif res[0].strip() == "1":
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
        print '\n'.join(res)
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
            try:
                self.host_run_command("systemctl status kdump-tools.service")
            except CommandFailed as cf:
                if cf.exitcode == 3:
                    pass
                else:
                    print str(cf)
                    raise OpTestError("kdump-tools service is failed to stop")
        else:
            self.host_run_command("systemctl stop kdump.service")
            try:
                self.host_run_command("systemctl status kdump.service")
            except CommandFailed as cf:
                if cf.exitcode == 3:
                    pass
                else:
                    print str(cf)
                    raise OpTestError("kdump service is failed to stop")

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
            self.host_run_command("systemctl status kdump.service")

    def host_check_sysfs_path_availability(self, path):
        res = self.host_run_command("ls %s" % path)
        if "No such file or directory" in res:
            return False
        return True

    def host_check_dt_node_exist(self, node_path):
        path = "/proc/device-tree/" + node_path
        res = self.host_run_command("ls %s" % path)
        if "No such file or directory" in res:
            return False
        return True

    def host_get_list_of_chips(self):
        res = self.host_run_command("PATH=/usr/local/sbin:$PATH getscom -l")
        chips = []
        for line in res:
            matchObj = re.search("(\d{8}).*processor", line)
            if matchObj:
                chips.append(matchObj.group(1))
        if not chips:
            raise Exception("Getscom failed to list processor chip ids")
        chips.sort()
        print chips # ['00000000', '00000001', '00000010']
        return chips

    def host_get_cores(self):
        proc_gen = self.host_get_proc_gen()
        core_ids = {}
        cpu_files = self.host_run_command("find /sys/devices/system/cpu/ -name 'cpu[0-9]*'")
        for cpu_file in cpu_files:
            cpu_id = self.host_run_command("basename %s | tr -dc '0-9'" % cpu_file)[-1]
            try:
                pir = self.host_run_command("cat %s/pir" % cpu_file)[-1]
            except CommandFailed:
                continue
            if proc_gen in ["POWER8", "POWER8E"]:
                core_id = hex((int("0x%s" % pir, 16) >> 3 ) & 0xf)
                chip_id = hex((int("0x%s" % pir, 16) >> 7 ) & 0x3f)
            elif proc_gen in ["POWER9"]:
                core_id =hex((int("0x%s" % pir, 16) >> 2 ) & 0x3f)
                chip_id = hex((int("0x%s" % pir, 16) >> 8 ) & 0x7f)
            else:
                raise OpTestError("Unknown or new processor type")
            core_id = core_id.split('x')[1]
            chip_id = chip_id.split('x')[1]

            if chip_id in core_ids:
                core_ids[chip_id].append(core_id)
            else:
                core_ids[chip_id] = [core_id]

        for i in core_ids:
            core_ids[i] = list(set(core_ids[i]))
        core_ids = sorted(core_ids.iteritems())
        print core_ids
        return core_ids

    # Supported on OpenPower and P9 FSP system
    def host_prd_supported(self, bmc_type):
        if not "FSP" in bmc_type:
            return True

        proc_gen = self.host_get_proc_gen()
        if proc_gen in ["POWER8", "POWER8E"]:
            return False

        return True

    def host_get_proc_gen(self):
        try:
            if self.proc_gen:
                pass
        except AttributeError:
            self.proc_gen = ''.join(self.host_run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'"))
        return self.proc_gen

    def host_get_smt(self):
        self.cpu = self.host_get_proc_gen()
        if self.cpu in ["POWER8", "POWER8E"]:
            return 8
        elif self.cpu in ["POWER9"]:
            return 4
        else:
            return 1

    def host_get_core_count(self):
        res = self.host_run_command("lscpu --all -e| wc -l")
        return int(res[0])/(self.host_get_smt())

    def host_gather_debug_logs(self):
        self.ssh.run_command_ignore_fail("grep ',[0-4]\]' /sys/firmware/opal/msglog")
        self.ssh.run_command_ignore_fail("dmesg -T --level=alert,crit,err,warn")

    def host_copy_fake_gard(self):
        path = os.path.abspath(os.path.join("common", os.pardir))
        i_image = path + "/test_binaries/fake.gard"
        # Copy the fake.gard file to the tmp folder in the host
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying fake.gard file to host failed"
            print l_msg
            raise OpTestError(l_msg)

    def host_pflash_get_partition(self, partition):
        d = self.host_run_command("pflash --info")
        for line in d:
            s = re.search(partition, line)
            if s:
                m = re.match(r'ID=\d+\s+\S+\s+((0[xX])?[0-9a-fA-F]+)..(0[xX])?[0-9a-fA-F]+\s+\(actual=((0[xX])?[0-9a-fA-F]+)\).*', line)
                offset = int(m.group(1), 16)
                length = int(m.group(4), 16)
                ret = {'offset': offset, 'length': length}
        return ret

    ##
    # @brief Check that host has a CAPI FPGA card
    #
    # @return True or False
    #
    def host_has_capi_fpga_card(self):
        l_cmd = "lspci -d \"1014:0477\""
        l_res = self.host_run_command(l_cmd)
        l_res = " ".join(l_res)
        if (l_res.__contains__('IBM Device 0477')):
            l_msg = "Host has a CAPI FPGA card"
            print l_msg
            return True
        else:
            l_msg = "Host has no CAPI FPGA card; skipping test"
            print l_msg
            return False

    ##
    # @brief Clone latest cxl-tests git repository in i_dir directory
    #
    # @param i_dir @type string: directory where cxl-tests will be cloned
    #
    # @return True or False
    #
    def host_clone_cxl_tests(self, i_dir):
        l_msg = "https://github.com/ibm-capi/cxl-tests.git"
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.host_run_command("git config --global http.sslverify false")
        self.host_run_command("rm -rf %s" % i_dir)
        self.host_run_command("mkdir %s" % i_dir)
        try:
            l_res = self.host_run_command(l_cmd)
            return True
        except:
            l_msg = "Cloning cxl-tests git repository is failed"
            return False

    def host_build_cxl_tests(self, i_dir):
        l_cmd = "cd %s; make" % i_dir
        self.host_run_command(l_cmd)
        l_cmd = "test -x %s/libcxl/libcxl.so" % i_dir
        self.host_run_command(l_cmd)
        l_cmd = "test -x %s/libcxl_tests; echo $?" % i_dir
        self.host_run_command(l_cmd)
        l_cmd = "test -x %s/memcpy_afu_ctx; echo $?" % i_dir
        self.host_run_command(l_cmd)

    def host_check_binary(self, i_dir, i_file):
        l_cmd = "test -x %s/%s;" % (i_dir, i_file)
        try:
            self.host_run_command(l_cmd)
            l_msg = "Executable file %s/%s is available" % (i_dir, i_file)
            print l_msg
            return True
        except CommandFailed:
            l_msg = "Executable file %s/%s is not present" % (i_dir, i_file)
            print l_msg
            return False
