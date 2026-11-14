#!/usr/bin/env python3
"""
Hex & VarInt Packet Frame Inspector for protocol debugging.
Execute from the repository root with:
    PYTHONPATH=src python3 tools/packet_inspector.py
"""

import struct
from mcrecon.utils.varint import pack_varint, pack_string, read_varint_bytes


def format_hexdump(data: bytes, bytes_per_line: int = 16) -> str:
    """Formats a byte string into a classic side-by-side Hex + ASCII table."""
    lines = []
    for offset in range(0, len(data), bytes_per_line):
        chunk = data[offset : offset + bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{offset:04X}  {hex_part:<{bytes_per_line * 3}}  |{ascii_part}|")
    return "\n".join(lines)


def inspect_sample_handshake(host: str = "127.0.0.1", port: int = 25565) -> None:
    """Builds and inspects a raw TCP 0x00 Handshake packet."""
    body = (
        b"\x00"
        + pack_varint(767)
        + pack_string(host)
        + struct.pack(">H", port)
        + pack_varint(1)
    )
    full_frame = pack_varint(len(body)) + body
    pkt_len, next_idx = read_varint_bytes(full_frame, 0)

    print("=== Minecraft TCP Handshake Frame Inspector ===")
    print(f"Target             : {host}:{port}")
    print(f"Total Wire Bytes   : {len(full_frame)}")
    print(f"Decoded Frame Len  : {pkt_len} bytes (VarInt header uses {next_idx} byte(s))\n")
    print(format_hexdump(full_frame))


if __name__ == "__main__":
    inspect_sample_handshake()
