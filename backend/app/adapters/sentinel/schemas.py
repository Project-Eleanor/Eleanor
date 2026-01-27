"""Pydantic schemas for Microsoft Sentinel API responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Incident severity level."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFORMATIONAL = "Informational"


class IncidentStatus(str, Enum):
    """Incident status."""

    NEW = "New"
    ACTIVE = "Active"
    CLOSED = "Closed"


class IncidentClassification(str, Enum):
    """Incident classification."""

    UNDETERMINED = "Undetermined"
    TRUE_POSITIVE = "TruePositive"
    BENIGN_POSITIVE = "BenignPositive"
    FALSE_POSITIVE = "FalsePositive"


class IncidentClassificationReason(str, Enum):
    """Reason for classification."""

    SUSPICIOUS_ACTIVITY = "SuspiciousActivity"
    SUSPICIOUS_BUT_EXPECTED = "SuspiciousButExpected"
    INCORRECT_ALERT_LOGIC = "IncorrectAlertLogic"
    INACCURATE_DATA = "InaccurateData"


class EntityKind(str, Enum):
    """Entity types in Sentinel."""

    ACCOUNT = "Account"
    HOST = "Host"
    IP = "Ip"
    MALWARE = "Malware"
    FILE = "File"
    PROCESS = "Process"
    CLOUD_APPLICATION = "CloudApplication"
    DNS = "Dns"
    AZURE_RESOURCE = "AzureResource"
    FILE_HASH = "FileHash"
    REGISTRY_KEY = "RegistryKey"
    REGISTRY_VALUE = "RegistryValue"
    SECURITY_GROUP = "SecurityGroup"
    URL = "Url"
    MAILBOX = "Mailbox"
    MAIL_CLUSTER = "MailCluster"
    MAIL_MESSAGE = "MailMessage"
    SUBMISSION_MAIL = "SubmissionMail"


class SentinelIncident(BaseModel):
    """Microsoft Sentinel incident."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Incident name/ID")
    etag: str | None = None
    incident_number: int | None = Field(None, alias="incidentNumber")
    title: str | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    classification: IncidentClassification | None = None
    classification_comment: str | None = Field(None, alias="classificationComment")
    classification_reason: IncidentClassificationReason | None = Field(
        None, alias="classificationReason"
    )
    owner: dict[str, Any] | None = None
    labels: list[dict[str, str]] = Field(default_factory=list)
    first_activity_time_utc: datetime | None = Field(None, alias="firstActivityTimeUtc")
    last_activity_time_utc: datetime | None = Field(None, alias="lastActivityTimeUtc")
    created_time_utc: datetime | None = Field(None, alias="createdTimeUtc")
    last_modified_time_utc: datetime | None = Field(None, alias="lastModifiedTimeUtc")
    alerts_count: int | None = Field(None, alias="alertsCount")
    bookmarks_count: int | None = Field(None, alias="bookmarksCount")
    comments_count: int | None = Field(None, alias="commentsCount")
    alert_product_names: list[str] = Field(default_factory=list, alias="alertProductNames")
    tactics: list[str] = Field(default_factory=list)
    related_analytic_rule_ids: list[str] = Field(
        default_factory=list, alias="relatedAnalyticRuleIds"
    )
    provider_name: str | None = Field(None, alias="providerName")
    provider_incident_id: str | None = Field(None, alias="providerIncidentId")
    additional_data: dict[str, Any] | None = Field(None, alias="additionalData")

    class Config:
        populate_by_name = True


class SentinelAlert(BaseModel):
    """Microsoft Sentinel alert."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Alert name/ID")
    alert_display_name: str | None = Field(None, alias="alertDisplayName")
    alert_type: str | None = Field(None, alias="alertType")
    confidence_level: str | None = Field(None, alias="confidenceLevel")
    confidence_score: float | None = Field(None, alias="confidenceScore")
    description: str | None = None
    end_time_utc: datetime | None = Field(None, alias="endTimeUtc")
    intent: str | None = None
    processing_end_time: datetime | None = Field(None, alias="processingEndTime")
    product_component_name: str | None = Field(None, alias="productComponentName")
    product_name: str | None = Field(None, alias="productName")
    product_version: str | None = Field(None, alias="productVersion")
    provider_alert_id: str | None = Field(None, alias="providerAlertId")
    remediation_steps: list[str] = Field(default_factory=list, alias="remediationSteps")
    severity: IncidentSeverity | None = None
    start_time_utc: datetime | None = Field(None, alias="startTimeUtc")
    status: str | None = None
    system_alert_id: str | None = Field(None, alias="systemAlertId")
    tactics: list[str] = Field(default_factory=list)
    time_generated: datetime | None = Field(None, alias="timeGenerated")
    vendor_name: str | None = Field(None, alias="vendorName")

    class Config:
        populate_by_name = True


class SentinelEntity(BaseModel):
    """Microsoft Sentinel entity."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Entity name/ID")
    kind: EntityKind | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    # Common entity properties (flattened for convenience)
    friendly_name: str | None = Field(None, alias="friendlyName")

    class Config:
        populate_by_name = True


