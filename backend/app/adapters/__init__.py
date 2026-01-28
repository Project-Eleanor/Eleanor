"""Adapter system for external integrations.

Eleanor uses adapters to integrate with external DFIR tools:
- Velociraptor: Endpoint collection and response
- IRIS: Case management backend
- OpenCTI: Threat intelligence enrichment
- Shuffle: SOAR/workflow automation
- Timesketch: Timeline analysis

Usage:
    from app.adapters import get_registry, init_adapters

    # At startup
    registry = await init_adapters(settings)

    # Get specific adapter
    velo = registry.get_collection()
    if velo:
        endpoints = await velo.list_endpoints()
"""

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    BaseAdapter,
    CaseManagementAdapter,
    CollectionAdapter,
    IndicatorType,
    Severity,
    SOARAdapter,
    ThreatIntelAdapter,
    Ticket,
    TicketComment,
    TicketingAdapter,
    TicketPriority,
    TicketTransition,
    TimelineAdapter,
)
from app.adapters.registry import (
    AdapterRegistry,
    get_registry,
    init_adapters,
)

__all__ = [
    # Base classes
    "AdapterConfig",
    "AdapterHealth",
    "AdapterStatus",
    "BaseAdapter",
    "CaseManagementAdapter",
    "CollectionAdapter",
    "IndicatorType",
    "Severity",
    "SOARAdapter",
    "ThreatIntelAdapter",
    "Ticket",
    "TicketComment",
    "TicketingAdapter",
    "TicketPriority",
    "TicketTransition",
    "TimelineAdapter",
    # Registry
    "AdapterRegistry",
    "get_registry",
    "init_adapters",
]
