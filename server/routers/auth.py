"""
Authentication Router
=====================

Provides login, logout, refresh, and user management endpoints.
Uses httpOnly cookies for secure token storage.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

from ..services.auth_service import (
    authenticate_user,
    create_token_pair,
    verify_token,
    create_user,
    change_password,
    delete_user,
    list_users,
    get_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response (without tokens - they're in cookies)."""
    username: str
    message: str


class CreateUserRequest(BaseModel):
    """Create user request body."""
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    current_password: str
    new_password: str


class UserInfo(BaseModel):
    """User info response."""
    username: str
    is_active: bool


# ============================================================================
# Cookie Configuration
# ============================================================================

# Cookie security settings from environment
# COOKIE_SECURE: Set to "false" for HTTP, "true" for HTTPS
# COOKIE_SAMESITE: "strict", "lax", or "none"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly auth cookies on response."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",  # Only sent to auth endpoints
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies from response."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth")


# ============================================================================
# Dependency: Get Current User
# ============================================================================

async def get_current_user(request: Request) -> Optional[str]:
    """Get current user from access token cookie."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None

    token_data = verify_token(access_token, expected_type="access")
    if not token_data:
        return None

    user = get_user(token_data.username)
    if not user or not user.is_active:
        return None

    return token_data.username


async def require_auth(request: Request) -> str:
    """Require authentication - raises 401 if not authenticated."""
    username = await get_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """
    Authenticate user and set auth cookies.

    Returns user info on success, sets httpOnly cookies for tokens.
    """
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token, refresh_token = create_token_pair(user.username)

    set_auth_cookies(response, access_token, refresh_token)

    return LoginResponse(
        username=user.username,
        message="Login successful",
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: Request, response: Response):
    """
    Refresh access token using refresh token.

    Rotates both tokens for security.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_data = verify_token(refresh_token, expected_type="refresh")
    if not token_data:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = get_user(token_data.username)
    if not user or not user.is_active:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Create new token pair (rotation)
    new_access, new_refresh = create_token_pair(user.username)

    set_auth_cookies(response, new_access, new_refresh)

    return LoginResponse(
        username=user.username,
        message="Tokens refreshed",
    )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing auth cookies.
    """
    clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
async def get_me(username: str = Depends(require_auth)):
    """
    Get current authenticated user info.
    """
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfo(
        username=user.username,
        is_active=user.is_active,
    )


@router.post("/change-password")
async def change_user_password(
    request: ChangePasswordRequest,
    username: str = Depends(require_auth),
):
    """
    Change current user's password.
    """
    user = authenticate_user(username, request.current_password)
    if not user:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    success = change_password(username, request.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to change password")

    return {"message": "Password changed successfully"}


# ============================================================================
# Admin Endpoints (for user management)
# ============================================================================

@router.get("/users")
async def get_users(username: str = Depends(require_auth)):
    """
    List all users (admin only - currently any authenticated user).
    """
    return {"users": list_users()}


@router.post("/users", response_model=UserInfo)
async def create_new_user(
    request: CreateUserRequest,
    username: str = Depends(require_auth),
):
    """
    Create a new user (admin only).
    """
    user = create_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=400, detail="User already exists")

    return UserInfo(
        username=user.username,
        is_active=user.is_active,
    )


@router.delete("/users/{target_username}")
async def delete_existing_user(
    target_username: str,
    username: str = Depends(require_auth),
):
    """
    Delete a user (admin only).
    """
    if target_username == username:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    success = delete_user(target_username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User {target_username} deleted"}
