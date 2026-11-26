# Minecraft Recon

[![CI](https://github.com/Pnn2486/minecraft-recon-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Pnn2486/minecraft-recon-framework/actions/workflows/ci.yml)
![Python 3.10 to 3.15](https://img.shields.io/badge/python-3.10%20to%203.15-blue)
![Runtime dependencies: none](https://img.shields.io/badge/runtime%20dependencies-none-brightgreen)

Minecraft Recon lets you look at a Minecraft Java server from the outside. You open a page in your browser and add the address of your server. From there you can see whether it is online and who is playing, send commands to its console, or join as a silent test player and watch what the server sends you. The only thing you need on your computer is Python, so there is nothing else to install.

It is meant for servers that belong to you, or ones you have written permission to test. The details are in [COPYING.md](./COPYING.md).

## Contents

1. [Install and start](#1-install-and-start)
2. [Requirements and supported systems](#2-requirements-and-supported-systems)
3. [What you can do with it](#3-what-you-can-do-with-it)
4. [The web page and the launchers](#4-the-web-page-and-the-launchers)
5. [Using the command line](#5-using-the-command-line)
6. [The settings file](#6-the-settings-file)
7. [When something goes wrong](#7-when-something-goes-wrong)
8. [Limits and test status](#8-limits-and-test-status)
9. [Project layout](#9-project-layout)
10. [How the protocols work](#10-how-the-protocols-work)
11. [Using it from Python code](#11-using-it-from-python-code)
12. [Other tools](#12-other-tools)
13. [References](#13-references)

Sections 1 to 8 are for using the tool. Sections 9 to 13 are for people who want to read or change the code.

---

## 1. Install and start

The quickest way is to download the project, unzip it and double-click the launcher for your system. If you would rather use git, pip or Docker, those are explained further down. Whichever way you go, you need Python 3.10 or newer on your computer first.

### 1.1 Do you already have Python?

Open a terminal. On Windows you search for Command Prompt, and on a Mac in open the Terminal app. Type `python3 --version` on a Mac or Linux. On Windows type `py --version`, and if Windows does not know that command, try `python --version`. If the response is 3.10 or higher, such as 3.11 or 3.12, you already have what you need and can skip ahead. If it is lower, or you only get an error, install Python with the command for your system from this table below.

| System | How to install Python |
|---|---|
| Windows | Download the installer from [python.org/downloads](https://www.python.org/downloads/) and tick "Add python.exe to PATH" on the first screen. If you prefer the terminal, `winget install Python.Python.3.12` does the same. |
| macOS | Download the installer from python.org, or run `brew install python` if you use Homebrew. The `python3` that came with your Mac is usually too old. |
| Ubuntu, Debian, Mint, Pop!_OS, Kali | `sudo apt install python3` |
| Fedora, RHEL, Rocky, AlmaLinux | `sudo dnf install python3` |
| Arch, Manjaro, EndeavourOS | `sudo pacman -S python` |
| openSUSE | `sudo zypper install python3` |
| Alpine | `sudo apk add python3` |
| Void, Gentoo, NixOS | `sudo xbps-install python3`, `sudo emerge --ask dev-lang/python` or `nix-shell -p python3` |

Some older Linux releases only offer an old Python in their normal repositories. If that happens to you, use the installer from python.org instead. Phones and tablets have not been tried.

One thing to keep in mind for the rest of this page: the Python command has a different name on different systems. On a Mac or Linux it is `python3`. On Windows it is `py` (the python.org installer sets that up for you), and `python` also works if you ticked "Add python.exe to PATH". Windows has a `python3` command too, but it usually just opens the Microsoft Store, so don’t use it there. Wherever a command below differs between systems, you will see one version for each.

### 1.2 Download the ZIP and double-click (the easiest way)

On the GitHub page of this project, click the green Code button and then Download ZIP. Unzip the file,  on Windows right-click it and choose Extract All, on MacOS double-click it, and on Linux right-click it and choose Extract Here. Then open the new folder, open the `launchers` folder inside it, and run the file that matches your system.

| System | File | What to expect |
|---|---|---|
| Windows | `boot-windows.bat` | Windows may show a warning. Click More info and then Run anyway. |
| macOS | `boot-mac.command` | The first time, right-click the file and choose Open, because your Mac does not trust downloaded files by default. |
| Linux | `boot-linux.sh` | Open it from your file manager, or type `sh boot-linux.sh` in a terminal inside the `launchers` folder. |
| Any other system | `boot.py` | Type `python launchers/boot.py` in a terminal inside the main folder of the project. |

A black window appears and your browser opens the page at `http://127.0.0.1:8765/`. That address only works on your own computer. When you are done, close the black window, or click on it and press Ctrl+C.

Sometimes a double-click on a Mac or Linux does nothing, because files taken out of a ZIP can lose the mark that says they may be run. In that case open a terminal inside the `launchers` folder and type `sh boot-mac.command` or `sh boot-linux.sh`. Typing `chmod +x boot-linux.sh boot-mac.command` once gives the mark back, and then double-clicking works.

### 1.3 Clone it with git

If you use git, you can get the project and start it with three commands:

The first two lines are the same on any system:

```bash
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
```

The last line starts the page, and it depends on your system.

```bash
# macOS and Linux
python3 launchers/boot.py

# Windows (PowerShell or Command Prompt)
py launchers\boot.py
```

When a new version comes out, run `git pull` inside the same folder to get it. You can add `--port 9000` to use another port, or `--no-browser` if you don’t want the page to open by itself.

### 1.4 Run it without installing anything

The launchers do exactly this for you. If you would rather type it yourself, go to the project folder and run one of these:

```bash
# macOS and Linux
PYTHONPATH=source python3 -m recon.gui          # the web page
PYTHONPATH=source python3 -m recon.cli --help   # the command line
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="source"
py -m recon.gui
py -m recon.cli --help
```

```bat
rem Windows Command Prompt
set PYTHONPATH=source
py -m recon.gui
py -m recon.cli --help
```

On Windows, the `PYTHONPATH` line only lasts as long as that window is open, so type it again in a new window.

### 1.5 Install it with pip

If you want the commands to work from any folder, you can install the project. That gives you two new commands: `recon` for the command line and `recon-gui` for the web page.

```bash
# macOS and Linux, straight from GitHub
python3 -m pip install git+https://github.com/Pnn2486/minecraft-recon-framework.git

# macOS and Linux, from a folder you downloaded or cloned (add -e if you plan to edit the code)
python3 -m pip install .
```

```bat
rem Windows, straight from GitHub
py -m pip install git+https://github.com/Pnn2486/minecraft-recon-framework.git

rem Windows, from a folder you downloaded or cloned (add -e if you plan to edit the code)
py -m pip install .
```

The GitHub version needs git installed. After either one, `recon-gui` opens the page and `recon --help` lists the command line options.

If you want to keep it apart from your other Python projects, create a virtual environment first and switch it on, then run the pip command inside it.

```bash
# macOS and Linux
python3 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

```bat
rem Windows Command Prompt
py -m venv .venv
.venv\Scripts\activate.bat
```

PowerShell sometimes refuses to run the activate script because of its security settings. If you see that error, use Command Prompt for this step instead. Another option is [pipx](https://pipx.pypa.io/), which creates the environment for you with one command on every system: `pipx install git+https://github.com/Pnn2486/minecraft-recon-framework.git`. To remove the project again, type `pip uninstall minecraft-recon-framework`.

### 1.6 Use a release file

Once a version has been released, the Releases page of the project offers a ready-made package, a `.whl` file and a `.tar.gz` file. Download the `.whl` file and install it with `python3 -m pip install` followed by the file name on a Mac or Linux, or `py -m pip install` followed by the file name on Windows.

### 1.7 Use Docker or Podman

This only gives you the command line, because the web page listens inside the container where your browser cannot reach it.

```bash
docker build -f Containerfile -t minecraft-recon-framework:latest .
docker run --rm minecraft-recon-framework:latest --host 10.0.0.5 --port 25565 --mode ping --quiet
```

The build runs the tests first, so a broken copy will not finish building. If your server runs on the same machine as Docker, use that machine's network address instead of `127.0.0.1`, since inside the container `127.0.0.1` means the container itself. Replace `docker` with `podman` if that is what you use.

### 1.8 Making sure it works

These two commands tell you quickly whether everything is in place. The first prints the program name and its version, and the second lists every system the launcher knows, with the Python install command for each.

```bash
# macOS and Linux
python3 launchers/boot.py --version
python3 launchers/boot.py --list

# Windows
py launchers\boot.py --version
py launchers\boot.py --list
```

If you want to run the project's own tests, use the line for your system from inside the project folder. They only talk to small fake servers on your own computer, so nothing goes out to the internet.

```bash
# macOS and Linux
PYTHONPATH=source python3 -m unittest discover -s tests -v
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="source"; py -m unittest discover -s tests -v
```

```bat
rem Windows Command Prompt
set PYTHONPATH=source && py -m unittest discover -s tests -v
```

## 2. Requirements and supported systems

The tool talks to servers over plain network connections. It does not start Minecraft or Java and draws nothing in 3D, so it needs far less than the game itself.

### 2.1 Hardware (minimum and recommended)

These figures are estimates, not measurements. The tool is small, so almost any computer is enough.

| Hardware component | Minimum specification (single-node audit) | Recommended specification (concurrent / CI / container fleet) | Technical justification |
| :--- | :--- | :--- | :--- |
| **CPU cores / threads** | 1 vCPU / 1 hardware thread (`>= 1.5 GHz`, x86_64 or ARM64, 64-bit OS) | 2-4 vCPUs / 4+ hardware threads (`>= 2.4 GHz`) | Single-target probes are I/O-bound waiting on network RTT; multi-threaded batch auditing and `zlib` stream decompression (`0x03`) scale across CPU threads. |
| **System memory (RAM)** | `128 MB` free RAM (`~20-40 MB` active CPython `3.10+` resident set size, plus headroom) | `1 GB - 2 GB` RAM | `ghost.py` processes `zlib` buffers in-memory; `1 GB+` prevents OOM kills when running inside Docker/Podman containers or parallel cron jobs. |
| **GPU / compute threads** | **0 GPU threads (none / headless)** | **0 GPU threads (none / headless)** | Unlike the official Minecraft client, this framework bypasses LWJGL, OpenGL, and Vulkan entirely. It runs natively on headless Linux servers, SSH terminals, and cloud VMs without a GPU or display server (`X11`/`Wayland`). |
| **Disk storage** | `200 MB` free disk space (includes a Python `3.10+` install if you don't already have one) | `1 GB` free disk space (if building OCI/Docker images or keeping logs) | Pure-Python source tree is `< 100 KB`; the interpreter is the main cost. Extra space is only required if storing JSON audit logs or Alpine Linux container layers. |
| **Network interface** | `5 Mbps` IPv4/IPv6 NIC | `100 Mbps+` low-jitter Ethernet / VPC interface | Play-state `ghost` mode receives continuous chunk, entity, and chat packets from active servers (roughly `50-250 KB/s`, occasionally up to `~2 Mbps`, per session; an estimate, not a measurement); `ping`, `query` and `rcon` use only a few KB per run. |
| **Network reliability** | Round-trip time `< 500 ms` to target, packet loss `< 5%`, working DNS resolution | Round-trip time `< 100 ms`, packet loss `< 1%` | The default socket timeout is `5.0 s`; unacknowledged UDP `query` datagrams and long-running `ghost` sessions fail on unstable or heavily lossy links. |

### 2.2 Supported operating systems

* **Linux (primary production target):**
  * Ubuntu `22.04 LTS`, `24.04 LTS` (Python `3.10+` ships by default)
  * Debian `12 (Bookworm)` or newer (Debian `11` ships Python `3.9` and needs a newer interpreter installed separately)
  * RHEL / AlmaLinux / Rocky Linux `8+` (install the `python3.11` package; the default `python3` is older), Fedora `38+`
  * Arch Linux, Kali Linux, Alpine Linux `3.18+` (musl libc supported)
* **macOS:**
  * macOS `12 (Monterey)`, `13 (Ventura)`, `14 (Sonoma)`, `15 (Sequoia)` on both **Apple Silicon (`arm64` / M1-M4)** and **Intel (`x86_64`)**. The system `python3` is older than `3.10`; install a current interpreter from python.org or Homebrew (`brew install python`).
* **Windows:**
  * Windows `10` (Build 19041+), Windows `11`, Windows Server `2019` / `2022` (via PowerShell, CMD, or WSL2).
* **Other systems (not tested):**
  * FreeBSD `13+` and OpenBSD `7+` should work with a Python `3.10+` build.
  * ARM boards such as the Raspberry Pi are just small Linux computers. Raspberry Pi OS `Bookworm` or newer (`ARMv7` / `aarch64`) follows the Linux notes above.
  * Apps that run Python on an iPad or iPhone (a-Shell, iSH) have not been tried.
  * The automatic tests run on Ubuntu, macOS and Windows only.

### 2.3 Software & runtime prerequisites

* **Python interpreter:** CPython `>= 3.10` (`3.11` or `3.12` recommended for optimal `socket` and `struct` performance). Python `3.9` and older are not supported.
* **Standard library modules (pre-installed with Python), including:** `socket`, `struct`, `zlib`, `hashlib`, `json`, `argparse`, `dataclasses`, `time`, `unittest`.
* **External `pip` packages required:** **None (`0`)**.
* **Optional tooling:**
  * `git` (for cloning and version control).
  * `docker` or `podman` (only if executing via `Containerfile`).
  * `jq` (optional command-line JSON processor for filtering `--mode ping` and `--mode query` output in Linux/macOS pipelines).

### 2.4 Network & firewall requirements

To audit a target node successfully, outbound traffic from your machine (and inbound rules on the target server's `iptables` / `nftables` / `ufw` / cloud security group) must permit:

* **TCP port `25565`** (or custom game port): Required for `--mode ping` and `--mode ghost`.
* **UDP port `25565`** (or custom `query.port`): Required for `--mode query`. Note that stateful firewalls must explicitly allow bidirectional **UDP** datagrams, not just TCP.
* **TCP port `25575`** (or custom `rcon.port`): Required for `--mode rcon`.

## 3. What you can do with it

The server status tool tells you whether the server is online, which Minecraft version it runs, how many players are on it and how quickly it answers. The server details tool goes further and shows the player list, the world name and the plugins, but only if the server has query turned on.

The console tool sends commands to your server over RCON. It also has a few ready-made sets of read-only commands (overview, performance, plugins, players and world) in case you just want a quick look without typing anything.

The test player joins the server without doing anything, shows you the chat messages it receives and can print a report about the session afterwards. It reads normal chat, system messages and signed player messages, for 46 versions between 1.8 and 26.1. It only works on servers that have `online-mode=false`, because it cannot log in to servers that check accounts with Mojang.

## 4. The web page and the launchers

### 4.1 The web page (`recon-gui`)

If you prefer buttons to command-line flags, start the web interface. It needs nothing extra to be installed.

```bash
python3 -m recon.gui          # or, after `pip install .`: recon-gui
```

This starts a small server on your own computer and opens `http://127.0.0.1:8765/` in your browser. If that port is busy it picks a free one and prints the address. The layout follows launchers such as Prism Launcher, with a modern look. Your saved servers are tiles in a grid, a toolbar on top adds, edits and removes them, and a side panel on the right shows the selected server and its four tools: server status (ping), server details (query), console (RCON) and test player (ghost client). Pick a tile, pick a tool, tick the box that says you own the server or have permission to test it, and press the green button at the bottom. Double-clicking a tile runs the chosen tool.

* **Chat and diagnostics.** The test player result shows the chat it saw as a list of messages, plus an optional diagnostics section. Plain, signed, system and disguised chat is decoded for the versions in the packet table, including the NBT text of 1.20.3 and newer. Signed chat is not encrypted, so its text is readable. Signatures are skipped, not checked. The encryption of an online-mode connection is not touched, and the test player cannot join such servers. A chat packet that does not match any known layout is listed as not decoded, with its readable text shown in the diagnostics.
* **Quick checks.** The console tool has a list of read-only command sets (overview, performance, plugins, players, world). They run on one RCON connection and each answer is shown under its command.
* **Same code as the command line.** The page runs the same functions as `recon`, so the same checks and limits apply. It shows ping and query results as cards and everything else as text.
* **Only on this computer.** The server listens on `127.0.0.1`, rejects other host names, needs a random token that is created at every start, and refuses requests that come from other web sites. Do not put it behind a reverse proxy or expose it to a network.
* **One job at a time.** A test player run lasts at most 120 seconds by default (you can raise that in the settings file, see section 6) and cannot be cancelled early. Close the program with Ctrl+C to stop everything.
* **Saved servers.** The server list (name, address, ports, icon and last status) is stored in this browser only. The RCON password is only kept in the form while the page is open. It is never saved or shown in the results.
* **Options.** `--port 9000` picks the port and `--no-browser` stops it from opening the browser.
* **Status.** The page was checked in a headless Chromium browser together with fake servers. It has not been used against a real Minecraft server. The chat decoder was written from the published packet layouts and tested only with hand-built packets, so a version can still differ in practice.

### 4.2 The double-click launchers

These files start the web interface without installing anything. Python 3.10 or newer must already be on the computer. If it is missing, the window prints the install command for your system.

| System | File | How to start it |
|---|---|---|
| Windows | `boot-windows.bat` | Double-click it. If Windows shows a blue warning, choose More info, then Run anyway. |
| macOS | `boot-mac.command` | Double-click it. The first time, right-click it and choose Open. |
| Linux (any distribution) | `boot-linux.sh` | Open it from your file manager, or run `sh boot-linux.sh`. |
| Anything else | `boot.py` | Run `python launchers/boot.py` from the main folder of the project. |

`boot.py` is the adapter behind them. It detects the system, finds the distribution on Linux (Debian, Ubuntu, Mint, Fedora, RHEL, Arch, openSUSE, Alpine, Void, Gentoo, NixOS and the systems based on them), checks the Python version and starts `recon-gui`. `python launchers/boot.py --list` shows the install hints for every system, and `python launchers/boot.py --os mac` shows the hint for one. Options such as `--port 9000` or `--no-browser` are passed on to the interface.

Files that come from a download or a web upload on GitHub lose their "runnable" mark. If a double-click does nothing on macOS or Linux, open a terminal in the `launchers` folder and type `sh boot-mac.command` or `sh boot-linux.sh` once, or `chmod +x boot-linux.sh boot-mac.command` to make them double-clickable.

## 5. Using the command line

### 5.1 Examples

If you do not want the web page, everything is also available in the terminal. These examples assume you are inside the project folder:

```bash
# macOS and Linux
PYTHONPATH=source python3 -m recon.cli --host 127.0.0.1 --mode ping
PYTHONPATH=source python3 -m recon.cli --host 127.0.0.1 --mode ghost --diagnostics
PYTHONPATH=source python3 -m recon.cli --host 127.0.0.1 --mode rcon --preset overview
```

```powershell
# Windows PowerShell (the first line only has to be typed once per window)
$env:PYTHONPATH="source"
py -m recon.cli --host 127.0.0.1 --mode ping
py -m recon.cli --host 127.0.0.1 --mode ghost --diagnostics
py -m recon.cli --host 127.0.0.1 --mode rcon --preset overview
```

```bat
rem Windows Command Prompt (the first line only has to be typed once per window)
set PYTHONPATH=source
py -m recon.cli --host 127.0.0.1 --mode ping
py -m recon.cli --host 127.0.0.1 --mode ghost --diagnostics
py -m recon.cli --host 127.0.0.1 --mode rcon --preset overview
```

If you installed the project with pip, you can type `recon` instead of the long part, for example `recon --host 127.0.0.1 --mode ping`, and skip the `PYTHONPATH` line. The complete list of options follows.

### 5.2 Options and exit codes

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | *Required* | Target hostname or IP address (`query` mode is IPv4 only) |
| `--mode` | `str` | *Required* | Protocol state machine: `ping`, `query`, `rcon`, `ghost` |
| `--port` | `int` | `25565` | Target TCP/UDP game port (`ping`, `query`, `ghost`) |
| `--rcon-port` | `int` | `25575` | Target TCP RCON port (`rcon` mode) |
| `--timeout` | `float` | `5.0` | Socket timeout in seconds |
| `--password` | `str` | *(unset)* | RCON authentication secret (required for `--mode rcon`). If it is not given, the `MC_RCON_PASSWORD` environment variable is used. The environment variable is safer, because command-line arguments are visible to other users and saved in shell history. |
| `--cmd` | `str` | `"list"` | Server console command for RCON. Repeat the option to run several commands on one connection |
| `--preset` | `str` | *(unset)* | Ready-made read-only RCON command set: `overview`, `performance`, `plugins`, `players` or `world`. Commands the server does not know are answered with the server's own error text |
| `--username` | `str` | `"AuditNode"` | Username sent in the login start packet (`0x00`) for `ghost` mode |
| `--protocol-version` | `str` | `auto` | Version for `ghost` mode: a Minecraft version (`1.16.5`), a protocol number (`754`), or `auto` to detect it from the server with a status ping. Versions without a profile are rejected (see section 10.4) |
| `--list-versions` | `flag` | `False` | Print every known Minecraft version with its protocol number and whether ghost mode supports it, then exit |
| `--config` | `path` | *(unset)* | Settings file to use (see section 6). |
| `--duration` | `int` | `30` | Socket read-loop TTL in seconds for `ghost` mode |
| `--diagnostics` | `flag` | `False` | Print a session report after `ghost` mode: timeline, packet counts, keep-alive timing and how many chat packets were decoded. Every report line starts with `[#]` |
| `--quiet` | `flag` | `False` | Suppress compliance banner on `stderr` for clean JSON piping |

* **Exit code `0`:** Handshake and payload deserialization succeeded.
* **Exit code `1`:** `ReconError`, `ProtocolFramingError`, `AuthenticationError`, `UnsupportedProtocolError` (ghost mode), or socket timeout.
* **Exit code `2`:** Invalid or missing mandatory CLI flag, or a value out of range (for example a port outside 1-65535, or a timeout of 0 or less).
* **Exit code `130`:** Operator `SIGINT` (`Ctrl+C`) termination.

## 6. The settings file

Most limits and defaults can be changed in one plain text file, `settings.ini`, in the main folder of the project. Open it in any text editor, change a value, save it and start the program again. The file is optional. If you delete it, the built-in values are used, and they are the same as the ones in the shipped file. Lines that start with `#` are comments that explain each setting.

### 6.1 Example: letting the test player stay for 3 hours

Three hours is 10800 seconds. Two settings are involved, because the web page has a safety limit on top of the default.

```ini
[limits]
max_duration_seconds = 10800

[defaults]
duration = 10800
```

The first one raises the longest session the web page accepts. The second one makes 10800 the default, so you don't have to type it each time. On the command line, only `duration` matters, because the command line has no upper limit of its own. The highest value the file accepts is 86400 (24 hours). A server can still kick the test player out earlier, for example for being idle or by an anti-bot plugin, and the report says why the session ended.

### 6.2 Where the program looks for it

1. The file you name with `--config`, for example `python3 launchers/boot.py --config my-settings.ini` or `recon --config my-settings.ini --host 127.0.0.1 --mode ping`.
2. The file named by the `RECON_CONFIG` environment variable.
3. `settings.ini` in the folder you started the program from.
4. `settings.ini` in the main folder of the project, the one that holds `source` and `launchers`.

If you installed the project with pip, there is no project folder, so use the third place (your current folder) or one of the first two. When the web page starts, it prints which file it loaded.

### 6.3 Mistakes are never ignored

A typo in a section or setting name, a value that is not a number, or a number outside the allowed range stops the program with a message that names the setting. For example, `max_durtion_seconds` gives `unknown setting max_durtion_seconds in [limits]. Did you mean max_duration_seconds?`, and the command line exits with code 2.

### 6.4 What can't be changed here

Some safety measures are fixed on purpose. The web page only listens on `127.0.0.1`, it always asks you to confirm that you own the server or have permission, it always checks its secret token and the host and origin of every request, and it never saves the RCON password. The size of one request to the page is fixed as well.

### 6.5 All settings

Every setting, its default and what it accepts. The file has the same list with comments.

| Section | Name | Default | Accepts | What it does |
|---|---|---|---|---|
| `[defaults]` | `port` | `25565` | 1 to 65535 | Game port of the server. |
| `[defaults]` | `rcon_port` | `25575` | 1 to 65535 | RCON port of the server. |
| `[defaults]` | `timeout` | `5` | 0.1 to 3600 | Seconds to wait for the server to answer. |
| `[defaults]` | `username` | `AuditNode` | 1 to 16 letters, digits or underscores | Name of the test player. |
| `[defaults]` | `protocol_version` | `auto` | see description | Version of the test player: `auto`, a protocol number or a version such as `1.16.5`. |
| `[defaults]` | `duration` | `30` | 1 to 86400 | Seconds the test player stays connected. |
| `[defaults]` | `diagnostics` | `false` | true or false | Print the session report after a test player run. |
| `[defaults]` | `quiet` | `false` | true or false | Hide the banner at the start of command line runs. |
| `[limits]` | `max_timeout_seconds` | `60` | 1 to 3600 | Longest timeout the web page accepts. |
| `[limits]` | `max_duration_seconds` | `120` | 1 to 86400 | Longest test player session the web page accepts. |
| `[limits]` | `max_command_chars` | `1000` | 1 to 10000 | Longest console command the web page accepts. |
| `[limits]` | `max_password_chars` | `256` | 1 to 1024 | Longest RCON password the web page accepts. |
| `[limits]` | `max_output_lines` | `5000` | 100 to 1000000 | How many output lines one run keeps. Extra lines are cut off. |
| `[limits]` | `max_line_chars` | `100000` | 100 to 1000000 | How many characters one output line keeps. |
| `[limits]` | `keep_jobs` | `10` | 1 to 100 | How many finished runs the page remembers. |
| `[web]` | `port` | `8765` | 1 to 65535 | Port of the web page. If it is busy, a free one is used. |
| `[web]` | `open_browser` | `true` | true or false | Open the browser by itself when the page starts. |
| `[chat]` | `show_player_chat` | `true` | true or false | Show chat from players. |
| `[chat]` | `show_system_chat` | `true` | true or false | Show messages from the server (joins, leaves, announcements). |
| `[chat]` | `show_disguised_chat` | `true` | true or false | Show chat sent by commands such as `/say` or `/tellraw`. |
| `[chat]` | `show_plain_chat` | `true` | true or false | Show chat from servers older than 1.19. |
| `[chat]` | `show_kind_label` | `true` | true or false | Put the kind in front of each line, like `(player)`. |
| `[chat]` | `show_undecoded` | `true` | true or false | Show a line for packets that could not be decoded. |
| `[chat]` | `timestamps` | `false` | true or false | Put the time in front of each line. |
| `[output]` | `show_keep_alives` | `true` | true or false | Show a line each time the test player answers a keep-alive. |
| `[diagnostics]` | `top_packets` | `12` | 1 to 100 | How many of the most common packets the report lists. |
| `[diagnostics]` | `max_undecoded_samples` | `5` | 0 to 50 | How many undecoded chat packets get a preview in the report. |

## 7. When something goes wrong

If the window says Python was not found, install Python 3.10 or newer. The window prints the right command for your system. If the page does not open by itself, type `http://127.0.0.1:8765/` into your browser. When that port is already in use, the window shows the address it picked instead.

If the status works but the server details do not, the server probably has query turned off, which is the default. Set `enable-query=true` in `server.properties`, restart the server and make sure the UDP port is open. If the console says your password was rejected, compare it with `rcon.password` in `server.properties` and check that `enable-rcon=true` is set.

If the test player says the server wants authentication, the server runs with `online-mode=true`. The test player cannot join those servers, and that is on purpose. If it says your version is not supported, choose the version yourself in the page, or run `python3 -m recon.cli --list-versions` (`py -m recon.cli --list-versions` on Windows) to see which ones are known.

## 8. Limits and test status

Please read this before relying on the tool.

### 8.1 What has and has not been tested

* **Automated tests use fake servers only.** The test suite (`tests/test_protocols.py`) starts small imitation servers on `127.0.0.1` that were written from the published protocol specifications. They prove the code follows those specifications. They do **not** prove it works against every real server.
* **No mode has been verified against a real Minecraft server by the authors.** This applies to `ping`, `query`, `rcon` and `ghost` alike. Treat the first run against your own server as the real test, and open an issue if something is different.
* **Python versions:** The code is written for Python `3.10+`. CI runs `3.10` through `3.15` on Linux, macOS and Windows, and the oldest and a recent version on more system versions (Ubuntu 22.04 and 24.04, Windows 2022 and 2025, macOS 15 and 26, and ARM and Intel processors). The tests also run inside 25 Linux containers (Debian, Ubuntu, Fedora, Rocky, Alma, Oracle, CentOS Stream, Amazon Linux, openSUSE, Alpine, Arch, Kali and Gentoo).

### 8.2 Minecraft version support

| Mode | Version dependence | Status |
| :--- | :--- | :--- |
| `ping` | Version independent. | Expected to work on any Java Edition server. |
| `query` | Version independent. Needs `enable-query=true` in `server.properties` and an open UDP port. | Expected to work on any server that has query enabled. |
| `rcon` | Version independent. Needs `enable-rcon=true` and an RCON password. | Expected to work on any server that has RCON enabled. |
| `ghost` | **Version specific**, because packet IDs change between releases. | Protocols `47` (1.8) to `775` (26.1), 46 in total (see section 10.4). Every other `--protocol-version` is rejected before connecting. |

### 8.3 Limits of the test player (`ghost` mode)

* **Offline-mode servers only.** The target must have `online-mode=false`. Servers that require Mojang authentication reply with an Encryption Request, and the client stops with `OnlineModeRequiredError`. It does not implement encryption or authentication.
* **Unsupported versions:** Minecraft 1.7.x (protocols `4` and `5`), 1.9.1, 1.14.2, 26.2, 26.3 and all snapshots have no packet table, although their names are known (`recon --list-versions` marks them). Supporting one means adding a row to `source/recon/protocols/ghost_profile_data.py`.
* **Chat decoding is best effort.** It was written from the published packet layouts and tested with hand-built packets only. A packet that does not match any known layout is reported as not decoded, with its size, and the diagnostics show its readable text. Signatures are skipped, not checked.
* **Passive behavior.** The client echoes keep-alive and ping packets and ignores world data. It does not move, send chat, or load chunks. Servers with anti-bot plugins, whitelists, or proxies (BungeeCord, Velocity) may kick it.
* **Listening window.** Sessions end after `--duration` seconds. If the server sends nothing for longer than `--timeout`, the session stops with a timeout error (exit code `1`).
* **Automatic detection can be wrong behind proxies.** Proxies and multi-version plugins may report a different protocol number than the server behind them. If login fails, pass `--protocol-version` explicitly.

### 8.4 Other limitations

* **Java Edition only.** Bedrock Edition uses different protocols and is not supported.
* **Addressing.** The UDP `query` mode is IPv4 only. The TCP modes (`ping`, `rcon`, `ghost`) accept IPv4 or IPv6. SRV record lookups (`_minecraft._tcp`) are not performed, so use the real host and port.
* **`tps` is not a vanilla command.** It exists only on Paper, Spigot and compatible servers.
* **Legal responsibility stays with you.** Use the tool only on servers you own or have written permission to test. See [COPYING.md](./COPYING.md).

### 8.5 Test layers

* **Fast tests (every push and pull request):** the loopback suite in `tests/`, a lint and type check (`ruff`, `mypy`), a coverage check that fails below 80 percent, and a build of the package that is installed and smoke tested in a clean environment.
* **Real server test (manual):** the `Real server integration test` workflow starts a disposable offline-mode server in Docker and runs `ping`, `query`, `rcon` and `ghost` against it. It only runs when you start it from the Actions tab, so ordinary CI does not depend on Docker. It has not been run yet, so the first run may need small fixes.
* **Testing safely on your own machine:** to try the tool without touching anyone else's server, run your own local server with the same settings the workflow uses (`online-mode=false`, query and RCON enabled) and point the tool at `127.0.0.1`.

### 8.6 Security notes

* **RCON password.** The password is never printed, logged or included in error messages. Prefer the `MC_RCON_PASSWORD` environment variable to `--password`.
* **Timeouts and retries.** Every connection has a timeout (default 5 seconds). There are no automatic retries on purpose, so a failing target is never hit repeatedly.
* **Web interface.** `recon-gui` listens on `127.0.0.1` only and checks the host name, a per-run token and the origin of every request. A connection that stays silent for 15 seconds is dropped, and on Windows the port is not shared with other programs. See section 4.1.
* **Hosts and ports.** Ports must be 1 to 65535. Host names must be 1 to 253 characters with no spaces or control characters, and they can't start with a dash.
* **Hostile servers.** A server can announce any packet size it likes, so the client refuses anything bigger than 8 MiB, which is more than Minecraft itself sends, and it never unpacks a compressed packet past that size. A status reply that is not a JSON object is rejected.
* **Proxies and DNS.** The tool ignores proxy settings and connects directly. It resolves host names with the operating system and does not look up SRV records, so use the real host and port.

---

## 9. Project layout

- **source**
  - **recon** - core Python package (PEP 420)
    - `cli.py` - argument parser, validation & dispatch entry point
    - `gui.py` - local web interface server (`recon-gui`)
    - `settings.py` - reads `settings.ini` (the table of every setting, its default and its limits)
    - **web** - the page the web interface shows (`index.html`, `style.css`, `app.js`, `favicon.svg`, and the Inter font files with their license)
    - `exceptions.py` - structured exception hierarchy (`ReconError`, etc.)
    - **utils**
      - `varint.py` - Base-128 VarInt, `recv_exact` & UUID v3 generators
      - `versions.py` - protocol number <-> Minecraft version name lookup
      - `nbt.py` - reader for the binary text format used by newer versions
      - `text.py` - turns chat text components into plain text
    - **protocols**
      - `ping.py` - TCP `0x00` Status + `0x01` RTT latency
      - `query.py` - UDP `0xFEFD` GameSpy4 challenge/response
      - `rcon.py` - TCP little-endian Source RCON client
      - `ghost.py` - TCP play-state client (zlib, configuration phase, keep-alive, chat)
      - `ghost_profiles.py` - per-version profile logic for `ghost.py`
      - `chat.py` - decodes plain, signed, system and disguised chat packets
      - `diagnostics.py` - session report for the ghost client
      - `rcon_presets.py` - ready-made read-only RCON command sets
      - `ghost_profile_data.py` - packet ID table, one row per protocol number
    - `__main__.py` - makes `python -m recon` work
- **.github**
  - `dependabot.yml` - weekly update pull requests for GitHub Actions and pip
  - `PULL_REQUEST_TEMPLATE.md` - checklist shown when you open a pull request
  - **ISSUE_TEMPLATE** - the form for bug reports
  - **workflows**
    - `ci.yml` - tests on Linux, macOS and Windows (several versions of each, Intel and ARM) with Python 3.10-3.15, plus lint, type check, coverage and a package build check
    - `linux-distros.yml` - runs the tests inside the Linux images listed in `tests/distros.json`
    - `integration.yml` - manual test against a real Minecraft server in Docker
    - `release.yml` - builds the package and creates a GitHub release when a version tag is pushed
- **program_info**
  - `org.recon.Framework.json` - protocol & port manifest
- **launchers**
  - `boot.py` - starts the web interface on any system (detects the system and checks Python)
  - `boot-windows.bat`, `boot-mac.command`, `boot-linux.sh` - double-click launchers that call `boot.py`
- **scripts**
  - `run_recon.py` - automated multi-protocol audit script
  - `packet_inspector.py` - hex + ASCII wire-frame inspector
- **tests**
  - `test_varint.py` - unit tests for serialization & framing
  - `test_protocols.py` - loopback tests for ping, query, RCON, ghost and CLI validation
  - `test_gui.py` - tests for the web interface server, its safety checks and its files
  - `test_hardening.py` - tests for the size limits on what a server can send and for option handling
  - `distros.json` - the Linux images the `linux-distros.yml` workflow tests in
  - `run_in_container.sh` - runs the tests inside one of those images
  - `test_boot.py` - tests for the launcher: system detection, install hints and the launcher files
  - `test_settings.py` - tests for the settings file and everything that reads it
  - `test_chat.py` - tests for the NBT and text readers, the chat decoder, diagnostics and RCON presets

- `settings.ini` - optional settings (limits and defaults), see section 6
- `pyproject.toml` - build spec & CLI entry point
- `Containerfile` - Docker / Podman container spec
- `README.md` - this file
- `CONTRIBUTING.md` - pull request & coding standards
- `SECURITY.md` - how to report a security problem
- `CHANGELOG.md` - what changed in each version
- `CODE_OF_CONDUCT.md` - community conduct rules & ethical-use standard
- `COPYING.md` - liability disclaimer
- `LICENSE` - authorized use license
- `.editorconfig`, `.gitattributes`, `.gitignore` - other necessary files

## 10. How the protocols work

### 10.1 Protocol 1: TCP server list ping (`source/recon/protocols/ping.py`)

Every modern Minecraft TCP packet is prefixed with a Base-128 `VarInt` specifying the exact byte length of `Packet ID + Payload`. All socket reads use `recv_exact()` to reassemble fragmented TCP segments deterministically.

| Packet phase | Direction | Packet ID | Wire payload structure |
| :--- | :--- | :--- | :--- |
| **1. Handshake** | Client -> Server | `0x00` | `VarInt(Protocol=767)` + `String(Host)` + `uint16_be(Port)` + `VarInt(NextState=1)` |
| **2. Status request** | Client -> Server | `0x00` | Empty payload (`b"\x01\x00"` wire frame) |
| **3. Status response** | Server -> Client | `0x00` | `String(UTF-8 JSON Descriptor)` |
| **4. Latency ping** | Client -> Server | `0x01` | `int64_be(Unix Epoch Milliseconds)` (`>q`) |
| **5. Latency pong** | Server -> Client | `0x01` | Echoed `int64_be` payload used to compute `latency_ms` |

The CLI adds one readable field to the server's reply, `version.minecraft_versions` (for example `"1.21 - 1.21.1"`), so the protocol number does not have to be looked up by hand.

---

### 10.2 Protocol 2: UDP GameSpy4 full stat query (`source/recon/protocols/query.py`)

GameSpy4 runs over unconnected UDP datagrams (`SOCK_DGRAM`) and enforces a stateless token handshake:

1. **Challenge request (`Client -> Server`, 7 bytes):**
   `Magic (0xFEFD, >H)` + `Type (0x09, B)` + `SessionID & 0x0F0F0F0F (>I)`.
2. **Challenge response (`Server -> Client`):**
   `Type (0x09, B)` + `SessionID (>I)` + `Null-terminated ASCII integer token`.
3. **Full stat request (`Client -> Server`, 15 bytes):**
   `Magic (0xFEFD, >H)` + `Type (0x00, B)` + `SessionID (>I)` + `ChallengeToken (>i, signed)` + `Padding (0x00000000, 4B)`.
4. **Full stat response (`Server -> Client`):**
   * **Header (`16 bytes`):** `\x00` + `SessionID (4B)` + `b"splitnum\x00\x80\x00"`.
   * **K/V metadata:** Null-delimited (`\x00`) alternating key/value strings.
   * **Binary boundary (`12 bytes`):** `b"\x00\x00\x01player_\x00\x00"`.
   * **Player array:** Null-delimited (`\x00`) online usernames terminated by `\x00\x00`.

---

### 10.3 Protocol 3: TCP Source RCON (`source/recon/protocols/rcon.py`)

Valve Source RCON frames integers in **32-bit signed little-endian** (`<i`) byte order:

| Byte offset | Field | Type (`struct`) | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | `Size` | `int32` (`<i`) | Byte length of remainder of frame (`4 + 4 + len(Body) + 2`) |
| `4..7` | `Request ID` | `int32` (`<i`) | Client correlation integer; server returns `-1` if authentication fails |
| `8..11` | `Type` | `int32` (`<i`) | `3` = `SERVERDATA_AUTH`, `2` = `SERVERDATA_EXECCOMMAND`, `0` = `SERVERDATA_RESPONSE_VALUE` |
| `12..N-2` | `Body` | `UTF-8` | Password or console command string |
| `N-2..N` | `Pad` | `2x Null` | Mandatory `b"\x00\x00"` terminator |

---

### 10.4 Protocol 4: offline play-state headless client (`source/recon/protocols/ghost.py`)

1. **Login handshake:** Transmits `Handshake (0x00)` with `Next State = 2`, followed by `Login Start (0x00)`. The bytes after the username depend on the version. For `protocol_version >= 764` (Minecraft 1.20.2+), `ghost.py` appends a 16-byte MD5 UUID v3 (`OfflinePlayer:<username>`). Versions 1.19 - 1.20.1 send "no signature / no UUID" flags instead.
2. **Zlib compression negotiation (`0x03`):** When the server transmits `Set Compression (0x03)`, all subsequent frames switch to RFC 1950 `zlib` framing:
   ```text
   [VarInt: Frame Length] [VarInt: Uncompressed Data Length] [zlib.compress(Packet ID + Payload)]
   ```
3. **Configuration phase (1.20.2+ only):** After the login success packet (`0x02`), the client sends `Login Acknowledged`, answers the server's Known Packs with an empty list, echoes Keep-Alive and Ping, and acknowledges `Finish Configuration` before entering Play.
4. **Play-state heartbeat loop:** Echoes the server's Keep-Alive token back unchanged (a VarInt before 1.12.2, a 64-bit integer from 1.12.2 on) to maintain socket persistence and reports incoming chat packets. Packet IDs come from the profile for the selected `--protocol-version`.

>[!NOTE]
> **Compatibility:** Packet IDs change in almost every Minecraft release, so `ghost` mode only runs versions that have a row in `ghost_profile_data.py`. Any other protocol number is rejected before the login connection is made. Protocol numbers are listed on the [Minecraft wiki](https://minecraft.wiki/w/Protocol_version).
>
> **Choosing a version:** by default (`--protocol-version auto`) the client sends a normal status ping first, reads the protocol number the server reports, shows it as a Minecraft version (for example `Minecraft 1.16.4 - 1.16.5 (protocol 754)`) and uses the matching profile. To skip detection, pass either a Minecraft version (`--protocol-version 1.16.5`) or a protocol number (`--protocol-version 754`), for example when a proxy or multi-version plugin reports a different number than the server behind it. Run `recon --list-versions` to print the full table.
>
> | Minecraft | Supported protocol numbers | Notes |
> | :--- | :--- | :--- |
> | 1.8 | `47` (1.8 - 1.8.9) |  |
> | 1.9 | `107` (1.9), `109` (1.9.2), `110` (1.9.3 - 1.9.4) |  |
> | 1.10 | `210` (1.10 - 1.10.2) |  |
> | 1.11 | `315` (1.11), `316` (1.11.1 - 1.11.2) |  |
> | 1.12 | `335` (1.12), `338` (1.12.1), `340` (1.12.2) |  |
> | 1.13 | `393` (1.13), `401` (1.13.1), `404` (1.13.2) |  |
> | 1.14 | `477` (1.14), `480` (1.14.1), `490` (1.14.3), `498` (1.14.4) |  |
> | 1.15 | `573` (1.15), `575` (1.15.1), `578` (1.15.2) |  |
> | 1.16 | `735` (1.16), `736` (1.16.1), `751` (1.16.2), `753` (1.16.3), `754` (1.16.4 - 1.16.5) |  |
> | 1.17 | `755` (1.17), `756` (1.17.1) |  |
> | 1.18 | `757` (1.18 - 1.18.1), `758` (1.18.2) |  |
> | 1.19 | `759` (1.19), `760` (1.19.1 - 1.19.2), `761` (1.19.3), `762` (1.19.4) | Login Start format changes at `759`, `760` and `761` |
> | 1.20 | `763` (1.20 - 1.20.1), `764` (1.20.2), `765` (1.20.3 - 1.20.4), `766` (1.20.5 - 1.20.6) | `764` and newer add the Configuration phase; `766` and newer add Known Packs |
> | 1.21 | `767` (1.21 - 1.21.1), `768` (1.21.2 - 1.21.3), `769` (1.21.4), `770` (1.21.5), `771` (1.21.6), `772` (1.21.7 - 1.21.8), `773` (1.21.9 - 1.21.10), `774` (1.21.11) | Known Packs in the Configuration phase |
> | 26.1 | `775` (26.1 - 26.1.2) |  |
> | anything else | 1.7.x, 1.9.1, 1.14.2, 26.2, 26.3, snapshots | **Not supported** (the version names are known, but there is no packet data yet) |
>
> The tables come from the community-maintained [`minecraft-data`](https://github.com/PrismarineJS/minecraft-data) project. Every profile passes a full login, configuration and play test against a fake local server, but **none has been run against a real Minecraft server by the authors**. Chat is decoded on every supported version (see the chat decoding part below), and any packet that doesn't fit a known layout is listed as not decoded. Servers that force a resource pack or run anti-bot plugins may still kick the client.
>
> **Adding a version:** append one row to `source/recon/protocols/ghost_profile_data.py` (the layout is explained at the top of that file) and add the version to the tests. No other file needs to change unless the new release alters the login sequence itself.

### 10.5 Adding support for a new Minecraft version

Two files hold the data, and both are plain tables. Nothing else needs to change unless the new release alters the login or configuration steps.

1. Add the release name to `source/recon/utils/versions.py`, in the tuple for its protocol number (or add a new line). This table only turns numbers into names, so it can list versions that ghost mode doesn't support. It follows `data/pc/common/protocolVersions.json` of [minecraft-data](https://github.com/PrismarineJS/minecraft-data), releases only, no snapshots.
2. Append one row to `source/recon/protocols/ghost_profile_data.py`. The packet IDs come from `data/pc/<version>/protocol.json` of the same project. The rows for 1.16.5 (754) and 1.21.1 (767) were also checked by hand against the published protocol documents. A row looks like this:

```text
(protocol, login_start_format, keep_alive_in, keep_alive_out, play_disconnect,
 chat_json_ids, chat_opaque_ids, text_is_json, configuration)
```

| Field | Meaning |
|---|---|
| `protocol` | The protocol number. The version name is not stored here. |
| `login_start_format` | What follows the username in the Login Start packet (table below). |
| `keep_alive_in`, `keep_alive_out` | Packet IDs of the keep-alive the server sends and the one the client sends back. |
| `play_disconnect` | Packet ID of the server's disconnect message in the play state. |
| `chat_json_ids` | Play packets whose first field is a JSON chat string. |
| `chat_opaque_ids` | Signed or NBT chat packets. The order of the IDs matters, see the chat decoding part. |
| `text_is_json` | `False` from protocol 765 (1.20.3) on, when text became NBT. |
| `configuration` | `None` before 1.20.2. Otherwise the tuple `(disconnect_in, finish_in, finish_ack_out, keep_alive_in, keep_alive_out, ping_in, pong_out, known_packs_in, known_packs_out, login_acknowledged_out)`, where the two `known_packs` values are `None` for 1.20.2 to 1.20.4. |

| `login_start_format` | Bytes after the username | Used by |
|---|---|---|
| `name` | nothing else | 1.8 to 1.18.2 |
| `name_sig` | a flag for "no signature data" | 1.19 |
| `name_sig_uuid` | "no signature data" and "no UUID" flags | 1.19.1 to 1.19.2 |
| `name_uuid_opt` | a "no UUID" flag | 1.19.3 to 1.20.1 |
| `name_uuid` | the 16-byte offline UUID | 1.20.2 and newer |

A protocol number without a row is rejected before any connection is made, so a wrong guess can't silently misread packets. Then add the version to the tests in `tests/test_protocols.py`.

### 10.6 Chat decoding

`source/recon/protocols/chat.py` reads the chat packets the test player receives in the play state.

Signed chat is only signed, not encrypted, so its text can be read and gets decoded. The encryption of an online-mode connection is a different thing. The test player never switches it on, so it cannot read such a connection. The signature bytes are skipped without being checked, because checking them would need Mojang session keys. To tell the chat packets apart, the decoder looks at the order of the IDs in `chat_opaque_ids`:

| Versions | Order of the opaque chat packets |
|---|---|
| 1.19 and 1.19.1 to 1.19.2 (759, 760) | player chat |
| 1.19.3 to 1.20.2 (761 to 764) | player chat, disguised chat |
| 1.20.3 and newer (765 and up) | system chat, player chat, disguised chat |

Player chat changed its layout several times, so the decoder tries the plausible layouts and keeps the first one that gives clean text. When nothing fits, the packet is printed as `packet 0xNN (N bytes, not decoded)` and the diagnostics show the readable text inside it. Text that arrives as NBT (1.20.3 and newer) is read by `source/recon/utils/nbt.py`. It never trusts a length from the network: depth, element counts and total size are capped, and every problem is reported as a framing error. `source/recon/utils/text.py` turns the result into plain text, fills in the common message keys (chat, joined, left and so on) and shows an unknown key as the key followed by its arguments, so nothing is lost silently.

### 10.7 Session diagnostics

`--diagnostics` (or the checkbox in the web page) prints a report after a test player session. Every line starts with `[#]`, so the page and scripts can pick the report out of the normal output. It shows the protocol and version, a timeline (connected, login success, play state), the compression threshold, how many packets and bytes arrived and how many per second, how many keep-alives were echoed and how often they came, how many chat packets were decoded or not, why the session ended, the most common packets (state, ID, count, bytes and a name such as "keep alive" or "system chat"), and for undecoded chat a hex preview with any readable text. It doesn't touch the network.

### 10.8 RCON quick checks

`--preset` (or the Quick check list in the page) runs a ready-made set of commands on one RCON connection. Every command only reads information and none changes the world, players or settings. Which commands exist depends on the server software: `tps` and `plugins` exist on Paper and Spigot, `forge tps` on Forge. A server that doesn't know a command answers with its own error text, and the answer is shown as it is.

| Preset | Commands |
|---|---|
| `overview` | `list`, `version`, `difficulty`, `seed`, `time query daytime`, `whitelist list`, `tps` |
| `performance` | `tps`, `mspt`, `forge tps`, `spark tps`, `list` |
| `plugins` | `plugins`, `version`, `paper version` |
| `players` | `list uuids`, `whitelist list`, `banlist players`, `banlist ips` |
| `world` | `seed`, `time query daytime`, `time query gametime`, `time query day`, `difficulty`, `worldborder get` |

### 10.9 Where the version data comes from

Packet IDs and version names come from the community project [minecraft-data](https://github.com/PrismarineJS/minecraft-data). Every profile passes a full login, configuration and play test against a fake local server, and none has been run against a real Minecraft server by the authors.

## 11. Using it from Python code

```python
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import RCONClient
from recon.protocols.ghost import headless_ghost_stream

try:
    # 1. TCP Status + RTT Latency Probe
    status = mc_status_ping("127.0.0.1", port=25565, measure_latency=True)
    print(f"Online: {status['players']['online']} | RTT: {status.get('latency_ms')} ms")

    # 2. UDP GameSpy4 Full Stat Dump
    query = gamespy4_full_query("127.0.0.1", port=25565)
    print("Uncapped Players:", query["players"])

    # 3. Persistent RCON Context Manager Session
    with RCONClient("127.0.0.1", port=25575, timeout=5.0) as rcon:
        rcon.authenticate("your_rcon_password")
        print(rcon.execute("list"))
        print(rcon.execute("tps"))  # Paper/Spigot only; vanilla servers have no tps command

    # 4. Offline-mode play-state client (version detected automatically;
    #    pass protocol_version=767 to force one)
    headless_ghost_stream("127.0.0.1", port=25565, duration=10)

except ReconError as err:
    print(f"Audit exception: {err}")
```

## 12. Other tools

### 12.1 Audit script (`scripts/run_recon.py`)

Runs ping, query and (if a password is given) RCON against one host and prints a summary. It is configured through environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MC_TARGET_HOST` | `127.0.0.1` | Target host |
| `MC_TARGET_PORT` | `25565` | Game port for ping and query |
| `MC_RCON_PORT` | `25575` | RCON port |
| `MC_RCON_PASSWORD` | *(unset)* | RCON password; the RCON step is skipped when it is not set |

```bash
# macOS and Linux
PYTHONPATH=source MC_TARGET_HOST=127.0.0.1 python3 scripts/run_recon.py
```

```powershell
# Windows PowerShell
$env:PYTHONPATH="source"; $env:MC_TARGET_HOST="127.0.0.1"; py scripts/run_recon.py
```

Exit code `0` means at least one attempted probe succeeded, `1` means every attempted probe failed, and `2` means an invalid port in the environment.

### 12.2 Packet inspector (`scripts/packet_inspector.py`)

Prints the exact bytes of the packets the tool sends (handshake, GameSpy4 challenge, RCON login) as hex and text, so you can compare them with the protocol documents. It never connects to anything. `PYTHONPATH=source python3 scripts/packet_inspector.py` shows them (on Windows PowerShell, `$env:PYTHONPATH="source"; py scripts/packet_inspector.py`), `--host` and `--port` change the sample address, and `--self-test` runs the silent checks that CI uses.

---
## 13. References

* **Minecraft modern TCP protocol & Base-128 VarInt specification:** [wiki.vg/Protocol](https://wiki.vg/Protocol)
* **Server list ping (`0x00` status & `0x01` ping/pong specification):** [wiki.vg/Server_List_Ping](https://wiki.vg/Server_List_Ping)
* **GameSpy4 (`0xFEFD`) UDP query protocol specification:** [wiki.vg/Query](https://wiki.vg/Query)
* **Valve Source RCON binary packet specification:** [developer.valvesoftware.com/wiki/Source_RCON_Protocol](https://developer.valvesoftware.com/wiki/Source_RCON_Protocol)
