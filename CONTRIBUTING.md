# Contributing to minecraft-recon-framework

We welcome pull requests from network engineers, systems administrators, and Python developers.

## Engineering Constraints

1. **Zero Third-Party Dependencies:** All modules under `source/recon/` must rely exclusively on the CPython `>= 3.8` standard library (`socket`, `struct`, `zlib`, `hashlib`, `json`, `argparse`).
2. **Deterministic Stream Reads:** Never invoke raw `sock.recv(N)` for fixed-length protocol headers. Always use `recv_exact(sock, N)` from `recon.utils.varint` to prevent TCP segment fragmentation bugs.
3. **Pre-Commit Verification:** Run the unit test suite and wire-frame inspector from the repository root before submitting a pull request:

```bash
export PYTHONPATH="$(pwd)/source"
python3 -m unittest discover -s tests -v
python3 tools/packet_inspector.py --self-test
