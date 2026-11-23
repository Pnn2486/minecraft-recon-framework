"""Tests for the local web interface (recon.gui). Everything runs on 127.0.0.1"""

import http.client
import json
import re
import threading
import time
import unittest
from pathlib import Path

from test_protocols import HOST, QueryServer, TcpServer, _rcon_handler, _status_handler

from recon import gui


class WebServerCase(unittest.TestCase):
    """Starts the web server once per test class and offers small request helpers"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = gui.create_server(0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method: str, path: str, body=None, token=True, host=None, origin=None):
        conn = http.client.HTTPConnection(HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.port}")
            if token is True:
                conn.putheader("X-Recon-Token", self.server.token)
            elif token:
                conn.putheader("X-Recon-Token", token)
            if origin:
                conn.putheader("Origin", origin)
            data = json.dumps(body).encode() if body is not None else b""
            if method == "POST":
                conn.putheader("Content-Type", "application/json")
                conn.putheader("Content-Length", str(len(data)))
            conn.endheaders(data)
            response = conn.getresponse()
            raw = response.read()
            return response.status, dict(response.getheaders()), raw
        finally:
            conn.close()

    def json_request(self, *args, **kwargs):
        status, _, raw = self.request(*args, **kwargs)
        return status, json.loads(raw)

    def wait_for_job(self, job_id: str, limit: float = 20.0) -> dict:
        deadline = time.monotonic() + limit
        lines: list[dict] = []
        while time.monotonic() < deadline:
            status, snap = self.json_request("GET", f"/api/jobs/{job_id}?since={len(lines)}")
            self.assertEqual(status, 200)
            lines.extend(snap["lines"])
            if snap["done"]:
                snap["lines"] = lines
                return snap
            time.sleep(0.1)
        self.fail("The job did not finish in time.")


class TestPagesAndSecurity(WebServerCase):
    def test_index_has_a_token_and_no_placeholder(self) -> None:
        status, headers, raw = self.request("GET", "/", token=False)
        page = raw.decode()
        self.assertEqual(status, 200)
        self.assertIn(self.server.token, page)
        self.assertNotIn("{{TOKEN}}", page)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_static_files_are_served(self) -> None:
        for name in ("style.css", "app.js", "favicon.svg"):
            with self.subTest(name=name):
                status, _, raw = self.request("GET", f"/static/{name}", token=False)
                self.assertEqual(status, 200)
                self.assertGreater(len(raw), 100)

    def test_other_static_paths_are_not_found(self) -> None:
        for path in ("/static/../gui.py", "/static/index.html", "/static/%2e%2e/gui.py", "/static/", "/nothing"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path, token=False)
                self.assertEqual(status, 404)

    def test_api_needs_the_token(self) -> None:
        for token in (False, "wrong-token"):
            with self.subTest(token=token):
                status, _ = self.json_request("GET", "/api/info", token=token)
                self.assertEqual(status, 403)
        status, body = self.json_request("GET", "/api/info")
        self.assertEqual(status, 200)
        self.assertIn("version", body)

    def test_post_needs_the_token(self) -> None:
        status, _ = self.json_request("POST", "/api/run", body={"mode": "ping"}, token=False)
        self.assertEqual(status, 403)

    def test_wrong_host_header_is_rejected(self) -> None:
        for path in ("/", "/api/info", "/static/app.js"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path, host="evil.example")
                self.assertEqual(status, 403)

    def test_localhost_host_header_is_accepted(self) -> None:
        status, _, _ = self.request("GET", "/", token=False, host=f"localhost:{self.port}")
        self.assertEqual(status, 200)

    def test_foreign_origin_is_rejected(self) -> None:
        status, _ = self.json_request("GET", "/api/info", origin="http://evil.example")
        self.assertEqual(status, 403)
        status, _ = self.json_request("POST", "/api/run", body={"mode": "ping"}, origin="https://evil.example")
        self.assertEqual(status, 403)

    def test_versions_list(self) -> None:
        status, body = self.json_request("GET", "/api/versions")
        self.assertEqual(status, 200)
        by_protocol = {row["protocol"]: row for row in body["versions"]}
        self.assertTrue(by_protocol[754]["supported"])
        self.assertIn("1.16.5", by_protocol[754]["name"])
        self.assertFalse(by_protocol[4]["supported"])

    def test_unknown_job_and_unknown_routes(self) -> None:
        self.assertEqual(self.json_request("GET", "/api/jobs/doesnotexist")[0], 404)
        self.assertEqual(self.json_request("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.json_request("POST", "/api/other", body={})[0], 404)


class TestRunValidation(WebServerCase):
    def run_error(self, payload: dict) -> str:
        status, body = self.json_request("POST", "/api/run", body=payload)
        self.assertEqual(status, 400, body)
        return body["error"]

    def test_authorization_is_required(self) -> None:
        self.assertIn("permission", self.run_error({"mode": "ping", "host": HOST}))
        self.assertIn("permission", self.run_error({"mode": "ping", "host": HOST, "authorized": "yes"}))

    def test_bad_requests_are_rejected(self) -> None:
        self.assertIn("tool", self.run_error({"mode": "nope", "authorized": True, "host": HOST}))
        self.assertIn("Server address", self.run_error({"mode": "ping", "authorized": True, "host": ""}))
        self.assertIn("Server address", self.run_error({"mode": "ping", "authorized": True, "host": "bad host"}))
        self.assertIn("Port", self.run_error({"mode": "ping", "authorized": True, "host": HOST, "port": "70000"}))
        self.assertIn("Timeout", self.run_error({"mode": "ping", "authorized": True, "host": HOST, "timeout": "0"}))
        self.assertIn("Timeout", self.run_error({"mode": "ping", "authorized": True, "host": HOST, "timeout": "600"}))

    def test_rcon_and_ghost_fields_are_checked(self) -> None:
        base = {"authorized": True, "host": HOST}
        self.assertIn("password", self.run_error({**base, "mode": "rcon"}))
        self.assertIn("Command", self.run_error({**base, "mode": "rcon", "password": "x", "command": "a" * 2000}))
        self.assertIn("Player name", self.run_error({**base, "mode": "ghost", "username": "bad name!"}))
        self.assertIn("Duration", self.run_error({**base, "mode": "ghost", "duration": "9999"}))
        self.assertIn("Version", self.run_error({**base, "mode": "ghost", "protocol_version": "99.99"}))

    def test_body_must_be_a_json_object(self) -> None:
        for body in ([1, 2], "text"):
            with self.subTest(body=body):
                status, _ = self.json_request("POST", "/api/run", body=body)
                self.assertEqual(status, 400)

    def test_build_argv(self) -> None:
        argv = gui.build_argv({"mode": "ghost", "authorized": True, "host": " 127.0.0.1 ", "port": "25570", "username": "Bot_1", "protocol_version": "1.16.5", "duration": "5", "timeout": "3"})
        self.assertEqual(argv[:2], ["--quiet", "--mode"])
        self.assertIn("127.0.0.1", argv)
        self.assertEqual(argv[argv.index("--protocol-version") + 1], "754")
        self.assertEqual(argv[argv.index("--port") + 1], "25570")


class TestRunning(WebServerCase):
    def start(self, payload: dict) -> str:
        status, body = self.json_request("POST", "/api/run", body=payload)
        self.assertEqual(status, 202, body)
        return body["job"]

    def test_ping_job_returns_the_server_data(self) -> None:
        with TcpServer(_status_handler) as target:
            job = self.wait_for_job(self.start({"mode": "ping", "authorized": True, "host": HOST, "port": target.port, "timeout": 5}))
        self.assertEqual(job["exit_code"], 0)
        data = json.loads("\n".join(line["text"] for line in job["lines"] if line["stream"] == "out"))
        self.assertEqual(data["players"]["online"], 2)
        self.assertEqual(data["version"]["minecraft_versions"], "1.21 - 1.21.1")

    def test_query_job(self) -> None:
        with QueryServer() as target:
            job = self.wait_for_job(self.start({"mode": "query", "authorized": True, "host": HOST, "port": target.port, "timeout": 5}))
        self.assertEqual(job["exit_code"], 0)
        data = json.loads("\n".join(line["text"] for line in job["lines"] if line["stream"] == "out"))
        self.assertEqual(data["players"], ["Alice", "Bob"])

    def test_rcon_job_and_the_password_is_never_returned(self) -> None:
        secret = "very-secret-value-123"
        with TcpServer(_rcon_handler) as target:
            payload = {"mode": "rcon", "authorized": True, "host": HOST, "rcon_port": target.port, "password": secret, "command": "list"}
            job = self.wait_for_job(self.start(payload))
        self.assertNotIn(secret, json.dumps(job))
        self.assertIn(job["exit_code"], (0, 1))

    def test_failed_job_reports_an_error_line(self) -> None:
        with TcpServer(lambda conn: None) as target:
            port = target.port
        job = self.wait_for_job(self.start({"mode": "ping", "authorized": True, "host": HOST, "port": port, "timeout": 2}))
        self.assertEqual(job["exit_code"], 1)
        self.assertTrue(any(line["stream"] == "err" for line in job["lines"]))

    def test_only_one_job_at_a_time(self) -> None:
        def silent(conn) -> None:
            time.sleep(2)

        with TcpServer(silent) as target:
            first = self.start({"mode": "ping", "authorized": True, "host": HOST, "port": target.port, "timeout": 1})
            status, body = self.json_request("POST", "/api/run", body={"mode": "ping", "authorized": True, "host": HOST, "port": target.port})
            self.assertEqual(status, 409, body)
            self.wait_for_job(first)


class TestAssets(unittest.TestCase):
    ROOT = Path(gui.WEB_DIR)

    def test_every_static_file_exists(self) -> None:
        for name in gui.STATIC_FILES:
            self.assertTrue((self.ROOT / name).is_file(), name)
        self.assertTrue((self.ROOT / "index.html").is_file())

    def test_page_only_references_known_files(self) -> None:
        page = (self.ROOT / "index.html").read_text(encoding="utf-8")
        for path in re.findall(r'(?:src|href)="(/static/[^"]+)"', page):
            self.assertIn(path[len("/static/"):], gui.STATIC_FILES, path)
        self.assertNotIn("<script>", page)
        self.assertNotIn("style=", page)

    def test_script_never_inserts_server_text_as_html(self) -> None:
        script = (self.ROOT / "app.js").read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
