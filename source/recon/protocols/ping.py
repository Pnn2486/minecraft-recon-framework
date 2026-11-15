"""
Protocol 1: TCP Server List Ping (Packet 0x00 Status + Packet 0x01 Latency Probe).
"""

import json
import socket
import struct
import time
from recon.exceptions import ProtocolFramingError, ReconError
from recon.utils.varint import (
    pack_varint,
    pack_string,
    recv_exact,
    read_varint_sock,
    read_varint_bytes,
    read_string_bytes,
)


def mc_status_ping(
    host: str,
    port: int = 25565,
    timeout: float = 5.0,
    protocol_version: int = 767,
    measure_latency: bool = True,
) -> dict:
    """
    Executes a TCP Server List Ping (0x00) and optional Latency Ping/Pong (0x01).
    Returns the parsed JSON dictionary enriched with `latency_ms` when enabled.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            handshake_payload = (
                pack_varint(0x00)
                + pack_varint(protocol_version)
                + pack_string(host)
                + struct.pack(">H", port)
                + pack_varint(1)
            )
            sock.sendall(pack_varint(len(handshake_payload)) + handshake_payload)
            sock.sendall(b"\x01\x00")

            frame_len = read_varint_sock(sock)
            frame_data = recv_exact(sock, frame_len)

            pkt_id, offset = read_varint_bytes(frame_data, 0)
            if pkt_id != 0x00:
                raise ProtocolFramingError(f"Expected Status Response ID 0x00, received {hex(pkt_id)}")

            raw_json, _ = read_string_bytes(frame_data, offset)
            descriptor: dict = json.loads(raw_json)

            if measure_latency:
                timestamp_ms = int(time.time() * 1000)
                ping_payload = pack_varint(0x01) + struct.pack(">q", timestamp_ms)
                t_start = time.perf_counter()
                sock.sendall(pack_varint(len(ping_payload)) + ping_payload)

                pong_len = read_varint_sock(sock)
                pong_data = recv_exact(sock, pong_len)
                t_elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

                pong_id, _ = read_varint_bytes(pong_data, 0)
                if pong_id == 0x01:
                    descriptor["latency_ms"] = t_elapsed_ms

            return descriptor

    except json.JSONDecodeError as exc:
        raise ProtocolFramingError(f"Malformed JSON in Server List Ping response: {exc}") from exc
    except OSError as exc:
        raise ReconError(f"TCP Ping socket failure on {host}:{port}: {exc}") from exc
