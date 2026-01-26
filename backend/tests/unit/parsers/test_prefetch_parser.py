"""Unit tests for the Windows Prefetch parser.

Tests the WindowsPrefetchParser class for correct parsing behavior,
magic byte detection, and ECS field mapping.
"""

import struct
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestWindowsPrefetchParser:
    """Tests for WindowsPrefetchParser class."""

    @pytest.fixture
    def prefetch_parser(self):
        """Create a Prefetch parser instance."""
        from app.parsers.formats.prefetch import WindowsPrefetchParser

        return WindowsPrefetchParser()

    def test_parser_name(self, prefetch_parser):
        """Test parser name property."""
        assert prefetch_parser.name == "windows_prefetch"

    def test_parser_category(self, prefetch_parser):
        """Test parser category is ARTIFACTS."""
        from app.parsers.base import ParserCategory

        assert prefetch_parser.category == ParserCategory.ARTIFACTS

    def test_parser_description(self, prefetch_parser):
        """Test parser has a description."""
        assert "prefetch" in prefetch_parser.description.lower()

    def test_supported_extensions(self, prefetch_parser):
        """Test parser supports .pf extension."""
        assert ".pf" in prefetch_parser.supported_extensions

    def test_supported_mime_types(self, prefetch_parser):
        """Test parser supports prefetch mime type."""
        assert "application/x-ms-prefetch" in prefetch_parser.supported_mime_types


class TestPrefetchCanParse:
    """Tests for can_parse detection."""

    @pytest.fixture
    def prefetch_parser(self):
        """Create a Prefetch parser instance."""
        from app.parsers.formats.prefetch import WindowsPrefetchParser

        return WindowsPrefetchParser()

    @pytest.fixture
    def prefetch_magic_v23(self):
        """Windows Vista/7 prefetch magic bytes."""
        return b"\x17\x00\x00\x00SCCA"

    @pytest.fixture
    def prefetch_magic_v26(self):
        """Windows 8 prefetch magic bytes."""
        return b"\x1a\x00\x00\x00SCCA"

    @pytest.fixture
    def prefetch_magic_v30(self):
        """Windows 10 prefetch magic bytes."""
        return b"\x1e\x00\x00\x00SCCA"

    @pytest.fixture
    def mam_magic(self):
        """Windows 10 compressed prefetch magic."""
        return b"MAM\x04"

    def test_can_parse_by_v23_magic(self, prefetch_parser, prefetch_magic_v23):
        """Test detection by Vista/7 prefetch magic bytes."""
        assert prefetch_parser.can_parse(content=prefetch_magic_v23) is True

    def test_can_parse_by_v26_magic(self, prefetch_parser, prefetch_magic_v26):
        """Test detection by Windows 8 prefetch magic bytes."""
        assert prefetch_parser.can_parse(content=prefetch_magic_v26) is True

    def test_can_parse_by_v30_magic(self, prefetch_parser, prefetch_magic_v30):
        """Test detection by Windows 10 prefetch magic bytes."""
        assert prefetch_parser.can_parse(content=prefetch_magic_v30) is True

    def test_can_parse_by_mam_magic(self, prefetch_parser, mam_magic):
        """Test detection by compressed prefetch magic bytes."""
        assert prefetch_parser.can_parse(content=mam_magic) is True

    def test_can_parse_invalid_magic_bytes(self, prefetch_parser):
        """Test rejection of non-prefetch content."""
        invalid_content = b"NOT_PREFETCH_FILE_CONTENT"
        assert prefetch_parser.can_parse(content=invalid_content) is False

    def test_can_parse_by_extension(self, prefetch_parser, tmp_path):
        """Test detection by .pf file extension."""
        pf_file = tmp_path / "CMD.EXE-12345678.pf"
        pf_file.write_bytes(b"")  # Empty file, extension-based check
        assert prefetch_parser.can_parse(file_path=pf_file) is True

    def test_cannot_parse_wrong_extension(self, prefetch_parser, tmp_path):
        """Test rejection of non-.pf extension without magic bytes."""
        wrong_file = tmp_path / "test.txt"
        wrong_file.write_bytes(b"just text content")
        assert prefetch_parser.can_parse(file_path=wrong_file) is False

    def test_can_parse_short_content(self, prefetch_parser):
        """Test handling of content shorter than magic bytes."""
        short_content = b"SCC"  # Less than 8 bytes
        assert prefetch_parser.can_parse(content=short_content) is False


