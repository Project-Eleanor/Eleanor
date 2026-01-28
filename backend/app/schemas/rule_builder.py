"""Schemas for the visual rule builder API."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PatternType(str, Enum):
    """Correlation pattern types."""

    SEQUENCE = "sequence"
    TEMPORAL_JOIN = "temporal_join"
    AGGREGATION = "aggregation"
    SPIKE = "spike"


class FieldType(str, Enum):
    """Field data types for rule conditions."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    IP = "ip"
    DATE = "date"
    KEYWORD = "keyword"


class ComparisonOperator(str, Enum):
    """Comparison operators for conditions."""

    EQUALS = "eq"
    NOT_EQUALS = "neq"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUALS = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUALS = "lte"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    MATCHES_REGEX = "regex"
    IN_LIST = "in"
    NOT_IN_LIST = "not_in"


# =============================================================================
# Event Definition Schemas
# =============================================================================


class FieldCondition(BaseModel):
    """A single field condition within an event definition."""

    field: str = Field(..., description="The field path (e.g., 'user.name', 'process.pid')")
    operator: ComparisonOperator = Field(..., description="Comparison operator")
    value: Any = Field(None, description="Value to compare against")
    negate: bool = Field(False, description="Negate the condition")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        """Validate field path format."""
        if not v or not v.strip():
            raise ValueError("Field path cannot be empty")
        return v.strip()


