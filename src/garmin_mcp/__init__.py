"""
Modular MCP Server for Garmin Connect Data
"""

import os
import sys

import requests
from mcp.server.fastmcp import FastMCP

from garth.exc import GarthHTTPError
from garminconnect import Garmin, GarminConnectAuthenticationError

# Import all modules
from garmin_mcp import activity_management
from garmin_mcp import health_wellness
from garmin_mcp import user_profile
from garmin_mcp import devices
from garmin_mcp import gear_management
from garmin_mcp import weight_management
from garmin_mcp import challenges
from garmin_mcp import training
from garmin_mcp import workouts
from garmin_mcp import workout_templates
from garmin_mcp import data_management
from garmin_mcp import womens_health
from garmin_mcp import nutrition


def is_interactive_terminal() -> bool:
    """Detect if running in interactive terminal vs MCP subprocess."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def get_mfa() -> str:
    """Get MFA code from user input."""
    if not is_interactive_terminal():
        print(
            "\nERROR: MFA code required but no interactive terminal available.\n"
            "Please run 'garmin-mcp-auth' in your terminal first.\n"
            "See: https://github.com/Taxuspt/garmin_mcp#mfa-setup\n",
            file=sys.stderr,
        )
        raise RuntimeError("MFA required but non-interactive environment")

    print(
        "\nGarmin Connect MFA required. Please check your email/phone for the code.",
        file=sys.stderr,
    )
    return input("Enter MFA code: ")


tokenstore = os.getenv("GARMINTOKENS") or "~/.garminconnect"
is_cn = os.getenv("GARMIN_IS_CN", "false").lower() in ("true", "1", "yes")


def init_api():
    """Initialize Garmin API — uses GARMINTOKENS_BASE64 env var (primary)
    or token files from GARMINTOKENS directory (fallback)."""
    import io

    try:
        # PRIMARY: Base64 token from environment variable
        base64_token = os.getenv("GARMINTOKENS_BASE64")
        if base64_token:
            print(
                "Trying to login to Garmin Connect using base64 token from environment...\n",
                file=sys.stderr,
            )
            garmin = Garmin(is_cn=is_cn)
            garmin.login(base64_token)
            print("Login successful using base64 token.\n", file=sys.stderr)
            return garmin

        # FALLBACK: Token files from directory
        print(
            f"No base64 token found, trying token files from '{tokenstore}'...\n",
            file=sys.stderr,
        )

        # Suppress stderr for token validation to avoid confusing library errors
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            garmin = Garmin(is_cn=is_cn)
            garmin.login(tokenstore)
        finally:
            sys.stderr = old_stderr

        print("Login successful using token files.\n", file=sys.stderr)
        return garmin

    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        # No valid tokens found — server cannot start without credentials
        print(
            "ERROR: No valid OAuth tokens found.\n"
            "Please authenticate first:\n"
            "  1. Run: garmin-mcp-auth\n"
            "  2. Enter your credentials and MFA code\n"
            "  3. Copy output of: cat ~/.garminconnect_base64\n"
            "  4. Set GARMINTOKENS_BASE64 environment variable in Render\n"
            "  5. Redeploy\n",
            file=sys.stderr,
        )
        return None


def main():
    """Initialize the MCP server and register all tools"""

    # Initialize Garmin client
    garmin_client = init_api()
    if not garmin_client:
        print("Failed to initialize Garmin Connect client. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("Garmin Connect client initialized successfully.", file=sys.stderr)

    # Configure all modules with the Garmin client
    activity_management.configure(garmin_client)
    health_wellness.configure(garmin_client)
    user_profile.configure(garmin_client)
    devices.configure(garmin_client)
    gear_management.configure(garmin_client)
    weight_management.configure(garmin_client)
    challenges.configure(garmin_client)
    training.configure(garmin_client)
    workouts.configure(garmin_client)
    data_management.configure(garmin_client)
    womens_health.configure(garmin_client)
    nutrition.configure(garmin_client)

    # Create the MCP app
    app = FastMCP("Garmin Connect v1.0")

    # Register tools from all modules
    app = activity_management.register_tools(app)
    app = health_wellness.register_tools(app)
    app = user_profile.register_tools(app)
    app = devices.register_tools(app)
    app = gear_management.register_tools(app)
    app = weight_management.register_tools(app)
    app = challenges.register_tools(app)
    app = training.register_tools(app)
    app = workouts.register_tools(app)
    app = data_management.register_tools(app)
    app = womens_health.register_tools(app)
    app = nutrition.register_tools(app)

    # Register resources (workout templates)
    app = workout_templates.register_resources(app)

    # Run the MCP server
    app.run()


if __name__ == "__main__":
    main()
