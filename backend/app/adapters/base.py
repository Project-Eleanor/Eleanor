"""Base adapter interfaces for external tool integrations.

All Eleanor adapters implement these abstract base classes to provide
consistent interfaces for case management, collection, threat intelligence,
SOAR, and timeline analysis tools.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
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
    version: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
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
    description: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[Severity] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    assignee: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalAsset:
    """Asset/host from case management system."""

    external_id: str
    name: str
    asset_type: str  # host, account, network, etc.
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    description: Optional[str] = None
    compromised: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalIOC:
    """Indicator of Compromise from case management."""

    external_id: str
    value: str
    ioc_type: IndicatorType
    description: Optional[str] = None
    tlp: str = "amber"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalNote:
    """Investigation note from case management."""

    external_id: str
    title: str
    content: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
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
        status: Optional[str] = None,
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
    async def get_case(self, external_id: str) -> Optional[ExternalCase]:
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
        description: Optional[str] = None,
        severity: Optional[Severity] = None,
        tags: Optional[list[str]] = None,
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
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[Severity] = None,
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
        resolution: Optional[str] = None,
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
    os: Optional[str] = None
    os_version: Optional[str] = None
    ip_addresses: list[str] = field(default_factory=list)
    mac_addresses: list[str] = field(default_factory=list)
    last_seen: Optional[datetime] = None
    labels: dict[str, str] = field(default_factory=dict)
    online: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionArtifact:
    """Artifact definition for collection."""

    name: str
    description: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    category: Optional[str] = None


@dataclass
class CollectionJob:
    """Collection job status."""

    job_id: str
    client_id: str
    artifact_name: str
    status: str  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_count: int = 0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hunt:
    """Hunt definition and status."""

    hunt_id: str
    name: str
    description: Optional[str] = None
    artifact_name: str
    state: str  # paused, running, stopped, completed
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
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
        search: Optional[str] = None,
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
    async def get_endpoint(self, client_id: str) -> Optional[Endpoint]:
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
        category: Optional[str] = None,
    ) -> list[CollectionArtifact]:
        """List available collection artifacts."""
        ...

    @abstractmethod
    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: Optional[dict[str, Any]] = None,
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
        state: Optional[str] = None,
    ) -> list[Hunt]:
        """List hunts."""
        ...

    @abstractmethod
    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
        target_labels: Optional[dict[str, str]] = None,
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
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatActor:
    """Threat actor profile."""

    external_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: Optional[str] = None
    motivation: Optional[str] = None
    sophistication: Optional[str] = None
    country: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    ttps: list[str] = field(default_factory=list)  # MITRE ATT&CK IDs
    associated_campaigns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Campaign:
    """Threat campaign."""

    external_id: str
    name: str
    description: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    threat_actor: Optional[str] = None
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
    async def get_threat_actor(self, name: str) -> Optional[ThreatActor]:
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
    async def get_campaign(self, name: str) -> Optional[Campaign]:
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
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
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
    description: Optional[str] = None
    category: Optional[str] = None
    triggers: list[str] = field(default_factory=list)
    is_active: bool = True
    parameters: list[dict[str, Any]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution status."""

    execution_id: str
    workflow_id: str
    workflow_name: str
    status: str  # pending, running, completed, failed, waiting_approval
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    triggered_by: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ApprovalRequest:
    """Workflow approval request."""

    approval_id: str
    execution_id: str
    workflow_name: str
    action: str
    description: str
    requested_at: datetime
    requested_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    parameters: dict[str, Any] = field(default_factory=dict)


class SOARAdapter(BaseAdapter):
    """Abstract adapter for SOAR platforms (Shuffle, Cortex XSOAR, etc.)."""

    name = "soar"
    description = "SOAR adapter"

    # Workflow management
    @abstractmethod
    async def list_workflows(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[Workflow]:
        """List available workflows."""
        ...

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow details."""
        ...

    @abstractmethod
    async def trigger_workflow(
        self,
        workflow_id: str,
        parameters: Optional[dict[str, Any]] = None,
        triggered_by: Optional[str] = None,
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
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
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
        comment: Optional[str] = None,
    ) -> bool:
        """Approve an approval request."""
        ...

    @abstractmethod
    async def deny_request(
        self,
        approval_id: str,
        denied_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Deny an approval request."""
        ...

    # Common response action shortcuts
    async def isolate_host_workflow(
        self,
        hostname: str,
        case_id: Optional[str] = None,
    ) -> WorkflowExecution:
        """Trigger host isolation workflow."""
        return await self.trigger_workflow(
            "host_isolation",
            parameters={"hostname": hostname, "case_id": case_id},
        )

    async def block_ip_workflow(
        self,
        ip_address: str,
        case_id: Optional[str] = None,
    ) -> WorkflowExecution:
        """Trigger IP blocking workflow."""
        return await self.trigger_workflow(
            "block_ip",
            parameters={"ip_address": ip_address, "case_id": case_id},
        )

    async def disable_user_workflow(
        self,
        username: str,
        case_id: Optional[str] = None,
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
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    owner: Optional[str] = None
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
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    source_type: Optional[str] = None  # plaso, csv, jsonl, etc.
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineEvent:
    """Event in a timeline."""

    event_id: str
    timestamp: datetime
    message: str
    source: Optional[str] = None
    source_short: Optional[str] = None
    timestamp_desc: Optional[str] = None
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
    created_at: Optional[datetime] = None
    owner: Optional[str] = None


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
    async def get_sketch(self, sketch_id: str) -> Optional[Sketch]:
        """Get sketch details."""
        ...

    @abstractmethod
    async def create_sketch(
        self,
        name: str,
        description: Optional[str] = None,
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
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
        timeline_ids: Optional[list[str]] = None,
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
    ) -> Optional[TimelineEvent]:
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
