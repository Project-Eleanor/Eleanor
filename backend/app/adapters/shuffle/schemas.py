"""Shuffle SOAR data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ShuffleWorkflow(BaseModel):
    """Shuffle workflow definition."""

    id: str
    name: str
    description: str = ""
    image: str = ""  # Workflow icon
    status: str = "test"  # test, production
    is_valid: bool = True
    public: bool = False
    org_id: str = ""
    created: datetime | None = None
    edited: datetime | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    triggers: list[dict[str, Any]] = Field(default_factory=list)
    branches: list[dict[str, Any]] = Field(default_factory=list)
    workflow_variables: list[dict[str, Any]] = Field(default_factory=list)
    execution_variables: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def trigger_types(self) -> list[str]:
        """Get list of trigger types."""
        return [t.get("trigger_type", "") for t in self.triggers]

    @property
    def action_count(self) -> int:
        """Get number of actions in workflow."""
        return len(self.actions)


class ShuffleExecution(BaseModel):
    """Shuffle workflow execution."""

    execution_id: str = Field(alias="execution_id")
    workflow_id: str = ""
    authorization: str = ""
    status: str = ""  # EXECUTING, FINISHED, ABORTED, WAITING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""
    execution_argument: str = ""  # JSON input
    execution_source: str = ""
    execution_org: str = ""
    last_node: str = ""
    results: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        populate_by_name = True

    @property
    def is_finished(self) -> bool:
        """Check if execution is complete."""
        return self.status in ("FINISHED", "ABORTED")


class ShuffleApp(BaseModel):
    """Shuffle app (integration)."""

    id: str = ""
    name: str
    description: str = ""
    version: str = ""
    app_version: str = ""
    large_image: str = ""
    sharing: bool = False
    verified: bool = False
    categories: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    authentication: dict[str, Any] = Field(default_factory=dict)


class ShuffleOrganization(BaseModel):
    """Shuffle organization."""

    id: str
    name: str
    description: str = ""
    image: str = ""
    org_id: str = ""
    users: list[dict[str, Any]] = Field(default_factory=list)
    role: str = ""
    active_apps: list[str] = Field(default_factory=list)


class ShuffleHook(BaseModel):
    """Shuffle webhook trigger."""

    id: str
    info: dict[str, Any] = Field(default_factory=dict)
    type: str = "webhook"
    status: str = "running"
    running: bool = True
    workflow_id: str = ""
    start: str = ""  # Node ID to start from


class ShuffleSchedule(BaseModel):
    """Shuffle schedule trigger."""

    id: str
    name: str = ""
    frequency: str = ""  # cron expression or interval
    workflow_id: str = ""
    environment: str = ""
    start: str = ""
    argument: str = ""  # JSON input
