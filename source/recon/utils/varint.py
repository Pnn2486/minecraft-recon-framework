"""
Base-128 VarInt, UTF-8 String Framing, Deterministic Socket Readers,
and Offline UUID v3 Generation for Minecraft Wire Protocols.
"""

import hashlib
import socket
from recon.exceptions import ProtocolFramingError


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Deterministically reads exactly `num_bytes` from a TCP stream socket.
    Prevents partial-read corruption when packets fragment across TCP segments.
    """
    if num_bytes < 0:
        raise ProtocolFramingError(f"Negative byte count requested: {num_bytes}")
    chunks: list[bytes] = []
    bytes_remaining = num_bytes
    while bytes_remaining > 0:
        chunk = sock.recv(min(bytes_remaining, 65536))
        if not chunk:
            raise ProtocolFramingError(
                f"Socket stream closed prematurely ({num_bytes - bytes_remaining}/{num_bytes} bytes read)."
            )
        chunks.append(chunk)
        bytes_remaining -= len(chunk)
    return b"".join(chunks)


def pack_varint(val: int) -> bytes:
    """
    Serializes a 32-bit signed or unsigned integer into a 1-to-5 byte Base-128 VarInt.
    Negative values are encoded using two's complement 32-bit bitmasking.
    """
    if val < 0:
        val = (1 << 32) + val
    out = bytearray()
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    if len(out) > 5:
        raise ProtocolFramingError(f"Integer {val} exceeds 5-byte VarInt maximum.")
    return bytes(out)


def pack_string(text: str) -> bytes:
    """Serializes a UTF-8 string prefixed with its byte length as a VarInt."""
    encoded = text.encode("utf-8")
    return pack_varint(len(encoded)) + encoded


def read_varint_sock(sock: socket.socket) -> int:
    """Reads and decodes a single Base-128 VarInt directly from a TCP socket."""
    val = 0
    shift = 0
    while True:
        raw = recv_exact(sock, 1)
        byte = raw[0]
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
        if shift >= 35:
            raise ProtocolFramingError("Malformed VarInt on socket: exceeds 5-byte limit.")
    if val & (1 << 31):
        val -= 1 << 32
    return val


def read_varint_bytes(buffer: bytes, offset: int = 0) -> tuple[int, int]:
    """
    Decodes a Base-128 VarInt from `buffer` starting at `offset`.
    Returns `(decoded_int, next_offset)`.
    """
    val = 0
    shift = 0
    idx = offset
    buf_len = len(buffer)
    while True:
        if idx >= buf_len:
            raise ProtocolFramingError("Buffer underflow while decoding VarInt.")
        byte = buffer[idx]
        idx += 1
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
        if shift >= 35:
            raise ProtocolFramingError("Malformed VarInt in buffer: exceeds 5-byte limit.")
    if val & (1 << 31):
        val -= 1 << 32
    return val, idx


def read_string_bytes(buffer: bytes, offset: int = 0) -> tuple[str, int]:
    """
    Decodes a VarInt-prefixed UTF-8 string from `buffer` starting at `offset`.
    Returns `(decoded_string, next_offset)`.
    """
    str_len, idx = read_varint_bytes(buffer, offset)
    if str_len < 0 or idx + str_len > len(buffer):
        raise ProtocolFramingError(f"Invalid string byte length ({str_len}) at offset {offset}.")
    decoded = buffer[idx : idx + str_len].decode("utf-8", errors="replace")
    return decoded, idx + str_len


def offline_player_uuid_bytes(username: str) -> bytes:
    """
    Computes the 16-byte offline-mode player UUID (UUID v3 MD5 namespace)
    matching `UUID.nameUUIDFromBytes(("OfflinePlayer:" + username).getBytes(UTF_8))` in Java.
    """
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{username}".encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return bytes(digest)
