#!/usr/bin/env python3
"""
Sequential multi-protocol reconnaissance audit script.
Usage:
    PYTHONPATH=source python3 scripts/run_recon.py
"""

import os
import sys
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import rcon_command

TARGET_HOST = os.environ.get("MC_TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("MC_TARGET_PORT", "25565"))
RCON_PORT = int(os.environ.get("MC_RCON_PORT", "25575"))
RCON_PASSWORD = os.environ.get("MC_RCON_PASSWORD", "")


def run_sequential_audit() -> int:
    print(f"[*] Target Node: {TARGET_HOST} (Game: {TARGET_PORT}, RCON: {RCON_PORT})")
    print("-" * 72)

    print("[1/3] Probing TCP Server List Ping (Packet 0x00)...")
    try:
        ping_data = mc_status_ping(TARGET_HOST, TARGET_PORT, timeout=5.0, measure_latency=True)
        version_info = ping_data.get("version", {})
        players_info = ping_data.get("players", {})
        print(f"  [+] Version      : {version_info.get('name')} (Protocol {version_info.get('protocol')})")
        print(f"  [+] Players      : {players_info.get('online')}/{players_info.get('max')}")
        print(f"  [+] RTT Latency  : {ping_data.get('latency_ms')} ms")
    except ReconError as exc:
        print(f"  [-] TCP Ping Failed: {exc}", file=sys.stderr)

    print("-" * 72)

    print("[2/3] Probing UDP GameSpy4 Full Stat Query (0xFEFD)...")
    try:
        query_data = gamespy4_full_query(TARGET_HOST, TARGET_PORT, timeout=5.0)
        meta = query_data.get("metadata", {})
        print(f"  [+] Server Engine: {meta.get('version', 'Unknown')}")
        print(f"  [+] World Map    : {meta.get('map', 'Unknown')}")
        print(f"  [+] Plugins      : {meta.get('plugins', 'None / Vanilla')}")
        print(f"  [+] Full Players ({query_data.get('player_count', 0)}): {query_data.get('players')}")
    except ReconError as exc:
        print(f"  [-] UDP Query Failed: {exc}", file=sys.stderr)

    print("-" * 72)

    print("[3/3] Probing TCP Source RCON Administrative Tunnel...")
    if not RCON_PASSWORD:
        print("  [~] Skipped: MC_RCON_PASSWORD environment variable is not set.")
    else:
        try:
            output = rcon_command(TARGET_HOST, RCON_PORT, RCON_PASSWORD, "list", timeout=5.0)
            print(f"  [+] RCON '/list' : {output.strip()}")
        except ReconError as exc:
            print(f"  [-] RCON Failed  : {exc}", file=sys.stderr)

    print("-" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(run_sequential_audit())
