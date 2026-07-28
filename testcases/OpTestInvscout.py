#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestInvScout.py $
#
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2026
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

# @package OpTestInvScout.py
# This module automates the InvScout VPD survey workflow:
#
#   Test scenarios:
#   1. Run 'invscout -g' on the LPAR to update the MRP file.
#   2. Run 'invscout -v' on the LPAR and verify VPD XML file is generated
#      under /var/adm/invscout/.
#   3. Retrieve machine type-model and serial number from the HMC using
#      'lssyscfg -r sys -F type_model,serial_num'.
#   4. On the HSCPE host (su to root), run
#      'invscout -v -s <serial> -m <type_model>' to generate the HMC-side
#      VPD survey XML.
#   5. List /var/adm/invscout/VPD/ on HSCPE to confirm the file exists.
#   6. Compare md5sum of the VPD XML on HSCPE with the corresponding file
#      on the LPAR; both checksums must match.
#
#   Prerequisites / CLI arguments (in addition to the standard HMC args):
#       --hscpe-ip           IP / hostname of the HSCPE (PE HMC)
#       --hscpe-username     SSH username for HSCPE  (default: hscpe)
#       --hscpe-password     SSH password for HSCPE login
#       --hscpe-su-password  Password for 'su -' on HSCPE

import re
import unittest
import pexpect

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Path constants
INVSCOUT_DIR = "/var/adm/invscout"
HSCPE_VPD_DIR = "/var/adm/invscout/VPD"

# Regex to strip all ANSI/VT100 escape sequences (including OSC title sequences)
_ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07)')


def _strip_ansi(text):
    """Remove all ANSI escape and OSC sequences from *text*."""
    return _ANSI_ESCAPE.sub('', text)


def _clean_lines(raw_lines):
    """Strip ANSI codes from every line and drop empty / pure-prompt lines."""
    cleaned = []
    for line in raw_lines:
        line = _strip_ansi(line).strip()
        # Drop lines that are only the bash/root prompt artifact
        if line and not re.match(r'^\[?root@', line) and not re.match(r'^\[?hscpe@', line):
            cleaned.append(line)
    return cleaned


