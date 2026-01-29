"""Rule builder API endpoints for visual correlation rule creation.

All endpoints require authentication since detection rules
are security-sensitive functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.core.tenant_context import get_current_tenant_id, get_elasticsearch_pattern
from app.database import get_db, get_elasticsearch
from app.models.user import User
from app.schemas.rule_builder import (
    AvailableField,
    CorrelationMatch,
    EventMatch,
    FieldsResponse,
    FieldType,
    PatternDefinition,
    PatternsResponse,
    PatternType,
    RuleBuilderConfig,
    RulePreviewRequest,
    RulePreviewResult,
    RuleTestRequest,
    RuleTestResult,
    RuleValidationResult,
    SigmaImportRequest,
    SigmaImportResult,
)
from app.services.correlation_engine import parse_duration
from app.services.rule_validator import (
    event_definition_to_query,
    get_rule_validator,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# Pattern Definitions
# =============================================================================

PATTERN_DEFINITIONS = [
    PatternDefinition(
        type=PatternType.SEQUENCE,
        name="Event Sequence",
        description="Detect ordered sequences of events (A then B then C)",
        use_cases=[
            "Brute force followed by successful login",
            "Reconnaissance followed by exploitation",
            "Data staging followed by exfiltration",
            "Multiple failed access attempts then privilege escalation",
        ],
        required_config=["events", "sequence.order"],
        example_config={
            "pattern_type": "sequence",
            "window": "5m",
            "events": [
                {"id": "failed_login", "query": "event.action:logon_failed"},
                {"id": "success", "query": "event.action:logon AND event.outcome:success"},
            ],
            "join_on": [{"field": "user.name"}],
            "sequence": {"order": ["failed_login", "success"]},
            "thresholds": [{"event": "failed_login", "count": ">= 5"}],
        },
    ),
    PatternDefinition(
        type=PatternType.TEMPORAL_JOIN,
        name="Temporal Join",
        description="Find events that occur together within a time window",
        use_cases=[
            "Process creation with network connection",
            "File modification with registry change",
            "User creation followed by privilege grant",
            "Service installation with scheduled task",
        ],
        required_config=["events", "join_on"],
        example_config={
            "pattern_type": "temporal_join",
            "window": "1m",
            "events": [
                {"id": "process", "query": "event.category:process AND event.type:start"},
                {"id": "network", "query": "event.category:network AND destination.port:443"},
            ],
            "join_on": [{"field": "process.pid"}, {"field": "host.name"}],
            "temporal_join": {"max_span": "30s", "require_all": True},
        },
    ),
    PatternDefinition(
        type=PatternType.AGGREGATION,
        name="Aggregation",
        description="Count events by group and trigger on thresholds",
        use_cases=[
            "Multiple failed logins from same source",
            "High volume of DNS queries to single domain",
            "Repeated access to sensitive files",
            "Multiple process spawns by parent",
        ],
        required_config=["events", "aggregation.group_by", "aggregation.having"],
        example_config={
            "pattern_type": "aggregation",
            "window": "15m",
            "events": [{"id": "dns_query", "query": "event.category:dns AND dns.type:query"}],
            "aggregation": {
                "group_by": ["source.ip", "dns.question.name"],
                "having": [{"event": "dns_query", "count": ">= 100"}],
            },
        },
    ),
    PatternDefinition(
        type=PatternType.SPIKE,
        name="Spike Detection",
        description="Detect anomalous spikes compared to baseline",
        use_cases=[
            "Sudden increase in failed logins",
            "Traffic spike to external IPs",
            "Unusual file access volume",
            "Process creation rate anomaly",
        ],
        required_config=["events", "spike.field", "spike.baseline_window"],
        example_config={
            "pattern_type": "spike",
            "window": "5m",
            "events": [{"id": "login_attempt", "query": "event.action:logon*"}],
            "spike": {
                "field": "source.ip",
                "baseline_window": "1h",
                "spike_window": "5m",
                "spike_threshold": 3.0,
                "min_baseline": 10,
            },
        },
    ),
]


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/validate", response_model=RuleValidationResult)
async def validate_rule(
    config: RuleBuilderConfig,
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleValidationResult:
    """Validate a rule builder configuration.

    Requires authentication.
    Returns validation errors, warnings, and the generated correlation_config.
    """
    validator = get_rule_validator()
    return validator.validate(config)


@router.post("/preview", response_model=RulePreviewResult)
async def preview_rule(
    request: RulePreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RulePreviewResult:
    """Preview rule matches against recent data.

    Requires authentication.
    Executes the rule configuration against the specified time range
    and returns matching correlations.
    """
    start_time = datetime.utcnow()

    # Validate configuration first
    validator = get_rule_validator()
    validation = validator.validate(request.config)

    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid rule configuration",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Parse time range
    time_range = parse_duration(request.time_range)
    end_time = datetime.utcnow()
    range_start = end_time - time_range

    # Get Elasticsearch client
    es = await get_elasticsearch()

    # Determine index pattern
    tenant_id = get_current_tenant_id()
    if tenant_id:
        index_pattern = get_elasticsearch_pattern("events")
    else:
        index_pattern = f"{settings.elasticsearch_index_prefix}-events-*"

    # Execute preview queries
    matches: list[CorrelationMatch] = []
    events_scanned = 0

    try:
        # Query events for each event definition
        all_events: dict[str, list[dict]] = {}

        for event_def in request.config.events:
            query_str = event_definition_to_query(event_def)

            # Build Elasticsearch query
            es_query = {
                "bool": {
                    "must": [
                        {"query_string": {"query": query_str}},
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": range_start.isoformat(),
                                    "lte": end_time.isoformat(),
                                }
                            }
                        },
                    ]
                }
            }

            response = await es.search(
                index=index_pattern,
                query=es_query,
                size=min(request.limit * 10, 10000),  # Get more events for correlation
                sort=[{"@timestamp": "asc"}],
            )

            hits = [hit["_source"] for hit in response["hits"]["hits"]]
            all_events[event_def.id] = hits
            events_scanned += response["hits"]["total"]["value"]

        # Group events by join key
        entity_events: dict[str, dict[str, list]] = {}
        join_fields = [j.field for j in request.config.join_on]

        for event_id, hits in all_events.items():
            for hit in hits:
                # Build entity key
                key_parts = []
                for field in join_fields:
                    value = _get_nested_value(hit, field)
                    if value:
                        key_parts.append(f"{field}:{value}")

                entity_key = "|".join(key_parts) if key_parts else "_global_"

                if entity_key not in entity_events:
                    entity_events[entity_key] = {}
                if event_id not in entity_events[entity_key]:
                    entity_events[entity_key][event_id] = []
                entity_events[entity_key][event_id].append(hit)

        # Build correlation matches based on pattern type
        matches = _build_correlation_matches(request.config, entity_events, request.limit)

    except Exception as e:
        logger.error("Preview failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Preview failed: {str(e)}"
        )

    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    return RulePreviewResult(
        total_matches=len(matches),
        matches=matches[: request.limit],
        events_scanned=events_scanned,
        duration_ms=duration_ms,
        time_range_start=range_start.isoformat(),
        time_range_end=end_time.isoformat(),
    )


@router.post("/test", response_model=RuleTestResult)
async def test_rule(
    request: RuleTestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RuleTestResult:
    """Test a rule against historical data.

    Requires authentication.
    Provides statistics on how the rule would have performed
    over the specified time period.
    """
    start_time = datetime.utcnow()

    # Validate configuration first
    validator = get_rule_validator()
    validation = validator.validate(request.config)

    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid rule configuration",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Get Elasticsearch client
    es = await get_elasticsearch()

    # Determine index pattern
    tenant_id = get_current_tenant_id()
    if tenant_id:
        index_pattern = get_elasticsearch_pattern("events")
    else:
        index_pattern = f"{settings.elasticsearch_index_prefix}-events-*"

    # Calculate time buckets (hourly)
    int((request.end_time - request.start_time).total_seconds() / 3600)
    matches_by_hour: dict[str, int] = {}
    all_matches: list[CorrelationMatch] = []
    entity_match_counts: dict[str, int] = {}

    try:
        # Process in hourly chunks
        current_start = request.start_time
        parse_duration(request.config.window)

        while current_start < request.end_time:
            current_end = min(current_start + timedelta(hours=1), request.end_time)

            # Query events for this hour
            all_events: dict[str, list[dict]] = {}

            for event_def in request.config.events:
                query_str = event_definition_to_query(event_def)

                es_query = {
                    "bool": {
                        "must": [
                            {"query_string": {"query": query_str}},
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": current_start.isoformat(),
                                        "lte": current_end.isoformat(),
                                    }
                                }
                            },
                        ]
                    }
                }

                response = await es.search(
                    index=index_pattern, query=es_query, size=10000, sort=[{"@timestamp": "asc"}]
                )

                all_events[event_def.id] = [hit["_source"] for hit in response["hits"]["hits"]]

            # Group by entity
            entity_events = _group_events_by_entity(
                all_events, [j.field for j in request.config.join_on]
            )

            # Build matches
            hour_matches = _build_correlation_matches(request.config, entity_events, 1000)

            # Record results
            hour_key = current_start.strftime("%Y-%m-%dT%H:00:00Z")
            matches_by_hour[hour_key] = len(hour_matches)
            all_matches.extend(hour_matches)

            # Track entity match counts
            for match in hour_matches:
                entity_match_counts[match.entity_key] = (
                    entity_match_counts.get(match.entity_key, 0) + 1
                )

            current_start = current_end

    except Exception as e:
        logger.error("Test failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Test failed: {str(e)}"
        )

    # Calculate statistics
    total_matches = len(all_matches)
    days = (request.end_time - request.start_time).total_seconds() / 86400
    estimated_alerts_per_day = total_matches / days if days > 0 else 0

    # Top entities
    top_entities = sorted(
        [{"entity": k, "count": v} for k, v in entity_match_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    return RuleTestResult(
        total_matches=total_matches,
        matches_by_hour=matches_by_hour,
        top_entities=top_entities,
        sample_matches=all_matches[:20],
        estimated_alerts_per_day=round(estimated_alerts_per_day, 2),
        duration_ms=duration_ms,
    )


@router.get("/fields", response_model=FieldsResponse)
async def get_available_fields(
    current_user: Annotated[User, Depends(get_current_user)],
    index_pattern: str | None = Query(None, description="Index pattern to query fields from"),
) -> FieldsResponse:
    """Get available fields for rule building.

    Requires authentication.
    Returns field definitions with types and sample values.
    """
    es = await get_elasticsearch()

    # Determine index pattern
    tenant_id = get_current_tenant_id()
    if index_pattern:
        pattern = index_pattern
    elif tenant_id:
        pattern = get_elasticsearch_pattern("events")
    else:
        pattern = f"{settings.elasticsearch_index_prefix}-events-*"

    fields: list[AvailableField] = []

    try:
        # Get field mappings
        mapping = await es.indices.get_mapping(index=pattern)

        # Extract fields from first index
        for index_name, index_mapping in mapping.items():
            properties = index_mapping.get("mappings", {}).get("properties", {})
            fields = _extract_fields_from_mapping(properties)
            break  # Just use first index

        # Get sample values for key fields
        key_fields = ["event.action", "event.category", "user.name", "host.name", "process.name"]
        for field_path in key_fields:
            for field in fields:
                if field.path == field_path:
                    try:
                        agg_response = await es.search(
                            index=pattern,
                            size=0,
                            aggs={"samples": {"terms": {"field": field_path, "size": 10}}},
                        )
                        buckets = agg_response["aggregations"]["samples"]["buckets"]
                        field.sample_values = [b["key"] for b in buckets]
                    except Exception:
                        pass  # Ignore errors getting sample values

    except Exception as e:
        logger.warning("Failed to get fields: %s", str(e))

    return FieldsResponse(fields=fields, index_patterns=[pattern])


@router.get("/patterns", response_model=PatternsResponse)
async def get_patterns(
    current_user: Annotated[User, Depends(get_current_user)],
) -> PatternsResponse:
    """Get available correlation pattern definitions.

    Requires authentication.
    """
    return PatternsResponse(patterns=PATTERN_DEFINITIONS)


@router.post("/import/sigma", response_model=SigmaImportResult)
async def import_sigma_rule(
    request: SigmaImportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SigmaImportResult:
    """Import a Sigma rule and convert to Eleanor format.

    Requires authentication.
    Supports basic Sigma rules and can optionally convert to correlation rules.
    """
    warnings: list[str] = []
    errors: list[str] = []

    try:
        sigma_rule = yaml.safe_load(request.sigma_yaml)
    except yaml.YAMLError as e:
        return SigmaImportResult(success=False, rule_name=None, errors=[f"Invalid YAML: {str(e)}"])

    if not isinstance(sigma_rule, dict):
        return SigmaImportResult(
            success=False, rule_name=None, errors=["Sigma rule must be a YAML dictionary"]
        )

    # Extract basic info
    rule_name = sigma_rule.get("title", "Imported Sigma Rule")
    description = sigma_rule.get("description", "")
    level = sigma_rule.get("level", "medium")

    # Map Sigma level to Eleanor severity
    severity_map = {
        "informational": "informational",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "critical",
    }
    severity = severity_map.get(level, "medium")

    # Extract MITRE ATT&CK mapping
    mitre_tactics = []
    mitre_techniques = []
    tags = sigma_rule.get("tags", [])
    for tag in tags:
        if tag.startswith("attack."):
            tag_value = tag[7:]  # Remove "attack." prefix
            if tag_value.startswith("t"):
                mitre_techniques.append(tag_value.upper())
            else:
                mitre_tactics.append(tag_value)

    # Convert detection to query
    detection = sigma_rule.get("detection", {})
    query_parts = []

    for key, value in detection.items():
        if key == "condition":
            continue
        if isinstance(value, dict):
            for field, pattern in value.items():
                if isinstance(pattern, list):
                    query_parts.append(f"({' OR '.join(f'{field}:{p}' for p in pattern)})")
                else:
                    query_parts.append(f"{field}:{pattern}")
        elif isinstance(value, list):
            warnings.append(f"List detection for '{key}' simplified")

    query = " AND ".join(query_parts) if query_parts else "*"

    # Build detection rule config
    detection_rule = {
        "name": rule_name,
        "description": description,
        "rule_type": "scheduled",
        "severity": severity,
        "status": "disabled",
        "query": query,
        "query_language": "lucene",
        "mitre_tactics": mitre_tactics,
        "mitre_techniques": mitre_techniques,
        "tags": [t for t in tags if not t.startswith("attack.")],
        "references": sigma_rule.get("references", []),
    }

    # Optionally convert to correlation
    correlation_config = None
    if request.convert_to_correlation:
        # Check if this could be a correlation rule
        condition = detection.get("condition", "")
        if " | count" in condition or "timeframe" in sigma_rule:
            correlation_config = {
                "pattern_type": "aggregation",
                "window": sigma_rule.get("detection", {}).get("timeframe", "5m"),
                "events": [{"id": "main", "query": query}],
                "aggregation": {
                    "group_by": ["user.name"],  # Default grouping
                    "having": [{"event": "main", "count": ">= 1"}],
                },
            }
            detection_rule["rule_type"] = "correlation"
            detection_rule["correlation_config"] = correlation_config
            warnings.append("Converted to correlation rule with default grouping")
        else:
            warnings.append("Rule not suitable for correlation conversion")

    return SigmaImportResult(
        success=True,
        rule_name=rule_name,
        detection_rule=detection_rule,
        correlation_config=correlation_config,
        warnings=warnings,
        errors=errors,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_nested_value(obj: dict, path: str) -> Any:
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _group_events_by_entity(
    all_events: dict[str, list[dict]], join_fields: list[str]
) -> dict[str, dict[str, list]]:
    """Group events by entity key."""
    entity_events: dict[str, dict[str, list]] = {}

    for event_id, hits in all_events.items():
        for hit in hits:
            key_parts = []
            for field in join_fields:
                value = _get_nested_value(hit, field)
                if value:
                    key_parts.append(f"{field}:{value}")

            entity_key = "|".join(key_parts) if key_parts else "_global_"

            if entity_key not in entity_events:
                entity_events[entity_key] = {}
            if event_id not in entity_events[entity_key]:
                entity_events[entity_key][event_id] = []
            entity_events[entity_key][event_id].append(hit)

    return entity_events


def _build_correlation_matches(
    config: RuleBuilderConfig, entity_events: dict[str, dict[str, list]], limit: int
) -> list[CorrelationMatch]:
    """Build correlation matches from grouped events."""
    matches: list[CorrelationMatch] = []

    # Build threshold lookup
    threshold_map: dict[str, tuple[str, int]] = {}
    for t in config.thresholds:
        threshold_map[t.event_id] = (t.operator, t.count)

    for entity_key, events_by_type in entity_events.items():
        match_valid = False

        if config.pattern_type == PatternType.SEQUENCE:
            if config.sequence:
                match_valid = True
                for event_id in config.sequence.order:
                    event_count = len(events_by_type.get(event_id, []))
                    if event_id in threshold_map:
                        op, thresh = threshold_map[event_id]
                        if not _check_threshold(event_count, op, thresh):
                            match_valid = False
                            break
                    elif event_count == 0:
                        match_valid = False
                        break

        elif config.pattern_type == PatternType.TEMPORAL_JOIN:
            # Check all event types are present
            if config.temporal_join and config.temporal_join.require_all:
                match_valid = all(len(events_by_type.get(e.id, [])) > 0 for e in config.events)
            else:
                match_valid = (
                    sum(1 for e in config.events if len(events_by_type.get(e.id, [])) > 0) >= 2
                )

        elif config.pattern_type == PatternType.AGGREGATION:
            if config.aggregation:
                match_valid = True
                for having in config.aggregation.having:
                    event_count = len(events_by_type.get(having.event_id, []))
                    if not _check_threshold(event_count, having.operator, having.count):
                        match_valid = False
                        break

        if match_valid:
            # Collect all events
            all_entity_events = []
            for event_id, events in events_by_type.items():
                for event in events:
                    all_entity_events.append(
                        EventMatch(
                            timestamp=event.get("@timestamp", ""),
                            event_id=event_id,
                            entity_key=entity_key,
                            document=event,
                        )
                    )

            # Sort by timestamp
            all_entity_events.sort(key=lambda x: x.timestamp)

            if all_entity_events:
                matches.append(
                    CorrelationMatch(
                        entity_key=entity_key,
                        event_counts={
                            e.id: len(events_by_type.get(e.id, [])) for e in config.events
                        },
                        first_event_time=all_entity_events[0].timestamp,
                        last_event_time=all_entity_events[-1].timestamp,
                        total_events=len(all_entity_events),
                        sample_events=all_entity_events[:5],
                    )
                )

        if len(matches) >= limit:
            break

    return matches


def _check_threshold(count: int, operator: str, threshold: int) -> bool:
    """Check if count meets threshold."""
    ops = {
        ">=": lambda x, y: x >= y,
        ">": lambda x, y: x > y,
        "<=": lambda x, y: x <= y,
        "<": lambda x, y: x < y,
        "==": lambda x, y: x == y,
    }
    return ops.get(operator, lambda x, y: x >= y)(count, threshold)


def _extract_fields_from_mapping(properties: dict, prefix: str = "") -> list[AvailableField]:
    """Extract fields from Elasticsearch mapping."""
    fields = []

    for field_name, field_def in properties.items():
        path = f"{prefix}.{field_name}" if prefix else field_name

        if "properties" in field_def:
            # Nested object
            fields.extend(_extract_fields_from_mapping(field_def["properties"], path))
        else:
            # Leaf field
            es_type = field_def.get("type", "keyword")
            field_type = {
                "keyword": FieldType.KEYWORD,
                "text": FieldType.STRING,
                "long": FieldType.NUMBER,
                "integer": FieldType.NUMBER,
                "float": FieldType.NUMBER,
                "double": FieldType.NUMBER,
                "boolean": FieldType.BOOLEAN,
                "ip": FieldType.IP,
                "date": FieldType.DATE,
            }.get(es_type, FieldType.STRING)

            fields.append(
                AvailableField(path=path, type=field_type, description=None, sample_values=[])
            )

    return fields
