"""
GitHub OAuth provider for FastMCP.

Flow:
  1. Claude → GET /authorize  → redirect to GitHub login
  2. GitHub → GET /auth/callback → verify username → redirect back to Claude
  3. Claude → POST /token → exchange code for access token
  4. Claude uses Bearer access token on every MCP request

Tokens are stored in memory — users re-authenticate after server restart
(happens at most once per cold start on Render Free Tier).
"""

import logging
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

ACCESS_TOKEN_TTL = 3600 * 8    # 8 hours
REFRESH_TOKEN_TTL = 3600 * 24 * 30  # 30 days
AUTH_CODE_TTL = 300            # 5 minutes (exchanged immediately)


class GitHubOAuthProvider(OAuthAuthorizationServerProvider):
    """
    MCP OAuth Authorization Server backed by GitHub as upstream identity provider.

    Only the GitHub account set in GITHUB_ALLOWED_USER (default: benediktwen)
    can complete the OAuth flow and receive an MCP access token.
    """

    def __init__(self, github_client_id: str, github_client_secret: str, server_url: str) -> None:
        self._github_client_id = github_client_id
        self._github_client_secret = github_client_secret
        self._callback_url = server_url.rstrip("/") + "/auth/callback"
        self._allowed_user = os.getenv("GITHUB_ALLOWED_USER", "benediktwen").lower()

        # In-memory stores — cleared on restart; clients simply re-authenticate
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._pending: dict[str, dict] = {}          # github_state → MCP params
        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._access_tokens: dict[str, AccessToken] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}

    # ------------------------------------------------------------------ #
    # Client registration (dynamic — Claude registers itself on first use) #
    # ------------------------------------------------------------------ #

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        logger.info("Registering OAuth client: %s", client_info.client_id)
        self._clients[client_info.client_id] = client_info

    # ------------------------------------------------------------------ #
    # Authorization: redirect user to GitHub                              #
    # ------------------------------------------------------------------ #

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        github_state = secrets.token_urlsafe(32)
        self._pending[github_state] = {
            "client_id": client.client_id,
            "code_challenge": params.code_challenge,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "scopes": params.scopes or [],
            "mcp_state": params.state,
            "resource": params.resource,
        }
        github_params = {
            "client_id": self._github_client_id,
            "redirect_uri": self._callback_url,
            "scope": "read:user",
            "state": github_state,
        }
        url = GITHUB_AUTHORIZE_URL + "?" + urlencode(github_params)
        logger.info("Redirecting to GitHub OAuth: %s", url)
        return url

    # ------------------------------------------------------------------ #
    # GitHub callback — registered as a custom FastMCP route              #
    # ------------------------------------------------------------------ #

    async def handle_github_callback(self, request: Request) -> HTMLResponse | RedirectResponse:
        code = request.query_params.get("code")
        github_state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            logger.warning("GitHub OAuth error: %s", error)
            return HTMLResponse(
                f"<h1>Authorization failed</h1><p>GitHub error: {error}</p>",
                status_code=400,
            )

        if not code or not github_state:
            return HTMLResponse(
                "<h1>Invalid callback</h1><p>Missing code or state.</p>",
                status_code=400,
            )

        pending = self._pending.pop(github_state, None)
        if not pending:
            return HTMLResponse(
                "<h1>Invalid state</h1><p>State not found or expired. Please try connecting again.</p>",
                status_code=400,
            )

        # Exchange GitHub code → GitHub access token
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.post(
                    GITHUB_TOKEN_URL,
                    data={
                        "client_id": self._github_client_id,
                        "client_secret": self._github_client_secret,
                        "code": code,
                        "redirect_uri": self._callback_url,
                    },
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                token_data = resp.json()
        except Exception as exc:
            logger.error("GitHub token exchange failed: %s", exc)
            return HTMLResponse(
                "<h1>GitHub error</h1><p>Could not exchange authorization code.</p>",
                status_code=502,
            )

        github_access_token = token_data.get("access_token")
        if not github_access_token:
            logger.error("No access_token in GitHub response: %s", token_data)
            return HTMLResponse(
                "<h1>GitHub error</h1><p>No access token received.</p>",
                status_code=502,
            )

        # Fetch GitHub user and enforce allowlist
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(
                    GITHUB_USER_URL,
                    headers={
                        "Authorization": f"Bearer {github_access_token}",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                user_data = resp.json()
        except Exception as exc:
            logger.error("GitHub user lookup failed: %s", exc)
            return HTMLResponse(
                "<h1>GitHub error</h1><p>Could not fetch user info.</p>",
                status_code=502,
            )

        github_username = user_data.get("login", "").lower()
        logger.info("GitHub OAuth: user='%s' allowed='%s'", github_username, self._allowed_user)

        if github_username != self._allowed_user:
            logger.warning("Access denied for GitHub user: %s", github_username)
            return HTMLResponse(
                f"<h1>Access Denied</h1>"
                f"<p>GitHub account <b>{user_data.get('login')}</b> is not authorized to use this server.</p>",
                status_code=403,
            )

        # Issue MCP authorization code
        mcp_code = secrets.token_urlsafe(32)
        self._auth_codes[mcp_code] = AuthorizationCode(
            code=mcp_code,
            client_id=pending["client_id"],
            scopes=pending["scopes"],
            expires_at=time.time() + AUTH_CODE_TTL,
            code_challenge=pending["code_challenge"],
            redirect_uri=pending["redirect_uri"],  # type: ignore[arg-type]
            redirect_uri_provided_explicitly=pending["redirect_uri_provided_explicitly"],
            resource=pending.get("resource"),
        )

        redirect_url = construct_redirect_uri(
            pending["redirect_uri"],
            code=mcp_code,
            state=pending.get("mcp_state"),
        )
        logger.info("GitHub OAuth complete for '%s' — redirecting to Claude", github_username)
        return RedirectResponse(redirect_url, status_code=302)

    # ------------------------------------------------------------------ #
    # Token exchange                                                       #
    # ------------------------------------------------------------------ #

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        obj = self._auth_codes.get(authorization_code)
        if obj and obj.expires_at > time.time():
            return obj
        return None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._auth_codes.pop(authorization_code.code, None)  # one-time use

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        self._access_tokens[access_token] = AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + ACCESS_TOKEN_TTL,
            resource=authorization_code.resource,
        )
        self._refresh_tokens[refresh_token] = RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self._refresh_tokens.get(refresh_token)
        if rt and (rt.expires_at is None or rt.expires_at > time.time()):
            return rt
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        self._refresh_tokens.pop(refresh_token.token, None)  # rotate

        access_token = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        effective_scopes = scopes or refresh_token.scopes

        self._access_tokens[access_token] = AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=effective_scopes,
            expires_at=int(time.time()) + ACCESS_TOKEN_TTL,
        )
        self._refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh,
            client_id=client.client_id,
            scopes=effective_scopes,
            expires_at=int(time.time()) + REFRESH_TOKEN_TTL,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=new_refresh,
            scope=" ".join(effective_scopes),
        )

    # ------------------------------------------------------------------ #
    # Token verification (called on every MCP request)                    #
    # ------------------------------------------------------------------ #

    async def load_access_token(self, token: str) -> AccessToken | None:
        at = self._access_tokens.get(token)
        if at and (at.expires_at is None or at.expires_at > time.time()):
            return at
        # Expired — clean up
        self._access_tokens.pop(token, None)
        return None

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self._access_tokens.pop(token.token, None)
        else:
            self._refresh_tokens.pop(token.token, None)
