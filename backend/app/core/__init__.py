"""Core business logic for Eleanor."""

from app.core.tenant_context import (
    TenantContext,
    get_current_tenant,
    get_current_tenant_id,
    get_elasticsearch_index,
    get_elasticsearch_pattern,
    get_tenant_context,
    require_feature,
    set_tenant_context,
)

__all__ = [
    "TenantContext",
    "get_current_tenant",
    "get_current_tenant_id",
    "get_elasticsearch_index",
    "get_elasticsearch_pattern",
    "get_tenant_context",
    "require_feature",
    "set_tenant_context",
]
