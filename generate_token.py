"""
One-time token generation script — run this locally, never on Render.

Uses the widget+cffi login strategy which bypasses Garmin's SSO rate limiting
by taking a different auth path (no clientId parameter → different rate-limit bucket).

Steps:
1. ~/.local/bin/uv run --python 3.12 python generate_token.py
2. Enter email, password and MFA code when prompted
3. Copy the printed GARMINTOKENS_BASE64 value
4. Paste it into Render → Environment Variables → GARMINTOKENS_BASE64
5. Trigger a Manual Deploy in Render
"""

import base64
import getpass

from garminconnect import Garmin


def main() -> None:
    print("=== Garmin Token Generator (widget bypass) ===\n")
    email = input("Garmin email: ")
    password = getpass.getpass(f"Password for {email}: ")

    print("\nLogging in (auto-cascades through all strategies, reaches widget+cffi if rate-limited)...")
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("MFA code: "),
    )
    client.login()

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
