"""Integration status and configuration endpoints.

Provides visibility into the status of all external tool integrations
and allows administrators to configure integration settings.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.adapters import AdapterHealth, AdapterStatus, get_registry
from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================


class IntegrationStatus(BaseModel):
    """Status of a single integration."""

    name: str
    description: str
    status: str  # connected, disconnected, error, configuring
    enabled: bool
    version: str | None = None
    message: str | None = None
    last_check: str | None = None
    details: dict[str, Any] = {}


class IntegrationsStatusResponse(BaseModel):
    """Response containing status of all integrations."""

    integrations: list[IntegrationStatus]
    summary: dict[str, int]  # Count by status


class IntegrationConfigResponse(BaseModel):
    """Response containing integration configuration (sanitized)."""

    name: str
    config: dict[str, Any]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=IntegrationsStatusResponse)
async def get_integrations_status(
    current_user: User = Depends(get_current_user),
) -> IntegrationsStatusResponse:
    """Get status of all integrations.

    Returns the current connection status, version info, and any error
    messages for each configured integration.
    """
    registry = get_registry()

    # Run health checks on all adapters
    health_results = await registry.health_check_all()

    integrations = []
    summary = {"connected": 0, "disconnected": 0, "error": 0, "configuring": 0}

    # Integration metadata
    integration_meta = {
        "velociraptor": {
            "description": "Endpoint visibility and collection",
        },
        "iris": {
            "description": "Case management backend",
        },
        "opencti": {
            "description": "Threat intelligence enrichment",
        },
        "shuffle": {
            "description": "SOAR workflow automation",
        },
        "timesketch": {
            "description": "Timeline analysis engine",
        },
    }

    for name in registry.list_registered():
        health: AdapterHealth = health_results.get(
            name,
            AdapterHealth(
                adapter_name=name,
                status=AdapterStatus.DISCONNECTED,
                message="Not configured",
            ),
        )

        meta = integration_meta.get(name, {"description": "Unknown integration"})
        adapter = registry.get(name)

        status_str = health.status.value
        summary[status_str] = summary.get(status_str, 0) + 1

        integrations.append(
            IntegrationStatus(
                name=name,
                description=meta["description"],
                status=status_str,
                enabled=adapter is not None,
                version=health.version,
                message=health.message,
                last_check=health.last_check.isoformat() if health.last_check else None,
                details=health.details,
            )
        )

    return IntegrationsStatusResponse(
        integrations=integrations,
        summary=summary,
    )


@router.get("/{integration_name}/status", response_model=IntegrationStatus)
async def get_integration_status(
    integration_name: str,
    current_user: User = Depends(get_current_user),
) -> IntegrationStatus:
    """Get status of a specific integration."""
    registry = get_registry()

    if integration_name not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration: {integration_name}",
        )

    adapter = registry.get(integration_name)
    if adapter:
        health = await adapter.health_check()
    else:
        health = AdapterHealth(
            adapter_name=integration_name,
            status=AdapterStatus.DISCONNECTED,
            message="Not enabled",
        )

    integration_meta = {
        "velociraptor": "Endpoint visibility and collection",
        "iris": "Case management backend",
        "opencti": "Threat intelligence enrichment",
        "shuffle": "SOAR workflow automation",
        "timesketch": "Timeline analysis engine",
    }

    return IntegrationStatus(
        name=integration_name,
        description=integration_meta.get(integration_name, "Unknown"),
        status=health.status.value,
        enabled=adapter is not None,
        version=health.version,
        message=health.message,
        last_check=health.last_check.isoformat() if health.last_check else None,
        details=health.details,
    )


@router.get("/{integration_name}/config", response_model=IntegrationConfigResponse)
async def get_integration_config(
    integration_name: str,
    current_user: User = Depends(get_current_user),
) -> IntegrationConfigResponse:
    """Get configuration of a specific integration (sanitized).

    Requires admin role. Sensitive values like API keys are masked.
    """
    # Check admin role
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    registry = get_registry()

    if integration_name not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration: {integration_name}",
        )

    adapter = registry.get(integration_name)
    if not adapter:
        return IntegrationConfigResponse(
            name=integration_name,
            config={"enabled": False},
        )

    config = await adapter.get_config()

    return IntegrationConfigResponse(
        name=integration_name,
        config=config,
    )


@router.post("/{integration_name}/test")
async def test_integration(
    integration_name: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Test connectivity to a specific integration.

    Performs a fresh health check and returns detailed results.
    """
    registry = get_registry()

    if integration_name not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration: {integration_name}",
        )

    adapter = registry.get(integration_name)
    if not adapter:
        return {
            "success": False,
            "message": f"{integration_name} is not enabled",
            "status": "disconnected",
        }

    try:
        health = await adapter.health_check()
        return {
            "success": health.status == AdapterStatus.CONNECTED,
            "message": health.message,
            "status": health.status.value,
            "version": health.version,
            "details": health.details,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "status": "error",
        }


@router.post("/{integration_name}/reconnect")
async def reconnect_integration(
    integration_name: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Attempt to reconnect to an integration.

    Requires admin role.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    registry = get_registry()

    if integration_name not in registry.list_registered():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration: {integration_name}",
        )

    adapter = registry.get(integration_name)
    if not adapter:
        return {
            "success": False,
            "message": f"{integration_name} is not enabled",
        }

    try:
        # Disconnect and reconnect
        await adapter.disconnect()
        success = await adapter.connect()
        return {
            "success": success,
            "message": "Reconnected successfully" if success else "Reconnection failed",
            "status": adapter.status.value,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
        }
