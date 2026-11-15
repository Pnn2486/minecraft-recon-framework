# Contributing to minecraft-recon-framework

Thank you for helping improve `minecraft-recon-framework`. We welcome pull requests from network engineers, systems administrators, and Python developers.

## Before you start

- **Authorized use only.** This project exists for network protocol research, systems administration, and authorized security auditing. Read [COPYING.md](./COPYING.md) and [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) first. Contributions or issues that promote unauthorized intrusion, denial-of-service, or abuse of third-party infrastructure will be closed.
- **Python 3.10 or newer.** Check your interpreter with `python3 --version`. The project supports CPython 3.10, 3.11, and 3.12.
- **Larger changes:** open an issue first so we can agree on the approach before you write code.

## Engineering constraints

1. **Zero third-party dependencies.** Everything under `source/recon/` must use only the CPython `>= 3.10` standard library (`socket`, `struct`, `zlib`, `hashlib`, `json`, `argparse`, and so on). Do not add packages to `pyproject.toml`.
2. **Deterministic stream reads.** Never call raw `sock.recv(N)` for fixed-length protocol headers. Always use `recv_exact(sock, N)` from `recon.utils.varint` to avoid TCP fragmentation bugs.
3. **Python 3.10 baseline.** Write modern 3.10 code, and do not use features that only exist in 3.11 or later.
   - Use `X | None` and `X | Y` instead of `Optional[X]` and `Union[X, Y]`.
   - Use built-in generics (`list[int]`, `dict[str, int]`, `tuple[int, ...]`) instead of `typing.List`, `typing.Dict`, and `typing.Tuple`.
   - Pass `strict=True` to `zip()` when the inputs must be the same length.
   - `match` statements are fine where they make packet handling clearer.
   - Avoid 3.11+ only features such as `tomllib`, `typing.Self`, `enum.StrEnum`, and `except*`.
4. **Type hints on public functions.** Annotate parameters and return types for anything exported from `recon`.
5. **Safe networking.** Every socket needs a timeout and must be closed (use `with` blocks or context managers). Never log or print passwords, RCON secrets, or full packet payloads that may contain credentials.
6. **Formatting.** Follow `.editorconfig`: UTF-8, LF line endings, consistent indentation.

## Development setup

Linux and macOS:

```bash
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
export PYTHONPATH="$(pwd)/source"
```

Windows (PowerShell):

```powershell
git clone https://github.com/Pnn2486/minecraft-recon-framework.git
cd minecraft-recon-framework
$env:PYTHONPATH="source"
```

## Pre-commit verification

Run these from the repository root before opening a pull request, and make sure they pass:

```bash
python3 -m unittest discover -s tests -v
python3 tools/packet_inspector.py
```

On Windows, use `python` instead of `python3`.

## Submitting a pull request

1. Fork the repository and create a branch from `main`, for example `git checkout -b fix/short-description`.
2. Keep each pull request focused on one change, with clear commit messages.
3. Add or update tests in `tests/` for any protocol or serialization change. Tests must use `unittest` and must not need network access.
4. Update `README.md` when behavior, flags, or requirements change.
5. Open the pull request and describe what changed, why, and how you tested it, including the Python version and Minecraft server version you used.

## Reporting bugs

Please include:

- your Python version (`python3 --version`) and operating system
- the Minecraft server version and type, if relevant
- the exact command you ran, with passwords and private addresses removed
- the full error message or traceback

Never post real server addresses, credentials, or logs from servers you do not own.

## License

By contributing, you agree that your contributions are licensed under the project's MIT License (see [LICENSE](./LICENSE)).
