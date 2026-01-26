"""Tenant middleware for multi-tenancy support.

This middleware extracts tenant information from incoming requests
and sets up the tenant context for the request lifecycle.
"""

import hashlib
import logging
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.config import get_settings
from app.core.tenant_context import TenantContext, set_tenant_context
from app.database import async_session_maker
from app.models.tenant import Tenant, TenantAPIKey, TenantStatus

logger = logging.getLogger(__name__)
settings = get_settings()

# Headers for tenant identification
TENANT_ID_HEADER = "X-Tenant-ID"
TENANT_SLUG_HEADER = "X-Tenant-Slug"
API_KEY_HEADER = "X-API-Key"

# Paths that don't require tenant context
TENANT_EXEMPT_PATHS = {
    "/health",
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/callback",
    "/api/v1/auth/refresh",
    "/api/v1/admin/tenants",  # Admin can list/create tenants without context
}


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts and validates tenant context from requests.

    Tenant identification methods (in order of priority):
    1. X-API-Key header - API key authentication includes tenant
    2. X-Tenant-ID header - Explicit tenant ID
    3. X-Tenant-Slug header - Explicit tenant slug
    4. User's default tenant (from JWT claims)
    5. Domain-based routing (for SSO)
    """

    def __init__(self, app: ASGIApp, default_tenant_slug: str | None = None):
        """Initialize the tenant middleware.

        Args:
            app: The ASGI application.
            default_tenant_slug: Optional default tenant slug for single-tenant deployments.
        """
        super().__init__(app)
        self.default_tenant_slug = default_tenant_slug

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and set up tenant context."""
        # Clear any existing tenant context
        set_tenant_context(None)

        # Check if path is exempt from tenant requirement
        path = request.url.path
        if self._is_exempt_path(path):
            return await call_next(request)

        # Try to identify tenant
        tenant_context = await self._identify_tenant(request)

        if tenant_context:
            set_tenant_context(tenant_context)
            logger.debug(
                "Tenant context set: %s (%s)",
                tenant_context.tenant_slug,
                tenant_context.tenant_id,
            )
        elif not self._is_public_path(path):
            # For non-public paths, tenant is required
            logger.warning("No tenant context for path: %s", path)
            # We don't return 403 here - let the endpoint decide if tenant is required
            # This allows for graceful handling of admin/system endpoints

        try:
            response = await call_next(request)
            return response
        finally:
            # Clean up tenant context
            set_tenant_context(None)

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from tenant requirement."""
        # Exact matches
        if path in TENANT_EXEMPT_PATHS:
            return True

        # Prefix matches for certain paths
        exempt_prefixes = ["/docs", "/redoc", "/static"]
        return any(path.startswith(prefix) for prefix in exempt_prefixes)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is publicly accessible without tenant."""
        return self._is_exempt_path(path)

    async def _identify_tenant(self, request: Request) -> TenantContext | None:
        """Identify tenant from request.

        Returns:
            TenantContext if tenant is identified, None otherwise.
        """
        # Skip DB lookups in testing mode (get settings dynamically for test overrides)
        current_settings = get_settings()
        if current_settings.testing:
            return None

        # Method 1: API Key authentication
        api_key = request.headers.get(API_KEY_HEADER)
        if api_key:
            tenant = await self._get_tenant_from_api_key(api_key)
            if tenant:
                return TenantContext.from_tenant(tenant)

        # Method 2: Explicit tenant ID header
        tenant_id_str = request.headers.get(TENANT_ID_HEADER)
        if tenant_id_str:
            try:
                tenant_id = UUID(tenant_id_str)
                tenant = await self._get_tenant_by_id(tenant_id)
                if tenant:
                    return TenantContext.from_tenant(tenant)
            except ValueError:
                logger.warning("Invalid tenant ID format: %s", tenant_id_str)

        # Method 3: Explicit tenant slug header
        tenant_slug = request.headers.get(TENANT_SLUG_HEADER)
        if tenant_slug:
            tenant = await self._get_tenant_by_slug(tenant_slug)
            if tenant:
                return TenantContext.from_tenant(tenant)

        # Method 4: User's default tenant (from request state, set by auth)
        user_default_tenant_id = getattr(request.state, "default_tenant_id", None)
        if user_default_tenant_id:
            tenant = await self._get_tenant_by_id(user_default_tenant_id)
            if tenant:
                return TenantContext.from_tenant(tenant)

        # Method 5: Domain-based routing
        host = request.headers.get("host", "").split(":")[0]
        if host and host != "localhost":
            tenant = await self._get_tenant_by_domain(host)
            if tenant:
                return TenantContext.from_tenant(tenant)

        # Method 6: Default tenant for single-tenant deployments
        if self.default_tenant_slug:
            tenant = await self._get_tenant_by_slug(self.default_tenant_slug)
            if tenant:
                return TenantContext.from_tenant(tenant)

        return None

    async def _get_tenant_from_api_key(self, api_key: str) -> Tenant | None:
        """Validate API key and get associated tenant."""
        if len(api_key) < 8:
            return None

        key_prefix = api_key[:8]
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        async with async_session_maker() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload

            query = (
                select(TenantAPIKey)
                .options(joinedload(TenantAPIKey.tenant))
                .where(
                    TenantAPIKey.key_prefix == key_prefix,
                    TenantAPIKey.key_hash == key_hash,
                    TenantAPIKey.is_active == True,  # noqa: E712
                )
            )
            result = await session.execute(query)
            api_key_record = result.scalar_one_or_none()

            if api_key_record and api_key_record.tenant.status == TenantStatus.ACTIVE:
                # Update last used timestamp
                from datetime import datetime, timezone

                api_key_record.last_used_at = datetime.now(timezone.utc)
                await session.commit()
                return api_key_record.tenant

        return None

    async def _get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Get active tenant by ID."""
        async with async_session_maker() as session:
            from sqlalchemy import select

            query = select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.status == TenantStatus.ACTIVE,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def _get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get active tenant by slug."""
        async with async_session_maker() as session:
            from sqlalchemy import select

            query = select(Tenant).where(
                Tenant.slug == slug.lower(),
                Tenant.status == TenantStatus.ACTIVE,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def _get_tenant_by_domain(self, domain: str) -> Tenant | None:
        """Get active tenant by domain."""
        async with async_session_maker() as session:
            from sqlalchemy import select

            query = select(Tenant).where(
                Tenant.domain == domain.lower(),
                Tenant.status == TenantStatus.ACTIVE,
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()


def require_tenant():
    """FastAPI dependency that requires tenant context.

    Usage:
        @router.get("/items")
        async def get_items(tenant: TenantContext = Depends(require_tenant)):
            ...
    """
    from fastapi import Depends, HTTPException

    def get_tenant_or_raise() -> TenantContext:
        from app.core.tenant_context import get_tenant_context

        ctx = get_tenant_context()
        if ctx is None:
            raise HTTPException(
                status_code=400,
                detail="Tenant context required. Provide X-Tenant-ID or X-Tenant-Slug header.",
            )
        return ctx

    return Depends(get_tenant_or_raise)


def optional_tenant():
    """FastAPI dependency that optionally provides tenant context.

    Usage:
        @router.get("/items")
        async def get_items(tenant: TenantContext | None = Depends(optional_tenant)):
            if tenant:
                # Tenant-scoped query
            else:
                # System-wide query (admin only)
    """
    from fastapi import Depends

    def get_optional_tenant() -> TenantContext | None:
        from app.core.tenant_context import get_tenant_context

        return get_tenant_context()

    return Depends(get_optional_tenant)
