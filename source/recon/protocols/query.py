"""
Protocol 2: UDP GameSpy4 Query Protocol (0xFEFD Challenge-Response Full Stat Dump).
"""

import socket
import struct
from recon.exceptions import ProtocolFramingError, ReconError

GAMESPY4_MAGIC = 0xFEFD
PACKET_TYPE_HANDSHAKE = 0x09
PACKET_TYPE_STAT = 0x00
PLAYER_SECTION_DELIMITER = b"\x00\x00\x01player_\x00\x00"


def gamespy4_full_query(
    host: str,
    port: int = 25565,
    timeout: float = 5.0,
    session_id: int = 0x01020304,
) -> dict:
    """
    Executes the stateless two-phase UDP GameSpy4 Full Stat query.
    Requires `enable-query=true` in the target server's `server.properties`.
    """
    masked_session = session_id & 0x0F0F0F0F
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        challenge_req = struct.pack(">HBI", GAMESPY4_MAGIC, PACKET_TYPE_HANDSHAKE, masked_session)
        sock.sendto(challenge_req, (host, port))

        resp_data, _ = sock.recvfrom(4096)
        if len(resp_data) < 5 or resp_data[0] != PACKET_TYPE_HANDSHAKE:
            raise ProtocolFramingError("Invalid GameSpy4 Handshake Challenge header.")

        token_ascii = resp_data[5:].rstrip(b"\x00").decode("ascii", errors="strict")
        challenge_token = int(token_ascii)

        stat_req = struct.pack(
            ">HBII4s",
            GAMESPY4_MAGIC,
            PACKET_TYPE_STAT,
            masked_session,
            challenge_token,
            b"\x00\x00\x00\x00",
        )
        sock.sendto(stat_req, (host, port))

        raw_stat, _ = sock.recvfrom(65535)
        if len(raw_stat) < 16 or raw_stat[0] != PACKET_TYPE_STAT:
            raise ProtocolFramingError("Truncated or invalid GameSpy4 Full Stat response.")

        body = raw_stat[16:]
        if PLAYER_SECTION_DELIMITER not in body:
            raise ProtocolFramingError("Missing GameSpy4 binary player section delimiter.")

        kv_raw, players_raw = body.split(PLAYER_SECTION_DELIMITER, 1)

        kv_tokens = kv_raw.decode("utf-8", errors="replace").split("\x00")
        metadata = dict(zip(kv_tokens[0::2], kv_tokens[1::2]))

        player_tokens = players_raw.rstrip(b"\x00").decode("utf-8", errors="replace").split("\x00")
        players = [p for p in player_tokens if p]

        return {
            "session_id": masked_session,
            "metadata": metadata,
            "player_count": len(players),
            "players": players,
        }

    except ValueError as exc:
        raise ProtocolFramingError(f"Failed to parse GameSpy4 challenge token: {exc}") from exc
    except OSError as exc:
        raise ReconError(
            f"UDP Query failed on {host}:{port} (Verify enable-query=true in server.properties): {exc}"
        ) from exc
    finally:
        sock.close()
