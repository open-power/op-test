#!/usr/bin/env python3
# IBM_PROLOG_BEGIN_TAG
# This is an automatically generated prolog.
#
# $Source: op-test-framework/testcases/OpTestInvscout.py $
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

# @package OpTestInvscout.py
# This module automates the InvScout VPD survey workflow:
#
#   Test scenarios:
#   1. Run 'invscout -g' on the LPAR to update the MRP file.
#   2. Run 'invscout -v' on the LPAR and verify VPD XML file is generated
#      under /var/adm/invscout/.
#   3. Retrieve machine type-model and serial number from the HMC using
#      'lssyscfg -r sys -F type_model,serial_num'.
#   4. On the HSCPE, run 'invscout -v -s <serial> -m <type_model>' to
#      generate the HMC-side VPD survey XML.
#   5. List /var/adm/invscout/VPD/ on HSCPE to confirm the file exists.
#   6. Compare md5sum of the VPD XML on HSCPE with the corresponding file
#      on the LPAR; both checksums must match.
#
#   Prerequisites / CLI arguments (in addition to the standard HMC args):
#       --hscpe-ip   IP / hostname of the HSCPE (PE HMC).
#                    The standard --hmc-username / --hmc-password credentials
#                    are reused for the HSCPE SSH connection.

import re
import unittest

import OpTestConfiguration
import OpTestLogger
from common.OpTestHMC import HMCUtil
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)

# Path constants
INVSCOUT_DIR = "/var/adm/invscout"
HSCPE_VPD_DIR = "/var/adm/invscout/VPD"

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
        self.hmc_ip = conf.args.hmc_ip
        self.hmc_user = conf.args.hmc_username
        self.hmc_password = conf.args.hmc_password
        self.system_name = conf.args.system_name
        self.lpar_name = conf.args.lpar_name
        self.cv_HMC = self.cv_SYSTEM.hmc
        # LPAR console (SSH to the LPAR OS) ----------------------------------
        self.c = self.cv_HMC.get_host_console()
        """
        HSCPE connection -------------------------------------------------
        IP is mandatory; username/password default to the HMC credentials
        but can be overridden with --hscpe-username / --hscpe-password when
        the HSCPE login user differs from the HMC admin user (e.g. 'hscpe'
        vs 'hscroot').  invscout must be in that user's PATH.
        """
        try:
            self.hscpe_ip = conf.args.hscpe_ip
        except AttributeError:
            self.skipTest("--hscpe-ip not provided; skipping InvScout test")
        hscpe_user = getattr(conf.args, "hscpe_username", None) or self.hmc_user
        hscpe_password = getattr(conf.args, "hscpe_password", None) or self.hmc_password
        self.hscpe = HMCUtil(
            self.hscpe_ip, hscpe_user, hscpe_password,
            block_setup_term=1,
        )
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self._check_invscout_installed()

    def _check_invscout_installed(self):
        log.info("Checking if invscout package is installed on the LPAR ...")
        try:
            invscout_check = self.c.run_command("which invscout", timeout=30)
        except CommandFailed:
            self.skipTest("invscout package is not installed on the LPAR")

    def _lpar_run(self, cmd, timeout=120):
        log.info("LPAR$ %s", cmd)
        out = self.c.run_command(cmd, timeout=timeout)
        log.info("LPAR output: %s", out)
        return out
    
    """
    Helper: run a command on the HSCPE via direct SSH only.
    Never falls back to the pexpect console — HSCPE is not a system
    console target and the fallback causes a mis-directed session hang.
    invscout exits 8 when some other LPARs on the managed system are
    inactive; our partition still succeeds, so exit 8 is accepted.
    """
    def _hscpe_run(self, cmd, timeout=120):
        """Run *cmd* on the HSCPE using direct SSH (no console fallback)."""
        log.info("HSCPE$ %s", cmd)
        try:
            out = self.hscpe.ssh.run_command_direct(cmd, timeout=timeout)
        except CommandFailed as e:
            # exit 8 = partial success (some other LPARs inactive) — not our error.
            if e.exitcode != 8:
                raise
            # e.output holds stderr (the survey table); return it as lines.
            out = e.output.splitlines() if isinstance(e.output, str) else list(e.output)
        log.info("HSCPE output: %s", out)
        return out

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

"""
Test 1: invscout -g
"""

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

"""
Test 2: invscout -v on LPAR
"""

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

