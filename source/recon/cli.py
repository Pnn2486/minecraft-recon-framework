"""Command-Line Interface and Dispatch Router for minecraft-recon-framework."""

import argparse
import json
import sys
from recon.exceptions import ReconError
from recon.protocols.ping import mc_status_ping
from recon.protocols.query import gamespy4_full_query
from recon.protocols.rcon import rcon_command
from recon.protocols.ghost import headless_ghost_stream

VERSION = "1.1.0"

COMPLIANCE_BANNER = (
    "========================================================================\n"
    f"minecraft-recon-framework v{VERSION} | Authorized Diagnostic Use Only\n"
    "The creator accepts no responsibility for any misuse of this software.\n"
    "========================================================================"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recon",
        description="Zero-dependency Minecraft network reconnaissance and protocol auditing framework.",
    )
    parser.add_argument("--version", action="version", version=f"recon {VERSION}")
    parser.add_argument("--host", required=True, help="Target IPv4 address or FQDN")
    parser.add_argument(
        "--mode",
        choices=["ping", "query", "rcon", "ghost"],
        required=True,
        help="Protocol state machine to execute",
    )
    parser.add_argument("--port", type=int, default=25565, help="Target TCP/UDP game port (default: 25565)")
    parser.add_argument("--rcon-port", type=int, default=25575, help="Target TCP RCON port (default: 25575)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Socket timeout in seconds (default: 5.0)")
    parser.add_argument("--password", default="", help="RCON authentication secret (required for --mode rcon)")
    parser.add_argument("--cmd", default="list", help="Console command payload for RCON execution (default: list)")
    parser.add_argument("--username", default="AuditNode", help="Login Start (0x00) username for --mode ghost")
    parser.add_argument(
        "--protocol-version",
        type=int,
        default=754,
        help="Minecraft protocol version integer for --mode ghost (default: 754 / 1.16.5)",
    )
    parser.add_argument("--duration", type=int, default=30, help="Session listen TTL in seconds for --mode ghost")
    parser.add_argument("--quiet", action="store_true", help="Suppress compliance banner for JSON piping")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.quiet:
        print(COMPLIANCE_BANNER, file=sys.stderr)

    try:
        if args.mode == "ping":
            result = mc_status_ping(
                host=args.host,
                port=args.port,
                timeout=args.timeout,
                measure_latency=True,
            )
            print(json.dumps(result, indent=2))

        elif args.mode == "query":
            result = gamespy4_full_query(
                host=args.host,
                port=args.port,
                timeout=args.timeout,
            )
            print(json.dumps(result, indent=2))

        elif args.mode == "rcon":
            if not args.password:
                print("[!] Error: --password is required when --mode rcon is selected.", file=sys.stderr)
                return 2
            output = rcon_command(
                host=args.host,
                port=args.rcon_port,
                password=args.password,
                command=args.cmd,
                timeout=args.timeout,
            )
            print(output)

        elif args.mode == "ghost":
            headless_ghost_stream(
                host=args.host,
                port=args.port,
                username=args.username,
                protocol_version=args.protocol_version,
                duration=args.duration,
                timeout=args.timeout,
            )

    except ReconError as exc:
        print(f"[!] Protocol Audit Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ConnectionError) as exc:
        print(f"[!] Network Transport Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[*] Session terminated by operator.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
