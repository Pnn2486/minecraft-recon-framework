"""
Loopback tests for the ping, query, RCON and ghost clients, plus CLI argument validation.

Every test talks to a tiny fake server bound to 127.0.0.1 on an ephemeral port,
so nothing ever leaves the local machine.

Run from the repository root (the folder containing source/ and tests/):

    Linux / macOS (bash/zsh) :
        PYTHONPATH=source python3 -m unittest discover -s tests -v

    Windows (PowerShell):
        $env:PYTHONPATH="source"; python -m unittest discover -s tests -v
"""

import contextlib
import io
import json
import socket
import struct
import threading
import unittest

from recon import cli
from recon.exceptions import (
    AuthenticationError,
    OnlineModeRequiredError,
    ProtocolFramingError,
    ReconError,
)
from recon.protocols.ghost import headless_ghost_stream
from recon.protocols.ghost_profiles import PROFILES, GhostProfile, UnsupportedProtocolError
from recon.utils.versions import VERSION_NAMES, describe, protocol_for_name, version_range
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import RCONClient, rcon_command

HOST = "127.0.0.1"


# --- Independent wire helpers (deliberately not imported from `recon`) -------------


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError("peer closed the connection")
        data += chunk
    return data


def _read_varint(sock: socket.socket) -> int:
    value = shift = 0
    while True:
        byte = _recv_exact(sock, 1)[0]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value
        shift += 7


def _frame(payload: bytes) -> bytes:
    return _varint(len(payload)) + payload


def _mc_string(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return _varint(len(encoded)) + encoded


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


# --- Fake servers -------------------------------------------------------------------


class TcpServer:
    """Accepts loopback connections and runs `handler(conn)` for each of them."""

    def __init__(self, handler) -> None:
        self._handler = handler
        self._stop = threading.Event()
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind((HOST, 0))
        self._listener.listen(5)
        self._listener.settimeout(0.2)
        self.port: int = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)

    def __enter__(self) -> "TcpServer":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._listener.close()

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            conn.settimeout(5.0)
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        try:
            with conn:
                self._handler(conn)
        except (OSError, EOFError):
            pass


class QueryServer:
    """Minimal GameSpy4 responder; `token` is the raw challenge-token bytes it hands out."""

    def __init__(self, token: bytes = b"9513307\x00") -> None:
        self.token = token
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((HOST, 0))
        self._sock.settimeout(0.2)
        self.port: int = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> "QueryServer":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._sock.close()

    def _full_stat(self, session: int) -> bytes:
        pairs = [
            b"hostname", b"Mock", b"gametype", b"SMP", b"version", b"1.21",
            b"plugins", b"", b"map", b"world", b"numplayers", b"2",
            b"maxplayers", b"20", b"hostport", b"25565",
        ]
        return (
            b"\x00" + struct.pack(">I", session) + b"splitnum\x00\x80\x00"
            + b"\x00".join(pairs)
            + b"\x00\x00\x01player_\x00\x00" + b"Alice\x00Bob\x00\x00"
        )

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            _, kind, session = struct.unpack(">HBI", data[:7])
            if kind == 0x09:
                self._sock.sendto(struct.pack(">BI", 0x09, session) + self.token, addr)
            elif kind == 0x00:
                self._sock.sendto(self._full_stat(session), addr)


def _status_handler(conn: socket.socket) -> None:
    _recv_exact(conn, _read_varint(conn))  # handshake
    _recv_exact(conn, _read_varint(conn))  # status request
    descriptor = {
        "version": {"name": "1.21", "protocol": 767},
        "players": {"online": 2, "max": 20},
        "description": "mock server",
    }
    conn.sendall(_frame(_varint(0x00) + _mc_string(json.dumps(descriptor))))
    ping = _recv_exact(conn, _read_varint(conn))
    if ping[0] == 0x01:
        conn.sendall(_frame(ping))


def _status_reply(conn: socket.socket, descriptor: dict) -> None:
    """Answers one status request (after the handshake has been read)."""
    _recv_exact(conn, _read_varint(conn))  # status request
    conn.sendall(_frame(_varint(0x00) + _mc_string(json.dumps(descriptor))))


