"""Unit tests for the Generic JSON parser.

Tests the GenericJSONParser class for JSON/JSONL parsing, timestamp extraction,
log type detection, and ECS field mapping for various cloud log formats.
"""

import json
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestGenericJSONParser:
    """Tests for GenericJSONParser class."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_parser_name(self, json_parser):
        """Test parser name property."""
        assert json_parser.name == "json"

    def test_parser_category(self, json_parser):
        """Test parser category is LOGS."""
        from app.parsers.base import ParserCategory

        assert json_parser.category == ParserCategory.LOGS

    def test_parser_description(self, json_parser):
        """Test parser has a description."""
        assert "JSON" in json_parser.description

    def test_supported_extensions(self, json_parser):
        """Test parser supports JSON extensions."""
        assert ".json" in json_parser.supported_extensions
        assert ".jsonl" in json_parser.supported_extensions
        assert ".ndjson" in json_parser.supported_extensions

    def test_supported_mime_types(self, json_parser):
        """Test parser supports JSON mime types."""
        assert "application/json" in json_parser.supported_mime_types
        assert "application/x-ndjson" in json_parser.supported_mime_types


class TestJSONCanParse:
    """Tests for can_parse detection."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_can_parse_json_array_content(self, json_parser):
        """Test detection of JSON array content."""
        content = b'[{"key": "value"}]'
        assert json_parser.can_parse(content=content) is True

    def test_can_parse_json_object_content(self, json_parser):
        """Test detection of JSON object content."""
        content = b'{"key": "value"}'
        assert json_parser.can_parse(content=content) is True

    def test_can_parse_by_extension(self, json_parser, tmp_path):
        """Test detection by .json extension."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")
        assert json_parser.can_parse(file_path=json_file) is True

    def test_can_parse_jsonl_extension(self, json_parser, tmp_path):
        """Test detection by .jsonl extension."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text("{}")
        assert json_parser.can_parse(file_path=jsonl_file) is True

    def test_can_parse_ndjson_extension(self, json_parser, tmp_path):
        """Test detection by .ndjson extension."""
        ndjson_file = tmp_path / "test.ndjson"
        ndjson_file.write_text("{}")
        assert json_parser.can_parse(file_path=ndjson_file) is True

    def test_cannot_parse_invalid_content(self, json_parser):
        """Test rejection of non-JSON content."""
        content = b"This is plain text, not JSON"
        assert json_parser.can_parse(content=content) is False

    def test_cannot_parse_wrong_extension(self, json_parser, tmp_path):
        """Test rejection of non-JSON extension."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("plain text")
        assert json_parser.can_parse(file_path=txt_file) is False


class TestJSONArrayParsing:
    """Tests for parsing JSON array files."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_parse_json_array(self, json_parser, sample_json_file, sample_json_events):
        """Test parsing of JSON array file."""
        events = list(json_parser.parse(sample_json_file))

        assert len(events) == len(sample_json_events)
        for event in events:
            assert event.timestamp is not None
            assert event.source_type == "json"

    def test_parse_json_array_timestamps(self, json_parser, sample_json_file):
        """Test timestamp extraction from JSON array."""
        events = list(json_parser.parse(sample_json_file))

        assert events[0].timestamp.year == 2026
        assert events[0].timestamp.month == 1
        assert events[0].timestamp.day == 15

    def test_parse_json_array_source_tracking(
        self, json_parser, sample_json_file, sample_json_events
    ):
        """Test source file and line tracking."""
        events = list(json_parser.parse(sample_json_file))

        for i, event in enumerate(events):
            assert event.source_file == str(sample_json_file)
            assert event.source_line == i + 1


