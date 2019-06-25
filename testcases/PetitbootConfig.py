#!/usr/bin/env python2

import time
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.OpTestKeys import OpTestKeys as keys

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class ConfigEditorTestCase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.console = self.system.console

        self.system.goto_state(OpSystemState.PETITBOOT)

        # Let Petitboot discovery settle
        time.sleep(10)

    def testConfigAvailable(self):
        c = self.console.get_console()
        c.send('c')
        c.expect('Petitboot System Configuration')

        c.send('x')

        c.expect("e=edit, n=new")


class TimeoutConfigTestCase(unittest.TestCase):
    default_timeout = 10
    new_timeout = 314

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.system.goto_state(OpSystemState.PETITBOOT)
        self.console = self.system.console

        # Let Petitboot discovery settle
        time.sleep(10)

    def setConfigTimeout(self, val):
        c = self.console.get_console()
        c.send('c')
        c.expect('Petitboot System Configuration')

        # navigate to timeout field
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)

        # clear field & insert new value
        c.send('\x7f\x7f\x7f\x7f\x7f')
        c.send(str(val))

        # save
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(keys.ENTER)

        c.expect("e=edit, n=new")

    def testConfigTimeoutDisplay(self):
        c = self.console.get_console()
        self.setConfigTimeout(self.new_timeout)

        # wait for UI to settle after update
        time.sleep(10)

        c.send('c')
        # expect our new timeout value
        c.expect(str(self.new_timeout))

        c.send('x')
        c.expect("e=edit, n=new")

    def testConfigTimeoutSave(self):
        c = self.console.get_console()
        self.setConfigTimeout(self.new_timeout)

        # exit to shell, check saved timeout
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        timeout = self.console.run_command_ignore_fail(
            'nvram --print-config=petitboot,timeout')
        self.assertTrue(str(self.new_timeout) in timeout,
                        "New timeout value not seen")

        self.system.goto_state(OpSystemState.PETITBOOT)

    def testConfigTimeoutSaveDefault(self):
        c = self.console.get_console()

        # set a new timeout
        self.setConfigTimeout(self.new_timeout)

        # exit to shell and check setting
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        self.console.run_command('ls')
        timeout = self.console.run_command(
            'nvram --print-config=petitboot,timeout')
        self.assertTrue("314" in timeout, "New timeout value not seen")

        # back to UI
        self.system.goto_state(OpSystemState.PETITBOOT)

        # wait for UI to settle after update
        time.sleep(10)

        # reset to default
        self.setConfigTimeout(self.default_timeout)

        # exit to shell and expect no setting
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        timeout = self.console.run_command_ignore_fail(
            'nvram --print-config | grep -c petitboot,timeout')
        self.assertTrue("0" in timeout, "Timeout doesn't appear to be reset")

        self.system.goto_state(OpSystemState.PETITBOOT)


class StaticNetworkConfigTestCase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.console = self.system.console

        if conf.args.bmc_type != 'qemu':
            self.skipTest("This test is intended for qemu")

        self.network_config_str = (
            self.bmc.console.mac_str +
            ',static,192.168.0.1/24,192.168.0.2 dns,192.168.0.3')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        try:
            self.console.run_command("pflash -r /tmp/nvram-save -P NVRAM")
        except CommandFailed:
            log.debug("Failed to save NVRAM, changes may persist")

        self.system.goto_state(OpSystemState.PETITBOOT)

        # Let Petitboot discovery settle
        time.sleep(10)

    def tearDown(self):

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        try:
            self.console.run_command(
                "pflash -f -e -p /tmp/nvram-save -P NVRAM")
        except CommandFailed:
            log.debug("Failed to restore NVRAM, changes may persist")

    def testConfigStaticNetworkVar(self):
        c = self.console.get_console()
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Static IP')
        time.sleep(1)

        # make stuff consistent by turning auto-boot on
        c.send(keys.DOWN)
        c.send(' ')

        # navigate to network-type widget
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)

        # select static
        c.send(keys.DOWN)
        c.send(keys.DOWN)
        c.send(' ')

        # navigate to ip params
        c.send(keys.TAB)
        c.send(keys.DOWN)
        c.send(' ')
        c.send(keys.TAB)

        # set up, mask, gateway, DNS.
        # we need to clear any existing configuration first
        for i in range(20):
            c.send(keys.BACKSPACE)
        c.send('192.168.0.1')
        c.send(keys.DOWN)
        for i in range(4):
            c.send(keys.BACKSPACE)
        c.send('24')
        c.send(keys.DOWN)
        for i in range(20):
            c.send(keys.BACKSPACE)
        c.send('192.168.0.2')
        c.send(keys.DOWN)
        # skip URL field
        c.send(keys.DOWN)
        for i in range(20):
            c.send(keys.BACKSPACE)
        c.send('192.168.0.3')

        # OK!
        c.send(keys.PGDOWN)
        c.send(keys.UP)
        c.send(keys.UP)
        c.send(' ')
        c.expect("e=edit, n=new")

        # drop to shell
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command('nvram --print-config')
        self.assertTrue(
            'petitboot,network=%s' %
            self.network_config_str in config,
            "Network config not correct")

        self.system.goto_state(OpSystemState.PETITBOOT)

    def testReconfig(self):
        # Test saving an un-changed config.
        # We should see the same results as the first save
        # testConfigStaticNetworkVar leaves us in PETITBOOT
        self.testConfigStaticNetworkVar()

        c = self.console.get_console()

        # enter system config
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Static IP')

        # select 'OK' button to save config
        time.sleep(0.1)
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(' ')
        time.sleep(0.1)

        # back to shell, check for the same config string
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command('nvram --print-config')
        self.assertTrue(
            'petitboot,network=%s' %
            self.network_config_str in config,
            "Network config not correct")

        self.system.goto_state(OpSystemState.PETITBOOT)


