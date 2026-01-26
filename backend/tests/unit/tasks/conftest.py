"""Shared fixtures for Celery task tests.

Provides mock Celery configuration, task fixtures, and common utilities
for testing Eleanor's asynchronous task processing.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_celery_app():
    """Create a mock Celery application."""
    app = MagicMock()
    app.control = MagicMock()
    app.control.revoke = MagicMock()
    return app


@pytest.fixture
def mock_task():
    """Create a mock Celery task instance."""
    task = MagicMock()
    task.request = MagicMock()
    task.request.id = str(uuid.uuid4())
    task.request.hostname = "worker@test"
    task.retry = MagicMock(side_effect=Exception("Task retry triggered"))
    task.update_state = MagicMock()
    return task


@pytest.fixture
def sample_job_id() -> str:
    """Generate a sample parsing job UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_evidence_id() -> str:
    """Generate a sample evidence UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_case_id() -> str:
    """Generate a sample case UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_parsing_result() -> dict[str, Any]:
    """Sample parsing result from a successful job."""
    return {
        "job_id": str(uuid.uuid4()),
        "status": "completed",
        "events_parsed": 1500,
        "events_indexed": 1500,
        "errors": 0,
        "duration_seconds": 45.5,
        "parser_used": "windows_evtx",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_batch_result() -> dict[str, Any]:
    """Sample batch parsing result."""
    return {
        "batch_id": str(uuid.uuid4()),
        "job_count": 5,
        "status": "submitted",
    }


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_elasticsearch():
    """Create a mock Elasticsearch client."""
    es = AsyncMock()
    es.index = AsyncMock(return_value={"result": "created"})
    es.bulk = AsyncMock(return_value={"errors": False, "items": []})
    es.indices = MagicMock()
    es.indices.create = AsyncMock()
    es.indices.exists = AsyncMock(return_value=True)
    return es


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.set = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.delete = MagicMock()
    redis.publish = MagicMock()
    return redis


@pytest.fixture
def sample_evidence_file(tmp_path):
    """Create a sample evidence file."""
    evidence_file = tmp_path / "test_evidence.evtx"
    # Write EVTX magic bytes
    evidence_file.write_bytes(b"ElfFile\x00" + b"\x00" * 100)
    return evidence_file


@pytest.fixture
def sample_parsing_job():
    """Create a sample ParsingJob model instance."""
    job = MagicMock()
    job.id = uuid.uuid4()
    job.evidence_id = uuid.uuid4()
    job.case_id = uuid.uuid4()
    job.status = "pending"
    job.parser_name = None
    job.events_parsed = 0
    job.events_indexed = 0
    job.started_at = None
    job.completed_at = None
    job.error_message = None
    return job


@pytest.fixture
def sample_evidence():
    """Create a sample Evidence model instance."""
    evidence = MagicMock()
    evidence.id = uuid.uuid4()
    evidence.case_id = uuid.uuid4()
    evidence.file_name = "test_evidence.evtx"
    evidence.file_path = "/evidence/test_evidence.evtx"
    evidence.file_size = 1024000
    evidence.file_hash_sha256 = "abc123"
    evidence.content_type = "application/x-ms-evtx"
    return evidence


# Helper functions for test assertions


def assert_task_succeeded(result: dict) -> None:
    """Assert that a task result indicates success."""
    assert result.get("status") in ("completed", "success", "submitted")


def assert_task_failed(result: dict) -> None:
    """Assert that a task result indicates failure."""
    assert result.get("status") in ("failed", "error", "cancelled")


def create_mock_parsed_events(count: int = 10) -> list[dict]:
    """Generate mock parsed events for testing."""
    from datetime import datetime, timezone

    events = []
    base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(count):
        events.append({
            "@timestamp": (base_time.replace(minute=i % 60)).isoformat(),
            "event": {
                "kind": "event",
                "category": ["process"],
                "type": ["start"],
                "action": "process_created",
            },
            "host": {"name": "WORKSTATION-01"},
            "user": {"name": f"user{i}"},
            "process": {"name": f"process{i}.exe"},
            "message": f"Test event {i}",
        })

    return events
