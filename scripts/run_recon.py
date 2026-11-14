#!/usr/bin/env python3
"""
Standalone multi-protocol reconnaissance runner.
Execute from the repository root with:
    PYTHONPATH=src python3 scripts/run_recon.py
"""

from mcrecon import mc_status_ping, gamespy4_full_query, rcon_command

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 25565
RCON_PORT = 25575
RCON_PASSWORD = "password_here"


def main() -> None:
    print(f"=== [1/3] TCP Server List Ping ({TARGET_HOST}:{TARGET_PORT}) ===")
    try:
        ping_res = mc_status_ping(TARGET_HOST, TARGET_PORT)
        version_name = ping_res.get("version", {}).get("name", "Unknown")
        online = ping_res.get("players", {}).get("online", 0)
        max_p = ping_res.get("players", {}).get("max", 0)
        print(f"[+] Server Version : {version_name}")
        print(f"[+] Players Online : {online}/{max_p}")
    except Exception as err:
        print(f"[-] Ping failed: {err}")

    print(f"\n=== [2/3] UDP GameSpy4 Full Query ({TARGET_HOST}:{TARGET_PORT}) ===")
    try:
        query_res = gamespy4_full_query(TARGET_HOST, TARGET_PORT)
        print(f"[+] Map Name       : {query_res.get('metadata', {}).get('map')}")
        print(f"[+] Plugins        : {query_res.get('metadata', {}).get('plugins')}")
        print(f"[+] Full PlayerList: {query_res.get('players')}")
    except Exception as err:
        print(f"[-] UDP Query failed: {err}")

    print(f"\n=== [3/3] TCP Source RCON ({TARGET_HOST}:{RCON_PORT}) ===")
    try:
        rcon_out = rcon_command(TARGET_HOST, RCON_PORT, RCON_PASSWORD, "list")
        print(f"[+] Console Output : {rcon_out}")
    except Exception as err:
        print(f"[-] RCON failed: {err}")


if __name__ == "__main__":
    main()