def _parse_handshake(frame: bytes) -> tuple[int, int]:
    """Returns (protocol number, next state) from a Handshake packet body."""
    pos = 1  # packet id 0x00
    protocol = shift = 0
    while True:
        byte = frame[pos]
        pos += 1
        protocol |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    host_len = frame[pos]
    pos += 1 + host_len + 2  # host string (short) + port
    return protocol, frame[pos]


def _bad_json_status_handler(conn: socket.socket) -> None:
    _recv_exact(conn, _read_varint(conn))
    _recv_exact(conn, _read_varint(conn))
    conn.sendall(_frame(_varint(0x00) + _mc_string("{not valid json")))


def _rcon_handler(conn: socket.socket) -> None:
    while True:
        size = struct.unpack("<i", _recv_exact(conn, 4))[0]
        body = _recv_exact(conn, size)
        request_id, packet_type = struct.unpack("<ii", body[:8])
        text = body[8:-2].decode("utf-8")
        if packet_type == 3:  # auth
            reply_id = request_id if text == "secret" else -1
            conn.sendall(struct.pack("<iii", 10, reply_id, 2) + b"\x00\x00")
        elif packet_type == 2:  # command
            reply = b"There are 2 of a max of 20 players online: Alice, Bob"
            conn.sendall(struct.pack("<iii", 10 + len(reply), request_id, 0) + reply + b"\x00\x00")


def _read_compressed_packet(conn: socket.socket) -> bytes:
    """Reads one client frame after Set Compression (threshold 256, small packets only)."""
    frame = _recv_exact(conn, _read_varint(conn))
    assert frame[0] == 0, "expected uncompressed body (data length 0)"
    return frame[1:]


def _compressed(payload: bytes) -> bytes:
    return _frame(_varint(0) + payload)  # below threshold: data length 0


def _ghost_handler_factory(state: dict):
    """Fake 1.16.5 (protocol 754) server: no Configuration phase."""
    keep_alive_id = 123456789

    def handler(conn: socket.socket) -> None:
        _recv_exact(conn, _read_varint(conn))  # handshake
        state["login_len"] = len(_recv_exact(conn, _read_varint(conn)))  # login start
        conn.sendall(_frame(_varint(0x03) + _varint(256)))  # set compression, threshold 256
        conn.sendall(_compressed(_varint(0x02) + b"\x00" * 20))  # login success
        conn.sendall(_compressed(_varint(0x1F) + struct.pack(">q", keep_alive_id)))
        reply = _read_compressed_packet(conn)
        state["echo_ok"] = reply == _varint(0x10) + struct.pack(">q", keep_alive_id)
        conn.sendall(_compressed(_varint(0x0E) + _mc_string('{"text":"<Alice> hello"}')))
        conn.sendall(_compressed(_varint(0x19) + _mc_string('{"text":"bye"}')))

    return handler


def _ghost_121_handler_factory(state: dict):
    """Fake 1.21.1 (protocol 767) server: Login -> Configuration -> Play."""
    keep_alive_id = 987654321
    state["steps"] = []

    def handler(conn: socket.socket) -> None:
        _recv_exact(conn, _read_varint(conn))  # handshake
        state["login_len"] = len(_recv_exact(conn, _read_varint(conn)))  # login start
        conn.sendall(_frame(_varint(0x03) + _varint(256)))
        conn.sendall(_compressed(_varint(0x02) + b"\x00" * 20 + _varint(0) + b"\x00"))  # login success

        state["steps"].append(("login_ack", _read_compressed_packet(conn)))  # expects 0x03
        conn.sendall(_compressed(_varint(0x04) + struct.pack(">q", 42)))  # config keep alive
        state["steps"].append(("config_keepalive_echo", _read_compressed_packet(conn)))
        conn.sendall(_compressed(_varint(0x0E) + _varint(0)))  # clientbound known packs (empty)
        state["steps"].append(("known_packs_reply", _read_compressed_packet(conn)))
        conn.sendall(_compressed(_varint(0x03)))  # finish configuration
        state["steps"].append(("finish_ack", _read_compressed_packet(conn)))

        conn.sendall(_compressed(_varint(0x26) + struct.pack(">q", keep_alive_id)))  # play keep alive
        state["steps"].append(("play_keepalive_echo", _read_compressed_packet(conn)))
        conn.sendall(_compressed(_varint(0x6C) + b"\x0a\x00"))  # system chat (opaque bytes)
        conn.sendall(_compressed(_varint(0x1D) + b"\x0a\x00"))  # play disconnect

    state["keep_alive_id"] = keep_alive_id
    return handler