class EventDefinition(BaseModel):
    """Definition of an event type for correlation rules."""

    id: str = Field(..., description="Unique identifier for this event type")
    name: str = Field(..., description="Display name for the event")
    description: str | None = Field(None, description="Optional description")
    conditions: list[FieldCondition] = Field(
        default_factory=list, description="Field conditions (ANDed together)"
    )
    # Raw query option for advanced users
    raw_query: str | None = Field(None, description="Raw KQL/Lucene query (overrides conditions)")
    indices: list[str] = Field(default_factory=list, description="Specific indices to query")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate event ID format."""
        if not v or not v.strip():
            raise ValueError("Event ID cannot be empty")
        # Allow alphanumeric and underscores
        import re
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", v):
            raise ValueError("Event ID must start with a letter and contain only alphanumeric characters and underscores")
        return v


class JoinField(BaseModel):
    """Field used to join events together."""

    field: str = Field(..., description="Field path to join on")
    alias: str | None = Field(None, description="Optional alias for the join key")


class ThresholdCondition(BaseModel):
    """Threshold condition for an event type."""

    event_id: str = Field(..., description="Event definition ID")
    operator: str = Field(..., description="Threshold operator (>=, >, <=, <, ==)")
    count: int = Field(..., ge=0, description="Threshold count")

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """Validate threshold operator."""
        valid_ops = {">=", ">", "<=", "<", "==", "="}
        if v not in valid_ops:
            raise ValueError(f"Invalid operator. Must be one of: {valid_ops}")
        return "==" if v == "=" else v


# =============================================================================
# Pattern Configuration Schemas
# =============================================================================


class SequenceConfig(BaseModel):
    """Configuration for sequence pattern."""

    order: list[str] = Field(..., description="Ordered list of event IDs")
    strict_order: bool = Field(
        False, description="If true, events must occur in exact order without interleaving"
    )


class TemporalJoinConfig(BaseModel):
    """Configuration for temporal join pattern."""

    max_span: str = Field("5m", description="Maximum time span between first and last event")
    require_all: bool = Field(True, description="Require all event types to be present")


class AggregationConfig(BaseModel):
    """Configuration for aggregation pattern."""

    group_by: list[str] = Field(..., description="Fields to group by")
    having: list[ThresholdCondition] = Field(..., description="Threshold conditions")


class SpikeConfig(BaseModel):
    """Configuration for spike detection pattern."""

    field: str = Field(..., description="Field to measure for spikes")
    baseline_window: str = Field("1h", description="Window for baseline calculation")
    spike_window: str = Field("5m", description="Window for spike detection")
    spike_threshold: float = Field(2.0, ge=1.0, description="Multiplier for spike detection")
    min_baseline: int = Field(10, ge=1, description="Minimum baseline count")


# =============================================================================
# Rule Builder Request/Response Schemas
# =============================================================================


class RuleBuilderConfig(BaseModel):
    """Complete rule builder configuration."""

    # Pattern selection
    pattern_type: PatternType = Field(..., description="The correlation pattern type")

    # Time window
    window: str = Field("5m", description="Correlation time window (e.g., '5m', '1h')")

    # Event definitions
    events: list[EventDefinition] = Field(
        ..., min_length=1, description="Event type definitions"
    )

    # Join configuration
    join_on: list[JoinField] = Field(
        default_factory=list, description="Fields to correlate events on"
    )

    # Thresholds
    thresholds: list[ThresholdCondition] = Field(
        default_factory=list, description="Event count thresholds"
    )

    # Pattern-specific configuration
    sequence: SequenceConfig | None = Field(None, description="Sequence pattern config")
    temporal_join: TemporalJoinConfig | None = Field(None, description="Temporal join config")
    aggregation: AggregationConfig | None = Field(None, description="Aggregation config")
    spike: SpikeConfig | None = Field(None, description="Spike detection config")

    # Realtime processing
    realtime: bool = Field(False, description="Enable real-time processing")


class RuleValidationError(BaseModel):
    """A validation error for a rule configuration."""

    field: str = Field(..., description="Field path that has the error")
    message: str = Field(..., description="Error message")
    severity: str = Field("error", description="Severity: error, warning, info")


class RuleValidationResult(BaseModel):
    """Result of rule validation."""

    valid: bool = Field(..., description="Whether the rule is valid")
    errors: list[RuleValidationError] = Field(default_factory=list)
    warnings: list[RuleValidationError] = Field(default_factory=list)
    generated_config: dict | None = Field(
        None, description="The generated correlation_config for the detection rule"
    )


class RulePreviewRequest(BaseModel):
    """Request to preview rule matches."""

    config: RuleBuilderConfig
    time_range: str = Field("24h", description="Time range to search (e.g., '24h', '7d')")
    limit: int = Field(100, ge=1, le=1000, description="Maximum matches to return")


class EventMatch(BaseModel):
    """A single event match from preview."""

    timestamp: str
    event_id: str
    entity_key: str | None
    document: dict


class CorrelationMatch(BaseModel):
    """A correlation match from preview."""

    entity_key: str
    event_counts: dict[str, int]
    first_event_time: str
    last_event_time: str
    total_events: int
    sample_events: list[EventMatch]


class RulePreviewResult(BaseModel):
    """Result of rule preview."""

    total_matches: int
    matches: list[CorrelationMatch]
    events_scanned: int
    duration_ms: int
    time_range_start: str
    time_range_end: str


class RuleTestRequest(BaseModel):
    """Request to test a rule against historical data."""

    config: RuleBuilderConfig
    start_time: datetime
    end_time: datetime


class RuleTestResult(BaseModel):
    """Result of historical rule testing."""

    total_matches: int
    matches_by_hour: dict[str, int]  # ISO hour -> count
    top_entities: list[dict]  # Top entities by match count
    sample_matches: list[CorrelationMatch]
    estimated_alerts_per_day: float
    duration_ms: int


class AvailableField(BaseModel):
    """An available field for rule building."""

    path: str = Field(..., description="Full field path")
    type: FieldType
    description: str | None = None
    sample_values: list[Any] = Field(default_factory=list)


class FieldsResponse(BaseModel):
    """Response with available fields."""

    fields: list[AvailableField]
    index_patterns: list[str]


class PatternDefinition(BaseModel):
    """Definition of a correlation pattern."""

    type: PatternType
    name: str
    description: str
    use_cases: list[str]
    required_config: list[str]
    example_config: dict


class PatternsResponse(BaseModel):
    """Response with available patterns."""

    patterns: list[PatternDefinition]


class SigmaImportRequest(BaseModel):
    """Request to import a Sigma rule."""

    sigma_yaml: str = Field(..., description="Sigma rule in YAML format")
    convert_to_correlation: bool = Field(
        False, description="Attempt to convert to correlation rule"
    )


class SigmaImportResult(BaseModel):
    """Result of Sigma rule import."""

    success: bool
    rule_name: str | None
    detection_rule: dict | None = Field(None, description="Generated detection rule config")
    correlation_config: dict | None = Field(None, description="Generated correlation config")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
