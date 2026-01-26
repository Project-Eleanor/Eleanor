"""Real-time event processor for sub-minute detection latency.

This service processes events from Redis Streams and:
- Executes real-time detection rules
- Updates correlation states
- Generates alerts for matches
- Sends WebSocket notifications

Designed for high-throughput event processing with minimal latency.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker, get_elasticsearch
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.analytics import DetectionRule, RuleExecution, RuleStatus, RuleType
from app.services.correlation_engine import CorrelationEngine, get_correlation_engine
from app.services.event_buffer import (
    ALERT_STREAM,
    CORRELATION_STREAM,
    EVENT_STREAM,
    EventBuffer,
    get_event_buffer,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class RealtimeProcessor:
    """Real-time event processor for detection and correlation.

    Processes events from Redis Streams with sub-minute latency
    for real-time threat detection.
    """

    def __init__(
        self,
        event_buffer: EventBuffer,
        correlation_engine: CorrelationEngine,
    ):
        """Initialize real-time processor.

        Args:
            event_buffer: Event buffer for stream consumption
            correlation_engine: Correlation engine for rule execution
        """
        self.event_buffer = event_buffer
        self.correlation_engine = correlation_engine
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Processing metrics
        self.events_processed = 0
        self.alerts_generated = 0
        self.correlations_matched = 0
        self.errors = 0
        self._start_time: datetime | None = None

    async def start(self, workers: int = 4) -> None:
        """Start the real-time processor.

        Args:
            workers: Number of parallel processing workers
        """
        if self._running:
            logger.warning("Real-time processor already running")
            return

        self._running = True
        self._start_time = datetime.utcnow()

        logger.info("Starting real-time processor with %d workers", workers)

        # Start event processing workers
        for i in range(workers):
            task = asyncio.create_task(
                self._process_events_worker(f"worker-{i}"),
                name=f"realtime-worker-{i}",
            )
            self._tasks.append(task)

        # Start correlation state cleanup task
        cleanup_task = asyncio.create_task(
            self._cleanup_expired_states(),
            name="correlation-cleanup",
        )
        self._tasks.append(cleanup_task)

        # Start pending message recovery task
        recovery_task = asyncio.create_task(
            self._recover_pending_messages(),
            name="pending-recovery",
        )
        self._tasks.append(recovery_task)

        logger.info("Real-time processor started")

    async def stop(self) -> None:
        """Stop the real-time processor."""
        if not self._running:
            return

        logger.info("Stopping real-time processor...")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info(
            "Real-time processor stopped. Processed %d events, generated %d alerts",
            self.events_processed,
            self.alerts_generated,
        )

    async def _process_events_worker(self, worker_id: str) -> None:
        """Event processing worker.

        Args:
            worker_id: Unique worker identifier
        """
        logger.info("Worker %s started", worker_id)

        while self._running:
            try:
                # Consume batch of events
                events = await self.event_buffer.consume_events(
                    stream=EVENT_STREAM,
                    count=100,
                    block_ms=1000,
                )

                if not events:
                    continue

                # Process each event
                message_ids_to_ack = []
                async with async_session_maker() as db:
                    for message_id, event in events:
                        try:
                            await self._process_single_event(event, db)
                            message_ids_to_ack.append(message_id)
                            self.events_processed += 1
                        except Exception as e:
                            logger.error(
                                "Worker %s failed to process event %s: %s",
                                worker_id,
                                message_id,
                                str(e),
                            )
                            self.errors += 1

                            # Move to dead letter queue after 3 failures
                            await self.event_buffer.move_to_dlq(
                                message_id,
                                event,
                                str(e),
                            )

                    await db.commit()

                # Acknowledge processed messages
                if message_ids_to_ack:
                    await self.event_buffer.acknowledge(message_ids_to_ack)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker %s error: %s", worker_id, str(e))
                self.errors += 1
                await asyncio.sleep(1)

        logger.info("Worker %s stopped", worker_id)

    async def _process_single_event(
        self,
        event: dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Process a single event through detection rules.

        Args:
            event: Event to process
            db: Database session
        """
        # Get real-time rules that should evaluate this event
        rules = await self._get_matching_rules(event, db)

        for rule in rules:
            try:
                if rule.rule_type == RuleType.CORRELATION:
                    # Process through correlation engine
                    matches = await self.correlation_engine.process_realtime_event(
                        event, db
                    )

                    for match in matches:
                        await self._generate_alert(rule, match, event, db)
                        self.correlations_matched += 1

                elif rule.rule_type == RuleType.REALTIME:
                    # Simple pattern match rule
                    if self._event_matches_rule(event, rule):
                        await self._generate_alert(
                            rule,
                            {"event": event},
                            event,
                            db,
                        )

            except Exception as e:
                logger.error(
                    "Failed to process rule %s for event: %s",
                    rule.name,
                    str(e),
                )

    async def _get_matching_rules(
        self,
        event: dict[str, Any],
        db: AsyncSession,
    ) -> list[DetectionRule]:
        """Get rules that should evaluate this event.

        Args:
            event: Event to match
            db: Database session

        Returns:
            List of applicable rules
        """
        # Get enabled real-time and correlation rules
        query = select(DetectionRule).where(
            DetectionRule.status == RuleStatus.ENABLED,
            DetectionRule.rule_type.in_([RuleType.REALTIME, RuleType.CORRELATION]),
        )
        result = await db.execute(query)
        rules = result.scalars().all()

        # Filter rules based on data source matching
        matching_rules = []
        event_index = event.get("_index", "")
        event_source = event.get("event", {}).get("module", "")

        for rule in rules:
            # Check if event index matches rule indices
            if rule.indices:
                matched = False
                for index_pattern in rule.indices:
                    if self._match_pattern(event_index, index_pattern):
                        matched = True
                        break
                if not matched:
                    continue

            # Check data sources if specified
            if rule.data_sources:
                if event_source not in rule.data_sources:
                    continue

            # For correlation rules, check if marked for real-time
            if rule.rule_type == RuleType.CORRELATION:
                config = rule.correlation_config or {}
                if not config.get("realtime", False):
                    continue

            matching_rules.append(rule)

        return matching_rules

    def _event_matches_rule(
        self,
        event: dict[str, Any],
        rule: DetectionRule,
    ) -> bool:
        """Check if event matches a simple rule query.

        Args:
            event: Event to check
            rule: Detection rule

        Returns:
            True if event matches
        """
        # Simple field:value pattern matching
        query = rule.query

        # Handle AND conditions
        conditions = query.split(" AND ")

        for condition in conditions:
            condition = condition.strip()

            if ":" not in condition:
                continue

            field, value = condition.split(":", 1)
            field = field.strip()
            value = value.strip().strip('"')

            # Get field value from event
            actual_value = self._get_nested_value(event, field)

            if actual_value is None:
                return False

            # Handle wildcards
            if "*" in value:
                import re
                pattern = value.replace("*", ".*")
                if not re.match(f"^{pattern}$", str(actual_value)):
                    return False
            elif str(actual_value) != value:
                return False

        return True

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get nested value using dot notation.

        Args:
            obj: Source dictionary
            path: Dot-separated path

        Returns:
            Value at path or None
        """
        parts = path.split(".")
        current = obj

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _match_pattern(self, value: str, pattern: str) -> bool:
        """Match string against wildcard pattern.

        Args:
            value: String to match
            pattern: Pattern with * wildcards

        Returns:
            True if matches
        """
        import re
        regex = pattern.replace("*", ".*")
        return bool(re.match(f"^{regex}$", value))

    async def _generate_alert(
        self,
        rule: DetectionRule,
        match: dict[str, Any],
        trigger_event: dict[str, Any],
        db: AsyncSession,
    ) -> Alert:
        """Generate an alert from a rule match.

        Args:
            rule: Matched detection rule
            match: Match details
            trigger_event: Event that triggered the match
            db: Database session

        Returns:
            Created alert
        """
        # Map rule severity to alert severity
        severity_map = {
            "informational": AlertSeverity.INFORMATIONAL,
            "low": AlertSeverity.LOW,
            "medium": AlertSeverity.MEDIUM,
            "high": AlertSeverity.HIGH,
            "critical": AlertSeverity.CRITICAL,
        }

        alert = Alert(
            title=f"[{rule.name}] Detection Alert",
            description=self._build_alert_description(rule, match),
            severity=severity_map.get(rule.severity.value, AlertSeverity.MEDIUM),
            status=AlertStatus.NEW,
            source="realtime_processor",
            rule_id=str(rule.id),
            raw_event=trigger_event,
            mitre_tactics=rule.mitre_tactics,
            mitre_techniques=rule.mitre_techniques,
            tags=rule.tags,
        )

        db.add(alert)
        await db.flush()

        # Update rule hit count
        rule.hit_count += 1

        # Publish alert to stream for notifications
        await self.event_buffer.publish_event(
            {
                "alert_id": str(alert.id),
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "severity": alert.severity.value,
                "title": alert.title,
                "timestamp": datetime.utcnow().isoformat(),
            },
            stream=ALERT_STREAM,
        )

        self.alerts_generated += 1
        logger.info(
            "Generated alert for rule %s: %s",
            rule.name,
            alert.id,
        )

        return alert

    def _build_alert_description(
        self,
        rule: DetectionRule,
        match: dict[str, Any],
    ) -> str:
        """Build alert description from rule and match.

        Args:
            rule: Detection rule
            match: Match details

        Returns:
            Formatted description
        """
        lines = [
            f"Detection rule '{rule.name}' triggered.",
            "",
            f"Rule Description: {rule.description or 'N/A'}",
            "",
            "Match Details:",
        ]

        # Add match-specific details
        if "entity_key" in match:
            lines.append(f"  Entity: {match['entity_key']}")

        if "sequence" in match:
            lines.append(f"  Sequence: {' -> '.join(match['sequence'])}")

        if "event_counts" in match:
            counts = match["event_counts"]
            lines.append(f"  Event Counts: {counts}")

        if "spike_ratio" in match:
            lines.append(f"  Spike Ratio: {match['spike_ratio']}x baseline")

        if "time_diff_seconds" in match:
            lines.append(f"  Time Between Events: {match['time_diff_seconds']}s")

        # Add MITRE ATT&CK mapping
        if rule.mitre_tactics or rule.mitre_techniques:
            lines.append("")
            lines.append("MITRE ATT&CK:")
            if rule.mitre_tactics:
                lines.append(f"  Tactics: {', '.join(rule.mitre_tactics)}")
            if rule.mitre_techniques:
                lines.append(f"  Techniques: {', '.join(rule.mitre_techniques)}")

        return "\n".join(lines)

    async def _cleanup_expired_states(self) -> None:
        """Periodically clean up expired correlation states."""
        while self._running:
            try:
                async with async_session_maker() as db:
                    from sqlalchemy import delete, and_
                    from app.models.analytics import CorrelationState, CorrelationStateStatus

                    now = datetime.utcnow()

                    # Delete expired active states
                    result = await db.execute(
                        delete(CorrelationState).where(
                            and_(
                                CorrelationState.status == CorrelationStateStatus.ACTIVE,
                                CorrelationState.window_end < now,
                            )
                        )
                    )

                    if result.rowcount > 0:
                        logger.info(
                            "Cleaned up %d expired correlation states",
                            result.rowcount,
                        )

                    # Delete old completed states (older than 24h)
                    from datetime import timedelta
                    old_threshold = now - timedelta(hours=24)

                    await db.execute(
                        delete(CorrelationState).where(
                            and_(
                                CorrelationState.status == CorrelationStateStatus.COMPLETED,
                                CorrelationState.updated_at < old_threshold,
                            )
                        )
                    )

                    await db.commit()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Correlation cleanup error: %s", str(e))

            # Run every minute
            await asyncio.sleep(60)

    async def _recover_pending_messages(self) -> None:
        """Recover pending messages from failed consumers."""
        while self._running:
            try:
                # Wait before first recovery attempt
                await asyncio.sleep(30)

                # Claim pending messages older than 1 minute
                claimed = await self.event_buffer.claim_pending(
                    stream=EVENT_STREAM,
                    min_idle_ms=60000,
                    count=100,
                )

                if claimed:
                    logger.info("Recovered %d pending messages", len(claimed))

                    # Process recovered messages
                    async with async_session_maker() as db:
                        message_ids = []
                        for message_id, event in claimed:
                            try:
                                await self._process_single_event(event, db)
                                message_ids.append(message_id)
                            except Exception as e:
                                logger.error(
                                    "Failed to process recovered message %s: %s",
                                    message_id,
                                    str(e),
                                )
                                await self.event_buffer.move_to_dlq(
                                    message_id, event, str(e)
                                )

                        await db.commit()

                        if message_ids:
                            await self.event_buffer.acknowledge(message_ids)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Pending recovery error: %s", str(e))

            # Run every 30 seconds
            await asyncio.sleep(30)

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics.

        Returns:
            Processing statistics
        """
        uptime = None
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return {
            "running": self._running,
            "uptime_seconds": uptime,
            "events_processed": self.events_processed,
            "alerts_generated": self.alerts_generated,
            "correlations_matched": self.correlations_matched,
            "errors": self.errors,
            "active_workers": len([t for t in self._tasks if not t.done()]),
        }


# Global processor instance
_realtime_processor: RealtimeProcessor | None = None


async def get_realtime_processor() -> RealtimeProcessor:
    """Get the global real-time processor instance.

    Returns:
        Configured processor
    """
    global _realtime_processor
    if _realtime_processor is None:
        event_buffer = await get_event_buffer()
        correlation_engine = await get_correlation_engine()
        _realtime_processor = RealtimeProcessor(event_buffer, correlation_engine)
    return _realtime_processor


async def start_realtime_processor(workers: int = 4) -> None:
    """Start the global real-time processor.

    Args:
        workers: Number of processing workers
    """
    processor = await get_realtime_processor()
    await processor.start(workers=workers)


async def stop_realtime_processor() -> None:
    """Stop the global real-time processor."""
    global _realtime_processor
    if _realtime_processor:
        await _realtime_processor.stop()
        _realtime_processor = None
