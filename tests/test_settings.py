"""Tests for the settings file (recon.settings) and for everything that reads it"""

import contextlib
import io
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_chat import nbt_compound, player_packet

from recon import cli, gui, settings
from recon.protocols.diagnostics import SessionStats
from recon.protocols.ghost import _report_chat
from recon.protocols.ghost_profiles import PROFILES

ROOT = Path(__file__).resolve().parent.parent


class SettingsCase(unittest.TestCase):
    def setUp(self) -> None:
        settings.reset()

    def tearDown(self) -> None:
        settings.reset()

    def write(self, text: str) -> Path:
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        path = Path(folder) / "settings.ini"
        path.write_text(text, encoding="utf-8")
        return path


class TestParsing(SettingsCase):
    def test_shipped_file_matches_the_built_in_values(self) -> None:
        self.assertEqual(settings.load(ROOT / "settings.ini"), settings.defaults())

    def test_shipped_file_mentions_every_setting(self) -> None:
        text = (ROOT / "settings.ini").read_text(encoding="utf-8")
        for section, names in settings.SPEC.items():
            self.assertIn(f"[{section}]", text)
            for name in names:
                self.assertRegex(text, rf"(?m)^{name} = ", f"{section}.{name}")

    def test_override_and_fill_in(self) -> None:
        values = settings.parse("[defaults]\nduration = 10800\n[chat]\ntimestamps = yes\n")
        self.assertEqual(values["defaults"]["duration"], 10800)
        self.assertIs(values["chat"]["timestamps"], True)
        self.assertEqual(values["defaults"]["port"], 25565)

    def test_boolean_words(self) -> None:
        for word, expected in (("true", True), ("On", True), ("1", True), ("no", False), ("OFF", False), ("0", False)):
            with self.subTest(word=word):
                self.assertIs(settings.parse(f"[web]\nopen_browser = {word}\n")["web"]["open_browser"], expected)

    def test_inline_comments_and_blank_lines(self) -> None:
        values = settings.parse("# note\n\n[defaults]\nusername = Bot_1   # the name\n")
        self.assertEqual(values["defaults"]["username"], "Bot_1")

    def test_unknown_names_are_never_ignored(self) -> None:
        with self.assertRaisesRegex(settings.SettingsError, r"unknown setting max_durtion_seconds in \[limits\]. Did you mean max_duration_seconds"):
            settings.parse("[limits]\nmax_durtion_seconds = 5\n")
        with self.assertRaisesRegex(settings.SettingsError, r"unknown section \[limit\]. Did you mean \[limits\]"):
            settings.parse("[limit]\nkeep_jobs = 5\n")

    def test_bad_values_name_the_setting(self) -> None:
        bad = [
            ("[web]\nopen_browser = maybe\n", "must be true or false"),
            ("[defaults]\nduration = 0\n", "from 1 to 86400"),
            ("[defaults]\nduration = 90000\n", "from 1 to 86400"),
            ("[defaults]\nduration = ten\n", "whole number"),
            ("[defaults]\ntimeout = fast\n", "must be a number"),
            ("[defaults]\nport = 70000\n", "from 1 to 65535"),
            ("[defaults]\nusername = bad name\n", "1 to 16 letters"),
            ("[defaults]\nprotocol_version = 1.99\n", "auto, a protocol number"),
            ("[diagnostics]\ntop_packets = 0\n", "from 1 to 100"),
        ]
        for text, message in bad:
            with self.subTest(text=text):
                with self.assertRaisesRegex(settings.SettingsError, message):
                    settings.parse(text)

    def test_protocol_version_forms(self) -> None:
        for text in ("auto", "AUTO", "754", "1.16.5"):
            with self.subTest(text=text):
                value = settings.parse(f"[defaults]\nprotocol_version = {text}\n")["defaults"]["protocol_version"]
                self.assertEqual(str(value).lower(), text.lower())

    def test_broken_file_structure(self) -> None:
        for text in ("duration = 5\n", "[defaults\nport = 1\n", "[defaults]\nport = 1\nport = 2\n"):
            with self.subTest(text=text):
                with self.assertRaises(settings.SettingsError):
                    settings.parse(text)

    def test_missing_and_binary_files(self) -> None:
        with self.assertRaisesRegex(settings.SettingsError, "Could not read"):
            settings.load(Path(tempfile.gettempdir()) / "recon-no-such-file.ini")
        path = self.write("")
        path.write_bytes(b"\xff\xfe\x00\x01")
        with self.assertRaisesRegex(settings.SettingsError, "UTF-8"):
            settings.load(path)