class TestPrefetchEventFields:
    """Tests for ParsedEvent field mapping."""

    @pytest.fixture
    def prefetch_parser(self):
        """Create a Prefetch parser instance."""
        from app.parsers.formats.prefetch import WindowsPrefetchParser

        return WindowsPrefetchParser()

    @pytest.fixture
    def mock_prefetch_record(self):
        """Create a mock prefetch record."""
        record = MagicMock()
        record.executable_name = "CMD.EXE"
        record.run_count = 5
        record.last_run_times = [datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)]
        record.prefetch_hash = 0x12345678
        record.filenames = ["\\WINDOWS\\SYSTEM32\\CMD.EXE", "\\WINDOWS\\SYSTEM32\\KERNEL32.DLL"]
        record.volumes = []
        return record

    def test_parse_record_timestamp(self, prefetch_parser, mock_prefetch_record):
        """Test timestamp extraction from last run time."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert event.timestamp.year == 2026
        assert event.timestamp.month == 1
        assert event.timestamp.day == 15

    def test_parse_record_process_fields(self, prefetch_parser, mock_prefetch_record):
        """Test process fields are correctly populated."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert event.process_name == "CMD.EXE"
        assert event.process_executable == "CMD.EXE"

    def test_parse_record_event_category(self, prefetch_parser, mock_prefetch_record):
        """Test event category is process."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert "process" in event.event_category
        assert event.event_action == "process_executed"

    def test_parse_record_raw_data(self, prefetch_parser, mock_prefetch_record):
        """Test raw data includes run count and other metadata."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert event.raw["executable_name"] == "CMD.EXE"
        assert event.raw["run_count"] == 5
        assert "last_run_times" in event.raw
        assert "prefetch_hash" in event.raw

    def test_parse_record_labels(self, prefetch_parser, mock_prefetch_record):
        """Test labels contain run count and execution evidence."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert event.labels["run_count"] == "5"
        assert event.labels["execution_evidence"] == "prefetch"

    def test_parse_record_tags(self, prefetch_parser, mock_prefetch_record):
        """Test tags include execution_evidence."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert "execution_evidence" in event.tags
        assert "windows_prefetch" in event.tags

    def test_parse_record_message(self, prefetch_parser, mock_prefetch_record):
        """Test message format."""
        event = prefetch_parser._parse_record(mock_prefetch_record, "CMD.EXE-12345678.pf")

        assert event is not None
        assert "CMD.EXE" in event.message
        assert "run count: 5" in event.message


class TestPrefetchEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def prefetch_parser(self):
        """Create a Prefetch parser instance."""
        from app.parsers.formats.prefetch import WindowsPrefetchParser

        return WindowsPrefetchParser()

    def test_missing_last_run_time(self, prefetch_parser):
        """Test handling of record without last run time."""
        record = MagicMock()
        record.executable_name = "TEST.EXE"
        record.run_count = 0
        record.last_run_times = []
        record.filenames = []
        record.volumes = []
        record.prefetch_hash = 0x0

        event = prefetch_parser._parse_record(record, "test.pf")

        assert event is not None
        # Should use current time as fallback
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_long_executable_path(self, prefetch_parser):
        """Test handling of long executable path."""
        record = MagicMock()
        record.executable_name = "\\DEVICE\\HARDDISKVOLUME1\\PROGRAM FILES\\COMPANY\\APPLICATION\\VERY\\DEEPLY\\NESTED\\PATH\\LONGFILENAME.EXE"
        record.run_count = 1
        record.last_run_times = [datetime.now(timezone.utc)]
        record.filenames = []
        record.volumes = []
        record.prefetch_hash = 0x0

        event = prefetch_parser._parse_record(record, "test.pf")

        assert event is not None
        assert "LONGFILENAME.EXE" in event.process_name or "EXE" in event.process_name

    def test_many_file_references(self, prefetch_parser):
        """Test handling of prefetch with many file references."""
        record = MagicMock()
        record.executable_name = "TEST.EXE"
        record.run_count = 10
        record.last_run_times = [datetime.now(timezone.utc)]
        # Simulate prefetch with 100+ file references
        record.filenames = [f"\\FILE{i}.DLL" for i in range(100)]
        record.volumes = []
        record.prefetch_hash = 0x12345678

        event = prefetch_parser._parse_record(record, "test.pf")

        assert event is not None
        # Should limit file references in raw data
        assert event.raw["file_reference_count"] == 100
        # Raw data should have truncated list
        if "file_references" in event.raw:
            assert len(event.raw["file_references"]) <= 50


class TestPrefetchToDictConversion:
    """Tests for ParsedEvent.to_dict() output."""

    @pytest.fixture
    def prefetch_parser(self):
        """Create a Prefetch parser instance."""
        from app.parsers.formats.prefetch import WindowsPrefetchParser

        return WindowsPrefetchParser()

    def test_to_dict_ecs_structure(self, prefetch_parser):
        """Test that to_dict produces valid ECS structure."""
        record = MagicMock()
        record.executable_name = "POWERSHELL.EXE"
        record.run_count = 25
        record.last_run_times = [datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)]
        record.filenames = ["\\WINDOWS\\SYSTEM32\\POWERSHELL.EXE"]
        record.volumes = []
        record.prefetch_hash = 0xABCDEF

        event = prefetch_parser._parse_record(record, "POWERSHELL.EXE-ABCDEF.pf")
        result = event.to_dict()

        # Check ECS structure
        assert "@timestamp" in result
        assert "event" in result
        assert "kind" in result["event"]
        assert "category" in result["event"]
        assert "action" in result["event"]
        assert "process" in result
        assert "name" in result["process"]