class OpTestInvScoutBase(unittest.TestCase):
    """
    Base class: setUp wires up all required handles.
    Sub-classes implement the individual test steps as runTest().
    """

    def setUp(self):
        conf = OpTestConfiguration.conf
        self.cv_SYSTEM = conf.system()
        self.cv_HOST = conf.host()
        self.bmc_type = conf.args.bmc_type

        if self.bmc_type not in ("FSP_PHYP", "EBMC_PHYP"):
            self.skipTest(
                "InvScout tests are supported only on LPAR (FSP_PHYP / EBMC_PHYP)"
            )
        # HMC handles -------------------------------------------------------
        self.hmc_ip = conf.args.hmc_ip
        self.hmc_user = conf.args.hmc_username
        self.hmc_password = conf.args.hmc_password
        self.system_name = conf.args.system_name
        self.lpar_name = conf.args.lpar_name
        self.cv_HMC = self.cv_SYSTEM.hmc
        # LPAR console (SSH to the LPAR OS) ----------------------------------
        self.c = self.cv_HMC.get_host_console()
        # HSCPE credentials -------------------------------------------------
        try:
            self.hscpe_ip = conf.args.hscpe_ip
        except AttributeError:
            self.skipTest("--hscpe-ip not provided; skipping InvScout test")
        self.hscpe_user = getattr(conf.args, "hscpe_username", "hscpe")
        self.hscpe_password = getattr(conf.args, "hscpe_password", None)
        if not self.hscpe_password:
            self.skipTest("--hscpe-password not provided; skipping InvScout test")
        # Password for 'su -' on HSCPE (defaults to same as login password)
        self.hscpe_su_password = getattr(
            conf.args, "hscpe_su_password", self.hscpe_password
        )
        # Bring LPAR to OS state --------------------------------------------
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self._check_invscout_installed()

    def _check_invscout_installed(self):
        log.info("Checking if invscout package is installed on the LPAR ...")
        try:
            invscout_check = self.c.run_command("which invscout", timeout=30)
        except CommandFailed:
            self.skipTest("invscout package is not installed on the LPAR")
    # ------------------------------------------------------------------
    # Helper: run a command on the LPAR console and return list of lines
    # ------------------------------------------------------------------
    def _lpar_run(self, cmd, timeout=120):
        log.info("LPAR$ %s", cmd)
        out = self.c.run_command(cmd, timeout=timeout)
        log.info("LPAR output: %s", out)
        return out

    # ------------------------------------------------------------------
    # Helper: open a fresh pexpect SSH session to HSCPE, escalate to
    # root via 'su -', run *cmd*, and return clean output lines.
    # A new session is opened every call so there are no state issues
    # between test steps.
    # ------------------------------------------------------------------
    def _hscpe_run_as_root(self, cmd, timeout=120):
        """
        SSH into HSCPE as hscpe, escalate to root with 'su -', execute
        *cmd*, capture output, and close the session.

        ANSI/colour codes are stripped from all captured output.
        """
        ssh_cmd = (
            "sshpass -p {pw} ssh"
            " -o PubkeyAuthentication=no"
            " -o StrictHostKeyChecking=no"
            " -o UserKnownHostsFile=/dev/null"
            " -l {user} {host}".format(
                pw=self.hscpe_password,
                user=self.hscpe_user,
                host=self.hscpe_ip,
            )
        )
        log.info("Connecting to HSCPE: %s@%s", self.hscpe_user, self.hscpe_ip)
        child = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=30)
        # Wait for the hscpe user shell prompt (ends with $ or >)
        child.expect([r'\$\s*$', r'>\s*$'], timeout=30)
        # Escalate to root
        child.sendline("su -")
        idx = child.expect(["[Pp]assword:", pexpect.TIMEOUT], timeout=15)
        if idx != 0:
            child.close()
            raise CommandFailed("su -", "No password prompt received on HSCPE", -1)
        child.sendline(self.hscpe_su_password)
        # Confirm we have a root prompt
        idx = child.expect([r'#\s*$', "incorrect", pexpect.TIMEOUT], timeout=15)
        if idx != 0:
            child.close()
            raise CommandFailed("su -", "Authentication failed for root on HSCPE", -1)

        log.info("HSCPE(root)# %s", cmd)
        child.sendline(cmd)
        # Collect output until root prompt returns
        child.expect(r'#\s*$', timeout=timeout)
        output_raw = child.before
        child.sendline("exit")
        try:
            child.expect(pexpect.EOF, timeout=10)
        except pexpect.TIMEOUT:
            pass
        child.close()
        # Clean: strip ANSI, remove the echoed command line and empty lines
        lines = _clean_lines(output_raw.splitlines())
        # Also drop any line that is identical to the command itself (echo)
        lines = [l for l in lines if l != cmd.strip()]
        log.info("HSCPE(root) output (clean): %s", lines)
        return lines

    # ------------------------------------------------------------------
    # Helper: retrieve type_model and serial_num from the HMC
    # ------------------------------------------------------------------
    def _get_machine_type_serial(self):
        """
        Returns (type_model, serial_num) by querying the HMC:
            lssyscfg -r sys -m <system_name> -F type_model,serial_num
        Example output line: "9080-HEX,134CA08"
        """
        out = self.cv_HMC.run_command(
            "lssyscfg -r sys -m {sys} -F type_model,serial_num".format(
                sys=self.system_name
            )
        )
        result_line = next(
            (l.strip() for l in reversed(out) if l.strip()), ""
        )
        if not result_line:
            self.fail(
                "lssyscfg returned no output for system '%s'" % self.system_name
            )
        parts = result_line.split(",")
        if len(parts) < 2:
            self.fail(
                "Unexpected lssyscfg output format: '%s'" % result_line
            )
        type_model = parts[0].strip()
        serial_num = parts[1].strip()
        log.info("Machine type-model: %s  serial: %s", type_model, serial_num)
        return type_model, serial_num

    # ------------------------------------------------------------------
    # Helper: get LPAR id from the HMC
    # ------------------------------------------------------------------
    def _get_lpar_id(self):
        """
        Returns the integer LPAR partition id for self.lpar_name.
        """
        out = self.cv_HMC.run_command(
            "lssyscfg -m {sys} -r lpar --filter lpar_names={lpar} -F lpar_id".format(
                sys=self.system_name, lpar=self.lpar_name
            )
        )
        lpar_id_str = next((l.strip() for l in reversed(out) if l.strip()), "")
        if not lpar_id_str or not lpar_id_str.isdigit():
            self.fail(
                "Could not determine LPAR id for '%s'; got: %s"
                % (self.lpar_name, out)
            )
        lpar_id = int(lpar_id_str)
        log.info("LPAR id for %s: %d", self.lpar_name, lpar_id)
        return lpar_id


# ---------------------------------------------------------------------------
# Test 1: invscout -g
# ---------------------------------------------------------------------------

class InvScoutGrepUpdate(OpTestInvScoutBase):
    """
    Step 1: Run 'invscout -g' on the LPAR.
    This updates the local MRP (Microcode Repository Package) database.
    """

    def runTest(self):
        log.info("===== InvScout Step 1: invscout -g (MRP update) =====")
        self._lpar_run("which invscout", timeout=30)
        out = self._lpar_run("invscout -g", timeout=300)
        combined = " ".join(out).lower()
        if "error" in combined and "no error" not in combined:
            self.fail("invscout -g reported an error: %s" % " ".join(out))
        log.info("invscout -g completed successfully")