class TestFindingTheFile(SettingsCase):
    def test_order_of_places(self) -> None:
        explicit = self.write("[defaults]\nduration = 11\n")
        from_env = self.write("[defaults]\nduration = 22\n")
        in_cwd = self.write("[defaults]\nduration = 33\n")
        with mock.patch.dict(os.environ, {settings.ENV_VAR: str(from_env)}):
            self.assertEqual(settings.find_file(str(explicit)), explicit)
            self.assertEqual(settings.find_file(), from_env)
        env = {k: v for k, v in os.environ.items() if k != settings.ENV_VAR}
        previous = Path.cwd()
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                os.chdir(in_cwd.parent)
                self.assertEqual(settings.find_file().resolve(), in_cwd.resolve())
            finally:
                os.chdir(previous)

    def test_no_file_means_built_in_values(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != settings.ENV_VAR}
        empty = tempfile.mkdtemp()
        previous = Path.cwd()
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(settings, "PROJECT_FILE", Path(empty) / "none.ini"):
            try:
                os.chdir(empty)
                settings.use_file()
            finally:
                os.chdir(previous)
        self.assertEqual(settings.current(), settings.defaults())
        self.assertIsNone(settings.origin())
        self.assertTrue(settings.configured())

    def test_explicit_missing_file_is_an_error(self) -> None:
        with self.assertRaises(settings.SettingsError):
            settings.use_file(Path(tempfile.gettempdir()) / "recon-no-such-file.ini")


class TestCommandLine(SettingsCase):
    def run_cli(self, argv: list[str]) -> tuple[object, str]:
        err = io.StringIO()
        code: object = None
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            try:
                code = cli.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, err.getvalue()

    def test_defaults_come_from_the_settings(self) -> None:
        values = settings.parse("[defaults]\nduration = 10800\nusername = Watcher\nport = 25570\ndiagnostics = true\nquiet = true\n")
        args = cli.build_parser(values).parse_args(["--host", "x", "--mode", "ping"])
        self.assertEqual((args.duration, args.username, args.port, args.diagnostics, args.quiet), (10800, "Watcher", 25570, True, True))

    def test_command_line_wins_over_the_file(self) -> None:
        values = settings.parse("[defaults]\nduration = 10800\n")
        args = cli.build_parser(values).parse_args(["--host", "x", "--mode", "ghost", "--duration", "5"])
        self.assertEqual(args.duration, 5)

    def test_config_option_loads_a_file(self) -> None:
        path = self.write("[defaults]\nduration = 7\n")
        code, _ = self.run_cli(["--config", str(path), "--list-versions"])
        self.assertEqual(code, 0)
        self.assertEqual(settings.get("defaults", "duration"), 7)

    def test_broken_file_exits_with_code_2_and_names_the_problem(self) -> None:
        path = self.write("[defaults]\nduration = ten\n")
        code, err = self.run_cli(["--config", str(path), "--host", "127.0.0.1", "--mode", "ping"])
        self.assertEqual(code, 2)
        self.assertIn("[defaults] duration", err)

    def test_missing_config_file_exits_with_code_2(self) -> None:
        code, err = self.run_cli(["--config", str(Path(tempfile.gettempdir()) / "recon-no-such-file.ini"), "--host", "x", "--mode", "ping"])
        self.assertEqual(code, 2)
        self.assertIn("Could not read", err)


