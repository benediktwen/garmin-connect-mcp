import base64
import logging
import os
import sys
from typing import Any

import anyio
import uvicorn
from garminconnect import Garmin
from mcp.server.fastmcp import FastMCP

from garmin_mcp import (
    activity_management,
    challenges,
    data_management,
    devices,
    gear_management,
    health_wellness,
    nutrition,
    training,
    user_profile,
    weight_management,
    womens_health,
    workout_templates,
    workouts,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_cn = os.getenv("GARMIN_IS_CN", "false").lower() == "true"

app = FastMCP("Garmin Health MCP Server")

_MODULES = [
    activity_management,
    challenges,
    data_management,
    devices,
    gear_management,
    health_wellness,
    nutrition,
    training,
    user_profile,
    weight_management,
    womens_health,
    workouts,
]


class _BearerAuthMiddleware:
    """ASGI middleware: blocks all requests without a valid bearer token.

    Uses MCP_SECRET — a permanent, never-rotating secret stored in Render.
    Separate from GARMINTOKENS_BASE64 so that Garmin token renewal never
    requires updating Claude's MCP configuration.
    """

    def __init__(self, asgi_app: Any) -> None:
        self._app = asgi_app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            expected = os.getenv("MCP_SECRET", "")
            if expected:
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()
                if auth != f"Bearer {expected}":
                    if scope["type"] == "http":
                        body = b"Unauthorized"
                        await send({
                            "type": "http.response.start",
                            "status": 401,
                            "headers": [
                                [b"content-type", b"text/plain"],
                                [b"content-length", str(len(body)).encode()],
                            ],
                        })
                        await send({"type": "http.response.body", "body": body})
                    return
        await self._app(scope, receive, send)


def init_api() -> Garmin:
    b64 = os.getenv("GARMINTOKENS_BASE64")
    if b64:
        logger.info("Trying to login to Garmin Connect using token from environment...")
        token_json = base64.b64decode(b64).decode("utf-8")
        garmin = Garmin(is_cn=is_cn)
        garmin.login(token_json)
        logger.info("Login successful using GARMINTOKENS_BASE64.")
        return garmin

    local = os.path.expanduser("~/.garminconnect")
    if os.path.isdir(local):
        logger.info("Using local token files from %s", local)
        garmin = Garmin(is_cn=is_cn)
        garmin.login(local)
        logger.info("Garmin Connect client initialized successfully.")
        return garmin

    logger.error(
        "No Garmin credentials found. "
        "Set GARMINTOKENS_BASE64 in Render Environment Variables."
    )
    sys.exit(1)


async def _serve() -> None:
    starlette_app = app.sse_app()
    protected_app = _BearerAuthMiddleware(starlette_app)
    config = uvicorn.Config(
        protected_app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    garmin = init_api()

    for module in _MODULES:
        module.configure(garmin)
        module.register_tools(app)

    workout_templates.register_resources(app)

    if not os.getenv("MCP_SECRET"):
        logger.warning("MCP_SECRET not set — server is publicly accessible!")
    else:
        logger.info("Bearer token auth enabled via MCP_SECRET.")
    anyio.run(_serve)
