"""Unit tests for Celery parsing tasks.

Tests the parse_evidence, batch_parse_evidence, and cancel_parsing_job
tasks for correct registration, configuration, and basic structure.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


class TestParseEvidenceTask:
    """Tests for the parse_evidence Celery task."""

    def test_task_is_registered(self):
        """Test that parse_evidence task is properly registered."""
        from app.tasks.parsing import parse_evidence

        assert parse_evidence.name == "eleanor.parse_evidence"

    def test_task_config(self):
        """Test task configuration attributes."""
        from app.tasks.parsing import parse_evidence

        assert parse_evidence.max_retries == 3
        assert parse_evidence.default_retry_delay == 60

    def test_task_time_limits(self):
        """Test that time limits are configured."""
        from app.tasks.parsing import parse_evidence

        # Soft limit should be less than hard limit
        assert parse_evidence.soft_time_limit < parse_evidence.time_limit


class TestBatchParseEvidenceTask:
    """Tests for the batch_parse_evidence Celery task."""

    def test_task_is_registered(self):
        """Test that batch_parse_evidence task is properly registered."""
        from app.tasks.parsing import batch_parse_evidence

        assert batch_parse_evidence.name == "eleanor.batch_parse_evidence"

    def test_task_config(self):
        """Test batch task configuration."""
        from app.tasks.parsing import batch_parse_evidence

        assert batch_parse_evidence.max_retries == 1

class TestCancelParsingJobTask:
    """Tests for the cancel_parsing_job Celery task."""

    def test_task_is_registered(self):
        """Test that cancel_parsing_job task is properly registered."""
        from app.tasks.parsing import cancel_parsing_job

        assert cancel_parsing_job.name == "eleanor.cancel_parsing_job"

class TestCeleryHealthCheck:
    """Tests for the health check task."""

    def test_health_check_registered(self):
        """Test that health_check task is registered."""
        from app.tasks.celery_app import health_check

        assert health_check.name == "eleanor.health_check"


class TestTaskStateManagement:
    """Tests for task state management."""

    def test_task_result_structure(self, mock_parsing_result):
        """Test that task results have expected structure."""
        assert "job_id" in mock_parsing_result
        assert "status" in mock_parsing_result
        assert "events_parsed" in mock_parsing_result
        assert "events_indexed" in mock_parsing_result

    def test_batch_result_structure(self, mock_batch_result):
        """Test that batch results have expected structure."""
        assert "batch_id" in mock_batch_result
        assert "job_count" in mock_batch_result
        assert "status" in mock_batch_result

    def test_parsing_result_has_metrics(self, mock_parsing_result):
        """Test that parsing result includes performance metrics."""
        assert "duration_seconds" in mock_parsing_result
        assert "parser_used" in mock_parsing_result

    def test_parsing_result_has_timestamp(self, mock_parsing_result):
        """Test that parsing result includes timestamp."""
        assert "timestamp" in mock_parsing_result


class TestTaskSignatures:
    """Tests for task function signatures."""

    def test_parse_evidence_accepts_required_args(self):
        """Test parse_evidence accepts required arguments."""
        from app.tasks.parsing import parse_evidence
        import inspect

        sig = inspect.signature(parse_evidence)
        params = list(sig.parameters.keys())

        assert "job_id" in params
        assert "evidence_id" in params
        assert "case_id" in params

    def test_parse_evidence_accepts_optional_args(self):
        """Test parse_evidence accepts optional arguments."""
        from app.tasks.parsing import parse_evidence
        import inspect

        sig = inspect.signature(parse_evidence)
        params = sig.parameters

        # Optional params should have defaults
        assert params["parser_hint"].default is None
        assert params["config"].default is None

    def test_batch_parse_accepts_job_ids(self):
        """Test batch_parse_evidence accepts job_ids."""
        from app.tasks.parsing import batch_parse_evidence
        import inspect

        sig = inspect.signature(batch_parse_evidence)
        params = list(sig.parameters.keys())

        assert "job_ids" in params

    def test_cancel_job_accepts_job_id(self):
        """Test cancel_parsing_job accepts job_id."""
        from app.tasks.parsing import cancel_parsing_job
        import inspect

        sig = inspect.signature(cancel_parsing_job)
        params = list(sig.parameters.keys())

        assert "job_id" in params
        assert "celery_task_id" in params


class TestCeleryAppConfiguration:
    """Tests for Celery app configuration."""

    def test_celery_app_exists(self):
        """Test that celery_app is properly configured."""
        from app.tasks.celery_app import celery_app

        assert celery_app is not None
        assert celery_app.main == "eleanor"

    def test_celery_has_task_routes(self):
        """Test that task routes are configured."""
        from app.tasks.celery_app import celery_app

        # Check that we have some route configuration
        routes = celery_app.conf.task_routes
        assert routes is not None or celery_app.conf.task_default_queue is not None
