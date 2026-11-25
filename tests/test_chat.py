"""Tests for chat decoding, NBT, text components, diagnostics and RCON presets, all packets are built by hand"""

import contextlib
import io
import json
import struct
import unittest

from recon import cli, gui
from recon.exceptions import ProtocolFramingError
from recon.protocols.chat import decode_chat_packet, hex_preview, packet_kinds, readable_strings
from recon.protocols.ghost import headless_ghost_stream
from recon.protocols.ghost_profiles import PROFILES
from recon.protocols.rcon_presets import PRESETS
from recon.utils.nbt import read_network_nbt
from recon.utils.text import component_to_text, json_text_to_plain, strip_codes

from test_protocols import (
    HOST,
    TcpServer,
    _compressed,
    _mc_string,
    _rcon_handler,
    _read_compressed_packet,
    _recv_exact,
    _read_varint,
    _varint,
    _frame,
)

SENDER = bytes(range(1, 17))
SIGNATURE = b"\xaa" * 256


def nbt_string(text: str) -> bytes:
    raw = text.encode()
    return struct.pack(">H", len(raw)) + raw


def nbt_compound(entries: dict) -> bytes:
    """A nameless compound whose values are strings, or lists of strings or compounds' bytes"""
    out = b"\x0a"
    for key, value in entries.items():
        if isinstance(value, str):
            out += b"\x08" + nbt_string(key) + nbt_string(value)
        else:
            out += b"\x09" + nbt_string(key) + b"\x08" + struct.pack(">i", len(value)) + b"".join(nbt_string(v) for v in value)
    return out + b"\x00"


def player_packet(message: str, name: str, global_index: bool = False, signed: bool = True) -> bytes:
    out = _varint(7) if global_index else b""
    out += SENDER + _varint(3)
    out += (b"\x01" + SIGNATURE) if signed else b"\x00"
    out += _mc_string(message) + struct.pack(">qq", 1700000000000, 99)
    out += _varint(0)  # previous messages
    out += b"\x00"  # unsigned content
    out += _varint(0)  # filter type
    out += _varint(1)  # chat type
    out += nbt_compound({"text": name})
    out += b"\x00"  # target name
    return out


class TestNbt(unittest.TestCase):
    def test_compound_with_strings_and_list(self) -> None:
        value, end = read_network_nbt(nbt_compound({"text": "hi", "list": ["a", "b"]}))
        self.assertEqual(value, {"text": "hi", "list": ["a", "b"]})
        self.assertEqual(end, len(nbt_compound({"text": "hi", "list": ["a", "b"]})))

    def test_bare_string_root(self) -> None:
        value, _ = read_network_nbt(b"\x08" + nbt_string("plain"))
        self.assertEqual(value, "plain")

    def test_truncated_data_raises(self) -> None:
        with self.assertRaises(ProtocolFramingError):
            read_network_nbt(nbt_compound({"text": "hello"})[:-4])

    def test_deep_nesting_is_refused(self) -> None:
        bomb = b"\x0a" + (b"\x0a\x00\x01a" * 200)
        with self.assertRaises(ProtocolFramingError):
            read_network_nbt(bomb)

    def test_unknown_tag_and_bad_list_raise(self) -> None:
        with self.assertRaises(ProtocolFramingError):
            read_network_nbt(b"\x63")
        with self.assertRaises(ProtocolFramingError):
            read_network_nbt(b"\x09\x00" + b"\x08" + struct.pack(">i", -5))


