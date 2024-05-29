#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2021
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
#

'''
OpTestLPM
---------

This test is to perform and validate basic Live Partition Mobility(LPM)  migration
from source to destination managed system

For running stress-ng test in parallel with LPM:
    - Tune the stress-ng command parameters according to the resources available
      on the system under test.
    - Provide the "--timeout" in the stress-ng command in minutes.
    - The stress-ng test command is run only once (across all iterations of LPM);
      provide the "--timeout" value accordingly.

TODO: Monitor the console for forward and backward LPM logs.
      The console is lost during migration, and hence, backward LPM logs are not
      captured, and forward LPM logs are partially captured.
'''

import unittest
import time
import os
import re
import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed
from common.OpTestUtil import OpTestUtil
from common.OpTestThread import OpSSHThreadLinearVar1
from common.OpTestSOL import OpSOLMonitorThread

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestLPM(unittest.TestCase):


    @staticmethod
    def errMsg(vios_name, mg_system):
        raise OpTestError("Mover Service Partition (MSP) for VIOS %s" \
        " (in managed system %s) not enabled" % (vios_name, mg_system))

    def setUp(self, remote_hmc=None):
        self.conf = OpTestConfiguration.conf
        self.cv_SYSTEM = self.conf.system()
        self.console = self.cv_SYSTEM.console
        self.cv_HOST = self.conf.host()
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.src_mg_sys = self.cv_HMC.mg_system
        self.dest_mg_sys = self.cv_HMC.tgt_mg_system
        self.oslevel = None
        self.slot_num = None
        self.options = self.conf.args.options if 'options' in self.conf.args else None
        self.lpm_timeout = int(self.conf.args.lpm_timeout) if 'lpm_timeout' in self.conf.args else 300
        self.iterations = int(self.conf.args.iterations) if 'iterations' in self.conf.args else 1
        self.stressng_command = self.conf.args.stressng_command if 'stressng_command' in self.conf.args else None
        self.inactive_lpm = bool(self.conf.args.inactive_lpm) if 'inactive_lpm' in self.conf.args else False
        self.util = OpTestUtil(OpTestConfiguration.conf)
        if 'os_file_logs' in self.conf.args:
            self.os_file_logs = self.conf.args.os_file_logs.split(",")+['/var/log/drmgr']
        else:
            self.os_file_logs = ['/var/log/drmgr']
        self.os_cmd_logs = self.conf.args.os_cmd_logs.split(",") if 'os_cmd_logs' in self.conf.args else []
        self.vios_logs = self.conf.args.vios_logs.split(",") if 'vios_logs' in self.conf.args else []
        self.hmc_logs = self.conf.args.hmc_logs.split(",") if 'hmc_logs' in self.conf.args else []
        if all(v in self.conf.args for v in ['vios_ip', 'vios_username', 'vios_password']):
            self.vios_ip = self.conf.args.vios_ip
            self.vios_username = self.conf.args.vios_username
            self.vios_password = self.conf.args.vios_password
        if all(v in self.conf.args for v in ['remote_vios_ip', 'remote_vios_username',
                                             'remote_vios_password']):
            self.remote_vios_ip = self.conf.args.remote_vios_ip
            self.remote_vios_username = self.conf.args.remote_vios_username
            self.remote_vios_password = self.conf.args.remote_vios_password

        if self.conf.args.lpar_vios and 'remote_lpar_vios' in self.conf.args:
            self.src_lpar_vios = self.cv_HMC.lpar_vios.split(",")
            self.dest_lpar_vios = self.conf.args.remote_lpar_vios.split(",")
            for vios_name in self.src_lpar_vios:
                if not self.cv_HMC.is_msp_enabled(self.src_mg_sys, vios_name):
                    self.errMsg(vios_name, self.src_mg_sys)
            for vios_name in self.dest_lpar_vios:
                if not self.cv_HMC.is_msp_enabled(self.dest_mg_sys, vios_name, remote_hmc):
                    self.errMsg(vios_name, self.dest_mg_sys)

        if 'slot_num' in self.conf.args:
            self.slot_num = self.conf.args.slot_num
        if self.slot_num:
            self.bandwidth = self.conf.args.bandwidth
            self.adapters = self.conf.args.adapters.split(",")
            self.target_adapters = self.conf.args.target_adapters.split(",")
            self.ports = self.conf.args.ports.split(",")
            self.target_ports = self.conf.args.target_ports.split(",")
            self.interface = self.conf.args.interface
            self.interface_ip = self.conf.args.interface_ip
            self.netmask = self.conf.args.netmask
            self.peer_ip = self.conf.args.peer_ip

            self.vios_id = []
            for vios_name in self.src_lpar_vios:
                self.vios_id.append(self.cv_HMC.get_lpar_id(self.src_mg_sys, vios_name))
            self.target_vios_id = []
            for vios_name in self.dest_lpar_vios:
                self.target_vios_id.append(self.cv_HMC.get_lpar_id(self.dest_mg_sys, vios_name, remote_hmc))
            self.adapter_id = []
            for adapter in self.adapters:
                self.adapter_id.append(self.cv_HMC.get_adapter_id(self.src_mg_sys, adapter))
            self.target_adapter_id = []
            for adapter in self.target_adapters:
                self.target_adapter_id.append(self.cv_HMC.get_adapter_id(self.dest_mg_sys, adapter, remote_hmc))

    def check_pkg_installation(self):
        pkg_found = True
        pkg_notfound = []
        self.oslevel = self.cv_HOST.host_get_OS_Level()
        lpm_pkg_list = ["src", "rsct.core", "rsct.core.utils", "rsct.basic", "rsct.opt.storagerm", "DynamicRM", "stress-ng"]
        for pkg in lpm_pkg_list:
            pkg_status = self.cv_HOST.host_check_pkg_installed(self.oslevel, pkg)
            if not pkg_status:
                pkg_found = False
                pkg_notfound.append(pkg)
        if pkg_found:
            return True
        raise OpTestError("Install the required packages : %s" % pkg_notfound)

    def lpm_setup(self):
        try:
            self.cv_HOST.host_run_command("systemctl status firewalld.service")
            self.firewall_status = True
            '''
            Systemctl returns 3 if the service is in stopped state, Hence it is a false failure,
            handling the same with exception with exitcode.
            '''
        except CommandFailed as cf:
            if cf.exitcode == 3:
                self.firewall_status = False
        if self.firewall_status:
            self.cv_HOST.host_run_command("systemctl stop firewalld.service")
        rc = self.cv_HOST.host_run_command("lssrc -a | grep 'rsct \| rsct_rm'")
        if "inoperative" in str(rc):
            self.cv_HOST.host_run_command("startsrc -g rsct_rm; startsrc -g rsct")
            rc = self.cv_HOST.host_run_command("lssrc -a")
            if "inoperative" in str(rc):
                raise OpTestError("LPM cannot continue as some of rsct services are not active")

    def vnic_options(self, remote=''):
        '''
        Form the vnic_mappings param based on the adapters' details
        provided.
        '''
        if int(self.slot_num) < 3 or int(self.slot_num) > 2999:
            return ""
        if remote:
            cmd = []
            for index in range(0, len(self.adapters)):
                l_cmd = []
                for param in [self.slot_num, 'ded', self.src_lpar_vios[index],
                              self.vios_id[index], self.adapter_id[index],
                              self.ports[index], self.bandwidth,
                              self.target_adapter_id[index],
                              self.target_ports[index]]:
                    l_cmd.append(param)
                cmd.append("/".join(l_cmd))
        else:
            cmd = []
            for index in range(0, len(self.adapters)):
                l_cmd = []
                for param in [self.slot_num, 'ded',
                              self.dest_lpar_vios[index],
                              self.target_vios_id[index],
                              self.target_adapter_id[index],
                              self.target_ports[index], self.bandwidth,
                              self.adapter_id[index], self.ports[index]]:
                    l_cmd.append(param)
                cmd.append("/".join(l_cmd))

        return " -i \"vnic_mappings=%s\" " % ",".join(cmd)

    def vnic_ping_test(self, output_dir=None):
        if not self.util.ping_test(self.interface, self.peer_ip, self.cv_HOST):
            self.collect_logs_test_fail(output_dir=output_dir, hmc_logs=False)
            raise OpTestError("Ping test to peer IP failed.")

    def check_dmesg_errors(self, remote_hmc=None, output_dir=None):
        skip_errors = ['uevent: failed to send synthetic uevent',
                       'failed to send uevent',
                       'registration failed',
                       'Power-on or device reset occurred',
                       'mobility: Failed lookup: phandle',
                       'Send warning',
                       'Unknown NUMA node; performance will be reduced',
                       'No hypervisor support for SR-IOV on this device, IOV BARs disabled',
                       'log_max_qp value in current profile',
                       'tc ct offload not supported',
                       'send_subcrq_indirect failed',
                       'LPAR Platform KeyStore is not supported',
                       'node lid missing',
                       'Failed to retrieve secvar operations',
                       'CONFIG_IMA_DISABLE_HTABLE is disabled',
                       'the capability attribute has been deprecated',
                       'NULL argv: empty string added']
                       
        warn_errors = ['Invalid request detected while CRQ is inactive, possible device state change during reset',
                       'rejecting I/O to offline device',
                       'blk_update_request: I/O error',
                       'device-mapper: multipath']

        err = self.util.collect_errors_by_level(output_dir=output_dir, level_check=4, skip_errors=skip_errors, warn_errors=warn_errors)
        return err

    def is_RMCActive(self, mg_system, remote_hmc=None):
        '''
        Get the state of the RMC connection for the given parition
        '''
        hmc = remote_hmc if remote_hmc else self.cv_HMC
        cmd = "diagrmc -m %s --ip %s -p %s --autocorrect" % (
            mg_system, self.cv_HOST.ip, self.cv_HMC.lpar_name)
        output = hmc.ssh.run_command(cmd, timeout=600)
        for line in output:
            if "%s has RMC connection." % self.cv_HOST.ip in line:
                return True
        return False

    def rmc_service_start(self, mg_system, remote_hmc=None, output_dir=None):
        '''
        Start RMC services which is needed for LPM migration
        '''
        for svc in ["-z", "-A", "-p"]:
            self.cv_HOST.host_run_command('/opt/rsct/bin/rmcctrl %s' % svc, timeout=120)
        if not self.util.wait_for(self.is_RMCActive, timeout=60, args=[mg_system, remote_hmc]):
            self.cv_HOST.host_run_command('/usr/sbin/rsct/install/bin/recfgct', timeout=120)
            self.cv_HOST.host_run_command('/opt/rsct/bin/rmcctrl -p', timeout=120)
            if not self.util.wait_for(self.is_RMCActive, timeout=300, args=[mg_system, remote_hmc]):
                self.collect_logs_test_fail(remote_hmc, output_dir)
                raise OpTestError("RMC connection is down!!")

    def execute_stressng(self):
        stress_ng_timeout = re.search('(?:--timeout|-t) (\d+[mM])', self.stressng_command)
        if stress_ng_timeout:
            thread_timeout = int(stress_ng_timeout.group(1)[:-1])
        else:
            raise OpTestError("Specify --timeout parameter in stress-ng command in minutes.")
        self.thread_stressng = OpSSHThreadLinearVar1(1, 'stressng-thread', [self.stressng_command],
                                                     5, thread_timeout, True, (thread_timeout+1)*60)
        self.thread_stressng.start()

    def lpm_failed_error(self, mg_system, remote_hmc=None, output_dir=None):
        if self.cv_HMC.is_lpar_in_managed_system(mg_system, self.cv_HMC.lpar_name):
            cmd = "lssyscfg -m %s -r lpar --filter lpar_names=%s -F state" % (
                   mg_system, self.cv_HMC.lpar_name)
            lpar_state = self.cv_HMC.ssh.run_command(cmd)[0]
            self.collect_logs_test_fail(remote_hmc, output_dir)
            raise OpTestError("LPAR migration failed. LPAR is in %s state." % lpar_state)
        self.collect_logs_test_fail(remote_hmc, output_dir)
        raise OpTestError("LPAR migration failed.")

    def collect_logs_test_fail(self, remote_hmc=None, output_dir='', os_logs=True, vios_logs=True, hmc_logs=True):
        if self.inactive_lpm:
            os_logs = False
        if os_logs:
            self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs, collect_sosreport=True,
                                     output_dir=os.path.join(output_dir, "testFail"))
        if vios_logs:
            self.util.gather_vios_logs(self.src_lpar_vios[0], self.vios_ip, self.vios_username,
                                       self.vios_password, self.vios_logs, os.path.join(output_dir, "testFail"))
            self.util.gather_vios_logs(self.dest_lpar_vios[0], self.remote_vios_ip, self.remote_vios_username,
                                       self.remote_vios_password, self.vios_logs, os.path.join(output_dir, "testFail"))
        if hmc_logs:
            self.util.gather_hmc_logs(self.hmc_logs, output_dir=os.path.join(output_dir, "testFail"))
            if remote_hmc:
                self.util.gather_hmc_logs(self.hmc_logs, remote_hmc, os.path.join(output_dir, "testFail"))


