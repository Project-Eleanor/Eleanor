"""Base adapter interfaces for external tool integrations.

All Eleanor adapters implement these abstract base classes to provide
consistent interfaces for case management, collection, threat intelligence,
SOAR, and timeline analysis tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

# =============================================================================
# Common Data Types
# =============================================================================


class AdapterStatus(str, Enum):
    """Adapter connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CONFIGURING = "configuring"
    DEGRADED = "degraded"


class Severity(str, Enum):
    """Severity levels used across adapters."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class IndicatorType(str, Enum):
    """Types of threat indicators."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    FILE_HASH_MD5 = "md5"
    FILE_HASH_SHA1 = "sha1"
    FILE_HASH_SHA256 = "sha256"
    FILE_NAME = "filename"
    REGISTRY_KEY = "registry"
    USER_AGENT = "useragent"
    CVE = "cve"
    MUTEX = "mutex"


@dataclass
class AdapterHealth:
    """Health status of an adapter."""

    adapter_name: str
    status: AdapterStatus
    version: str | None = None
    last_check: datetime = field(default_factory=datetime.utcnow)
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig:
    """Configuration for an adapter."""

    enabled: bool = False
    url: str = ""
    api_key: str = ""
    verify_ssl: bool = True
    timeout: int = 30
    extra: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Base Adapter
# =============================================================================


class BaseAdapter(ABC):
    """Abstract base class for all Eleanor adapters.

    All adapters must implement health_check and get_config methods
    to support the integration status dashboard.
    """

    name: str = "base"
    description: str = "Base adapter"

    def __init__(self, config: AdapterConfig):
        """Initialize adapter with configuration."""
        self.config = config
        self._status = AdapterStatus.DISCONNECTED

    @property
    def status(self) -> AdapterStatus:
        """Get current adapter status."""
        return self._status

    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check adapter connectivity and health.

        Returns:
            AdapterHealth with current status and any error messages.
        """
        ...

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized, no secrets).

        Returns:
            Dictionary of configuration values safe for display.
        """
        ...

    async def connect(self) -> bool:
        """Establish connection to the external service.

        Returns:
            True if connection successful, False otherwise.
        """
        health = await self.health_check()
        self._status = health.status
        return health.status == AdapterStatus.CONNECTED

    async def disconnect(self) -> None:
        """Clean up connection resources."""
        self._status = AdapterStatus.DISCONNECTED


# =============================================================================
# Case Management Adapter
# =============================================================================


