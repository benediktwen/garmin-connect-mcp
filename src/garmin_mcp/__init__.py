import base64
import logging
import os
import sys

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

app = FastMCP(
    "Garmin Health MCP Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", 8000)),
)

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


def init_api() -> Garmin:
    # Primary: token JSON from env var (base64-encoded)
    b64 = os.getenv("GARMINTOKENS_BASE64")
    if b64:
        logger.info("Trying to login to Garmin Connect using token from environment...")
        token_json = base64.b64decode(b64).decode("utf-8")
        garmin = Garmin(is_cn=is_cn)
        garmin.login(token_json)  # JSON string > 512 chars → client.loads() path
        logger.info("Login successful using GARMINTOKENS_BASE64.")
        return garmin

    # Fallback: token files on disk (local dev or Render Persistent Disk)
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


def main() -> None:
    garmin = init_api()

    for module in _MODULES:
        module.configure(garmin)
        module.register_tools(app)

    workout_templates.register_resources(app)

    app.run(transport="sse")
