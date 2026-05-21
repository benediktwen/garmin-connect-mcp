# Garmin Connect MCP

Remote MCP server for Garmin Connect data. Connects Claude to your Garmin account
over the internet — no local server required.

Built on top of [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) (MIT)
and [cyberjunky/python-garminconnect](https://github.com/cyberjunky/python-garminconnect).

## What makes this different from taxuspt/garmin_mcp

taxuspt's server runs locally on your machine and is accessed by a local Claude
Desktop client. This version is deployed as a remote HTTPS service, protected by
GitHub OAuth, so it works from Claude.ai web, Claude mobile, and any MCP-compatible
client — without running anything locally.

## What it does

Exposes 96+ Garmin Connect tools via MCP so Claude can query health data directly:

- Health & Wellness: sleep, HRV, stress, body battery, heart rate, SpO2, respiration
- Activities: runs, rides, swims — with splits, weather, HR zones
- Training: readiness, status, VO2max, load
- Body composition, weight, hydration
- Workouts, gear, nutrition, challenges

## How it works

```
Claude → /authorize → GitHub login (+ 2FA) → /auth/callback
       → username verified → MCP access token issued → MCP connection
```

Access is protected by **GitHub OAuth** — only the GitHub account set in
`GITHUB_ALLOWED_USER` can authenticate. Every session requires a fresh GitHub
login with 2FA. No shared secrets are stored in Claude's config.

1. Claude detects the MCP server requires OAuth
2. Browser opens — user logs in to GitHub with 2FA
3. Server verifies the GitHub username matches `GITHUB_ALLOWED_USER`
4. Claude receives a time-limited access token (8 h) with silent refresh (30 days)

> **Cold start note:** If the hosting platform sleeps the container, the first
> request after wake-up takes a few seconds. OAuth tokens are persisted to
> a Redis-compatible store so Claude does **not** need to re-authenticate.
> The `_pending` OAuth state is in-memory only — if a cold start happens
> mid-login flow, just click Connect again.

## Deploy your own

You will need:

- A container hosting platform (e.g. Render, Railway, Fly.io)
- A Redis-compatible key-value store for token persistence (e.g. Upstash, Redis Cloud)
- A GitHub OAuth App for authentication

### Step 1 — Redis store

Create a Redis database on your preferred provider. Note the **REST URL** and
**auth token** (or connection string, depending on provider).

### Step 2 — GitHub OAuth App (one-time)

Create a GitHub OAuth App at **Settings → Developer settings → OAuth Apps**:

- **Application name:** anything (e.g. `My MCP Servers`)
- **Homepage URL:** `https://your-service-url`
- **Callback URL:** `https://your-service-url/auth/callback`

Note the **Client ID** and generate a **Client Secret**.

> Running multiple MCP services? You can reuse one GitHub OAuth App by adding
> each service's callback URL under **Add Callback URL** in the app settings.

### Step 3 — Garmin token

Run `generate_token.py` locally to obtain your `GARMINTOKENS_BASE64`:

```bash
~/.local/bin/uv run --python 3.12 python generate_token.py
```

### Step 4 — Deploy

1. Fork this repo
2. Deploy to your container hosting platform (a `render.yaml` is included for Render)
3. Set the environment variables listed below
4. Trigger a deploy

### Step 5 — Configure Claude

In Claude.ai web (connector dialog):
- **URL:** `https://your-service-url/mcp`
- OAuth fields: leave empty — the server advertises its own OAuth metadata

Claude Desktop and mobile sync automatically from the web connector.

## Configuration reference

| Env var | Required | Rotates | Description |
|---|---|---|---|
| `GARMINTOKENS_BASE64` | ✅ | ~6 months | Garmin OAuth session token (from `generate_token.py`) |
| `GITHUB_CLIENT_ID` | ✅ | Never | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | Never | GitHub OAuth App client secret |
| `GITHUB_ALLOWED_USER` | ✅ | Never | GitHub username allowed to connect |
| `SERVER_URL` | ✅ | Never | Public base URL of this service |
| `UPSTASH_REDIS_REST_URL` | ✅ | Never | Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | ✅ | Never | Redis auth token |
| `GARMIN_IS_CN` | — | — | Set `true` for Garmin Connect China |

## Garmin token renewal (~every 6 months)

When `GARMINTOKENS_BASE64` expires:

1. Run `generate_token.py` locally
2. Update `GARMINTOKENS_BASE64` in your hosting platform → redeploy

Claude's config and GitHub OAuth are **not** affected.

## Architecture

- **Transport:** Streamable HTTP (MCP 1.x) via FastMCP + uvicorn
- **Auth:** GitHub OAuth 2.0 — server acts as Authorization Server, GitHub as Identity Provider
- **User restriction:** GitHub username verified against `GITHUB_ALLOWED_USER` on every login
- **Token lifetime:** 8 h access token, 30-day refresh token (rotated on each refresh)
- **Token persistence:** Redis-compatible store — tokens survive container restarts
- **Garmin auth:** OAuth via `garminconnect` ≥ 0.3.2, widget+cffi strategy