def _online_mode_handler(conn: socket.socket) -> None:
    _recv_exact(conn, _read_varint(conn))
    _recv_exact(conn, _read_varint(conn))
    conn.sendall(_frame(_varint(0x01) + b"\x00" * 4))  # Encryption Request


# --- Tests --------------------------------------------------------------------------


class TestPing(unittest.TestCase):
    def test_status_and_latency(self) -> None:
        with TcpServer(_status_handler) as server:
            result = mc_status_ping(HOST, server.port, timeout=5.0)
        self.assertEqual(result["version"]["protocol"], 767)
        self.assertEqual(result["players"]["online"], 2)
        self.assertIn("latency_ms", result)

    def test_malformed_json_raises_framing_error(self) -> None:
        with TcpServer(_bad_json_status_handler) as server:
            with self.assertRaises(ProtocolFramingError):
                mc_status_ping(HOST, server.port, timeout=5.0)

    def test_closed_port_raises_recon_error(self) -> None:
        with self.assertRaises(ReconError):
            mc_status_ping(HOST, _unused_port(), timeout=2.0)


class TestQuery(unittest.TestCase):
    def test_full_stat(self) -> None:
        with QueryServer() as server:
            result = gamespy4_full_query(HOST, server.port, timeout=5.0)
        self.assertEqual(result["metadata"]["hostname"], "Mock")
        self.assertEqual(result["players"], ["Alice", "Bob"])
        self.assertEqual(result["player_count"], 2)

    def test_negative_challenge_token_is_accepted(self) -> None:
        with QueryServer(token=b"-5\x00") as server:
            result = gamespy4_full_query(HOST, server.port, timeout=5.0)
        self.assertEqual(result["player_count"], 2)

    def test_non_numeric_challenge_token_raises_framing_error(self) -> None:
        with QueryServer(token=b"abc\x00") as server:
            with self.assertRaises(ProtocolFramingError):
                gamespy4_full_query(HOST, server.port, timeout=5.0)


class TestRcon(unittest.TestCase):
    def test_authenticate_and_execute(self) -> None:
        with TcpServer(_rcon_handler) as server:
            with RCONClient(HOST, server.port, timeout=5.0) as client:
                client.authenticate("secret")
                output = client.execute("list")
        self.assertIn("Alice", output)

    def test_wrong_password_raises_authentication_error(self) -> None:
        with TcpServer(_rcon_handler) as server:
            with self.assertRaises(AuthenticationError):
                rcon_command(HOST, server.port, "wrong", "list", timeout=5.0)

    def test_one_shot_helper(self) -> None:
        with TcpServer(_rcon_handler) as server:
            output = rcon_command(HOST, server.port, "secret", "list", timeout=5.0)
        self.assertIn("2 of a max of 20", output)


class TestGhost(unittest.TestCase):
    def _run_ghost(self, protocol_version: int, handler_factory=_ghost_handler_factory) -> tuple[dict, str]:
        state: dict = {}
        captured = io.StringIO()
        with TcpServer(handler_factory(state)) as server:
            with contextlib.redirect_stdout(captured):
                headless_ghost_stream(
                    HOST,
                    port=server.port,
                    username="AuditNode",
                    protocol_version=protocol_version,
                    duration=5,
                    timeout=5.0,
                )
        return state, captured.getvalue()

    def test_protocol_754_login_has_no_uuid(self) -> None:
        state, output = self._run_ghost(754)
        self.assertEqual(state["login_len"], 1 + 1 + len("AuditNode"))
        self.assertTrue(state["echo_ok"])
        self.assertIn("Echoed Keep-Alive", output)
        self.assertIn("<Alice> hello", output)

    def test_protocol_767_full_login_configuration_play_flow(self) -> None:
        state, output = self._run_ghost(767, _ghost_121_handler_factory)
        self.assertEqual(state["login_len"], 1 + 1 + len("AuditNode") + 16)  # name + UUID
        steps = dict(state["steps"])
        self.assertEqual(steps["login_ack"], _varint(0x03))
        self.assertEqual(steps["config_keepalive_echo"], _varint(0x04) + struct.pack(">q", 42))
        self.assertEqual(steps["known_packs_reply"], _varint(0x07) + _varint(0))
        self.assertEqual(steps["finish_ack"], _varint(0x03))
        self.assertEqual(
            steps["play_keepalive_echo"], _varint(0x18) + struct.pack(">q", state["keep_alive_id"])
        )
        self.assertIn("Configuration finished", output)
        self.assertIn("packet 0x6C", output)
        self.assertIn("Play-State Disconnect (0x1D)", output)

    def test_unsupported_protocol_is_rejected_before_connecting(self) -> None:
        for version in (-1, 0, 5, 46, 600, 776, 99999):
            with self.subTest(version=version):
                with self.assertRaises(UnsupportedProtocolError):
                    headless_ghost_stream(HOST, port=_unused_port(), protocol_version=version, duration=1)

    def test_online_mode_server_raises(self) -> None:
        with TcpServer(_online_mode_handler) as server:
            with self.assertRaises(OnlineModeRequiredError):
                headless_ghost_stream(HOST, port=server.port, protocol_version=754, duration=5, timeout=5.0)


