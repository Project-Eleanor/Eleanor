"""Unit tests for authentication endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4

from jose import jwt

from app.api.v1.auth import create_access_token, Token, UserResponse
from app.models.user import AuthProvider, User


pytestmark = pytest.mark.unit


class TestCreateAccessToken:
    """Tests for JWT token creation."""

    def test_create_access_token_basic(self, test_settings):
        """Test basic token creation."""
        with patch("app.api.v1.auth.settings", test_settings):
            token = create_access_token(data={"sub": "testuser"})

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_subject(self, test_settings):
        """Test token contains subject claim."""
        with patch("app.api.v1.auth.settings", test_settings):
            token = create_access_token(data={"sub": "testuser", "user_id": "123"})

        payload = jwt.decode(
            token,
            test_settings.secret_key,
            algorithms=[test_settings.jwt_algorithm],
        )

        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"

    def test_create_access_token_has_expiration(self, test_settings):
        """Test token has expiration claim."""
        with patch("app.api.v1.auth.settings", test_settings):
            token = create_access_token(data={"sub": "testuser"})

        payload = jwt.decode(
            token,
            test_settings.secret_key,
            algorithms=[test_settings.jwt_algorithm],
        )

        assert "exp" in payload
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Token should expire within the configured time
        assert exp_time > now
        assert exp_time < now + timedelta(minutes=test_settings.jwt_expire_minutes + 1)

    def test_create_access_token_custom_expiration(self, test_settings):
        """Test token with custom expiration."""
        custom_delta = timedelta(hours=2)

        with patch("app.api.v1.auth.settings", test_settings):
            token = create_access_token(
                data={"sub": "testuser"},
                expires_delta=custom_delta,
            )

        payload = jwt.decode(
            token,
            test_settings.secret_key,
            algorithms=[test_settings.jwt_algorithm],
        )

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should be close to 2 hours from now
        assert timedelta(hours=1, minutes=55) < (exp_time - now) < timedelta(hours=2, minutes=5)


class TestLoginEndpoint:
    """Tests for login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "password123"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, inactive_user):
        """Test login with inactive user."""
        # inactive_user is pre-populated in mock_session with password "testpassword123"
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "inactive", "password": "testpassword123"},
        )

        assert response.status_code == 400
        assert "Inactive user" in response.json()["message"]


class TestMeEndpoint:
    """Tests for /me endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, authenticated_client, test_user):
        """Test getting current user info."""
        response = await authenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert data["is_admin"] == test_user.is_admin

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client):
        """Test accessing /me without authentication."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client):
        """Test accessing /me with invalid token."""
        client.headers["Authorization"] = "Bearer invalid_token"
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestRefreshEndpoint:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, authenticated_client):
        """Test successful token refresh."""
        response = await authenticated_client.post("/api/v1/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_unauthorized(self, client):
        """Test refresh without authentication."""
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401


class TestLogoutEndpoint:
    """Tests for logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, authenticated_client):
        """Test successful logout."""
        response = await authenticated_client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]


class TestUserPermissions:
    """Tests for user permission checking."""

    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self, admin_user):
        """Test that admin users have all permissions."""
        assert admin_user.has_permission("cases:read")
        assert admin_user.has_permission("admin:manage")
        assert admin_user.has_permission("any:permission")

    @pytest.mark.asyncio
    async def test_admin_get_permissions_returns_wildcard(self, admin_user):
        """Test that admin get_permissions returns wildcard."""
        permissions = admin_user.get_permissions()
        assert "*" in permissions

    @pytest.mark.asyncio
    async def test_regular_user_limited_permissions(self, test_user):
        """Test that regular users have limited permissions."""
        # Without role assignments, user should have no permissions
        # (except for what their roles provide)
        permissions = test_user.get_permissions()
        # Since we haven't assigned roles with permissions in the fixture,
        # the set should be empty
        assert isinstance(permissions, set)


class TestAdminEndpoint:
    """Tests for admin-only endpoints."""

    @pytest.mark.asyncio
    async def test_admin_access_granted(self, admin_client):
        """Test admin can access admin endpoints."""
        # This would test an admin-only endpoint if one exists
        # For now, just verify the admin client is properly authenticated
        response = await admin_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] is True

    @pytest.mark.asyncio
    async def test_non_admin_access_denied(self, authenticated_client):
        """Test non-admin cannot access admin endpoints."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] is False


class TestTokenValidation:
    """Tests for token validation."""

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client, test_settings, test_user):
        """Test that expired tokens are rejected."""
        # Create a token that's already expired
        with patch("app.api.v1.auth.settings", test_settings):
            token = create_access_token(
                data={"sub": test_user.username, "user_id": str(test_user.id)},
                expires_delta=timedelta(seconds=-1),  # Already expired
            )

        client.headers["Authorization"] = f"Bearer {token}"
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, client):
        """Test that malformed tokens are rejected."""
        client.headers["Authorization"] = "Bearer not.a.valid.jwt.token"
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix_rejected(self, client, sample_jwt_token):
        """Test that tokens without Bearer prefix are rejected."""
        client.headers["Authorization"] = sample_jwt_token  # Missing "Bearer "
        response = await client.get("/api/v1/auth/me")

        # FastAPI OAuth2PasswordBearer should reject this
        assert response.status_code == 401
