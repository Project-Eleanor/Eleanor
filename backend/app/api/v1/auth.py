"""Authentication API endpoints.

Supports multiple authentication methods:
- Local (SAM): Username/password stored in database
- OIDC: OpenID Connect for SSO (Azure AD, Okta, Keycloak, etc.)
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from jose.exceptions import JWTClaimsError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import AuthProvider, User

router = APIRouter()
settings = get_settings()

# In-memory store for OIDC state (in production, use Redis)
_oidc_states: dict[str, dict] = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""

    username: str | None = None
    user_id: str | None = None


class UserResponse(BaseModel):
    """User information response."""

    id: str
    username: str
    email: str | None
    display_name: str | None
    auth_provider: str
    is_active: bool
    is_admin: bool
    roles: list[str]
    last_login: datetime | None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """User creation request."""

    username: str
    email: str | None = None
    display_name: str | None = None
    password: str


class SetupRequest(BaseModel):
    """Initial setup request for creating first admin user."""

    username: str
    email: str | None = None
    password: str


class SetupStatusResponse(BaseModel):
    """Setup status response."""

    needs_setup: bool
    message: str


class OIDCAuthUrlResponse(BaseModel):
    """OIDC authorization URL response."""

    auth_url: str
    state: str


class OIDCConfigResponse(BaseModel):
    """OIDC configuration status response."""

    enabled: bool
    issuer: str | None = None
    provider_name: str | None = None


class AuthMethodsResponse(BaseModel):
    """Available authentication methods response."""

    local_enabled: bool
    oidc_enabled: bool
    oidc_provider: str | None = None


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


async def get_current_active_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate user and return JWT token."""
    from app.utils.password import verify_password

    # Find user
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or user.auth_provider != AuthProvider.SAM:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.password_hash or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Update last login
    user.last_login = datetime.now(UTC)
    await db.commit()

    # Create token
    access_token = create_access_token(data={"sub": user.username, "user_id": str(user.id)})

    return Token(
        access_token=access_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Get current user information."""
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        display_name=current_user.display_name,
        auth_provider=current_user.auth_provider.value,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        roles=current_user.roles,
        last_login=current_user.last_login,
    )


@router.post("/logout")
async def logout() -> dict:
    """Logout current user (client-side token removal)."""
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Token:
    """Refresh access token."""
    access_token = create_access_token(
        data={"sub": current_user.username, "user_id": str(current_user.id)}
    )
    return Token(
        access_token=access_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/setup/status", response_model=SetupStatusResponse)
async def get_setup_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SetupStatusResponse:
    """Check if initial setup is needed (no users exist)."""
    from sqlalchemy import func

    result = await db.execute(select(func.count()).select_from(User))
    user_count = result.scalar() or 0

    if user_count == 0:
        return SetupStatusResponse(
            needs_setup=True,
            message="No users exist. Please create an admin account.",
        )
    return SetupStatusResponse(
        needs_setup=False,
        message="Setup complete. Please login.",
    )


@router.post("/setup", response_model=UserResponse)
async def initial_setup(
    setup_data: SetupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Create initial admin user. Only works when no users exist."""
    from sqlalchemy import func

    from app.utils.password import hash_password

    # Check if any users exist
    result = await db.execute(select(func.count()).select_from(User))
    user_count = result.scalar() or 0

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already complete. Users already exist.",
        )

    # Validate password length
    if len(setup_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    # Create admin user
    admin_user = User(
        username=setup_data.username,
        email=setup_data.email,
        display_name=setup_data.username,
        auth_provider=AuthProvider.SAM,
        password_hash=hash_password(setup_data.password),
        is_admin=True,
        is_active=True,
        roles=["admin"],
    )

    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)

    return UserResponse(
        id=str(admin_user.id),
        username=admin_user.username,
        email=admin_user.email,
        display_name=admin_user.display_name,
        auth_provider=admin_user.auth_provider.value,
        is_active=admin_user.is_active,
        is_admin=admin_user.is_admin,
        roles=admin_user.roles,
        last_login=admin_user.last_login,
    )