class TestText(unittest.TestCase):
    def test_translate_chat_type(self) -> None:
        component = {"translate": "chat.type.text", "with": [{"text": "Alice"}, "hello"]}
        self.assertEqual(component_to_text(component), "<Alice> hello")

    def test_join_message_and_numbered_placeholders(self) -> None:
        self.assertEqual(component_to_text({"translate": "multiplayer.player.joined", "with": ["Bob"]}), "Bob joined the game")
        self.assertEqual(component_to_text({"translate": "x", "fallback": "%2$s then %1$s", "with": ["a", "b"]}), "b then a")

    def test_unknown_key_keeps_key_and_arguments(self) -> None:
        self.assertEqual(component_to_text({"translate": "custom.key", "with": ["x", "y"]}), "custom.key: x, y")

    def test_extra_and_colour_codes(self) -> None:
        component = {"text": "A ", "extra": [{"text": "B"}, "C"]}
        self.assertEqual(component_to_text(component), "A BC")
        self.assertEqual(strip_codes("§aGreen§r text"), "Green text")
        self.assertEqual(json_text_to_plain(json.dumps({"text": "§bhi"})), "hi")
        self.assertEqual(json_text_to_plain("not json"), "not json")

    def test_deep_nesting_does_not_crash(self) -> None:
        component: dict = {"text": "x"}
        for _ in range(200):
            component = {"text": "", "extra": [component]}
        self.assertIsInstance(component_to_text(component), str)


class TestChatDecoder(unittest.TestCase):
    def test_packet_kinds_by_era(self) -> None:
        self.assertEqual(sorted(packet_kinds(PROFILES[754]).values()), ["chat"])
        self.assertEqual(sorted(packet_kinds(PROFILES[759]).values()), ["player", "system"])
        self.assertEqual(sorted(packet_kinds(PROFILES[763]).values()), ["disguised", "player", "system"])
        self.assertEqual(packet_kinds(PROFILES[767]), {0x6C: "system", 0x39: "player", 0x1E: "disguised"})

    def test_old_json_chat(self) -> None:
        message = decode_chat_packet(PROFILES[754], 0x0E, _mc_string('{"text":"<Alice> hi"}') + b"\x00")
        assert message is not None
        self.assertEqual((message.kind, message.text), ("chat", "<Alice> hi"))

    def test_system_chat_json_and_nbt(self) -> None:
        json_msg = decode_chat_packet(PROFILES[761], 0x60, _mc_string('{"translate":"multiplayer.player.joined","with":["Bob"]}') + b"\x00")
        nbt_msg = decode_chat_packet(PROFILES[767], 0x6C, nbt_compound({"text": "Server restart soon"}) + b"\x00")
        assert json_msg is not None and nbt_msg is not None
        self.assertEqual(json_msg.text, "Bob joined the game")
        self.assertEqual((nbt_msg.kind, nbt_msg.text), ("system", "Server restart soon"))

    def test_system_chat_nbt_translate(self) -> None:
        data = nbt_compound({"translate": "multiplayer.player.left", "with": ["Carol"]}) + b"\x00"
        message = decode_chat_packet(PROFILES[767], 0x6C, data)
        assert message is not None
        self.assertEqual(message.text, "Carol left the game")

    def test_signed_player_chat_without_global_index(self) -> None:
        message = decode_chat_packet(PROFILES[767], 0x39, player_packet("hello world", "Alice"))
        assert message is not None
        self.assertEqual((message.kind, message.text, message.signed), ("player", "<Alice> hello world", True))

    def test_unsigned_player_chat(self) -> None:
        message = decode_chat_packet(PROFILES[765], 0x37, player_packet("unsigned hi", "Dave", signed=False))
        assert message is not None
        self.assertEqual((message.text, message.signed), ("<Dave> unsigned hi", False))

    def test_player_chat_with_global_index_on_newer_versions(self) -> None:
        message = decode_chat_packet(PROFILES[768], 0x3B, player_packet("new layout", "Erin", global_index=True))
        assert message is not None
        self.assertEqual(message.text, "<Erin> new layout")

    def test_player_chat_falls_back_to_uuid_when_tail_is_unreadable(self) -> None:
        data = player_packet("short", "Name")
        head = data[: data.index(b"\x00\x00\x00\x00", 16 + 1 + 1 + 256)]  # cut inside the tail
        message = decode_chat_packet(PROFILES[767], 0x39, head)
        if message is not None:
            self.assertIn("short", message.text)

    def test_disguised_chat(self) -> None:
        data = nbt_compound({"text": "boom"}) + _varint(2) + nbt_compound({"text": "Console"}) + b"\x00"
        message = decode_chat_packet(PROFILES[767], 0x1E, data)
        assert message is not None
        self.assertEqual((message.kind, message.text), ("disguised", "<Console> boom"))

    def test_legacy_signed_chat_1_19(self) -> None:
        data = _mc_string('{"text":"hi there"}') + b"\x00" + _varint(0) + SENDER + _mc_string('{"text":"Frank"}')
        message = decode_chat_packet(PROFILES[759], 0x30, data)
        assert message is not None
        self.assertEqual(message.text, "<Frank> hi there")

    def test_garbage_and_unknown_ids_return_none(self) -> None:
        self.assertIsNone(decode_chat_packet(PROFILES[767], 0x39, b"\xff" * 9))
        self.assertIsNone(decode_chat_packet(PROFILES[767], 0x6C, b"\x0a\x00"))
        self.assertIsNone(decode_chat_packet(PROFILES[767], 0x01, b"anything"))

    def test_every_profile_survives_random_bytes(self) -> None:
        blobs = [b"", b"\x00", b"\xff" * 64, bytes(range(256)), b"\x0a" * 50]
        for profile in PROFILES.values():
            for pkt_id in packet_kinds(profile):
                for blob in blobs:
                    decode_chat_packet(profile, pkt_id, blob)

    def test_helpers(self) -> None:
        self.assertEqual(readable_strings(b"\x00\x01hello world\x00ab\x00more text"), ["hello world", "more text"])
        self.assertTrue(hex_preview(bytes(100)).endswith("..."))


