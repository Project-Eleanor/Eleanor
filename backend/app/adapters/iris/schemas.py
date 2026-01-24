"""IRIS case management data models.

Models representing IRIS's API responses for cases, assets, IOCs, and notes.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class IRISCase(BaseModel):
    """IRIS case representation."""

    case_id: int
    case_uuid: str = ""
    case_name: str
    case_description: str = ""
    case_soc_id: str = ""  # External reference ID
    status_id: int = 0
    status_name: str = ""
    severity_id: int = 0
    severity_name: str = ""
    owner_id: Optional[int] = None
    owner: str = ""
    client_id: Optional[int] = None
    client_name: str = ""
    classification_id: Optional[int] = None
    classification_name: str = ""
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    modification_history: dict[str, Any] = Field(default_factory=dict)
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class IRISAsset(BaseModel):
    """IRIS case asset (affected system/account)."""

    asset_id: int
    asset_uuid: str = ""
    asset_name: str
    asset_description: str = ""
    asset_type_id: int = 0
    asset_type_name: str = ""  # Windows, Linux, Account, Network, etc.
    asset_ip: str = ""
    asset_domain: str = ""
    asset_compromise_status_id: int = 0
    case_id: int = 0
    analysis_status_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class IRISIOCEntry(BaseModel):
    """IRIS Indicator of Compromise."""

    ioc_id: int
    ioc_uuid: str = ""
    ioc_value: str
    ioc_description: str = ""
    ioc_type_id: int = 0
    ioc_type: str = ""  # IP, Domain, Hash, etc.
    ioc_tlp_id: int = 2  # Default TLP:AMBER
    ioc_tags: str = ""
    case_id: int = 0
    user_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def tlp(self) -> str:
        """Get TLP color name."""
        tlp_map = {1: "red", 2: "amber", 3: "green", 4: "white"}
        return tlp_map.get(self.ioc_tlp_id, "amber")


class IRISNote(BaseModel):
    """IRIS case note."""

    note_id: int
    note_uuid: str = ""
    note_title: str
    note_content: str = ""
    note_creationdate: Optional[datetime] = None
    note_lastupdate: Optional[datetime] = None
    group_id: int = 0
    group_title: str = ""
    case_id: int = 0
    user_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class IRISTask(BaseModel):
    """IRIS case task."""

    task_id: int
    task_uuid: str = ""
    task_title: str
    task_description: str = ""
    task_status_id: int = 0
    task_status_name: str = ""
    task_assignee_id: Optional[int] = None
    task_assignee: str = ""
    task_open_date: Optional[datetime] = None
    task_close_date: Optional[datetime] = None
    case_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class IRISAlert(BaseModel):
    """IRIS alert."""

    alert_id: int
    alert_uuid: str = ""
    alert_title: str
    alert_description: str = ""
    alert_source: str = ""
    alert_source_ref: str = ""
    alert_source_link: str = ""
    alert_severity_id: int = 0
    alert_severity_name: str = ""
    alert_status_id: int = 0
    alert_status_name: str = ""
    alert_creation_time: Optional[datetime] = None
    case_id: Optional[int] = None
    customer_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class IRISTimelineEntry(BaseModel):
    """IRIS timeline entry."""

    event_id: int
    event_uuid: str = ""
    event_title: str
    event_content: str = ""
    event_raw: str = ""
    event_source: str = ""
    event_date: Optional[datetime] = None
    event_date_wtz: Optional[datetime] = None
    event_tz: str = ""
    event_tags: str = ""
    event_color: str = ""
    event_in_summary: bool = False
    event_in_graph: bool = False
    case_id: int = 0
    custom_attributes: dict[str, Any] = Field(default_factory=dict)