# =============================================================================
# Authentication Methods Info
# =============================================================================


@router.get("/methods", response_model=AuthMethodsResponse)
async def get_auth_methods() -> AuthMethodsResponse:
    """Get available authentication methods."""
    oidc_provider = None
    if settings.oidc_enabled and settings.oidc_issuer:
        # Extract provider name from issuer URL
        issuer = settings.oidc_issuer.lower()
        if "microsoftonline" in issuer or "azure" in issuer:
            oidc_provider = "Azure AD"
        elif "okta" in issuer:
            oidc_provider = "Okta"
        elif "keycloak" in issuer:
            oidc_provider = "Keycloak"
        elif "auth0" in issuer:
            oidc_provider = "Auth0"
        elif "google" in issuer:
            oidc_provider = "Google"
        else:
            oidc_provider = "SSO"

    return AuthMethodsResponse(
        local_enabled=settings.sam_enabled,
        oidc_enabled=settings.oidc_enabled,
        oidc_provider=oidc_provider,
    )


# =============================================================================
# OIDC Authentication Endpoints
# =============================================================================


async def get_oidc_discovery() -> dict:
    """Fetch OIDC discovery document."""
    if not settings.oidc_enabled or not settings.oidc_issuer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC is not configured",
        )

    discovery_url = f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(discovery_url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch OIDC discovery: {e}",
            )


@router.get("/oidc/config", response_model=OIDCConfigResponse)
async def get_oidc_config() -> OIDCConfigResponse:
    """Get OIDC configuration status."""
    if not settings.oidc_enabled:
        return OIDCConfigResponse(enabled=False)

    # Determine provider name
    provider_name = None
    if settings.oidc_issuer:
        issuer = settings.oidc_issuer.lower()
        if "microsoftonline" in issuer:
            provider_name = "Microsoft Azure AD"
        elif "okta" in issuer:
            provider_name = "Okta"
        elif "keycloak" in issuer:
            provider_name = "Keycloak"
        elif "auth0" in issuer:
            provider_name = "Auth0"
        elif "google" in issuer:
            provider_name = "Google"

    return OIDCConfigResponse(
        enabled=True,
        issuer=settings.oidc_issuer,
        provider_name=provider_name,
    )


@router.get("/oidc/login")
async def oidc_login_redirect() -> RedirectResponse:
    """Redirect to OIDC provider for authentication."""
    discovery = await get_oidc_discovery()
    auth_endpoint = discovery.get("authorization_endpoint")

    if not auth_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC provider missing authorization endpoint",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Store state for verification (expires in 10 minutes)
    _oidc_states[state] = {
        "nonce": nonce,
        "created_at": datetime.now(UTC),
    }

    # Clean up expired states
    _cleanup_expired_states()

    # Build authorization URL
    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
    }

    auth_url = f"{auth_endpoint}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oidc/authorize", response_model=OIDCAuthUrlResponse)
async def get_oidc_auth_url() -> OIDCAuthUrlResponse:
    """Get OIDC authorization URL for client-side redirect."""
    discovery = await get_oidc_discovery()
    auth_endpoint = discovery.get("authorization_endpoint")

    if not auth_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC provider missing authorization endpoint",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    # Store state for verification
    _oidc_states[state] = {
        "nonce": nonce,
        "created_at": datetime.now(UTC),
    }

    _cleanup_expired_states()

    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
    }

    auth_url = f"{auth_endpoint}?{urlencode(params)}"
    return OIDCAuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/oidc/callback", response_model=Token)
