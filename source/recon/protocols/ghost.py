"""
Protocol 4: Offline-Mode Play-State Headless Client.
Supports dynamic Zlib compression (0x03), the 1.20.2+ Configuration phase,
Keep-Alive heartbeat echoing, and chat packet reporting.

Packet IDs are version specific. The table is `recon.protocols.ghost_profile_data` and the logic that uses it is `recon.protocols.ghost_profiles`. The protocol version can be given as a number or as "auto", which asks the server for it with a status ping first.
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
from recon.protocols.ghost_profiles import GhostProfile, get_profile
from recon.protocols.ping import mc_status_ping
from recon.utils.versions import describe
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


def _build_login_start_packet(username: str, profile: GhostProfile) -> bytes:
    """
    Constructs Login Start (0x00). The bytes after the username depend on the version
    (see LOGIN_START_FORMATS in ghost_profiles.py).
    """
    packet = pack_varint(0x00) + pack_string(username)
    fmt = profile.login_start_format
    if fmt == "name_sig":
        packet += b"\x00"  # no signature data
    elif fmt == "name_sig_uuid":
        packet += b"\x00\x00"  # no signature data, no UUID
    elif fmt == "name_uuid_opt":
        packet += b"\x00"  # no UUID
    elif fmt == "name_uuid":
        packet += offline_player_uuid_bytes(username)
    return packet


def _report_chat(profile: GhostProfile, pkt_id: int, data: bytes) -> None:
    if pkt_id in profile.play_chat_json_ids:
        try:
            chat_json, _ = read_string_bytes(data, 0)
            print(f"[CHAT] {chat_json}")
            return
        except ProtocolFramingError:
            pass
    # Signed player chat and NBT text components are not decoded.
    print(f"[CHAT] packet 0x{pkt_id:02X} ({len(data)} bytes, not decoded)")


AUTO_PROTOCOL = "auto"


def detect_protocol_version(host: str, port: int = 25565, timeout: float = 5.0) -> tuple[int, str]:
    """
    Asks the server which protocol it speaks, using a plain status ping.
    Returns (protocol number, version name as the server reports it).

    Servers behind a proxy or a multi-version plugin may report a different number than
    their backend; pass an explicit protocol number if detection picks the wrong one.
    """
    status = mc_status_ping(host, port, timeout=timeout, measure_latency=False)
    version = status.get("version")
    protocol = version.get("protocol") if isinstance(version, dict) else None
    if not isinstance(protocol, int) or isinstance(protocol, bool) or protocol < 0:
        raise ProtocolFramingError(
            "The server status reply has no usable protocol number. Pass --protocol-version explicitly."
        )
    return protocol, str(version.get("name", "unknown"))


def headless_ghost_stream(
    host: str,
    port: int = 25565,
    username: str = "AuditNode",
    protocol_version: int | str = AUTO_PROTOCOL,
    duration: int = 30,
    timeout: float = 10.0,
) -> None:
    """
    Connects to an offline-mode server (`online-mode=false`), negotiates zlib compression,
    passes through the Configuration phase when the version has one, enters Play State,
    echoes Keep-Alive tokens, and reports chat packets.

    `protocol_version` is a protocol number, or "auto" (the default) to detect it with a
    status ping on the same host and port first.

    Raises UnsupportedProtocolError (before the login connection) when the protocol has no profile.
    """
    if protocol_version == AUTO_PROTOCOL:
        protocol_version, server_name = detect_protocol_version(host, port, timeout)
        print(f"[+] Detected server version: {describe(protocol_version)}; the server calls itself {server_name!r}")
    profile = get_profile(protocol_version)
    compression_threshold = -1
    state = "login"  # login -> (configuration ->) play

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
            _send_framed_packet(sock, _build_login_start_packet(username, profile), compression_threshold)

            start_ts = time.time()
            while time.time() - start_ts < duration:
                pkt_id, data = _recv_framed_packet(sock, compression_threshold)

                if state == "login":
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
                        if profile.has_configuration_phase:
                            _send_framed_packet(
                                sock, pack_varint(profile.login_acknowledged_out), compression_threshold
                            )
                            state = "configuration"
                            print(f"[+] Login Success (0x02): '{username}' entering Configuration phase.")
                        else:
                            state = "play"
                            print(f"[+] Login Success (0x02): '{username}' entered Play State.")

                elif state == "configuration":
                    if pkt_id == profile.config_disconnect_in:
                        print(f"[!] Server Configuration Disconnect (0x{pkt_id:02X})")
                        break

                    elif pkt_id == profile.config_keep_alive_in and data:
                        _send_framed_packet(
                            sock, pack_varint(profile.config_keep_alive_out) + data, compression_threshold
                        )
                        print("[~] Echoed Keep-Alive (configuration)")

                    elif pkt_id == profile.config_ping_in and len(data) == 4:
                        _send_framed_packet(
                            sock, pack_varint(profile.config_pong_out) + data, compression_threshold
                        )

                    elif pkt_id == profile.config_known_packs_in:
                        # Reply "no known packs" (empty array); the server waits for this reply.
                        _send_framed_packet(
                            sock, pack_varint(profile.config_known_packs_out) + pack_varint(0), compression_threshold
                        )

                    elif pkt_id == profile.config_finish_in:
                        _send_framed_packet(
                            sock, pack_varint(profile.config_finish_ack_out), compression_threshold
                        )
                        state = "play"
                        print(f"[+] Configuration finished: '{username}' entered Play State.")

                else:
                    if pkt_id == profile.play_keep_alive_in and data:
                        # The token is an int, VarInt or long depending on the version; echoing the raw bytes works for all.
                        pong_frame = pack_varint(profile.play_keep_alive_out) + data
                        _send_framed_packet(sock, pong_frame, compression_threshold)
                        print(f"[~] Echoed Keep-Alive Heartbeat (0x{profile.play_keep_alive_out:02X}): {len(data)} bytes")

                    elif pkt_id in profile.play_chat_json_ids or pkt_id in profile.play_chat_opaque_ids:
                        _report_chat(profile, pkt_id, data)

                    elif pkt_id == profile.play_disconnect:
                        reason = f"({len(data)} bytes, not decoded)"
                        if profile.text_is_json:
                            try:
                                reason, _ = read_string_bytes(data, 0)
                            except ProtocolFramingError:
                                pass
                        print(f"[!] Server Play-State Disconnect (0x{pkt_id:02X}): {reason}")
                        break

    except OSError as exc:
        raise ReconError(f"Ghost client socket error on {host}:{port}: {exc}") from exc
