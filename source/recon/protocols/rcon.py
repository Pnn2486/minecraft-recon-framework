"""Protocol 3: Source RCON, the remote console"""

import socket
import struct
from recon.exceptions import AuthenticationError, ProtocolFramingError, ReconError
from recon.utils.varint import recv_exact

SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RCONClient:
    """Stateful TCP Source RCON client supporting context manager lifecycle"""

    def __init__(self, host: str, port: int = 25575, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._req_counter = 100

    def __enter__(self) -> "RCONClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def connect(self) -> None:
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise ReconError(f"RCON connection failed on {self.host}:{self.port}: {exc}") from exc

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @staticmethod
    def pack_frame(req_id: int, pkt_type: int, payload: str) -> bytes:
        body = payload.encode("utf-8") + b"\x00\x00"
        size = 4 + 4 + len(body)
        return struct.pack("<iii", size, req_id, pkt_type) + body

    def _read_frame(self) -> tuple[int, int, str]:
        if self._sock is None:
            raise ReconError("RCON socket is not connected.")
        raw_size = recv_exact(self._sock, 4)
        frame_size = struct.unpack("<i", raw_size)[0]
        if frame_size < 10 or frame_size > 16384:
            raise ProtocolFramingError(f"Invalid RCON frame size: {frame_size} bytes.")

        frame_body = recv_exact(self._sock, frame_size)
        req_id, pkt_type = struct.unpack("<ii", frame_body[:8])
        if frame_body[-2:] != b"\x00\x00":
            raise ProtocolFramingError("Malformed RCON frame: missing trailing null bytes.")
        text = frame_body[8:-2].decode("utf-8", errors="replace")
        return req_id, pkt_type, text

    def authenticate(self, password: str) -> None:
        if self._sock is None:
            self.connect()
        assert self._sock is not None
        self._req_counter += 1
        auth_id = self._req_counter
        self._sock.sendall(self.pack_frame(auth_id, SERVERDATA_AUTH, password))

        resp_id, resp_type, _ = self._read_frame()
        if resp_type == SERVERDATA_RESPONSE_VALUE:
            resp_id, resp_type, _ = self._read_frame()

        if resp_id == -1 or resp_id != auth_id:
            raise AuthenticationError("RCON authentication failed: the server rejected the password (ID -1).")

    def execute(self, command: str) -> str:
        if self._sock is None:
            raise ReconError("Cannot execute command: RCON session is not authenticated.")
        self._req_counter += 1
        cmd_id = self._req_counter
        self._sock.sendall(self.pack_frame(cmd_id, SERVERDATA_EXECCOMMAND, command))
        _, _, output = self._read_frame()
        return output


def rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    timeout: float = 5.0,
) -> str:
    """One-shot helper to authenticate, execute a single RCON command, and close the socket"""
    with RCONClient(host=host, port=port, timeout=timeout) as client:
        client.authenticate(password)
        return client.execute(command)


def rcon_commands(
    host: str,
    port: int,
    password: str,
    commands: list[str],
    timeout: float = 5.0,
) -> list[tuple[str, str]]:
    """Authenticates once and runs several commands on the same connection. Returns `(command, output)` pairs"""
    results: list[tuple[str, str]] = []
    with RCONClient(host=host, port=port, timeout=timeout) as client:
        client.authenticate(password)
        for command in commands:
            results.append((command, client.execute(command)))
    return results
