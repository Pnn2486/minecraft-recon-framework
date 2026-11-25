FROM python:3.12-alpine

LABEL org.opencontainers.image.title="minecraft-recon-framework" \
      org.opencontainers.image.description="Zero-dependency Minecraft network reconnaissance and administration framework" \
      org.opencontainers.image.licenses="LicenseRef-Authorized-Use"

WORKDIR /app

COPY pyproject.toml README.md LICENSE COPYING.md settings.ini /app/
COPY source/ /app/source/
COPY launchers/ /app/launchers/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/

ENV PYTHONPATH=/app/source \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python3 -m unittest discover -s tests && \
    python3 scripts/packet_inspector.py --self-test

ENTRYPOINT ["python3", "-m", "recon.cli"]
CMD ["--help"]