class TestJSONLParsing:
    """Tests for parsing JSONL (newline-delimited) files."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_parse_jsonl_file(self, json_parser, sample_jsonl_file, sample_json_events):
        """Test parsing of JSONL file."""
        events = list(json_parser.parse(sample_jsonl_file))

        assert len(events) == len(sample_json_events)

    def test_parse_jsonl_line_numbers(self, json_parser, sample_jsonl_file):
        """Test line number tracking in JSONL."""
        events = list(json_parser.parse(sample_jsonl_file))

        for i, event in enumerate(events):
            assert event.source_line == i + 1

    def test_parse_jsonl_skips_empty_lines(self, json_parser, tmp_evidence_dir):
        """Test that empty lines are skipped."""
        jsonl_file = tmp_evidence_dir / "with_blanks.jsonl"
        content = '{"a": 1}\n\n{"b": 2}\n\n\n{"c": 3}'
        jsonl_file.write_text(content)

        events = list(json_parser.parse(jsonl_file))
        assert len(events) == 3

    def test_parse_jsonl_skips_comments(self, json_parser, tmp_evidence_dir):
        """Test that comment lines are skipped."""
        jsonl_file = tmp_evidence_dir / "with_comments.jsonl"
        content = '{"a": 1}\n# This is a comment\n{"b": 2}'
        jsonl_file.write_text(content)

        events = list(json_parser.parse(jsonl_file))
        assert len(events) == 2


class TestCloudTrailParsing:
    """Tests for AWS CloudTrail log parsing."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_detect_cloudtrail_log_type(self, json_parser, sample_cloudtrail_events):
        """Test CloudTrail log type detection."""
        record = sample_cloudtrail_events[0]
        log_type = json_parser._detect_log_type(record)
        assert log_type == "aws_cloudtrail"

    def test_parse_cloudtrail_file(self, json_parser, sample_cloudtrail_file):
        """Test parsing of CloudTrail file."""
        events = list(json_parser.parse(sample_cloudtrail_file))

        assert len(events) >= 1
        event = events[0]
        assert event.source_type == "aws_cloudtrail"

    def test_cloudtrail_user_extraction(self, json_parser, sample_cloudtrail_file):
        """Test user extraction from CloudTrail."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        event = events[0]

        assert event.user_name == "admin"

    def test_cloudtrail_ip_extraction(self, json_parser, sample_cloudtrail_file):
        """Test IP extraction from CloudTrail."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        event = events[0]

        assert event.source_ip == "203.0.113.50"

    def test_cloudtrail_event_action(self, json_parser, sample_cloudtrail_file):
        """Test event action from CloudTrail."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        event = events[0]

        assert event.event_action == "ConsoleLogin"

    def test_cloudtrail_labels(self, json_parser, sample_cloudtrail_file):
        """Test CloudTrail labels are set."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        event = events[0]

        assert event.labels["aws_region"] == "us-east-1"
        assert "signin.amazonaws.com" in event.labels["event_source"]


