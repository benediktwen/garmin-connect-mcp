# Garmin Health MCP Server

Remote MCP server for Garmin Connect health data, deployed on Render.
Based on [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) (MIT).

## What it does

Exposes 96+ Garmin Connect tools via MCP so Claude can query health data directly:

- Health & Wellness: sleep, HRV, stress, body battery, heart rate, SpO2, respiration
- Activities: runs, rides, swims — with splits, weather, HR zones
- Training: readiness, status, VO2max, load
- Body composition, weight, hydration
- Workouts, gear, nutrition, challenges

## Security

Access is protected by **GitHub OAuth** — only the configured GitHub account
(`benediktwen`) can authenticate. Every MCP session requires a fresh GitHub login
with 2FA (Authy). No shared secrets are stored in Claude's config.

### How the OAuth flow works

```
Claude → /authorize → GitHub login (+ 2FA) → /auth/callback
       → username verified → MCP access token issued → SSE connection
```

1. Claude detects the MCP server requires OAuth
2. Browser opens — user logs in to GitHub with 2FA
3. Server verifies the GitHub username matches `GITHUB_ALLOWED_USER`
4. Claude receives a time-limited access token (8 h) with silent refresh (30 days)

### Environment variables

| Variable | Where set | Rotates? | Purpose |
|---|---|---|---|
| `GARMINTOKENS_BASE64` | Render only | ~6 months | Garmin OAuth session |
| `GITHUB_CLIENT_ID` | Render only | Never | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | Render only | Never | GitHub OAuth App client secret |
| `GITHUB_ALLOWED_USER` | render.yaml | Never | GitHub username allowed to connect |

## Setup

### Step 1 — GitHub OAuth App (one-time)

Already created: **Claude MCP Servers** (`Ov23liJvwWff3lXGxbF7`)

Callback URL set to: `https://garmin-health-sync.onrender.com/auth/callback`

To add the broker MCP later: add its callback URL in the same OAuth App.

### Step 2 — Configure Render

Render Dashboard → `garmin-health-sync` → Environment Variables:

| Variable | Value |
|---|---|
| `GARMINTOKENS_BASE64` | Output from `generate_token.py` |
| `GITHUB_CLIENT_ID` | `Ov23liJvwWff3lXGxbF7` |
| `GITHUB_CLIENT_SECRET` | *(from GitHub OAuth App settings)* |

`GITHUB_ALLOWED_USER` is set to `benediktwen` via `render.yaml` — no manual entry needed.

Then: **Manual Deploy**.

### Step 3 — Configure Claude (one-time, never changes)

**Claude.ai web** (connector dialog):
- URL: `https://garmin-health-sync.onrender.com/sse`
- OAuth fields: leave empty — the server advertises its own OAuth metadata

Claude Desktop and iPhone sync automatically from the web connector.

### Step 4 — First connection

1. Click Connect in Claude
2. Browser opens → GitHub login → 2FA with Authy
3. Access granted — token valid for 8 hours, refreshes silently for 30 days

## Garmin token renewal (~every 6 months)

When `GARMINTOKENS_BASE64` expires:

1. Run `generate_token.py` locally
2. Update `GARMINTOKENS_BASE64` in Render → Manual Deploy

Claude's config and GitHub OAuth are **not** affected.

```bash
~/.local/bin/uv run --python 3.12 python generate_token.py
```

## Configuration reference

| Env var | Required | Rotates | Description |
|---|---|---|---|
| `GARMINTOKENS_BASE64` | ✅ | ~6 months | Garmin OAuth session token |
| `GITHUB_CLIENT_ID` | ✅ | Never | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | ✅ | Never | GitHub OAuth App client secret |
| `GITHUB_ALLOWED_USER` | ✅ | Never | GitHub username allowed to connect (in render.yaml) |
| `GARMIN_IS_CN` | — | — | Set `true` for Garmin Connect China |

## Architecture

- **Runtime:** Docker on Render Free tier
- **Transport:** SSE (Server-Sent Events) via FastMCP + uvicorn
- **MCP auth:** GitHub OAuth 2.0 — server acts as Authorization Server, GitHub as Identity Provider
- **User restriction:** GitHub username verified against `GITHUB_ALLOWED_USER` on every login
- **Token lifetime:** 8 h access token, 30-day refresh token (rotated on each refresh)
- **Garmin auth:** OAuth via `garminconnect` ≥ 0.3.2, widget+cffi strategy
- **Library:** [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)

## Shared GitHub OAuth App (synergy with broker MCP)

The same GitHub OAuth App (`Claude MCP Servers`) can serve multiple MCP servers.
When the broker MCP is deployed, add its callback URL in the GitHub OAuth App settings:

```
https://garmin-health-sync.onrender.com/auth/callback   ← already set
https://broker-mcp.onrender.com/auth/callback           ← add later
```

Each server issues its own independent access tokens. One GitHub login covers both.
