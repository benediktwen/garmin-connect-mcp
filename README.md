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

The server requires **bearer token authentication** on every request:
```
Authorization: Bearer <MCP_SECRET>
```

Two secrets exist, each with a different purpose:

| Secret | Where | Rotates? | Purpose |
|---|---|---|---|
| `MCP_SECRET` | Render only | Never | MCP access control — set once, stays forever |
| `GARMINTOKENS_BASE64` | Render only | ~every 6 months | Garmin OAuth session |

Claude's config only ever needs `MCP_SECRET`. When `GARMINTOKENS_BASE64` rotates,
only Render needs to be updated — Claude's config stays untouched.

Unauthenticated requests receive `401 Unauthorized`.

## Setup

### Step 1 — Generate Garmin token (one-time, run locally)

```bash
~/.local/bin/uv run --python 3.12 python generate_token.py
```

Enter email, password, and MFA code. Copy the printed `GARMINTOKENS_BASE64` value.

### Step 2 — Configure Render

Render Dashboard → `garmin-health-sync` → Environment Variables:

| Variable | Value |
|---|---|
| `GARMINTOKENS_BASE64` | Output from Step 1 |
| `MCP_SECRET` | A strong random string you generate once (e.g. `openssl rand -hex 32`) |

Then: **Manual Deploy**.

### Step 3 — Configure Claude (one-time, never changes)

Add to `~/.claude.json` (global) or `.mcp.json` (project-level):

```json
{
  "mcpServers": {
    "garmin": {
      "type": "sse",
      "url": "https://garmin-health-sync.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer <MCP_SECRET>"
      }
    }
  }
}
```

Replace `<MCP_SECRET>` with the value you set in Render. **This never needs to change.**

## Token renewal (every ~6 months)

When `GARMINTOKENS_BASE64` expires:

1. Run `generate_token.py` locally
2. Update `GARMINTOKENS_BASE64` in Render → Manual Deploy

Claude's config does **not** need to be touched.

## Configuration reference

| Env var | Required | Rotates | Description |
|---|---|---|---|
| `GARMINTOKENS_BASE64` | ✅ | ~6 months | Garmin OAuth session token |
| `MCP_SECRET` | ✅ | Never | MCP bearer token for Claude access |
| `GARMIN_IS_CN` | — | — | Set `true` for Garmin Connect China |

## Architecture

- **Runtime:** Docker on Render Free tier
- **Transport:** SSE (Server-Sent Events) via FastMCP + uvicorn
- **MCP auth:** Static bearer token (`MCP_SECRET`) checked via ASGI middleware
- **Garmin auth:** OAuth via `garminconnect` ≥ 0.3.2, widget+cffi strategy
- **Library:** [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