# ---------------------------------------------------------------------------
# Test 2: invscout -v on LPAR
# ---------------------------------------------------------------------------

class InvScoutVpdSurveyLpar(OpTestInvScoutBase):
    """
    Step 2: Run 'invscout -v' on the LPAR and verify the VPD XML file is
    generated under /var/adm/invscout/.
    """

    def runTest(self):
        log.info("===== InvScout Step 2: invscout -v on LPAR =====")
        out = self._lpar_run("invscout -v", timeout=300)
        combined = " ".join(out).lower()
        if "error" in combined and "no error" not in combined:
            self.fail("invscout -v reported an error: %s" % " ".join(out))

        # Verify the VPD XML file exists
        files = self._lpar_run(
            "ls %s/*.xml 2>/dev/null || true" % INVSCOUT_DIR, timeout=30
        )
        xml_files = [
            f.strip()
            for f in files
            if f.strip().endswith(".xml")
        ]
        if not xml_files:
            self.fail(
                "No VPD XML file found under %s after invscout -v" % INVSCOUT_DIR
            )
        log.info("VPD XML file(s) found on LPAR: %s", xml_files)


# ---------------------------------------------------------------------------
# Test 3: invscout on HSCPE + md5sum cross-check
# ---------------------------------------------------------------------------

class InvScoutVpdSurveyHscpe(OpTestInvScoutBase):
    """
    Steps 3–6:
      3. Retrieve machine type-model and serial from HMC.
      4. Run 'invscout -v -s <serial> -m <type_model>' on HSCPE (as root).
      5. List /var/adm/invscout/VPD/ on HSCPE to find the generated file.
      6. Compare md5sum of VPD XML on HSCPE with the matching file on LPAR.
         Both checksums must match.
    """

    def runTest(self):
        # --- Step 3: get type_model and serial_num from HMC ----------------
        log.info("===== InvScout Step 3: Retrieve machine info from HMC =====")
        type_model, serial_num = self._get_machine_type_serial()
        lpar_id = self._get_lpar_id()
        # --- Step 4: run invscout on HSCPE as root -------------------------
        log.info("===== InvScout Step 4: invscout -v on HSCPE (root) =====")
        invscout_cmd = "invscout -v -s {serial} -m {model}".format(
            serial=serial_num, model=type_model
        )
        hscpe_out = self._hscpe_run_as_root(invscout_cmd, timeout=300)
        combined_hscpe = " ".join(hscpe_out).lower()
        if "error" in combined_hscpe and "no error" not in combined_hscpe:
            self.fail(
                "invscout -v on HSCPE reported an error: %s" % " ".join(hscpe_out)
            )
        # --- Step 5: list VPD directory on HSCPE (no colour codes) ---------
        log.info("===== InvScout Step 5: List VPD dir on HSCPE =====")
        # Use --color=never so the shell never emits ANSI colour escapes
        hscpe_raw = self._hscpe_run_as_root(
            "ls --color=never %s" % HSCPE_VPD_DIR, timeout=30
        )
        # Extra defensive strip: remove any residual ANSI that slipped through
        hscpe_vpd_files = [_strip_ansi(f).strip() for f in hscpe_raw if _strip_ansi(f).strip()]
        log.info("HSCPE VPD directory contents (clean): %s", hscpe_vpd_files)

        # Find the ClientPartition file for our type_model + serial + lpar_id.
        # Expected name: invscoutHMC_VPD_Survey_ClientPartition_<model>_<serial>-<lpar_id>.VPD.xml
        # We look for an exact lpar_id match first, then fall back to newest mtime.
        target_fname = self._find_hscpe_vpd_file(
            hscpe_vpd_files, type_model, serial_num, lpar_id
        )

        log.info("HSCPE VPD XML file selected: %s", target_fname)
        # --- Step 6: compare md5sums ---------------------------------------
        log.info("===== InvScout Step 6: md5sum comparison =====")

        hscpe_md5 = self._md5_on_hscpe(
            "{d}/{f}".format(d=HSCPE_VPD_DIR, f=target_fname)
        )
        log.info("HSCPE md5sum: %s  (%s)", hscpe_md5, target_fname)
        # Derive the LPAR-side filename from the HSCPE filename
        lpar_xml_fname = _hscpe_to_lpar_filename(target_fname)
        lpar_xml_path = "{d}/{f}".format(d=INVSCOUT_DIR, f=lpar_xml_fname)
        log.info("Corresponding LPAR VPD file: %s", lpar_xml_path)
        lpar_md5 = self._md5_on_lpar(lpar_xml_path)
        log.info("LPAR  md5sum: %s  (%s)", lpar_md5, lpar_xml_fname)
        if hscpe_md5 != lpar_md5:
            self.fail(
                "md5sum mismatch!\n"
                "  HSCPE (%s): %s\n"
                "  LPAR  (%s): %s"
                % (target_fname, hscpe_md5, lpar_xml_fname, lpar_md5)
            )
        log.info(
            "md5sum match confirmed: %s  [HSCPE:%s / LPAR:%s]",
            hscpe_md5, target_fname, lpar_xml_fname,
        )

    # ------------------------------------------------------------------
    # Private helpers used only in this test class
    # ------------------------------------------------------------------

    def _find_hscpe_vpd_file(self, file_list, type_model, serial_num, lpar_id):
        """
        Locate the correct ClientPartition VPD XML on HSCPE.

        Priority:
          1. Exact match: ...ClientPartition_<model>_<serial>-<lpar_id>.VPD.xml
          2. Any non-'.previous' ClientPartition_<model>_<serial>-*.VPD.xml
             — pick the one with the numerically highest suffix (most recent run)
        """
        prefix = "invscoutHMC_VPD_Survey_ClientPartition_{m}_{s}".format(
            m=type_model, s=serial_num
        )

        # Exact lpar_id match
        exact = "{p}-{lid}.VPD.xml".format(p=prefix, lid=lpar_id)
        if exact in file_list:
            return exact
        # All non-.previous ClientPartition files for this model+serial
        candidates = [
            f for f in file_list
            if f.startswith(prefix) and f.endswith(".VPD.xml") and not f.endswith(".previous")
        ]
        if not candidates:
            self.fail(
                "No ClientPartition VPD XML file found on HSCPE for "
                "%s_%s (lpar_id %d). Files present: %s"
                % (type_model, serial_num, lpar_id, file_list)
            )
        # Pick the one with the highest numeric suffix (most recent invscout run)
        def _suffix_num(fname):
            m = re.search(r'-(\d+)\.VPD\.xml$', fname)
            return int(m.group(1)) if m else -1

        candidates.sort(key=_suffix_num, reverse=True)
        log.info(
            "Exact lpar_id %d not found; using highest-suffix candidate: %s",
            lpar_id, candidates[0]
        )
        return candidates[0]

    def _md5_on_hscpe(self, full_path):
        """Run md5sum on HSCPE for *full_path* and return the hex digest."""
        # Quote the path to be safe against any residual special chars
        out = self._hscpe_run_as_root(
            "md5sum '{p}'".format(p=full_path), timeout=60
        )
        md5 = _extract_md5(out)
        if not md5:
            self.fail(
                "Could not parse md5sum from HSCPE output for '%s': %s"
                % (full_path, out)
            )
        return md5

    def _md5_on_lpar(self, full_path):
        """Run md5sum on the LPAR for *full_path* and return the hex digest."""
        out = self._lpar_run("md5sum '%s'" % full_path, timeout=60)
        md5 = _extract_md5(out)
        if not md5:
            self.fail(
                "Could not parse md5sum from LPAR output for '%s': %s"
                % (full_path, out)
            )
        return md5


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_md5(output_lines):
    """
    Parse md5sum output of the form:
        <32-hex-chars>  <filename>
    Returns the hex digest string, or None if not found.
    """
    for line in output_lines:
        m = re.match(r'([0-9a-fA-F]{32})\s+', _strip_ansi(line).strip())
        if m:
            return m.group(1)
    return None


