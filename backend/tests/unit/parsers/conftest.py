"""Shared fixtures for parser unit tests.

Provides sample test data, mock files, and common utilities for testing
Eleanor's evidence parsers.
"""

import json
import struct
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest


@pytest.fixture
def tmp_evidence_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test evidence files."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    return evidence_dir


@pytest.fixture
def sample_json_events() -> list[dict]:
    """Sample JSON event data for testing."""
    return [
        {
            "timestamp": "2026-01-15T10:30:00Z",
            "event_type": "login",
            "user": "admin",
            "source_ip": "192.168.1.100",
            "status": "success",
        },
        {
            "timestamp": "2026-01-15T10:31:00Z",
            "event_type": "file_access",
            "user": "admin",
            "file_path": "/etc/passwd",
            "action": "read",
        },
        {
            "timestamp": "2026-01-15T10:32:00Z",
            "event_type": "process_start",
            "user": "root",
            "process_name": "bash",
            "pid": 1234,
            "command_line": "/bin/bash -c 'whoami'",
        },
    ]


@pytest.fixture
def sample_json_file(tmp_evidence_dir: Path, sample_json_events: list[dict]) -> Path:
    """Create a sample JSON file with test events."""
    json_file = tmp_evidence_dir / "test_events.json"
    json_file.write_text(json.dumps(sample_json_events))
    return json_file


@pytest.fixture
def sample_jsonl_file(tmp_evidence_dir: Path, sample_json_events: list[dict]) -> Path:
    """Create a sample JSONL (newline-delimited) file with test events."""
    jsonl_file = tmp_evidence_dir / "test_events.jsonl"
    lines = [json.dumps(event) for event in sample_json_events]
    jsonl_file.write_text("\n".join(lines))
    return jsonl_file


@pytest.fixture
def sample_cloudtrail_events() -> list[dict]:
    """Sample AWS CloudTrail events for testing."""
    return [
        {
            "eventVersion": "1.08",
            "userIdentity": {
                "type": "IAMUser",
                "principalId": "AIDAEXAMPLE",
                "arn": "arn:aws:iam::123456789012:user/admin",
                "accountId": "123456789012",
                "userName": "admin",
            },
            "eventTime": "2026-01-15T10:30:00Z",
            "eventSource": "signin.amazonaws.com",
            "eventName": "ConsoleLogin",
            "awsRegion": "us-east-1",
            "sourceIPAddress": "203.0.113.50",
            "userAgent": "Mozilla/5.0",
            "requestParameters": None,
            "responseElements": {"ConsoleLogin": "Success"},
            "eventID": "abc12345-1234-1234-1234-abc123456789",
            "eventType": "AwsConsoleSignIn",
        },
    ]


@pytest.fixture
def sample_cloudtrail_file(
    tmp_evidence_dir: Path, sample_cloudtrail_events: list[dict]
) -> Path:
    """Create a sample CloudTrail JSON file."""
    ct_file = tmp_evidence_dir / "cloudtrail.json"
    ct_data = {"Records": sample_cloudtrail_events}
    ct_file.write_text(json.dumps(ct_data))
    return ct_file


@pytest.fixture
def minimal_evtx_header() -> bytes:
    """Create minimal EVTX file header for testing can_parse detection.

    Note: This is just the magic header, not a valid complete EVTX file.
    """
    # EVTX magic: "ElfFile\x00"
    return b"ElfFile\x00"


@pytest.fixture
def sample_evtx_bytes(minimal_evtx_header: bytes) -> BytesIO:
    """Create a BytesIO with EVTX magic header for testing detection."""
    return BytesIO(minimal_evtx_header)


@pytest.fixture
def minimal_registry_header() -> bytes:
    """Create minimal Windows Registry hive header for testing can_parse detection.

    Note: This is just the magic header, not a valid complete registry file.
    """
    # Registry hive magic: "regf"
    return b"regf"


@pytest.fixture
def sample_registry_bytes(minimal_registry_header: bytes) -> BytesIO:
    """Create a BytesIO with registry magic header for testing detection."""
    return BytesIO(minimal_registry_header)


@pytest.fixture
def mock_evtx_event() -> dict:
    """Sample parsed EVTX event structure (as would be returned by python-evtx)."""
    return {
        "System": {
            "Provider": {"@Name": "Microsoft-Windows-Security-Auditing"},
            "EventID": 4624,
            "TimeCreated": {"@SystemTime": "2026-01-15T10:30:00.123456Z"},
            "Computer": "WORKSTATION01",
            "Channel": "Security",
        },
        "EventData": {
            "TargetUserName": "admin",
            "TargetDomainName": "CORP",
            "LogonType": "10",
            "IpAddress": "192.168.1.100",
            "ProcessName": "C:\\Windows\\System32\\svchost.exe",
        },
    }


@pytest.fixture
def mock_registry_key() -> dict:
    """Sample parsed registry key structure."""
    return {
        "path": "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
        "timestamp": datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "values": {
            "SecurityHealth": "C:\\Windows\\system32\\SecurityHealthSystray.exe",
            "VMware User Process": "\"C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe\"",
        },
    }


@pytest.fixture
def empty_file(tmp_evidence_dir: Path) -> Path:
    """Create an empty file for edge case testing."""
    empty = tmp_evidence_dir / "empty.json"
    empty.write_text("")
    return empty


@pytest.fixture
def invalid_json_file(tmp_evidence_dir: Path) -> Path:
    """Create an invalid JSON file for error handling testing."""
    invalid = tmp_evidence_dir / "invalid.json"
    invalid.write_text("{not valid json")
    return invalid


@pytest.fixture
def large_json_events(sample_json_events: list[dict]) -> list[dict]:
    """Generate a larger set of events for performance testing."""
    events = []
    base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(100):
        for event in sample_json_events:
            new_event = event.copy()
            new_event["timestamp"] = (
                base_time.replace(minute=i % 60, second=i % 60)
            ).isoformat()
            new_event["sequence"] = i
            events.append(new_event)
    return events


# Helper functions for test assertions


def assert_valid_parsed_event(event):
    """Assert that a ParsedEvent has required fields."""
    assert event.timestamp is not None
    assert isinstance(event.timestamp, datetime)
    assert event.source_type != ""


def assert_event_has_ecs_fields(event, expected_fields: list[str]):
    """Assert that a ParsedEvent has expected ECS fields populated."""
    for field in expected_fields:
        value = getattr(event, field, None)
        assert value is not None, f"Expected field '{field}' to be set"


def create_test_json_file(path: Path, events: list[dict]) -> Path:
    """Helper to create a JSON file with given events."""
    path.write_text(json.dumps(events))
    return path


def create_test_jsonl_file(path: Path, events: list[dict]) -> Path:
    """Helper to create a JSONL file with given events."""
    lines = [json.dumps(event) for event in events]
    path.write_text("\n".join(lines))
    return path
