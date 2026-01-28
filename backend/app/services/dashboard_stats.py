"""Dashboard statistics service for real-time SOC monitoring.

Provides aggregated statistics, metrics, and live data for the SOC dashboard.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.tenant_context import get_current_tenant_id, get_elasticsearch_pattern
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.analytics import DetectionRule, RuleStatus
from app.models.case import Case, CaseStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class DashboardStats:
    """Service for computing dashboard statistics."""

    def __init__(self, es: AsyncElasticsearch):
        """Initialize with Elasticsearch client."""
        self.es = es
        self.index_prefix = settings.elasticsearch_index_prefix

    async def get_overview_stats(
        self,
        db: AsyncSession,
        time_range: str = "24h",
    ) -> dict[str, Any]:
        """Get overview statistics for dashboard.

        Args:
            db: Database session
            time_range: Time range for stats (1h, 24h, 7d, 30d)

        Returns:
            Dashboard statistics
        """
        tenant_id = get_current_tenant_id()

        # Parse time range
        range_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        since = datetime.now(UTC) - delta

        # Get alert stats
        alert_stats = await self._get_alert_stats(db, tenant_id, since)

        # Get case stats
        case_stats = await self._get_case_stats(db, tenant_id)

        # Get rule stats
        rule_stats = await self._get_rule_stats(db, tenant_id)

        # Get event stats from Elasticsearch
        event_stats = await self._get_event_stats(tenant_id, since)

        return {
            "time_range": time_range,
            "since": since.isoformat(),
            "alerts": alert_stats,
            "cases": case_stats,
            "rules": rule_stats,
            "events": event_stats,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def get_alert_timeline(
        self,
        db: AsyncSession,
        interval: str = "1h",
        time_range: str = "24h",
    ) -> list[dict[str, Any]]:
        """Get alert counts over time for timeline chart.

        Args:
            db: Database session
            interval: Bucket interval (15m, 1h, 4h)
            time_range: Time range

        Returns:
            List of time buckets with alert counts
        """
        tenant_id = get_current_tenant_id()

        # Parse time range
        range_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        since = datetime.now(UTC) - delta

        # Get index pattern
        if tenant_id:
            index_pattern = get_elasticsearch_pattern("alerts")
        else:
            index_pattern = f"{self.index_prefix}-alerts-*"

        # Elasticsearch date histogram aggregation
        try:
            response = await self.es.search(
                index=index_pattern,
                size=0,
                query={
                    "range": {
                        "@timestamp": {
                            "gte": since.isoformat(),
                            "lte": datetime.now(UTC).isoformat(),
                        }
                    }
                },
                aggs={
                    "alerts_over_time": {
                        "date_histogram": {
                            "field": "@timestamp",
                            "fixed_interval": interval,
                        },
                        "aggs": {"by_severity": {"terms": {"field": "severity"}}},
                    }
                },
            )

            buckets = response["aggregations"]["alerts_over_time"]["buckets"]
            return [
                {
                    "timestamp": bucket["key_as_string"],
                    "count": bucket["doc_count"],
                    "by_severity": {
                        sev["key"]: sev["doc_count"] for sev in bucket["by_severity"]["buckets"]
                    },
                }
                for bucket in buckets
            ]

        except Exception as e:
            logger.warning("Failed to get alert timeline: %s", str(e))
            return []

    async def get_top_rules(
        self,
        db: AsyncSession,
        limit: int = 10,
        time_range: str = "24h",
    ) -> list[dict[str, Any]]:
        """Get top triggering rules.

        Args:
            db: Database session
            limit: Number of rules to return
            time_range: Time range

        Returns:
            List of top rules with hit counts
        """
        tenant_id = get_current_tenant_id()

        # Get rules with recent hits
        query = (
            select(DetectionRule)
            .where(DetectionRule.status == RuleStatus.ENABLED)
            .order_by(DetectionRule.hit_count.desc())
            .limit(limit)
        )

        if tenant_id:
            query = query.where(DetectionRule.tenant_id == tenant_id)

        result = await db.execute(query)
        rules = result.scalars().all()

        return [
            {
                "id": str(rule.id),
                "name": rule.name,
                "severity": rule.severity.value,
                "hit_count": rule.hit_count,
                "last_run_at": rule.last_run_at.isoformat() if rule.last_run_at else None,
                "mitre_techniques": rule.mitre_techniques,
            }
            for rule in rules
        ]

    async def get_severity_distribution(
        self,
        db: AsyncSession,
        time_range: str = "24h",
    ) -> dict[str, int]:
        """Get alert severity distribution.

        Args:
            db: Database session
            time_range: Time range

        Returns:
            Severity counts
        """
        tenant_id = get_current_tenant_id()

        # Parse time range
        range_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        since = datetime.now(UTC) - delta

        query = (
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.created_at >= since)
            .group_by(Alert.severity)
        )

        if tenant_id:
            query = query.where(Alert.tenant_id == tenant_id)

        result = await db.execute(query)
        rows = result.all()

        return {row[0].value: row[1] for row in rows}

    async def get_mitre_heatmap(
        self,
        db: AsyncSession,
        time_range: str = "7d",
    ) -> dict[str, int]:
        """Get MITRE technique heatmap data.

        Args:
            db: Database session
            time_range: Time range

        Returns:
            Technique ID to count mapping
        """
        tenant_id = get_current_tenant_id()

        # Get index pattern
        if tenant_id:
            index_pattern = get_elasticsearch_pattern("alerts")
        else:
            index_pattern = f"{self.index_prefix}-alerts-*"

        # Parse time range
        range_map = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(days=7))
        since = datetime.now(UTC) - delta

        try:
            response = await self.es.search(
                index=index_pattern,
                size=0,
                query={
                    "range": {
                        "@timestamp": {
                            "gte": since.isoformat(),
                        }
                    }
                },
                aggs={
                    "techniques": {
                        "terms": {
                            "field": "mitre_techniques",
                            "size": 100,
                        }
                    }
                },
            )

            buckets = response["aggregations"]["techniques"]["buckets"]
            return {bucket["key"]: bucket["doc_count"] for bucket in buckets}

        except Exception as e:
            logger.warning("Failed to get MITRE heatmap: %s", str(e))
            return {}

    async def _get_alert_stats(
        self,
        db: AsyncSession,
        tenant_id: Any,
        since: datetime,
    ) -> dict[str, Any]:
        """Get alert statistics."""
        base_query = select(func.count(Alert.id)).where(Alert.created_at >= since)
        if tenant_id:
            base_query = base_query.where(Alert.tenant_id == tenant_id)

        # Total alerts
        result = await db.execute(base_query)
        total = result.scalar() or 0

        # Open alerts
        open_query = base_query.where(Alert.status == AlertStatus.OPEN)
        result = await db.execute(open_query)
        open_count = result.scalar() or 0

        # Critical alerts
        critical_query = base_query.where(Alert.severity == AlertSeverity.CRITICAL)
        result = await db.execute(critical_query)
        critical_count = result.scalar() or 0

        # High alerts
        high_query = base_query.where(Alert.severity == AlertSeverity.HIGH)
        result = await db.execute(high_query)
        high_count = result.scalar() or 0

        return {
            "total": total,
            "open": open_count,
            "critical": critical_count,
            "high": high_count,
        }

    async def _get_case_stats(
        self,
        db: AsyncSession,
        tenant_id: Any,
    ) -> dict[str, Any]:
        """Get case statistics."""
        base_query = select(func.count(Case.id))
        if tenant_id:
            base_query = base_query.where(Case.tenant_id == tenant_id)

        # Total cases
        result = await db.execute(base_query)
        total = result.scalar() or 0

        # Active cases
        active_statuses = [CaseStatus.NEW, CaseStatus.INVESTIGATING, CaseStatus.CONTAINED]
        active_query = base_query.where(Case.status.in_(active_statuses))
        result = await db.execute(active_query)
        active = result.scalar() or 0

        return {
            "total": total,
            "active": active,
        }

    async def _get_rule_stats(
        self,
        db: AsyncSession,
        tenant_id: Any,
    ) -> dict[str, Any]:
        """Get rule statistics."""
        base_query = select(func.count(DetectionRule.id))
        if tenant_id:
            base_query = base_query.where(DetectionRule.tenant_id == tenant_id)

        # Total rules
        result = await db.execute(base_query)
        total = result.scalar() or 0

        # Enabled rules
        enabled_query = base_query.where(DetectionRule.status == RuleStatus.ENABLED)
        result = await db.execute(enabled_query)
        enabled = result.scalar() or 0

        return {
            "total": total,
            "enabled": enabled,
        }

    async def _get_event_stats(
        self,
        tenant_id: Any,
        since: datetime,
    ) -> dict[str, Any]:
        """Get event statistics from Elasticsearch."""
        # Get index pattern
        if tenant_id:
            index_pattern = get_elasticsearch_pattern("events")
        else:
            index_pattern = f"{self.index_prefix}-events-*"

        try:
            response = await self.es.count(
                index=index_pattern,
                query={
                    "range": {
                        "@timestamp": {
                            "gte": since.isoformat(),
                        }
                    }
                },
            )

            return {
                "total": response["count"],
            }

        except Exception as e:
            logger.warning("Failed to get event stats: %s", str(e))
            return {"total": 0}


# Module-level instance
_dashboard_stats: DashboardStats | None = None


async def get_dashboard_stats() -> DashboardStats:
    """Get the dashboard stats service."""
    global _dashboard_stats
    if _dashboard_stats is None:
        from app.database import get_elasticsearch

        es = await get_elasticsearch()
        _dashboard_stats = DashboardStats(es)
    return _dashboard_stats