class TestWebPage(SettingsCase):
    BASE = {"authorized": True, "host": "127.0.0.1", "mode": "ghost"}

    def test_built_in_limits(self) -> None:
        with self.assertRaisesRegex(gui.RequestError, "at most 120 seconds"):
            gui.build_argv({**self.BASE, "duration": "10800"})

    def test_raised_limits_are_accepted(self) -> None:
        settings.use(settings.parse("[limits]\nmax_duration_seconds = 10800\nmax_timeout_seconds = 300\n"))
        argv = gui.build_argv({**self.BASE, "duration": "10800", "timeout": "300"})
        self.assertEqual(argv[argv.index("--duration") + 1], "10800")
        with self.assertRaisesRegex(gui.RequestError, "at most 10800 seconds"):
            gui.build_argv({**self.BASE, "duration": "10801"})
        with self.assertRaisesRegex(gui.RequestError, "at most 300 seconds"):
            gui.build_argv({**self.BASE, "timeout": "301"})

    def test_lowered_limits_are_enforced(self) -> None:
        settings.use(settings.parse("[limits]\nmax_command_chars = 10\nmax_password_chars = 4\n"))
        with self.assertRaisesRegex(gui.RequestError, "at most 10 characters"):
            gui.build_argv({"authorized": True, "host": "x", "mode": "rcon", "password": "abcd", "command": "x" * 11})
        with self.assertRaisesRegex(gui.RequestError, "too long"):
            gui.build_argv({"authorized": True, "host": "x", "mode": "rcon", "password": "abcde"})

    def test_output_limits(self) -> None:
        settings.use(settings.parse("[limits]\nmax_output_lines = 100\nmax_line_chars = 100\n"))
        job = gui.Job("1", "ping")
        for number in range(150):
            job.add("out", "x" * 300 if number == 0 else "y")
        snapshot = job.snapshot(0)
        self.assertEqual(len(snapshot["lines"]), 100)
        self.assertEqual(len(snapshot["lines"][0]["text"]), 100)
        self.assertTrue(snapshot["truncated"])

    def test_the_page_gets_the_limits_and_defaults(self) -> None:
        settings.use(settings.parse("[limits]\nmax_duration_seconds = 10800\n[defaults]\nduration = 60\n"))
        server = gui.create_server(0)
        try:
            import http.client
            import json
            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", "/api/info", headers={"Host": f"127.0.0.1:{port}", "X-Recon-Token": server.token})
            info = json.loads(conn.getresponse().read())
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(info["limits"]["max_duration_seconds"], 10800)
        self.assertEqual(info["defaults"]["duration"], 60)

    def test_main_stops_on_a_broken_file(self) -> None:
        path = self.write("[web]\nport = 99999\n")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = gui.main(["--config", str(path), "--no-browser"])
        self.assertEqual(code, 2)
        self.assertIn("[web] port", err.getvalue())


class TestChatOutput(SettingsCase):
    PROFILE = PROFILES[767]

    def run_chat(self, ini: str, pkt_id: int, data: bytes) -> tuple[str, SessionStats]:
        settings.use(settings.parse(ini))
        stats = SessionStats(self.PROFILE)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            _report_chat(self.PROFILE, pkt_id, data, stats)
        return out.getvalue(), stats

    SYSTEM = (0x6C, nbt_compound({"text": "Welcome"}) + b"\x00")
    PLAYER = (0x39, player_packet("hello", "Alice"))
    BROKEN = (0x39, b"\xff" * 5)

    def test_default_output(self) -> None:
        self.assertEqual(self.run_chat("", *self.SYSTEM)[0], "[CHAT] (system) Welcome\n")
        self.assertEqual(self.run_chat("", *self.PLAYER)[0], "[CHAT] (player) <Alice> hello\n")
        self.assertEqual(self.run_chat("", *self.BROKEN)[0], "[CHAT] packet 0x39 (5 bytes, not decoded)\n")

    def test_hiding_a_kind_still_counts_it(self) -> None:
        output, stats = self.run_chat("[chat]\nshow_system_chat = false\n", *self.SYSTEM)
        self.assertEqual(output, "")
        self.assertEqual(stats.chat_ok, 1)
        self.assertEqual(self.run_chat("[chat]\nshow_system_chat = false\n", *self.PLAYER)[0], "[CHAT] (player) <Alice> hello\n")
        self.assertEqual(self.run_chat("[chat]\nshow_player_chat = false\n", *self.PLAYER)[0], "")

    def test_label_and_timestamp(self) -> None:
        self.assertEqual(self.run_chat("[chat]\nshow_kind_label = false\n", *self.SYSTEM)[0], "[CHAT] Welcome\n")
        self.assertRegex(self.run_chat("[chat]\ntimestamps = true\n", *self.SYSTEM)[0], r"^\[CHAT\] \d\d:\d\d:\d\d \(system\) Welcome\n$")

    def test_undecoded_lines_can_be_hidden(self) -> None:
        output, stats = self.run_chat("[chat]\nshow_undecoded = false\n", *self.BROKEN)
        self.assertEqual(output, "")
        self.assertEqual(stats.chat_failed, 1)

    def test_page_pattern_still_matches_every_form(self) -> None:
        script = (ROOT / "source" / "recon" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn(r"(?:\d\d:\d\d:\d\d )?", script)


class TestDiagnosticsSettings(SettingsCase):
    def test_top_packets_and_samples(self) -> None:
        settings.use(settings.parse("[diagnostics]\ntop_packets = 1\nmax_undecoded_samples = 0\n"))
        stats = SessionStats(PROFILES[767])
        stats.packet("play", 0x26, 8)
        stats.packet("play", 0x26, 8)
        stats.packet("play", 0x01, 4)
        stats.chat(False, 0x39, b"\xff" * 5)
        report = "\n".join(stats.report())
        self.assertEqual(len(re.findall(r"\[#\] packet ", report)), 1)
        self.assertNotIn("undecoded chat 0x39", report)


if __name__ == "__main__":
    unittest.main()