class RestoreConfigDefaultTestCase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.console = self.system.console

        if conf.args.bmc_type != 'qemu':
            self.skipTest("This test is intended for qemu")

        self.network_config_str = (
            self.bmc.console.mac_str +
            ',static,192.168.0.1/24,192.168.0.2 dns,192.168.0.3')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        try:
            self.console.run_command("pflash -r /tmp/nvram-save -P NVRAM")
        except CommandFailed:
            log.debug("Failed to save NVRAM, changes may persist")

        self.system.goto_state(OpSystemState.PETITBOOT)

        # Let Petitboot discovery settle
        time.sleep(10)

    def tearDown(self):

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        try:
            self.console.run_command(
                "pflash -f -e -p /tmp/nvram-save -P NVRAM")
        except CommandFailed:
            log.debug("Failed to restore NVRAM, changes may persist")

    def testRestoreDefaultAutoboot(self):
        c = self.console.get_console()

        # enter config
        c.send('c')
        c.expect('Petitboot System Configuration')

        # make sure auto-boot is enabled
        c.send(keys.DOWN)
        c.send(' ')

        # clear boot order list
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.DOWN)
        c.send(keys.DOWN)
        c.send(' ')

        # save config, exit from UI
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command_ignore_fail(
            'nvram --print-config | grep auto-boot')
        self.assertTrue("auto-boot?=false" not in config, "Autoboot disabled!")

        self.system.goto_state(OpSystemState.PETITBOOT)
        c.send('c')
        c.expect('Petitboot System Configuration')
        # Autoboot will have been disabled by an empty boot order
        c.expect('Autoboot:')

        # re-enable autoboot
        c.send(keys.DOWN)
        c.send(' ')
        # set autoboot option
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(' ')
        c.send(keys.UP)
        c.send(keys.UP)
        c.send(' ')

        # save config again, exit from UI
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(' ')

        # we should see that the auto-boot nvram setting has been removed
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command_ignore_fail(
            'nvram --print-config | grep -q auto-boot; echo $?')
        self.assertTrue(
            "auto-boot?=false" not in config,
            "Autoboot still disabled")

        self.system.goto_state(OpSystemState.PETITBOOT)

    def testRestoreDefaultTimeout(self):
        c = self.console.get_console()

        # enter config
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Boot Order')

        # set timeout to non-default
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.sendcontrol('h')
        c.sendcontrol('h')
        c.send('42')

        # save config, exit from UI
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        timeout = self.console.run_command(
            'nvram --print-config | grep petitboot,timeout')
        self.assertTrue(
            "petitboot,timeout=42" in timeout,
            "New timeout value not seen")

        # exit shell
        self.system.goto_state(OpSystemState.PETITBOOT)

        # set timeout back to default of 10
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Boot Order')
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.TAB)
        c.send(keys.BACKSPACE)
        c.send(keys.BACKSPACE)
        c.send('10')

        # save config again, exit from UI
        c.send(keys.PGDOWN)
        c.send(keys.BTAB)
        c.send(keys.BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        # we should see that the timeout nvram setting has been removed
        timeout = self.console.run_command_ignore_fail(
            'nvram --print-config | grep -q petitboot,timeout')
        self.assertTrue(
            "timeout=42" not in timeout,
            "Timeout doesn't appear to be reset")

        self.system.goto_state(OpSystemState.PETITBOOT)
