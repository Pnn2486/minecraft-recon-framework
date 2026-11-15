#!/usr/bin/env python3
"""
Sequential multi-protocol reconnaissance audit script.

Configuration is read from environment variables:
    MC_TARGET_HOST    target host (default: 127.0.0.1)
    MC_TARGET_PORT    game port used for TCP ping and UDP query (default: 25565)
    MC_RCON_PORT      RCON port (default: 25575)
    MC_RCON_PASSWORD  RCON password; the RCON step is skipped when it is not set

Exit codes:
    0  at least one attempted probe succeeded
    1  every attempted probe failed
    2  invalid environment configuration

Usage:
    PYTHONPATH=source python3 scripts/run_recon.py
"""

import os
import sys
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import rcon_command


def _env_port(name: str, default: int) -> int:
    """Reads a TCP/UDP port from the environment and rejects invalid values."""
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if not 1 <= value <= 65535:
        print(f"[!] {name} must be a port number between 1 and 65535 (got {raw!r}).", file=sys.stderr)
        raise SystemExit(2)
    return value


TARGET_HOST = os.environ.get("MC_TARGET_HOST", "127.0.0.1")
TARGET_PORT = _env_port("MC_TARGET_PORT", 25565)
RCON_PORT = _env_port("MC_RCON_PORT", 25575)
RCON_PASSWORD = os.environ.get("MC_RCON_PASSWORD", "")


def run_sequential_audit() -> int:
    attempted = 0
    succeeded = 0

    print(f"[*] Target Node: {TARGET_HOST} (Game: {TARGET_PORT}, RCON: {RCON_PORT})")
    print("-" * 72)

    print("[1/3] Probing TCP Server List Ping (Packet 0x00)...")
    attempted += 1
    try:
        ping_data = mc_status_ping(TARGET_HOST, TARGET_PORT, timeout=5.0, measure_latency=True)
        version_info = ping_data.get("version", {})
        players_info = ping_data.get("players", {})
        print(f"  [+] Version      : {version_info.get('name')} (Protocol {version_info.get('protocol')})")
        print(f"  [+] Players      : {players_info.get('online')}/{players_info.get('max')}")
        print(f"  [+] RTT Latency  : {ping_data.get('latency_ms')} ms")
        succeeded += 1
    except ReconError as exc:
        print(f"  [-] TCP Ping Failed: {exc}", file=sys.stderr)

    print("-" * 72)

    print("[2/3] Probing UDP GameSpy4 Full Stat Query (0xFEFD)...")
    attempted += 1
    try:
        query_data = gamespy4_full_query(TARGET_HOST, TARGET_PORT, timeout=5.0)
        meta = query_data.get("metadata", {})
        print(f"  [+] Server Engine: {meta.get('version', 'Unknown')}")
        print(f"  [+] World Map    : {meta.get('map', 'Unknown')}")
        print(f"  [+] Plugins      : {meta.get('plugins', 'None / Vanilla')}")
        print(f"  [+] Full Players ({query_data.get('player_count', 0)}): {query_data.get('players')}")
        succeeded += 1
    except ReconError as exc:
        print(f"  [-] UDP Query Failed: {exc}", file=sys.stderr)

    print("-" * 72)

    print("[3/3] Probing TCP Source RCON Administrative Tunnel...")
    if not RCON_PASSWORD:
        print("  [~] Skipped: MC_RCON_PASSWORD environment variable is not set.")
    else:
        attempted += 1
        try:
            output = rcon_command(TARGET_HOST, RCON_PORT, RCON_PASSWORD, "list", timeout=5.0)
            print(f"  [+] RCON '/list' : {output.strip()}")
            succeeded += 1
        except ReconError as exc:
            print(f"  [-] RCON Failed  : {exc}", file=sys.stderr)

    print("-" * 72)
    print(f"[*] {succeeded} of {attempted} probes succeeded.")
    return 1 if succeeded == 0 else 0


if __name__ == "__main__":
    sys.exit(run_sequential_audit())
