#!/usr/bin/env python3
"""
Wire-Frame Hexadecimal and VarInt Diagnostic Inspector.
Generates and verifies raw byte frames for TCP Ping, UDP GameSpy4, and Source RCON.

Usage:
    PYTHONPATH=source python3 tools/packet_inspector.py
    PYTHONPATH=source python3 tools/packet_inspector.py --self-test
"""

import argparse
import struct
import sys
from recon.utils.varint import (
    pack_varint,
    pack_string,
    read_varint_bytes,
    offline_player_uuid_bytes,
)


def format_hexdump(data: bytes, width: int = 16) -> str:
    """Formats a raw byte sequence into an aligned 16-byte Hex + ASCII table."""
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_cols = " ".join(f"{b:02X}" for b in chunk)
        ascii_cols = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"  {offset:04X}  {hex_cols:<{width * 3}}  |{ascii_cols}|")
    return "\n".join(lines)


def build_handshake_frame(host: str, port: int, protocol: int = 767, next_state: int = 1) -> bytes:
    """Constructs a complete length-prefixed TCP 0x00 Handshake wire frame."""
    payload = (
        pack_varint(0x00)
        + pack_varint(protocol)
        + pack_string(host)
        + struct.pack(">H", port)
        + pack_varint(next_state)
    )
    return pack_varint(len(payload)) + payload


def build_gamespy4_challenge_frame(session_id: int = 0x01020304) -> bytes:
    """Constructs a 7-byte UDP GameSpy4 0xFEFD Handshake Challenge datagram."""
    masked_session = session_id & 0x0F0F0F0F
    return struct.pack(">HBI", 0xFEFD, 0x09, masked_session)


def build_rcon_auth_frame(req_id: int, password: str) -> bytes:
    """Constructs a signed little-endian TCP Source RCON Type 3 Auth frame."""
    body = password.encode("utf-8") + b"\x00\x00"
    size = 4 + 4 + len(body)
    return struct.pack("<iii", size, req_id, 3) + body


def run_inspector(host: str, port: int, self_test: bool = False) -> int:
    tcp_frame = build_handshake_frame(host, port, protocol=767, next_state=1)
    decoded_len, payload_offset = read_varint_bytes(tcp_frame, 0)
    udp_frame = build_gamespy4_challenge_frame()
    rcon_frame = build_rcon_auth_frame(req_id=100, password="audit_password")
    uuid_bytes = offline_player_uuid_bytes("AuditNode")

    if self_test:
        assert len(tcp_frame) == decoded_len + payload_offset, "TCP VarInt length mismatch"
        assert udp_frame[:3] == b"\xfe\xfd\x09", "UDP GameSpy4 magic header mismatch"
        assert struct.unpack("<i", rcon_frame[:4])[0] == len(rcon_frame) - 4, "RCON size mismatch"
        assert len(uuid_bytes) == 16, "Offline UUID must be 16 bytes"
        print("[+] Wire-frame self-test passed: All binary headers verified.")
        return 0

    print("=== [1] TCP 0x00 Status Handshake Frame ===")
    print(f"  Target Host        : {host}:{port}")
    print(f"  Total Wire Bytes   : {len(tcp_frame)} bytes (payload {decoded_len} bytes + {payload_offset}-byte VarInt length prefix)")
    print(format_hexdump(tcp_frame))

    print("\n=== [2] UDP 0xFEFD GameSpy4 Challenge Frame ===")
    print(f"  Total Wire Bytes   : {len(udp_frame)} bytes")
    print(format_hexdump(udp_frame))

    print("\n=== [3] TCP Source RCON Type 3 Auth Frame (Little-Endian) ===")
    print(f"  Total Wire Bytes   : {len(rcon_frame)} bytes")
    print(format_hexdump(rcon_frame))

    print("\n=== [4] Offline Player UUID v3 (MD5 'OfflinePlayer:AuditNode') ===")
    print(f"  Total Wire Bytes   : {len(uuid_bytes)} bytes")
    print(format_hexdump(uuid_bytes))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Minecraft Wire-Frame Hexdump Inspector")
    parser.add_argument("--host", default="127.0.0.1", help="Sample hostname for framing")
    parser.add_argument("--port", type=int, default=25565, help="Sample port for framing")
    parser.add_argument("--self-test", action="store_true", help="Run silent assertion checks for CI")
    args = parser.parse_args()
    return run_inspector(args.host, args.port, args.self_test)


if __name__ == "__main__":
    sys.exit(main())