@dataclass
class ExternalCase:
    """Case representation from external case management system."""

    external_id: str
    title: str
    description: str | None = None
    status: str | None = None
    severity: Severity | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    assignee: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalAsset:
    """Asset/host from case management system."""

    external_id: str
    name: str
    asset_type: str  # host, account, network, etc.
    ip_address: str | None = None
    hostname: str | None = None
    description: str | None = None
    compromised: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalIOC:
    """Indicator of Compromise from case management."""

    external_id: str
    value: str
    ioc_type: IndicatorType
    description: str | None = None
    tlp: str = "amber"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalNote:
    """Investigation note from case management."""

    external_id: str
    title: str
    content: str
    author: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CaseManagementAdapter(BaseAdapter):
    """Abstract adapter for case management systems (IRIS, TheHive, etc.)."""

    name = "case_management"
    description = "Case management adapter"

    @abstractmethod
    async def list_cases(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[ExternalCase]:
        """List cases from external system.

        Args:
            limit: Maximum number of cases to return.
            offset: Pagination offset.
            status: Filter by case status.

        Returns:
            List of ExternalCase objects.
        """
        ...

    @abstractmethod
    async def get_case(self, external_id: str) -> ExternalCase | None:
        """Get a specific case by external ID.

        Args:
            external_id: The case ID in the external system.

        Returns:
            ExternalCase if found, None otherwise.
        """
        ...

    @abstractmethod
    async def create_case(
        self,
        title: str,
        description: str | None = None,
        severity: Severity | None = None,
        tags: list[str] | None = None,
    ) -> ExternalCase:
        """Create a new case in external system.

        Args:
            title: Case title.
            description: Case description.
            severity: Case severity level.
            tags: List of tags.

        Returns:
            Created ExternalCase.
        """
        ...

    @abstractmethod
    async def update_case(
        self,
        external_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        severity: Severity | None = None,
    ) -> ExternalCase:
        """Update an existing case.

        Args:
            external_id: The case ID in the external system.
            title: New title (optional).
            description: New description (optional).
            status: New status (optional).
            severity: New severity (optional).

        Returns:
            Updated ExternalCase.
        """
        ...

    @abstractmethod
    async def close_case(
        self,
        external_id: str,
        resolution: str | None = None,
    ) -> ExternalCase:
        """Close a case.

        Args:
            external_id: The case ID in the external system.
            resolution: Resolution notes.

        Returns:
            Updated ExternalCase.
        """
        ...

    @abstractmethod
    async def sync_case(
        self,
        eleanor_id: UUID,
        external_id: str,
    ) -> bool:
        """Sync an Eleanor case with external case management.

        Args:
            eleanor_id: Eleanor's internal case UUID.
            external_id: External system's case ID.

        Returns:
            True if sync successful.
        """
        ...

    # Asset management
    @abstractmethod
    async def list_assets(self, case_id: str) -> list[ExternalAsset]:
        """List assets associated with a case."""
        ...

    @abstractmethod
    async def add_asset(
        self,
        case_id: str,
        asset: ExternalAsset,
    ) -> ExternalAsset:
        """Add an asset to a case."""
        ...

    # IOC management
    @abstractmethod
    async def list_iocs(self, case_id: str) -> list[ExternalIOC]:
        """List IOCs associated with a case."""
        ...

    @abstractmethod
    async def add_ioc(
        self,
        case_id: str,
        ioc: ExternalIOC,
    ) -> ExternalIOC:
        """Add an IOC to a case."""
        ...

    # Notes
    @abstractmethod
    async def list_notes(self, case_id: str) -> list[ExternalNote]:
        """List notes for a case."""
        ...

    @abstractmethod
    async def add_note(
        self,
        case_id: str,
        note: ExternalNote,
    ) -> ExternalNote:
        """Add a note to a case."""
        ...


# =============================================================================
# Collection Adapter (EDR/Endpoint)
# =============================================================================


@dataclass
class Endpoint:
    """Endpoint/client from collection system."""

    client_id: str
    hostname: str
    os: str | None = None
    os_version: str | None = None
    ip_addresses: list[str] = field(default_factory=list)
    mac_addresses: list[str] = field(default_factory=list)
    last_seen: datetime | None = None
    labels: dict[str, str] = field(default_factory=dict)
    online: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionArtifact:
    """Artifact definition for collection."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    category: str | None = None


@dataclass
class CollectionJob:
    """Collection job status."""

    job_id: str
    client_id: str
    artifact_name: str
    status: str  # pending, running, completed, failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hunt:
    """Hunt definition and status."""

    hunt_id: str
    name: str
    artifact_name: str
    state: str  # paused, running, stopped, completed
    description: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    total_clients: int = 0
    completed_clients: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CollectionAdapter(BaseAdapter):
    """Abstract adapter for endpoint collection tools (Velociraptor, etc.)."""

    name = "collection"
    description = "Endpoint collection adapter"

    # Endpoint management
    @abstractmethod
    async def list_endpoints(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        online_only: bool = False,
    ) -> list[Endpoint]:
        """List managed endpoints.

        Args:
            limit: Maximum endpoints to return.
            offset: Pagination offset.
            search: Search query for hostname/IP.
            online_only: Only return currently online endpoints.

        Returns:
            List of Endpoint objects.
        """
        ...

    @abstractmethod
    async def get_endpoint(self, client_id: str) -> Endpoint | None:
        """Get a specific endpoint by client ID."""
        ...

    @abstractmethod
    async def search_endpoints(self, query: str) -> list[Endpoint]:
        """Search endpoints by hostname, IP, or label."""
        ...

    # Artifact collection
    @abstractmethod
    async def list_artifacts(
        self,
        category: str | None = None,
    ) -> list[CollectionArtifact]:
        """List available collection artifacts."""
        ...

    @abstractmethod
    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: dict[str, Any] | None = None,
        urgent: bool = False,
    ) -> CollectionJob:
        """Trigger artifact collection on an endpoint.

        Args:
            client_id: Target endpoint ID.
            artifact_name: Name of artifact to collect.
            parameters: Artifact parameters.
            urgent: Priority collection (faster but more resource intensive).

        Returns:
            CollectionJob with job tracking info.
        """
        ...

    @abstractmethod
    async def get_collection_status(self, job_id: str) -> CollectionJob:
        """Get status of a collection job."""
        ...

    @abstractmethod
    async def get_collection_results(
        self,
        job_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get results from a completed collection job."""
        ...

    # Hunt management
    @abstractmethod
    async def list_hunts(
        self,
        limit: int = 50,
        state: str | None = None,
    ) -> list[Hunt]:
        """List hunts."""
        ...

    @abstractmethod
    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        target_labels: dict[str, str] | None = None,
        expires_hours: int = 168,
    ) -> Hunt:
        """Create a new hunt.

        Args:
            name: Hunt name.
            artifact_name: Artifact to hunt with.
            description: Hunt description.
            parameters: Artifact parameters.
            target_labels: Label-based targeting.
            expires_hours: Hours until hunt expires.

        Returns:
            Created Hunt.
        """
        ...

    @abstractmethod
    async def start_hunt(self, hunt_id: str) -> Hunt:
        """Start a paused hunt."""
        ...

    @abstractmethod
    async def stop_hunt(self, hunt_id: str) -> Hunt:
        """Stop a running hunt."""
        ...

    @abstractmethod
    async def get_hunt_results(
        self,
        hunt_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get aggregated results from a hunt."""
        ...

    # Response actions
    @abstractmethod
    async def isolate_host(self, client_id: str) -> bool:
        """Isolate a host from the network.

        Returns:
            True if isolation command sent successfully.
        """
        ...

    @abstractmethod
    async def unisolate_host(self, client_id: str) -> bool:
        """Remove network isolation from a host."""
        ...

    @abstractmethod
    async def quarantine_file(
        self,
        client_id: str,
        file_path: str,
    ) -> bool:
        """Quarantine a file on an endpoint."""
        ...

    @abstractmethod
    async def kill_process(
        self,
        client_id: str,
        pid: int,
    ) -> bool:
        """Kill a process on an endpoint."""
        ...


# =============================================================================
# Threat Intelligence Adapter
# =============================================================================


@dataclass
class ThreatIndicator:
    """Threat indicator with enrichment data."""

    value: str
    indicator_type: IndicatorType
    score: int = 0  # 0-100 risk score
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatActor:
    """Threat actor profile."""

    external_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    motivation: str | None = None
    sophistication: str | None = None
    country: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    ttps: list[str] = field(default_factory=list)  # MITRE ATT&CK IDs
    associated_campaigns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Campaign:
    """Threat campaign."""

    external_id: str
    name: str
    description: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    threat_actor: str | None = None
    targets: list[str] = field(default_factory=list)
    malware: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnrichmentResult:
    """Result of indicator enrichment."""

    indicator: ThreatIndicator
    risk_score: int
    verdict: str  # malicious, suspicious, clean, unknown
    threat_actors: list[ThreatActor] = field(default_factory=list)
    campaigns: list[Campaign] = field(default_factory=list)
    related_indicators: list[ThreatIndicator] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


class ThreatIntelAdapter(BaseAdapter):
    """Abstract adapter for threat intelligence platforms (OpenCTI, MISP, etc.)."""

    name = "threat_intel"
    description = "Threat intelligence adapter"

    @abstractmethod
    async def enrich_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
    ) -> EnrichmentResult:
        """Enrich an indicator with threat intelligence.

        Args:
            value: The indicator value (IP, domain, hash, etc.).
            indicator_type: Type of indicator.

        Returns:
            EnrichmentResult with full context.
        """
        ...

    @abstractmethod
    async def bulk_enrich(
        self,
        indicators: list[tuple[str, IndicatorType]],
    ) -> list[EnrichmentResult]:
        """Bulk enrich multiple indicators."""
        ...

    @abstractmethod
    async def get_threat_actor(self, name: str) -> ThreatActor | None:
        """Get threat actor profile by name."""
        ...

    @abstractmethod
    async def search_threat_actors(
        self,
        query: str,
        limit: int = 20,
    ) -> list[ThreatActor]:
        """Search threat actors."""
        ...

    @abstractmethod
    async def get_campaign(self, name: str) -> Campaign | None:
        """Get campaign by name."""
        ...

    @abstractmethod
    async def search_campaigns(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Campaign]:
        """Search campaigns."""
        ...

    @abstractmethod
    async def get_related_indicators(
        self,
        value: str,
        indicator_type: IndicatorType,
        limit: int = 50,
    ) -> list[ThreatIndicator]:
        """Get indicators related to the given indicator."""
        ...

    @abstractmethod
    async def submit_indicator(
        self,
        value: str,
        indicator_type: IndicatorType,
        description: str | None = None,
        tags: list[str] | None = None,
        confidence: int = 50,
    ) -> ThreatIndicator:
        """Submit a new indicator to the threat intel platform."""
        ...


# =============================================================================
# SOAR Adapter
# =============================================================================


@dataclass
class Workflow:
    """SOAR workflow definition."""

    workflow_id: str
    name: str
    description: str | None = None
    category: str | None = None
    triggers: list[str] = field(default_factory=list)
    is_active: bool = True
    parameters: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution status."""

    execution_id: str
    workflow_id: str
    workflow_name: str
    status: str  # pending, running, completed, failed, waiting_approval
    started_at: datetime | None = None
    completed_at: datetime | None = None
    triggered_by: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ApprovalRequest:
    """Workflow approval request."""

    approval_id: str
    execution_id: str
    workflow_name: str
    action: str
    description: str
    requested_at: datetime
    requested_by: str | None = None
    expires_at: datetime | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


class SOARAdapter(BaseAdapter):
    """Abstract adapter for SOAR platforms (Shuffle, Cortex XSOAR, etc.)."""

    name = "soar"
    description = "SOAR adapter"

    # Workflow management
    @abstractmethod
    async def list_workflows(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[Workflow]:
        """List available workflows."""
        ...

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get workflow details."""
        ...

    @abstractmethod
    async def trigger_workflow(
        self,
        workflow_id: str,
        parameters: dict[str, Any] | None = None,
        triggered_by: str | None = None,
    ) -> WorkflowExecution:
        """Trigger a workflow execution.

        Args:
            workflow_id: ID of workflow to trigger.
            parameters: Input parameters for workflow.
            triggered_by: User/system that triggered execution.

        Returns:
            WorkflowExecution tracking object.
        """
        ...

    @abstractmethod
    async def get_execution_status(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """Get workflow execution status."""
        ...

    @abstractmethod
    async def list_executions(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowExecution]:
        """List workflow executions."""
        ...

    @abstractmethod
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running workflow execution."""
        ...

    # Approval management
    @abstractmethod
    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        """List pending approval requests."""
        ...

    @abstractmethod
    async def approve_request(
        self,
        approval_id: str,
        approved_by: str,
        comment: str | None = None,
    ) -> bool:
        """Approve an approval request."""
        ...

    @abstractmethod
    async def deny_request(
        self,
        approval_id: str,
        denied_by: str,
        reason: str | None = None,
    ) -> bool:
        """Deny an approval request."""
        ...

    # Common response action shortcuts
    async def isolate_host_workflow(
        self,
        hostname: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger host isolation workflow."""
        return await self.trigger_workflow(
            "host_isolation",
            parameters={"hostname": hostname, "case_id": case_id},
        )

    async def block_ip_workflow(
        self,
        ip_address: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger IP blocking workflow."""
        return await self.trigger_workflow(
            "block_ip",
            parameters={"ip_address": ip_address, "case_id": case_id},
        )

    async def disable_user_workflow(
        self,
        username: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger user disable workflow."""
        return await self.trigger_workflow(
            "disable_user",
            parameters={"username": username, "case_id": case_id},
        )


# =============================================================================
# Timeline Adapter
# =============================================================================


@dataclass
class Sketch:
    """Timeline sketch/investigation."""

    sketch_id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    owner: str | None = None
    status: str = "active"
    timeline_count: int = 0
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Timeline:
    """Individual timeline within a sketch."""

    timeline_id: str
    sketch_id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    source_type: str | None = None  # plaso, csv, jsonl, etc.
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineEvent:
    """Event in a timeline."""

    event_id: str
    timestamp: datetime
    message: str
    source: str | None = None
    source_short: str | None = None
    timestamp_desc: str | None = None
    tags: list[str] = field(default_factory=list)
    starred: bool = False
    comments: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SavedView:
    """Saved search/view in timeline."""

    view_id: str
    sketch_id: str
    name: str
    query: str
    created_at: datetime | None = None
    owner: str | None = None


class TimelineAdapter(BaseAdapter):
    """Abstract adapter for timeline analysis tools (Timesketch, etc.)."""

    name = "timeline"
    description = "Timeline analysis adapter"

    # Sketch management
    @abstractmethod
    async def list_sketches(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Sketch]:
        """List timeline sketches."""
        ...

    @abstractmethod
    async def get_sketch(self, sketch_id: str) -> Sketch | None:
        """Get sketch details."""
        ...

    @abstractmethod
    async def create_sketch(
        self,
        name: str,
        description: str | None = None,
    ) -> Sketch:
        """Create a new sketch."""
        ...

    @abstractmethod
    async def delete_sketch(self, sketch_id: str) -> bool:
        """Delete a sketch."""
        ...

    # Timeline management
    @abstractmethod
    async def list_timelines(self, sketch_id: str) -> list[Timeline]:
        """List timelines in a sketch."""
        ...

    @abstractmethod
    async def upload_timeline(
        self,
        sketch_id: str,
        name: str,
        file_path: str,
        source_type: str = "jsonl",
    ) -> Timeline:
        """Upload a timeline file to a sketch."""
        ...

    @abstractmethod
    async def delete_timeline(
        self,
        sketch_id: str,
        timeline_id: str,
    ) -> bool:
        """Delete a timeline from a sketch."""
        ...

    # Event search
    @abstractmethod
    async def search_events(
        self,
        sketch_id: str,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
        timeline_ids: list[str] | None = None,
    ) -> list[TimelineEvent]:
        """Search events in a sketch.

        Args:
            sketch_id: Target sketch.
            query: Search query (Lucene/OpenSearch syntax).
            start_time: Filter events after this time.
            end_time: Filter events before this time.
            limit: Maximum events to return.
            timeline_ids: Limit search to specific timelines.

        Returns:
            List of matching TimelineEvents.
        """
        ...

    @abstractmethod
    async def get_event(
        self,
        sketch_id: str,
        event_id: str,
    ) -> TimelineEvent | None:
        """Get a specific event."""
        ...

    # Annotations
    @abstractmethod
    async def tag_event(
        self,
        sketch_id: str,
        event_id: str,
        tags: list[str],
    ) -> TimelineEvent:
        """Add tags to an event."""
        ...

    @abstractmethod
    async def star_event(
        self,
        sketch_id: str,
        event_id: str,
        starred: bool = True,
    ) -> TimelineEvent:
        """Star/unstar an event."""
        ...

    @abstractmethod
    async def add_comment(
        self,
        sketch_id: str,
        event_id: str,
        comment: str,
    ) -> TimelineEvent:
        """Add a comment to an event."""
        ...

    # Saved views
    @abstractmethod
    async def list_saved_views(self, sketch_id: str) -> list[SavedView]:
        """List saved views in a sketch."""
        ...

    @abstractmethod
    async def create_saved_view(
        self,
        sketch_id: str,
        name: str,
        query: str,
    ) -> SavedView:
        """Create a saved view."""
        ...

    @abstractmethod
    async def delete_saved_view(
        self,
        sketch_id: str,
        view_id: str,
    ) -> bool:
        """Delete a saved view."""
        ...


# =============================================================================
# TICKETING ADAPTER
# =============================================================================


@dataclass
class Ticket:
    """Representation of a ticket in an external ticketing system.

    PATTERN: Data Transfer Object (DTO)
    Provides a normalized view of tickets across different ticketing systems
    (Jira, ServiceNow, etc.) enabling consistent handling in Eleanor workflows.
    """

    ticket_id: str
    key: str  # External key (e.g., "DFIR-123" in Jira)
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    assignee: str | None = None
    reporter: str | None = None
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None
    case_id: str | None = None  # Linked Eleanor case
    url: str | None = None  # Web URL to view ticket
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketComment:
    """A comment on a ticket.

    PATTERN: Data Transfer Object (DTO)
    Normalizes comment representation across ticketing systems.
    """

    comment_id: str
    ticket_id: str
    author: str
    body: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_internal: bool = False  # Internal/private comment
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketTransition:
    """Available status transition for a ticket.

    PATTERN: Data Transfer Object (DTO)
    Represents possible workflow transitions in ticketing systems.
    """

    transition_id: str
    name: str
    to_status: str
    requires_fields: list[str] = field(default_factory=list)


class TicketPriority(str, Enum):
    """Standard ticket priority levels.

    DESIGN DECISION: Using string enum for serialization compatibility
    and mapping to various ticketing system priority schemes.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRIVIAL = "trivial"


class TicketingAdapter(BaseAdapter):
    """Abstract base for ticketing system integration.

    PATTERN: Adapter Pattern
    Provides a unified interface for ticketing systems (Jira, ServiceNow, etc.)
    enabling Eleanor to create, update, and track incident tickets.

    EXTENSION POINT: Implement this class to add new ticketing integrations.
    See adapters/jira/adapter.py for reference implementation.

    Capabilities:
    - Ticket CRUD operations
    - Comment management
    - Case linking for investigation tracking
    - Status workflow transitions
    - Attachment support
    """

    @abstractmethod
    async def create_ticket(
        self,
        title: str,
        description: str,
        priority: TicketPriority | str = TicketPriority.MEDIUM,
        labels: list[str] | None = None,
        assignee: str | None = None,
        project_key: str | None = None,
        issue_type: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Ticket:
        """Create a new ticket.

        Args:
            title: Ticket summary/title
            description: Detailed description (supports markdown in most systems)
            priority: Ticket priority level
            labels: Tags/labels to apply
            assignee: Username or email of assignee
            project_key: Project identifier (e.g., "DFIR" in Jira)
            issue_type: Type of issue (e.g., "Bug", "Task", "Incident")
            custom_fields: System-specific custom field values

        Returns:
            Created ticket with assigned ID and key
        """
        ...

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Get a ticket by ID or key.

        Args:
            ticket_id: Ticket ID or key (e.g., "DFIR-123")

        Returns:
            Ticket if found, None otherwise
        """
        ...

    @abstractmethod
    async def update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: TicketPriority | str | None = None,
        labels: list[str] | None = None,
        assignee: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Ticket:
        """Update an existing ticket.

        Args:
            ticket_id: Ticket ID or key
            title: New title (None to keep existing)
            description: New description
            priority: New priority
            labels: New labels (replaces existing)
            assignee: New assignee
            custom_fields: Custom field updates

        Returns:
            Updated ticket
        """
        ...

    @abstractmethod
    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        is_internal: bool = False,
    ) -> TicketComment:
        """Add a comment to a ticket.

        Args:
            ticket_id: Ticket ID or key
            comment: Comment body (supports markdown)
            is_internal: Whether comment is internal/private

        Returns:
            Created comment
        """
        ...

    @abstractmethod
    async def get_comments(
        self,
        ticket_id: str,
        limit: int = 50,
    ) -> list[TicketComment]:
        """Get comments on a ticket.

        Args:
            ticket_id: Ticket ID or key
            limit: Maximum comments to return

        Returns:
            List of comments, newest first
        """
        ...

    @abstractmethod
    async def link_to_case(
        self,
        ticket_id: str,
        case_id: str,
        link_type: str = "relates_to",
    ) -> bool:
        """Link a ticket to an Eleanor case.

        DESIGN DECISION: Uses custom field or description update to store
        case reference, as most ticketing systems don't have native
        Eleanor integration.

        Args:
            ticket_id: Ticket ID or key
            case_id: Eleanor case ID
            link_type: Type of relationship

        Returns:
            True if linked successfully
        """
        ...

    @abstractmethod
    async def get_transitions(self, ticket_id: str) -> list[TicketTransition]:
        """Get available status transitions for a ticket.

        Args:
            ticket_id: Ticket ID or key

        Returns:
            List of available transitions
        """
        ...

    @abstractmethod
    async def transition_ticket(
        self,
        ticket_id: str,
        transition_id: str,
        resolution: str | None = None,
        comment: str | None = None,
    ) -> Ticket:
        """Transition a ticket to a new status.

        Args:
            ticket_id: Ticket ID or key
            transition_id: Transition ID from get_transitions()
            resolution: Resolution value (for close transitions)
            comment: Optional comment to add with transition

        Returns:
            Updated ticket
        """
        ...

    @abstractmethod
    async def close_ticket(
        self,
        ticket_id: str,
        resolution: str = "Done",
        comment: str | None = None,
    ) -> Ticket:
        """Close a ticket with resolution.

        DESIGN DECISION: Provides convenience method that finds appropriate
        close transition automatically, as transition IDs vary by system.

        Args:
            ticket_id: Ticket ID or key
            resolution: Resolution type (e.g., "Done", "Won't Do", "Duplicate")
            comment: Optional closing comment

        Returns:
            Closed ticket
        """
        ...

    @abstractmethod
    async def search_tickets(
        self,
        query: str,
        project_key: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        limit: int = 50,
    ) -> list[Ticket]:
        """Search tickets.

        Args:
            query: Search query (system-specific syntax)
            project_key: Filter by project
            status: Filter by status
            assignee: Filter by assignee
            labels: Filter by labels (all must match)
            limit: Maximum results

        Returns:
            Matching tickets
        """
        ...

    async def add_attachment(
        self,
        ticket_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """Add an attachment to a ticket.

        EXTENSION POINT: Override in implementations that support attachments.

        Args:
            ticket_id: Ticket ID or key
            filename: Attachment filename
            content: File content
            content_type: MIME type

        Returns:
            True if attached successfully
        """
        raise NotImplementedError("Attachments not supported by this adapter")

    async def get_linked_cases(self, ticket_id: str) -> list[str]:
        """Get Eleanor case IDs linked to a ticket.

        Args:
            ticket_id: Ticket ID or key

        Returns:
            List of linked case IDs
        """
        ticket = await self.get_ticket(ticket_id)
        if ticket and ticket.case_id:
            return [ticket.case_id]
        return []


# =============================================================================
# SIEM ADAPTER
# =============================================================================


@dataclass
class SavedSearch:
    """Representation of a saved search/query in a SIEM.

    PATTERN: Data Transfer Object (DTO)
    Normalizes saved search representation across SIEM platforms.
    """

    search_id: str
    name: str
    query: str
    description: str = ""
    owner: str | None = None
    is_scheduled: bool = False
    schedule: str | None = None  # Cron expression
    last_run: datetime | None = None
    next_run: datetime | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SIEMAlert:
    """Representation of an alert from a SIEM.

    PATTERN: Data Transfer Object (DTO)
    Normalizes alert representation across SIEM platforms.
    """

    alert_id: str
    name: str
    description: str = ""
    severity: Severity = Severity.MEDIUM
    status: str = "new"
    trigger_time: datetime | None = None
    source_search: str | None = None
    result_count: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexInfo:
    """Information about a SIEM index/data source.

    PATTERN: Data Transfer Object (DTO)
    """

    name: str
    event_count: int = 0
    size_bytes: int = 0
    earliest_time: datetime | None = None
    latest_time: datetime | None = None
    fields: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SIEMAdapter(TimelineAdapter):
    """Abstract base for SIEM integration with bidirectional data flow.

    PATTERN: Adapter Pattern
    Extends TimelineAdapter to provide bidirectional SIEM integration,
    allowing Eleanor to both query events from and send events to SIEM platforms.

    EXTENSION POINT: Implement this class to add new SIEM integrations.
    See adapters/splunk/adapter.py for reference implementation.

    Capabilities:
    - Bidirectional event flow (query and ingest)
    - Saved search management
    - Alert retrieval and management
    - Index/data source management
    """

    # Event sending

    @abstractmethod
    async def send_events(
        self,
        events: list[dict[str, Any]],
        index: str | None = None,
        source: str = "eleanor",
        sourcetype: str = "eleanor:events",
    ) -> int:
        """Send events to the SIEM.

        Args:
            events: List of event dictionaries
            index: Target index (uses default if not specified)
            source: Source identifier
            sourcetype: Source type for the events

        Returns:
            Number of events successfully sent
        """
        ...

    @abstractmethod
    async def send_event(
        self,
        event: dict[str, Any],
        index: str | None = None,
        source: str = "eleanor",
        sourcetype: str = "eleanor:events",
    ) -> bool:
        """Send a single event to the SIEM.

        Args:
            event: Event dictionary
            index: Target index
            source: Source identifier
            sourcetype: Source type

        Returns:
            True if sent successfully
        """
        ...

    # Saved searches

    @abstractmethod
    async def list_saved_searches(
        self,
        owner: str | None = None,
        scheduled_only: bool = False,
        limit: int = 100,
    ) -> list[SavedSearch]:
        """List saved searches.

        Args:
            owner: Filter by owner
            scheduled_only: Only return scheduled searches
            limit: Maximum results

        Returns:
            List of saved searches
        """
        ...

    @abstractmethod
    async def get_saved_search(self, search_id: str) -> SavedSearch | None:
        """Get a saved search by ID or name.

        Args:
            search_id: Search ID or name

        Returns:
            Saved search or None
        """
        ...

    @abstractmethod
    async def create_saved_search(
        self,
        name: str,
        query: str,
        description: str | None = None,
        schedule: str | None = None,
        enabled: bool = True,
    ) -> SavedSearch:
        """Create a new saved search.

        Args:
            name: Search name
            query: Search query in SIEM's query language
            description: Optional description
            schedule: Cron expression for scheduling
            enabled: Whether the search is enabled

        Returns:
            Created saved search
        """
        ...

    @abstractmethod
    async def update_saved_search(
        self,
        search_id: str,
        name: str | None = None,
        query: str | None = None,
        description: str | None = None,
        schedule: str | None = None,
        enabled: bool | None = None,
    ) -> SavedSearch:
        """Update a saved search.

        Args:
            search_id: Search ID or name
            name: New name
            query: New query
            description: New description
            schedule: New schedule
            enabled: New enabled state

        Returns:
            Updated saved search
        """
        ...

    @abstractmethod
    async def delete_saved_search(self, search_id: str) -> bool:
        """Delete a saved search.

        Args:
            search_id: Search ID or name

        Returns:
            True if deleted
        """
        ...

    @abstractmethod
    async def run_saved_search(
        self,
        search_id: str,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Run a saved search and return results.

        Args:
            search_id: Search ID or name
            earliest_time: Override earliest time
            latest_time: Override latest time

        Returns:
            Search results
        """
        ...

    # Alerts

    @abstractmethod
    async def list_alerts(
        self,
        severity: Severity | None = None,
        status: str | None = None,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
        limit: int = 100,
    ) -> list[SIEMAlert]:
        """List triggered alerts.

        Args:
            severity: Filter by severity
            status: Filter by status
            earliest_time: Start of time range
            latest_time: End of time range
            limit: Maximum results

        Returns:
            List of alerts
        """
        ...

    @abstractmethod
    async def get_alert(self, alert_id: str) -> SIEMAlert | None:
        """Get an alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert or None
        """
        ...

    @abstractmethod
    async def update_alert_status(
        self,
        alert_id: str,
        status: str,
        comment: str | None = None,
    ) -> SIEMAlert:
        """Update alert status.

        Args:
            alert_id: Alert ID
            status: New status
            comment: Optional comment

        Returns:
            Updated alert
        """
        ...

    # Index management

    @abstractmethod
    async def list_indexes(self) -> list[IndexInfo]:
        """List available indexes/data sources.

        Returns:
            List of index information
        """
        ...

    @abstractmethod
    async def get_index_info(self, index_name: str) -> IndexInfo | None:
        """Get information about an index.

        Args:
            index_name: Index name

        Returns:
            Index info or None
        """
        ...

    # Query helpers

    async def query_by_ioc(
        self,
        ioc_value: str,
        ioc_type: str,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Search for events containing an IOC.

        EXTENSION POINT: Override to implement SIEM-specific IOC search.

        Args:
            ioc_value: IOC value
            ioc_type: IOC type (ip, domain, hash, etc.)
            earliest_time: Start of time range
            latest_time: End of time range
            limit: Maximum results

        Returns:
            Matching events
        """
        # Default implementation - override for better performance
        query = f'"{ioc_value}"'
        return await self.search_events(
            query=query,
            start_time=earliest_time,
            end_time=latest_time,
            limit=limit,
        )

    async def get_field_summary(
        self,
        index: str,
        field: str,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get summary statistics for a field.

        EXTENSION POINT: Override to implement SIEM-specific field summary.

        Args:
            index: Index to search
            field: Field to summarize
            earliest_time: Start of time range
            latest_time: End of time range
            limit: Maximum unique values

        Returns:
            Field value counts
        """
        raise NotImplementedError("Field summary not implemented")
