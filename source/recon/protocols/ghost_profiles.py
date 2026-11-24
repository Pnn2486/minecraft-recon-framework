"""Packet IDs per Minecraft version for the test player, the numbers are in ghost_profile_data.py"""

from dataclasses import dataclass

from recon.exceptions import ReconError
from recon.protocols.ghost_profile_data import ROWS
from recon.utils.versions import describe, version_range


class UnsupportedProtocolError(ReconError):
    """Raised when --protocol-version has no ghost profile"""


# How the login start packet is built after the username:
#   name           nothing else                         (1.8 - 1.18.2)
#   name_sig       "no signature data"                  (1.19)
#   name_sig_uuid  "no signature data", "no UUID"       (1.19.1 - 1.19.2)
#   name_uuid_opt  "no UUID"                            (1.19.3 - 1.20.1)
#   name_uuid      16-byte offline UUID                 (1.20.2 and newer)
LOGIN_START_FORMATS = ("name", "name_sig", "name_sig_uuid", "name_uuid_opt", "name_uuid")


@dataclass(frozen=True)
class GhostProfile:
    protocol: int
    name: str
    login_start_format: str
    has_configuration_phase: bool
    # Play state
    play_keep_alive_in: int
    play_keep_alive_out: int
    play_disconnect: int
    play_chat_json_ids: frozenset[int]
    play_chat_opaque_ids: frozenset[int]
    text_is_json: bool
    # Login state
    login_acknowledged_out: int = -1
    # Configuration state (only used when has_configuration_phase is True; -1 means "not present")
    config_disconnect_in: int = -1
    config_finish_in: int = -1
    config_finish_ack_out: int = -1
    config_keep_alive_in: int = -1
    config_keep_alive_out: int = -1
    config_ping_in: int = -1
    config_pong_out: int = -1
    config_known_packs_in: int = -1
    config_known_packs_out: int = -1

    @property
    def login_start_has_uuid(self) -> bool:
        return self.login_start_format == "name_uuid"


def _none_to_missing(value: int | None) -> int:
    return -1 if value is None else value


def _build(row: tuple) -> GhostProfile:
    (protocol, fmt, ka_in, ka_out, disconnect, json_ids, opaque_ids, text_json, cfg) = row
    if fmt not in LOGIN_START_FORMATS:
        raise ValueError(f"unknown login start format {fmt!r} for protocol {protocol}")
    common = dict(
        protocol=protocol,
        name=version_range(protocol) or f"protocol {protocol}",
        login_start_format=fmt,
        play_keep_alive_in=ka_in,
        play_keep_alive_out=ka_out,
        play_disconnect=disconnect,
        play_chat_json_ids=frozenset(json_ids),
        play_chat_opaque_ids=frozenset(opaque_ids),
        text_is_json=text_json,
    )
    if cfg is None:
        return GhostProfile(has_configuration_phase=False, **common)
    (dis, fin, fin_ack, ka_c_in, ka_c_out, ping, pong, kp_in, kp_out, login_ack) = cfg
    return GhostProfile(
        has_configuration_phase=True,
        login_acknowledged_out=login_ack,
        config_disconnect_in=dis,
        config_finish_in=fin,
        config_finish_ack_out=fin_ack,
        config_keep_alive_in=ka_c_in,
        config_keep_alive_out=ka_c_out,
        config_ping_in=ping,
        config_pong_out=pong,
        config_known_packs_in=_none_to_missing(kp_in),
        config_known_packs_out=_none_to_missing(kp_out),
        **common,
    )


PROFILES: dict[int, GhostProfile] = {row[0]: _build(row) for row in ROWS}


def supported_versions() -> str:
    """Human-readable list such as '1.8 - 1.8.9 (47), 1.9 (107), ...'"""
    return ", ".join(f"{p.name} ({num})" for num, p in sorted(PROFILES.items()))


def get_profile(protocol_version: int) -> GhostProfile:
    """Returns the profile for `protocol_version` or raises UnsupportedProtocolError"""
    try:
        return PROFILES[protocol_version]
    except KeyError:
        raise UnsupportedProtocolError(
            f"Ghost mode has no packet table for {describe(protocol_version)}. Supported: {supported_versions()}."
        ) from None
