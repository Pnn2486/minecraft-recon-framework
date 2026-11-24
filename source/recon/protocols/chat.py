"""Reads the chat packets the test player gets in the game, how it works is in README section 10.6"""

import re
import struct
import uuid
from dataclasses import dataclass

from recon.exceptions import ProtocolFramingError
from recon.protocols.ghost_profile_data import ROWS
from recon.protocols.ghost_profiles import GhostProfile
from recon.utils.nbt import read_network_nbt
from recon.utils.text import component_to_text, json_text_to_plain, strip_codes
from recon.utils.varint import read_varint_bytes

MAX_MESSAGE_BYTES = 4096
SIGNATURE_BYTES = 256
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


@dataclass(frozen=True)
class ChatMessage:
    kind: str  # chat, system, player, disguised
    text: str
    sender: str = ""
    signed: bool | None = None


def _opaque_in_table_order(protocol: int) -> list[int]:
    for row in ROWS:
        if row[0] == protocol:
            return list(row[6])
    return []


def packet_kinds(profile: GhostProfile) -> dict[int, str]:
    """Maps every chat packet ID of a profile to its kind"""
    kinds: dict[int, str] = {}
    json_kind = "chat" if profile.protocol < 759 else "system"
    for pkt_id in profile.play_chat_json_ids:
        kinds[pkt_id] = json_kind
    names: tuple[str, ...]
    if profile.protocol >= 765:
        names = ("system", "player", "disguised")
    elif profile.protocol >= 761:
        names = ("player", "disguised")
    else:
        names = ("player",)
    for pkt_id, name in zip(_opaque_in_table_order(profile.protocol), names, strict=False):
        kinds[pkt_id] = name
    return kinds


class _Reader:
    def __init__(self, data: bytes, json_text: bool) -> None:
        self.data = data
        self.pos = 0
        self.json_text = json_text

    def take(self, count: int) -> bytes:
        if count < 0 or self.pos + count > len(self.data):
            raise ProtocolFramingError("chat packet ends too early")
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def varint(self) -> int:
        value, self.pos = read_varint_bytes(self.data, self.pos)
        return value

    def boolean(self) -> bool:
        return self.take(1)[0] != 0

    def long(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def string(self) -> str:
        length = self.varint()
        if length < 0 or length > MAX_MESSAGE_BYTES:
            raise ProtocolFramingError("chat string has an invalid length")
        try:
            return self.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolFramingError("chat string is not UTF-8") from exc

    def component(self) -> str:
        if self.json_text:
            return json_text_to_plain(self.string())
        value, self.pos = read_network_nbt(self.data, self.pos)
        return strip_codes(component_to_text(value))

    def optional_component(self) -> str:
        return self.component() if self.boolean() else ""


def _clean_message(text: str) -> str:
    if not text or CONTROL.search(text):
        raise ProtocolFramingError("chat text is empty or has control characters")
    return text


def _decode_simple(profile: GhostProfile, kind: str, data: bytes) -> ChatMessage:
    """Plain JSON chat (before 1.19) and system chat (1.19 and newer): the component comes first"""
    reader = _Reader(data, profile.text_is_json)
    return ChatMessage(kind, reader.component())


def _decode_disguised(profile: GhostProfile, data: bytes) -> ChatMessage:
    reader = _Reader(data, profile.text_is_json)
    message = reader.component()
    reader.varint()  # chat type
    sender = reader.component()
    return ChatMessage("disguised", f"<{sender}> {message}" if sender else message, sender, False)


def _player_tail(reader: _Reader) -> str:
    """The part after the signed message. Only the sender name matters, so any failure is ignored"""
    for _ in range(reader.varint()):  # previous messages
        if reader.varint() == 0:
            reader.take(SIGNATURE_BYTES)
    reader.optional_component()  # unsigned content
    if reader.varint() == 2:  # filter type with bit set
        reader.take(8 * reader.varint())
    reader.varint()  # chat type
    return reader.component()


def _player_candidate(profile: GhostProfile, data: bytes, global_index: bool) -> ChatMessage:
    reader = _Reader(data, profile.text_is_json)
    if global_index:
        reader.varint()
    sender_uuid = str(uuid.UUID(bytes=reader.take(16)))
    reader.varint()  # index
    signed = reader.boolean()
    if signed:
        reader.take(SIGNATURE_BYTES)
    message = _clean_message(reader.string())
    reader.long()  # timestamp
    reader.long()  # salt
    sender = ""
    try:
        sender = _player_tail(reader)
    except (ProtocolFramingError, ValueError):
        sender = ""
    label = sender or sender_uuid[:8]
    return ChatMessage("player", f"<{label}> {message}", label, signed)


def _decode_player_legacy(profile: GhostProfile, data: bytes) -> ChatMessage:
    """1.19 to 1.19.2: signed content, optional unsigned content, type, sender UUID, sender name"""
    reader = _Reader(data, True)
    signed_text = json_text_to_plain(reader.string())
    unsigned = ""
    if reader.boolean():
        unsigned = json_text_to_plain(reader.string())
    reader.varint()  # chat type
    sender_uuid = str(uuid.UUID(bytes=reader.take(16)))
    sender = json_text_to_plain(reader.string())
    text = _clean_message(unsigned or signed_text)
    label = sender or sender_uuid[:8]
    return ChatMessage("player", f"<{label}> {text}", label, True)


def _decode_player(profile: GhostProfile, data: bytes) -> ChatMessage:
    if profile.protocol < 761:
        return _decode_player_legacy(profile, data)
    order = (True, False) if profile.protocol >= 768 else (False, True)
    last: Exception | None = None
    for global_index in order:
        try:
            return _player_candidate(profile, data, global_index)
        except (ProtocolFramingError, ValueError) as exc:
            last = exc
    raise ProtocolFramingError(f"player chat layout not recognised: {last}")


def decode_chat_packet(profile: GhostProfile, pkt_id: int, data: bytes) -> ChatMessage | None:
    """Returns the decoded message, or None when the packet cannot be read (the caller then reports it as not decoded)"""
    kind = packet_kinds(profile).get(pkt_id)
    if kind is None:
        return None
    try:
        if kind in ("chat", "system"):
            message = _decode_simple(profile, kind, data)
        elif kind == "disguised":
            message = _decode_disguised(profile, data)
        else:
            message = _decode_player(profile, data)
    except (ProtocolFramingError, ValueError, struct.error):
        return None
    if not message.text.strip():
        return None
    return message


def readable_strings(data: bytes, minimum: int = 4, limit: int = 6) -> list[str]:
    """Runs of readable characters inside a packet. A hint for packets that could not be decoded"""
    text = data.decode("utf-8", errors="ignore")
    runs = re.findall(rf"[^\x00-\x1f\x7f]{{{minimum},}}", text)
    return [run[:120] for run in runs[:limit]]


def hex_preview(data: bytes, limit: int = 48) -> str:
    shown = " ".join(f"{b:02x}" for b in data[:limit])
    return shown + (" ..." if len(data) > limit else "")
