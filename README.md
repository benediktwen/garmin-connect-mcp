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

## Deployment (Render)

### One-time token generation

```bash
# Run locally — uses widget+cffi strategy to bypass SSO rate limiting
~/.local/bin/uv run --python 3.12 python generate_token.py
```

Enter password and MFA code when prompted. Copy the `GARMINTOKENS_BASE64` output.

### Render setup

1. Render Dashboard → `garmin-health-sync` → Environment Variables
2. Set `GARMINTOKENS_BASE64` = token from above
3. Manual Deploy

Expected logs on success:
```
Trying to login to Garmin Connect using token from environment...
Login successful using GARMINTOKENS_BASE64.
Garmin Connect client initialized successfully.
```

### Token renewal

OAuth tokens auto-refresh as long as the server runs regularly. If the server was offline for an extended period, re-run `generate_token.py` and update the Render env var.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `GARMINTOKENS_BASE64` | — | Base64-encoded OAuth token JSON (required on Render) |
| `GARMIN_IS_CN` | `false` | Set `true` for Garmin Connect China |

## Architecture

- **Runtime:** Docker on Render Free tier
- **Auth:** OAuth tokens via `garminconnect>=0.3.2`, widget+cffi strategy for rate-limit bypass
- **Library:** [python-garminconnect](https://github.com/cyberjunky/python-garminconnect)
