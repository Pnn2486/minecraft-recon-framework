#!/bin/sh
# Runs the test suite inside one Linux image, used by the linux-distros workflow
# Needs IMAGE and INSTALL, PYTHON is optional (default python3)
set -e
docker run --rm \
  -v "$PWD":/src -w /src \
  -e PYTHONPATH=source -e PYTHONDONTWRITEBYTECODE=1 \
  -e INSTALL -e PYTHON="${PYTHON:-python3}" \
  "$IMAGE" sh -c '
    set -e
    eval "$INSTALL"
    . /etc/os-release && echo "System: $PRETTY_NAME"
    "$PYTHON" --version
    "$PYTHON" -m unittest discover -s tests
    "$PYTHON" scripts/packet_inspector.py --self-test
  '