def _expected_login_start(profile: GhostProfile, username: str) -> bytes:
    """Independent description of the Login Start payload for each protocol era."""
    name = _mc_string(username)
    if profile.protocol <= 758:
        return name
    if profile.protocol == 759:
        return name + b"\x00"
    if profile.protocol == 760:
        return name + b"\x00\x00"
    if profile.protocol <= 763:
        return name + b"\x00"
    return name  # 764+: followed by a 16-byte UUID, checked separately


def _profile_handler_factory(profile: GhostProfile, state: dict):
    """Generic fake server for any profile: Login -> (Configuration) -> Play."""
    # The keep-alive token is a VarInt before 1.12.2 and a long afterwards; the client must echo raw bytes.
    token = _varint(300) if profile.protocol < 340 else struct.pack(">q", 1234567890123)
    state["token"] = token
    state["steps"] = {}

    def handler(conn: socket.socket) -> None:
        _recv_exact(conn, _read_varint(conn))  # handshake
        session(conn)

    def session(conn: socket.socket) -> None:
        login = _recv_exact(conn, _read_varint(conn))
        state["login"] = login
        conn.sendall(_frame(_varint(0x03) + _varint(256)))
        conn.sendall(_compressed(_varint(0x02) + b"\x00" * 20))  # login success

        if profile.has_configuration_phase:
            state["steps"]["login_ack"] = _read_compressed_packet(conn)
            conn.sendall(_compressed(_varint(profile.config_keep_alive_in) + struct.pack(">q", 42)))
            state["steps"]["config_keepalive"] = _read_compressed_packet(conn)
            if profile.config_known_packs_in >= 0:
                conn.sendall(_compressed(_varint(profile.config_known_packs_in) + _varint(0)))
                state["steps"]["known_packs"] = _read_compressed_packet(conn)
            conn.sendall(_compressed(_varint(profile.config_finish_in)))
            state["steps"]["finish_ack"] = _read_compressed_packet(conn)

        conn.sendall(_compressed(_varint(profile.play_keep_alive_in) + token))
        state["steps"]["play_keepalive"] = _read_compressed_packet(conn)
        for chat_id in sorted(profile.play_chat_json_ids):
            conn.sendall(_compressed(_varint(chat_id) + _mc_string('{"text":"hello"}')))
        for chat_id in sorted(profile.play_chat_opaque_ids):
            conn.sendall(_compressed(_varint(chat_id) + b"\x0a\x00\x00"))
        conn.sendall(_compressed(_varint(profile.play_disconnect) + _mc_string('{"text":"bye"}')))

    handler.session = session  # type: ignore[attr-defined]
    return handler


def _auto_server_handler_factory(profile: GhostProfile, state: dict, reported_protocol: int, reported_name: str):
    """Fake server that answers a status ping first and then a login on the same port."""
    login_session = _profile_handler_factory(profile, state).session  # type: ignore[attr-defined]

    def handler(conn: socket.socket) -> None:
        handshake = _recv_exact(conn, _read_varint(conn))
        _, next_state = _parse_handshake(handshake)
        if next_state == 1:
            _status_reply(conn, {"version": {"name": reported_name, "protocol": reported_protocol}})
        else:
            login_session(conn)

    return handler


