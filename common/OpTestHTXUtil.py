#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2025
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

'''
OpTestHTXUtil
-------------
Reusable HTX utility for op-test.

Provides OpTestHTXUtil — a self-contained helper that manages the full
HTX lifecycle on a remote host via the existing op-test SSH/console
handles:

  install()          Install HTX RPM from a URL directory listing.
  start(devs, mdt)   Select mdt, activate devices, start the run.
  wait_and_check()   Poll htxerr for the configured duration.
  stop()             Shutdown mdt and htxd daemon cleanly.
  is_configured()    Gate: returns False when rpm_link is absent.

Design notes
~~~~~~~~~~~~
* No avocado, no subprocess curl — all host commands run via the
  op-test console/SSH handles that the caller already owns.
* distro_name and distro_version are passed in at construction time;
  the caller resolves them via OpTestUtil (already done in setUp()).
* The class is stateless between test runs: start() sets _started=True,
  stop() resets it.  tearDown() callers check _started before calling
  stop() to avoid redundant shutdowns.
* All public methods are no-ops (return []) when is_configured() is
  False, so callers need no extra guards.
'''

import re
import subprocess
import time

import OpTestLogger

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


# ======================================================================= #
#  Constants                                                               #
# ======================================================================= #

HTX_BASE_DIR    = '/usr/lpp/htx'
HTX_MDT_DIR     = HTX_BASE_DIR + '/mdt'
HTX_ERR_FILE    = '/tmp/htx/htxerr'
HTX_D_STATUS    = HTX_BASE_DIR + '/etc/scripts/htx.d'
HTX_D_RUN       = HTX_BASE_DIR + '/etc/scripts/htxd_run'
HTX_D_SHUTDOWN  = HTX_BASE_DIR + '/etc/scripts/htxd_shutdown'
DEFAULT_MDT     = 'mdt.hd'
DEFAULT_RUN_TIME = 1800          # 30 minutes
POLL_INTERVAL   = 60             # seconds between htxerr checks


# ======================================================================= #
#  OpTestHTXUtil                                                           #
# ======================================================================= #