async def oidc_callback(
    code: str = Query(..., description="Authorization code from OIDC provider"),
    state: str = Query(..., description="State parameter for CSRF verification"),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Handle OIDC callback and exchange code for tokens."""
    # Verify state
    stored_state = _oidc_states.pop(state, None)
    if not stored_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    # Check state age (10 minute expiry)
    state_age = datetime.now(UTC) - stored_state["created_at"]
    if state_age.total_seconds() > 600:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State parameter expired",
        )

    # Get discovery document for token endpoint
    discovery = await get_oidc_discovery()
    token_endpoint = discovery.get("token_endpoint")
    userinfo_endpoint = discovery.get("userinfo_endpoint")

    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC provider missing token endpoint",
        )

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.oidc_redirect_uri,
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                },
                timeout=30.0,
            )
            token_response.raise_for_status()
            tokens = token_response.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange code for tokens: {e}",
            )

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ID token received from OIDC provider",
        )

    # Decode and validate ID token
    try:
        # Get JWKS for token validation
        jwks_uri = discovery.get("jwks_uri")
        if jwks_uri:
            async with httpx.AsyncClient() as client:
                jwks_response = await client.get(jwks_uri, timeout=10.0)
                jwks = jwks_response.json()

            # Decode token with validation
            id_claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256", "RS384", "RS512"],
                audience=settings.oidc_client_id,
                issuer=settings.oidc_issuer,
                options={"verify_at_hash": False},
            )
        else:
            # Fallback: decode without signature verification (not recommended)
            id_claims = jwt.decode(
                id_token,
                options={"verify_signature": False},
            )
    except (JWTError, JWTClaimsError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token: {e}",
        )

    # Extract user info from ID token or userinfo endpoint
    user_info = await _extract_user_info(id_claims, access_token, userinfo_endpoint)

    # Find or create user
    user = await _get_or_create_oidc_user(db, user_info)

    # Update last login
    user.last_login = datetime.now(UTC)
    await db.commit()

    # Create Eleanor JWT token
    eleanor_token = create_access_token(data={"sub": user.username, "user_id": str(user.id)})

    return Token(
        access_token=eleanor_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/oidc/token", response_model=Token)
async def oidc_token_exchange(
    id_token: str = Query(..., description="ID token from OIDC provider"),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Exchange an OIDC ID token for an Eleanor JWT token.

    This endpoint is useful for SPAs that handle the OIDC flow client-side.
    """
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC is not configured",
        )

    discovery = await get_oidc_discovery()

    try:
        # Get JWKS for token validation
        jwks_uri = discovery.get("jwks_uri")
        if jwks_uri:
            async with httpx.AsyncClient() as client:
                jwks_response = await client.get(jwks_uri, timeout=10.0)
                jwks = jwks_response.json()

            id_claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256", "RS384", "RS512"],
                audience=settings.oidc_client_id,
                issuer=settings.oidc_issuer,
                options={"verify_at_hash": False},
            )
        else:
            id_claims = jwt.decode(
                id_token,
                options={"verify_signature": False},
            )
    except (JWTError, JWTClaimsError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token: {e}",
        )

    # Extract user info
    user_info = await _extract_user_info(id_claims, None, None)

    # Find or create user
    user = await _get_or_create_oidc_user(db, user_info)

    # Update last login
    user.last_login = datetime.now(UTC)
    await db.commit()

    # Create Eleanor JWT token
    eleanor_token = create_access_token(data={"sub": user.username, "user_id": str(user.id)})

    return Token(
        access_token=eleanor_token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


async def _extract_user_info(
    id_claims: dict,
    access_token: str | None,
    userinfo_endpoint: str | None,
) -> dict:
    """Extract user information from ID token claims or userinfo endpoint."""
    user_info = {
        "sub": id_claims.get("sub"),
        "email": id_claims.get("email"),
        "name": id_claims.get("name"),
        "preferred_username": id_claims.get("preferred_username"),
        "given_name": id_claims.get("given_name"),
        "family_name": id_claims.get("family_name"),
        "groups": id_claims.get("groups", []),
        "roles": id_claims.get("roles", []),
    }

    # Try to get additional info from userinfo endpoint
    if access_token and userinfo_endpoint and not user_info.get("email"):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    userinfo = response.json()
                    user_info.update(
                        {
                            "email": userinfo.get("email") or user_info.get("email"),
                            "name": userinfo.get("name") or user_info.get("name"),
                            "preferred_username": userinfo.get("preferred_username")
                            or user_info.get("preferred_username"),
                        }
                    )
        except httpx.HTTPError:
            pass  # Userinfo is optional, continue without it

    return user_info


async def _get_or_create_oidc_user(db: AsyncSession, user_info: dict) -> User:
    """Get existing OIDC user or create a new one."""
    external_id = user_info.get("sub")
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC token missing subject claim",
        )

    # Try to find existing user by external_id
    result = await db.execute(
        select(User).where(
            User.external_id == external_id,
            User.auth_provider == AuthProvider.OIDC,
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info on login
        user.email = user_info.get("email") or user.email
        user.display_name = user_info.get("name") or user.display_name

        # Update roles from OIDC groups/roles claims
        oidc_roles = _map_oidc_roles(user_info)
        if oidc_roles:
            user.roles = oidc_roles
            # Check for admin role
            user.is_admin = "admin" in oidc_roles or "Admin" in user_info.get("groups", [])

        return user

    # Create new user
    # Generate username from preferred_username, email, or sub
    username = (
        user_info.get("preferred_username")
        or user_info.get("email", "").split("@")[0]
        or f"oidc_{hashlib.sha256(external_id.encode()).hexdigest()[:8]}"
    )

    # Ensure username is unique
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        username = f"{username}_{secrets.token_hex(4)}"

    # Map OIDC groups to roles
    roles = _map_oidc_roles(user_info)

    # Check if this is the first user (make them admin)
    from sqlalchemy import func

    count_result = await db.execute(select(func.count()).select_from(User))
    is_first_user = (count_result.scalar() or 0) == 0

    # Check for admin role in OIDC claims
    is_admin = is_first_user or "admin" in roles or "Admin" in user_info.get("groups", [])

    new_user = User(
        username=username,
        email=user_info.get("email"),
        display_name=user_info.get("name") or username,
        auth_provider=AuthProvider.OIDC,
        external_id=external_id,
        is_admin=is_admin,
        is_active=True,
        roles=roles or ["user"],
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


def _map_oidc_roles(user_info: dict) -> list[str]:
    """Map OIDC groups/roles to Eleanor roles."""
    roles = set()

    # Check roles claim
    oidc_roles = user_info.get("roles", [])
    if isinstance(oidc_roles, str):
        oidc_roles = [oidc_roles]

    for role in oidc_roles:
        role_lower = role.lower()
        if "admin" in role_lower:
            roles.add("admin")
        elif "analyst" in role_lower:
            roles.add("analyst")
        elif "viewer" in role_lower or "read" in role_lower:
            roles.add("viewer")

    # Check groups claim
    groups = user_info.get("groups", [])
    if isinstance(groups, str):
        groups = [groups]

    for group in groups:
        group_lower = group.lower()
        if "eleanor-admin" in group_lower or "dfir-admin" in group_lower:
            roles.add("admin")
        elif "eleanor-analyst" in group_lower or "dfir-analyst" in group_lower:
            roles.add("analyst")
        elif "eleanor" in group_lower or "dfir" in group_lower:
            roles.add("user")

    # Default to user role if no roles found
    if not roles:
        roles.add("user")

    return list(roles)


def _cleanup_expired_states():
    """Remove expired OIDC states from memory."""
    now = datetime.now(UTC)
    expired = [
        state
        for state, data in _oidc_states.items()
        if (now - data["created_at"]).total_seconds() > 600
    ]
    for state in expired:
        _oidc_states.pop(state, None)
