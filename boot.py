"""Starts the web page on any system, after checking the OS and the Python version (README section 4.2)"""

import argparse
import os
import platform
import sys

MINIMUM = (3, 10)

LINUX_FAMILIES = (
    ("Debian, Ubuntu, Linux Mint, Pop!_OS, Kali, Raspberry Pi OS", ("debian", "ubuntu", "linuxmint", "pop", "kali", "raspbian", "elementary", "zorin", "neon"), "sudo apt install python3"),
    ("Fedora, RHEL, CentOS, Rocky, AlmaLinux, Nobara", ("fedora", "rhel", "centos", "rocky", "almalinux", "nobara", "amzn"), "sudo dnf install python3"),
    ("Arch, Manjaro, EndeavourOS, Garuda, CachyOS", ("arch", "manjaro", "endeavouros", "garuda", "cachyos", "artix"), "sudo pacman -S python"),
    ("openSUSE, SUSE Linux Enterprise", ("opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse", "sles"), "sudo zypper install python3"),
    ("Alpine Linux", ("alpine",), "sudo apk add python3"),
    ("Void Linux", ("void",), "sudo xbps-install python3"),
    ("Gentoo", ("gentoo",), "sudo emerge --ask dev-lang/python"),
    ("NixOS", ("nixos",), "nix-shell -p python3"),
)

SYSTEMS = {
    "windows": ("Windows", "winget install Python.Python.3.12   (or download it from https://www.python.org/downloads/)"),
    "mac": ("macOS", "brew install python   (or download it from https://www.python.org/downloads/)"),
    "linux": ("Linux", None),
}


def detect_system(name=None):
    """Gives back windows, mac, linux or other"""
    name = name if name is not None else platform.system()
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(name, "other")


def parse_os_release(text):
    """Pulls the ID and ID_LIKE words out of the text of /etc/os-release"""
    words = []
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key in ("ID", "ID_LIKE"):
            words += value.strip().strip('"').strip("'").lower().split()
    return words


def linux_family(words):
    """Finds the first matching family and gives back its name and install command, or None"""
    for family, ids, command in LINUX_FAMILIES:
        if any(word in ids for word in words):
            return family, command
    return None


def read_os_release():
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            continue
    return ""


def install_hint(system, words=None):
    """A short line you can copy to install Python on that system"""
    if system == "linux":
        match = linux_family(words if words is not None else parse_os_release(read_os_release()))
        if match:
            return f"{match[0]}: {match[1]}"
        return "Install Python 3.10 or newer with your package manager, or from https://www.python.org/downloads/"
    if system in SYSTEMS:
        return f"{SYSTEMS[system][0]}: {SYSTEMS[system][1]}"
    return "Install Python 3.10 or newer from https://www.python.org/downloads/"


def print_list():
    print("Systems I know:")
    print("  Windows   double-click boot-windows.bat")
    print("  macOS     double-click boot-mac.command")
    print("  Linux     run boot-linux.sh, or open it from your file manager")
    print("  anything with Python 3.10 or newer:  python boot.py")
    print("")
    print("Installing Python:")
    for key in ("windows", "mac"):
        print("  " + install_hint(key))
    for family, _ids, command in LINUX_FAMILIES:
        print(f"  {family}: {command}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the web interface on this computer.", add_help=True)
    parser.add_argument("--list", action="store_true", help="show the systems I know and how to install Python on them")
    parser.add_argument("--os", choices=sorted(SYSTEMS), default=None, help="show the Python install hint for another system, then stop")
    args, rest = parser.parse_known_args(argv)

    if args.list:
        print_list()
        return 0
    if args.os:
        print(install_hint(args.os))
        return 0

    system = detect_system()
    if sys.version_info < MINIMUM:
        print(f"You need Python {MINIMUM[0]}.{MINIMUM[1]} or newer. You have {sys.version_info[0]}.{sys.version_info[1]}.")
        print(install_hint(system))
        return 1

    root = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(root, "source")
    if not os.path.isdir(os.path.join(source, "recon")):
        print("I can't find the source/recon folder next to boot.py. Keep this file in the main folder of the project.")
        return 1
    sys.path.insert(0, source)

    from recon import gui

    return gui.main(rest)


if __name__ == "__main__":
    sys.exit(main())
