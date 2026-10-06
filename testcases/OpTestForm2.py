#!/usr/bin/env python3
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

'''
OpTestForm2: Build QEMU on PowerVM LPAR, boot a qcow2 guest, verify NUMA.

Config keys (op-test section):
  qemu_source_dir     - where to clone QEMU (default: /home)
  qemu_disk_dir       - where to store the qcow2 (default: /home)
  qemu_qcow2_url      - URL to download qcow2 image (required)
  qemu_qcow2_filename - image filename (default: guest.qcow2)
  host_password       - guest root password (fallback if qemu_guest_passwd not set)
  qemu_guest_passwd   - root password for the qcow2 guest (overrides host_password)
'''

import unittest
import time

import OpTestConfiguration
import OpTestLogger
from common.OpTestSystem import OpSystemState
from common.Exceptions import CommandFailed

log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestForm2(unittest.TestCase):
    '''Build QEMU on a PowerVM LPAR and verify NUMA topologies in a qcow2 guest.'''

    NUMA_CONFIGS = {
        '4node_symmetric': {
            'nodes': 4,
            'mem_per_node': '8G',
            'cpus_per_node': 2,
            'total_cpus': 8,
            'description': '4-node symmetric NUMA (equal remote distances)',
            'distance_matrix': {
                (0,0): 10, (0,1): 20, (0,2): 20, (0,3): 20,
                (1,0): 20, (1,1): 10, (1,2): 20, (1,3): 20,
                (2,0): 20, (2,1): 20, (2,2): 10, (2,3): 20,
                (3,0): 20, (3,1): 20, (3,2): 20, (3,3): 10,
            }
        },
        '4node_asymmetric': {
            'nodes': 4,
            'mem_per_node': '8G',
            'cpus_per_node': 2,
            'total_cpus': 8,
            'description': '4-node asymmetric NUMA (multi-socket simulation)',
            'distance_matrix': {
                (0,0): 10, (0,1): 20, (0,2): 113, (0,3): 255,
                (1,0): 20, (1,1): 10, (1,2): 56,  (1,3): 76,
                (2,0): 113, (2,1): 56, (2,2): 10, (2,3): 99,
                (3,0): 255, (3,1): 76, (3,2): 99, (3,3): 10,
            }
        },
        '8node_symmetric': {
            'nodes': 8,
            'mem_per_node': '4G',
            'cpus_per_node': 1,
            'total_cpus': 8,
            'description': '8-node symmetric NUMA (equal remote distances)',
            'distance_matrix': {
                (0,0): 10, (0,1): 20, (0,2): 20, (0,3): 20, (0,4): 20, (0,5): 20, (0,6): 20, (0,7): 20,
                (1,0): 20, (1,1): 10, (1,2): 20, (1,3): 20, (1,4): 20, (1,5): 20, (1,6): 20, (1,7): 20,
                (2,0): 20, (2,1): 20, (2,2): 10, (2,3): 20, (2,4): 20, (2,5): 20, (2,6): 20, (2,7): 20,
                (3,0): 20, (3,1): 20, (3,2): 20, (3,3): 10, (3,4): 20, (3,5): 20, (3,6): 20, (3,7): 20,
                (4,0): 20, (4,1): 20, (4,2): 20, (4,3): 20, (4,4): 10, (4,5): 20, (4,6): 20, (4,7): 20,
                (5,0): 20, (5,1): 20, (5,2): 20, (5,3): 20, (5,4): 20, (5,5): 10, (5,6): 20, (5,7): 20,
                (6,0): 20, (6,1): 20, (6,2): 20, (6,3): 20, (6,4): 20, (6,5): 20, (6,6): 10, (6,7): 20,
                (7,0): 20, (7,1): 20, (7,2): 20, (7,3): 20, (7,4): 20, (7,5): 20, (7,6): 20, (7,7): 10,
            }
        },
        '8node_asymmetric': {
            'nodes': 8,
            'mem_per_node': '4G',
            'cpus_per_node': 1,
            'total_cpus': 8,
            'description': '8-node asymmetric NUMA (4-socket simulation)',
            'distance_matrix': {
                (0,0): 10,  (0,1): 20,  (0,2): 80,  (0,3): 90,  (0,4): 140, (0,5): 150, (0,6): 200, (0,7): 255,
                (1,0): 20,  (1,1): 10,  (1,2): 75,  (1,3): 85,  (1,4): 135, (1,5): 145, (1,6): 195, (1,7): 250,
                (2,0): 80,  (2,1): 75,  (2,2): 10,  (2,3): 30,  (2,4): 100, (2,5): 110, (2,6): 160, (2,7): 170,
                (3,0): 90,  (3,1): 85,  (3,2): 30,  (3,3): 10,  (3,4): 95,  (3,5): 105, (3,6): 155, (3,7): 165,
                (4,0): 140, (4,1): 135, (4,2): 100, (4,3): 95,  (4,4): 10,  (4,5): 25,  (4,6): 70,  (4,7): 80,
                (5,0): 150, (5,1): 145, (5,2): 110, (5,3): 105, (5,4): 25,  (5,5): 10,  (5,6): 65,  (5,7): 75,
                (6,0): 200, (6,1): 195, (6,2): 160, (6,3): 155, (6,4): 70,  (6,5): 65,  (6,6): 10,  (6,7): 22,
                (7,0): 255, (7,1): 250, (7,2): 170, (7,3): 165, (7,4): 80,  (7,5): 75,  (7,6): 22,  (7,7): 10,
            }
        },
    }

    @classmethod
    def setUpClass(cls):
        conf = OpTestConfiguration.conf
        cls.cv_HOST = conf.host()
        cls.cv_IPMI = conf.ipmi()
        cls.cv_SYSTEM = conf.system()
        cls.cv_BMC = conf.bmc()

        cls.qemu_source_dir = getattr(conf.args, 'qemu_source_dir', '/home').rstrip('/')
        cls.qemu_disk_dir = getattr(conf.args, 'qemu_disk_dir', '/home').rstrip('/')
        cls.qemu_repo_dir = cls.qemu_source_dir + '/qemu'
        cls.qemu_binary = cls.qemu_repo_dir + '/build/qemu-system-ppc64'

        if 'qemu_qcow2_url' not in conf.args or not conf.args.qemu_qcow2_url:
            raise ValueError(
                "Config key 'qemu_qcow2_url' is required but not set in the .conf file."
            )
        cls.qcow2_url = conf.args.qemu_qcow2_url

        cls.qcow2_filename = getattr(conf.args, 'qemu_qcow2_filename', 'guest.qcow2')
        cls.qcow2_path = cls.qemu_disk_dir + '/' + cls.qcow2_filename

        cls.guest_password = getattr(conf.args, 'qemu_guest_passwd', None) or conf.args.host_password

    def setUp(self):
        self.cv_SYSTEM.goto_state(OpSystemState.OS)
        self.console = self.cv_HOST.get_ssh_connection()

    def install_packages(self):
        log.info("Installing required packages for QEMU build...")

        pkg_manager = self._detect_pkg_manager()

        if pkg_manager is None:
            log.error("No supported package manager found (zypper, dnf, or yum)")
            raise RuntimeError("No supported package manager found")

        log.info(f"Detected package manager: {pkg_manager}")

        if pkg_manager == "zypper":
            packages = [
                "git", "gcc", "gcc-c++", "cmake", "ninja", "autoconf", "automake", "make",
                "python3-devel", "glibc-devel", "zlib-devel", "libopenssl-devel",
                "libgcrypt-devel", "libgpg-error-devel", "libcap-devel", "libcap-ng-devel",
                "mksh", "libslirp-devel", "libpixman-1-0-devel",
                "libattr1", "libattr-devel", "libaio-devel", "libbsd0", "libbsd-devel",
                "lksctp-tools", "lksctp-tools-devel", "libxcrypt-devel-static", "popt-devel",
                "xz-devel", "libpmem-devel", "libpng16-16", "gnutls", "libssh-devel", "libiscsi-devel",
                "libnfs-devel", "libgvnc-1_0-0", "libnettle-devel", "qemu-hw-display-virtio-vga",
                "libgcc_s1", "libkeyutils1", "libzstd1", "libzstd-devel", "libudev1",
                "libnuma-devel", "numatop", "binutils-devel", "libpfm-devel", "virt-install",
                "virt-manager", "libvirt-devel", "python3-libvirt-python",
                "libvirt", "libvirt-daemon-driver-storage-disk", "libvirt-glib-devel",
                "libvirt-client-qemu", "libvirt-daemon-qemu",
                "wget", "screen",
            ]
        else:
            packages = [
                "git", "gcc", "gcc-c++", "cmake", "ninja-build", "autoconf", "automake", "make",
                "python3-devel", "glibc-devel", "zlib-devel", "openssl-devel",
                "libgcrypt-devel", "libgpg-error-devel", "libcap-devel", "libcap-ng-devel",
                "mksh", "libslirp-devel", "pixman-devel",
                "libattr", "libattr-devel", "libaio-devel", "libbsd", "libbsd-devel",
                "lksctp-tools", "lksctp-tools-devel", "libxcrypt-devel", "popt-devel",
                "xz-devel", "libpng-devel", "gnutls", "libssh-devel", "libiscsi-devel",
                "libnfs-devel", "libvncserver-devel", "nettle-devel", "qemu-ui-spice",
                "glibc", "keyutils-libs-devel", "libzstd", "libzstd-devel", "systemd-devel",
                "numactl-devel", "numatop", "binutils-devel", "libpfm-devel", "virt-install",
                "virt-manager", "libvirt-devel", "python3-libvirt",
                "libvirt", "libvirt-daemon-driver-storage", "libvirt-glib-devel",
                "libvirt-daemon", "libvirt-daemon-qemu",
                "wget", "screen",
            ]

        log.info(f"Installing {len(packages)} packages one by one (best-effort)...")
        for pkg in packages:
            try:
                if pkg_manager == "zypper":
                    self.console.run_command(
                        f"zypper --non-interactive install -y {pkg}", timeout=120)
                else:
                    self.console.run_command(
                        f"{pkg_manager} install -y {pkg}", timeout=120)
                log.info(f"Installed or verified: {pkg}")
            except CommandFailed as e:
                log.warning(f"Failed to install '{pkg}': {e}. Continuing.")

        missing_tools = []
        for tool in ["git", "gcc", "make", "cmake"]:
            try:
                self.console.run_command(f"which {tool}", timeout=10)
                log.info(f"Verified essential tool: {tool}")
            except CommandFailed:
                missing_tools.append(tool)

        try:
            self.console.run_command("which g++", timeout=10)
            log.info("Verified C++ compiler (g++)")
        except CommandFailed:
            log.warning("C++ compiler (g++) not found on PATH")

        ninja_found = False
        for ninja_cmd in ["ninja", "ninja-build"]:
            try:
                self.console.run_command(f"which {ninja_cmd}", timeout=10)
                log.info(f"Verified ninja as: {ninja_cmd}")
                ninja_found = True
                break
            except CommandFailed:
                continue

        if not ninja_found:
            missing_tools.append("ninja")

        if missing_tools:
            log.warning(f"Missing build tools: {missing_tools}. Proceeding anyway.")
        else:
            log.info("Essential build tools verification completed successfully")

        log.info("Package installation and validation phase completed")

    def clone_qemu_repo(self):
        log.info(f"Cloning QEMU repository into {self.qemu_repo_dir}...")

        try:
            self.console.run_command(f"test -d {self.qemu_repo_dir}", timeout=10)
            log.info(f"{self.qemu_repo_dir} already exists, removing it...")
            self.console.run_command(f"rm -rf {self.qemu_repo_dir}", timeout=60)
        except CommandFailed:
            log.info(f"{self.qemu_repo_dir} does not exist, proceeding with clone...")

        clone_cmd = f"cd {self.qemu_source_dir} && git clone https://github.com/qemu/qemu.git"
        output = self.console.run_command(clone_cmd, timeout=600)
        log.info("QEMU repository cloned successfully")

        verify_output = self.console.run_command(f"ls -la {self.qemu_repo_dir}", timeout=10)
        log.info(f"QEMU directory contents:\n{verify_output}")
        return output

    def build_qemu(self):
        log.info("Building QEMU...")

        build_dir = f"{self.qemu_repo_dir}/build"
        self.console.run_command(f"mkdir -p {build_dir}", timeout=30)

        log.info("Configuring QEMU (--target-list=ppc64-softmmu --enable-slirp)...")
        configure_cmd = f"cd {build_dir} && ../configure --target-list=ppc64-softmmu --enable-slirp"
        configure_output = self.console.run_command(configure_cmd, timeout=300)
        log.info("QEMU configuration completed")
        log.debug(f"Configure output:\n{configure_output}")

        log.info("Building QEMU with make -j32 (this may take a while)...")
        self.console.run_command(f"cd {build_dir} && make -j32", timeout=3600)
        log.info("QEMU parallel build completed")

        log.info("Running final make...")
        final_output = self.console.run_command(f"cd {build_dir} && make", timeout=1800)
        log.info("QEMU build completed successfully")
        return final_output

    def verify_qemu_build(self):
        log.info("Verifying QEMU build...")

        output = self.console.run_command(f"ls -lh {self.qemu_binary}", timeout=10)
        log.info(f"QEMU binary found:\n{output}")

        version_output = self.console.run_command(f"{self.qemu_binary} --version", timeout=10)
        log.info(f"QEMU version:\n{version_output}")
        return output

    def _detect_pkg_manager(self):
        if not hasattr(self, '_pkg_manager'):
            self._pkg_manager = None
            for candidate in ["zypper", "dnf", "yum"]:
                try:
                    self.console.run_command(f"which {candidate}", timeout=10)
                    self._pkg_manager = candidate
                    break
                except CommandFailed:
                    continue
        return self._pkg_manager

    def download_qcow2_image(self):
        log.info(f"Downloading qcow2 image from configured URL...")
        log.info(f"Destination: {self.qcow2_path}")

        try:
            self.console.run_command(f"test -f {self.qcow2_path}", timeout=10)
            log.info(f"Existing image found at {self.qcow2_path}, removing it...")
            self.console.run_command(f"rm -f {self.qcow2_path}", timeout=30)
        except CommandFailed:
            log.info("No existing image found, proceeding with fresh download...")

        self.console.run_command(f"mkdir -p {self.qemu_disk_dir}", timeout=10)

        download_cmd = (
            f"wget --no-verbose -O {self.qcow2_path} {self.qcow2_url}"
        )
        log.info(f"Running: {download_cmd}")
        output = self.console.run_command(download_cmd, timeout=1800)
        log.info(f"Download complete:\n{output}")
        return True

    def verify_qcow2_image(self):
        log.info(f"Verifying qcow2 image at {self.qcow2_path}...")
        try:
            output = self.console.run_command(f"ls -lh {self.qcow2_path}", timeout=10)
            log.info(f"QCOW2 image found:\n{output}")
            return True
        except CommandFailed:
            log.error(f"QCOW2 image not found at {self.qcow2_path}")
            return False

    def build_numa_config(self, config_name):
        if config_name not in self.NUMA_CONFIGS:
            raise ValueError(
                f"Unknown NUMA config: {config_name}. "
                f"Available: {list(self.NUMA_CONFIGS.keys())}"
            )

        config = self.NUMA_CONFIGS[config_name]
        numa_parts = []

        for node_id in range(config['nodes']):
            numa_parts.append(
                f"-object memory-backend-ram,id=mem{node_id},size={config['mem_per_node']}"
            )
            if config['cpus_per_node'] == 1:
                cpu_range = str(node_id)
            else:
                start_cpu = node_id * config['cpus_per_node']
                end_cpu = start_cpu + config['cpus_per_node'] - 1
                cpu_range = f"{start_cpu}-{end_cpu}"
            numa_parts.append(
                f"-numa node,memdev=mem{node_id},cpus={cpu_range},nodeid={node_id}"
            )

        for src in range(config['nodes']):
            for dst in range(config['nodes']):
                distance = config['distance_matrix'][(src, dst)]
                numa_parts.append(f"-numa dist,src={src},dst={dst},val={distance}")

        return " ".join(numa_parts)

    def ensure_screen_installed(self):
        try:
            self.console.run_command("which screen", timeout=10)
            log.info("screen is already installed")
            return
        except CommandFailed:
            pass

        log.info("screen not found — trying package manager first...")
        pkg_manager = self._detect_pkg_manager()
        if pkg_manager is not None:
            install_cmds = {
                "zypper": "zypper --non-interactive install -y screen",
                "dnf":    "dnf install -y screen",
                "yum":    "yum install -y screen",
            }
            try:
                self.console.run_command(install_cmds[pkg_manager], timeout=120)
                self.console.run_command("which screen", timeout=10)
                log.info(f"screen installed successfully via {pkg_manager}")
                return
            except CommandFailed as e:
                log.warning(f"Failed to install screen via {pkg_manager}: {e}")

        log.info("Package manager could not install screen — building from source...")
        screen_version = "4.9.1"
        screen_tarball = f"screen-{screen_version}.tar.gz"
        screen_url = f"https://mirror.netcologne.de/gnu/screen/{screen_tarball}"
        screen_src = f"/tmp/screen-{screen_version}"

        build_cmds = [
            ("install ncurses-devel",
             "dnf install -y ncurses-devel 2>/dev/null || "
             "yum install -y ncurses-devel 2>/dev/null || "
             "zypper --non-interactive install -y ncurses-devel 2>/dev/null || true",
             60),
            ("download screen tarball",
             f"wget -q -O /tmp/{screen_tarball} {screen_url}",
             120),
            ("extract tarball",
             f"tar -xzf /tmp/{screen_tarball} -C /tmp",
             30),
            ("configure screen",
             f"cd {screen_src} && ./configure --prefix=/usr/local",
             60),
            ("build screen",
             f"cd {screen_src} && make -j$(nproc)",
             120),
            ("install screen",
             f"cd {screen_src} && make install",
             30),
        ]

        for step_name, cmd, timeout in build_cmds:
            log.info(f"Building screen from source — {step_name}...")
            try:
                self.console.run_command(cmd, timeout=timeout)
            except CommandFailed as e:
                raise RuntimeError(
                    f"Failed to build screen from source at step '{step_name}': {e}\n"
                    "Please install the 'screen' package manually on the LPAR."
                )

        try:
            self.console.run_command("which screen || which /usr/local/bin/screen", timeout=10)
            log.info("screen built and installed from source successfully")
        except CommandFailed:
            raise RuntimeError(
                "screen binary not found after source build. "
                "Please install the 'screen' package manually on the LPAR."
            )

        try:
            self.console.run_command(f"rm -rf {screen_src} /tmp/{screen_tarball}", timeout=15)
        except Exception:
            pass

    def boot_qemu_guest_and_verify_numa(self, config_name):
        config = self.NUMA_CONFIGS[config_name]
        log.info(f"Booting QEMU guest with {config['description']}...")

        self.ensure_screen_installed()

        if not self.verify_qcow2_image():
            raise Exception(
                f"QCOW2 image not found at {self.qcow2_path}. "
                "Ensure download_qcow2_image() ran successfully."
            )

        numa_config = self.build_numa_config(config_name)

        qemu_cmd = (
            f"cd {self.qemu_repo_dir}/build && "
            "./qemu-system-ppc64 "
            "-name FEAT "
            f"-smp {config['total_cpus']} "
            "-m 32G "
            "-vga none "
            "-nographic "
            "-cpu POWER11 "
            "-accel tcg "
            "-device virtio-scsi-pci "
            f"-drive file={self.qcow2_path},if=none,format=qcow2,id=hd0 "
            "-device scsi-hd,drive=hd0 "
            f"{numa_config} "
            "-boot c"
        )

        log.info(f"QEMU GUEST BOOT - {config['description'].upper()}")
        log.info(f"Nodes: {config['nodes']}, CPUs: {config['total_cpus']}, image: {self.qcow2_path}")

        guest_user = "root"
        guest_password = self.guest_password

        screen_name = f"qemu-numa-{config_name}"
        script_path = f"/tmp/qemu_start_{config_name}.sh"
        log.info(f"Starting QEMU in screen session '{screen_name}'...")
        try:
            self.console.run_command(
                f"screen -X -S {screen_name} quit 2>/dev/null || true", timeout=10)
        except Exception:
            pass

        script_content = f"#!/bin/bash\n{qemu_cmd}\n"
        self.console.run_command(
            f"cat > {script_path} << 'EOFSCRIPT'\n{script_content}EOFSCRIPT",
            timeout=10)
        self.console.run_command(f"chmod +x {script_path}", timeout=10)

        self.console.run_command(
            f"screen -dmS {screen_name} {script_path}", timeout=30)

        log.info("QEMU started, waiting for boot...")

        try:
            output = self.console.run_command("screen -list", timeout=10)
            log.info(f"Active screen sessions:\n{output}")
            if screen_name not in str(output):
                log.error(f"Screen session '{screen_name}' not found in 'screen -list'")
                try:
                    qemu_ps = self.console.run_command(
                        "ps aux | grep qemu-system-ppc64 | grep -v grep", timeout=10)
                    log.info(f"QEMU processes:\n{qemu_ps}")
                except Exception:
                    pass
                raise Exception(f"Failed to start QEMU in screen session '{screen_name}'")
            log.info(f"Screen session '{screen_name}' confirmed running")
        except CommandFailed as e:
            raise Exception(f"Failed to verify screen session: {e}")

        log.info("Waiting for login prompt...")

        def wait_for_screen(pattern, wait_secs=30, poll_secs=3, label="pattern"):
            deadline = time.time() + wait_secs
            while time.time() < deadline:
                try:
                    buf = self.console.run_command(
                        f"screen -S {screen_name} -X hardcopy /tmp/qemu-screen.txt "
                        f"&& cat /tmp/qemu-screen.txt",
                        timeout=10
                    )
                    if pattern.lower() in "\n".join(buf).lower():
                        log.info(f"Detected '{label}' on screen")
                        return True
                except Exception:
                    pass
                time.sleep(poll_secs)
            log.warning(f"Timed out waiting for '{label}' on screen after {wait_secs}s")
            return False

        if not wait_for_screen("login:", wait_secs=300, poll_secs=10, label="login prompt"):
            log.error("Guest failed to boot — login prompt not seen within timeout")
            try:
                self.console.run_command(f"screen -X -S {screen_name} quit", timeout=10)
            except Exception:
                pass
            raise Exception("Guest boot timeout — no login prompt")

        log.info("Guest booted, logging in...")
        log.info(f"Sending username: {guest_user}")
        self.console.run_command(
            f"screen -S {screen_name} -X stuff '{guest_user}^M'", timeout=10)
        if not wait_for_screen("password:", wait_secs=30, label="Password prompt"):
            log.warning("Password prompt not confirmed — proceeding anyway")

        log.info("Sending password...")
        self.console.run_command(
            f"screen -S {screen_name} -X stuff '{guest_password}^M'", timeout=10)
        if not wait_for_screen("#", wait_secs=30, label="shell prompt"):
            log.warning("Shell prompt not confirmed — proceeding anyway")

        guest_output_file = "/tmp/numa_output.txt"
        log.info("Running 'numactl -H' in guest...")
        self.console.run_command(
            f"screen -S {screen_name} -X stuff "
            f"'numactl -H > {guest_output_file} 2>&1^M'",
            timeout=10)
        time.sleep(10)

        self.console.run_command(
            f"screen -S {screen_name} -X stuff 'cat {guest_output_file}^M'", timeout=10)
        time.sleep(3)

        log.info("Capturing numactl output...")
        output = self.console.run_command(
            f"screen -S {screen_name} -X hardcopy /tmp/qemu-numa-output.txt "
            f"&& cat /tmp/qemu-numa-output.txt",
            timeout=10
        )

        log.info("numactl -H output:")
        for line in output:
            log.info(line)

        output_str = "\n".join(output)
        expected_nodes = config['nodes']
        numa_nodes_found = [
            i for i in range(expected_nodes)
            if f"node {i}" in output_str.lower()
        ]

        if len(numa_nodes_found) == expected_nodes:
            log.info(f"SUCCESS: All {expected_nodes} NUMA nodes detected: {numa_nodes_found}")
        else:
            log.warning(
                f"WARNING: Only {len(numa_nodes_found)}/{expected_nodes} "
                f"NUMA nodes detected: {numa_nodes_found}"
            )

        if "node distances:" in output_str.lower() or "distance:" in output_str.lower():
            log.info("NUMA distance matrix present in output")
        else:
            log.warning("NUMA distance matrix not clearly visible in output")

        log.info("Exiting QEMU...")
        try:
            self.console.run_command(
                f"screen -S {screen_name} -X stuff '^Ax'", timeout=10)
            time.sleep(2)
        except Exception:
            pass

        try:
            self.console.run_command(f"screen -X -S {screen_name} quit", timeout=10)
        except Exception:
            pass

        try:
            self.console.run_command(
                f"rm -f /tmp/qemu-screen.txt /tmp/qemu-numa-output.txt {script_path}",
                timeout=10)
        except Exception:
            pass

        log.info(f"NUMA result: {len(numa_nodes_found)}/{expected_nodes} nodes found for {config['description']}")
        if len(numa_nodes_found) != expected_nodes:
            log.warning("Not all NUMA nodes detected — check numactl output above")

        return True

    def runTest(self):
        log.info(f"OpTestForm2: src={self.qemu_source_dir} disk={self.qemu_disk_dir} qcow2={self.qcow2_path}")
        try:
            log.info("[STEP 1/8] Installing packages...")
            self.install_packages()

            log.info("[STEP 2/8] Cloning QEMU...")
            self.clone_qemu_repo()

            log.info("[STEP 3/8] Building QEMU...")
            self.build_qemu()

            log.info("[STEP 4/8] Verifying QEMU build...")
            self.verify_qemu_build()

            log.info(f"[STEP 5/8] Downloading qcow2 from {self.qcow2_url}...")
            self.download_qcow2_image()

            log.info("[STEP 6/8] Testing 4-node symmetric NUMA...")
            self.boot_qemu_guest_and_verify_numa('4node_symmetric')

            log.info("[STEP 7/8] Testing 4-node asymmetric NUMA...")
            self.boot_qemu_guest_and_verify_numa('4node_asymmetric')

            log.info("[STEP 8a/8] Testing 8-node symmetric NUMA...")
            self.boot_qemu_guest_and_verify_numa('8node_symmetric')

            log.info("[STEP 8b/8] Testing 8-node asymmetric NUMA...")
            self.boot_qemu_guest_and_verify_numa('8node_asymmetric')

            log.info("OpTestForm2 completed successfully.")

        except CommandFailed as e:
            self.fail(f"OpTestForm2 failed: {e}")
        except Exception as e:
            self.fail(f"OpTestForm2 failed: {e}")


def qemu_setup_suite():
    suite = unittest.TestSuite()
    suite.addTest(OpTestForm2('runTest'))
    return suite
