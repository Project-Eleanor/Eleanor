"""Microsoft Sentinel adapter for Eleanor.

Provides integration with Microsoft Sentinel SIEM for:
- Incident management
- Alert retrieval
- KQL query execution
- Entity lookup
- Watchlist management
- Hunting queries
"""

from app.adapters.sentinel.adapter import SentinelAdapter
from app.adapters.sentinel.schemas import (
    SentinelAlert,
    SentinelEntity,
    SentinelHuntingQuery,
    SentinelIncident,
    SentinelWatchlist,
)

__all__ = [
    "SentinelAdapter",
    "SentinelIncident",
    "SentinelAlert",
    "SentinelEntity",
    "SentinelWatchlist",
    "SentinelHuntingQuery",
]
