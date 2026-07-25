"""Auth routes: register, login, /me."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.core.db import get_supabase
from app.core.logging import get_logger
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

log = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> TokenResponse:
    """Register a new org + owner user. Self-serve MVP — can gate later."""
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled for this deployment",
        )
    sb = get_supabase()

    # Check if email already exists
    existing = sb.table("users").select("id").eq("email", payload.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create org
    org_row = {"name": payload.org_name}
    org_result = sb.table("orgs").insert(org_row).execute()
    if not org_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )
    org = org_result.data[0]

    # Create owner user
    user_row = {
        "org_id": org["id"],
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "role": "owner",
    }
    user_result = sb.table("users").insert(user_row).execute()
    if not user_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )
    user = user_result.data[0]

    # Issue JWT
    token = create_access_token(user["id"], user["org_id"], user["role"])

    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user["id"],
            email=user["email"],
            org_id=user["org_id"],
            org_name=org["name"],
            role=user["role"],
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    """Login with email + password → return JWT."""
    sb = get_supabase()

    # Fetch user + org in one query (join)
    result = (
        sb.table("users")
        .select("id, email, password_hash, org_id, role, orgs(name)")
        .eq("email", payload.email)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = result.data
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Issue JWT
    token = create_access_token(user["id"], user["org_id"], user["role"])

    # Extract org name from join (Supabase returns nested dict)
    org_name = None
    if user.get("orgs") and isinstance(user["orgs"], dict):
        org_name = user["orgs"].get("name")

    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user["id"],
            email=user["email"],
            org_id=user["org_id"],
            org_name=org_name,
            role=user["role"],
        ),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current: CurrentUser = Depends(get_current_user)) -> UserOut:
    """Get current user info from JWT."""
    sb = get_supabase()

    # Fetch full user + org
    result = (
        sb.table("users")
        .select("id, email, org_id, role, orgs(name)")
        .eq("id", current.user_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = result.data
    org_name = None
    if user.get("orgs") and isinstance(user["orgs"], dict):
        org_name = user["orgs"].get("name")

    return UserOut(
        id=user["id"],
        email=user["email"],
        org_id=user["org_id"],
        org_name=org_name,
        role=user["role"],
    )
