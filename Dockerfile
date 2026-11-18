FROM python:3.12-slim

# Debian security fixes that the base image does not carry yet (e.g. zlib1g
# CVE-2026-85091 on 2026-11-18). The deploy passes the current week as
# APT_REFRESH, so this layer is rebuilt once a week instead of staying cached.
ARG APT_REFRESH=none
RUN echo "apt refresh: ${APT_REFRESH}" \
 && apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user. The bind-mounted /state (token store) must be
# writable by this UID on the host; it defaults to 1000, the first user on Ubuntu.
# Override at build time if your host differs (the server uses 1001):
#   docker compose build --build-arg APP_UID=$(id -u) garmin-connect-mcp
ARG APP_UID=1000
ARG APP_GID=1000

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Dependencies come from uv.lock (exact versions, checked by hash), not from
# whatever is newest on the day of the build.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --require-hashes -r /tmp/requirements.txt \
 && uv pip install --system --no-cache --no-deps . \
 && rm /tmp/requirements.txt

# The app user gets a real home: the Garmin token directory lives in ~/.garminconnect.
RUN groupadd --gid "${APP_GID}" app \
 && useradd --uid "${APP_UID}" --gid app --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
 && mkdir -p /home/app/.garminconnect /state \
 && chmod 700 /home/app/.garminconnect \
 && chown -R app:app /home/app /state

USER app

ENTRYPOINT ["garmin-mcp"]
