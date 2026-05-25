"""
SAGE-PRO Authentication API Routes
════════════════════════════════════
Google OAuth2 login, JWT session management, user profile retrieval.

Endpoints:
    GET  /auth/google          — Redirect to Google consent screen
    GET  /auth/google/callback — Exchange auth code, issue JWT
    POST /auth/logout          — Invalidate session (client-side)
    GET  /auth/me              — Return current user profile from JWT
"""

import os
import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from sage.auth.google_oauth import get_google_auth_url, exchange_code
from sage.auth.session_manager import create_token, verify_token

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_login():
    """Redirects to Google consent screen."""
    auth_url = get_google_auth_url()
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(code: str, response: Response):
    """Exchanges Google auth code for user info, issues JWT.

    Args:
        code: The authorization code from Google.
        response: FastAPI response to set cookie.

    Returns:
        User profile + JWT token.
    """
    try:
        user_info = await exchange_code(code)
    except Exception as e:
        logger.error("google_auth_failed", error=str(e))
        raise HTTPException(status_code=401, detail=f"Google auth failed: {e}")

    # In production, upsert user into DB here
    # For now, issue JWT from the Google profile
    token = create_token(
        user_id=user_info["google_id"],
        email=user_info["email"],
    )

    return {
        "token": token,
        "user": user_info,
    }


@router.post("/logout")
async def logout():
    """Invalidates session — JWT is stateless so client discards token."""
    return {"status": "logged_out"}


@router.get("/me")
async def get_current_user(request: Request):
    """Returns current user profile from JWT.

    Reads the Authorization: Bearer <token> header.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.split("Bearer ", 1)[1]
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
    }
