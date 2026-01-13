"""
Authentication Service
======================

Handles JWT token creation/verification, user management with bcrypt,
and refresh token rotation for secure authentication.
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Data directory for users storage
DATA_DIR = Path(os.getenv("DATA_DIR", Path.home() / ".auto-agent-harness"))
USERS_FILE = DATA_DIR / "users.json"


class User(BaseModel):
    """User model."""
    username: str
    hashed_password: str
    is_active: bool = True
    created_at: str = ""


class TokenData(BaseModel):
    """Decoded token data."""
    username: str
    token_type: str  # "access" or "refresh"
    exp: datetime


def _ensure_data_dir() -> None:
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_users() -> dict[str, User]:
    """Load users from JSON file."""
    _ensure_data_dir()
    if not USERS_FILE.exists():
        return {}

    try:
        data = json.loads(USERS_FILE.read_text())
        return {username: User(**user_data) for username, user_data in data.items()}
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_users(users: dict[str, User]) -> None:
    """Save users to JSON file."""
    _ensure_data_dir()
    data = {username: user.model_dump() for username, user in users.items()}
    USERS_FILE.write_text(json.dumps(data, indent=2))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def create_token(username: str, expires_delta: timedelta, token_type: str = "access") -> str:
    """Create a JWT token."""
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": username,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(username: str) -> tuple[str, str]:
    """Create access and refresh token pair."""
    access_token = create_token(
        username,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access"
    )
    refresh_token = create_token(
        username,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh"
    )
    return access_token, refresh_token


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenData]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        exp = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)

        if username is None:
            return None

        if token_type != expected_type:
            return None

        return TokenData(username=username, token_type=token_type, exp=exp)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user(username: str) -> Optional[User]:
    """Get a user by username."""
    users = _load_users()
    return users.get(username)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = get_user(username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(username: str, password: str) -> Optional[User]:
    """Create a new user."""
    users = _load_users()

    if username in users:
        return None  # User already exists

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    users[username] = user
    _save_users(users)

    return user


def change_password(username: str, new_password: str) -> bool:
    """Change a user's password."""
    users = _load_users()

    if username not in users:
        return False

    users[username].hashed_password = hash_password(new_password)
    _save_users(users)

    return True


def delete_user(username: str) -> bool:
    """Delete a user."""
    users = _load_users()

    if username not in users:
        return False

    del users[username]
    _save_users(users)

    return True


def list_users() -> list[str]:
    """List all usernames."""
    users = _load_users()
    return list(users.keys())


def ensure_default_user() -> None:
    """Ensure a default admin user exists if no users exist."""
    users = _load_users()

    if not users:
        # Create default admin user
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
        create_user("admin", default_password)


# Initialize default user on module load
ensure_default_user()