class TestTimestampExtraction:
    """Tests for timestamp parsing from various formats."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_iso_timestamp_with_z(self, json_parser):
        """Test ISO timestamp with Z suffix."""
        record = {"timestamp": "2026-01-15T10:30:00Z"}
        ts = json_parser._extract_timestamp(record)

        assert ts.year == 2026
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 10
        assert ts.minute == 30

    def test_iso_timestamp_with_timezone(self, json_parser):
        """Test ISO timestamp with explicit timezone."""
        record = {"timestamp": "2026-01-15T10:30:00+00:00"}
        ts = json_parser._extract_timestamp(record)

        assert ts.year == 2026

    def test_iso_timestamp_with_microseconds(self, json_parser):
        """Test ISO timestamp with microseconds."""
        record = {"timestamp": "2026-01-15T10:30:00.123456Z"}
        ts = json_parser._extract_timestamp(record)

        assert ts.microsecond == 123456

    def test_unix_timestamp_seconds(self, json_parser):
        """Test Unix timestamp in seconds."""
        # Jan 15, 2026 10:30:00 UTC
        record = {"timestamp": 1768563000}
        ts = json_parser._extract_timestamp(record)

        assert ts.year == 2026

    def test_unix_timestamp_milliseconds(self, json_parser):
        """Test Unix timestamp in milliseconds."""
        # Same time but in milliseconds
        record = {"timestamp": 1768563000000}
        ts = json_parser._extract_timestamp(record)

        assert ts.year == 2026

    def test_alternative_timestamp_fields(self, json_parser):
        """Test various timestamp field names."""
        fields = ["time", "datetime", "eventTime", "createdDateTime", "_time"]

        for field in fields:
            record = {field: "2026-01-15T10:30:00Z"}
            ts = json_parser._extract_timestamp(record)
            assert ts.year == 2026, f"Failed for field: {field}"

    def test_missing_timestamp_uses_now(self, json_parser):
        """Test fallback to current time when no timestamp found."""
        record = {"no_timestamp_field": "value"}
        ts = json_parser._extract_timestamp(record)

        # Should be close to now
        now = datetime.now(timezone.utc)
        assert (now - ts).total_seconds() < 5


class TestLogTypeDetection:
    """Tests for automatic log type detection."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_detect_azure_signin(self, json_parser):
        """Test Azure Sign-in log detection."""
        record = {
            "createdDateTime": "2026-01-15T10:30:00Z",
            "userPrincipalName": "user@example.com",
            "conditionalAccessStatus": "success",
            "ipAddress": "1.2.3.4",
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type == "azure_signin"

    def test_detect_azure_audit(self, json_parser):
        """Test Azure Audit log detection."""
        record = {
            "activityDateTime": "2026-01-15T10:30:00Z",
            "operationType": "Add",
            "targetResources": [],
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type == "azure_audit"

    def test_detect_gcp_audit(self, json_parser):
        """Test GCP Audit log detection."""
        record = {
            "protoPayload": {},
            "resource": {},
            "severity": "INFO",
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type == "gcp_audit"

    def test_detect_okta(self, json_parser):
        """Test Okta log detection."""
        record = {
            "actor": {"id": "user123"},
            "outcome": {"result": "SUCCESS"},
            "eventType": "user.session.start",
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type == "okta"

    def test_detect_o365_audit(self, json_parser):
        """Test Office 365 audit log detection."""
        record = {
            "Workload": "Exchange",
            "Operation": "MailItemsAccessed",
            "UserId": "user@example.com",
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type == "o365_audit"

    def test_unknown_log_type(self, json_parser):
        """Test unknown log type returns None."""
        record = {
            "random_field": "value",
            "another_field": 123,
        }
        log_type = json_parser._detect_log_type(record)
        assert log_type is None


class TestGenericFieldMapping:
    """Tests for generic field extraction."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_generic_user_extraction_string(self, json_parser, tmp_evidence_dir):
        """Test generic user extraction from string field."""
        json_file = tmp_evidence_dir / "test.json"
        record = {"timestamp": "2026-01-15T10:30:00Z", "user": "admin"}
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].user_name == "admin"

    def test_generic_user_extraction_dict(self, json_parser, tmp_evidence_dir):
        """Test generic user extraction from dict field."""
        json_file = tmp_evidence_dir / "test.json"
        record = {
            "timestamp": "2026-01-15T10:30:00Z",
            "user": {"name": "admin", "id": "123"},
        }
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].user_name == "admin"
        assert events[0].user_id == "123"

    def test_generic_ip_extraction(self, json_parser, tmp_evidence_dir):
        """Test generic IP address extraction."""
        json_file = tmp_evidence_dir / "test.json"
        record = {"timestamp": "2026-01-15T10:30:00Z", "ip_address": "10.0.0.1"}
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].source_ip == "10.0.0.1"

    def test_generic_action_extraction(self, json_parser, tmp_evidence_dir):
        """Test generic action extraction."""
        json_file = tmp_evidence_dir / "test.json"
        record = {"timestamp": "2026-01-15T10:30:00Z", "action": "login"}
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].event_action == "login"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_empty_file(self, json_parser, empty_file):
        """Test handling of empty file."""
        events = list(json_parser.parse(empty_file))
        assert len(events) == 0

    def test_invalid_json_line_skipped(self, json_parser, tmp_evidence_dir):
        """Test that invalid JSON lines are skipped in JSONL."""
        jsonl_file = tmp_evidence_dir / "partial_invalid.jsonl"
        content = '{"valid": 1}\n{invalid json\n{"valid": 2}'
        jsonl_file.write_text(content)

        events = list(json_parser.parse(jsonl_file))
        # Should parse 2 valid lines, skip 1 invalid
        assert len(events) == 2

    def test_raw_data_preserved(self, json_parser, tmp_evidence_dir):
        """Test that raw record data is preserved."""
        json_file = tmp_evidence_dir / "test.json"
        record = {
            "timestamp": "2026-01-15T10:30:00Z",
            "custom_field": "custom_value",
            "nested": {"key": "value"},
        }
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].raw["custom_field"] == "custom_value"
        assert events[0].raw["nested"]["key"] == "value"

    def test_message_extraction(self, json_parser, tmp_evidence_dir):
        """Test message field extraction."""
        json_file = tmp_evidence_dir / "test.json"
        record = {
            "timestamp": "2026-01-15T10:30:00Z",
            "message": "User login successful",
        }
        json_file.write_text(json.dumps([record]))

        events = list(json_parser.parse(json_file))
        assert events[0].message == "User login successful"

    def test_parse_from_binary_stream(self, json_parser):
        """Test parsing from binary stream."""
        data = b'{"timestamp": "2026-01-15T10:30:00Z", "event": "test"}'
        stream = BytesIO(data)

        events = list(json_parser.parse(stream, "stream_test"))
        assert len(events) == 1
        assert events[0].source_file == "stream_test"


class TestToDictConversion:
    """Tests for ParsedEvent.to_dict() output from JSON parser."""

    @pytest.fixture
    def json_parser(self):
        """Create a JSON parser instance."""
        from app.parsers.formats.json import GenericJSONParser

        return GenericJSONParser()

    def test_to_dict_ecs_structure(self, json_parser, sample_cloudtrail_file):
        """Test that to_dict produces valid ECS structure."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        result = events[0].to_dict()

        assert "@timestamp" in result
        assert "event" in result
        assert "category" in result["event"]
        assert "_source" in result

    def test_to_dict_preserves_raw(self, json_parser, sample_cloudtrail_file):
        """Test that raw data is preserved in to_dict."""
        events = list(json_parser.parse(sample_cloudtrail_file))
        result = events[0].to_dict()

        assert "_raw" in result
        assert "eventName" in result["_raw"]
