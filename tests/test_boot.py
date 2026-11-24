"""Tests for the boot launcher: system detection, install hints and launcher files"""

import ast
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_boot():
    spec = importlib.util.spec_from_file_location("boot", ROOT / "boot.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boot = _load_boot()


class TestDetection(unittest.TestCase):
    def test_system_names(self) -> None:
        self.assertEqual(boot.detect_system("Windows"), "windows")
        self.assertEqual(boot.detect_system("Darwin"), "mac")
        self.assertEqual(boot.detect_system("Linux"), "linux")
        self.assertEqual(boot.detect_system("FreeBSD"), "other")

    def test_os_release_parsing(self) -> None:
        ubuntu = 'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_ID="24.04"\n'
        self.assertEqual(boot.parse_os_release(ubuntu), ["ubuntu", "debian"])
        self.assertEqual(boot.parse_os_release('ID="arch"\n'), ["arch"])
        self.assertEqual(boot.parse_os_release(""), [])

    def test_linux_families(self) -> None:
        expected = {
            "ubuntu": "apt", "linuxmint": "apt", "kali": "apt", "fedora": "dnf", "rocky": "dnf", "arch": "pacman", "endeavouros": "pacman",
            "opensuse-tumbleweed": "zypper", "alpine": "apk", "void": "xbps", "gentoo": "emerge", "nixos": "nix-shell",
        }
        for distro, tool in expected.items():
            match = boot.linux_family([distro])
            self.assertIsNotNone(match, distro)
            self.assertIn(tool, match[1])
        self.assertIsNone(boot.linux_family(["unknownos"]))

    def test_derivatives_use_the_parent_family(self) -> None:
        self.assertIn("apt", boot.linux_family(["pop", "ubuntu", "debian"])[1])
        self.assertIn("dnf", boot.linux_family(["customname", "fedora"])[1])

    def test_install_hints(self) -> None:
        self.assertIn("winget", boot.install_hint("windows"))
        self.assertIn("brew", boot.install_hint("mac"))
        self.assertIn("pacman", boot.install_hint("linux", ["arch"]))
        self.assertIn("python.org", boot.install_hint("linux", ["unknownos"]))
        self.assertIn("python.org", boot.install_hint("other"))


class TestLauncherFiles(unittest.TestCase):
    def test_files_exist_and_point_at_boot_py(self) -> None:
        for name in ("boot-windows.bat", "boot-mac.command", "boot-linux.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("boot.py", text, name)
            self.assertIn("3, 10", text, name)

    def test_windows_file_starts_quietly(self) -> None:
        self.assertTrue((ROOT / "boot-windows.bat").read_text(encoding="utf-8").startswith("@echo off"))

    def test_boot_py_stays_parseable_by_old_python(self) -> None:
        source = (ROOT / "boot.py").read_text(encoding="utf-8")
        ast.parse(source, feature_version=(3, 7))
        self.assertNotIn(":=", source)
        self.assertNotIn("| None", source)

    def test_list_and_hint_options(self) -> None:
        listing = subprocess.run([sys.executable, str(ROOT / "boot.py"), "--list"], capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(listing.returncode, 0)
        self.assertIn("boot-windows.bat", listing.stdout)
        hint = subprocess.run([sys.executable, str(ROOT / "boot.py"), "--os", "windows"], capture_output=True, text=True, timeout=30, check=False)
        self.assertIn("winget", hint.stdout)

    def test_version_goes_through_to_the_interface(self) -> None:
        result = subprocess.run([sys.executable, str(ROOT / "boot.py"), "--version"], capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("recon-gui", result.stdout)

    @unittest.skipIf(os.name == "nt", "the shell launchers are for macOS and Linux")
    def test_shell_launchers_start_the_interface(self) -> None:
        for name in ("boot-linux.sh", "boot-mac.command"):
            result = subprocess.run(["sh", str(ROOT / name), "--version"], capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, name + result.stderr)
            self.assertIn("recon-gui", result.stdout)


if __name__ == "__main__":
    unittest.main()
