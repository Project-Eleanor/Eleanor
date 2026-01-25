"""Alert generator service for creating alerts from detection rule matches.

This service handles:
- Alert creation from rule execution results
- Alert deduplication
- Alert enrichment
- Integration with case management
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.analytics import DetectionRule

logger = logging.getLogger(__name__)


class AlertGenerator:
    """Alert generation service.

    Creates alerts from detection rule matches and manages alert lifecycle.
    """

    async def create_alerts_from_rule_execution(
        self,
        rule: DetectionRule,
        execution_result: dict[str, Any],
        db: AsyncSession,
    ) -> list[Alert]:
        """Create alerts from rule execution results.

        Args:
            rule: The detection rule that matched
            execution_result: Results from detection engine
            db: Database session

        Returns:
            List of created alerts
        """
        hits = execution_result.get("hits", [])
        if not hits:
            return []

        # Skip if threshold not exceeded
        if not execution_result.get("threshold_exceeded", False):
            return []

        created_alerts = []

        # Check for existing open alerts for this rule (deduplication)
        existing_query = select(Alert).where(
            Alert.rule_id == rule.id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.IN_PROGRESS]),
        )
        existing_result = await db.execute(existing_query)
        existing_alert = existing_result.scalar_one_or_none()

        if existing_alert:
            # Update existing alert with new hit count
            existing_alert.hit_count += len(hits)
            existing_alert.last_seen_at = datetime.utcnow()
            existing_alert.updated_at = datetime.utcnow()

            # Add new events to alert
            existing_events = existing_alert.events or []
            for hit in hits[:100]:  # Limit stored events
                existing_events.append({
                    "timestamp": hit.get("@timestamp", datetime.utcnow().isoformat()),
                    "data": hit,
                })
            existing_alert.events = existing_events[-100:]  # Keep last 100

            created_alerts.append(existing_alert)
            logger.info(
                "Updated existing alert %s with %d new hits",
                existing_alert.id,
                len(hits),
            )
        else:
            # Create new alert
            alert = Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                title=f"Detection: {rule.name}",
                description=rule.description or f"Alert triggered by detection rule: {rule.name}",
                severity=self._map_severity(rule.severity),
                status=AlertStatus.OPEN,
                hit_count=len(hits),
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                mitre_tactics=rule.mitre_tactics,
                mitre_techniques=rule.mitre_techniques,
                tags=rule.tags,
                events=[
                    {
                        "timestamp": hit.get("@timestamp", datetime.utcnow().isoformat()),
                        "data": hit,
                    }
                    for hit in hits[:100]
                ],
            )

            # Extract entities from hits
            alert.entities = self._extract_entities(hits)

            db.add(alert)
            created_alerts.append(alert)
            logger.info(
                "Created new alert for rule %s with %d hits",
                rule.name,
                len(hits),
            )

        await db.commit()

        return created_alerts

    def _map_severity(self, rule_severity) -> AlertSeverity:
        """Map rule severity to alert severity.

        Args:
            rule_severity: RuleSeverity enum value

        Returns:
            Corresponding AlertSeverity
        """
        mapping = {
            "informational": AlertSeverity.INFORMATIONAL,
            "low": AlertSeverity.LOW,
            "medium": AlertSeverity.MEDIUM,
            "high": AlertSeverity.HIGH,
            "critical": AlertSeverity.CRITICAL,
        }
        return mapping.get(rule_severity.value, AlertSeverity.MEDIUM)

    def _extract_entities(self, hits: list[dict[str, Any]]) -> dict[str, list[str]]:
        """Extract unique entities from alert hits.

        Args:
            hits: List of matching documents

        Returns:
            Dictionary of entity types to unique values
        """
        entities: dict[str, set[str]] = {
            "hosts": set(),
            "users": set(),
            "ips": set(),
            "hashes": set(),
            "files": set(),
        }

        for hit in hits:
            # Extract hosts
            if "host" in hit and "name" in hit["host"]:
                entities["hosts"].add(hit["host"]["name"])

            # Extract users
            if "user" in hit and "name" in hit["user"]:
                entities["users"].add(hit["user"]["name"])

            # Extract IPs
            for ip_field in ["source.ip", "destination.ip", "host.ip"]:
                parts = ip_field.split(".")
                value = hit
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = None
                        break
                if value and isinstance(value, str):
                    entities["ips"].add(value)

            # Extract hashes
            if "file" in hit and "hash" in hit["file"]:
                for hash_type in ["sha256", "sha1", "md5"]:
                    if hash_type in hit["file"]["hash"]:
                        entities["hashes"].add(hit["file"]["hash"][hash_type])

            # Extract files
            if "file" in hit and "path" in hit["file"]:
                entities["files"].add(hit["file"]["path"])
            if "process" in hit and "executable" in hit["process"]:
                entities["files"].add(hit["process"]["executable"])

        # Convert sets to lists
        return {k: list(v) for k, v in entities.items() if v}

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> Alert | None:
        """Acknowledge an alert.

        Args:
            alert_id: Alert to acknowledge
            user_id: User acknowledging
            db: Database session

        Returns:
            Updated alert or None if not found
        """
        query = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(query)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()

        await db.commit()
        return alert

    async def close_alert(
        self,
        alert_id: UUID,
        resolution: str,
        user_id: UUID,
        db: AsyncSession,
        is_false_positive: bool = False,
    ) -> Alert | None:
        """Close an alert.

        Args:
            alert_id: Alert to close
            resolution: Resolution notes
            user_id: User closing
            db: Database session
            is_false_positive: Whether this was a false positive

        Returns:
            Updated alert or None if not found
        """
        query = select(Alert).where(Alert.id == alert_id)
        result = await db.execute(query)
        alert = result.scalar_one_or_none()

        if not alert:
            return None

        alert.status = AlertStatus.CLOSED
        alert.resolution = resolution
        alert.closed_by = user_id
        alert.closed_at = datetime.utcnow()
        alert.is_false_positive = is_false_positive
        alert.updated_at = datetime.utcnow()

        # Update rule false positive count if applicable
        if is_false_positive and alert.rule_id:
            rule_query = select(DetectionRule).where(DetectionRule.id == alert.rule_id)
            rule_result = await db.execute(rule_query)
            rule = rule_result.scalar_one_or_none()
            if rule:
                rule.false_positive_count += 1

        await db.commit()
        return alert


# Global alert generator instance
_alert_generator: AlertGenerator | None = None


def get_alert_generator() -> AlertGenerator:
    """Get the alert generator instance.

    Returns:
        Configured alert generator
    """
    global _alert_generator
    if _alert_generator is None:
        _alert_generator = AlertGenerator()
    return _alert_generator
