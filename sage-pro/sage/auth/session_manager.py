"""
SAGE-PRO Session Manager
═════════════════════════
JWT issue / verify / refresh.
Secret and expiry from environment variables:
  JWT_SECRET, JWT_EXPIRE_HOURS
"""

import os
import time
import structlog
from typing import Dict, Any, Optional

from jose import jwt, JWTError

logger = structlog.get_logger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production-64-byte-hex")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))


def create_token(user_id: str, email: str) -> str:
    """Issues a signed JWT for a user.

    Args:
        user_id: The user's UUID.
        email: The user's email.

    Returns:
        The signed JWT string.
    """
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + (JWT_EXPIRE_HOURS * 3600),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.info("jwt_issued", user_id=user_id)
    return token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies and decodes a JWT.

    Args:
        token: The JWT string from the Authorization header.

    Returns:
        The decoded payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("jwt_verification_failed", error=str(e))
        return None


def refresh_token(token: str) -> Optional[str]:
    """Refreshes a JWT if it's still valid.

    Args:
        token: The existing JWT string.

    Returns:
        A new JWT with extended expiry, or None if the original is invalid.
    """
    payload = verify_token(token)
    if payload is None:
        return None

    return create_token(payload["sub"], payload["email"])
