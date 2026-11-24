"""Local web interface, only reachable from your computer (README section 4.1)"""

import argparse
import contextlib
import io
import json
import re
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from recon import cli, settings
from recon.protocols.ghost_profiles import PROFILES
from recon.protocols.rcon_presets import PRESET_LABELS, PRESETS
from recon.utils.versions import VERSION_NAMES, version_range

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_FILES = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "favicon.svg": "image/svg+xml",
}
MODES = ("ping", "query", "rcon", "ghost")
MAX_BODY_BYTES = 16 * 1024  # fixed on purpose, not a setting


def _limit(name: str) -> int:
    return settings.get("limits", name)  # type: ignore[no-any-return]
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,16}$")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class RequestError(Exception):
    """The page sent something that cannot be run. The message is shown to the user"""


class JobBusyError(Exception):
    """Another job is still running"""


def _field(payload: dict, key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise RequestError(f"The value for {key} is not valid.")
    return str(value).strip()


def _checked(payload: dict, key: str, label: str, validator, required: bool = False) -> str | None:
    text = _field(payload, key)
    if not text:
        if required:
            raise RequestError(f"{label} is required.")
        return None
    try:
        return str(validator(text))
    except Exception as exc:
        raise RequestError(f"{label}: {exc}") from None


def build_argv(payload: dict) -> list[str]:
    """Turns the form values of the page into command line arguments for `recon.cli.main`"""
    mode = payload.get("mode")
    if mode not in MODES:
        raise RequestError("Choose a tool first.")
    if payload.get("authorized") is not True:
        raise RequestError("Confirm that you own this server or have written permission to test it.")

    argv = ["--quiet", "--mode", str(mode)]
    argv += ["--host", _checked(payload, "host", "Server address", cli.hostname, required=True) or ""]

    timeout = _checked(payload, "timeout", "Timeout", cli.positive_seconds)
    if timeout is not None:
        if float(timeout) > _limit("max_timeout_seconds"):
            raise RequestError(f"Timeout: must be at most {_limit('max_timeout_seconds')} seconds.")
        argv += ["--timeout", timeout]

    if mode == "rcon":
        rcon_port = _checked(payload, "rcon_port", "RCON port", cli.port_number)
        if rcon_port is not None:
            argv += ["--rcon-port", rcon_port]
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise RequestError("Enter the RCON password.")
        if len(password) > _limit("max_password_chars") or CONTROL_CHARS.search(password):
            raise RequestError("RCON password: too long or contains control characters.")
        preset = _field(payload, "preset")
        if preset and preset not in PRESETS:
            raise RequestError("Quick check: choose one of the listed sets.")
        command = _field(payload, "command")
        if len(command) > _limit("max_command_chars") or CONTROL_CHARS.search(command):
            raise RequestError(f"Command: must be at most {_limit('max_command_chars')} characters, on one line.")
        argv += ["--password", password]
        if preset:
            argv += ["--preset", preset]
        if command or not preset:
            argv += ["--cmd", command or "list"]
        return argv

    port = _checked(payload, "port", "Port", cli.port_number)
    if port is not None:
        argv += ["--port", port]

    if mode == "ghost":
        username = _field(payload, "username") or "AuditNode"
        if not USERNAME_PATTERN.match(username):
            raise RequestError("Player name: use 1 to 16 letters, digits or underscores.")
        argv += ["--username", username]
        version = _checked(payload, "protocol_version", "Version", cli.protocol_choice)
        if version is not None:
            argv += ["--protocol-version", version]
        duration = _checked(payload, "duration", "Duration", cli.positive_int)
        if duration is not None:
            if int(duration) > _limit("max_duration_seconds"):
                raise RequestError(f"Duration: must be at most {_limit('max_duration_seconds')} seconds.")
            argv += ["--duration", duration]
        diagnostics = payload.get("diagnostics")
        if diagnostics not in (None, True, False):
            raise RequestError("Diagnostics: must be on or off.")
        if diagnostics is True:
            argv.append("--diagnostics")
    return argv


class Job:
    """Output and state of one run, read by the page while it is running"""

    def __init__(self, job_id: str, mode: str) -> None:
        self.id = job_id
        self.mode = mode
        self.lines: list[dict[str, str]] = []
        self.done = False
        self.exit_code: int | None = None
        self.truncated = False
        self.started = time.monotonic()
        self.seconds = 0.0
        self.lock = threading.Lock()

    def add(self, stream: str, text: str) -> None:
        with self.lock:
            if len(self.lines) >= _limit("max_output_lines"):
                self.truncated = True
                return
            self.lines.append({"stream": stream, "text": text[: _limit("max_line_chars")]})

    def finish(self, exit_code: int) -> None:
        with self.lock:
            self.exit_code = exit_code
            self.seconds = round(time.monotonic() - self.started, 1)
            self.done = True

    def snapshot(self, since: int) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "mode": self.mode,
                "lines": self.lines[since:],
                "next": len(self.lines),
                "done": self.done,
                "exit_code": self.exit_code,
                "seconds": self.seconds if self.done else round(time.monotonic() - self.started, 1),
                "truncated": self.truncated,
            }


class _LineWriter(io.TextIOBase):
    """Collects what the CLI prints and hands it to the job one line at a time"""

    def __init__(self, job: Job, stream: str) -> None:
        self._job = job
        self._stream = stream
        self._buffer = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._job.add(self._stream, line)
        return len(text)

    def flush(self) -> None:
        pass

    def finish(self) -> None:
        if self._buffer:
            self._job.add(self._stream, self._buffer)
            self._buffer = ""


