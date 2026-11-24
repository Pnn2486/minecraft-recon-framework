"""The test player (ghost mode), a headless client for offline-mode servers"""

import socket
import struct
import time
import zlib
from recon import settings
from recon.exceptions import (
    AuthenticationError,
    OnlineModeRequiredError,
    ProtocolFramingError,
    ReconError,
)
from recon.protocols.chat import decode_chat_packet
from recon.protocols.diagnostics import SessionStats
from recon.protocols.ghost_profiles import GhostProfile, UnsupportedProtocolError, get_profile
from recon.protocols.ping import mc_status_ping
from recon.utils.nbt import read_network_nbt
from recon.utils.text import component_to_text, json_text_to_plain, strip_codes
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
    """Transmits a Minecraft packet, applying RFC 1950 zlib compression when active"""
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
    """Reads a complete packet frame from the socket, decompressing when threshold >= 0"""
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
    """Builds the login start packet, what follows the username depends on the version"""
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


CHAT_KIND_SETTINGS = {
    "player": "show_player_chat",
    "system": "show_system_chat",
    "disguised": "show_disguised_chat",
    "chat": "show_plain_chat",
}


def _report_chat(profile: GhostProfile, pkt_id: int, data: bytes, stats: SessionStats) -> None:
    cfg = settings.current()["chat"]
    message = decode_chat_packet(profile, pkt_id, data)
    stats.chat(message is not None, pkt_id, data)  # counted even when hidden
    stamp = time.strftime("%H:%M:%S ") if cfg["timestamps"] else ""
    if message is None:
        if cfg["show_undecoded"]:
            print(f"[CHAT] {stamp}packet 0x{pkt_id:02X} ({len(data)} bytes, not decoded)")
        return
    if not cfg.get(CHAT_KIND_SETTINGS.get(message.kind, ""), True):
        return
    label = f"({message.kind}) " if cfg["show_kind_label"] else ""
    print(f"[CHAT] {stamp}{label}{message.text}")


def _disconnect_reason(profile: GhostProfile, data: bytes) -> str:
    """The reason text of a Disconnect packet, or a size note when it cannot be read"""
    try:
        if profile.text_is_json:
            reason = json_text_to_plain(read_string_bytes(data, 0)[0])
        else:
            reason = strip_codes(component_to_text(read_network_nbt(data, 0)[0]))
    except ProtocolFramingError:
        reason = ""
    return reason or f"({len(data)} bytes, not decoded)"


AUTO_PROTOCOL = "auto"


def detect_protocol_version(host: str, port: int = 25565, timeout: float = 5.0) -> tuple[int, str]:
    """Asks the server which protocol it speaks with a status ping, gives (number, version name)"""
    status = mc_status_ping(host, port, timeout=timeout, measure_latency=False)
    version = status.get("version")
    protocol = version.get("protocol") if isinstance(version, dict) else None
    if not isinstance(protocol, int) or isinstance(protocol, bool) or protocol < 0:
        raise ProtocolFramingError("The server status reply has no usable protocol number. Pass --protocol-version explicitly.")
    return protocol, str(version.get("name", "unknown")) if isinstance(version, dict) else "unknown"


