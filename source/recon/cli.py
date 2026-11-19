"""Command-Line Interface and Dispatch Router for minecraft-recon-framework."""

import argparse
import json
import math
import sys
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import rcon_command
from recon.protocols.ghost import AUTO_PROTOCOL, headless_ghost_stream
from recon.protocols.ghost_profiles import PROFILES
from recon.utils.versions import VERSION_NAMES, protocol_for_name, version_range

VERSION = "1.1.0"

COMPLIANCE_BANNER =     "========================================================================\n"
    f"minecraft-recon-framework v{VERSION} | Authorized Diagnostic Use Only\n"
    "The creator accepts no responsibility for any misuse of this software.\n"
    "========================================================================"

def _parse_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer value: {text!r}") from None


def port_number(text: str) -> int:
    value = _parse_int(text)
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError(f"{value} is not a valid port (expected 1-65535)")
    return value


def positive_int(text: str) -> int:
    value = _parse_int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{value} must be at least 1")
    return value


def non_negative_int(text: str) -> int:
    value = _parse_int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"{value} must not be negative")
    return value


def protocol_choice(text: str) -> int | str:
    """A protocol number, a Minecraft version such as 1.16.5, or the word "auto"."""
    text = text.strip()
    if text.lower() == AUTO_PROTOCOL:
        return AUTO_PROTOCOL
    if text.isdigit():
        return int(text)
    protocol = protocol_for_name(text)
    if protocol is not None:
        return protocol
    if text.startswith("-") and text[1:].isdigit():
        raise argparse.ArgumentTypeError(f"{text} must not be negative")
    raise argparse.ArgumentTypeError(f"unknown version {text!r}: use a protocol number, a Minecraft version such as 1.16.5, or auto (see --list-versions)")


class _ListVersions(argparse.Action):
    """Prints every known Minecraft release with its protocol number and ghost-mode support, then exits."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"{'Minecraft':<20} {'Protocol':>8}  Ghost mode")
        for protocol in sorted(VERSION_NAMES):
            support = "supported" if protocol in PROFILES else "not supported"
            print(f"{version_range(protocol):<20} {protocol:>8}  {support}")
        parser.exit(0)


def positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"{text} must be a positive number of seconds")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recon", description="Zero-dependency Minecraft network reconnaissance and protocol auditing framework.")
    parser.add_argument("--version", action="version", version=f"recon {VERSION}")
    parser.add_argument("--list-versions", action=_ListVersions, help="List known Minecraft versions and their protocol numbers, then exit")
    parser.add_argument("--host", required=True, help="Target hostname or IP address (query mode is IPv4 only)")
    parser.add_argument("--mode", choices=["ping", "query", "rcon", "ghost"], required=True, help="Protocol state machine to execute")
    parser.add_argument("--port", type=port_number, default=25565, help="Target TCP/UDP game port (default: 25565)")
    parser.add_argument("--rcon-port", type=port_number, default=25575, help="Target TCP RCON port (default: 25575)")
    parser.add_argument("--timeout", type=positive_seconds, default=5.0, help="Socket timeout in seconds (default: 5.0)")
    parser.add_argument("--password", default="", help="RCON authentication secret (required for --mode rcon)")
    parser.add_argument("--cmd", default="list", help="Console command payload for RCON execution (default: list)")
    parser.add_argument("--username", default="AuditNode", help="Login Start (0x00) username for --mode ghost")
    parser.add_argument("--protocol-version", type=protocol_choice, default=AUTO_PROTOCOL, help='Version for --mode ghost: a protocol number (754), a Minecraft version (1.16.5), or "auto" to detect it from the server (default: auto)')
    parser.add_argument("--duration", type=positive_int, default=30, help="Session listen TTL in seconds for --mode ghost")
    parser.add_argument("--quiet", action="store_true", help="Suppress compliance banner for JSON piping")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.quiet:
        print(COMPLIANCE_BANNER, file=sys.stderr)

    try:
        if args.mode == "ping":
            result = mc_status_ping(host=args.host, port=args.port, timeout=args.timeout, measure_latency=True)
            version = result.get("version")
            if isinstance(version, dict) and isinstance(version.get("protocol"), int):
                names = version_range(version["protocol"])
                if names:
                    version["minecraft_versions"] = names  # readable form of the protocol number
            print(json.dumps(result, indent=2))

        elif args.mode == "query":
            result = gamespy4_full_query(host=args.host, port=args.port, timeout=args.timeout)
            print(json.dumps(result, indent=2))

        elif args.mode == "rcon":
            if not args.password:
                print("[!] Error: --password is required when --mode rcon is selected.", file=sys.stderr)
                return 2
            output = rcon_command(host=args.host, port=args.rcon_port, password=args.password, command=args.cmd, timeout=args.timeout)
            print(output)

        elif args.mode == "ghost":
            headless_ghost_stream(host=args.host, port=args.port, username=args.username, protocol_version=args.protocol_version, duration=args.duration, timeout=args.timeout)

    except ReconError as exc:
        print(f"[!] Protocol Audit Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[!] Network Transport Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[*] Session terminated by operator.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
