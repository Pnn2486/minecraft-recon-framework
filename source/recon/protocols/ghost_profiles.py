"""
Per-version packet tables for the headless ghost client.

Packet IDs change between Minecraft releases, so each supported protocol number
maps to one `GhostProfile`. A protocol number without a profile is rejected
before any connection is made, instead of silently misreading packets.

Status of each profile:
    754 (1.16.5)         Original target of the ghost client.
    767 (1.21, 1.21.1)   IDs taken from the published protocol documentation for
                         1.21.1. Includes the Configuration phase added in 1.20.2.

Neither profile has been run against a real server by the authors of this change;
both are exercised only by the loopback mock servers in tests/test_protocols.py.
Treat them as "implemented to spec", not "field tested".
"""

from dataclasses import dataclass

from recon.exceptions import ReconError


class UnsupportedProtocolError(ReconError):
    """Raised when --protocol-version has no ghost profile."""


@dataclass(frozen=True)
class GhostProfile:
    name: str
    login_start_has_uuid: bool
    has_configuration_phase: bool
    # Play state
    play_keep_alive_in: int
    play_keep_alive_out: int
    play_disconnect: int
    play_chat_ids: frozenset[int]
    chat_is_json_string: bool
    # Login state (same for all supported versions, kept here for clarity)
    login_acknowledged_out: int = 0x03
    # Configuration state (only used when has_configuration_phase is True)
    config_disconnect_in: int = -1
    config_finish_in: int = -1
    config_finish_ack_out: int = -1
    config_keep_alive_in: int = -1
    config_keep_alive_out: int = -1
    config_ping_in: int = -1
    config_pong_out: int = -1
    config_known_packs_in: int = -1
    config_known_packs_out: int = -1


PROFILES: dict[int, GhostProfile] = {
    754: GhostProfile(
        name="1.16.5",
        login_start_has_uuid=False,
        has_configuration_phase=False,
        play_keep_alive_in=0x1F,
        play_keep_alive_out=0x10,
        play_disconnect=0x19,
        play_chat_ids=frozenset({0x0E}),
        chat_is_json_string=True,
    ),
    767: GhostProfile(
        name="1.21 - 1.21.1",
        login_start_has_uuid=True,
        has_configuration_phase=True,
        play_keep_alive_in=0x26,
        play_keep_alive_out=0x18,
        play_disconnect=0x1D,
        play_chat_ids=frozenset({0x39, 0x6C}),  # Player Chat, System Chat
        chat_is_json_string=False,  # signed chat / NBT text components
        config_disconnect_in=0x02,
        config_finish_in=0x03,
        config_finish_ack_out=0x03,
        config_keep_alive_in=0x04,
        config_keep_alive_out=0x04,
        config_ping_in=0x05,
        config_pong_out=0x05,
        config_known_packs_in=0x0E,
        config_known_packs_out=0x07,
    ),
}


def get_profile(protocol_version: int) -> GhostProfile:
    """Returns the profile for `protocol_version` or raises UnsupportedProtocolError."""
    try:
        return PROFILES[protocol_version]
    except KeyError:
        supported = ", ".join(f"{num} ({p.name})" for num, p in sorted(PROFILES.items()))
        raise UnsupportedProtocolError(
            f"Ghost mode has no packet table for protocol {protocol_version}. Supported: {supported}."
        ) from None
