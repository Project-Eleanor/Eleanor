"""Pydantic schemas for Microsoft Defender for Endpoint API responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceHealthStatus(str, Enum):
    """Device health status."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    IMPAIREDALERTS = "ImpairedAlerts"
    NOSESORDATA = "NoSensorData"


class DeviceRiskLevel(str, Enum):
    """Device risk level."""

    NONE = "None"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    INFORMATIONAL = "Informational"


class AlertSeverity(str, Enum):
    """Alert severity level."""

    INFORMATIONAL = "Informational"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AlertStatus(str, Enum):
    """Alert status."""

    NEW = "New"
    INPROGRESS = "InProgress"
    RESOLVED = "Resolved"


class AlertClassification(str, Enum):
    """Alert classification."""

    UNKNOWN = "Unknown"
    FALSEPOSITIE = "FalsePositive"
    TRUEPOSITIE = "TruePositive"


class ActionType(str, Enum):
    """Machine action type."""

    RUNANTIVIRUSSCAN = "RunAntiVirusScan"
    OFFBOARD = "Offboard"
    COLLECTINVESTIGATIONPACKAGE = "CollectInvestigationPackage"
    ISOLATE = "Isolate"
    UNISOLATE = "Unisolate"
    STOPANDQUARANTINEFILE = "StopAndQuarantineFile"
    RESTRICTCODEEXECUTION = "RestrictCodeExecution"
    UNRESTRICTCODEEXECUTION = "UnrestrictCodeExecution"


class ActionStatus(str, Enum):
    """Machine action status."""

    PENDING = "Pending"
    INPROGRESS = "InProgress"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    TIMEOUT = "TimeOut"
    CANCELLED = "Cancelled"


class DefenderDevice(BaseModel):
    """Microsoft Defender device/machine."""

    id: str = Field(..., description="Device ID")
    computer_dns_name: str | None = Field(None, alias="computerDnsName")
    first_seen: datetime | None = Field(None, alias="firstSeen")
    last_seen: datetime | None = Field(None, alias="lastSeen")
    os_platform: str | None = Field(None, alias="osPlatform")
    os_version: str | None = Field(None, alias="osVersion")
    os_processor: str | None = Field(None, alias="osProcessor")
    version: str | None = None
    last_ip_address: str | None = Field(None, alias="lastIpAddress")
    last_external_ip_address: str | None = Field(None, alias="lastExternalIpAddress")
    agent_version: str | None = Field(None, alias="agentVersion")
    health_status: DeviceHealthStatus | None = Field(None, alias="healthStatus")
    is_aad_joined: bool | None = Field(None, alias="isAadJoined")
    aad_device_id: str | None = Field(None, alias="aadDeviceId")
    machine_tags: list[str] = Field(default_factory=list, alias="machineTags")
    risk_score: DeviceRiskLevel | None = Field(None, alias="riskScore")
    exposure_level: str | None = Field(None, alias="exposureLevel")
    rbac_group_id: int | None = Field(None, alias="rbacGroupId")
    rbac_group_name: str | None = Field(None, alias="rbacGroupName")
    onboarding_status: str | None = Field(None, alias="onboardingStatus")
    device_value: str | None = Field(None, alias="deviceValue")

    class Config:
        populate_by_name = True


