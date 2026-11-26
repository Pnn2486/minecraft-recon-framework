"""Tests for the limits on what a server can send us and for option handling in the web interface"""

import argparse
import socket
import threading
import unittest
import zlib

from recon import cli, gui
from recon.exceptions import ProtocolFramingError
from recon.protocols import ghost
from recon.protocols.ping import mc_status_ping
from recon.utils.varint import MAX_PACKET_BYTES, check_packet_length, pack_string, pack_varint

HOST = "127.0.0.1"


def serve_once(reply: bytes) -> int:
    """A fake server that answers the first connection with the given bytes"""
    server = socket.socket()
    server.bind((HOST, 0))
    server.listen(1)

    def run() -> None:
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(reply)
            connection.shutdown(socket.SHUT_WR)
            connection.settimeout(3)
            try:
                while connection.recv(4096):  # keep reading until the client hangs up, Windows resets the connection otherwise
                    pass
            except OSError:
                pass
        server.close()

    threading.Thread(target=run, daemon=True).start()
    return server.getsockname()[1]  # type: ignore[no-any-return]


class TestPacketLimits(unittest.TestCase):
    def test_length_check(self) -> None:
        self.assertEqual(check_packet_length(0), 0)
        self.assertEqual(check_packet_length(MAX_PACKET_BYTES), MAX_PACKET_BYTES)
        for bad in (-1, MAX_PACKET_BYTES + 1):
            with self.assertRaises(ProtocolFramingError):
                check_packet_length(bad)

    def test_ghost_rejects_a_huge_frame(self) -> None:
        reader, writer = socket.socketpair()
        with reader, writer:
            writer.sendall(pack_varint(100_000_000))
            with self.assertRaises(ProtocolFramingError):
                ghost._recv_framed_packet(reader, -1)

    def test_ghost_rejects_a_zlib_bomb(self) -> None:
        reader, writer = socket.socketpair()
        with reader, writer:
            packed = zlib.compress(b"\x00" * (MAX_PACKET_BYTES + 1024))
            body = pack_varint(1000) + packed  # the announced size is small, the real one is not
            writer.sendall(pack_varint(len(body)) + body)
            with self.assertRaises(ProtocolFramingError):
                ghost._recv_framed_packet(reader, 0)

    def test_ping_rejects_a_huge_frame(self) -> None:
        port = serve_once(pack_varint(50_000_000))
        with self.assertRaises(ProtocolFramingError):
            mc_status_ping(HOST, port, timeout=3, measure_latency=False)

    def test_ping_rejects_json_that_is_not_an_object(self) -> None:
        packet = pack_varint(0) + pack_string("[]")
        port = serve_once(pack_varint(len(packet)) + packet)
        with self.assertRaises(ProtocolFramingError):
            mc_status_ping(HOST, port, timeout=3, measure_latency=False)


class TestOptionHandling(unittest.TestCase):
    BASE = {"authorized": True, "host": HOST, "mode": "rcon"}

    def test_password_starting_with_a_dash_survives(self) -> None:
        argv = gui.build_argv({**self.BASE, "password": "-abc", "command": "-x"})
        args = cli.build_parser().parse_args(argv)
        self.assertEqual(args.password, "-abc")
        self.assertEqual(args.cmd, ["-x"])

    def test_host_must_not_start_with_a_dash(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.hostname("-evil")
        with self.assertRaises(gui.RequestError):
            gui.build_argv({**self.BASE, "host": "-evil", "password": "x"})


if __name__ == "__main__":
    unittest.main()
