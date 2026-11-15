# minecraft-recon-framework

**Zero-dependency Python network reconnaissance, wire-protocol dissection, and remote administration framework for Minecraft Java Edition infrastructure (`Python >= 3.8`, CPython standard library only).**

`minecraft-recon-framework` implements deterministic TCP and UDP socket state machines across all four network intelligence layers exposed by Minecraft Java Edition server daemons:

1. **TCP Server List Ping (`0x00` Status + `0x01` Latency Probe):** Unauthenticated descriptor extraction (MOTD, protocol version integer, server brand, favicon payload, sample player UUIDs) paired with a 64-bit big-endian timestamp echo for true Round-Trip Time (`latency_ms`) measurement.
2. **UDP GameSpy4 Full Stat Query (`0xFEFD`):** Stateless two-phase challenge-response handshake extracting uncapped online player arrays, server engine identifiers, active plugin matrices, and world map topology.
3. **TCP Source RCON (`0x03` / `0x02`):** Authenticated 32-bit signed little-endian administrative tunnel (`RCONClient`) for remote command execution, tick-rate (`TPS`) auditing, and memory profiling.
4. **TCP Play-State Headless Client (`0x02` Login -> Play):** Stateful virtual client supporting offline UUID v3 generation, dynamic RFC 1950 `zlib` frame compression (`0x03`), automated 64-bit `Keep-Alive` (`0x1F` -> `0x10`) heartbeat echoing, and real-time `0x0E` chat packet scraping.
>[!IMPORTANT]
> **Authorization & Compliance Notice:** This framework is engineered strictly for systems administrators, infrastructure engineers, and security researchers conducting authorized diagnostics on nodes they own or hold explicit written permission to audit. Refer to [COPYING.md](./COPYING.md) for full liability terms.

---


## 1. Repository architecture & module map

```markdown
minecraft-recon-framework/
├── .github/workflows/ci.yml              # Matrix CI (Linux & macOS, Python 3.9-3.12)
├── program_info/org.recon.Framework.json # Machine-readable protocol & port manifest
├── scripts/run_recon.py                  # Automated sequential multi-protocol audit script
├── source/recon/                         # Core Python namespace package (PEP 420)
│   ├── cli.py                            # Argument parser, validation & dispatch entry point
│   ├── exceptions.py                     # Structured exception hierarchy (ReconError, etc.)
│   ├── utils/
│   │   └── varint.py                     # Base-128 VarInt, recv_exact & UUID v3 generators
│   └── protocols/
│       ├── ping.py                       # TCP 0x00 Status + 0x01 RTT Latency implementation
│       ├── query.py                      # UDP 0xFEFD GameSpy4 Challenge/Response state machine
│       ├── rcon.py                       # TCP Little-Endian Source RCON client & context manager
│       └── ghost.py                      # TCP Play-State client (zlib + Keep-Alive + Chat stream)
├── tests/test_varint.py                  # Unit test suite for binary serialization & framing
├── tools/packet_inspector.py             # 16-byte aligned Hex + ASCII wire-frame inspector
├── .editorconfig                         # Cross-editor indentation and UTF-8/LF rules
├── .gitattributes                        # Git line-ending normalization rules
├── .gitignore                            # Bytecode, virtual environment & secret exclusions
├── CODE_OF_CONDUCT.md                    # Contributor Covenant & ethical engineering standards
├── CONTRIBUTING.md                       # Pull request & deterministic socket coding standards
├── COPYING.md                            # Legal liability disclaimer & authorized-use mandate
├── Containerfile                         # OCI / Docker / Podman Alpine container specification
├── LICENSE                               # MIT License
├── pyproject.toml                        # PEP 621 build specification & CLI entry point
└── README.md                             # This file, used for instructions
```
——

## 2. System, hardware & network requirements

Because `minecraft-recon-framework` operates directly on raw POSIX/Winsock network sockets without launching a Java Virtual Machine (JVM) or rendering a 3D viewport, its hardware footprint is orders of magnitude smaller than a standard Minecraft client.

