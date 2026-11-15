"""
Protocol 4: Offline-Mode Play-State Headless Client.
Supports dynamic Zlib compression (0x03), Keep-Alive heartbeat echoing,
and real-time Chat packet extraction.
"""

import socket
import struct
import time
import zlib
from recon.exceptions import (
    AuthenticationError,
    OnlineModeRequiredError,
    ProtocolFramingError,
    ReconError,
)
from recon.utils.varint import (
    pack_varint,
    pack_string,
    recv_exact,
    read_varint_sock,
    read_varint_bytes,
    read_string_bytes,
    offline_player_uuid_bytes,
)


def _send_framed_packet(sock: socket.socket, payload: bytes, compression_threshold: int) -> None:
    """Transmits a Minecraft packet, applying RFC 1950 zlib compression when active."""
    if compression_threshold < 0:
        sock.sendall(pack_varint(len(payload)) + payload)
    else:
        if len(payload) < compression_threshold:
            body = pack_varint(0) + payload
            sock.sendall(pack_varint(len(body)) + body)
        else:
            compressed = zlib.compress(payload)
            body = pack_varint(len(payload)) + compressed
            sock.sendall(pack_varint(len(body)) + body)


def _recv_framed_packet(sock: socket.socket, compression_threshold: int) -> tuple[int, bytes]:
    """Reads a complete packet frame from the socket, decompressing when threshold >= 0."""
    frame_len = read_varint_sock(sock)
    raw_frame = recv_exact(sock, frame_len)

    if compression_threshold >= 0:
        uncompressed_len, offset = read_varint_bytes(raw_frame, 0)
        if uncompressed_len == 0:
            payload = raw_frame[offset:]
        else:
            try:
                payload = zlib.decompress(raw_frame[offset:])
            except zlib.error as exc:
                raise ProtocolFramingError(f"Zlib stream decompression error: {exc}") from exc
    else:
        payload = raw_frame

    pkt_id, offset = read_varint_bytes(payload, 0)
    return pkt_id, payload[offset:]


def _build_login_start_packet(username: str, protocol_version: int) -> bytes:
    """
    Constructs Login Start (0x00) tailored to the target protocol version:
    - Protocol <= 758 (1.16.5 - 1.18.2): [0x00] [String: Username]
    - Protocol >= 764 (1.20.2 - 1.21+):  [0x00] [String: Username] [UUID: 16 bytes]
    """
    if protocol_version >= 764:
        return pack_varint(0x00) + pack_string(username) + offline_player_uuid_bytes(username)
    return pack_varint(0x00) + pack_string(username)


def headless_ghost_stream(
    host: str,
    port: int = 25565,
    username: str = "AuditNode",
    protocol_version: int = 754,
    duration: int = 30,
    timeout: float = 10.0,
) -> None:
    """
    Connects to an offline-mode server (`online-mode=false`), negotiates zlib compression,
    transitions to Play State, echoes 64-bit Keep-Alive tokens, and streams chat frames.
    """
    compression_threshold = -1
    in_play_state = False

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            handshake = (
                pack_varint(0x00)
                + pack_varint(protocol_version)
                + pack_string(host)
                + struct.pack(">H", port)
                + pack_varint(2)
            )
            _send_framed_packet(sock, handshake, compression_threshold)

            login_start = _build_login_start_packet(username, protocol_version)
            _send_framed_packet(sock, login_start, compression_threshold)

            start_ts = time.time()
            while time.time() - start_ts < duration:
                pkt_id, data = _recv_framed_packet(sock, compression_threshold)

                if not in_play_state:
                    if pkt_id == 0x00:
                        reason, _ = read_string_bytes(data, 0)
                        raise AuthenticationError(f"Login Disconnect (0x00): {reason}")

                    elif pkt_id == 0x01:
                        raise OnlineModeRequiredError(
                            "Server issued Encryption Request (0x01). Target has online-mode=true."
                        )

                    elif pkt_id == 0x03:
                        compression_threshold, _ = read_varint_bytes(data, 0)
                        print(f"[+] Negotiated Zlib Compression Threshold: {compression_threshold} bytes")

                    elif pkt_id == 0x02:
                        in_play_state = True
                        print(f"[+] Login Success (0x02): '{username}' entered Play State.")

                else:
                    if pkt_id == 0x1F and len(data) == 8:
                        keep_alive_id = struct.unpack(">q", data)[0]
                        pong_frame = pack_varint(0x10) + struct.pack(">q", keep_alive_id)
                        _send_framed_packet(sock, pong_frame, compression_threshold)
                        print(f"[~] Echoed Keep-Alive Heartbeat (0x10): ID={keep_alive_id}")

                    elif pkt_id == 0x0E:
                        chat_json, _ = read_string_bytes(data, 0)
                        print(f"[CHAT] {chat_json}")

                    elif pkt_id == 0x19:
                        reason, _ = read_string_bytes(data, 0)
                        print(f"[!] Server Play-State Disconnect (0x19): {reason}")
                        break

    except OSError as exc:
        raise ReconError(f"Ghost client socket error on {host}:{port}: {exc}") from exc
