"""Timesketch timeline analysis data models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TimesketchSketch(BaseModel):
    """Timesketch sketch (investigation container)."""

    id: int
    name: str
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: dict[str, Any] = Field(default_factory=dict)
    status: list[dict[str, Any]] = Field(default_factory=list)
    timelines: list["TimesketchTimeline"] = Field(default_factory=list)
    active_timelines: list["TimesketchTimeline"] = Field(default_factory=list)
    label_string: str = ""
    acl: dict[str, Any] = Field(default_factory=dict)

    @property
    def owner(self) -> str:
        """Get sketch owner username."""
        return self.user.get("username", "")

    @property
    def status_name(self) -> str:
        """Get current status name."""
        if self.status:
            return self.status[0].get("status", "")
        return "unknown"

    @property
    def timeline_count(self) -> int:
        """Get number of timelines."""
        return len(self.timelines)


class TimesketchTimeline(BaseModel):
    """Timesketch timeline (data source within a sketch)."""

    id: int
    name: str
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: dict[str, Any] = Field(default_factory=dict)
    color: str = ""
    searchindex: dict[str, Any] = Field(default_factory=dict)
    status: list[dict[str, Any]] = Field(default_factory=list)
    datasources: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def index_name(self) -> str:
        """Get Elasticsearch index name."""
        return self.searchindex.get("index_name", "")

    @property
    def status_name(self) -> str:
        """Get current status name."""
        if self.status:
            return self.status[0].get("status", "")
        return "unknown"


class TimesketchEvent(BaseModel):
    """Timesketch timeline event."""

    # Fields renamed to avoid leading underscore (Pydantic v2 requirement)
    # The alias allows parsing JSON that uses _id, _index, _source
    es_id: str = Field(alias="_id", default="")
    es_index: str = Field(alias="_index", default="")
    es_source: dict[str, Any] = Field(alias="_source", default_factory=dict)

    model_config = {"populate_by_name": True}

    @property
    def event_id(self) -> str:
        """Get event ID."""
        return self.es_id

    @property
    def timestamp(self) -> Optional[datetime]:
        """Get event timestamp."""
        ts = self.es_source.get("datetime")
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    @property
    def message(self) -> str:
        """Get event message."""
        return self.es_source.get("message", "")

    @property
    def source_name(self) -> str:
        """Get data source name."""
        return self.es_source.get("data_type", self.es_source.get("source_name", ""))

    @property
    def source_short(self) -> str:
        """Get short source description."""
        return self.es_source.get("source_short", "")

    @property
    def timestamp_desc(self) -> str:
        """Get timestamp description."""
        return self.es_source.get("timestamp_desc", "")

    @property
    def tags(self) -> list[str]:
        """Get event tags."""
        return self.es_source.get("tag", [])

    @property
    def starred(self) -> bool:
        """Check if event is starred."""
        return "__ts_star" in self.tags

    @property
    def comments(self) -> list[str]:
        """Get event comments."""
        return self.es_source.get("__ts_comments", [])

    @property
    def attributes(self) -> dict[str, Any]:
        """Get all event attributes."""
        return self.es_source


class TimesketchSavedView(BaseModel):
    """Timesketch saved search/view."""

    id: int
    name: str
    description: str = ""
    query_string: str = ""
    query_filter: dict[str, Any] = Field(default_factory=dict)
    query_dsl: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: dict[str, Any] = Field(default_factory=dict)

    @property
    def query(self) -> str:
        """Get the query string."""
        return self.query_string

    @property
    def owner(self) -> str:
        """Get view owner username."""
        return self.user.get("username", "")


class TimesketchSearchResult(BaseModel):
    """Timesketch search result container."""

    objects: list[TimesketchEvent] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """Get total matching events."""
        return self.meta.get("total_count", len(self.objects))

    @property
    def events(self) -> list[TimesketchEvent]:
        """Get events from search result."""
        return self.objects


class TimesketchAnalyzer(BaseModel):
    """Timesketch analyzer definition."""

    name: str
    display_name: str = ""
    description: str = ""
    is_multi: bool = False


class TimesketchAnalyzerSession(BaseModel):
    """Timesketch analyzer session (running/completed analysis)."""

    id: int
    status: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    analyzer_name: str = ""
    results: str = ""
    log: str = ""
    timeline_id: int = 0