### 2.1 Hardware specifications (Minimum vs. Recommended)

| Hardware Component | Minimum Specification (Single-Node Audit) | Recommended Specification (Concurrent / CI / Container Fleet) | Technical Justification |
| :--- | :--- | :--- | :--- |
| **CPU Cores / Threads** | 1 vCPU / 1 Hardware Thread (`>= 1.0 GHz`, x86_64 or ARM64) | 2-4 vCPUs / 4+ Hardware Threads (`>= 2.4 GHz`) | Single-target probes are I/O-bound waiting on network RTT; multi-threaded batch auditing and `zlib` stream decompression (`0x03`) scale across CPU threads. |
| **System Memory (RAM)** | `64 MB` free RAM (`~18-25 MB` active CPython resident set size) | `512 MB - 1 GB` RAM | `ghost.py` processes `zlib` buffers in-memory; `512 MB+` prevents OOM kills when running inside Docker/Podman containers or parallel cron jobs. |
| **GPU / Compute Threads** | **0 GPU Threads (None / Headless)** | **0 GPU Threads (None / Headless)** | Unlike the official Minecraft client, this framework bypasses LWJGL, OpenGL, and Vulkan entirely. It runs natively on headless Linux servers, SSH terminals, and cloud VMs without a GPU or display server (`X11`/`Wayland`). |
| **Disk Storage** | `5 MB` free disk space | `250 MB` free disk space (if building OCI/Docker images) | Pure-Python source tree is `< 100 KB`; extra space is only required if storing JSON audit logs or Alpine Linux container layers. |
| **Network Interface** | `1 Mbps` IPv4/IPv6 NIC | `100 Mbps+` low-jitter Ethernet / VPC interface | Play-state `ghost` mode receives continuous chunk, entity, and chat packets from active servers (`~50-250 KB/s` per session). |

### 2.2 Supported operating systems

* **Linux (Primary Production Target):**
  * Ubuntu `20.04 LTS`, `22.04 LTS`, `24.04 LTS`
  * Debian `11 (Bullseye)`, `12 (Bookworm)`
  * RHEL / AlmaLinux / Rocky Linux `8+`, Fedora `38+`
  * Arch Linux, Kali Linux, Alpine Linux `3.18+` (musl libc supported)
* **macOS:**
  * macOS `12 (Monterey)`, `13 (Ventura)`, `14 (Sonoma)`, `15 (Sequoia)` on both **Apple Silicon (`arm64` / M1-M4)** and **Intel (`x86_64`)**.
* **Windows:**
  * Windows `10` (Build 19041+), Windows `11`, Windows Server `2019` / `2022` (via PowerShell, CMD, or WSL2).
* **Mobile / BSD / Embedded POSIX:**
  * FreeBSD `13+`, OpenBSD `7+`, Raspberry Pi OS (`ARMv7` / `aarch64`), iPadOS (`a-Shell` / `iSH`).

### 2.3 Software & runtime prerequisites

* **Python Interpreter:** CPython `>= 3.8` (`3.10`, `3.11`, or `3.12` recommended for optimal `socket` and `struct` performance).
* **Standard Library Modules (Pre-installed with Python):** `socket`, `struct`, `zlib`, `hashlib`, `json`, `argparse`, `time`, `unittest`.
* **External `pip` Packages Required:** **None (`0`)**.
* **Optional Tooling:**
  * `git` (for cloning and version control).
  * `docker` or `podman` (only if executing via `Containerfile`).
  * `jq` (optional command-line JSON processor for filtering `--mode ping` and `--mode query` output in Linux/macOS pipelines).

### 2.4 Network & firewall requirements