class TestGhostAllProfiles(unittest.TestCase):
    """Runs the whole ghost flow against a fake server for every supported protocol."""

    def test_every_profile_completes_login_configuration_and_play(self) -> None:
        for protocol, profile in sorted(PROFILES.items()):
            with self.subTest(protocol=protocol, version=profile.name):
                state: dict = {}
                captured = io.StringIO()
                with TcpServer(_profile_handler_factory(profile, state)) as server:
                    with contextlib.redirect_stdout(captured):
                        headless_ghost_stream(
                            HOST, port=server.port, username="AuditNode",
                            protocol_version=protocol, duration=5, timeout=5.0,
                        )
                output = captured.getvalue()
                login = state["login"]
                prefix = _varint(0x00) + _expected_login_start(profile, "AuditNode")
                self.assertTrue(login.startswith(prefix), "Login Start prefix mismatch")
                extra = login[len(prefix):]
                self.assertEqual(len(extra), 16 if protocol >= 764 else 0)

                steps = state["steps"]
                self.assertEqual(
                    steps["play_keepalive"], _varint(profile.play_keep_alive_out) + state["token"]
                )
                if profile.has_configuration_phase:
                    self.assertEqual(steps["login_ack"], _varint(0x03))
                    self.assertEqual(steps["finish_ack"], _varint(profile.config_finish_ack_out))
                    self.assertEqual(
                        steps["config_keepalive"],
                        _varint(profile.config_keep_alive_out) + struct.pack(">q", 42),
                    )
                    if profile.config_known_packs_in >= 0:
                        self.assertEqual(
                            steps["known_packs"], _varint(profile.config_known_packs_out) + _varint(0)
                        )
                self.assertIn("Play-State Disconnect", output)
                if profile.play_chat_json_ids:
                    self.assertIn("hello" if profile.text_is_json else "not decoded", output)

    def test_login_start_formats_by_era(self) -> None:
        formats = {p: PROFILES[p].login_start_format for p in (47, 340, 754, 758, 759, 760, 761, 763, 764, 767)}
        self.assertEqual(
            formats,
            {47: "name", 340: "name", 754: "name", 758: "name", 759: "name_sig", 760: "name_sig_uuid",
             761: "name_uuid_opt", 763: "name_uuid_opt", 764: "name_uuid", 767: "name_uuid"},
        )

    def test_known_keep_alive_ids(self) -> None:
        # (protocol, clientbound keep alive, serverbound keep alive) for widely used versions
        expected = [
            (47, 0x00, 0x00),    # 1.8
            (340, 0x1F, 0x0B),   # 1.12.2
            (754, 0x1F, 0x10),   # 1.16.5
            (758, 0x21, 0x0F),   # 1.18.2
            (762, 0x23, 0x12),   # 1.19.4
            (763, 0x23, 0x12),   # 1.20.1
            (765, 0x24, 0x15),   # 1.20.4
            (767, 0x26, 0x18),   # 1.21.1
        ]
        for protocol, keep_in, keep_out in expected:
            with self.subTest(protocol=protocol):
                self.assertEqual(PROFILES[protocol].play_keep_alive_in, keep_in)
                self.assertEqual(PROFILES[protocol].play_keep_alive_out, keep_out)

    def test_configuration_phase_starts_at_764_and_known_packs_at_766(self) -> None:
        for protocol, profile in PROFILES.items():
            self.assertEqual(profile.has_configuration_phase, protocol >= 764, protocol)
            self.assertEqual(profile.config_known_packs_in >= 0, protocol >= 766, protocol)



