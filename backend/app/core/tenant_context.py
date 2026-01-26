"""Tenant context management for multi-tenancy.

This module provides context variables and utilities for tracking
the current tenant throughout a request lifecycle.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.tenant import Tenant


@dataclass
class TenantContext:
    """Context holding current tenant information.

    This is stored in a context variable and is available throughout
    the request lifecycle after the tenant middleware processes the request.
    """

    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    elasticsearch_prefix: str
    features: list[str]
    settings: dict

    @classmethod
    def from_tenant(cls, tenant: "Tenant") -> "TenantContext":
        """Create context from a Tenant model instance."""
        return cls(
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            elasticsearch_prefix=tenant.elasticsearch_prefix,
            features=tenant.settings.get("features", []),
            settings=tenant.settings,
        )


# Context variable for storing current tenant
_tenant_context: ContextVar[TenantContext | None] = ContextVar(
    "tenant_context", default=None
)


def set_tenant_context(context: TenantContext | None) -> None:
    """Set the current tenant context.

    Args:
        context: The tenant context to set, or None to clear.
    """
    _tenant_context.set(context)


def get_tenant_context() -> TenantContext | None:
    """Get the current tenant context.

    Returns:
        The current tenant context, or None if not set.
    """
    return _tenant_context.get()


def get_current_tenant_id() -> UUID | None:
    """Get the current tenant ID.

    Returns:
        The current tenant's UUID, or None if no tenant context is set.
    """
    ctx = get_tenant_context()
    return ctx.tenant_id if ctx else None


def get_current_tenant() -> TenantContext:
    """Get the current tenant context, raising if not set.

    Returns:
        The current tenant context.

    Raises:
        RuntimeError: If no tenant context is set.
    """
    ctx = get_tenant_context()
    if ctx is None:
        raise RuntimeError("No tenant context set. Ensure tenant middleware is active.")
    return ctx


def require_feature(feature: str) -> bool:
    """Check if the current tenant has a required feature.

    Args:
        feature: The feature name to check.

    Returns:
        True if the feature is available.

    Raises:
        RuntimeError: If no tenant context is set.
        PermissionError: If the tenant doesn't have the feature.
    """
    ctx = get_current_tenant()
    if feature not in ctx.features:
        raise PermissionError(f"Feature '{feature}' is not available for this tenant.")
    return True


def get_elasticsearch_index(index_type: str, date_suffix: str | None = None) -> str:
    """Get the tenant-scoped Elasticsearch index name.

    Args:
        index_type: The type of index (events, timeline, alerts, etc.)
        date_suffix: Optional date suffix (e.g., "2026.01.26")

    Returns:
        The full index name with tenant prefix.

    Raises:
        RuntimeError: If no tenant context is set.
    """
    ctx = get_current_tenant()
    if date_suffix:
        return f"{ctx.elasticsearch_prefix}-{index_type}-{date_suffix}"
    return f"{ctx.elasticsearch_prefix}-{index_type}"


def get_elasticsearch_pattern(index_type: str) -> str:
    """Get the tenant-scoped Elasticsearch index pattern.

    Args:
        index_type: The type of index (events, timeline, alerts, etc.)

    Returns:
        The index pattern with tenant prefix (e.g., "eleanor-acme-events-*")

    Raises:
        RuntimeError: If no tenant context is set.
    """
    ctx = get_current_tenant()
    return f"{ctx.elasticsearch_prefix}-{index_type}-*"