class OpTestHTXUtil:
    '''
    Reusable HTX lifecycle manager for op-test test cases.

    Parameters
    ----------
    console : op-test host console/SSH handle
        Used for all HTX control commands (htxcmdline, htxd scripts).
        Must expose run_command() and run_command_ignore_fail().
    ssh_host : op-test SSH handle (OpTestSSH or OpTestHost)
        Used for lightweight polling commands (wc -c htxerr) that do
        not need the interactive console.  Must expose run_command().
    distro_name : str
        Short distro name as returned by OpTestUtil.distro_name(),
        e.g. 'rhel' or 'sles'.
    distro_version : str
        Major version digit as returned by OpTestUtil.get_distro_version(),
        e.g. '9' or '15'.
    rpm_link : str or None
        URL of the directory that lists HTX RPMs
        (e.g. 'http://ltcftp.ltc.ibm.com/lpp/linux/htx/').
        When None or empty, all public methods become no-ops and
        is_configured() returns False.
    run_time : int
        HTX stress duration in seconds (default: 1800 = 30 min).
    '''

    def __init__(self, console, ssh_host, distro_name, distro_version,
                 rpm_link, run_time=DEFAULT_RUN_TIME):
        self._console       = console
        self._ssh           = ssh_host
        self._distro_name   = distro_name.lower()
        self._distro_version = str(distro_version).split('.')[0]
        self._rpm_link      = (rpm_link or '').rstrip('/') + '/'
        self._run_time      = int(run_time) if run_time else DEFAULT_RUN_TIME
        self._started       = False
        self._mdt           = DEFAULT_MDT

        # Normalise suse → sles to match HTX RPM naming
        if self._distro_name == 'suse':
            self._distro_name = 'sles'

    # ------------------------------------------------------------------ #
    #  Public gate                                                         #
    # ------------------------------------------------------------------ #

    def is_configured(self):
        '''
        Return True only when an RPM link has been supplied.
        All other public methods are no-ops when this returns False.
        '''
        return bool(self._rpm_link.strip('/'))

    @property
    def started(self):
        '''True after start() succeeds, reset to False by stop().'''
        return self._started

    # ------------------------------------------------------------------ #
    #  RPM installation                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_rpm_name(self):
        '''
        Curl the RPM directory index and return the latest RPM filename
        that matches the current distro/version pattern.

        Uses subprocess on the *test driver* machine (not on the host)
        — identical to OpTestHtxBootme.install_latest_htx_rpm().

        Raises RuntimeError when no matching RPM is found.
        '''
        distro_pattern = '%s%s' % (self._distro_name, self._distro_version)
        log.info("HTX: fetching RPM index from %s (pattern=%s)",
                 self._rpm_link, distro_pattern)
        try:
            result = subprocess.run(
                'curl --silent -k %s' % self._rpm_link,
                shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=30,
            )
            index_html = result.stdout.decode('utf-8')
        except Exception as exc:
            raise RuntimeError(
                "HTX: failed to fetch RPM index from %s: %s"
                % (self._rpm_link, exc)
            )

        # Same regex used in avocado htx_test.py and OpTestHtxBootme
        candidates = re.findall(
            r'(?<=>)htx\w*-\d+-\w+\.\w+\.\w+', index_html
        )
        matching = sorted(
            [r for r in candidates if distro_pattern in r], reverse=True
        )
        if not matching:
            raise RuntimeError(
                "HTX: no RPM found for pattern '%s' at %s"
                % (distro_pattern, self._rpm_link)
            )
        log.info("HTX: resolved RPM → %s", matching[0])
        return matching[0]

    def _remove_existing_htx(self):
        '''Remove any previously installed HTX RPM and directory.'''
        old_pkgs = self._console.run_command_ignore_fail(
            'rpm -qa | grep htx'
        )
        for pkg in old_pkgs:
            pkg = pkg.strip()
            if pkg:
                log.info("HTX: removing old package %s", pkg)
                self._console.run_command_ignore_fail(
                    'rpm -e %s' % pkg, timeout=60
                )
        self._console.run_command_ignore_fail(
            'rm -rf %s' % HTX_BASE_DIR, timeout=60
        )

    def install(self):
        '''
        Install the latest distro-matching HTX RPM from rpm_link onto
        the host, then start htxd and regenerate the MDT catalogue.

        Steps
        -----
        1. Resolve the RPM filename from the directory index.
        2. Remove any existing HTX installation.
        3. wget the RPM onto the host and install it.
        4. Start the HTX daemon (htxd_run).
        5. Enable on-demand MDT creation and run htxcmdline -createmdt.

        Raises RuntimeError on any installation failure so the caller
        can treat it as a hard test error.
        '''
        if not self.is_configured():
            log.info("HTX: rpm_link not set — skipping install")
            return

        rpm_name = self._fetch_rpm_name()
        self._remove_existing_htx()

        log.info("HTX: downloading %s onto host", rpm_name)
        wget_cmd = (
            'wget %s%s -O /tmp/%s --no-check-certificate'
            % (self._rpm_link, rpm_name, rpm_name)
        )
        out = self._console.run_command(wget_cmd, timeout=300)
        if any('ERROR' in l or 'error:' in l for l in out):
            raise RuntimeError("HTX: wget failed for %s" % rpm_name)

        log.info("HTX: installing %s", rpm_name)
        install_cmd = 'rpm -ivh /tmp/%s --force' % rpm_name
        out = self._console.run_command(install_cmd, timeout=180)
        if any('ERROR' in l or 'error:' in l for l in out):
            raise RuntimeError("HTX: rpm install failed for %s" % rpm_name)

        # Clean up the downloaded RPM from /tmp
        self._console.run_command_ignore_fail(
            'rm -f /tmp/%s' % rpm_name, timeout=30
        )

        # Kill any stale htxd, then start fresh
        self._console.run_command_ignore_fail('pkill -f htxd', timeout=15)
        time.sleep(5)
        log.info("HTX: starting htxd daemon")
        self._console.run_command(HTX_D_RUN, timeout=30)

        # Enable on-demand MDT so mdt.hd is always present
        log.info("HTX: enabling on-demand MDT and creating catalogue")
        self._console.run_command(
            'hcl -set_htx_env HTX_ON_DEMAND_MDT_CREATION 1', timeout=30
        )
        self._console.run_command('htxcmdline -createmdt', timeout=60)
        log.info("HTX: installation and MDT creation complete")

    # ------------------------------------------------------------------ #
    #  Run lifecycle                                                       #
    # ------------------------------------------------------------------ #

    def start(self, block_devs, mdt=DEFAULT_MDT):
        '''
        Select *mdt*, suspend all devices, activate the given block
        devices, and start the HTX run.

        Parameters
        ----------
        block_devs : list[str]
            Bare block device names without /dev/, e.g.
            ['nvme0n1', 'nvme1n1'].
        mdt : str
            MDT filename to use (default: 'mdt.hd').

        Does nothing when is_configured() is False or block_devs is empty.
        '''
        if not self.is_configured() or not block_devs:
            return

        self._mdt = mdt
        devs_str = ' '.join(block_devs)
        log.info("HTX: selecting %s", mdt)
        self._console.run_command(
            'htxcmdline -select -mdt %s' % mdt
        )

        log.info("HTX: suspending all devices in %s", mdt)
        self._console.run_command(
            'htxcmdline -suspend all -mdt %s' % mdt
        )

        log.info("HTX: activating devices: %s", devs_str)
        self._console.run_command(
            'htxcmdline -activate %s -mdt %s' % (devs_str, mdt)
        )

        log.info("HTX: starting run on %s with mdt=%s", devs_str, mdt)
        self._console.run_command('htxcmdline -run -mdt %s' % mdt)
        self._started = True

    # ------------------------------------------------------------------ #
    #  Error polling                                                       #
    # ------------------------------------------------------------------ #

    def wait_and_check(self):
        '''
        Poll /tmp/htx/htxerr every POLL_INTERVAL seconds for
        self._run_time total seconds.

        Returns a list of failure strings (empty list = clean run).
        Stops polling early on the first error detected.
        '''
        if not self.is_configured() or not self._started:
            return []

        failures = []
        elapsed  = 0
        log.info(
            "HTX: running %s for %d seconds (%d min)",
            self._mdt, self._run_time, self._run_time // 60,
        )

        while elapsed < self._run_time:
            sleep_for = min(POLL_INTERVAL, self._run_time - elapsed)
            time.sleep(sleep_for)
            elapsed += sleep_for

            try:
                err_size_out = self._ssh.run_command(
                    'wc -c %s' % HTX_ERR_FILE
                )
                err_bytes = int(err_size_out[0].split()[0])
            except (IndexError, ValueError, Exception) as exc:
                log.warning(
                    "HTX: could not read htxerr size at t+%ds: %s",
                    elapsed, exc,
                )
                continue

            if err_bytes != 0:
                failures.append(
                    "HTX htxerr non-empty (%d bytes) at t+%ds — "
                    "inspect %s on the host for details"
                    % (err_bytes, elapsed, HTX_ERR_FILE)
                )
                log.error(
                    "HTX: htxerr non-empty (%d bytes) at t+%ds",
                    err_bytes, elapsed,
                )
                break

            log.info(
                "HTX: t+%ds / %ds — htxerr clean",
                elapsed, self._run_time,
            )

        return failures

    # ------------------------------------------------------------------ #
    #  Shutdown                                                            #
    # ------------------------------------------------------------------ #

    def stop(self):
        '''
        Shutdown the active MDT and stop the HTX daemon if still running.
        Safe to call even when start() was never reached (no-op in that
        case for the daemon check).
        '''
        if not self.is_configured():
            return

        log.info("HTX: shutting down mdt %s", self._mdt)
        self._console.run_command_ignore_fail(
            'htxcmdline -shutdown -mdt %s' % self._mdt, timeout=120
        )

        daemon_out = self._console.run_command_ignore_fail(
            '%s status' % HTX_D_STATUS
        )
        if any('running' in l for l in daemon_out):
            log.info("HTX: stopping htxd daemon")
            self._console.run_command_ignore_fail(
                HTX_D_SHUTDOWN, timeout=60
            )

        self._started = False
        log.info("HTX: shutdown complete")
