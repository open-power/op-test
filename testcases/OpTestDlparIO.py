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
OpTestDlpar
---------

This test is to preform and validate dlpar commands on SRIOV and Physical adapters

Example Conf file for dlpar
[op-test]
bmc_type=FSP_PHYP
bmc_ip=<fsp-ip>
bmc_username=<fsp userid>
bmc_password=<fsp password>
host_ip=<host ip>
host_user=<host userid>
host_password=<host password>
hmc_ip=<hmc ip or domin name>
hmc_username=<hmc userid>
hmc_password=<hmc password>
system_name=<managed system name>
lpar_name=<source lparname>
lpar_prof=default
host_cmd_timeout=36000
git_home=/home/linux_src
use_kexec=True
machine_state=OS
target_lpar=<target lparname>
pci_device=<pci id> (example : 4007:01:00.0)
sriov=<yes / no >
num_of_dlpar=<no of iterations>

Executing dlpar tests
./op-test --run-suite ${test}-suite -c test_conf

To run all scenarios part of the suite. 
./op-test --run-suite DlparIO-suite -c dlpar.conf

To run individual test.
/op-test --run testcases.OpTestDlparIO.OpTestDlpar -c dlpar.conf

'''

import unittest
import re
import OpTestConfiguration
import OpTestLogger
from common import OpTestHMC
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

class OpTestDlparIO(unittest.TestCase):

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.console = self.cv_SYSTEM.console
        self.cv_HMC = self.cv_SYSTEM.hmc
        self.cv_HOST = conf.host()
        self.mg_system = self.cv_HMC.mg_system
        self.dest_lpar = conf.args.target_lpar_name
        self.pci_device = conf.args.pci_device
        self.sriov = conf.args.sriov
        self.num_of_dlpar = int(conf.args.num_of_dlpar)

        if not self.cv_HMC.is_lpar_in_managed_system(self.mg_system, self.cv_HMC.lpar_name):
            raise OpTestError("Lpar %s not found in managed system %s" % (
                              self.cv_HMC.lpar_name, self.mg_system))
        if self.dest_lpar is not None:
            if not self.cv_HMC.is_lpar_in_managed_system(self.mg_system, self.dest_lpar):
                raise OpTestError("Lpar %s not found in managed system %s" % (self.dest_lpar, self.mg_system))
        self.check_pkg_installation()
        self.rsct_service_start()
        if self.dest_lpar is not None:
            cmd = 'lshwres -r io -m %s --rsubtype slot --filter \
                   lpar_names=%s -F lpar_id' % (self.mg_system, self.dest_lpar)
            output = self.cv_HMC.ssh.run_command(cmd)
            self.dest_lpar_id =  output[0]
        self.loc_code = self.get_slot_from_sysfs(self.pci_device)
        self.get_slot_hw_details()

    def check_pkg_installation(self):
        """
        Check required packages installed, Continue only if installed.
        Raise exception if packages not installed.
        """
        pkg_found = True
        pkg_notfound= []
        self.oslevel = self.cv_HOST.host_get_OS_Level()
        lpm_pkg_list = ["src", "rsct.core", "rsct.core.utils", "rsct.basic", "rsct.opt.storagerm", "DynamicRM"]
        for pkg in lpm_pkg_list:
            pkg_status = self.cv_HOST.host_check_pkg_installed(self.oslevel, pkg)
            if not pkg_status:
                pkg_found = False
                pkg_notfound.append(pkg)
        if pkg_found:
            return True
        raise OpTestError("Install the required packages : %s" % pkg_notfound)

    def rsct_service_start(self):
        """
        Check if rsct and rsct_rm services are up and running, if not start the same.
        """
        rc = self.cv_HOST.host_run_command("lssrc -a")
        if "inoperative" in str(rc):
            self.cv_HOST.host_run_command("startsrc -g rsct_rm; startsrc -g rsct")
            rc = self.cv_HOST.host_run_command("lssrc -a")
            if "inoperative" in str(rc):
                raise OpTestError("LPM cannot continue as some of rsct services are not active")


    def get_slot_hw_details(self):
        """
        Depending upon Pyscial or SRIOV adapters get the HW slot details from HMC.
        """
        if self.sriov == "yes":
            cmd = "lshwres -r sriov --rsubtype logport -m %s \
            --level eth --filter lpar_names=%s -F \
            'adapter_id,logical_port_id,phys_port_id,lpar_id,location_code,drc_name'" \
                   % (self.mg_system, self.cv_HMC.lpar_name)
            output = self.cv_HMC.ssh.run_command(cmd)
            log.info("output = %s" % output)
            for line in output:
                if self.loc_code in line:
                    self.adapter_id = line.split(',')[0]
                    self.logical_port_id = line.split(',')[1]
                    self.phys_port_id = line.split(',')[2]
                    self.lpar_id = line.split(',')[3]
                    self.location_code = line.split(',')[4]
                    self.phb = line.split(',')[5].split(' ')[1]
                    break
            log.info("lpar_id : %s, loc_code: %s",
                          self.lpar_id, self.loc_code)
        else:
            cmd = 'lshwres -r io -m %s --rsubtype slot \
                   --filter lpar_names=%s -F drc_index,lpar_id,drc_name,bus_id' \
                   % (self.mg_system, self.cv_HMC.lpar_name)
            output = self.cv_HMC.ssh.run_command(cmd)
            log.info("output = %s" % output)
            for line in output:
                if self.loc_code in line:
                    self.drc_index = line.split(',')[0]
                    self.lpar_id = line.split(',')[1]
                    self.phb = line.split(',')[3]
                    break
            log.info("lpar_id : %s, loc_code: %s, drc_index: %s, phb: %s",
                     self.lpar_id, self.loc_code, self.drc_index, self.phb)


    def get_slot_from_sysfs(self, full_pci_address):
        """
        Get slot form host sysfs.
        """
        try:
            devspec = self.cv_HOST.host_run_command("cat /sys/bus/pci/devices/%s/devspec" % full_pci_address)
        except CommandFailed as c:
            log.debug("CommandFailed to get devspec, probably the adapter is not attached to the system")
            self.assertEqual(
                c.exitcode, 0, "Attach the PCI adapter before starting the test : {}".format(c))
        slot = self.cv_HOST.host_run_command("cat /proc/device-tree/%s/ibm,loc-code" % devspec[0])
        slot_ibm = re.match(r'((\w+)[.])+(\w+)-[PC(\d+)-]*C(\d+)', slot[0])
        if slot_ibm:
            return slot_ibm.group()
        slot_openpower = re.match(r'(\w+)[\s]*(\w+)(\d*)', slot[0])
        if slot_openpower:
            return slot_openpower.group()
        raise OpTestError("Failed to get slot from: '%s'" % full_pci_address)


class OpTestDlpar(OpTestDlparIO):

    def dlpar_remove(self):
        """
        Function to remove the identified SRIOV or Physical adapter
        """
        output = None
        if self.sriov == "yes":
            self.changehwres_sriov(self.mg_system, 'r', self.lpar_id,
                                   self.adapter_id, self.logical_port_id,
                                   self.phys_port_id, 'remove')
            try:
                output = self.listhwres_sriov(self.mg_system, self.cv_HMC.lpar_name,
                                              self.logical_port_id)
            except CommandFailed:
                pass
        else:
            self.changehwres(self.mg_system, 'r', self.lpar_id, self.cv_HMC.lpar_name,
                             self.drc_index, 'remove')
            try:
                output = self.listhwres(self.mg_system, self.cv_HMC.lpar_name, self.drc_index)
            except CommandFailed:
                pass
        if output:
            log.debug(output)
            raise OpTestError("lshwres still lists the PCI device even after dlpar remove")

    def dlpar_add(self):
        """
        Function to add the identified SRIOV or Physical adapter
        """
        output = None
        if self.sriov == "yes":
            self.changehwres_sriov(self.mg_system, 'a', self.lpar_id,
                                   self.adapter_id, self.logical_port_id,
                                   self.phys_port_id, 'add')
            output = self.listhwres_sriov(self.mg_system, self.cv_HMC.lpar_name,
                                          self.logical_port_id)
            if not output:
                raise OpTestError("lshwres fails to list the port_id after dlpar add")
        else:
            self.changehwres(self.mg_system, 'a', self.lpar_id, self.cv_HMC.lpar_name,
                             self.drc_index, 'add')
            output = self.listhwres(self.mg_system, self.cv_HMC.lpar_name, self.drc_index)
            if not output:
                raise OpTestError("lshwres fails to list the drc_index after dlpar add")

    def dlpar_move(self):
        """
        Function to move the identified SRIOV or Physical adapter
        """
        if self.dest_lpar is None or self.sriov == "yes":
            log.warning("Skipping dlpar move check for adapter type or destination lpar")
            return
        self.changehwres(self.mg_system, 'm', self.lpar_id, self.dest_lpar,
                         self.drc_index, 'move')
        try:
            output = self.listhwres(self.mg_system, self.cv_HMC.lpar_name, self.drc_index)
        except CommandFailed:
            pass
        else:
            log.debug(output)
            raise OpTestError("lshwres still lists the drc in source lpar %s after \
                      dlpar move to destination lpar %s " % self.cv_HMC.lpar_name, self.dest_lpar)
        try:
            output = self.listhwres(self.mg_system, self.dest_lpar, self.drc_index)
        except CommandFailed:
            raise OpTestError("lshwres fails to list the drc in destination lpar %s after \
                       dlpar move" % self.dest_lpar)

        # dlpar move operation from lpar2 to lpar1
        self.changehwres(self.mg_system, 'm', self.dest_lpar_id, self.cv_HMC.lpar_name,
                         self.drc_index, 'move')
        try:
            output = self.listhwres(self.mg_system, self.cv_HMC.lpar_name, self.drc_index)
        except CommandFailed:
            raise OpTestError("lshwres fails to list the drc in lpar %s after \
                       dlpar move" % self.cv_HMC.lpar_name)
        try:
            output = self.listhwres(self.mg_system, self.dest_lpar, self.drc_index)
        except CommandFailed:
            pass
        else:   
            log.debug(output)
            raise OpTestError("lshwres still lists the drc in dest lpar %s after \
                      dlpar move to source lpar %s" % (self.dest_lpar, self.cv_HMC.lpar_name))

    def listhwres(self, server, lpar, drc_index):
        """
        Function to list the HW resource for given lpar and drc_index
        """
        cmd = 'lshwres -r io -m %s \
               --rsubtype slot --filter lpar_names= %s \
               | grep -i %s' % (server, lpar, drc_index)
        return self.cv_HMC.ssh.run_command(cmd)

    def listhwres_sriov(self, server, lpar, logical_port_id):
        """
        Function to list the HW resource for given lpar and logical_port_id
        """
        cmd = 'lshwres -r sriov -m %s \
              --rsubtype logport --filter lpar_names= %s --level eth \
              | grep -i %s' % (server, lpar, logical_port_id)
        return self.cv_HMC.ssh.run_command(cmd)

    def changehwres(self, server, operation, lpar_id, lpar, drc_index, msg):
        """
        Function to add, remove or move physical adapter from one lpar to another
        in same managed system.
        """
        if operation == 'm':
            cmd = 'chhwres -r io --rsubtype slot -m %s \
               -o %s --id %s -t %s -l %s ' % (server, operation, lpar_id,
                                              lpar, drc_index)
        else:
            cmd = 'chhwres -r io --rsubtype slot -m %s \
                   -o %s --id %s -l %s ' % (server, operation, lpar_id,
                                            drc_index)
        self.cv_HMC.ssh.run_command(cmd)

    def changehwres_sriov(self, server, operation, lpar_id, adapter_id,
                          logical_port_id, phys_port_id, msg):
        """
        Function to add, remove SRIOV adapter from one lpar to another
        in same managed system.
        """
        if operation == 'r':
            cmd = 'chhwres -r sriov -m %s --rsubtype logport -o r --id %s -a \
                  adapter_id=%s,logical_port_id=%s' \
                  % (server, lpar_id, adapter_id, logical_port_id)
        elif operation == 'a':
            cmd = 'chhwres -r sriov -m %s --rsubtype logport -o a --id %s -a \
                  phys_port_id=%s,adapter_id=%s,logical_port_id=%s, \
                  logical_port_type=eth' % (server, lpar_id, phys_port_id,
                                            adapter_id, logical_port_id)
        self.cv_HMC.ssh.run_command(cmd)

    def runTest(self):
        '''
        DLPAR remove, add and move operations from lpar_1 to lpar_2
        '''
        for _ in range(self.num_of_dlpar):
            self.dlpar_remove()
            self.dlpar_add()
            self.dlpar_move()

class OpTestdrmgr_pci(OpTestDlparIO):

    def do_drmgr_pci(self, operation):
        cmd = "echo -e \"\n\" | drmgr -c pci -s %s -%s" % (self.loc_code,
                                                           operation)
        self.cv_HOST.host_run_command(cmd)

    def runTest(self):
        for _ in range(self.num_of_dlpar):
            self.do_drmgr_pci('r')
            self.do_drmgr_pci('a')
        for _ in range(self.num_of_dlpar):
            self.do_drmgr_pci('R')

class OpTestdrmgr_phb(OpTestDlparIO):

    def do_drmgr_phb(self, operation):
        cmd = "drmgr -c phb -s \"PHB %s\" -%s" % (self.phb, operation)
        self.cv_HOST.host_run_command(cmd)

    def runTest(self):
        for _ in range(self.num_of_dlpar):
            self.do_drmgr_phb('r')
            self.do_drmgr_phb('a')

def DlparIO_suite():
    s = unittest.TestSuite()
    s.addTest(OpTestDlpar())
    s.addTest(OpTestdrmgr_pci())
    s.addTest(OpTestdrmgr_phb())
    return s