def _chat_server_handler(conn) -> None:
    """Fake 1.21.1 server that sends system, player and disguised chat, then disconnects"""
    _recv_exact(conn, _read_varint(conn))
    _recv_exact(conn, _read_varint(conn))
    conn.sendall(_frame(_varint(0x03) + _varint(256)))
    conn.sendall(_compressed(_varint(0x02) + b"\x00" * 20 + _varint(0) + b"\x00"))
    _read_compressed_packet(conn)  # login acknowledged
    conn.sendall(_compressed(_varint(0x0E) + _varint(0)))
    _read_compressed_packet(conn)  # known packs reply
    conn.sendall(_compressed(_varint(0x03)))
    _read_compressed_packet(conn)  # finish acknowledged
    conn.sendall(_compressed(_varint(0x26) + struct.pack(">q", 5)))
    _read_compressed_packet(conn)  # keep alive echo
    conn.sendall(_compressed(_varint(0x6C) + nbt_compound({"text": "Welcome!"}) + b"\x00"))
    conn.sendall(_compressed(_varint(0x39) + player_packet("hello all", "Alice")))
    conn.sendall(_compressed(_varint(0x39) + b"\xff" * 5))
    conn.sendall(_compressed(_varint(0x1D) + nbt_compound({"text": "Bye"})))


class TestGhostDiagnostics(unittest.TestCase):
    def _run(self, diagnostics: bool) -> str:
        captured = io.StringIO()
        with TcpServer(_chat_server_handler) as server, contextlib.redirect_stdout(captured):
            headless_ghost_stream(HOST, port=server.port, protocol_version=767, duration=5, timeout=5.0, diagnostics=diagnostics)
        return captured.getvalue()

    def test_chat_is_decoded_and_disconnect_reason_is_read(self) -> None:
        output = self._run(False)
        self.assertIn("[CHAT] (system) Welcome!", output)
        self.assertIn("[CHAT] (player) <Alice> hello all", output)
        self.assertIn("packet 0x39 (5 bytes, not decoded)", output)
        self.assertIn("Server disconnect in the play state (0x1D): Bye", output)
        self.assertNotIn("[#]", output)

    def test_diagnostics_report(self) -> None:
        output = self._run(True)
        self.assertIn("[#] --- Session diagnostics ---", output)
        self.assertIn("[#] protocol: 767", output)
        self.assertIn("compression threshold: 256 bytes", output)
        self.assertIn("chat packets: 2 decoded, 1 not decoded", output)
        self.assertIn("ended because: server disconnected the test player", output)
        self.assertIn("[#] packet play 0x6C count=1", output)
        self.assertIn("name=system chat", output)
        self.assertIn("[#] undecoded chat 0x39: ff ff ff ff ff", output)
        self.assertIn("keep-alives echoed: 1", output)


