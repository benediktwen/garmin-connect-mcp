FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

COPY pyproject.toml README.md ./

COPY src/ ./src/

RUN uv pip install -e .

RUN mkdir -p /root/.garminconnect && \
    chmod 700 /root/.garminconnect

ENTRYPOINT ["garmin-mcp"]
