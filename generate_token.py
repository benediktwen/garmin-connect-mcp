"""
One-time token generation script — run this locally, never on Render.

Steps:
1. cd ~/Drives/Claude\ local/garmin-connect-mcp
2. ~/.local/bin/uv run --python 3.12 python generate_token.py
3. Enter email and password (MFA code prompted separately if needed)
4. Copy the printed GARMINTOKENS_BASE64 value
5. Paste it into Render → Environment Variables → GARMINTOKENS_BASE64
6. Trigger a Manual Deploy in Render
"""

import base64
import getpass

from garminconnect import Garmin


def main() -> None:
    print("=== Garmin Token Generator ===\n")
    email = input("Garmin email: ")
    password = getpass.getpass(f"Password for {email}: ")

    print("\nLogging in...")
    client = Garmin(email=email, password=password)

    try:
        client.login()
    except Exception as e:
        if any(kw in str(e).lower() for kw in ["mfa", "two", "factor", "verification", "code"]):
            mfa_code = input("MFA/2FA code: ")
            client.login(mfa_code)
        else:
            raise

    token_json = client.client.dumps()
    b64 = base64.b64encode(token_json.encode()).decode()

    print("\n" + "=" * 60)
    print("GARMINTOKENS_BASE64 (copy this to Render):")
    print("=" * 60)
    print(b64)
    print("=" * 60)
    print("\nTokens auto-refresh as long as the server runs regularly.")
    print("If the server was offline for months, re-run this script.")


if __name__ == "__main__":
    main()
