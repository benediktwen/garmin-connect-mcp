"""
Garmin Connect token generator for cloud/server deployments.

Generates a GARMINTOKENS_BASE64 value that can be set as an environment
variable on any hosting platform (Render, Railway, Fly.io, etc.).

Requirements:
    pip install garmin-connect-mcp   # or: uv run python generate_token.py

Usage:
    python generate_token.py

Then set the printed value as GARMINTOKENS_BASE64 in your environment and
trigger a redeploy.
"""

import base64
import getpass

from garminconnect import Garmin


def main() -> None:
    print("=== Garmin Connect Token Generator ===\n")
    email = input("Garmin email: ")
    password = getpass.getpass("Password: ")

    print("\nLogging in...")
    client = Garmin(email=email, password=password)

    try:
        client.login()
    except Exception as e:
        if any(kw in str(e).lower() for kw in ["mfa", "two", "factor", "verification", "code"]):
            mfa_code = input("MFA / 2FA code: ")
            client.login(mfa_code)
        else:
            raise

    token_json = client.garth.dumps()
    b64 = base64.b64encode(token_json.encode()).decode()

    print("\n" + "=" * 60)
    print("Set this as GARMINTOKENS_BASE64 in your environment:")
    print("=" * 60)
    print(b64)
    print("=" * 60)
    print("\nTokens auto-refresh while the server runs regularly.")
    print("Re-run this script if the server has been offline for months.")


if __name__ == "__main__":
    main()