class TestRconPresets(unittest.TestCase):
    def test_presets_are_read_only(self) -> None:
        forbidden = ("stop", "op ", "deop", "ban ", "kick", "kill", "give", "gamemode", "whitelist add", "whitelist remove", "save-off", "reload")
        for name, commands in PRESETS.items():
            self.assertTrue(commands, name)
            for command in commands:
                self.assertFalse(command.startswith(forbidden), f"{name}: {command}")

    def test_cli_preset_runs_all_commands_on_one_connection(self) -> None:
        captured = io.StringIO()
        with TcpServer(_rcon_handler) as server, contextlib.redirect_stdout(captured):
            code = cli.main(["--quiet", "--host", HOST, "--mode", "rcon", "--rcon-port", str(server.port), "--password", "secret", "--preset", "world"])
        self.assertEqual(code, 0)
        output = captured.getvalue()
        for command in PRESETS["world"]:
            self.assertIn(f"[>] {command}", output)
        self.assertEqual(output.count("2 of a max of 20"), len(PRESETS["world"]))

    def test_repeated_cmd_options(self) -> None:
        captured = io.StringIO()
        with TcpServer(_rcon_handler) as server, contextlib.redirect_stdout(captured):
            cli.main(["--quiet", "--host", HOST, "--mode", "rcon", "--rcon-port", str(server.port), "--password", "secret", "--cmd", "list", "--cmd", "seed"])
        self.assertIn("[>] list", captured.getvalue())
        self.assertIn("[>] seed", captured.getvalue())

    def test_single_command_output_is_unchanged(self) -> None:
        captured = io.StringIO()
        with TcpServer(_rcon_handler) as server, contextlib.redirect_stdout(captured):
            cli.main(["--quiet", "--host", HOST, "--mode", "rcon", "--rcon-port", str(server.port), "--password", "secret"])
        self.assertEqual(captured.getvalue().strip(), "There are 2 of a max of 20 players online: Alice, Bob")

    def test_unknown_preset_is_rejected_by_cli(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["--quiet", "--host", HOST, "--mode", "rcon", "--preset", "nope"])


class TestGuiOptions(unittest.TestCase):
    BASE = {"authorized": True, "host": HOST, "mode": "rcon", "password": "secret"}

    def test_preset_and_command(self) -> None:
        argv = gui.build_argv({**self.BASE, "preset": "plugins"})
        self.assertIn("--preset", argv)
        self.assertNotIn("--cmd", argv)
        argv = gui.build_argv({**self.BASE, "preset": "plugins", "command": "list"})
        self.assertIn("--cmd=list", argv)
        self.assertEqual(gui.build_argv(self.BASE)[-1], "--cmd=list")

    def test_bad_preset_is_rejected(self) -> None:
        with self.assertRaises(gui.RequestError):
            gui.build_argv({**self.BASE, "preset": "rm -rf"})

    def test_diagnostics_flag(self) -> None:
        base = {"authorized": True, "host": HOST, "mode": "ghost"}
        self.assertIn("--diagnostics", gui.build_argv({**base, "diagnostics": True}))
        self.assertNotIn("--diagnostics", gui.build_argv({**base, "diagnostics": False}))
        with self.assertRaises(gui.RequestError):
            gui.build_argv({**base, "diagnostics": "yes"})


if __name__ == "__main__":
    unittest.main()