def headless_ghost_stream(
    host: str,
    port: int = 25565,
    username: str = "AuditNode",
    protocol_version: int | str = AUTO_PROTOCOL,
    duration: int = 30,
    timeout: float = 10.0,
    diagnostics: bool = False,
) -> None:
    """Joins an offline-mode server, echoes keep-alives and prints the chat, protocol_version can also be auto"""
    if protocol_version == AUTO_PROTOCOL:
        protocol, server_name = detect_protocol_version(host, port, timeout)
        print(f"[+] Detected server version: {describe(protocol)}; the server calls itself {server_name!r}")
    elif isinstance(protocol_version, int):
        protocol = protocol_version
    else:
        raise UnsupportedProtocolError(f"protocol_version must be a number or {AUTO_PROTOCOL!r}, got {protocol_version!r}")
    profile = get_profile(protocol)
    compression_threshold = -1
    state = "login"  # login -> (configuration ->) play
    stats = SessionStats(profile)

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            stats.mark("connected")
            handshake = pack_varint(0x00) + pack_varint(protocol) + pack_string(host) + struct.pack(">H", port) + pack_varint(2)
            _send_framed_packet(sock, handshake, compression_threshold)
            _send_framed_packet(sock, _build_login_start_packet(username, profile), compression_threshold)

            start_ts = time.time()
            while time.time() - start_ts < duration:
                pkt_id, data = _recv_framed_packet(sock, compression_threshold)
                stats.packet(state, pkt_id, len(data))

                if state == "login":
                    if pkt_id == 0x00:
                        reason, _ = read_string_bytes(data, 0)
                        raise AuthenticationError(f"Login disconnect (0x00): {reason}")

                    elif pkt_id == 0x01:
                        raise OnlineModeRequiredError("Server sent an encryption request (0x01). The target has online-mode=true.")

                    elif pkt_id == 0x03:
                        compression_threshold, _ = read_varint_bytes(data, 0)
                        stats.compression = compression_threshold
                        print(f"[+] Compression threshold set by the server (zlib): {compression_threshold} bytes")

                    elif pkt_id == 0x02:
                        stats.mark("login")
                        if profile.has_configuration_phase:
                            _send_framed_packet(sock, pack_varint(profile.login_acknowledged_out), compression_threshold)
                            state = "configuration"
                            print(f"[+] Login success (0x02): '{username}' entering the configuration phase.")
                        else:
                            state = "play"
                            stats.mark("play")
                            print(f"[+] Login success (0x02): '{username}' entered the play state.")

                elif state == "configuration":
                    if pkt_id == profile.config_disconnect_in:
                        print(f"[!] Server disconnect during configuration (0x{pkt_id:02X}): {_disconnect_reason(profile, data)}")
                        stats.end_reason = "server disconnected during configuration"
                        break

                    elif pkt_id == profile.config_keep_alive_in and data:
                        _send_framed_packet(sock, pack_varint(profile.config_keep_alive_out) + data, compression_threshold)
                        print("[~] Echoed keep-alive (configuration)")

                    elif pkt_id == profile.config_ping_in and len(data) == 4:
                        _send_framed_packet(sock, pack_varint(profile.config_pong_out) + data, compression_threshold)

                    elif pkt_id == profile.config_known_packs_in:
                        # Reply "no known packs" (empty array); the server waits for this reply
                        _send_framed_packet(sock, pack_varint(profile.config_known_packs_out) + pack_varint(0), compression_threshold)

                    elif pkt_id == profile.config_finish_in:
                        _send_framed_packet(sock, pack_varint(profile.config_finish_ack_out), compression_threshold)
                        state = "play"
                        stats.mark("play")
                        print(f"[+] Configuration finished: '{username}' entered the play state.")

                else:
                    if pkt_id == profile.play_keep_alive_in and data:
                        # The token is an int, VarInt or long depending on the version. Echoing the raw bytes works for all of them
                        pong_frame = pack_varint(profile.play_keep_alive_out) + data
                        _send_framed_packet(sock, pong_frame, compression_threshold)
                        stats.keep_alive()
                        if settings.get("output", "show_keep_alives"):
                            print(f"[~] Echoed keep-alive (0x{profile.play_keep_alive_out:02X}): {len(data)} bytes")

                    elif pkt_id in profile.play_chat_json_ids or pkt_id in profile.play_chat_opaque_ids:
                        _report_chat(profile, pkt_id, data, stats)

                    elif pkt_id == profile.play_disconnect:
                        print(f"[!] Server disconnect in the play state (0x{pkt_id:02X}): {_disconnect_reason(profile, data)}")
                        stats.end_reason = "server disconnected the test player"
                        break

    except OSError as exc:
        raise ReconError(f"Ghost client socket error on {host}:{port}: {exc}") from exc
    finally:
        if diagnostics:
            for line in stats.report():
                print(line)