def _hscpe_to_lpar_filename(hscpe_fname):
    """
    Convert an HSCPE ClientPartition VPD filename to the LPAR-side name.

    HSCPE: invscoutHMC_VPD_Survey_ClientPartition_9080-HEX_134CA08-7.VPD.xml
    LPAR:  9080-HEX_134CA08-7.VPD.xml

    The fixed prefix 'invscoutHMC_VPD_Survey_ClientPartition_' is stripped.
    """
    prefix = "invscoutHMC_VPD_Survey_ClientPartition_"
    if hscpe_fname.startswith(prefix):
        return hscpe_fname[len(prefix):]
    # Fallback: extract model_serial suffix
    m = re.search(r'(\d{4}-\w+_\w+.*\.VPD\.xml)$', hscpe_fname)
    if m:
        return m.group(1)
    return hscpe_fname


# ---------------------------------------------------------------------------
# Test suite loader
# ---------------------------------------------------------------------------

def suite():
    tests = [
        "InvScoutGrepUpdate",
        "InvScoutVpdSurveyLpar",
        "InvScoutVpdSurveyHscpe",
    ]
    loader = unittest.TestLoader()
    full_suite = unittest.TestSuite()
    for t in tests:
        full_suite.addTest(
            loader.loadTestsFromName(t, module=__import__(__name__))
        )
    return full_suite
