#!/usr/bin/env python2

import time
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.OpTestKeys import OpTestKeys as keys

class PetitbootCancelBoot(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()

        self.system.goto_state(OpSystemState.OFF)
        # Manually power on to avoid boot override being set
        self.system.sys_power_on()

        self.system.state = OpSystemState.PETITBOOT

class TestCancel(PetitbootCancelBoot):
    def runTest(self):
        c = self.system.console.get_console()

        c.expect("Booting in ", timeout=300)
        c.send(keys.PGDOWN)
        c.expect("Default boot cancelled")

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        result = self.system.console.run_command_ignore_fail(
                "grep \"Cancelling default\" " +
                "/var/log/petitboot/pb-discover.log")
        assert("Cancelling default" in result, "Autoboot was not cancelled")

