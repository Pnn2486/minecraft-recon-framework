# Changelog

All notable changes are listed here, newest first. Version numbers go major.minor.patch, so 1.2.0 comes after 1.1.0.

## 1.2.0 - unreleased

### Added
- Local web interface (`recon-gui`) for server status, server details, the RCON console and the test player, with saved server tiles
- Chat decoding for the test player: player, system and disguised chat, including the text format of 1.20.3 and newer
- Session diagnostics report for the test player (`--diagnostics`)
- Ready-made read-only RCON command sets (`--preset`), and several commands on one connection
- Optional `settings.ini` with 27 settings, and `--config` to pick another file
- Launchers for Windows, macOS and Linux in the `launchers` folder, with `boot.py` checking the system and the Python version
- `SECURITY.md`, this changelog and issue and pull request templates
- Tests on more systems: Ubuntu 22.04 and 24.04, Windows 2022, 2025 and 11 ARM, macOS 14, 15 and Intel, ARM Linux, and 25 Linux distribution containers

### Changed
- README rewritten with numbered sections, install steps for every system and a table of settings
- Packet inspector moved from `tools/` to `scripts/`, launchers moved from the main folder to `launchers/`
- Development status in `pyproject.toml` is now Beta

### Fixed
- A server can no longer make the client read or unpack an unlimited amount of data, packets over 8 MiB are refused
- A status reply that is not a JSON object no longer crashes the client
- An RCON password or command that starts with a dash now works in the web interface
- On Windows the web interface no longer shares its port with another program, and silent connections are dropped after 15 seconds
- Static file serving in the web interface only uses a fixed list of paths

## 1.1.0

### Added
- Protocol version detection from the server (`--protocol-version auto`), now the default
- Minecraft version names in the output and in errors, and `--list-versions` to see every known version
- Python 3.13, 3.14 and 3.15 in the test matrix
- A GitHub workflow that builds the package and makes a release when a version tag is pushed
- Text component conversion for server messages

### Included from the start
- Server list ping with a latency check, GameSpy4 query over UDP, Source RCON and a headless test player for offline-mode servers

