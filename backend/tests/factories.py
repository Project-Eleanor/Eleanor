"""Factory Boy factories for generating test data."""

import factory
from datetime import datetime, timezone
from uuid import uuid4

from app.models.case import Case, CaseStatus, Priority, Severity
from app.models.evidence import (
    CustodyAction,
    CustodyEvent,
    Evidence,
    EvidenceStatus,
    EvidenceType,
)
from app.models.user import AuthProvider, User


class UserFactory(factory.Factory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    id = factory.LazyFunction(uuid4)
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    display_name = factory.LazyAttribute(lambda obj: f"User {obj.username}")
    auth_provider = AuthProvider.SAM
    password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VQVyBJzJ/PjxKe"  # "password"
    is_active = True
    is_admin = False
    roles = ["analyst"]
    last_login = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AdminUserFactory(UserFactory):
    """Factory for creating admin User instances."""

    username = factory.Sequence(lambda n: f"admin{n}")
    is_admin = True
    roles = ["admin"]


class CaseFactory(factory.Factory):
    """Factory for creating Case instances."""

    class Meta:
        model = Case

    id = factory.LazyFunction(uuid4)
    case_number = factory.Sequence(lambda n: f"ELEANOR-2026-{n:04d}")
    title = factory.Sequence(lambda n: f"Test Case {n}")
    description = factory.LazyAttribute(lambda obj: f"Description for {obj.title}")
    severity = Severity.MEDIUM
    priority = Priority.P3
    status = CaseStatus.NEW
    assignee_id = None
    created_by = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    closed_at = None
    tags = factory.LazyFunction(list)
    mitre_tactics = factory.LazyFunction(list)
    mitre_techniques = factory.LazyFunction(list)
    metadata = factory.LazyFunction(dict)


class CriticalCaseFactory(CaseFactory):
    """Factory for creating critical severity cases."""

    severity = Severity.CRITICAL
    priority = Priority.P1
    tags = ["critical", "urgent"]


class ClosedCaseFactory(CaseFactory):
    """Factory for creating closed cases."""

    status = CaseStatus.CLOSED
    closed_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class EvidenceFactory(factory.Factory):
    """Factory for creating Evidence instances."""

    class Meta:
        model = Evidence

    id = factory.LazyFunction(uuid4)
    case_id = factory.LazyFunction(uuid4)
    filename = factory.Sequence(lambda n: f"evidence_{n}.bin")
    original_filename = factory.LazyAttribute(lambda obj: obj.filename)
    file_path = factory.LazyAttribute(lambda obj: f"/evidence/{obj.filename}")
    file_size = factory.Faker("random_int", min=1024, max=1024000)
    sha256 = factory.Faker("sha256")
    sha1 = factory.Faker("sha1")
    md5 = factory.Faker("md5")
    mime_type = "application/octet-stream"
    evidence_type = EvidenceType.ARTIFACT
    status = EvidenceStatus.READY
    source_host = factory.Sequence(lambda n: f"host-{n:03d}")
    collected_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    collected_by = "IR Team"
    uploaded_by = None
    uploaded_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    description = factory.LazyAttribute(lambda obj: f"Evidence from {obj.source_host}")
    metadata = factory.LazyFunction(dict)


class DiskImageEvidenceFactory(EvidenceFactory):
    """Factory for disk image evidence."""

    filename = factory.Sequence(lambda n: f"disk_image_{n}.dd")
    mime_type = "application/x-raw-disk-image"
    evidence_type = EvidenceType.DISK_IMAGE
    file_size = factory.Faker("random_int", min=1000000000, max=10000000000)


class MemoryDumpEvidenceFactory(EvidenceFactory):
    """Factory for memory dump evidence."""

    filename = factory.Sequence(lambda n: f"memory_{n}.raw")
    mime_type = "application/x-raw-memory-dump"
    evidence_type = EvidenceType.MEMORY_DUMP
    file_size = factory.Faker("random_int", min=500000000, max=8000000000)


class LogEvidenceFactory(EvidenceFactory):
    """Factory for log file evidence."""

    filename = factory.Sequence(lambda n: f"logs_{n}.evtx")
    mime_type = "application/x-ms-evtx"
    evidence_type = EvidenceType.LOGS
    file_size = factory.Faker("random_int", min=1000, max=100000000)


class MalwareSampleFactory(EvidenceFactory):
    """Factory for malware sample evidence."""

    filename = factory.Sequence(lambda n: f"sample_{n}.exe")
    mime_type = "application/x-executable"
    evidence_type = EvidenceType.MALWARE_SAMPLE
    status = EvidenceStatus.QUARANTINED


class CustodyEventFactory(factory.Factory):
    """Factory for creating CustodyEvent instances."""

    class Meta:
        model = CustodyEvent

    id = factory.LazyFunction(uuid4)
    evidence_id = factory.LazyFunction(uuid4)
    action = CustodyAction.UPLOADED
    actor_id = None
    actor_name = factory.Sequence(lambda n: f"User {n}")
    ip_address = "192.168.1.100"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Test Agent"
    details = factory.LazyFunction(dict)
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


# =============================================================================
# Sample Data Generators
# =============================================================================

def generate_sample_ioc_data() -> dict:
    """Generate sample IOC data for testing."""
    return {
        "ip_addresses": [
            "192.168.1.100",
            "10.0.0.50",
            "172.16.0.25",
        ],
        "domains": [
            "malware.example.com",
            "c2.badactor.net",
            "phishing.evil.org",
        ],
        "file_hashes": [
            {
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
            },
            {
                "sha256": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b3b2c7e8b3e8c4d4c",
                "sha1": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12",
                "md5": "900150983cd24fb0d6963f7d28e17f72",
            },
        ],
        "urls": [
            "https://malware.example.com/payload.exe",
            "http://c2.badactor.net/beacon",
        ],
    }


def generate_sample_mitre_data() -> dict:
    """Generate sample MITRE ATT&CK data for testing."""
    return {
        "tactics": [
            {"id": "TA0001", "name": "Initial Access"},
            {"id": "TA0002", "name": "Execution"},
            {"id": "TA0003", "name": "Persistence"},
            {"id": "TA0004", "name": "Privilege Escalation"},
            {"id": "TA0005", "name": "Defense Evasion"},
            {"id": "TA0006", "name": "Credential Access"},
            {"id": "TA0007", "name": "Discovery"},
            {"id": "TA0008", "name": "Lateral Movement"},
            {"id": "TA0009", "name": "Collection"},
            {"id": "TA0010", "name": "Exfiltration"},
            {"id": "TA0011", "name": "Command and Control"},
        ],
        "techniques": [
            {"id": "T1566", "name": "Phishing", "tactic": "TA0001"},
            {"id": "T1059", "name": "Command and Scripting Interpreter", "tactic": "TA0002"},
            {"id": "T1053", "name": "Scheduled Task/Job", "tactic": "TA0003"},
            {"id": "T1055", "name": "Process Injection", "tactic": "TA0004"},
            {"id": "T1070", "name": "Indicator Removal", "tactic": "TA0005"},
            {"id": "T1003", "name": "OS Credential Dumping", "tactic": "TA0006"},
        ],
    }


def generate_sample_endpoint_data() -> list[dict]:
    """Generate sample endpoint data for testing."""
    return [
        {
            "client_id": "C.abc123def456",
            "hostname": "WORKSTATION-001",
            "os": "Windows 10 Enterprise",
            "ip_address": "192.168.1.101",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "online": True,
            "labels": ["production", "finance"],
        },
        {
            "client_id": "C.xyz789ghi012",
            "hostname": "SERVER-001",
            "os": "Windows Server 2019",
            "ip_address": "192.168.1.10",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "online": True,
            "labels": ["production", "infrastructure"],
        },
        {
            "client_id": "C.jkl345mno678",
            "hostname": "WORKSTATION-002",
            "os": "Windows 11 Enterprise",
            "ip_address": "192.168.1.102",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "online": False,
            "labels": ["production", "hr"],
        },
    ]


def generate_sample_workflow_data() -> list[dict]:
    """Generate sample workflow data for testing."""
    return [
        {
            "id": "wf-001",
            "name": "Isolate Host",
            "description": "Isolate a compromised host from the network",
            "category": "response",
            "enabled": True,
            "requires_approval": True,
            "parameters": [
                {"name": "hostname", "type": "string", "required": True},
                {"name": "reason", "type": "string", "required": True},
            ],
        },
        {
            "id": "wf-002",
            "name": "Block IP",
            "description": "Block an IP address on the firewall",
            "category": "response",
            "enabled": True,
            "requires_approval": True,
            "parameters": [
                {"name": "ip_address", "type": "string", "required": True},
                {"name": "duration", "type": "integer", "required": False},
            ],
        },
        {
            "id": "wf-003",
            "name": "Enrich IOC",
            "description": "Automatically enrich IOCs with threat intelligence",
            "category": "enrichment",
            "enabled": True,
            "requires_approval": False,
            "parameters": [
                {"name": "ioc_value", "type": "string", "required": True},
                {"name": "ioc_type", "type": "string", "required": True},
            ],
        },
    ]


def generate_sample_timeline_events() -> list[dict]:
    """Generate sample timeline events for testing."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "timestamp": base_time.isoformat(),
            "title": "Initial phishing email received",
            "description": "User received phishing email with malicious attachment",
            "category": "email",
            "source": "exchange",
            "entities": {"users": ["jsmith"], "ips": []},
            "tags": ["phishing", "initial-access"],
        },
        {
            "timestamp": base_time.isoformat(),
            "title": "Malicious attachment executed",
            "description": "User opened malicious document triggering macro",
            "category": "process",
            "source": "edr",
            "entities": {"users": ["jsmith"], "hosts": ["WORKSTATION-001"]},
            "tags": ["execution", "macro"],
        },
        {
            "timestamp": base_time.isoformat(),
            "title": "C2 connection established",
            "description": "Outbound connection to command and control server",
            "category": "network",
            "source": "firewall",
            "entities": {"ips": ["198.51.100.50"], "hosts": ["WORKSTATION-001"]},
            "tags": ["c2", "beacon"],
        },
    ]
