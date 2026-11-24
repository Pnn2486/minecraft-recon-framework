"""Reads the NBT text that servers send since 1.20.3"""

import struct
from typing import Any

from recon.exceptions import ProtocolFramingError

MAX_DEPTH = 64
MAX_ELEMENTS = 100_000

TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE = range(7)
TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY = range(7, 13)

_FIXED = {TAG_BYTE: ">b", TAG_SHORT: ">h", TAG_INT: ">i", TAG_LONG: ">q", TAG_FLOAT: ">f", TAG_DOUBLE: ">d"}


def _take(buf: bytes, offset: int, count: int) -> tuple[bytes, int]:
    if count < 0 or offset + count > len(buf):
        raise ProtocolFramingError("NBT data ends too early.")
    return buf[offset : offset + count], offset + count


def _read_string(buf: bytes, offset: int) -> tuple[str, int]:
    raw, offset = _take(buf, offset, 2)
    length = struct.unpack(">H", raw)[0]
    text, offset = _take(buf, offset, length)
    return text.decode("utf-8", errors="replace"), offset


def _read_payload(buf: bytes, offset: int, tag: int, depth: int) -> tuple[Any, int]:
    if depth > MAX_DEPTH:
        raise ProtocolFramingError("NBT is nested too deeply.")
    if tag in _FIXED:
        fmt = _FIXED[tag]
        raw, offset = _take(buf, offset, struct.calcsize(fmt))
        return struct.unpack(fmt, raw)[0], offset
    if tag == TAG_STRING:
        return _read_string(buf, offset)
    if tag in (TAG_BYTE_ARRAY, TAG_INT_ARRAY, TAG_LONG_ARRAY):
        raw, offset = _take(buf, offset, 4)
        count = struct.unpack(">i", raw)[0]
        size = {TAG_BYTE_ARRAY: 1, TAG_INT_ARRAY: 4, TAG_LONG_ARRAY: 8}[tag]
        if count < 0 or count > MAX_ELEMENTS:
            raise ProtocolFramingError("NBT array has an invalid length.")
        data, offset = _take(buf, offset, count * size)
        return data, offset
    if tag == TAG_LIST:
        raw, offset = _take(buf, offset, 5)
        item_tag = raw[0]
        count = struct.unpack(">i", raw[1:])[0]
        if count < 0 or count > MAX_ELEMENTS or (count and item_tag == TAG_END):
            raise ProtocolFramingError("NBT list has an invalid length or type.")
        items = []
        for _ in range(count):
            item, offset = _read_payload(buf, offset, item_tag, depth + 1)
            items.append(item)
        return items, offset
    if tag == TAG_COMPOUND:
        result: dict[str, Any] = {}
        while True:
            raw, offset = _take(buf, offset, 1)
            child = raw[0]
            if child == TAG_END:
                return result, offset
            if len(result) >= MAX_ELEMENTS:
                raise ProtocolFramingError("NBT compound has too many entries.")
            name, offset = _read_string(buf, offset)
            result[name], offset = _read_payload(buf, offset, child, depth + 1)
    raise ProtocolFramingError(f"Unknown NBT tag type {tag}.")


def read_network_nbt(buf: bytes, offset: int = 0) -> tuple[Any, int]:
    """Reads one nameless root tag. Returns `(python_value, next_offset)`"""
    raw, offset = _take(buf, offset, 1)
    tag = raw[0]
    if tag == TAG_END:
        return None, offset
    return _read_payload(buf, offset, tag, 0)
