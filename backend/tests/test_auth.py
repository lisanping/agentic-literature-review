"""Unit tests for v0.4 authentication — password, JWT, register/login/refresh/logout."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)


# ═══════════════════════════════════════════════════
# Password hashing
# ═══════════════════════════════════════════════════


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "my-secure-password-123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_different_hashes_for_same_password(self):
        p = "same-password"
        h1 = hash_password(p)
        h2 = hash_password(p)
        assert h1 != h2  # different salts
        assert verify_password(p, h1)
        assert verify_password(p, h2)


# ═══════════════════════════════════════════════════
# JWT encode/decode
# ═══════════════════════════════════════════════════


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token("user-1", "u@test.com", "user")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-1"
        assert payload["email"] == "u@test.com"
        assert payload["role"] == "user"
        assert "exp" in payload
        assert "iat" in payload

    def test_expired_token_raises(self):
        # Manually create an already-expired token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "email": "u@test.com",
            "role": "user",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token("not-a-valid-jwt")

    def test_wrong_secret_raises(self):
        payload = {
            "sub": "user-1",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(token)


# ═══════════════════════════════════════════════════
# Refresh token utilities
# ═══════════════════════════════════════════════════


class TestRefreshToken:
    def test_generate_is_unique(self):
        t1 = generate_refresh_token()
        t2 = generate_refresh_token()
        assert t1 != t2
        assert len(t1) > 32  # sufficient entropy

    def test_hash_deterministic(self):
        token = "test-token-value"
        h1 = hash_refresh_token(token)
        h2 = hash_refresh_token(token)
        assert h1 == h2

    def test_hash_different_tokens(self):
        assert hash_refresh_token("a") != hash_refresh_token("b")

    def test_expires_at_in_future(self):
        exp = refresh_token_expires_at()
        assert exp > datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════
# User ORM model
# ═══════════════════════════════════════════════════


class TestUserModel:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=hash_password("password123"),
        )
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.email == "test@example.com")
        )
        saved = result.scalar_one()
        assert saved.username == "testuser"
        assert saved.role == "user"
        assert saved.is_active is True
        assert saved.id is not None

    @pytest.mark.asyncio
    async def test_user_defaults(self, db_session: AsyncSession):
        user = User(
            email="defaults@example.com",
            username="defaults",
            hashed_password="fakeHash",
        )
        db_session.add(user)
        await db_session.commit()

        result = await db_session.execute(
            select(User).where(User.email == "defaults@example.com")
        )
        saved = result.scalar_one()
        assert saved.role == "user"
        assert saved.is_active is True
        assert saved.avatar_url is None
        assert saved.last_login_at is None


# ═══════════════════════════════════════════════════
# Auth API endpoints
# ═══════════════════════════════════════════════════


class TestAuthAPI:
    """Integration tests for /api/v1/auth/ endpoints."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "secure-pass-123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        payload = {
            "email": "dup@example.com",
            "username": "user1",
            "password": "secure-pass-123",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "username": "user",
            "password": "short",
        })
        assert resp.status_code == 422  # validation error

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "username": "user",
            "password": "secure-pass-123",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        # Register first
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "my-password-123",
        })
        # Login
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "my-password-123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrong@example.com",
            "username": "user",
            "password": "correct-password",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrong-password",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "some-password",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, client: AsyncClient):
        # Register and get tokens
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "refresh@example.com",
            "username": "refreshuser",
            "password": "my-password-123",
        })
        refresh_token = reg_resp.json()["refresh_token"]

        # Refresh
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        new_refresh = data["refresh_token"]
        assert new_refresh != refresh_token  # rotation: new token

        # Old refresh token should be invalid now
        resp2 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp2.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient):
        # Register
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "logout@example.com",
            "username": "logoutuser",
            "password": "my-password-123",
        })
        tokens = reg_resp.json()
        access = tokens["access_token"]
        refresh = tokens["refresh_token"]

        # Logout
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 204

        # Refresh token should no longer work
        resp2 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp2.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": "some-token",
        })
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# Auth dependency (get_current_user)
# ═══════════════════════════════════════════════════


class TestAuthDependency:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, client: AsyncClient):
        # Register
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "dep@example.com",
            "username": "depuser",
            "password": "my-password-123",
        })
        access = reg_resp.json()["access_token"]

        # Access a protected-ish endpoint (projects list works without auth by default)
        # Just verify the token is decodable
        payload = decode_access_token(access)
        assert payload["email"] == "dep@example.com"

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client: AsyncClient):
        """Expired token should be rejected when calling get_current_user."""
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": "fake-user-id",
            "email": "exp@test.com",
            "role": "user",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = pyjwt.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        # Logout requires auth → use it to test the dependency
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "x"},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_auth_header_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout", json={"refresh_token": "x"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════
# AUTH_REQUIRED backward compatibility
# ═══════════════════════════════════════════════════


class TestAuthBackwardCompat:
    @pytest.mark.asyncio
    async def test_existing_apis_work_without_auth(self, client: AsyncClient):
        """With AUTH_REQUIRED=false (default), existing APIs should still work."""
        # Projects list should work (no auth required on existing routes)
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200
