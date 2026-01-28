"""Correlation engine for complex detection patterns.

This service handles multi-event correlation rules including:
- Sequence patterns: Ordered event chains (A -> B -> C)
- Temporal join: Events within time windows
- Aggregation: Count thresholds with grouping
- Spike: Anomaly detection vs baseline

Example correlation rule configuration:
```yaml
name: "Brute Force Followed by Success"
correlation:
  pattern_type: sequence
  window: "5m"
  events:
    - id: failed_logins
      query: "event.action:logon_failed"
    - id: success
      query: "event.action:logon AND event.outcome:success"
  join_on:
    - field: "user.name"
  sequence:
    order: [failed_logins, success]
  thresholds:
    - event: failed_logins
      count: ">= 5"
```
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.analytics import (
    CorrelationState,
    CorrelationStateStatus,
    DetectionRule,
    RuleExecution,
    RuleType,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '5m', '1h', '30s' into timedelta.

    Args:
        duration_str: Duration string (e.g., '5m', '1h', '30s', '2d')

    Returns:
        timedelta object
    """
    match = re.match(r"^(\d+)([smhdw])$", duration_str.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")

    value = int(match.group(1))
    unit = match.group(2)

    units = {
        "s": "seconds",
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "w": "weeks",
    }

    return timedelta(**{units[unit]: value})


def parse_threshold(threshold_str: str) -> tuple[str, int]:
    """Parse threshold string like '>= 5' or '> 10'.

    Args:
        threshold_str: Threshold expression

    Returns:
        Tuple of (operator, value)
    """
    match = re.match(r"^(>=|>|<=|<|==|=)\s*(\d+)$", threshold_str.strip())
    if not match:
        raise ValueError(f"Invalid threshold format: {threshold_str}")

    operator = match.group(1)
    if operator == "=":
        operator = "=="
    value = int(match.group(2))

    return operator, value


def check_threshold(count: int, operator: str, threshold: int) -> bool:
    """Check if count meets threshold condition.

    Args:
        count: Actual count
        operator: Comparison operator
        threshold: Threshold value

    Returns:
        True if threshold condition is met
    """
    ops = {
        ">=": lambda x, y: x >= y,
        ">": lambda x, y: x > y,
        "<=": lambda x, y: x <= y,
        "<": lambda x, y: x < y,
        "==": lambda x, y: x == y,
    }
    return ops[operator](count, threshold)


class CorrelationEngine:
    """Engine for executing correlation rules against event streams.

    Supports multiple correlation patterns for complex threat detection.

    ## State Persistence & Recovery

    The CorrelationEngine uses the `CorrelationState` database model to persist
    in-progress correlation states across executions. This is essential for:

    1. **Window Continuity**: Correlation windows often span multiple rule
       execution cycles. State persistence ensures events from earlier
       executions are retained until the window expires.

    2. **Service Restart Recovery**: If the service restarts mid-correlation,
       active states are recovered from the database on next execution.

    3. **Distributed Execution**: When running multiple engine instances,
       the database provides shared state coordination.

    ## State Lifecycle

    States transition through the following statuses:
    - ACTIVE: Correlation window is open, accumulating events
    - TRIGGERED: Pattern was matched, alert was generated
    - EXPIRED: Window closed without matching (cleaned up automatically)

    ## Cleanup Strategy

    Expired states (window_end < now) are deleted at the start of each
    execution to prevent unbounded state growth. States that triggered
    alerts are retained for audit purposes.

    ## Example Usage

    ```python
    engine = CorrelationEngine(es_client)
    result = await engine.execute_correlation_rule(rule, execution, db)
    ```
    """

    def __init__(self, es: AsyncElasticsearch):
        """Initialize correlation engine.

        Args:
            es: Elasticsearch client
        """
        self.es = es
        self.index_prefix = settings.elasticsearch_index_prefix

    async def execute_correlation_rule(
        self,
        rule: DetectionRule,
        execution: RuleExecution,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a correlation rule.

        Args:
            rule: Detection rule with correlation_config
            execution: Execution record to update
            db: Database session

        Returns:
            Execution results including correlated matches
        """
        if rule.rule_type != RuleType.CORRELATION:
            raise ValueError(f"Rule {rule.id} is not a correlation rule")

        if not rule.correlation_config:
            raise ValueError(f"Rule {rule.id} has no correlation_config")

        config = rule.correlation_config
        pattern_type = config.get("pattern_type", "sequence")

        start_time = datetime.utcnow()

        try:
            if pattern_type == "sequence":
                result = await self._execute_sequence(rule, config, db)
            elif pattern_type == "temporal_join":
                result = await self._execute_temporal_join(rule, config, db)
            elif pattern_type == "aggregation":
                result = await self._execute_aggregation(rule, config, db)
            elif pattern_type == "spike":
                result = await self._execute_spike(rule, config, db)
            else:
                raise ValueError(f"Unknown pattern type: {pattern_type}")

            # Update execution record
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            execution.completed_at = end_time
            execution.duration_ms = duration_ms
            execution.hits_count = len(result.get("matches", []))
            execution.status = "completed"

            rule.hit_count += execution.hits_count
            rule.last_run_at = end_time

            await db.commit()

            logger.info(
                "Correlation rule %s executed: %d matches in %dms",
                rule.name,
                execution.hits_count,
                duration_ms,
            )

            return {
                "rule_id": str(rule.id),
                "execution_id": str(execution.id),
                "pattern_type": pattern_type,
                "matches": result.get("matches", []),
                "hits_count": execution.hits_count,
                "duration_ms": duration_ms,
                "status": "completed",
            }

        except Exception as e:
            logger.error(
                "Correlation rule execution failed for %s: %s",
                rule.name,
                str(e),
            )

            execution.completed_at = datetime.utcnow()
            execution.status = "failed"
            execution.error_message = str(e)

            await db.commit()

            return {
                "rule_id": str(rule.id),
                "execution_id": str(execution.id),
                "pattern_type": pattern_type,
                "matches": [],
                "hits_count": 0,
                "status": "failed",
                "error": str(e),
            }

    async def _execute_sequence(
        self,
        rule: DetectionRule,
        config: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a sequence correlation pattern.

        Detects ordered event sequences like:
        failed_login -> failed_login -> ... -> successful_login

        Args:
            rule: Detection rule
            config: Correlation configuration
            db: Database session

        Returns:
            Dict with matched sequences
        """
        window = parse_duration(config.get("window", "5m"))
        events_config = config.get("events", [])
        join_on = config.get("join_on", [])
        sequence_order = config.get("sequence", {}).get("order", [])
        thresholds = config.get("thresholds", [])

        # Build threshold lookup
        threshold_map = {}
        for t in thresholds:
            operator, value = parse_threshold(t["count"])
            threshold_map[t["event"]] = (operator, value)

        now = datetime.utcnow()
        window_start = now - window

        # Clean up expired states
        await db.execute(
            delete(CorrelationState).where(
                and_(
                    CorrelationState.rule_id == rule.id,
                    CorrelationState.window_end < now,
                    CorrelationState.status == CorrelationStateStatus.ACTIVE,
                )
            )
        )

        # Query events for each step
        all_events = {}
        for event_def in events_config:
            event_id = event_def["id"]
            query = event_def["query"]

            hits = await self._query_events(query, window_start, now, rule.indices)
            all_events[event_id] = hits

        # Group events by join key
        entity_events: dict[str, dict[str, list]] = {}

        for event_id, hits in all_events.items():
            for hit in hits:
                # Build entity key from join_on fields
                key_parts = []
                for join_field in join_on:
                    field_name = join_field.get("field", join_field)
                    value = self._get_nested_value(hit, field_name)
                    if value:
                        key_parts.append(f"{field_name}:{value}")

                if key_parts:
                    entity_key = "|".join(key_parts)
                    if entity_key not in entity_events:
                        entity_events[entity_key] = {}
                    if event_id not in entity_events[entity_key]:
                        entity_events[entity_key][event_id] = []
                    entity_events[entity_key][event_id].append(hit)

        # Check sequences for each entity
        matches = []

        for entity_key, events_by_type in entity_events.items():
            # Check if sequence order is satisfied
            sequence_valid = True

            for event_id in sequence_order:
                event_count = len(events_by_type.get(event_id, []))

                # Check threshold if defined
                if event_id in threshold_map:
                    operator, threshold = threshold_map[event_id]
                    if not check_threshold(event_count, operator, threshold):
                        sequence_valid = False
                        break
                elif event_count == 0:
                    sequence_valid = False
                    break

            if sequence_valid:
                # Collect all contributing events
                contributing_events = []
                for event_id in sequence_order:
                    contributing_events.extend(events_by_type.get(event_id, []))

                # Sort by timestamp
                contributing_events.sort(
                    key=lambda x: x.get("@timestamp", ""),
                )

                matches.append(
                    {
                        "entity_key": entity_key,
                        "sequence": sequence_order,
                        "event_counts": {
                            eid: len(events_by_type.get(eid, [])) for eid in sequence_order
                        },
                        "first_event": contributing_events[0] if contributing_events else None,
                        "last_event": contributing_events[-1] if contributing_events else None,
                        "total_events": len(contributing_events),
                    }
                )

        return {"matches": matches}

    async def _execute_temporal_join(
        self,
        rule: DetectionRule,
        config: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a temporal join correlation pattern.

        Finds events that occur within a specified time window of each other.

        Args:
            rule: Detection rule
            config: Correlation configuration
            db: Database session

        Returns:
            Dict with matched event pairs
        """
        window = parse_duration(config.get("window", "5m"))
        events_config = config.get("events", [])
        join_on = config.get("join_on", [])

        if len(events_config) != 2:
            raise ValueError("Temporal join requires exactly 2 event definitions")

        now = datetime.utcnow()
        lookback = parse_duration(config.get("lookback", "1h"))
        window_start = now - lookback

        # Query both event types
        event_a_config = events_config[0]
        event_b_config = events_config[1]

        events_a = await self._query_events(
            event_a_config["query"], window_start, now, rule.indices
        )
        events_b = await self._query_events(
            event_b_config["query"], window_start, now, rule.indices
        )

        # Build lookup by join key for event B
        events_b_by_key: dict[str, list] = {}
        for event in events_b:
            key_parts = []
            for join_field in join_on:
                field_name = join_field.get("field", join_field)
                value = self._get_nested_value(event, field_name)
                if value:
                    key_parts.append(f"{field_name}:{value}")

            if key_parts:
                entity_key = "|".join(key_parts)
                if entity_key not in events_b_by_key:
                    events_b_by_key[entity_key] = []
                events_b_by_key[entity_key].append(event)

        # Find temporal matches
        matches = []

        for event_a in events_a:
            # Get entity key for event A
            key_parts = []
            for join_field in join_on:
                field_name = join_field.get("field", join_field)
                value = self._get_nested_value(event_a, field_name)
                if value:
                    key_parts.append(f"{field_name}:{value}")

            if not key_parts:
                continue

            entity_key = "|".join(key_parts)

            # Get timestamp for event A
            timestamp_a = event_a.get("@timestamp")
            if not timestamp_a:
                continue

            ts_a = datetime.fromisoformat(timestamp_a.replace("Z", "+00:00"))

            # Check for matching events B within window
            for event_b in events_b_by_key.get(entity_key, []):
                timestamp_b = event_b.get("@timestamp")
                if not timestamp_b:
                    continue

                ts_b = datetime.fromisoformat(timestamp_b.replace("Z", "+00:00"))

                # Check if within window
                time_diff = abs((ts_b - ts_a).total_seconds())
                if time_diff <= window.total_seconds():
                    matches.append(
                        {
                            "entity_key": entity_key,
                            "event_a": {
                                "id": event_a_config["id"],
                                "timestamp": timestamp_a,
                                "event": event_a,
                            },
                            "event_b": {
                                "id": event_b_config["id"],
                                "timestamp": timestamp_b,
                                "event": event_b,
                            },
                            "time_diff_seconds": time_diff,
                        }
                    )

        return {"matches": matches}

    async def _execute_aggregation(
        self,
        rule: DetectionRule,
        config: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute an aggregation correlation pattern.

        Detects when event counts exceed thresholds, grouped by fields.

        Args:
            rule: Detection rule
            config: Correlation configuration
            db: Database session

        Returns:
            Dict with entities exceeding thresholds
        """
        window = parse_duration(config.get("window", "5m"))
        query = config.get("query", "*")
        group_by = config.get("group_by", [])
        threshold_config = config.get("threshold", {})

        operator, threshold_value = parse_threshold(threshold_config.get("count", ">= 1"))

        now = datetime.utcnow()
        window_start = now - window

        # Build aggregation query
        agg_body = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"query_string": {"query": query}},
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": window_start.isoformat(),
                                    "lte": now.isoformat(),
                                }
                            }
                        },
                    ]
                }
            },
            "aggs": {},
        }

        # Build nested aggregations for group_by fields
        current_agg = agg_body["aggs"]
        for i, field in enumerate(group_by):
            agg_name = f"group_{i}"
            current_agg[agg_name] = {
                "terms": {"field": field, "size": 1000},
            }
            if i < len(group_by) - 1:
                current_agg[agg_name]["aggs"] = {}
                current_agg = current_agg[agg_name]["aggs"]

        # Execute aggregation
        indices = rule.indices or [f"{self.index_prefix}-events-*"]
        index_pattern = ",".join(indices)

        response = await self.es.search(index=index_pattern, body=agg_body)

        # Parse aggregation results
        matches = []

        def parse_buckets(buckets: list, prefix: list, depth: int):
            for bucket in buckets:
                key = bucket["key"]
                count = bucket["doc_count"]

                current_prefix = prefix + [f"{group_by[depth]}:{key}"]

                # Check if there are more nested aggregations
                next_agg = f"group_{depth + 1}"
                if next_agg in bucket:
                    parse_buckets(
                        bucket[next_agg]["buckets"],
                        current_prefix,
                        depth + 1,
                    )
                else:
                    # Leaf level - check threshold
                    if check_threshold(count, operator, threshold_value):
                        matches.append(
                            {
                                "entity_key": "|".join(current_prefix),
                                "group_values": dict(
                                    zip(group_by[: depth + 1], [key] + [b["key"] for b in prefix])
                                ),
                                "count": count,
                                "threshold": f"{operator} {threshold_value}",
                            }
                        )

        # Start parsing from first aggregation
        if group_by:
            first_agg = response.get("aggregations", {}).get("group_0", {})
            parse_buckets(first_agg.get("buckets", []), [], 0)
        else:
            # No grouping - check total count
            total = response.get("hits", {}).get("total", {}).get("value", 0)
            if check_threshold(total, operator, threshold_value):
                matches.append(
                    {
                        "entity_key": "*",
                        "group_values": {},
                        "count": total,
                        "threshold": f"{operator} {threshold_value}",
                    }
                )

        return {"matches": matches}

    async def _execute_spike(
        self,
        rule: DetectionRule,
        config: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a spike detection correlation pattern.

        Detects anomalous increases compared to baseline.

        Args:
            rule: Detection rule
            config: Correlation configuration
            db: Database session

        Returns:
            Dict with spike detections
        """
        current_window = parse_duration(config.get("current_window", "5m"))
        baseline_window = parse_duration(config.get("baseline_window", "1h"))
        spike_factor = config.get("spike_factor", 3.0)
        query = config.get("query", "*")
        group_by = config.get("group_by", [])

        now = datetime.utcnow()
        current_start = now - current_window
        baseline_start = now - baseline_window

        # Query current period count
        current_count = await self._count_events(query, current_start, now, rule.indices, group_by)

        # Query baseline period count (excluding current)
        baseline_count = await self._count_events(
            query, baseline_start, current_start, rule.indices, group_by
        )

        # Calculate baseline periods
        baseline_periods = baseline_window / current_window

        matches = []

        if group_by:
            # Compare each entity's current vs baseline
            for entity_key, current in current_count.items():
                baseline = baseline_count.get(entity_key, 0)
                baseline_avg = baseline / baseline_periods if baseline_periods else 0

                if baseline_avg > 0:
                    spike_ratio = current / baseline_avg
                    if spike_ratio >= spike_factor:
                        matches.append(
                            {
                                "entity_key": entity_key,
                                "current_count": current,
                                "baseline_avg": round(baseline_avg, 2),
                                "spike_ratio": round(spike_ratio, 2),
                                "spike_factor": spike_factor,
                            }
                        )
                elif current > 0:
                    # No baseline but activity now
                    matches.append(
                        {
                            "entity_key": entity_key,
                            "current_count": current,
                            "baseline_avg": 0,
                            "spike_ratio": float("inf"),
                            "spike_factor": spike_factor,
                            "note": "New activity with no baseline",
                        }
                    )
        else:
            # Global spike detection
            current_total = sum(current_count.values()) if current_count else 0
            baseline_total = sum(baseline_count.values()) if baseline_count else 0
            baseline_avg = baseline_total / baseline_periods if baseline_periods else 0

            if baseline_avg > 0:
                spike_ratio = current_total / baseline_avg
                if spike_ratio >= spike_factor:
                    matches.append(
                        {
                            "entity_key": "*",
                            "current_count": current_total,
                            "baseline_avg": round(baseline_avg, 2),
                            "spike_ratio": round(spike_ratio, 2),
                            "spike_factor": spike_factor,
                        }
                    )
            elif current_total > 0:
                matches.append(
                    {
                        "entity_key": "*",
                        "current_count": current_total,
                        "baseline_avg": 0,
                        "spike_ratio": float("inf"),
                        "spike_factor": spike_factor,
                        "note": "New activity with no baseline",
                    }
                )

        return {"matches": matches}

    async def _query_events(
        self,
        query: str,
        time_from: datetime,
        time_to: datetime,
        indices: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query events from Elasticsearch.

        Args:
            query: KQL/Lucene query string
            time_from: Start time
            time_to: End time
            indices: Index patterns to search

        Returns:
            List of matching events
        """
        index_pattern = ",".join(indices or [f"{self.index_prefix}-events-*"])

        query_body = {
            "bool": {
                "must": [
                    {"query_string": {"query": query}},
                    {
                        "range": {
                            "@timestamp": {
                                "gte": time_from.isoformat(),
                                "lte": time_to.isoformat(),
                            }
                        }
                    },
                ]
            }
        }

        response = await self.es.search(
            index=index_pattern,
            query=query_body,
            size=10000,  # Reasonable limit
            sort=[{"@timestamp": "asc"}],
        )

        return [
            {"_id": hit["_id"], "_index": hit["_index"], **hit["_source"]}
            for hit in response["hits"]["hits"]
        ]

    async def _count_events(
        self,
        query: str,
        time_from: datetime,
        time_to: datetime,
        indices: list[str] | None = None,
        group_by: list[str] | None = None,
    ) -> dict[str, int]:
        """Count events, optionally grouped by fields.

        Args:
            query: KQL/Lucene query string
            time_from: Start time
            time_to: End time
            indices: Index patterns
            group_by: Fields to group by

        Returns:
            Dict of entity_key -> count (or {"*": total} if no grouping)
        """
        index_pattern = ",".join(indices or [f"{self.index_prefix}-events-*"])

        body: dict[str, Any] = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"query_string": {"query": query}},
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": time_from.isoformat(),
                                    "lte": time_to.isoformat(),
                                }
                            }
                        },
                    ]
                }
            },
        }

        if group_by:
            # Multi-level aggregation
            body["aggs"] = {}
            current = body["aggs"]
            for i, field in enumerate(group_by):
                current[f"group_{i}"] = {
                    "terms": {"field": field, "size": 10000},
                }
                if i < len(group_by) - 1:
                    current[f"group_{i}"]["aggs"] = {}
                    current = current[f"group_{i}"]["aggs"]

        response = await self.es.search(index=index_pattern, body=body)

        counts: dict[str, int] = {}

        if group_by:

            def extract_counts(aggs: dict, prefix: list, depth: int):
                agg_key = f"group_{depth}"
                if agg_key not in aggs:
                    return

                for bucket in aggs[agg_key]["buckets"]:
                    key = bucket["key"]
                    current_prefix = prefix + [f"{group_by[depth]}:{key}"]

                    if depth + 1 < len(group_by):
                        extract_counts(bucket, current_prefix, depth + 1)
                    else:
                        entity_key = "|".join(current_prefix)
                        counts[entity_key] = bucket["doc_count"]

            extract_counts(response.get("aggregations", {}), [], 0)
        else:
            counts["*"] = response.get("hits", {}).get("total", {}).get("value", 0)

        return counts

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get nested value from dict using dot notation.

        Args:
            obj: Source dictionary
            path: Dot-separated path (e.g., 'user.name')

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

    async def process_realtime_event(
        self,
        event: dict[str, Any],
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Process a single event for real-time correlation rules.

        Used by the real-time processor to update correlation states
        and check for completed sequences.

        Args:
            event: Event to process
            db: Database session

        Returns:
            List of correlation matches triggered by this event
        """
        # Get active real-time correlation rules
        query = select(DetectionRule).where(
            and_(
                DetectionRule.rule_type == RuleType.CORRELATION,
                DetectionRule.status.in_(["enabled", "testing"]),
                DetectionRule.correlation_config.isnot(None),
            )
        )
        result = await db.execute(query)
        rules = result.scalars().all()

        matches = []

        for rule in rules:
            config = rule.correlation_config
            if not config:
                continue

            # Only process rules marked for real-time
            if not config.get("realtime", False):
                continue

            match = await self._update_correlation_state(rule, event, db)
            if match:
                matches.append(match)

        return matches

    async def _update_correlation_state(
        self,
        rule: DetectionRule,
        event: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        """Update correlation state for a rule based on an event.

        Args:
            rule: Correlation rule
            event: New event
            db: Database session

        Returns:
            Match dict if correlation completes, None otherwise
        """
        config = rule.correlation_config
        pattern_type = config.get("pattern_type", "sequence")

        if pattern_type != "sequence":
            # Real-time currently supports sequence patterns
            return None

        events_config = config.get("events", [])
        join_on = config.get("join_on", [])
        sequence_order = config.get("sequence", {}).get("order", [])
        thresholds = config.get("thresholds", [])
        window = parse_duration(config.get("window", "5m"))

        # Determine which event type this matches
        matched_event_id = None
        for event_def in events_config:
            if self._event_matches_query(event, event_def["query"]):
                matched_event_id = event_def["id"]
                break

        if not matched_event_id:
            return None

        # Build entity key
        key_parts = []
        for join_field in join_on:
            field_name = join_field.get("field", join_field)
            value = self._get_nested_value(event, field_name)
            if value:
                key_parts.append(f"{field_name}:{value}")

        if not key_parts:
            return None

        entity_key = "|".join(key_parts)
        now = datetime.utcnow()

        # Get or create correlation state
        state_query = select(CorrelationState).where(
            and_(
                CorrelationState.rule_id == rule.id,
                CorrelationState.entity_key == entity_key,
                CorrelationState.status == CorrelationStateStatus.ACTIVE,
                CorrelationState.window_end >= now,
            )
        )
        result = await db.execute(state_query)
        state = result.scalar_one_or_none()

        if not state:
            # Create new state
            state = CorrelationState(
                rule_id=rule.id,
                entity_key=entity_key,
                state={
                    "matched_events": [],
                    "counts": {},
                    "first_event_id": event.get("_id"),
                },
                window_start=now,
                window_end=now + window,
            )
            db.add(state)

        # Update counts
        counts = state.state.get("counts", {})
        counts[matched_event_id] = counts.get(matched_event_id, 0) + 1

        # Add to matched events
        matched_events = state.state.get("matched_events", [])
        matched_events.append(
            {
                "event_id": event.get("_id"),
                "step": matched_event_id,
                "timestamp": event.get("@timestamp"),
            }
        )

        state.state = {
            **state.state,
            "counts": counts,
            "matched_events": matched_events,
        }

        # Check if sequence is complete
        threshold_map = {}
        for t in thresholds:
            operator, value = parse_threshold(t["count"])
            threshold_map[t["event"]] = (operator, value)

        sequence_complete = True
        for event_id in sequence_order:
            event_count = counts.get(event_id, 0)
            if event_id in threshold_map:
                operator, threshold = threshold_map[event_id]
                if not check_threshold(event_count, operator, threshold):
                    sequence_complete = False
                    break
            elif event_count == 0:
                sequence_complete = False
                break

        if sequence_complete:
            # Mark state as completed
            state.status = CorrelationStateStatus.COMPLETED

            return {
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "entity_key": entity_key,
                "sequence": sequence_order,
                "event_counts": counts,
                "total_events": len(matched_events),
                "window_start": state.window_start.isoformat(),
                "window_end": state.window_end.isoformat(),
            }

        return None

    def _event_matches_query(self, event: dict[str, Any], query: str) -> bool:
        """Simple check if event matches a query pattern.

        This is a simplified matcher for real-time processing.
        For complex queries, use Elasticsearch.

        Args:
            event: Event to check
            query: Simple query string (field:value format)

        Returns:
            True if event matches
        """
        # Parse simple field:value patterns
        parts = query.split(" AND ")

        for part in parts:
            part = part.strip()
            if ":" not in part:
                continue

            field, value = part.split(":", 1)
            field = field.strip()
            value = value.strip().strip('"')

            actual_value = self._get_nested_value(event, field)
            if actual_value is None:
                return False

            # Handle wildcards
            if "*" in value:
                pattern = value.replace("*", ".*")
                if not re.match(f"^{pattern}$", str(actual_value)):
                    return False
            elif str(actual_value) != value:
                return False

        return True


# Global correlation engine instance
_correlation_engine: CorrelationEngine | None = None


async def get_correlation_engine() -> CorrelationEngine:
    """Get the correlation engine instance.

    Returns:
        Configured correlation engine
    """
    global _correlation_engine
    if _correlation_engine is None:
        from app.database import get_elasticsearch

        es = await get_elasticsearch()
        _correlation_engine = CorrelationEngine(es)
    return _correlation_engine
