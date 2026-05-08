import base64
import logging
import os
import sys

import anyio
import uvicorn
from garminconnect import Garmin
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

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
from garmin_mcp.github_oauth_provider import GitHubOAuthProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_cn = os.getenv("GARMIN_IS_CN", "false").lower() == "true"

SERVER_URL = "https://garmin-health-sync.onrender.com"

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


def _build_app() -> tuple[FastMCP, GitHubOAuthProvider]:
    github_client_id = os.getenv("GITHUB_CLIENT_ID", "")
    github_client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

    if not github_client_id or not github_client_secret:
        logger.error("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set.")
        sys.exit(1)

    oauth_provider = GitHubOAuthProvider(
        github_client_id=github_client_id,
        github_client_secret=github_client_secret,
        server_url=SERVER_URL,
    )

    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl(SERVER_URL),
        resource_server_url=None,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["mcp"],
            default_scopes=["mcp"],
        ),
        revocation_options=RevocationOptions(enabled=True),
    )

    mcp_app = FastMCP(
        "Garmin Health MCP Server",
        auth_server_provider=oauth_provider,
        auth=auth_settings,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
    )

    # GitHub redirects here after user login
    @mcp_app.custom_route("/auth/callback", methods=["GET"])
    async def github_callback(request):
        return await oauth_provider.handle_github_callback(request)

    return mcp_app, oauth_provider


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


async def _serve(mcp_app: FastMCP) -> None:
    starlette_app = mcp_app.sse_app()
    config = uvicorn.Config(
        starlette_app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    garmin = init_api()
    mcp_app, _ = _build_app()

    for module in _MODULES:
        module.configure(garmin)
        module.register_tools(mcp_app)

    workout_templates.register_resources(mcp_app)

    logger.info("GitHub OAuth enabled — only '%s' can authenticate.", os.getenv("GITHUB_ALLOWED_USER", "benediktwen"))
    anyio.run(_serve, mcp_app)
