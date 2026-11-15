"""
Unit tests for binary serialization, Base-128 VarInt boundaries, RCON framing,
and offline UUID v3 generation.

Run from the repository root (the folder containing source/ and tests/):

    Linux / macOS (bash/zsh) :
        PYTHONPATH=source python3 -m unittest discover -s tests -v

    Windows (PowerShell):
        $env:PYTHONPATH="source"; python -m unittest discover -s tests -v

    Windows (CMD):
        set PYTHONPATH=source && python -m unittest discover -s tests -v
"""


import struct
import unittest
from recon.exceptions import ProtocolFramingError
from recon.protocols.rcon import RCONClient
from recon.utils.varint import (
    pack_varint,
    pack_string,
    read_varint_bytes,
    read_string_bytes,
    offline_player_uuid_bytes,
)


class TestWireSerialization(unittest.TestCase):
    def test_varint_zero_and_single_byte(self) -> None:
        self.assertEqual(pack_varint(0), b"\x00")
        self.assertEqual(pack_varint(127), b"\x7f")
        val, idx = read_varint_bytes(b"\x7f", 0)
        self.assertEqual((val, idx), (127, 1))

    def test_varint_protocol_versions(self) -> None:
        self.assertEqual(pack_varint(754), b"\xf2\x05")
        self.assertEqual(pack_varint(767), b"\xff\x05")
        val, idx = read_varint_bytes(b"\xff\x05", 0)
        self.assertEqual((val, idx), (767, 2))

    def test_varint_negative_twos_complement(self) -> None:
        packed = pack_varint(-1)
        self.assertEqual(packed, b"\xff\xff\xff\xff\x0f")
        val, idx = read_varint_bytes(packed, 0)
        self.assertEqual((val, idx), (-1, 5))

    def test_varint_overflow_raises(self) -> None:
        corrupt = b"\x80\x80\x80\x80\x80\x01"
        with self.assertRaises(ProtocolFramingError):
            read_varint_bytes(corrupt, 0)

    def test_utf8_string_roundtrip(self) -> None:
        original = "mc.example.org"
        framed = pack_string(original)
        decoded, idx = read_string_bytes(framed, 0)
        self.assertEqual(decoded, original)
        self.assertEqual(idx, len(framed))

    def test_rcon_little_endian_frame(self) -> None:
        frame = RCONClient.pack_frame(req_id=42, pkt_type=3, payload="secret")
        size, req_id, pkt_type = struct.unpack("<iii", frame[:12])
        self.assertEqual(size, len(frame) - 4)
        self.assertEqual(req_id, 42)
        self.assertEqual(pkt_type, 3)
        self.assertTrue(frame.endswith(b"secret\x00\x00"))

    def test_offline_uuid_v3_deterministic(self) -> None:
        uuid_raw = offline_player_uuid_bytes("AuditNode")
        self.assertEqual(len(uuid_raw), 16)
        self.assertEqual(uuid_raw[6] & 0xF0, 0x30)
        self.assertEqual(uuid_raw[8] & 0xC0, 0x80)


if __name__ == "__main__":
    unittest.main()
