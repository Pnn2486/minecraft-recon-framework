"""Command-line interface and dispatch router for minecraft-recon-framework"""

import argparse
import json
import math
import os
import sys
from recon import settings
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import rcon_command, rcon_commands
from recon.protocols.rcon_presets import PRESETS
from recon.protocols.ghost import AUTO_PROTOCOL, headless_ghost_stream
from recon.protocols.ghost_profiles import PROFILES
from recon.utils.versions import VERSION_NAMES, protocol_for_name, version_range

VERSION = "1.1.0"
PASSWORD_ENV_VAR = "MC_RCON_PASSWORD"

COMPLIANCE_BANNER = f"========================================================================\nminecraft-recon-framework v{VERSION} | Authorized diagnostic use only\nThe creator accepts no responsibility for any misuse of this software.\n========================================================================"


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
    """Prints every known Minecraft release with its protocol number and ghost-mode support, then exits"""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"{'Minecraft':<20} {'Protocol':>8}  Ghost mode")
        for protocol in sorted(VERSION_NAMES):
            support = "supported" if protocol in PROFILES else "not supported"
            print(f"{version_range(protocol):<20} {protocol:>8}  {support}")
        parser.exit(0)


def hostname(text: str) -> str:
    """A non-empty host name or IP address without spaces or control characters"""
    value = text.strip()
    if not value or len(value) > 253:
        raise argparse.ArgumentTypeError("host must be 1 to 253 characters long")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise argparse.ArgumentTypeError("host must not contain spaces or control characters")
    return value


def positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"{text} must be a positive number of seconds")
    return value


def build_parser(cfg: dict | None = None) -> argparse.ArgumentParser:
    cfg = (cfg or settings.current())["defaults"]
    parser = argparse.ArgumentParser(prog="recon", description="Zero-dependency Minecraft network reconnaissance and protocol auditing framework.")
    parser.add_argument("--version", action="version", version=f"recon {VERSION}")
    parser.add_argument("--list-versions", action=_ListVersions, help="List known Minecraft versions and their protocol numbers, then exit")
    parser.add_argument("--config", default=None, metavar="FILE", help=f"Settings file to use (default: the {settings.ENV_VAR} variable, or settings.ini in this folder or the project folder)")
    parser.add_argument("--host", type=hostname, required=True, help="Target hostname or IP address (query mode is IPv4 only)")
    parser.add_argument("--mode", choices=["ping", "query", "rcon", "ghost"], required=True, help="Protocol state machine to execute")
    parser.add_argument("--port", type=port_number, default=cfg["port"], help=f"Target TCP/UDP game port (default: {cfg['port']})")
    parser.add_argument("--rcon-port", type=port_number, default=cfg["rcon_port"], help=f"Target TCP RCON port (default: {cfg['rcon_port']})")
    parser.add_argument("--timeout", type=positive_seconds, default=cfg["timeout"], help=f"Socket timeout in seconds (default: {cfg['timeout']})")
    parser.add_argument("--password", default=None, help=f"RCON authentication secret (required for --mode rcon). Prefer the {PASSWORD_ENV_VAR} environment variable: command-line arguments are visible to other users and saved in shell history")
    parser.add_argument("--cmd", action="append", default=None, help="Console command for --mode rcon (default: list). Repeat the option to run several commands on one connection")
    parser.add_argument("--preset", choices=sorted(PRESETS), default=None, help="Run a ready-made set of read-only commands with --mode rcon: " + ", ".join(sorted(PRESETS)))
    parser.add_argument("--username", default=cfg["username"], help=f"Username sent in the login start packet (0x00) for --mode ghost (default: {cfg['username']})")
    parser.add_argument("--protocol-version", type=protocol_choice, default=protocol_choice(str(cfg["protocol_version"])), help=f'Version for --mode ghost: a protocol number (754), a Minecraft version (1.16.5), or "auto" to detect it from the server (default: {cfg["protocol_version"]})')
    parser.add_argument("--duration", type=positive_int, default=cfg["duration"], help=f"Session listen TTL in seconds for --mode ghost (default: {cfg['duration']})")
    parser.add_argument("--diagnostics", action="store_true", default=cfg["diagnostics"], help="Print a session report (timeline, packet counts, chat decoding) after --mode ghost")
    parser.add_argument("--quiet", action="store_true", default=cfg["quiet"], help="Suppress compliance banner for JSON piping")
    return parser


def _load_settings(argv: list[str] | None) -> None:
    """Loads the settings file named by --config, or finds one, unless the caller already did"""
    early = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    early.add_argument("--config", default=None)
    explicit = early.parse_known_args(argv)[0].config
    if explicit or not settings.configured():
        settings.use_file(explicit)


def main(argv: list[str] | None = None) -> int:
    try:
        _load_settings(argv)
    except settings.SettingsError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2
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
            password = args.password if args.password is not None else os.environ.get(PASSWORD_ENV_VAR, "")
            if not password:
                print(f"[!] Error: --password or the {PASSWORD_ENV_VAR} environment variable is required when --mode rcon is selected.", file=sys.stderr)
                return 2
            commands = list(PRESETS[args.preset]) if args.preset else []
            commands += args.cmd or ([] if args.preset else ["list"])
            if len(commands) == 1:
                print(rcon_command(host=args.host, port=args.rcon_port, password=password, command=commands[0], timeout=args.timeout))
            else:
                for command, output in rcon_commands(host=args.host, port=args.rcon_port, password=password, commands=commands, timeout=args.timeout):
                    print(f"[>] {command}")
                    print(output if output.strip() else "(no output)")

        elif args.mode == "ghost":
            headless_ghost_stream(host=args.host, port=args.port, username=args.username, protocol_version=args.protocol_version, duration=args.duration, timeout=args.timeout, diagnostics=args.diagnostics)

    except ReconError as exc:
        print(f"[!] Protocol error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[!] Network error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[*] Session terminated by operator.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
