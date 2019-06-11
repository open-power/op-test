#!/usr/bin/env python2

import time
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.OpTestKeys import OpTestKeys as keys

class ManyDisksTestCase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()

        if OpTestConfiguration.conf.args.bmc_type != "qemu":
            self.skipTest("10,000 disks requires QEMU")

        # Realistically you probably don't have a machine on hand that has the
        # memory to do 10,000 disks. This starts at five, change this number to
        # push it further.
        for i in range(1,5):
            self.bmc.add_temporary_disk("500K")

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

    def testListDisks(self):
        c = self.system.console

        c.run_command("ls -l /dev/vd* | wc -l")
