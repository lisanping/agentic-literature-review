"""User-related Pydantic schemas — v0.4 authentication."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data in API responses."""

    id: str
    email: str
    username: str
    role: str
    is_active: bool
    avatar_url: str | None = None
    preferences: dict = {}
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Partial update of current user profile."""

    username: str | None = Field(None, min_length=2, max_length=50)
    avatar_url: str | None = None
    preferences: dict | None = None


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenRefresh(BaseModel):
    """Token refresh request."""

    refresh_token: str


class AdminUserUpdate(BaseModel):
    """Admin-level user update."""

    username: str | None = Field(None, min_length=2, max_length=50)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None
