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


def _ghost_handler_factory(state: dict):
    keep_alive_id = 123456789

    def handler(conn: socket.socket) -> None:
        _recv_exact(conn, _read_varint(conn))  # handshake
        state["login_len"] = len(_recv_exact(conn, _read_varint(conn)))  # login start
        conn.sendall(_frame(_varint(0x03) + _varint(256)))  # set compression, threshold 256

        def compressed(payload: bytes) -> bytes:
            return _frame(_varint(0) + payload)  # below threshold: data length 0

        conn.sendall(compressed(_varint(0x02) + b"\x00" * 20))  # login success
        conn.sendall(compressed(_varint(0x1F) + struct.pack(">q", keep_alive_id)))
        reply = _recv_exact(conn, _read_varint(conn))
        state["echo_ok"] = reply[0] == 0 and reply[1:] == _varint(0x10) + struct.pack(">q", keep_alive_id)
        conn.sendall(compressed(_varint(0x0E) + _mc_string('{"text":"<Alice> hello"}')))
        conn.sendall(compressed(_varint(0x19) + _mc_string('{"text":"bye"}')))

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
    def _run_ghost(self, protocol_version: int) -> tuple[dict, str]:
        state: dict = {}
        captured = io.StringIO()
        with TcpServer(_ghost_handler_factory(state)) as server:
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

    def test_protocol_767_login_appends_uuid(self) -> None:
        state, _ = self._run_ghost(767)
        self.assertEqual(state["login_len"], 1 + 1 + len("AuditNode") + 16)
        self.assertTrue(state["echo_ok"])

    def test_online_mode_server_raises(self) -> None:
        with TcpServer(_online_mode_handler) as server:
            with self.assertRaises(OnlineModeRequiredError):
                headless_ghost_stream(HOST, port=server.port, duration=5, timeout=5.0)


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


if __name__ == "__main__":
    unittest.main()
