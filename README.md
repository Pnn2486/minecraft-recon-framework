# minecraft-recon-framework

[![CI](https://github.com/Pnn2486/minecraft-recon-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/Pnn2486/minecraft-recon-framework/actions/workflows/ci.yml)
![Python 3.10 to 3.15](https://img.shields.io/badge/python-3.10%20to%203.15-blue)
![Runtime dependencies: none](https://img.shields.io/badge/runtime%20dependencies-none-brightgreen)

**Zero-dependency Python network diagnostics, wire-protocol dissection, and remote administration framework for Minecraft Java Edition infrastructure (`Python >= 3.10`, CPython standard library only).**

`minecraft-recon-framework` implements deterministic TCP and UDP socket state machines across all four network intelligence layers exposed by Minecraft Java Edition server daemons:

1. **TCP server list ping (`0x00` status + `0x01` latency probe):** Unauthenticated descriptor extraction (MOTD, protocol version integer, server brand, favicon payload, sample player UUIDs) paired with a 64-bit big-endian timestamp echo for true Round-Trip Time (`latency_ms`) measurement.
2. **UDP GameSpy4 full stat query (`0xFEFD`):** Stateless two-phase challenge-response handshake extracting uncapped online player arrays, server engine identifiers, active plugin matrices, and world map topology.
3. **TCP Source RCON (`0x03` / `0x02`):** Authenticated 32-bit signed little-endian administrative tunnel (`RCONClient`) for remote command execution, tick-rate (`TPS`, Paper/Spigot servers only) auditing, and memory profiling.
4. **TCP play-state headless client (`0x02` login -> play):** Stateful virtual client supporting offline UUID v3 generation, dynamic RFC 1950 `zlib` frame compression (`0x03`), the Configuration phase added in Minecraft 1.20.2, Keep-Alive heartbeat echoing, and chat packet reporting. It supports 46 protocol versions from Minecraft 1.8 to 26.1 and detects the server's version automatically; see the compatibility table in [section 3.4](#34-protocol-4-offline-play-state-headless-client-sourcereconprotocolsghostpy) and the [known limitations](#7-known-limitations--test-status).

>[!WARNING]
> Not affiliated with, endorsed by, or approved by Mojang or Microsoft. Minecraft is a trademark of Mojang.

>[!IMPORTANT]
> **Authorization & compliance notice:** This framework is engineered strictly for systems administrators, infrastructure engineers, and security researchers conducting authorized diagnostics on nodes they own or hold explicit written permission to audit. Refer to [COPYING.md](./COPYING.md) for full liability terms.

---

## 1. Repository architecture & module map

- **source**
  - **recon** - core Python package (PEP 420)
    - `cli.py` - argument parser, validation & dispatch entry point
    - `gui.py` - local web interface server (`recon-gui`)
    - **web** - the page the web interface shows (`index.html`, `style.css`, `app.js`, `favicon.svg`)
    - `exceptions.py` - structured exception hierarchy (`ReconError`, etc.)
    - **utils**
      - `varint.py` - Base-128 VarInt, `recv_exact` & UUID v3 generators
      - `versions.py` - protocol number <-> Minecraft version name lookup
    - **protocols**
      - `ping.py` - TCP `0x00` Status + `0x01` RTT latency
      - `query.py` - UDP `0xFEFD` GameSpy4 challenge/response
      - `rcon.py` - TCP little-endian Source RCON client
      - `ghost.py` - TCP play-state client (zlib, Configuration phase, Keep-Alive, chat)
      - `ghost_profiles.py` - per-version profile logic for `ghost.py`
      - `chat.py` - decodes plain, signed, system and disguised chat packets
      - `diagnostics.py` - session report for the ghost client
      - `rcon_presets.py` - ready-made read-only RCON command sets
      - `ghost_profile_data.py` - packet ID table, one row per protocol number
    - `__main__.py` - makes `python -m recon` work
- **.github**
  - `dependabot.yml` - weekly update pull requests for GitHub Actions and pip
  - **workflows**
    - `ci.yml` - tests on Linux, macOS and Windows with Python 3.10-3.15, plus lint, type check, coverage and a package build check
    - `integration.yml` - manual test against a real Minecraft server in Docker
    - `release.yml` - builds the package and creates a GitHub release when a version tag is pushed
- **program_info**
  - `org.recon.Framework.json` - protocol & port manifest
- **scripts**
  - `run_recon.py` - automated multi-protocol audit script
- **tools**
  - `packet_inspector.py` - hex + ASCII wire-frame inspector
- **tests**
  - `test_varint.py` - unit tests for serialization & framing
  - `test_protocols.py` - loopback tests for ping, query, RCON, ghost and CLI validation
  - `test_gui.py` - tests for the web interface server, its safety checks and its files
  - `test_chat.py` - tests for the NBT and text readers, the chat decoder, diagnostics and RCON presets

- `pyproject.toml` - build spec & CLI entry point
- `Containerfile` - Docker / Podman container spec
- `README.md` - this file
- `CONTRIBUTING.md` - pull request & coding standards
- `CODE_OF_CONDUCT.md` - community conduct rules & ethical-use standard
- `COPYING.md` - liability disclaimer
- `LICENSE` - Authorized Use License
- `.editorconfig`, `.gitattributes`, `.gitignore` - other necessary files

---

## 2. System, hardware & network requirements

Because `minecraft-recon-framework` operates directly on raw POSIX/Winsock network sockets without launching a Java Virtual Machine (JVM) or rendering a 3D viewport, its hardware footprint is orders of magnitude smaller than a standard Minecraft client.

### 2.1 Hardware specifications (Minimum vs. Recommended)

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
* **Mobile / BSD / embedded POSIX:**
  * FreeBSD `13+`, OpenBSD `7+`, Raspberry Pi OS `Bookworm` or newer (`ARMv7` / `aarch64`), iPadOS (`a-Shell` / `iSH`). All require a Python `3.10+` build.

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

---

## 3. Deep-dive wire protocol specifications

### 3.1 Protocol 1: TCP server list ping (`source/recon/protocols/ping.py`)

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

### 3.2 Protocol 2: UDP GameSpy4 full stat query (`source/recon/protocols/query.py`)

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

### 3.3 Protocol 3: TCP Source RCON (`source/recon/protocols/rcon.py`)

Valve Source RCON frames integers in **32-bit signed little-endian** (`<i`) byte order:

| Byte offset | Field | Type (`struct`) | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | `Size` | `int32` (`<i`) | Byte length of remainder of frame (`4 + 4 + len(Body) + 2`) |
| `4..7` | `Request ID` | `int32` (`<i`) | Client correlation integer; server returns `-1` if authentication fails |
| `8..11` | `Type` | `int32` (`<i`) | `3` = `SERVERDATA_AUTH`, `2` = `SERVERDATA_EXECCOMMAND`, `0` = `SERVERDATA_RESPONSE_VALUE` |
| `12..N-2` | `Body` | `UTF-8` | Password or console command string |
| `N-2..N` | `Pad` | `2x Null` | Mandatory `b"\x00\x00"` terminator |

---

### 3.4 Protocol 4: offline play-state headless client (`source/recon/protocols/ghost.py`)

1. **Login handshake:** Transmits `Handshake (0x00)` with `Next State = 2`, followed by `Login Start (0x00)`. The bytes after the username depend on the version. For `protocol_version >= 764` (Minecraft 1.20.2+), `ghost.py` appends a 16-byte MD5 UUID v3 (`OfflinePlayer:<username>`). Versions 1.19 - 1.20.1 send "no signature / no UUID" flags instead.
2. **Zlib compression negotiation (`0x03`):** When the server transmits `Set Compression (0x03)`, all subsequent frames switch to RFC 1950 `zlib` framing:
   ```text
   [VarInt: Frame Length] [VarInt: Uncompressed Data Length] [zlib.compress(Packet ID + Payload)]
   ```
3. **Configuration phase (1.20.2+ only):** After `Login Success (0x02)`, the client sends `Login Acknowledged`, answers the server's Known Packs with an empty list, echoes Keep-Alive and Ping, and acknowledges `Finish Configuration` before entering Play.
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
> The tables come from the community-maintained [`minecraft-data`](https://github.com/PrismarineJS/minecraft-data) project. Every profile passes a full login, configuration and play test against a fake local server, but **none has been run against a real Minecraft server by the authors**. Chat is shown as JSON text on 1.8 - 1.20.2; on newer versions and for signed player chat only the packet size is shown. Servers that force a resource pack or run anti-bot plugins may still kick the client.
>
> **Adding a version:** append one row to `source/recon/protocols/ghost_profile_data.py` (the layout is explained at the top of that file) and add the version to the tests. No other file needs to change unless the new release alters the login sequence itself.

---

## 4. Environment setup & OS execution workflows

### 4.1 Linux (Ubuntu, Debian, RHEL, Fedora, Arch, Kali)

#### Option A — direct source execution (`PYTHONPATH=source`)
```bash
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
export PYTHONPATH="$(pwd)/source"

# Verify unit tests and wire-frame assertions
python3 -m unittest discover -s tests -v
python3 tools/packet_inspector.py --self-test

# Execute protocol state machines
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode ping
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode query
python3 -m recon.cli --host 127.0.0.1 --rcon-port 25575 --password "rcon_secret" --cmd "list" --mode rcon
python3 -m recon.cli --host 127.0.0.1 --port 25565 --username "AuditNode" --duration 60 --mode ghost   # version is detected automatically
# python3 -m recon.cli --host 127.0.0.1 --protocol-version 1.21.1 --mode ghost   # or force one
```

#### Option B — editable package installation (`pyproject.toml`)
Installing in editable mode registers the `recon` binary directly in your user PATH so `PYTHONPATH` is no longer required:
```bash
pip install --user -e .
recon --host 127.0.0.1 --port 25565 --mode ping --quiet
```

---

### 4.2 macOS (Apple Silicon & Intel — Zsh / Bash)

```zsh
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
export PYTHONPATH="${PWD}/source"

# Run test suite and wire-frame hexdump utility
python3 -m unittest discover -s tests -v
python3 tools/packet_inspector.py

# Execute CLI modes (or pass PYTHONPATH=source inline per command)
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode ping
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode query
python3 -m recon.cli --host 127.0.0.1 --rcon-port 25575 --password "rcon_secret" --cmd "list" --mode rcon
python3 -m recon.cli --host 127.0.0.1 --port 25565 --username "AuditNode" --duration 60 --mode ghost   # version is detected automatically
# python3 -m recon.cli --host 127.0.0.1 --protocol-version 1.21.1 --mode ghost   # or force one
```

---

### 4.3 Containerized execution (Docker & Podman on Linux / macOS)

```bash
docker build -f Containerfile -t minecraft-recon-framework:latest .
docker run --rm minecraft-recon-framework:latest --host 10.0.0.5 --port 25565 --mode ping --quiet
```

---

### 4.4 Windows (PowerShell & CMD)

```powershell
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
$env:PYTHONPATH="source"

python -m unittest discover -s tests -v
python -m recon.cli --host 127.0.0.1 --port 25565 --mode ping
```

---

### 4.5 Automated audit script (`scripts/run_recon.py`)

Runs ping, query and (if a password is given) RCON against one host and prints a summary. It is configured through environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MC_TARGET_HOST` | `127.0.0.1` | Target host |
| `MC_TARGET_PORT` | `25565` | Game port for ping and query |
| `MC_RCON_PORT` | `25575` | RCON port |
| `MC_RCON_PASSWORD` | *(unset)* | RCON password; the RCON step is skipped when it is not set |

```bash
PYTHONPATH=source MC_TARGET_HOST=127.0.0.1 python3 scripts/run_recon.py
```

Exit code `0` means at least one attempted probe succeeded, `1` means every attempted probe failed, and `2` means an invalid port in the environment.

---

### 4.6 Web interface (`recon-gui`)

If you prefer buttons to command-line flags, start the web interface. It needs nothing extra to be installed.

```bash
python3 -m recon.gui          # or, after `pip install .`: recon-gui
```

This starts a small server on your own computer and opens `http://127.0.0.1:8765/` in your browser. If that port is busy it picks a free one and prints the address. The layout follows launchers such as Prism Launcher, with a modern look. Your saved servers are tiles in a grid, a toolbar on top adds, edits and removes them, and a side panel on the right shows the selected server and its four tools: server status (ping), server details (query), console (RCON) and test player (ghost client). Pick a tile, pick a tool, tick the box that says you own the server or have permission to test it, and press the green button at the bottom. Double-clicking a tile runs the chosen tool.

* **Chat and diagnostics.** The test player result shows the chat it saw as a list of messages, plus an optional diagnostics section. Plain, signed, system and disguised chat is decoded for the versions in the packet table, including the NBT text of 1.20.3 and newer. Signed chat is not encrypted, so its text is readable. Signatures are skipped, not checked. The encryption of an online-mode connection is not touched, and the test player cannot join such servers. A chat packet that does not match any known layout is listed as not decoded, with its readable text shown in the diagnostics.
* **Quick checks.** The console tool has a list of read-only command sets (overview, performance, plugins, players, world). They run on one RCON connection and each answer is shown under its command.
* **Same code as the command line.** The page runs the same functions as `recon`, so the same checks and limits apply. It shows ping and query results as cards and everything else as text.
* **Only on this computer.** The server listens on `127.0.0.1`, rejects other host names, needs a random token that is created at every start, and refuses requests that come from other web sites. Do not put it behind a reverse proxy or expose it to a network.
* **One job at a time.** A test player run lasts at most 120 seconds and cannot be cancelled early. Close the program with Ctrl+C to stop everything.
* **Saved servers.** The server list (name, address, ports, icon and last status) is stored in this browser only. The RCON password is only kept in the form while the page is open. It is never saved or shown in the results.
* **Options.** `--port 9000` picks the port and `--no-browser` stops it from opening the browser.
* **Status.** The page was checked in a headless Chromium browser together with fake servers. It has not been used against a real Minecraft server. The chat decoder was written from the published packet layouts and tested only with hand-built packets, so a version can still differ in practice.

## 5. Programmatic Python API integration

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

---

## 6. CLI arguments & exit codes

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
| `--username` | `str` | `"AuditNode"` | `Login Start (0x00)` username for `ghost` mode |
| `--protocol-version` | `str` | `auto` | Version for `ghost` mode: a Minecraft version (`1.16.5`), a protocol number (`754`), or `auto` to detect it from the server with a status ping. Versions without a profile are rejected (see section 3.4) |
| `--list-versions` | `flag` | `False` | Print every known Minecraft version with its protocol number and whether ghost mode supports it, then exit |
| `--duration` | `int` | `30` | Socket read-loop TTL in seconds for `ghost` mode |
| `--diagnostics` | `flag` | `False` | Print a session report after `ghost` mode: timeline, packet counts, keep-alive timing and how many chat packets were decoded. Every report line starts with `[#]` |
| `--quiet` | `flag` | `False` | Suppress compliance banner on `stderr` for clean JSON piping |

* **Exit code `0`:** Handshake and payload deserialization succeeded.
* **Exit code `1`:** `ReconError`, `ProtocolFramingError`, `AuthenticationError`, `UnsupportedProtocolError` (ghost mode), or socket timeout.
* **Exit code `2`:** Invalid or missing mandatory CLI flag, or a value out of range (for example a port outside 1-65535, or a timeout of 0 or less).
* **Exit code `130`:** Operator `SIGINT` (`Ctrl+C`) termination.

---

## 7. Known limitations & test status

Please read this before relying on the tool.

### 7.1 What has and has not been tested

* **Automated tests use fake servers only.** The test suite (`tests/test_protocols.py`) starts small imitation servers on `127.0.0.1` that were written from the published protocol specifications. They prove the code follows those specifications. They do **not** prove it works against every real server.
* **No mode has been verified against a real Minecraft server by the authors.** This applies to `ping`, `query`, `rcon` and `ghost` alike. Treat the first run against your own server as the real test, and open an issue if something is different.
* **Python versions:** The code is written for Python `3.10+`. CI runs `3.10` through `3.15` on Linux, macOS and Windows.

### 7.2 Minecraft version support

| Mode | Version dependence | Status |
| :--- | :--- | :--- |
| `ping` | Version independent. | Expected to work on any Java Edition server. |
| `query` | Version independent. Needs `enable-query=true` in `server.properties` and an open UDP port. | Expected to work on any server that has query enabled. |
| `rcon` | Version independent. Needs `enable-rcon=true` and an RCON password. | Expected to work on any server that has RCON enabled. |
| `ghost` | **Version specific**, because packet IDs change between releases. | Protocols `47` (1.8) to `775` (26.1), 46 in total (see section 3.4). Every other `--protocol-version` is rejected before connecting. |

### 7.3 Known limitations of `ghost` mode

* **Offline-mode servers only.** The target must have `online-mode=false`. Servers that require Mojang authentication reply with an Encryption Request, and the client stops with `OnlineModeRequiredError`. It does not implement encryption or authentication.
* **Unsupported versions:** Minecraft 1.7.x (protocols `4` and `5`), 1.9.1, 1.14.2, 26.2, 26.3 and all snapshots have no packet table, although their names are known (`recon --list-versions` marks them). Supporting one means adding a row to `source/recon/protocols/ghost_profile_data.py`.
* **Chat is only partly decoded.** On 1.8 - 1.20.2 plain chat is shown as raw JSON text. Signed player chat and the NBT text used from 1.20.3 on are reported as a packet ID and size only.
* **Passive behavior.** The client echoes Keep-Alive and Ping packets and ignores world data. It does not move, send chat, or load chunks. Servers with anti-bot plugins, whitelists, or proxies (BungeeCord, Velocity) may kick it.
* **Listening window.** Sessions end after `--duration` seconds. If the server sends nothing for longer than `--timeout`, the session stops with a timeout error (exit code `1`).
* **Automatic detection can be wrong behind proxies.** Proxies and multi-version plugins may report a different protocol number than the server behind them. If login fails, pass `--protocol-version` explicitly.

### 7.4 Other limitations

* **Java Edition only.** Bedrock Edition uses different protocols and is not supported.
* **Addressing.** The UDP `query` mode is IPv4 only. The TCP modes (`ping`, `rcon`, `ghost`) accept IPv4 or IPv6. SRV record lookups (`_minecraft._tcp`) are not performed, so use the real host and port.
* **`tps` is not a vanilla command.** It exists only on Paper, Spigot and compatible servers.
* **Legal responsibility stays with you.** Use the tool only on servers you own or have written permission to test. See [COPYING.md](./COPYING.md).

### 7.5 Test layers

* **Fast tests (every push and pull request):** the loopback suite in `tests/`, a lint and type check (`ruff`, `mypy`), a coverage check that fails below 80 percent, and a build of the package that is installed and smoke tested in a clean environment.
* **Real server test (manual):** the `Real server integration test` workflow starts a disposable offline-mode server in Docker and runs `ping`, `query`, `rcon` and `ghost` against it. It only runs when you start it from the Actions tab, so ordinary CI does not depend on Docker. It has not been run yet, so the first run may need small fixes.
* **Testing safely on your own machine:** to try the tool without touching anyone else's server, run your own local server with the same settings the workflow uses (`online-mode=false`, query and RCON enabled) and point the tool at `127.0.0.1`.

### 7.6 Security notes

* **RCON password.** The password is never printed, logged or included in error messages. Prefer the `MC_RCON_PASSWORD` environment variable to `--password`.
* **Timeouts and retries.** Every connection has a timeout (default 5 seconds). There are no automatic retries on purpose, so a failing target is never hit repeatedly.
* **Web interface.** `recon-gui` listens on `127.0.0.1` only and checks the host name, a per-run token and the origin of every request. See section 4.6.
* **Hosts and ports.** Ports must be 1 to 65535. Host names must be 1 to 253 characters with no spaces or control characters.
* **Proxies and DNS.** The tool ignores proxy settings and connects directly. It resolves host names with the operating system and does not look up SRV records, so use the real host and port.

---

## 8. Protocol specifications & technical references

* **Minecraft modern TCP protocol & Base-128 VarInt specification:** [wiki.vg/Protocol](https://wiki.vg/Protocol)
* **Server list ping (`0x00` status & `0x01` ping/pong specification):** [wiki.vg/Server_List_Ping](https://wiki.vg/Server_List_Ping)
* **GameSpy4 (`0xFEFD`) UDP query protocol specification:** [wiki.vg/Query](https://wiki.vg/Query)
* **Valve Source RCON binary packet specification:** [developer.valvesoftware.com/wiki/Source_RCON_Protocol](https://developer.valvesoftware.com/wiki/Source_RCON_Protocol)
