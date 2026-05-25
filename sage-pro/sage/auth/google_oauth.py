"""
SAGE-PRO Google OAuth2 Authentication
══════════════════════════════════════
Handles the Google OAuth2 flow:
  1. Redirect to Google consent screen
  2. Exchange auth code for ID token
  3. Verify token, upsert user, issue JWT

All secrets from environment variables:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
"""

import os
import structlog
from typing import Dict, Any, Optional

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = structlog.get_logger(__name__)

# All config from environment — zero hardcoded secrets
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


def get_google_auth_url() -> str:
    """Generates the Google OAuth2 consent screen URL.

    Returns:
        The full authorization URL to redirect the user to.
    """
    scopes = "openid email profile"
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"access_type=offline"
    )


async def exchange_code(code: str) -> Dict[str, Any]:
    """Exchanges an authorization code for a Google ID token.

    Args:
        code: The authorization code from Google's callback.

    Returns:
        Dict with user info: google_id, email, name, avatar_url.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

    # Verify the ID token
    id_info = id_token.verify_oauth2_token(
        token_data["id_token"],
        google_requests.Request(),
        GOOGLE_CLIENT_ID,
    )

    user_info = {
        "google_id": id_info["sub"],
        "email": id_info["email"],
        "name": id_info.get("name", ""),
        "avatar_url": id_info.get("picture", ""),
    }

    logger.info("google_auth_success", email=user_info["email"])
    return user_info
