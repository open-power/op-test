#!/usr/bin/env python3

import time
import unittest

import OpTestConfiguration
from common.OpTestUtil import OpTestUtil
from common.OpTestSystem import OpSystemState
from common.OpTestError import OpTestError
from common.OpTestKeys import OpTestKeys as keys


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

        if conf.args.bmc_type is not 'qemu':
            self.skipTest("This test is intended for qemu")

        # TODO extend to use real network device in qemu / real machine
        self.network_config_str = (self.bmc.console.mac_str +
                                   ',static,192.168.0.1/24,192.168.0.2 dns,192.168.0.3')

        self.system.goto_state(OpSystemState.PETITBOOT)

        # Let Petitboot discovery settle
        time.sleep(10)

    def testConfigStaticNetworkVar(self):
        c = self.console.get_console()
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Static IP')
        time.sleep(1)

        # navigate to network-type widget
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)

        # select static
        c.send(self.KEY_DOWN)
        c.send(self.KEY_DOWN)
        c.send(' ')

        # navigate to ip params
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)

        # set up, mask, gateway, DNS
        c.send('192.168.0.1')
        c.send(self.KEY_DOWN)
        c.send('24')
        c.send(self.KEY_DOWN)
        c.send('192.168.0.2')
        c.send(self.KEY_DOWN)
        # skip URL field
        c.send(self.KEY_DOWN)
        c.send('192.168.0.3')

        # OK!
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_UP)
        c.send(self.KEY_UP)
        c.send(' ')
        c.expect("e=edit, n=new")

        # drop to shell
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command('nvram --print-config')
        self.assertTrue('petitboot,network=%s' %
                        self.network_config_str in tconfig, "Network config not correct")

        self.system.goto_state(OpSystemState.PETITBOOT)

    def testReconfig(self):
        # Test saving an un-changed config.
        # We should see the same results as the first save

        self.testConfigStaticNetworkVar()

        # return to petitboot UI
        c.send('exit')
        c.expect('Petitboot')

        # enter system config
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Static IP')

        # select 'OK' button to save config
        time.sleep(0.1)
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_BTAB)
        c.send(self.KEY_BTAB)
        c.send(' ')
        time.sleep(0.1)

        # back to shell, check for the same config string
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command('nvram --print-config')
        self.assertTrue('petitboot,network=%s' %
                        self.network_config_str in tconfig, "Network config not correct")

        self.system.goto_state(OpSystemState.PETITBOOT)


class RestoreConfigDefaultTestCase(unittest.TestCase):
    def setUp(self):
        conf = OpTestConfiguration.conf
        self.system = conf.system()
        self.bmc = conf.bmc()
        self.console = self.system.console

        if conf.args.bmc_type is not 'qemu':
            self.skipTest("This test is intended for qemu")

        # TODO extend to use real network device in qemu / real machine
        self.network_config_str = (self.bmc.console.mac_str +
                                   ',static,192.168.0.1/24,192.168.0.2 dns,192.168.0.3')

        self.system.goto_state(OpSystemState.PETITBOOT)

        # Let Petitboot discovery settle
        time.sleep(10)

    def testRestoreDefaultAutoboot(self):
        c = self.console.get_console()

        # enter config
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Boot Order')

        # clear boot order list
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_DOWN)
        c.send(self.KEY_DOWN)
        c.send(' ')

        # save config, exit from UI
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_BTAB)
        c.send(self.KEY_BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command(
            'nvram --print-config | grep auto-boot')
        self.assertTrue("auto-boot?=false" in config, "Autoboot not disabled")

        self.system.goto_state(OpSystemState.PETITBOOT)
        c.send('c')
        c.expect('Petitboot System Configuration')
        # Autoboot will have been disabled by an empty boot order
        c.expect('Autoboot:')

        # re-enable autoboot
        c.send(self.KEY_DOWN)
        c.send(' ')
        # set autoboot option
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(' ')
        c.send(self.KEY_UP)
        c.send(self.KEY_UP)
        c.send(' ')

        # save config again, exit from UI
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_BTAB)
        c.send(self.KEY_BTAB)
        c.send(' ')

        # we should see that the auto-boot nvram setting has been removed
        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        config = self.console.run_command_ignore_fail(
            'nvram --print-config | grep -q auto-boot; echo $?')
        self.assertTrue("auto-boot?=false" not in config,
                        "Autoboot still disabled")

        self.system.goto_state(OpSystemState.PETITBOOT)

    def testRestoreDefaultTimeout(self):
        c = self.console.get_console()

        # enter config
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Boot Order')

        # set timeout to non-default
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.sendcontrol('h')
        c.sendcontrol('h')
        c.send('42')

        # save config, exit from UI
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_BTAB)
        c.send(self.KEY_BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)
        timeout = self.console.run_command(
            'nvram --print-config | grep petitboot,timeout')
        self.assertTrue("petitboot,timeout=42" in timeout,
                        "New timeout value not seen")

        # exit shell
        self.system.goto_state(OpSystemState.PETITBOOT)

        # set timeout back to default of 10
        c.send('c')
        c.expect('Petitboot System Configuration')
        c.expect('Boot Order')
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.send(self.KEY_TAB)
        c.sendcontrol('h')
        c.sendcontrol('h')
        c.send('10')

        # save config again, exit from UI
        c.send(self.KEY_PGDOWN)
        c.send(self.KEY_BTAB)
        c.send(self.KEY_BTAB)
        c.send(' ')

        self.system.goto_state(OpSystemState.PETITBOOT_SHELL)

        # we should see that the auto-boot nvram setting has been removed
        timeout = self.console.run_command_ignore_fail(
            'nvram --print-config | grep -q petitboot,timeout')
        self.assertTrue("0" in timeout, "Timeout doesn't appear to be reset")

        self.system.goto_state(OpSystemState.PETITBOOT)