To audit a target node successfully, outbound traffic from your machine (and inbound rules on the target server's `iptables` / `nftables` / `ufw` / cloud security group) must permit:

* **TCP Port `25565`** (or custom game port): Required for `--mode ping` and `--mode ghost`.
* **UDP Port `25565`** (or custom `query.port`): Required for `--mode query`. Note that stateful firewalls must explicitly allow bidirectional **UDP** datagrams, not just TCP.
* **TCP Port `25575`** (or custom `rcon.port`): Required for `--mode rcon`.

---

## 3. Deep-dive wire protocol specifications

### 3.1 Protocol 1: TCP Server List Ping (`source/recon/protocols/ping.py`)

Every modern Minecraft TCP packet is prefixed with a Base-128 `VarInt` specifying the exact byte length of `Packet ID + Payload`. All socket reads use `recv_exact()` to reassemble fragmented TCP segments deterministically.

| Packet Phase | Direction | Packet ID | Wire Payload Structure |
| :--- | :--- | :--- | :--- |
| **1. Handshake** | Client -> Server | `0x00` | `VarInt(Protocol=767)` + `String(Host)` + `uint16_be(Port)` + `VarInt(NextState=1)` |
| **2. Status Request** | Client -> Server | `0x00` | Empty payload (`b"\x01\x00"` wire frame) |
| **3. Status Response** | Server -> Client | `0x00` | `String(UTF-8 JSON Descriptor)` |
| **4. Latency Ping** | Client -> Server | `0x01` | `int64_be(Unix Epoch Milliseconds)` (`>q`) |
| **5. Latency Pong** | Server -> Client | `0x01` | Echoed `int64_be` payload used to compute `latency_ms` |

---

### 3.2 Protocol 2: UDP GameSpy4 Full Stat Query (`source/recon/protocols/query.py`)

GameSpy4 runs over unconnected UDP datagrams (`SOCK_DGRAM`) and enforces a stateless token handshake:

1. **Challenge Request (`Client -> Server`, 7 bytes):**
   `Magic (0xFEFD, >H)` + `Type (0x09, B)` + `SessionID & 0x0F0F0F0F (>I)`.
2. **Challenge Response (`Server -> Client`):**
   `Type (0x09, B)` + `SessionID (>I)` + `Null-terminated ASCII integer token`.
3. **Full Stat Request (`Client -> Server`, 15 bytes):**
   `Magic (0xFEFD, >H)` + `Type (0x00, B)` + `SessionID (>I)` + `ChallengeToken (>I)` + `Padding (0x00000000, 4B)`.
4. **Full Stat Response (`Server -> Client`):**
   * **Header (`16 bytes`):** `\x00` + `SessionID (4B)` + `b"splitnum\x00\x80\x00"`.
   * **K/V Metadata:** Null-delimited (`\x00`) alternating key/value strings.
   * **Binary Boundary (`10 bytes`):** `b"\x00\x00\x01player_\x00\x00"`.
   * **Player Array:** Null-delimited (`\x00`) online usernames terminated by `\x00\x00`.

---

### 3.3 Protocol 3: TCP Source RCON (`source/recon/protocols/rcon.py`)

Valve Source RCON frames integers in **32-bit signed little-endian** (`<i`) byte order:

| Byte Offset | Field | Type (`struct`) | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | `Size` | `int32` (`<i`) | Byte length of remainder of frame (`4 + 4 + len(Body) + 2`) |
| `4..7` | `Request ID` | `int32` (`<i`) | Client correlation integer; server returns `-1` if authentication fails |
| `8..11` | `Type` | `int32` (`<i`) | `3` = `SERVERDATA_AUTH`, `2` = `SERVERDATA_EXECCOMMAND`, `0` = `SERVERDATA_RESPONSE_VALUE` |
| `12..N-2` | `Body` | `UTF-8` | Password or console command string |
| `N-2..N` | `Pad` | `2x Null` | Mandatory `b"\x00\x00"` terminator |

---

### 3.4 Protocol 4: Offline Play-State Headless Client (`source/recon/protocols/ghost.py`)

1. **Login Handshake:** Transmits `Handshake (0x00)` with `Next State = 2`, followed by `Login Start (0x00)`. For `protocol_version >= 764` (Minecraft 1.20.2+), `ghost.py` automatically appends a 16-byte MD5 UUID v3 (`OfflinePlayer:<username>`).
2. **Zlib Compression Negotiation (`0x03`):** When the server transmits `Set Compression (0x03)`, all subsequent frames switch to RFC 1950 `zlib` framing:
   ```text
   [VarInt: Frame Length] [VarInt: Uncompressed Data Length] [zlib.compress(Packet ID + Payload)]
   ```
3. **Play-State Heartbeat Loop (`0x1F` -> `0x10`):** Echoes 64-bit big-endian Keep-Alive IDs (`>q`) to maintain socket persistence while decoding incoming `0x0E` JSON chat packets.

---

## 4. Environment setup & OS execution workflows

### 4.1 Linux (Ubuntu, Debian, RHEL, Fedora, Arch, Kali)

#### Option A — Direct source execution (`PYTHONPATH=source`)
```bash
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
export PYTHONPATH="$(pwd)/source"

# Verify unit tests and wire-frame assertions
python3 -m unittest discover -s tests -v
python3 tools/packet_inspector.py

# Execute protocol state machines
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode ping
python3 -m recon.cli --host 127.0.0.1 --port 25565 --mode query
python3 -m recon.cli --host 127.0.0.1 --rcon-port 25575 --password "rcon_secret" --cmd "tps" --mode rcon
python3 -m recon.cli --host 127.0.0.1 --port 25565 --username "AuditNode" --duration 60 --mode ghost
```

#### Option B — Editable package installation (`pyproject.toml`)
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
python3 -m recon.cli --host 127.0.0.1 --port 25565 --username "AuditNode" --duration 60 --mode ghost
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
        print(rcon.execute("tps"))

except ReconError as err:
    print(f"Audit exception: {err}")
```

---

## 6. CLI arguments & exit codes

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | *Required* | Target IPv4 address or FQDN |
| `--mode` | `str` | *Required* | Protocol state machine: `ping`, `query`, `rcon`, `ghost` |
| `--port` | `int` | `25565` | Target TCP/UDP game port (`ping`, `query`, `ghost`) |
| `--rcon-port` | `int` | `25575` | Target TCP RCON port (`rcon` mode) |
| `--timeout` | `float` | `5.0` | Socket timeout in seconds |
| `--password` | `str` | `""` | RCON authentication secret (required for `--mode rcon`) |
| `--cmd` | `str` | `"list"` | Server console command payload for RCON execution |
| `--username` | `str` | `"AuditNode"` | `Login Start (0x00)` username for `ghost` mode |
| `--protocol-version` | `int` | `754` | Protocol version integer for `ghost` mode (`754` = 1.16.5, `767` = 1.21) |
| `--duration` | `int` | `30` | Socket read-loop TTL in seconds for `ghost` mode |
| `--quiet` | `flag` | `False` | Suppress compliance banner on `stderr` for clean JSON piping |

* **Exit Code `0`:** Handshake and payload deserialization succeeded.
* **Exit Code `1`:** `ReconError`, `ProtocolFramingError`, `AuthenticationError`, or socket timeout.
* **Exit Code `2`:** Invalid or missing mandatory CLI flag.
* **Exit Code `130`:** Operator `SIGINT` (`Ctrl+C`) termination.

---

## 7. Protocol specifications & technical references

* **Minecraft Modern TCP Protocol & Base-128 VarInt Specification:** [wiki.vg/Protocol](https://wiki.vg/Protocol)
* **Server List Ping (`0x00` Status & `0x01` Ping/Pong Specification):** [wiki.vg/Server_List_Ping](https://wiki.vg/Server_List_Ping)
* **GameSpy4 (`0xFEFD`) UDP Query Protocol Specification:** [wiki.vg/Query](https://wiki.vg/Query)
* **Valve Source RCON Binary Packet Specification:** [developer.valvesoftware.com/wiki/Source_RCON_Protocol](https://developer.valvesoftware.com/wiki/Source_RCON_Protocol)