"""
Test 3: invscout on HSCPE + md5sum cross-check
"""

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
        log.info("===== InvScout Step 3: Retrieve machine info from HMC =====")
        type_model, serial_num = self._get_machine_type_serial()
        lpar_id = self._get_lpar_id()
        log.info("===== InvScout Step 4: invscout -v on HSCPE =====")
        invscout_cmd = "invscout -v -s {serial} -m {model}".format(
            serial=serial_num, model=type_model
        )
        hscpe_out = self._hscpe_run(invscout_cmd, timeout=300)
        combined_hscpe = " ".join(hscpe_out).lower()
        if "error" in combined_hscpe and "no error" not in combined_hscpe:
            self.fail(
                "invscout -v on HSCPE reported an error: %s" % " ".join(hscpe_out)
            )
        log.info("===== InvScout Step 5: List VPD dir on HSCPE =====")
        hscpe_vpd_files = self._hscpe_run(
            "ls %s" % HSCPE_VPD_DIR, timeout=30
        )
        log.info("HSCPE VPD directory contents: %s", hscpe_vpd_files)
        """
        Find the ClientPartition file for our type_model + serial + lpar_id.
        Expected name: invscoutHMC_VPD_Survey_ClientPartition_<model>_<serial>-<lpar_id>.VPD.xml
        We look for an exact lpar_id match first, then fall back to newest mtime.
        """
        target_fname = self._find_hscpe_vpd_file(
            hscpe_vpd_files, type_model, serial_num, lpar_id
        )

        log.info("HSCPE VPD XML file selected: %s", target_fname)
        log.info("===== InvScout Step 6: md5sum comparison =====")

        hscpe_md5 = self._md5_on_hscpe(
            "{d}/{f}".format(d=HSCPE_VPD_DIR, f=target_fname)
        )
        log.info("HSCPE md5sum: %s  (%s)", hscpe_md5, target_fname)
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

    def _find_hscpe_vpd_file(self, file_list, type_model, serial_num, lpar_id):
        """
        Locate the correct ClientPartition VPD XML on HSCPE.

        Priority:
          1. Exact lpar_id match (non-.previous):
             invscoutHMC_VPD_Survey_ClientPartition_<model>_<serial>-<lpar_id>.VPD.xml
          2. Exact lpar_id match (.previous) — invscout rotates the previous
             run to .previous when a new run completes; .previous IS current data.
          3. Any non-.previous ClientPartition file for this model+serial
             — pick highest numeric suffix.
          4. Any .previous ClientPartition file for this model+serial
             — pick the one whose suffix matches lpar_id, else highest suffix.
        """
        prefix = "invscoutHMC_VPD_Survey_ClientPartition_{m}_{s}".format(
            m=type_model, s=serial_num
        )

        def _suffix_num(fname):
            m = re.search(r'-(\d+)\.VPD\.xml', fname)
            return int(m.group(1)) if m else -1

        exact = "{p}-{lid}.VPD.xml".format(p=prefix, lid=lpar_id)
        if exact in file_list:
            return exact
        exact_prev = exact + ".previous"
        if exact_prev in file_list:
            log.info("Using .previous file for lpar_id %d: %s", lpar_id, exact_prev)
            return exact_prev
        candidates = [
            f for f in file_list
            if f.startswith(prefix) and f.endswith(".VPD.xml")
            and not f.endswith(".previous")
        ]
        if candidates:
            candidates.sort(key=_suffix_num, reverse=True)
            log.info(
                "Exact lpar_id %d not found; using highest-suffix candidate: %s",
                lpar_id, candidates[0]
            )
            return candidates[0]
        prev_candidates = [
            f for f in file_list
            if f.startswith(prefix) and f.endswith(".VPD.xml.previous")
        ]
        if not prev_candidates:
            self.fail(
                "No ClientPartition VPD XML file found on HSCPE for "
                "%s_%s (lpar_id %d). Files present: %s"
                % (type_model, serial_num, lpar_id, file_list)
            )
        prev_candidates.sort(key=_suffix_num, reverse=True)
        log.info(
            "Using .previous fallback for lpar_id %d: %s",
            lpar_id, prev_candidates[0]
        )
        return prev_candidates[0]

    def _md5_on_hscpe(self, full_path):
        """Run md5sum on HSCPE for *full_path* and return the hex digest."""
        out = self._hscpe_run(
            "md5sum '%s'" % full_path, timeout=60
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


def _extract_md5(output_lines):
    """
    Parse md5sum output of the form:
        <32-hex-chars>  <filename>
    Returns the hex digest string, or None if not found.
    """
    for line in output_lines:
        m = re.match(r'([0-9a-fA-F]{32})\s+', line.strip())
        if m:
            return m.group(1)
    return None


def _hscpe_to_lpar_filename(hscpe_fname):
    """
    Convert an HSCPE ClientPartition VPD filename to the LPAR-side name.

    HSCPE: invscoutHMC_VPD_Survey_ClientPartition_9080-HEX_134CA08-14.VPD.xml
    HSCPE: invscoutHMC_VPD_Survey_ClientPartition_9080-HEX_134CA08-14.VPD.xml.previous
    LPAR:  9080-HEX_134CA08-14.VPD.xml

    Strips the fixed prefix and the trailing .previous suffix (if present).
    """
    # Strip .previous suffix first so the prefix match works cleanly
    fname = hscpe_fname
    if fname.endswith(".previous"):
        fname = fname[: -len(".previous")]
    prefix = "invscoutHMC_VPD_Survey_ClientPartition_"
    if fname.startswith(prefix):
        return fname[len(prefix):]
    # Fallback: extract model_serial suffix
    m = re.search(r'(\d{4}-\w+_\w+.*\.VPD\.xml)$', fname)
    if m:
        return m.group(1)
    return fname

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
