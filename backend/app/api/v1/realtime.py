"""Real-time dashboard API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.dashboard_stats import get_dashboard_stats

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class AlertStats(BaseModel):
    """Alert statistics."""

    total: int
    open: int
    critical: int
    high: int


class CaseStats(BaseModel):
    """Case statistics."""

    total: int
    active: int


class RuleStats(BaseModel):
    """Rule statistics."""

    total: int
    enabled: int


class EventStats(BaseModel):
    """Event statistics."""

    total: int


class OverviewStats(BaseModel):
    """Dashboard overview statistics."""

    time_range: str
    since: str
    alerts: AlertStats
    cases: CaseStats
    rules: RuleStats
    events: EventStats
    generated_at: str


class TimelineBucket(BaseModel):
    """Alert timeline bucket."""

    timestamp: str
    count: int
    by_severity: dict[str, int] = Field(default_factory=dict)


class TopRule(BaseModel):
    """Top triggering rule."""

    id: str
    name: str
    severity: str
    hit_count: int
    last_run_at: str | None
    mitre_techniques: list[str]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/stats", response_model=OverviewStats)
async def get_overview_stats(
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get dashboard overview statistics.

    Returns aggregated stats for alerts, cases, rules, and events.
    """
    stats_service = await get_dashboard_stats()
    return await stats_service.get_overview_stats(db, time_range)


@router.get("/alerts/timeline", response_model=list[TimelineBucket])
async def get_alert_timeline(
    interval: str = Query("1h", pattern="^(15m|1h|4h|1d)$"),
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get alert timeline for charts.

    Returns bucketed alert counts over time with severity breakdown.
    """
    stats_service = await get_dashboard_stats()
    return await stats_service.get_alert_timeline(db, interval, time_range)


@router.get("/rules/top", response_model=list[TopRule])
async def get_top_rules(
    limit: int = Query(10, ge=1, le=50),
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get top triggering rules.

    Returns rules with the most hits in the specified time range.
    """
    stats_service = await get_dashboard_stats()
    return await stats_service.get_top_rules(db, limit, time_range)


@router.get("/alerts/severity")
async def get_severity_distribution(
    time_range: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get alert severity distribution.

    Returns counts for each severity level.
    """
    stats_service = await get_dashboard_stats()
    return await stats_service.get_severity_distribution(db, time_range)


@router.get("/mitre/heatmap")
async def get_mitre_heatmap(
    time_range: str = Query("7d", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get MITRE ATT&CK technique heatmap.

    Returns technique IDs with alert/incident counts.
    """
    stats_service = await get_dashboard_stats()
    return await stats_service.get_mitre_heatmap(db, time_range)
