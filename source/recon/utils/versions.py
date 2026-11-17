"""
Minecraft release names for each protocol number, so output can say "1.16.5" instead of "754".

Covers every Java Edition release from 1.7 (the first with the current network protocol) up to
the newest one . A number can appear here without being supported by ghost
mode (see ghost_profile_data.py): this table only translates numbers into names.

Source: `data/pc/common/protocolVersions.json` in the PrismarineJS `minecraft-data` project
(https://github.com/PrismarineJS/minecraft-data). Releases only; snapshots are left out.

To add a release, append its name to the tuple for its protocol number (or add a new line).
"""

VERSION_NAMES: dict[int, tuple[str, ...]] = {
    4: ('1.7.2', '1.7.4', '1.7.5'),
    5: ('1.7.6', '1.7.7', '1.7.8', '1.7.9', '1.7.10'),
    47: ('1.8', '1.8.1', '1.8.2', '1.8.3', '1.8.4', '1.8.5', '1.8.6', '1.8.7', '1.8.8', '1.8.9'),
    107: ('1.9',),
    108: ('1.9.1',),
    109: ('1.9.2',),
    110: ('1.9.3', '1.9.4'),
    210: ('1.10', '1.10.1', '1.10.2'),
    315: ('1.11',),
    316: ('1.11.1', '1.11.2'),
    335: ('1.12',),
    338: ('1.12.1',),
    340: ('1.12.2',),
    393: ('1.13',),
    401: ('1.13.1',),
    404: ('1.13.2',),
    477: ('1.14',),
    480: ('1.14.1',),
    485: ('1.14.2',),
    490: ('1.14.3',),
    498: ('1.14.4',),
    573: ('1.15',),
    575: ('1.15.1',),
    578: ('1.15.2',),
    735: ('1.16',),
    736: ('1.16.1',),
    751: ('1.16.2',),
    753: ('1.16.3',),
    754: ('1.16.4', '1.16.5'),
    755: ('1.17',),
    756: ('1.17.1',),
    757: ('1.18', '1.18.1'),
    758: ('1.18.2',),
    759: ('1.19',),
    760: ('1.19.1', '1.19.2'),
    761: ('1.19.3',),
    762: ('1.19.4',),
    763: ('1.20', '1.20.1'),
    764: ('1.20.2',),
    765: ('1.20.3', '1.20.4'),
    766: ('1.20.5', '1.20.6'),
    767: ('1.21', '1.21.1'),
    768: ('1.21.2', '1.21.3'),
    769: ('1.21.4',),
    770: ('1.21.5',),
    771: ('1.21.6',),
    772: ('1.21.7', '1.21.8'),
    773: ('1.21.9', '1.21.10'),
    774: ('1.21.11',),
    775: ('26.1', '26.1.1', '26.1.2'),
    776: ('26.2',),
    777: ('26.3',),
}


def version_range(protocol: int) -> str | None:
    """Readable release names for a protocol number: "1.16.4 - 1.16.5", "1.12.2", or None if unknown."""
    names = VERSION_NAMES.get(protocol)
    if not names:
        return None
    return names[0] if len(names) == 1 else f"{names[0]} - {names[-1]}"


def describe(protocol: int) -> str:
    """One-line description such as "Minecraft 1.16.4 - 1.16.5 (protocol 754)"."""
    rng = version_range(protocol)
    if rng is None:
        return f"an unknown Minecraft version (protocol {protocol})"
    return f"Minecraft {rng} (protocol {protocol})"


_NAME_TO_PROTOCOL: dict[str, int] = {name: proto for proto, names in VERSION_NAMES.items() for name in names}


def protocol_for_name(name: str) -> int | None:
    """Protocol number for a release name such as "1.16.5", or None if the name is unknown."""
    return _NAME_TO_PROTOCOL.get(name.strip())
