"""Auth: JWT tokens, password hashing, FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.hash import bcrypt
from pydantic import BaseModel

from app.core.config import settings
from app.core.db import get_supabase
from app.core.logging import get_logger

log = get_logger(__name__)

# FastAPI security scheme for Bearer token
security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Decoded JWT payload — injected into route handlers via Depends(get_current_user)."""
    user_id: str
    org_id: str
    role: str  # owner | member | platform_admin


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.verify(plain, hashed)


def create_access_token(user_id: str, org_id: str, role: str) -> str:
    """Create a JWT access token with user_id, org_id, role."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET not configured — cannot issue tokens")

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises jwt exceptions on invalid/expired."""
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET not configured")

    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    """FastAPI dependency: extract + verify JWT from Authorization: Bearer header.

    Returns CurrentUser with user_id, org_id, role.
    Raises 401 if token missing/invalid/expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        log.warning(f"Invalid JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    org_id = payload.get("org_id")
    role = payload.get("role")

    if not user_id or not org_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )

    return CurrentUser(user_id=user_id, org_id=org_id, role=role)


async def require_platform_admin(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency: require platform_admin role.

    Use this on /admin/* routes to gate access to global credentials.
    """
    if current.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return current


def authenticate_ws(token: str) -> CurrentUser:
    """Authenticate a WebSocket connection via query param token.

    Raises HTTPException on invalid token (caller should close WS).
    """
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    org_id = payload.get("org_id")
    role = payload.get("role")

    if not user_id or not org_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    return CurrentUser(user_id=user_id, org_id=org_id, role=role)
