#!/bin/sh
# Starts the web interface on a Mac.
# Double-click it in Finder. The first time, your Mac may ask first: right-click the file and pick Open.
# If it still will not open, open Terminal in this folder and type: sh boot-mac.command

cd "$(dirname "$0")" || exit 1

for cmd in python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        exec "$cmd" boot.py "$@"
    fi
done

echo "Python 3.10 or newer was not found."
echo "Install it with: brew install python"
echo "Or download the installer from https://www.python.org/downloads/"
echo "The python3 that macOS offers to install with the developer tools is often too old."
printf "Press Enter to close this window. "
read -r _
exit 1
