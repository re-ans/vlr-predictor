"""Authentication utilities: password hashing, JWT tokens, FastAPI dependency.

Uses only stdlib + PyJWT to avoid compiled-extension issues on CPython 3.14.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from ..config import settings
from ..db.base import session_scope
from ..db.models import User

_ALGORITHM = "HS256"
_HASH_ITERS = 260_000  # OWASP recommendation for PBKDF2-SHA256

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing (stdlib PBKDF2-SHA256, per-user 16-byte salt)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _HASH_ITERS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _HASH_ITERS)
    return dk == expected


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependency: returns authenticated User or raises 401
# ---------------------------------------------------------------------------

def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    with session_scope() as session:
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        # Detach from session so caller can use it outside this scope
        session.expunge(user)
        return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    """Like get_current_user but returns None instead of 401."""
    if creds is None:
        return None
    try:
        return get_current_user(creds)
    except HTTPException:
        return None