class JobRunner:
    """Runs one job at a time in a background thread"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._current: Job | None = None

    def start(self, mode: str, argv: list[str]) -> Job:
        with self._lock:
            if self._current is not None and not self._current.done:
                raise JobBusyError("A job is still running. Wait for it to finish.")
            job = Job(secrets.token_hex(8), mode)
            self._jobs[job.id] = job
            while len(self._jobs) > _limit("keep_jobs"):
                del self._jobs[next(iter(self._jobs))]
            self._current = job
        threading.Thread(target=self._run, args=(job, argv), daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    @staticmethod
    def _run(job: Job, argv: list[str]) -> None:
        out = _LineWriter(job, "out")
        err = _LineWriter(job, "err")
        code = 1
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = cli.main(argv)
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else 1
        except Exception as exc:
            err.write(f"[!] Unexpected error: {type(exc).__name__}: {exc}\n")
            code = 1
        finally:
            out.finish()
            err.finish()
            job.finish(code)


class ReconWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.token = secrets.token_urlsafe(32)
        self.runner = JobRunner()
        actual = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{actual}", f"localhost:{actual}"}

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/"


def _version_rows() -> list[dict]:
    rows = []
    for protocol in sorted(VERSION_NAMES, reverse=True):
        rows.append({"protocol": protocol, "name": version_range(protocol), "supported": protocol in PROFILES})
    return rows


class _Handler(BaseHTTPRequestHandler):
    server: ReconWebServer  # type: ignore[assignment]
    server_version = "ReconWeb"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:
        pass

    # --- helpers -------------------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def _fail(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def _api_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{host}" for host in self.server.allowed_hosts}:
            return False
        token = self.headers.get("X-Recon-Token", "")
        return secrets.compare_digest(token.encode("utf-8"), self.server.token.encode("utf-8"))

    # --- routes --------------------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._host_ok():
            self._fail(403, "Unexpected host header.")
            return
        parts = urlsplit(self.path)
        path = parts.path
        if path in ("/", "/index.html"):
            page = (WEB_DIR / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", self.server.token)
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            name = path[len("/static/") :]
            if name not in STATIC_FILES:
                self._fail(404, "Not found.")
                return
            self._send(200, (WEB_DIR / name).read_bytes(), STATIC_FILES[name])
        elif path.startswith("/api/"):
            if not self._api_ok():
                self._fail(403, "Missing or wrong token.")
                return
            self._get_api(path, parse_qs(parts.query))
        else:
            self._fail(404, "Not found.")

    def _get_api(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/info":
            presets = [{"name": name, "label": PRESET_LABELS[name]} for name in PRESETS]
            cfg = settings.current()
            limits = {"max_timeout_seconds": _limit("max_timeout_seconds"), "max_duration_seconds": _limit("max_duration_seconds")}
            shown = {"timeout": cfg["defaults"]["timeout"], "duration": cfg["defaults"]["duration"], "username": cfg["defaults"]["username"]}
            self._json(200, {"version": cli.VERSION, "modes": list(MODES), "presets": presets, "limits": limits, "defaults": shown})
        elif path == "/api/versions":
            self._json(200, {"versions": _version_rows()})
        elif path.startswith("/api/jobs/"):
            job = self.server.runner.get(path[len("/api/jobs/") :])
            if job is None:
                self._fail(404, "Unknown job.")
                return
            try:
                since = max(0, int(query.get("since", ["0"])[0]))
            except ValueError:
                since = 0
            self._json(200, job.snapshot(since))
        else:
            self._fail(404, "Not found.")

    def do_POST(self) -> None:
        if not self._host_ok():
            self._fail(403, "Unexpected host header.")
            return
        if not self._api_ok():
            self._fail(403, "Missing or wrong token.")
            return
        if urlsplit(self.path).path != "/api/run":
            self._fail(404, "Not found.")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY_BYTES:
            self._fail(400, "The request body is missing or too large.")
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self._fail(400, "The request is not valid JSON.")
            return
        try:
            argv = build_argv(payload)
            job = self.server.runner.start(str(payload["mode"]), argv)
        except RequestError as exc:
            self._fail(400, str(exc))
        except JobBusyError as exc:
            self._fail(409, str(exc))
        else:
            self._json(202, {"job": job.id})


def create_server(port: int = 0) -> ReconWebServer:
    return ReconWebServer(port)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recon-gui", description="Open the Minecraft Recon web interface in your browser.")
    parser.add_argument("--version", action="version", version=f"recon-gui {cli.VERSION}")
    parser.add_argument("--config", default=None, metavar="FILE", help=f"Settings file to use (default: the {settings.ENV_VAR} variable, or settings.ini in this folder or the project folder)")
    parser.add_argument("--port", type=cli.port_number, default=None, help="Port for the local page (default: web port from the settings, or any free port)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    args = parser.parse_args(argv)

    try:
        settings.use_file(args.config)
    except settings.SettingsError as exc:
        print(f"[!] {exc}", file=cli.sys.stderr)
        return 2
    candidates: list[int] = [args.port] if args.port else [settings.get("web", "port"), 0]
    server: ReconWebServer | None = None
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            server = create_server(candidate)
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        print(f"[!] Could not start the local web server: {last_error}", file=cli.sys.stderr)
        return 1

    print(cli.COMPLIANCE_BANNER)
    print(f"Minecraft Recon is running at {server.url}")
    print(f"Settings: {settings.origin() or 'built-in values (no settings.ini found)'}")
    print("The page only works on this computer. Press Ctrl+C to stop.")
    if not args.no_browser and settings.get("web", "open_browser") and not webbrowser.open(server.url):
        print("Could not open a browser automatically. Open the address above yourself.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
