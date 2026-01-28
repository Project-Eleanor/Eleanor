"""Velociraptor data models.

These models represent Velociraptor's native data structures as returned
by the gRPC/REST API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VelociraptorClient(BaseModel):
    """Velociraptor client/endpoint."""

    client_id: str
    hostname: str = ""
    fqdn: str = ""
    os_info: dict[str, Any] = Field(default_factory=dict)
    agent_info: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_ip: str = ""
    last_interrogate_flow_id: str = ""

    @property
    def os(self) -> str:
        """Get OS name."""
        value = self.os_info.get("system", "Unknown")
        return str(value) if value else "Unknown"

    @property
    def os_version(self) -> str:
        """Get OS version."""
        value = self.os_info.get("release", "")
        return str(value) if value else ""

    @property
    def is_online(self) -> bool:
        """Check if client is considered online (seen in last 15 minutes)."""
        if not self.last_seen_at:
            return False
        delta = datetime.utcnow() - self.last_seen_at
        return delta.total_seconds() < 900  # 15 minutes


class VelociraptorArtifact(BaseModel):
    """Velociraptor artifact definition."""

    name: str
    description: str = ""
    author: str = ""
    type: str = "CLIENT"  # CLIENT, SERVER, INTERNAL
    tools: list[Any] = Field(default_factory=list)  # Can be strings or dicts
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    precondition: str = ""


class VelociraptorFlow(BaseModel):
    """Velociraptor flow (collection job)."""

    flow_id: str = Field(alias="session_id")
    client_id: str
    request: dict[str, Any] = Field(default_factory=dict)
    state: str = "UNSET"  # UNSET, RUNNING, FINISHED, ERROR
    status: str = ""
    create_time: datetime | None = None
    start_time: datetime | None = None
    active_time: datetime | None = None
    total_uploaded_files: int = 0
    total_uploaded_bytes: int = 0
    total_collected_rows: int = 0
    artifacts_with_results: list[str] = Field(default_factory=list)
    outstanding_requests: int = 0
    next_response_id: int = 0
    user_notified: bool = False

    class Config:
        populate_by_name = True

    @property
    def artifact_names(self) -> list[str]:
        """Get artifact names from request."""
        artifacts = self.request.get("artifacts", [])
        return list(artifacts) if artifacts else []


class VelociraptorHunt(BaseModel):
    """Velociraptor hunt."""

    hunt_id: str
    hunt_description: str = ""
    creator: str = ""
    create_time: datetime | None = None
    start_time: datetime | None = None
    expires: datetime | None = None
    state: str = "UNSET"  # UNSET, PAUSED, RUNNING, STOPPED, ARCHIVED
    stats: dict[str, Any] = Field(default_factory=dict)
    start_request: dict[str, Any] = Field(default_factory=dict)
    condition: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_clients_scheduled(self) -> int:
        """Get total clients scheduled."""
        value = self.stats.get("total_clients_scheduled", 0)
        return int(value) if value else 0

    @property
    def total_clients_with_results(self) -> int:
        """Get clients that have returned results."""
        value = self.stats.get("total_clients_with_results", 0)
        return int(value) if value else 0

    @property
    def artifact_names(self) -> list[str]:
        """Get artifact names from start request."""
        artifacts = self.start_request.get("artifacts", [])
        return list(artifacts) if artifacts else []


class VelociraptorFlowResult(BaseModel):
    """Result row from a Velociraptor flow."""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    artifact_name: str = ""


class VelociraptorVQLResponse(BaseModel):
    """Response from a VQL query."""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    query: str = ""
    log: list[str] = Field(default_factory=list)
