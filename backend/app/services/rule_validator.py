"""Rule validator service for the visual rule builder.

Validates correlation rule configurations and generates the
correlation_config JSON for DetectionRule models.
"""

import logging
import re
from typing import Any

from app.schemas.rule_builder import (
    ComparisonOperator,
    EventDefinition,
    FieldCondition,
    PatternType,
    RuleBuilderConfig,
    RuleValidationError,
    RuleValidationResult,
)

logger = logging.getLogger(__name__)


DURATION_PATTERN = re.compile(r"^(\d+)([smhdw])$", re.IGNORECASE)

VALID_OPERATORS = {">=", ">", "<=", "<", "=="}


def validate_duration(duration: str) -> tuple[bool, str | None]:
    """Validate a duration string.

    Args:
        duration: Duration string like "5m", "1h", etc.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not duration:
        return False, "Duration cannot be empty"

    match = DURATION_PATTERN.match(duration)
    if not match:
        return False, f"Invalid duration format: {duration}. Use format like '5m', '1h', '30s', '2d'"

    value = int(match.group(1))
    if value <= 0:
        return False, "Duration value must be positive"

    return True, None


def validate_field_path(path: str) -> tuple[bool, str | None]:
    """Validate a field path.

    Args:
        path: Field path like "user.name", "process.pid"

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path or not path.strip():
        return False, "Field path cannot be empty"

    # Allow alphanumeric, dots, underscores, and @
    if not re.match(r"^[@a-zA-Z][a-zA-Z0-9_.@]*$", path):
        return False, f"Invalid field path: {path}"

    return True, None


def condition_to_query(condition: FieldCondition) -> str:
    """Convert a field condition to KQL/Lucene query string.

    Args:
        condition: The field condition

    Returns:
        Query string fragment
    """
    field = condition.field
    value = condition.value
    negate = condition.negate

    # Escape special characters in value if string
    if isinstance(value, str):
        escaped_value = value.replace('"', '\\"')
        if " " in escaped_value or any(c in escaped_value for c in [':', '(', ')', '[', ']']):
            escaped_value = f'"{escaped_value}"'
    else:
        escaped_value = str(value) if value is not None else "*"

    query = ""

    match condition.operator:
        case ComparisonOperator.EQUALS:
            query = f"{field}:{escaped_value}"
        case ComparisonOperator.NOT_EQUALS:
            query = f"NOT {field}:{escaped_value}"
            negate = False  # Already negated
        case ComparisonOperator.CONTAINS:
            query = f"{field}:*{escaped_value}*"
        case ComparisonOperator.NOT_CONTAINS:
            query = f"NOT {field}:*{escaped_value}*"
            negate = False
        case ComparisonOperator.STARTS_WITH:
            query = f"{field}:{escaped_value}*"
        case ComparisonOperator.ENDS_WITH:
            query = f"{field}:*{escaped_value}"
        case ComparisonOperator.GREATER_THAN:
            query = f"{field}:>{value}"
        case ComparisonOperator.GREATER_THAN_OR_EQUALS:
            query = f"{field}:>={value}"
        case ComparisonOperator.LESS_THAN:
            query = f"{field}:<{value}"
        case ComparisonOperator.LESS_THAN_OR_EQUALS:
            query = f"{field}:<={value}"
        case ComparisonOperator.EXISTS:
            query = f"_exists_:{field}"
        case ComparisonOperator.NOT_EXISTS:
            query = f"NOT _exists_:{field}"
            negate = False
        case ComparisonOperator.MATCHES_REGEX:
            query = f"{field}:/{escaped_value}/"
        case ComparisonOperator.IN_LIST:
            if isinstance(value, list):
                values = " OR ".join(f"{field}:{v}" for v in value)
                query = f"({values})"
            else:
                query = f"{field}:{escaped_value}"
        case ComparisonOperator.NOT_IN_LIST:
            if isinstance(value, list):
                values = " OR ".join(f"{field}:{v}" for v in value)
                query = f"NOT ({values})"
            else:
                query = f"NOT {field}:{escaped_value}"
            negate = False
        case _:
            query = f"{field}:{escaped_value}"

    if negate:
        query = f"NOT ({query})"

    return query


def event_definition_to_query(event: EventDefinition) -> str:
    """Convert an event definition to a query string.

    Args:
        event: Event definition with conditions

    Returns:
        Full query string
    """
    if event.raw_query:
        return event.raw_query

    if not event.conditions:
        return "*"

    condition_queries = [condition_to_query(c) for c in event.conditions]
    return " AND ".join(f"({q})" for q in condition_queries)


