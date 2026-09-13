"""
Google OAuth Service using Authlib.
"""

from __future__ import annotations

import logging
from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth2Client

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = "openid email profile"


def get_oauth_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=GOOGLE_REDIRECT_URI,
        scope=SCOPES,
    )


def get_authorization_url() -> tuple[str, str]:
    """
    Build the Google authorization URL.
    Returns (url, state) — state must be stored in session to prevent CSRF.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth credentials are not configured.")
    client = get_oauth_client()
    url, state = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        access_type="online",
        prompt="select_account",
    )
    return url, state


async def exchange_code_for_user(
    code: str,
    state: str,
    expected_state: str,
) -> dict[str, Any] | None:
    """
    Exchange the authorization code for user info.
    Returns dict with 'sub', 'email', 'name', 'picture' or None on failure.
    """
    if state != expected_state:
        logger.warning("OAuth state mismatch — possible CSRF.")
        return None

    try:
        client = get_oauth_client()
        token = await client.fetch_token(
            GOOGLE_TOKEN_URL,
            code=code,
            grant_type="authorization_code",
        )
        resp = await client.get(GOOGLE_USERINFO)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Google OAuth exchange failed: %s", exc)
        return None