class DefenderAlert(BaseModel):
    """Microsoft Defender alert."""

    id: str = Field(..., description="Alert ID")
    incident_id: int | None = Field(None, alias="incidentId")
    investigation_id: int | None = Field(None, alias="investigationId")
    investigation_state: str | None = Field(None, alias="investigationState")
    assigned_to: str | None = Field(None, alias="assignedTo")
    severity: AlertSeverity | None = None
    status: AlertStatus | None = None
    classification: AlertClassification | None = None
    determination: str | None = None
    detection_source: str | None = Field(None, alias="detectionSource")
    category: str | None = None
    threat_family_name: str | None = Field(None, alias="threatFamilyName")
    title: str | None = None
    description: str | None = None
    alert_creation_time: datetime | None = Field(None, alias="alertCreationTime")
    first_event_time: datetime | None = Field(None, alias="firstEventTime")
    last_event_time: datetime | None = Field(None, alias="lastEventTime")
    last_update_time: datetime | None = Field(None, alias="lastUpdateTime")
    resolved_time: datetime | None = Field(None, alias="resolvedTime")
    machine_id: str | None = Field(None, alias="machineId")
    computer_dns_name: str | None = Field(None, alias="computerDnsName")
    aad_tenant_id: str | None = Field(None, alias="aadTenantId")
    comments: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class DefenderAction(BaseModel):
    """Microsoft Defender machine action."""

    id: str = Field(..., description="Action ID")
    type: ActionType | None = None
    title: str | None = None
    requestor: str | None = None
    requestor_comment: str | None = Field(None, alias="requestorComment")
    status: ActionStatus | None = None
    machine_id: str | None = Field(None, alias="machineId")
    computer_dns_name: str | None = Field(None, alias="computerDnsName")
    creation_date_time_utc: datetime | None = Field(None, alias="creationDateTimeUtc")
    last_update_date_time_utc: datetime | None = Field(None, alias="lastUpdateDateTimeUtc")
    cancellation_requestor: str | None = Field(None, alias="cancellationRequestor")
    cancellation_comment: str | None = Field(None, alias="cancellationComment")
    cancellation_date_time_utc: datetime | None = Field(None, alias="cancellationDateTimeUtc")
    error_hrresult: int | None = Field(None, alias="errorHResult")
    scope: str | None = None
    external_id: str | None = Field(None, alias="externalId")
    request_source: str | None = Field(None, alias="requestSource")
    related_file_info: dict[str, Any] | None = Field(None, alias="relatedFileInfo")
    commands: list[dict[str, Any]] = Field(default_factory=list)
    troubleshoot_info: str | None = Field(None, alias="troubleshootInfo")

    class Config:
        populate_by_name = True


class DefenderInvestigation(BaseModel):
    """Microsoft Defender automated investigation."""

    id: str = Field(..., description="Investigation ID")
    start_time: datetime | None = Field(None, alias="startTime")
    end_time: datetime | None = Field(None, alias="endTime")
    cancelled_by: str | None = Field(None, alias="cancelledBy")
    investigation_state: str | None = Field(None, alias="investigationState")
    status_details: str | None = Field(None, alias="statusDetails")
    machine_id: str | None = Field(None, alias="machineId")
    computer_dns_name: str | None = Field(None, alias="computerDnsName")
    triggering_alert_id: str | None = Field(None, alias="triggeringAlertId")

    class Config:
        populate_by_name = True


class DefenderFile(BaseModel):
    """File information from Defender."""

    sha1: str | None = None
    sha256: str | None = None
    md5: str | None = None
    global_prevalence: int | None = Field(None, alias="globalPrevalence")
    global_first_observed: datetime | None = Field(None, alias="globalFirstObserved")
    global_last_observed: datetime | None = Field(None, alias="globalLastObserved")
    size: int | None = None
    file_type: str | None = Field(None, alias="fileType")
    is_pe_file: bool | None = Field(None, alias="isPeFile")
    file_publisher: str | None = Field(None, alias="filePublisher")
    file_product_name: str | None = Field(None, alias="fileProductName")
    signer: str | None = None
    issuer: str | None = None
    signer_hash: str | None = Field(None, alias="signerHash")
    is_valid_certificate: bool | None = Field(None, alias="isValidCertificate")
    determination_type: str | None = Field(None, alias="determinationType")
    determination_value: str | None = Field(None, alias="determinationValue")

    class Config:
        populate_by_name = True


class LiveResponseSession(BaseModel):
    """Live response session information."""

    id: str = Field(..., description="Session ID")
    machine_id: str = Field(..., alias="machineId")
    created_by: str | None = Field(None, alias="createdBy")
    created_date_time: datetime | None = Field(None, alias="createdDateTime")
    session_status: str | None = Field(None, alias="sessionStatus")
    error_details: str | None = Field(None, alias="errorDetails")

    class Config:
        populate_by_name = True


class LiveResponseCommand(BaseModel):
    """Live response command result."""

    index: int | None = None
    start_time: datetime | None = Field(None, alias="startTime")
    end_time: datetime | None = Field(None, alias="endTime")
    command_status: str | None = Field(None, alias="commandStatus")
    errors: list[str] = Field(default_factory=list)
    value: str | None = None

    class Config:
        populate_by_name = True