class TestGhostAutoDetect(unittest.TestCase):
    """`--protocol-version auto`: ping first, then log in with the detected version."""

    def _run_auto(self, protocol: int, reported_protocol: int | None = None) -> tuple[dict, str]:
        profile = PROFILES[protocol]
        state: dict = {}
        captured = io.StringIO()
        handler = _auto_server_handler_factory(
            profile, state, reported_protocol if reported_protocol is not None else protocol, f"Mock {profile.name}"
        )
        with TcpServer(handler) as server:
            with contextlib.redirect_stdout(captured):
                headless_ghost_stream(HOST, port=server.port, duration=5, timeout=5.0)  # default is auto
        return state, captured.getvalue()

    def test_auto_is_the_default_and_picks_the_reported_profile(self) -> None:
        for protocol in (47, 340, 754, 759, 763, 765, 767, 775):
            with self.subTest(protocol=protocol):
                state, output = self._run_auto(protocol)
                self.assertIn(f"protocol {protocol})", output)
                self.assertIn("Detected server version", output)
                self.assertIn("Play-State Disconnect", output)
                expected_prefix = _varint(0x00) + _expected_login_start(PROFILES[protocol], "AuditNode")
                self.assertTrue(state["login"].startswith(expected_prefix))

    def test_unsupported_detected_version_is_reported_clearly(self) -> None:
        state: dict = {}
        handler = _auto_server_handler_factory(PROFILES[754], state, 600, "Mock future")
        with TcpServer(handler) as server:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(UnsupportedProtocolError) as ctx:
                    headless_ghost_stream(HOST, port=server.port, duration=5, timeout=5.0)
        self.assertIn("600", str(ctx.exception))
        self.assertIn("Mock future", out.getvalue())
        self.assertNotIn("login", state)  # never attempted a login

    def test_status_without_protocol_number_raises_framing_error(self) -> None:
        for descriptor in ({"description": "no version"}, {"version": {"name": "x", "protocol": "abc"}},
                           {"version": {"name": "x", "protocol": True}}, {"version": {"name": "x", "protocol": -1}}):
            with self.subTest(descriptor=descriptor):
                def handler(conn: socket.socket, d=descriptor) -> None:
                    _recv_exact(conn, _read_varint(conn))
                    _status_reply(conn, d)

                with TcpServer(handler) as server:
                    with self.assertRaises(ProtocolFramingError):
                        headless_ghost_stream(HOST, port=server.port, duration=5, timeout=5.0)

    def test_explicit_number_skips_detection(self) -> None:
        state: dict = {}
        captured = io.StringIO()
        with TcpServer(_profile_handler_factory(PROFILES[754], state)) as server:
            with contextlib.redirect_stdout(captured):
                headless_ghost_stream(HOST, port=server.port, protocol_version=754, duration=5, timeout=5.0)
        self.assertNotIn("Detected", captured.getvalue())

    def test_cli_defaults_to_auto(self) -> None:
        state: dict = {}
        handler = _auto_server_handler_factory(PROFILES[767], state, 767, "Mock 1.21.1")
        stdout = io.StringIO()
        with TcpServer(handler) as server:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["--quiet", "--host", HOST, "--mode", "ghost", "--port", str(server.port),
                                 "--duration", "5", "--timeout", "5"])
        self.assertEqual(code, 0)
        self.assertIn("Detected server version: Minecraft 1.21 - 1.21.1 (protocol 767)", stdout.getvalue())
        self.assertIn("Mock 1.21.1", stdout.getvalue())


class TestVersionNames(unittest.TestCase):
    """The protocol number <-> Minecraft version lookup."""

    def test_known_conversions(self) -> None:
        expected = {
            47: "1.8 - 1.8.9", 340: "1.12.2", 754: "1.16.4 - 1.16.5", 763: "1.20 - 1.20.1",
            767: "1.21 - 1.21.1", 5: "1.7.6 - 1.7.10",
        }
        for protocol, text in expected.items():
            with self.subTest(protocol=protocol):
                self.assertEqual(version_range(protocol), text)

    def test_names_map_back_to_protocols(self) -> None:
        for name, protocol in (("1.16.5", 754), ("1.8.9", 47), ("1.21.1", 767), ("1.7.10", 5), ("26.1", 775)):
            with self.subTest(name=name):
                self.assertEqual(protocol_for_name(name), protocol)
        self.assertIsNone(protocol_for_name("1.99"))
        self.assertIsNone(protocol_for_name("banana"))

    def test_every_release_name_is_unique_and_round_trips(self) -> None:
        seen: dict[str, int] = {}
        for protocol, names in VERSION_NAMES.items():
            for name in names:
                self.assertNotIn(name, seen, f"{name} listed under two protocols")
                seen[name] = protocol
                self.assertEqual(protocol_for_name(name), protocol)

    def test_every_supported_profile_has_a_readable_name(self) -> None:
        for protocol, profile in PROFILES.items():
            self.assertIsNotNone(version_range(protocol), protocol)
            self.assertEqual(profile.name, version_range(protocol))

    def test_unknown_number_is_described_not_crashing(self) -> None:
        self.assertIn("unknown", describe(600))
        self.assertIn("600", describe(600))


