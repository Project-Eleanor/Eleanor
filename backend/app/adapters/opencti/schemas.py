"""OpenCTI threat intelligence data models.

Models based on STIX 2.1 standard as used by OpenCTI.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OpenCTIIndicator(BaseModel):
    """OpenCTI indicator (observable + context)."""

    id: str
    standard_id: str = ""  # STIX ID
    entity_type: str = "Indicator"
    name: str = ""
    description: str = ""
    pattern: str = ""  # STIX pattern
    pattern_type: str = "stix"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    x_opencti_score: int = 50  # 0-100 confidence score
    x_opencti_detection: bool = False
    created: datetime | None = None
    modified: datetime | None = None
    created_by: str = ""
    labels: list[str] = Field(default_factory=list)
    external_references: list[dict[str, Any]] = Field(default_factory=list)
    kill_chain_phases: list[dict[str, Any]] = Field(default_factory=list)


class OpenCTIObservable(BaseModel):
    """OpenCTI STIX Cyber Observable (SCO)."""

    id: str
    standard_id: str = ""
    entity_type: str = ""  # IPv4-Addr, Domain-Name, File, etc.
    observable_value: str = ""
    x_opencti_score: int = 0
    created: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)  # Related indicator IDs


class OpenCTIThreatActor(BaseModel):
    """OpenCTI threat actor (intrusion set)."""

    id: str
    standard_id: str = ""
    entity_type: str = "Threat-Actor"
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    sophistication: str = ""
    resource_level: str = ""
    primary_motivation: str = ""
    secondary_motivations: list[str] = Field(default_factory=list)
    personal_motivations: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    created: datetime | None = None
    modified: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    external_references: list[dict[str, Any]] = Field(default_factory=list)
    x_opencti_score: int = 0


class OpenCTIMalware(BaseModel):
    """OpenCTI malware definition."""

    id: str
    standard_id: str = ""
    entity_type: str = "Malware"
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    is_family: bool = False
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    malware_types: list[str] = Field(default_factory=list)
    architecture_execution_envs: list[str] = Field(default_factory=list)
    implementation_languages: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    created: datetime | None = None
    modified: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    kill_chain_phases: list[dict[str, Any]] = Field(default_factory=list)


class OpenCTICampaign(BaseModel):
    """OpenCTI campaign."""

    id: str
    standard_id: str = ""
    entity_type: str = "Campaign"
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    objective: str = ""
    created: datetime | None = None
    modified: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    external_references: list[dict[str, Any]] = Field(default_factory=list)


class OpenCTIRelationship(BaseModel):
    """OpenCTI relationship between entities."""

    id: str
    standard_id: str = ""
    entity_type: str = "Relationship"
    relationship_type: str = ""  # indicates, uses, attributed-to, etc.
    description: str = ""
    source_ref: str = ""
    target_ref: str = ""
    start_time: datetime | None = None
    stop_time: datetime | None = None
    confidence: int = 0
    created: datetime | None = None
