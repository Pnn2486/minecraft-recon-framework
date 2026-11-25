#!/bin/sh
# Starts the web interface on Linux.
# Works on any distro. If Python 3.10 or newer is missing, it shows the install command for yours.
# If your file manager will not run it, open a terminal in this folder and type: sh boot-linux.sh

cd "$(dirname "$0")" || exit 1

for cmd in python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        exec "$cmd" boot.py "$@"
    fi
done

echo "Python 3.10 or newer was not found."
ids=""
for file in /etc/os-release /usr/lib/os-release; do
    if [ -r "$file" ]; then
        ids=$(sed -n 's/^ID\(_LIKE\)\{0,1\}=//p' "$file" | tr -d '"' | tr '\n' ' ')
        break
    fi
done
case " $ids " in
    *" debian "*|*" ubuntu "*|*" linuxmint "*|*" pop "*|*" kali "*|*" raspbian "*) echo "Install it with: sudo apt install python3" ;;
    *" fedora "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*) echo "Install it with: sudo dnf install python3" ;;
    *" arch "*|*" manjaro "*|*" endeavouros "*|*" garuda "*|*" cachyos "*) echo "Install it with: sudo pacman -S python" ;;
    *" opensuse "*|*" opensuse-leap "*|*" opensuse-tumbleweed "*|*" suse "*) echo "Install it with: sudo zypper install python3" ;;
    *" alpine "*) echo "Install it with: sudo apk add python3" ;;
    *" void "*) echo "Install it with: sudo xbps-install python3" ;;
    *" gentoo "*) echo "Install it with: sudo emerge --ask dev-lang/python" ;;
    *" nixos "*) echo "Start a shell with it: nix-shell -p python3" ;;
    *) echo "Install Python 3.10 or newer with your package manager, or from https://www.python.org/downloads/" ;;
esac
echo "Your distribution may only offer an older version. In that case use the installer from python.org."
printf "Press Enter to close this window. "
read -r _
exit 1