class OpTestLPM_LocalHMC(OpTestLPM):


    def setUp(self):
        super(OpTestLPM_LocalHMC, self).setUp()

    def lpar_migrate_test(self):
        error_list = []
        self.util.clear_dmesg()
        self.check_pkg_installation()
        self.lpm_setup()

        if self.stressng_command:
            self.execute_stressng()

        for iteration in range(1, self.iterations + 1):
            if not self.is_RMCActive(self.src_mg_sys):
                log.info("RMC service is inactive..!")
                self.rmc_service_start(self.src_mg_sys, output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM")))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            fwd_lpm_logs_monitor_thread = OpSOLMonitorThread(1, "console")
            fwd_lpm_logs_monitor_thread.start()

            cmd = ''
            if self.slot_num:
                cmd = self.vnic_options()
                self.util.configure_host_ip(self.interface, self.interface_ip, self.netmask, self.cv_HOST)
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            if self.inactive_lpm:
                self.cv_HMC.poweroff_lpar()

            if not self.cv_HMC.migrate_lpar(self.src_mg_sys, self.dest_mg_sys, self.options,
              cmd, timeout=self.lpm_timeout):
                self.lpm_failed_error(self.src_mg_sys, output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            fwd_lpm_logs_monitor_thread.console_terminate()

            if self.inactive_lpm:
                self.cv_HMC.poweron_lpar()
                time.sleep(60)

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM")))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if not self.is_RMCActive(self.dest_mg_sys):
                log.info("RMC service is inactive..!")
                self.rmc_service_start(self.dest_mg_sys, output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if self.slot_num:
                cmd = self.vnic_options('remote')
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if self.inactive_lpm:
                self.cv_HMC.poweroff_lpar()

            log.debug("Migrating lpar back to original managed system")
            if not self.cv_HMC.migrate_lpar(self.dest_mg_sys, self.src_mg_sys, self.options,
              cmd, timeout=self.lpm_timeout):
                self.lpm_failed_error(self.dest_mg_sys, output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"))

            if self.inactive_lpm:
                self.cv_HMC.poweron_lpar()

            if self.slot_num:
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"))

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM")))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"))
        if error_list:
            self.collect_logs_test_fail(output_dir=os.path.join("logs_postLPM_failtest"), remote_hmc=None)
            raise OpTestError("Test failed. {}".format(err))

    def runTest(self):
        self.lpar_migrate_test()

    def tearDown(self):
        if self.stressng_command and self.thread_stressng.isAlive():
            self.cv_HOST.host_run_command('pkill -x "stress-ng"')
            self.thread_stressng.console_terminate()


class OpTestLPM_CrossHMC(OpTestLPM):


    def setUp(self):
        self.conf = OpTestConfiguration.conf

        # The following variables needs to be defined in
        # ~/.op-test-framework.conf
        self.target_hmc_ip = self.conf.args.target_hmc_ip
        self.target_hmc_username = self.conf.args.target_hmc_username
        self.target_hmc_password = self.conf.args.target_hmc_password

        self.remote_hmc = OpTestHMC.OpTestHMC(self.target_hmc_ip,
                                              self.target_hmc_username,
                                              self.target_hmc_password,
                                              managed_system=self.conf.args.target_system_name,
                                              lpar_name=self.conf.args.remote_lpar_vios,
                                              lpar_user=self.conf.args.remote_vios_username,
                                              lpar_password=self.conf.args.remote_vios_password,
                                              lpar_vios=self.conf.args.remote_lpar_vios)
        self.remote_hmc.set_system(self.conf.system())

        super(OpTestLPM_CrossHMC, self).setUp(self.remote_hmc)

    def cross_hmc_migrate_test(self):
        error_list = []
        self.util.clear_dmesg()
        self.check_pkg_installation()
        self.lpm_setup()

        if self.stressng_command:
            self.execute_stressng()

        for iteration in range(1, self.iterations + 1):
            if not self.is_RMCActive(self.src_mg_sys):
                log.info("RMC service is inactive..!")
                self.rmc_service_start(self.src_mg_sys, output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"),
                                        remote_hmc=self.remote_hmc))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            fwd_lpm_logs_monitor_thread = OpSOLMonitorThread(1, "console")
            fwd_lpm_logs_monitor_thread.start()

            cmd = ''
            if self.slot_num:
                cmd = self.vnic_options()
                self.util.configure_host_ip(self.interface, self.interface_ip, self.netmask, self.cv_HOST)
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "preForwardLPM"))

            if self.inactive_lpm:
                self.cv_HMC.poweroff_lpar()

            self.cv_HMC.cross_hmc_migration(
                    self.src_mg_sys, self.dest_mg_sys, self.target_hmc_ip,
                    self.target_hmc_username, self.target_hmc_password,
                    options=self.options, param=cmd, timeout=self.lpm_timeout
            )

            log.debug("Waiting for %.2f minutes." % (self.lpm_timeout/60))
            time.sleep(self.lpm_timeout)

            fwd_lpm_logs_monitor_thread.console_terminate()

            if self.inactive_lpm:
                self.cv_HMC.poweron_lpar(remote_hmc=self.remote_hmc)
                time.sleep(60)

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"),
                                        remote_hmc=self.remote_hmc))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if not self.is_RMCActive(self.dest_mg_sys, self.remote_hmc):
                log.info("RMC service is inactive..!")
                self.rmc_service_start(self.dest_mg_sys, self.remote_hmc,
                                       output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if self.slot_num:
                cmd = self.vnic_options('remote')
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "postForwardLPM"))

            if self.inactive_lpm:
                self.cv_HMC.poweroff_lpar(remote_hmc=self.remote_hmc)

            self.cv_HMC.cross_hmc_migration(
                    self.dest_mg_sys, self.src_mg_sys, self.cv_HMC.hmc_ip,
                    self.cv_HMC.user, self.cv_HMC.passwd, self.remote_hmc,
                    options=self.options, param=cmd, timeout=self.lpm_timeout
            )

            log.debug("Waiting for %.2f minutes." % (self.lpm_timeout/60))
            time.sleep(self.lpm_timeout)

            if self.inactive_lpm:
                self.cv_HMC.poweron_lpar()

            if self.slot_num:
                self.vnic_ping_test(output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"))

            if not self.inactive_lpm:
                error_list.append(self.check_dmesg_errors(output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"),
                                        remote_hmc=self.remote_hmc))
                self.util.gather_os_logs(self.os_file_logs, self.os_cmd_logs,
                                         output_dir=os.path.join("logs_itr"+str(iteration), "postBackwardLPM"))
        if error_list:
            self.collect_logs_test_fail(output_dir=os.path.join("logs_postLPM_failtest"), remote_hmc=self.remote_hmc)
            raise OpTestError("Test failed. {}".format(err))

    def runTest(self):
        self.cross_hmc_migrate_test()

    def tearDown(self):
        if self.stressng_command and self.thread_stressng.isAlive():
            self.cv_HOST.host_run_command('pkill -x "stress-ng"')
            self.thread_stressng.console_terminate()
