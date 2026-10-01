# Garmin Connect MCP

Remote MCP server for Garmin Connect. Gives AI assistants access to your Garmin health and activity data over the internet — no local server or app required.

Built on top of [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) and [cyberjunky/python-garminconnect](https://github.com/cyberjunky/python-garminconnect).

## What makes this different from Taxuspt/garmin_mcp

Taxuspt's original server runs locally on your machine and requires a locally installed AI desktop client. This version runs as a cloud service, protected by GitHub OAuth, so it works from any MCP-compatible AI assistant on any device — without running anything locally.

## What it does

Exposes 96+ Garmin Connect tools so AI assistants can query your health data directly:

- Health & Wellness: sleep, HRV, stress, body battery, heart rate, SpO2, respiration
- Activities: runs, rides, swims — with splits, weather, HR zones
- Training: readiness, status, VO2max, load
- Body composition, weight, hydration
- Workouts, gear, nutrition, challenges

## How it works

```
AI assistant → /authorize → GitHub login (+ 2FA) → /auth/callback
             → username verified → MCP access token issued → MCP connection
```

Access is protected by **GitHub OAuth** — only the GitHub account set in
`GITHUB_ALLOWED_USER_ID` can authenticate. GitHub login with 2FA is required
once every 30 days; tokens are persisted to a token store (file or Redis). No credentials are stored
in the AI assistant's configuration.

1. The AI assistant detects the MCP server requires OAuth
2. A browser window opens — you log in to GitHub with 2FA
3. The server verifies your GitHub account matches `GITHUB_ALLOWED_USER_ID`
4. The AI assistant receives a 30-day access token and a 30-day refresh token

> **Restart note:** OAuth tokens are persisted to the token store, so
> the AI assistant does **not** need to re-authenticate after a container
> restart. The `_pending` OAuth state is in-memory only — if the container
> restarts mid-login flow, just click Connect again.

## Deploy your own

You will need:

- A Docker host reachable over HTTPS (any VPS or container platform)
- Persistent storage for OAuth tokens: a mounted volume (recommended on your own
  server) or, on platforms without persistent disks, an Upstash Redis database
- A GitHub OAuth App for authentication

### Step 1 — Token store

On a server with persistent storage, set `TOKEN_STORE_FILE` to a path inside a
mounted volume (e.g. `/state/token_store.json`). The file is written atomically
with owner-only permissions — keep the volume outside any git checkout, it
contains live access tokens.

On platforms without persistent disks, create an Upstash Redis database instead
and note its **REST URL** and **REST token**. Free databases may be deleted after
a period of inactivity — prefer the file store when you can.

### Step 2 — GitHub OAuth App (one-time)

Create a GitHub OAuth App at **Settings → Developer settings → OAuth Apps**:

- **Application name:** anything (e.g. `My MCP Servers`)
- **Homepage URL:** `https://your-service-url`
- **Callback URL:** `https://your-service-url/auth/callback`

Note the **Client ID** and generate a **Client Secret**.

### Step 3 — Garmin token

Run `generate_token.py` locally to obtain your Garmin token.

> **Important:** You must run this from inside the project folder, and you must
> use `uv run` — not `python3`. `uv run` uses the project's own virtual
> environment, which installs the exact same library versions as your deployment.
> Using `python3` directly may use a different version on your machine, producing
> a token format the server can't read.

```bash
cd /path/to/garmin-connect-mcp   # must be in this folder
~/.local/bin/uv run --python 3.12 python generate_token.py
```

The script will prompt for your Garmin email, password, and MFA code. On
success it writes the base64-encoded token to **`token.txt`** in the project
folder — do not copy from the terminal (the long base64 string wraps and truncates).

Then provide the token to the server in one of two ways:

- **Token directory (recommended):** decode it into a file named
  `garmin_tokens.json` and mount its directory into the container at
  `/root/.garminconnect`. `garminconnect` writes refreshed tokens back to this
  file, so the session survives restarts.
  ```bash
  mkdir -p ./garmin-tokens && base64 -d < token.txt > ./garmin-tokens/garmin_tokens.json
  ```
- **Environment variable:** paste the contents of `token.txt` into
  `GARMINTOKENS_BASE64`. Simpler, but refreshed tokens are not persisted —
  after a restart the server falls back to the original token.

Delete `token.txt` afterwards — it contains your Garmin session.

### Step 4 — Deploy

1. Fork this repo
2. Build and run the Docker image, e.g.
   ```bash
   docker build -t garmin-connect-mcp .
   docker run -d --env-file .env -p 8000:8000 \
     -v "$PWD/garmin-tokens:/root/.garminconnect" \
     -v "$PWD/state:/state" -e TOKEN_STORE_FILE=/state/token_store.json \
     garmin-connect-mcp
   ```
3. Put it behind an HTTPS reverse proxy and set `SERVER_URL` to the public URL
4. Set the environment variables listed below (in `.env` — never commit it)

### Step 5 — Connect to your AI assistant

In your MCP-compatible AI assistant, add this server as a remote MCP connection:

- **URL:** `https://your-service-url/mcp`
- Authentication: leave empty — the server handles OAuth automatically

**For Claude:** paste the URL into the connector dialog at [claude.ai](https://claude.ai). Claude Desktop and mobile sync automatically from the web connector.

## Configuration reference

| Env var | Required | Rotates | Description |
|---|---|---|---|
| `GARMINTOKENS_BASE64` | — | ~90 days | Garmin session token (from `generate_token.py`); not needed when a token directory is mounted |
| `GITHUB_CLIENT_ID` | ✅ | Never | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | Never | GitHub OAuth App client secret |
| `GITHUB_ALLOWED_USER_ID` | ✅ | Never | Immutable numeric GitHub user ID allowed to connect (preferred) |
| `GITHUB_ALLOWED_USER` | — | Never | GitHub username — legacy fallback, used only if `GITHUB_ALLOWED_USER_ID` is unset |
| `SERVER_URL` | ✅ | Never | Public base URL of this service |
| `TOKEN_STORE_FILE` | ✅* | Never | Path of the OAuth token store file (in a mounted volume); takes precedence over Redis |
| `UPSTASH_REDIS_REST_URL` | ✅* | Never | Upstash Redis REST endpoint (alternative to `TOKEN_STORE_FILE`) |
| `UPSTASH_REDIS_REST_TOKEN` | ✅* | Never | Upstash Redis REST token |
| `TOKEN_STORE_KEY` | — | Never | Redis key for the OAuth token store (default `mcp:garmin:token_store`) |
| `PORT` | — | Never | Listen port inside the container (default `8000`) |
| `GARMIN_IS_CN` | — | — | Set `true` for Garmin Connect China |

\* Set either `TOKEN_STORE_FILE` or both Upstash variables. Without either, tokens
are kept in memory only and every restart requires reconnecting the AI assistant.

## Garmin token renewal (~every 90 days)

The server logs the exact token expiry date at every startup. Check the
container logs (`docker logs <container>`) for lines like:

```
Garmin refresh token valid until 2026-08-15 (84 days).
Garmin refresh token expires in 12 day(s) on 2026-06-03 — regenerate GARMINTOKENS_BASE64 soon.
Garmin refresh token has EXPIRED — all API calls will fail. Regenerate GARMINTOKENS_BASE64.
```

When the token needs renewal:

```bash
cd /path/to/garmin-connect-mcp   # must be in this folder
~/.local/bin/uv run --python 3.12 python generate_token.py
```

1. Replace the token the same way you provided it in Step 3 (token directory or
   `GARMINTOKENS_BASE64`)
2. Restart the container (`docker restart <container>`; if you changed `.env`,
   recreate it — a plain restart does not re-read env files with Docker Compose)
3. Delete `token.txt`

Your AI assistant's configuration and GitHub OAuth are **not** affected.

## Architecture

- **Transport:** Streamable HTTP (MCP 1.x) via FastMCP + uvicorn
- **Auth:** GitHub OAuth 2.0 — server acts as Authorization Server, GitHub as Identity Provider
- **User restriction:** GitHub user ID verified against `GITHUB_ALLOWED_USER_ID` on every login (immutable; `GITHUB_ALLOWED_USER` is a legacy username fallback)
- **Token lifetime:** 30-day access token, 30-day refresh token (rotated on each refresh)
- **Token persistence:** `TOKEN_STORE_FILE` (atomic, 0600) or Upstash Redis — tokens survive container restarts
- **Garmin auth:** OAuth via `garminconnect` (pinned in `pyproject.toml` — the
  token format can change between releases, so upgrade deliberately and generate
  tokens with the same version)

## Contributing

This code was built with AI assistance ([Claude Code](https://claude.ai/code)) — vibe-coded with the best intentions. Security has been a priority throughout, but the code has not been independently audited. Use it at your own risk. If you spot a bug, a vulnerability, or an opportunity to improve anything, issues and pull requests are very welcome.

## Credits

- [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) — original local MCP server this remote version was adapted from (MIT)
- [cyberjunky/python-garminconnect](https://github.com/cyberjunky/python-garminconnect) — Python library powering Garmin Connect API access
- Built with [Claude Code](https://claude.ai/code)
