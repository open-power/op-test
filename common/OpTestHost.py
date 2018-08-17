#!/usr/bin/env python2
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

'''
Host package which contains all functions related to HOST communication

This class encapsulates all function which deals with the Host
in OpenPower systems
'''

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

import OpTestConfiguration
from OpTestConstants import OpTestConstants as BMC_CONST
from OpTestError import OpTestError
from OpTestUtil import OpTestUtil
from OpTestSSH import OpTestSSH
import OpTestQemu
from Exceptions import CommandFailed, NoKernelConfig, KernelModuleNotLoaded, KernelConfigNotSet, ParameterCheck

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestHost():
    '''
    An object to manipulate and run things on the host.
    '''
    def __init__(self, i_hostip, i_hostuser, i_hostpasswd, i_bmcip, i_results_dir,
                 scratch_disk="", proxy="", logfile=sys.stdout,
                 check_ssh_keys=False, known_hosts_file=None):
        # testcases.HelloWorld fails with these runtime checks
#        if i_bmcip is None:
#          raise ParameterCheck(msg="OpTestHost __init__ passed i_bmcip as None, this doesn't seem right, check your configuration for bmc_ip")
        self.ip = i_hostip
        self.user = i_hostuser
        self.passwd = i_hostpasswd
        self.util = OpTestUtil()
        self.bmcip = i_bmcip
        self.results_dir = i_results_dir
        self.logfile = logfile
        self.ssh = OpTestSSH(i_hostip, i_hostuser, i_hostpasswd,
                logfile=self.logfile, check_ssh_keys=check_ssh_keys,
                known_hosts_file=known_hosts_file)
        self.scratch_disk = scratch_disk
        self.proxy = proxy
        self.scratch_disk_size = None
        self.conf = OpTestConfiguration.conf

    def hostname(self):
        return self.ip

    def username(self):
        return self.user

    def password(self):
        return self.passwd

    def set_system(self, system):
        self.ssh.set_system(system)

    def get_scratch_disk(self):
        return self.scratch_disk

    def get_scratch_disk_size(self, console=None):
        if self.scratch_disk_size is not None:
            return self.scratch_disk_size
        if console is None:
            raise Exception("You need to call get_scratch_disk_size() with a console first")
        dev_sdX = console.run_command("readlink -f %s" % self.get_scratch_disk())
        dev_sdX = dev_sdX[0].replace("/dev/","")
        scratch_disk_size = console.run_command("cat /sys/block/%s/size" % dev_sdX)
        # Use the (undocumented) /size sysfs property of nr 512byte sectors
        self.scratch_disk_size = int(scratch_disk_size[0])*512


    def get_proxy(self):
        return self.proxy

    def get_ssh_connection(self):
        return self.ssh

    def host_get_OS_Level(self, console=0):
        '''
        Get the OS version.
        '''
        l_oslevel = self.host_run_command("cat /etc/os-release", timeout=60, console=console)
        return '\n'.join(l_oslevel)

    def host_cold_reset(self):
        '''
        Cold reboot the host
        '''
        log.debug(("Applying Cold reset on host."))
        l_rc = self.ssh.run_command(BMC_CONST.HOST_COLD_RESET, timeout=60)

        self.util.PingFunc(self.bmcip, totalSleepTime=BMC_CONST.PING_RETRY_FOR_STABILITY)

    def host_code_update(self, i_image, imagecomponent):
        '''
        Flash firmware (HPM image) using ipmitool.

        i_image
          hpm file
        i_imagecomponent
          component to be updated from the HPM file.
          Probably BMC_CONST.BMC_FW_IMAGE_UPDATE or BMC_CONST.BMC_PNOR_IMAGE
        '''
        # Copy the hpm file to the tmp folder in the host
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying hpm file to host failed"
            log.warning(l_msg)
            raise OpTestError(l_msg)

        l_cmd = "\necho y | ipmitool -I usb " + BMC_CONST.BMC_HPM_UPDATE + "/tmp/" \
                + i_image.rsplit("/", 1)[-1] + " " + imagecomponent
        log.debug(l_cmd)
        try:
            l_rc = self.ssh.run_command(l_cmd, timeout=1500)
            log.debug(l_rc)
            self.ssh.run_command("rm -rf /tmp/" + i_image.rsplit("/", 1)[1],timeout=120)
        except subprocess.CalledProcessError:
            l_msg = "Code Update Failed"
            log.warning(l_msg)
            raise OpTestError(l_msg)

        if(l_rc.__contains__("Firmware upgrade procedure successful")):
            return BMC_CONST.FW_SUCCESS
        else:
            l_msg = "Code Update Failed"
            log.warning(l_msg)
            raise OpTestError(l_msg)

    def host_run_command(self, i_cmd, timeout=1500, retry=0, console=0):
        # if we are QEMU use the system console
        if isinstance(self.ssh.system.console, OpTestQemu.QemuConsole) or (console == 1):
          return self.ssh.system.console.run_command(i_cmd, timeout, retry)
        else:
          return self.ssh.run_command(i_cmd, timeout, retry)

    def host_gather_opal_msg_log(self, console=0):
        '''
        Gather OPAL logs (from the host) and store in a file
        '''
        try:
            l_data = '\n'.join(self.host_run_command(BMC_CONST.OPAL_MSG_LOG, console=console))
        except OpTestError:
            l_msg = "Failed to gather OPAL message logs"
            raise OpTestError(l_msg)

        if not self.results_dir:
            log.debug(l_data)
            return

        l_res = (time.asctime(time.localtime())).replace(" ", "_")
        l_logFile = "Opal_msglog_%s.log" % l_res
        fn = os.path.join(self.results_dir, l_logFile)
        log.debug(fn)
        with open(fn, 'w') as f:
            f.write(l_data)

    def host_check_command(self, *i_cmd, **kwargs):
        '''
        Check if one or more binaries are present on host
        '''
        default_vals = {'console': 0}
        for key in default_vals:
          if key not in kwargs.keys():
            kwargs[key] = default_vals[key]
        l_cmd = 'which ' + ' '.join(i_cmd)
        log.debug(l_cmd)
        try:
            l_res = self.host_run_command(l_cmd, console=kwargs['console'])
        except CommandFailed as c:
            l_msg = "host_check_command: (%s) not present on host. output of '%s': %s" % (','.join(i_cmd), l_cmd, '\n'.join(c.output))
            log.error(l_msg)
            raise OpTestError(l_msg)

        return True

    def host_get_kernel_version(self, console=0):
        '''
        Get Linux kernel version running on the host (using uname).
        '''
        l_kernel = self.host_run_command("uname -a | awk {'print $3'}", timeout=60, console=0)
        l_kernel = ''.join(l_kernel)
        log.debug(l_kernel)
        return l_kernel

    def host_check_config(self, i_kernel, i_config, console=0):
        '''
        This function will checks first for config file for a given kernel version on host,
        if available then check for config option value and return that value
        whether it is y or m...etc.

        sample config option values: ::

          CONFIG_CRYPTO_ZLIB=m
          CONFIG_CRYPTO_LZO=y
          # CONFIG_CRYPTO_842 is not set

        i_kernel
          kernel version
        i_config
          Which config option want to check in config file. e.g. `CONFIG_SENSORS_IBMPOWERNV`

        It will return config option value y or m,
        or raise OpTestError if config file is not available on host
        or raise OpTestError if config option is not set in file.
        '''
        l_file = "/boot/config-%s" % i_kernel
        try:
            l_res = self.host_run_command("test -e %s" % l_file, timeout=60, console=console)
        except CommandFailed:
            raise NoKernelConfig(i_kernel, l_file)

        log.debug("Config file is available")
        l_cmd = "cat %s | grep -i --color=never %s" % (l_file, i_config)
        l_res = self.host_run_command(l_cmd, timeout=60, console=console)
        log.debug(l_res)
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

    def host_check_pkg_for_utility(self, i_oslevel, i_cmd, console=0):
        '''
        Check if a package is installed on the host.
        The `i_oslevel` is used to determine if we should use `dpkg` or `rpm` to
        search for the package name.
        '''
        if 'Ubuntu' in i_oslevel:
            return ''.join(self.host_run_command("dpkg -S `which %s`" % i_cmd, timeout=60, console=console))
        else:
            l_cmd = "rpm -qf `which %s`" % i_cmd
            return ''.join(self.host_run_command(l_cmd, timeout=60, console=console))

    def host_load_ibmpowernv(self, i_oslevel):
        '''
        This function loads ibmpowernv driver only on powernv platform
        and also this function works only in root user mode
        '''
        if "PowerKVM" not in i_oslevel:
            o = self.ssh.run_command("modprobe ibmpowernv",timeout=60)
            cmd = "lsmod | grep -i ibmpowernv"
            response = self.ssh.run_command(cmd, timeout=60)
            if "ibmpowernv" not in ''.join(response):
                l_msg = "ibmpowernv module is not loaded, exiting"
                raise OpTestError(l_msg)
            else:
                log.debug("ibmpowernv module is loaded")
            log.debug(cmd)
            log.debug(response)
            return BMC_CONST.FW_SUCCESS

    def host_start_lm_sensor_svc(self, i_oslevel, console=0):
        '''
        This function restarts the lm_sensors service on host using systemctl utility
        systemctl utility is not present in ubuntu, This function will work in remaining all
        other OS'es i.e redhat, sles and PowerKVM
        '''
        if 'Ubuntu' in i_oslevel:
            pass
        else:
            try:
                # Start the lm_sensors service
                cmd = "/bin/systemctl stop  lm_sensors.service"
                self.host_run_command(cmd, console=console)
                cmd = "/bin/systemctl start  lm_sensors.service"
                self.host_run_command(cmd, console=console)
                cmd = "/bin/systemctl status  lm_sensors.service"
                res = self.host_run_command(cmd, console=console)
                return BMC_CONST.FW_SUCCESS
            except:
                l_msg = "loading lm_sensors service failed"
                log.error(l_msg)
                raise OpTestError(l_msg)

    def host_clone_linux_source(self, i_dir):
        '''
        It will clone latest linux git repository in i_dir directory.

        i_dir
          directory where linux source will be cloned.
        '''
        l_msg = 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git'
        l_cmd = "git clone --depth=1 %s %s" % (l_msg, i_dir)
        self.ssh.run_command("rm -rf %s" % i_dir, timeout=300)
        self.ssh.run_command("mkdir %s" % i_dir, timeout=60)
        try:
            log.debug(l_cmd)
            res = self.ssh.run_command(l_cmd, timeout=1500)
            log.debug(res)
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning linux git repository is failed"
            log.error(l_msg)
            raise OpTestError(l_msg)

    def host_load_module(self, i_module, console=0):
        '''
        It will load the module using modprobe and verify whether it is loaded or not
        '''
        try:
            l_res = self.host_run_command("modprobe %s" % i_module, console=console)
        except CommandFailed as c:
            l_msg = "Error in loading the module %s, modprobe failed: %s" % (i_module,str(c))
            raise OpTestError(l_msg)
        l_res = self.host_run_command("lsmod | grep -i --color=never %s" % i_module, console=console)
        if re.search(i_module, ''.join(l_res)):
            log.debug("%s module is loaded" % i_module)
            return BMC_CONST.FW_SUCCESS
        else:
            raise KernelModuleNotLoaded(i_module)

    def host_read_hwclock(self, console=0):
        '''
        This function will read real time clock(RTC) time using hwclock utility.
        '''
        log.debug("Reading the hwclock")
        self.host_run_command("hwclock -r;echo $?", console=console)

    def host_read_systime(self, console=0):
        '''
        This function will read system time using date utility (This will be mantained by kernel).
        '''
        log.debug("Reading system time using date utility")
        l_res = self.host_run_command("date", console=console)
        return l_res

    def host_set_hwclock_time(self, i_time, console=0):
        '''
        This function will set hwclock time using the --date option
        format should be "2015-01-01 12:12:12"
        '''
        log.debug("Setting the hwclock time to %s" % i_time)
        self.host_run_command("hwclock --set --date \'%s\'" % i_time, console=console)

    ##
    #
    # @return BMC_CONST.FW_SUCCESS or raise OpTestError
    #
    def host_load_module_based_on_config(self, i_kernel, i_config, i_module, console=0):
        '''
        This function will load driver module on host based on the config option
        if config value

        m
          built as a module
        y
          driver built into kernel itself
        else
          raises OpTestError

        i_kernel
          kernel version to get config file
        i_config
          config option to check in config file
        i_module
          driver module to load on host based on config value
        '''
        l_val = self.host_check_config(i_kernel, i_config, console=console)
        if l_val == 'm':
            self.host_load_module(i_module, console=console)
        elif l_val == 'y':
            log.debug("Driver built into kernel itself")
        elif l_val == 'n':
            raise KernelConfigNotSet(i_config)

    def host_clone_skiboot_source(self, i_dir, console=0):
        '''
        It will clone latest skiboot git repository in i_dir directory

        i_dir
          directory where skiboot source will be cloned
        '''
        l_msg = 'https://github.com/open-power/skiboot.git/'
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.host_run_command("git config --global http.sslverify false", console=console)
        self.host_run_command("rm -rf %s" % i_dir, console=console)
        self.host_run_command("mkdir %s" % i_dir, console=console)
        try:
            log.debug(l_cmd)
            l_res = self.host_run_command(l_cmd, console=console)
            log.debug(l_res)
            return BMC_CONST.FW_SUCCESS
        except:
            l_msg = "Cloning skiboot git repository is failed"
            log.debug(l_msg)
            raise OpTestError(l_msg)

    def host_enable_single_core(self, console=0):
        '''
        This function enable only a single core
        '''
        self.host_run_command("ppc64_cpu --cores-on=1", console=console)

    def host_enable_all_cores(self, console=0):
        '''
        Enables all cores
        '''
        self.host_run_command("ppc64_cpu --cores-on=all", console=console)

    def host_get_list_of_pci_domains(self, console=0):
        '''
        This function is used to get list of PCI PHB domains.
        '''
        self.pci_domains = []
        self.host_run_command("lspci -mm", console=console)
        res = self.host_run_command('lspci -mm | cut -d":" -f1 | sort | uniq', console=console)
        for domain in res:
            if not domain:
                continue
            if len(domain) != 4:
                domain = ''.join(("00", domain))
            domain = 'PCI' + domain
            if not self.pci_domains.__contains__(domain):
                self.pci_domains.append(domain)
        log.debug(self.pci_domains)
        return self.pci_domains

    def host_get_root_phb(self, console=0):
        '''
        This function is used to get the PHB domain of root port where
        the filesystem is mounted(We need to skip this in EEH tests as recovery
        will fail on this domain is expected)
        '''
        cmd = "df -h /boot | awk 'END {print $1}'"
        res = self.host_run_command(cmd, console=console)
        boot_disk = ''.join(res).split("/dev/")[1]
        boot_disk = boot_disk.replace("\r\n", "")
        cmd  = "ls -l /dev/disk/by-path/ | grep %s | awk '{print $(NF-2)}'" % boot_disk
        res = self.host_run_command(cmd, console=console)
        matchObj = re.search(r"\d{4}(?!\d)", '\n'.join(res), re.S)
        if not matchObj:
            raise OpTestError("Not able to find out root phb domain")
        boot_domain = 'PCI' + matchObj.group(0)
        return  boot_domain

    def host_gather_kernel_log(self, console=0):
        '''
        It will gather kernel dmesg logs and store the copy in a logfile
        which will be stored in results dir.
        '''
        try:
            l_data = '\n'.join(self.host_run_command("dmesg", console=console))
        except OpTestError:
            l_msg = "Failed to gather kernel dmesg log"
            raise OpTestError(l_msg)
        if not self.results_dir:
            log.debug(l_data)
            return
        l_res = (time.asctime(time.localtime())).replace(" ", "_")
        l_logFile = "Kernel_dmesg_log_%s.log" % l_res
        fn = os.path.join(self.results_dir, l_logFile)
        log.debug(fn)
        with open(fn, 'w') as f:
            f.write(l_data)
        return BMC_CONST.FW_SUCCESS

    def host_start_opal_errd_daemon(self, console=0):
        '''
        starts opal_errd daemon
        '''
        self.host_run_command("systemctl start opal_errd", console=console)

    def host_stop_opal_errd_daemon(self, console=0):
        '''
        stops opal_errd daemon
        '''
        self.host_run_command("systemctl stop opal_errd", console=console)

    def host_get_status_of_opal_errd_daemon(self, console=0):
        '''
        This function gets the status of opal_errd daemon.
        Raises an exception if not running.
        '''
        res = self.host_run_command("ps -ef | grep -v grep | grep opal_errd | wc -l", console=console)
        log.debug(res)
        if res[0].strip() == "0":
            log.warning("Opal_errd daemon is not running")
            return False
        elif res[0].strip() == "1":
            log.debug("Opal_errd daemon is running")
            return True
        else:
            raise OpTestError("Not able to get status of opal errd daemon")

    def host_list_all_errorlogs(self, console=0):
        '''
        This function lists all error logs in host
        '''
        self.host_run_command("opal-elog-parse -l", console=console)

    def host_list_all_service_action_logs(self, console=0):
        '''
        This function lists all service action logs in host.
        '''
        self.host_run_command("opal-elog-parse -s", console=console)

    def host_get_number_of_errorlogs(self, console=0):
        '''
        This function gets the number of error logs
        '''
        res = self.host_run_command("ls %s | wc -l" % BMC_CONST.OPAL_ELOG_DIR, console=console)
        log.debug(res)
        return res

    def host_clear_error_logs(self, console=0):
        '''
        This function clears/acknowledges all error logs in host
        '''
        self.host_run_command("rm -f %s/*" % BMC_CONST.OPAL_ELOG_DIR, console=console)
        res = self.host_run_command("ls %s -1 --color=never" % BMC_CONST.OPAL_ELOG_SYSFS_DIR, console=console)
        log.debug('\n'.join(res))
        for entry in res:
            entry = entry.strip()
            if entry == '':
                continue
            self.host_run_command("echo 1 > %s/%s/acknowledge" % (BMC_CONST.OPAL_ELOG_SYSFS_DIR, entry), console=console)
        return True

    def host_clear_all_dumps(self, console=0):
        '''
        This function clears/acknowledges all dumps in host.
        '''
        self.host_run_command("rm -f %s/*" % BMC_CONST.OPAL_DUMP_DIR, console=console)
        res = self.host_run_command("ls %s -1 --color=never" % BMC_CONST.OPAL_DUMP_SYSFS_DIR, console=console)
        for entry in res:
            entry = entry.strip()
            if (entry == "initiate_dump") or (entry == ''):
                continue
            else:
                self.host_run_command("echo 1 > %s/%s/acknowledge" % (BMC_CONST.OPAL_DUMP_SYSFS_DIR, entry), console=console)
        return True

    def host_disable_kdump_service(self, os_level, console=0):
        '''
        This function disables kdump service. Needs the OS version (from `/etc/os-release`) to
        know if we should use systemd commands or not.
        '''
        if "Ubuntu" in os_level:
            self.host_run_command("systemctl stop kdump-tools.service", console=console)
            try:
                self.host_run_command("systemctl status kdump-tools.service", console=console)
            except CommandFailed as cf:
                if cf.exitcode == 3:
                    pass
                else:
                    log.debug(str(cf))
                    raise OpTestError("kdump-tools service is failed to stop")
        else:
            self.host_run_command("systemctl stop kdump.service", console=console)
            try:
                self.host_run_command("systemctl status kdump.service", console=console)
            except CommandFailed as cf:
                if cf.exitcode == 3:
                    pass
                else:
                    log.debug(str(cf))
                    raise OpTestError("kdump service is failed to stop")

    def host_enable_kdump_service(self, os_level, console=0):
        '''
        disables kdump service, needs `/etc/os-release` to work out service name.
        '''
        if "Ubuntu" in os_level:
            self.host_run_command("systemctl stop kdump-tools.service", console=console)
            self.host_run_command("systemctl start kdump-tools.service", console=console)
            self.host_run_command("systemctl status kdump-tools.service", console=console)
        else:
            self.host_run_command("systemctl stop kdump.service", console=console)
            self.host_run_command("systemctl start kdump.service", console=console)
            self.host_run_command("systemctl status kdump.service", console=console)

    def host_check_sysfs_path_availability(self, path, console=0):
        res = self.host_run_command("ls --color=never %s" % path, console=console)
        if "No such file or directory" in res:
            return False
        return True

    def host_check_dt_node_exist(self, node_path, console=0):
        path = "/proc/device-tree/" + node_path
        res = self.host_run_command("ls %s" % path, console=console)
        if "No such file or directory" in res:
            return False
        return True

    def host_get_list_of_chips(self, console=0):
        res = self.host_run_command("PATH=/usr/local/sbin:$PATH getscom -l", console=console)
        chips = []
        for line in res:
            matchObj = re.search("(\d{8}).*processor", line)
            if matchObj:
                chips.append(matchObj.group(1))
        if not chips:
            raise Exception("Getscom failed to list processor chip ids")
        chips.sort()
        log.debug(chips) # ['00000000', '00000001', '00000010']
        return chips

    def host_get_cores(self, console=0):
        proc_gen = self.host_get_proc_gen(console=console)
        core_ids = {}
        cpu_pirs = self.host_run_command("find /sys/devices/system/cpu/*/pir -exec cat {} \;", console=console)
        for pir in cpu_pirs:
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
        log.debug(core_ids)
        return core_ids

    # Supported on OpenPower and P9 FSP system
    def host_prd_supported(self, bmc_type, console=0):
        if not "FSP" in bmc_type:
            return True

        proc_gen = self.host_get_proc_gen(console=console)
        if proc_gen in ["POWER8", "POWER8E"]:
            return False

        return True

    def host_get_proc_gen(self, console=0):
        try:
            if self.proc_gen:
                pass
        except AttributeError:
            self.proc_gen = ''.join(self.host_run_command("grep '^cpu' /proc/cpuinfo |uniq|sed -e 's/^.*: //;s/[,]* .*//;'", console=console))
        return self.proc_gen

    def host_get_smt(self, console=0):
        self.cpu = self.host_get_proc_gen(console=console)
        if self.cpu in ["POWER8", "POWER8E"]:
            return 8
        elif self.cpu in ["POWER9"]:
            return 4
        else:
            return 1

    def host_get_core_count(self, console=0):
        res = self.host_run_command("lscpu --all -e| wc -l", console=console)
        return int(res[0])/(self.host_get_smt(console=console))

    def host_gather_debug_logs(self, console=0):
        self.host_run_command("grep ',[0-4]\]' /sys/firmware/opal/msglog", console=console)
        self.host_run_command("dmesg -T --level=alert,crit,err,warn", console=console)

    def host_copy_fake_gard(self):
        i_image = os.path.join(self.conf.basedir, "test_binaries", "fake.gard")
        # Copy the fake.gard file to the tmp folder in the host
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, "/tmp/", self.passwd)
        except:
            l_msg = "Copying fake.gard file to host failed"
            log.error(l_msg)
            raise OpTestError(l_msg)

    def copy_test_file_to_host(self, filename, sourcedir="test_binaries",
                               dstdir="/tmp/"):
        i_image = os.path.join(self.conf.basedir, sourcedir, filename)
        try:
            self.util.copyFilesToDest(i_image, self.user,
                                             self.ip, dstdir, self.passwd)
        except subprocess.CalledProcessError as e:
            l_msg = "Copying %s file to host failed" % filename
            log.error(l_msg)
            raise OpTestError(l_msg + str(e))

    def copy_files_from_host(self, sourcepath="", destpath="/tmp/"):
        if sourcepath == "":
            sourcepath = self.conf.output
        try:
            self.util.copyFilesFromDest(self.user,
                                        self.ip, destpath, self.passwd, sourcepath)
        except subprocess.CalledProcessError as e:
            l_msg = "Copying %s file(s) from host failed" % destpath
            log.debug(str(e))
            log.error(l_msg)
            raise OpTestError(l_msg + str(e))

    def host_pflash_get_partition(self, partition, console=0):
        d = self.host_run_command("pflash --info", console=console)
        for line in d:
            s = re.search(partition, line)
            if s:
                m = re.match(r'ID=\d+\s+\S+\s+((0[xX])?[0-9a-fA-F]+)..(0[xX])?[0-9a-fA-F]+\s+\(actual=((0[xX])?[0-9a-fA-F]+)\)\s(\[)?([A-Za-z-]+)?(\])?.*', line)
                if not m:
                    continue
                offset = int(m.group(1), 16)
                length = int(m.group(4), 16)
                ret = {'offset': offset,
                       'length': length
                       }
                flags = m.group(7)
                if flags:
                    ret['flags'] = [x for x in list(flags) if x != '-']
                return ret

    def host_has_capi_fpga_card(self, console=0):
        '''
        Check that host has a CAPI FPGA card
        '''
        l_cmd = "lspci -d \"1014::1200\""
        l_res = self.host_run_command(l_cmd, console=console)
        l_res = " ".join(l_res)
        if (l_res.__contains__('IBM Device')):
            l_msg = "Host has a CAPI FPGA card"
            log.debug(l_msg)
            return True
        else:
            l_msg = "Host has no CAPI FPGA card; skipping test"
            log.warning(l_msg)
            return False

    def host_clone_cxl_tests(self, i_dir, console=0):
        '''
        Clone latest cxl-tests git repository in i_dir directory.

        i_dir
          directory where cxl-tests will be cloned
        '''
        l_msg = "https://github.com/ibm-capi/cxl-tests.git"
        l_cmd = "git clone %s %s" % (l_msg, i_dir)
        self.host_run_command("git config --global http.sslverify false", console=console)
        self.host_run_command("rm -rf %s" % i_dir, console=console)
        self.host_run_command("mkdir %s" % i_dir, console=console)
        try:
            l_res = self.host_run_command(l_cmd, console=console)
            return True
        except:
            l_msg = "Cloning cxl-tests git repository is failed"
            return False

    def host_build_cxl_tests(self, i_dir, console=0):
        l_cmd = "cd %s; make" % i_dir
        self.host_run_command(l_cmd, console=console)
        l_cmd = "test -x %s/libcxl/libcxl.so" % i_dir
        self.host_run_command(l_cmd, console=console)
        l_cmd = "test -x %s/libcxl_tests; echo $?" % i_dir
        self.host_run_command(l_cmd, console=console)
        l_cmd = "test -x %s/memcpy_afu_ctx; echo $?" % i_dir
        self.host_run_command(l_cmd, console=console)

    def host_check_binary(self, i_dir, i_file, console=0):
        l_cmd = "test -x %s/%s;" % (i_dir, i_file)
        try:
            self.host_run_command(l_cmd, console=console)
            l_msg = "Executable file %s/%s is available" % (i_dir, i_file)
            log.debug(l_msg)
            return True
        except CommandFailed:
            l_msg = "Executable file %s/%s is not present" % (i_dir, i_file)
            log.debug(l_msg)
            return False