class SentinelComment(BaseModel):
    """Incident comment."""

    id: str = Field(..., description="Comment ID")
    name: str | None = None
    message: str | None = None
    author: dict[str, Any] | None = None
    created_time_utc: datetime | None = Field(None, alias="createdTimeUtc")

    class Config:
        populate_by_name = True


class SentinelWatchlist(BaseModel):
    """Microsoft Sentinel watchlist."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Watchlist name")
    etag: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    provider: str | None = None
    source: str | None = None
    created: datetime | None = None
    updated: datetime | None = None
    created_by: dict[str, Any] | None = Field(None, alias="createdBy")
    updated_by: dict[str, Any] | None = Field(None, alias="updatedBy")
    description: str | None = None
    watchlist_type: str | None = Field(None, alias="watchlistType")
    watchlist_alias: str | None = Field(None, alias="watchlistAlias")
    is_deleted: bool | None = Field(None, alias="isDeleted")
    labels: list[str] = Field(default_factory=list)
    default_duration: str | None = Field(None, alias="defaultDuration")
    items_search_key: str | None = Field(None, alias="itemsSearchKey")
    number_of_lines_to_skip: int | None = Field(None, alias="numberOfLinesToSkip")

    class Config:
        populate_by_name = True


class SentinelWatchlistItem(BaseModel):
    """Watchlist item."""

    id: str = Field(..., description="Item ID")
    name: str | None = None
    etag: str | None = None
    watchlist_item_type: str | None = Field(None, alias="watchlistItemType")
    watchlist_item_id: str | None = Field(None, alias="watchlistItemId")
    tenant_id: str | None = Field(None, alias="tenantId")
    is_deleted: bool | None = Field(None, alias="isDeleted")
    created: datetime | None = None
    updated: datetime | None = None
    created_by: dict[str, Any] | None = Field(None, alias="createdBy")
    updated_by: dict[str, Any] | None = Field(None, alias="updatedBy")
    items_key_value: dict[str, Any] | None = Field(None, alias="itemsKeyValue")

    class Config:
        populate_by_name = True


class SentinelHuntingQuery(BaseModel):
    """Hunting query (saved search)."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Query name")
    etag: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    query: str | None = None
    description: str | None = None
    tactics: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    required_data_connectors: list[dict[str, Any]] = Field(
        default_factory=list, alias="requiredDataConnectors"
    )

    class Config:
        populate_by_name = True


class SentinelAnalyticsRule(BaseModel):
    """Analytics rule."""

    id: str = Field(..., description="Resource ID")
    name: str = Field(..., description="Rule name")
    etag: str | None = None
    kind: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    description: str | None = None
    severity: IncidentSeverity | None = None
    enabled: bool | None = None
    query: str | None = None
    query_frequency: str | None = Field(None, alias="queryFrequency")
    query_period: str | None = Field(None, alias="queryPeriod")
    trigger_operator: str | None = Field(None, alias="triggerOperator")
    trigger_threshold: int | None = Field(None, alias="triggerThreshold")
    suppression_duration: str | None = Field(None, alias="suppressionDuration")
    suppression_enabled: bool | None = Field(None, alias="suppressionEnabled")
    tactics: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    incident_configuration: dict[str, Any] | None = Field(
        None, alias="incidentConfiguration"
    )
    event_grouping_settings: dict[str, Any] | None = Field(
        None, alias="eventGroupingSettings"
    )
    alert_details_override: dict[str, Any] | None = Field(
        None, alias="alertDetailsOverride"
    )

    class Config:
        populate_by_name = True


class KQLQueryResult(BaseModel):
    """Result of a KQL query."""

    tables: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] | None = None
    render: dict[str, Any] | None = None

    def get_rows(self, table_index: int = 0) -> list[dict[str, Any]]:
        """Get rows from a specific result table as dictionaries."""
        if not self.tables or table_index >= len(self.tables):
            return []

        table = self.tables[table_index]
        columns = table.get("columns", [])
        rows = table.get("rows", [])

        col_names = [col.get("name", f"col_{i}") for i, col in enumerate(columns)]

        return [dict(zip(col_names, row)) for row in rows]