class RuleValidator:
    """Validates and generates correlation rule configurations."""

    def validate(self, config: RuleBuilderConfig) -> RuleValidationResult:
        """Validate a rule builder configuration.

        Args:
            config: The rule builder configuration

        Returns:
            Validation result with errors, warnings, and generated config
        """
        errors: list[RuleValidationError] = []
        warnings: list[RuleValidationError] = []

        # Validate window duration
        valid, err = validate_duration(config.window)
        if not valid:
            errors.append(RuleValidationError(
                field="window",
                message=err or "Invalid window",
                severity="error"
            ))

        # Validate events
        event_ids = set()
        for i, event in enumerate(config.events):
            event_errors = self._validate_event(event, i)
            errors.extend(event_errors)

            if event.id in event_ids:
                errors.append(RuleValidationError(
                    field=f"events[{i}].id",
                    message=f"Duplicate event ID: {event.id}",
                    severity="error"
                ))
            event_ids.add(event.id)

        # Validate join fields
        for i, join in enumerate(config.join_on):
            valid, err = validate_field_path(join.field)
            if not valid:
                errors.append(RuleValidationError(
                    field=f"join_on[{i}].field",
                    message=err or "Invalid field path",
                    severity="error"
                ))

        # Validate thresholds reference valid events
        for i, threshold in enumerate(config.thresholds):
            if threshold.event_id not in event_ids:
                errors.append(RuleValidationError(
                    field=f"thresholds[{i}].event_id",
                    message=f"Threshold references unknown event: {threshold.event_id}",
                    severity="error"
                ))

        # Validate pattern-specific configuration
        pattern_errors, pattern_warnings = self._validate_pattern(config, event_ids)
        errors.extend(pattern_errors)
        warnings.extend(pattern_warnings)

        # Generate config if valid
        generated_config = None
        if not errors:
            generated_config = self._generate_correlation_config(config)

        return RuleValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            generated_config=generated_config
        )

    def _validate_event(
        self, event: EventDefinition, index: int
    ) -> list[RuleValidationError]:
        """Validate a single event definition."""
        errors = []
        prefix = f"events[{index}]"

        if not event.id:
            errors.append(RuleValidationError(
                field=f"{prefix}.id",
                message="Event ID is required",
                severity="error"
            ))

        if not event.name:
            errors.append(RuleValidationError(
                field=f"{prefix}.name",
                message="Event name is required",
                severity="error"
            ))

        # Validate conditions
        for j, condition in enumerate(event.conditions):
            valid, err = validate_field_path(condition.field)
            if not valid:
                errors.append(RuleValidationError(
                    field=f"{prefix}.conditions[{j}].field",
                    message=err or "Invalid field path",
                    severity="error"
                ))

            # Validate value for operators that require it
            if condition.operator not in {
                ComparisonOperator.EXISTS,
                ComparisonOperator.NOT_EXISTS
            }:
                if condition.value is None:
                    errors.append(RuleValidationError(
                        field=f"{prefix}.conditions[{j}].value",
                        message="Value is required for this operator",
                        severity="error"
                    ))

        return errors

    def _validate_pattern(
        self, config: RuleBuilderConfig, event_ids: set[str]
    ) -> tuple[list[RuleValidationError], list[RuleValidationError]]:
        """Validate pattern-specific configuration."""
        errors = []
        warnings = []

        match config.pattern_type:
            case PatternType.SEQUENCE:
                if not config.sequence:
                    errors.append(RuleValidationError(
                        field="sequence",
                        message="Sequence configuration is required for sequence pattern",
                        severity="error"
                    ))
                elif not config.sequence.order:
                    errors.append(RuleValidationError(
                        field="sequence.order",
                        message="Sequence order must have at least one event",
                        severity="error"
                    ))
                else:
                    for i, event_id in enumerate(config.sequence.order):
                        if event_id not in event_ids:
                            errors.append(RuleValidationError(
                                field=f"sequence.order[{i}]",
                                message=f"Unknown event ID in sequence: {event_id}",
                                severity="error"
                            ))

                if not config.join_on:
                    warnings.append(RuleValidationError(
                        field="join_on",
                        message="No join fields specified. Sequence will correlate all events regardless of entity.",
                        severity="warning"
                    ))

            case PatternType.TEMPORAL_JOIN:
                if config.temporal_join:
                    valid, err = validate_duration(config.temporal_join.max_span)
                    if not valid:
                        errors.append(RuleValidationError(
                            field="temporal_join.max_span",
                            message=err or "Invalid duration",
                            severity="error"
                        ))

                if len(config.events) < 2:
                    errors.append(RuleValidationError(
                        field="events",
                        message="Temporal join requires at least 2 event types",
                        severity="error"
                    ))

            case PatternType.AGGREGATION:
                if not config.aggregation:
                    errors.append(RuleValidationError(
                        field="aggregation",
                        message="Aggregation configuration is required",
                        severity="error"
                    ))
                elif not config.aggregation.group_by:
                    errors.append(RuleValidationError(
                        field="aggregation.group_by",
                        message="At least one group_by field is required",
                        severity="error"
                    ))
                elif not config.aggregation.having:
                    errors.append(RuleValidationError(
                        field="aggregation.having",
                        message="At least one threshold condition is required",
                        severity="error"
                    ))

            case PatternType.SPIKE:
                if not config.spike:
                    errors.append(RuleValidationError(
                        field="spike",
                        message="Spike configuration is required",
                        severity="error"
                    ))
                else:
                    valid, err = validate_duration(config.spike.baseline_window)
                    if not valid:
                        errors.append(RuleValidationError(
                            field="spike.baseline_window",
                            message=err or "Invalid duration",
                            severity="error"
                        ))

                    valid, err = validate_duration(config.spike.spike_window)
                    if not valid:
                        errors.append(RuleValidationError(
                            field="spike.spike_window",
                            message=err or "Invalid duration",
                            severity="error"
                        ))

                    valid, err = validate_field_path(config.spike.field)
                    if not valid:
                        errors.append(RuleValidationError(
                            field="spike.field",
                            message=err or "Invalid field path",
                            severity="error"
                        ))

        return errors, warnings

    def _generate_correlation_config(self, config: RuleBuilderConfig) -> dict[str, Any]:
        """Generate correlation_config from builder config.

        Args:
            config: Validated rule builder configuration

        Returns:
            correlation_config dict for DetectionRule model
        """
        correlation_config: dict[str, Any] = {
            "pattern_type": config.pattern_type.value,
            "window": config.window,
            "realtime": config.realtime,
            "events": [],
            "join_on": [],
            "thresholds": [],
        }

        # Convert events
        for event in config.events:
            event_config = {
                "id": event.id,
                "query": event_definition_to_query(event),
            }
            if event.indices:
                event_config["indices"] = event.indices
            correlation_config["events"].append(event_config)

        # Convert join fields
        for join in config.join_on:
            correlation_config["join_on"].append({"field": join.field})

        # Convert thresholds
        for threshold in config.thresholds:
            correlation_config["thresholds"].append({
                "event": threshold.event_id,
                "count": f"{threshold.operator} {threshold.count}"
            })

        # Add pattern-specific config
        match config.pattern_type:
            case PatternType.SEQUENCE:
                if config.sequence:
                    correlation_config["sequence"] = {
                        "order": config.sequence.order,
                        "strict_order": config.sequence.strict_order,
                    }

            case PatternType.TEMPORAL_JOIN:
                if config.temporal_join:
                    correlation_config["temporal_join"] = {
                        "max_span": config.temporal_join.max_span,
                        "require_all": config.temporal_join.require_all,
                    }

            case PatternType.AGGREGATION:
                if config.aggregation:
                    correlation_config["aggregation"] = {
                        "group_by": config.aggregation.group_by,
                        "having": [
                            {
                                "event": h.event_id,
                                "count": f"{h.operator} {h.count}"
                            }
                            for h in config.aggregation.having
                        ]
                    }

            case PatternType.SPIKE:
                if config.spike:
                    correlation_config["spike"] = {
                        "field": config.spike.field,
                        "baseline_window": config.spike.baseline_window,
                        "spike_window": config.spike.spike_window,
                        "spike_threshold": config.spike.spike_threshold,
                        "min_baseline": config.spike.min_baseline,
                    }

        return correlation_config


# Module-level instance
_rule_validator: RuleValidator | None = None


def get_rule_validator() -> RuleValidator:
    """Get the rule validator instance."""
    global _rule_validator
    if _rule_validator is None:
        _rule_validator = RuleValidator()
    return _rule_validator
