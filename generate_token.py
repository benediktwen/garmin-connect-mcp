"""
Garmin Connect token generator for cloud/server deployments.

Generates a GARMINTOKENS_BASE64 value that can be set as an environment
variable on any hosting platform (Render, Railway, Fly.io, etc.).

IMPORTANT: Run with uv from inside the project folder to ensure the
garminconnect version matches what the server uses on Render:

    cd /path/to/garmin-connect-mcp
    ~/.local/bin/uv run --python 3.12 python generate_token.py

The token is written to token.txt — open that file and copy its contents
into GARMINTOKENS_BASE64 on your hosting platform. Do NOT copy from the
terminal (the long base64 line wraps and gets truncated).
"""

import base64
import getpass
import os

from garminconnect import Garmin


def main() -> None:
    print("=== Garmin Connect Token Generator ===\n")
    email = input("Garmin email: ")
    password = getpass.getpass("Password: ")

    print("\nLogging in...")
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA / 2FA code: "),
    )
    client.login()

    auth = getattr(client, 'garth', None) or getattr(client, 'client', None)
    token_json = auth.dumps()
    b64 = base64.b64encode(token_json.encode()).decode()

    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
    with open(output_file, "w") as f:
        f.write(b64)

    print(f"\n✓ Token saved to: {output_file}")
    print("\nNext steps:")
    print("  1. Open token.txt")
    print("  2. Copy the entire contents (one long line)")
    print("  3. Paste into GARMINTOKENS_BASE64 on Render → Environment")
    print("  4. Trigger a Manual Deploy")
    print("\nTokens auto-refresh while the server runs regularly.")
    print("Re-run this script if the server has been offline for months.")
    print("\n⚠️  Delete token.txt after pasting — it contains sensitive credentials.")


if __name__ == "__main__":
    main()