class TestGhostVersionNamesInOutput(unittest.TestCase):
    def test_unsupported_but_known_version_is_named_in_the_error(self) -> None:
        state: dict = {}
        handler = _auto_server_handler_factory(PROFILES[754], state, 5, "Old server")
        with TcpServer(handler) as server:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(UnsupportedProtocolError) as ctx:
                    headless_ghost_stream(HOST, port=server.port, duration=5, timeout=5.0)
        self.assertIn("1.7.6 - 1.7.10", str(ctx.exception))

    def test_supported_list_in_the_error_uses_version_names(self) -> None:
        with self.assertRaises(UnsupportedProtocolError) as ctx:
            headless_ghost_stream(HOST, port=_unused_port(), protocol_version=600, duration=1)
        self.assertIn("1.16.4 - 1.16.5 (754)", str(ctx.exception))


class TestCliValidation(unittest.TestCase):
    BASE = ["--quiet", "--host", HOST, "--mode", "ping"]

    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(argv)
        return code, stdout.getvalue()

    def test_out_of_range_numbers_exit_with_code_2(self) -> None:
        bad_values = [
            ["--port", "0"],
            ["--port", "70000"],
            ["--port", "abc"],
            ["--rcon-port", "99999"],
            ["--timeout", "-1"],
            ["--timeout", "0"],
            ["--timeout", "nan"],
            ["--duration", "0"],
            ["--protocol-version", "foo"],
            ["--protocol-version", "-3"],
        ]
        for extra in bad_values:
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit) as ctx:
                    self._run_cli(self.BASE + extra)
                self.assertEqual(ctx.exception.code, 2)

    def test_rcon_mode_requires_password(self) -> None:
        code, _ = self._run_cli(["--quiet", "--host", HOST, "--mode", "rcon"])
        self.assertEqual(code, 2)

    def test_ping_through_cli(self) -> None:
        with TcpServer(_status_handler) as server:
            code, output = self._run_cli(self.BASE + ["--port", str(server.port)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["players"]["max"], 20)

    def _run_cli_allow_exit(self, argv: list[str]) -> tuple[object, str]:
        stdout = io.StringIO()
        code: object = None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue()

    def test_list_versions_prints_the_table_and_exits_cleanly(self) -> None:
        code, output = self._run_cli_allow_exit(["--list-versions"])
        self.assertEqual(code, 0)
        self.assertRegex(output, r"1\.16\.4 - 1\.16\.5\s+754\s+supported")
        self.assertRegex(output, r"1\.7\.6 - 1\.7\.10\s+5\s+not supported")

    def test_protocol_version_accepts_a_minecraft_version_name(self) -> None:
        state: dict = {}
        with TcpServer(_profile_handler_factory(PROFILES[754], state)) as server:
            code, output = self._run_cli_allow_exit(
                ["--quiet", "--host", HOST, "--mode", "ghost", "--port", str(server.port),
                 "--protocol-version", "1.16.5", "--duration", "5", "--timeout", "5"]
            )
        self.assertEqual(code, 0)
        self.assertNotIn("Detected", output)  # explicit version, no detection
        self.assertTrue(state["login"].startswith(_varint(0x00)))

    def test_unknown_version_name_exits_with_code_2(self) -> None:
        for bad in ("1.99", "banana", ""):
            with self.subTest(value=bad):
                code, _ = self._run_cli_allow_exit(self.BASE + ["--protocol-version", bad])
                self.assertEqual(code, 2)

    def test_ping_output_includes_readable_version(self) -> None:
        with TcpServer(_status_handler) as server:
            code, output = self._run_cli(self.BASE + ["--port", str(server.port)])
        self.assertEqual(code, 0)
        version = json.loads(output)["version"]
        self.assertEqual(version["protocol"], 767)
        self.assertEqual(version["minecraft_versions"], "1.21 - 1.21.1")


if __name__ == "__main__":
    unittest.main()
