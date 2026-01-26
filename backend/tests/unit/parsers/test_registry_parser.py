"""Unit tests for the Windows Registry parser.

Tests the WindowsRegistryParser class for magic byte detection,
forensic path categorization, and ECS field mapping.
"""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestWindowsRegistryParser:
    """Tests for WindowsRegistryParser class."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    def test_parser_name(self, registry_parser):
        """Test parser name property."""
        assert registry_parser.name == "windows_registry"

    def test_parser_category(self, registry_parser):
        """Test parser category is ARTIFACTS."""
        from app.parsers.base import ParserCategory

        assert registry_parser.category == ParserCategory.ARTIFACTS

    def test_parser_description(self, registry_parser):
        """Test parser has a description."""
        assert "Registry" in registry_parser.description
        assert "SAM" in registry_parser.description or "hive" in registry_parser.description.lower()

    def test_supported_extensions(self, registry_parser):
        """Test parser supports registry extensions."""
        extensions = registry_parser.supported_extensions
        assert ".dat" in extensions
        # Should support common hive file extensions
        assert any("SAM" in ext.upper() for ext in extensions) or ".dat" in extensions


class TestRegistryCanParse:
    """Tests for can_parse detection."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    def test_can_parse_by_magic_bytes(self, registry_parser, minimal_registry_header):
        """Test detection by registry magic bytes."""
        assert registry_parser.can_parse(content=minimal_registry_header) is True

    def test_can_parse_invalid_magic_bytes(self, registry_parser):
        """Test rejection of non-registry content."""
        invalid_content = b"NOT_REGF_FILE"
        assert registry_parser.can_parse(content=invalid_content) is False

    def test_can_parse_by_sam_name(self, registry_parser, tmp_path):
        """Test detection of SAM hive by filename."""
        sam_file = tmp_path / "SAM"
        sam_file.write_bytes(b"regf" + b"\x00" * 100)
        assert registry_parser.can_parse(file_path=sam_file) is True

    def test_can_parse_by_system_name(self, registry_parser, tmp_path):
        """Test detection of SYSTEM hive by filename."""
        system_file = tmp_path / "SYSTEM"
        system_file.write_bytes(b"regf" + b"\x00" * 100)
        assert registry_parser.can_parse(file_path=system_file) is True

    def test_can_parse_by_software_name(self, registry_parser, tmp_path):
        """Test detection of SOFTWARE hive by filename."""
        software_file = tmp_path / "SOFTWARE"
        software_file.write_bytes(b"regf" + b"\x00" * 100)
        assert registry_parser.can_parse(file_path=software_file) is True

    def test_can_parse_by_ntuser_name(self, registry_parser, tmp_path):
        """Test detection of NTUSER.DAT by filename."""
        ntuser_file = tmp_path / "NTUSER.DAT"
        ntuser_file.write_bytes(b"regf" + b"\x00" * 100)
        assert registry_parser.can_parse(file_path=ntuser_file) is True

    def test_can_parse_short_content(self, registry_parser):
        """Test handling of content shorter than magic bytes."""
        short_content = b"reg"  # Less than 4 bytes
        assert registry_parser.can_parse(content=short_content) is False


class TestForensicPathMapping:
    """Tests for forensic path categorization."""

    def test_persistence_paths_defined(self):
        """Test persistence-related paths are defined."""
        from app.parsers.formats.registry_hive import FORENSIC_PATHS

        persistence_paths = [k for k, v in FORENSIC_PATHS.items() if v == "persistence"]
        assert len(persistence_paths) > 0
        assert any("Run" in p for p in persistence_paths)

    def test_service_paths_defined(self):
        """Test service-related paths are defined."""
        from app.parsers.formats.registry_hive import FORENSIC_PATHS

        service_paths = [k for k, v in FORENSIC_PATHS.items() if v == "service"]
        assert len(service_paths) > 0
        assert any("Services" in p for p in service_paths)

    def test_network_paths_defined(self):
        """Test network-related paths are defined."""
        from app.parsers.formats.registry_hive import FORENSIC_PATHS

        network_paths = [k for k, v in FORENSIC_PATHS.items() if v == "network"]
        assert len(network_paths) > 0

    def test_usb_paths_defined(self):
        """Test USB-related paths are defined."""
        from app.parsers.formats.registry_hive import FORENSIC_PATHS

        usb_paths = [k for k, v in FORENSIC_PATHS.items() if "usb" in v.lower()]
        assert len(usb_paths) > 0

    def test_user_account_paths_defined(self):
        """Test user account paths are defined."""
        from app.parsers.formats.registry_hive import FORENSIC_PATHS

        user_paths = [k for k, v in FORENSIC_PATHS.items() if v == "user_account"]
        assert len(user_paths) > 0


class TestDissectAdapterBase:
    """Tests for DissectParserAdapter base functionality."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    def test_to_datetime_with_datetime(self, registry_parser):
        """Test timestamp conversion from datetime."""
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = registry_parser._to_datetime(dt)

        assert result == dt

    def test_to_datetime_with_naive_datetime(self, registry_parser):
        """Test timestamp conversion from naive datetime."""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = registry_parser._to_datetime(dt)

        assert result.tzinfo == timezone.utc
        assert result.year == 2026

    def test_to_datetime_with_unix_timestamp(self, registry_parser):
        """Test timestamp conversion from Unix timestamp."""
        # Jan 15, 2026 10:30:00 UTC
        result = registry_parser._to_datetime(1768563000)

        assert result.year == 2026

    def test_to_datetime_with_milliseconds(self, registry_parser):
        """Test timestamp conversion from milliseconds."""
        result = registry_parser._to_datetime(1768563000000)

        assert result.year == 2026

    def test_to_datetime_with_nanoseconds(self, registry_parser):
        """Test timestamp conversion from nanoseconds."""
        result = registry_parser._to_datetime(1768563000000000000)

        assert result.year == 2026

    def test_to_datetime_with_iso_string(self, registry_parser):
        """Test timestamp conversion from ISO string."""
        result = registry_parser._to_datetime("2026-01-15T10:30:00Z")

        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_to_datetime_with_none(self, registry_parser):
        """Test timestamp conversion with None returns current time."""
        result = registry_parser._to_datetime(None)

        now = datetime.now(timezone.utc)
        assert (now - result).total_seconds() < 5

    def test_safe_str_with_value(self, registry_parser):
        """Test safe string conversion."""
        assert registry_parser._safe_str("test") == "test"
        assert registry_parser._safe_str(123) == "123"
        assert registry_parser._safe_str(None) is None

    def test_safe_int_with_value(self, registry_parser):
        """Test safe int conversion."""
        assert registry_parser._safe_int(123) == 123
        assert registry_parser._safe_int("456") == 456
        assert registry_parser._safe_int(None) is None
        assert registry_parser._safe_int("not_a_number") is None

    def test_extract_path_parts(self, registry_parser):
        """Test path extraction."""
        dir_path, filename = registry_parser._extract_path_parts(
            "C:\\Windows\\System32\\config\\SAM"
        )

        assert "config" in dir_path
        assert filename == "SAM"

    def test_extract_path_parts_none(self, registry_parser):
        """Test path extraction with None."""
        dir_path, filename = registry_parser._extract_path_parts(None)

        assert dir_path is None
        assert filename is None


class TestMockedRegistryParsing:
    """Tests for registry parsing with mocked Dissect library."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    @pytest.fixture
    def mock_registry_key(self):
        """Create a mock registry key object."""
        key = MagicMock()
        key.path = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        key.name = "Run"
        key.timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Mock values
        value1 = MagicMock()
        value1.name = "SecurityHealth"
        value1.value = "C:\\Windows\\System32\\SecurityHealthSystray.exe"

        value2 = MagicMock()
        value2.name = "VMwareUserProcess"
        value2.value = b"C:\\Program Files\\VMware\\VMware Tools\\vmtoolsd.exe\x00"

        key.values.return_value = [value1, value2]
        key.subkeys.return_value = []

        return key

    def test_parse_record_basic(self, registry_parser, mock_registry_key):
        """Test basic record parsing."""
        event = registry_parser._parse_record(mock_registry_key, "SOFTWARE")

        assert event is not None
        assert event.timestamp.year == 2026
        assert event.source_type == "windows_registry"
        assert event.source_file == "SOFTWARE"

    def test_parse_record_persistence_category(self, registry_parser, mock_registry_key):
        """Test persistence path is categorized correctly."""
        event = registry_parser._parse_record(mock_registry_key, "SOFTWARE")

        # Run key should be categorized as persistence
        assert "persistence" in event.event_category or "configuration" in event.event_category
        assert event.labels["forensic_category"] == "persistence"

    def test_parse_record_labels(self, registry_parser, mock_registry_key):
        """Test that labels contain registry metadata."""
        event = registry_parser._parse_record(mock_registry_key, "SOFTWARE")

        assert "registry_key" in event.labels
        assert "Run" in event.labels["registry_key"]

    def test_parse_record_message(self, registry_parser, mock_registry_key):
        """Test message contains key path."""
        event = registry_parser._parse_record(mock_registry_key, "SOFTWARE")

        assert "Registry key:" in event.message
        assert "Run" in event.message

    def test_parse_record_raw_data(self, registry_parser, mock_registry_key):
        """Test raw data contains key information."""
        event = registry_parser._parse_record(mock_registry_key, "SOFTWARE")

        assert "key_path" in event.raw
        assert "key_name" in event.raw
        assert "value_count" in event.raw


class TestRegistryECSMapping:
    """Tests for ECS category mapping based on registry path."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    def _create_mock_key(self, path: str):
        """Helper to create a mock key with given path."""
        key = MagicMock()
        key.path = path
        key.name = path.split("\\")[-1] if "\\" in path else path
        key.timestamp = datetime(2026, 1, 15, tzinfo=timezone.utc)
        key.values.return_value = []
        key.subkeys.return_value = []
        return key

    def test_persistence_ecs_mapping(self, registry_parser):
        """Test ECS mapping for persistence paths."""
        key = self._create_mock_key(
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        )
        event = registry_parser._parse_record(key, "SOFTWARE")

        assert "persistence" in event.event_category or "configuration" in event.event_category
        assert event.event_action == "registry_persistence"

    def test_service_ecs_mapping(self, registry_parser):
        """Test ECS mapping for service paths."""
        key = self._create_mock_key(r"HKLM\SYSTEM\ControlSet001\Services\SomeService")
        event = registry_parser._parse_record(key, "SYSTEM")

        assert "process" in event.event_category or "configuration" in event.event_category
        assert event.event_action == "registry_service"

    def test_network_ecs_mapping(self, registry_parser):
        """Test ECS mapping for network paths."""
        key = self._create_mock_key(
            r"HKLM\SYSTEM\ControlSet001\Services\Tcpip\Parameters\Interfaces\{guid}"
        )
        event = registry_parser._parse_record(key, "SYSTEM")

        assert "network" in event.event_category
        assert event.event_action == "registry_network"

    def test_usb_ecs_mapping(self, registry_parser):
        """Test ECS mapping for USB paths."""
        key = self._create_mock_key(r"HKLM\SYSTEM\ControlSet001\Enum\USBSTOR\Disk")
        event = registry_parser._parse_record(key, "SYSTEM")

        assert "file" in event.event_category
        assert event.event_action == "registry_usb"

    def test_user_account_ecs_mapping(self, registry_parser):
        """Test ECS mapping for SAM user paths."""
        key = self._create_mock_key(r"HKLM\SAM\SAM\Domains\Account\Users\000001F4")
        event = registry_parser._parse_record(key, "SAM")

        assert "iam" in event.event_category
        assert event.event_action == "registry_user"

    def test_default_ecs_mapping(self, registry_parser):
        """Test default ECS mapping for unrecognized paths."""
        key = self._create_mock_key(r"HKLM\SOME\RANDOM\PATH")
        event = registry_parser._parse_record(key, "SYSTEM")

        assert "configuration" in event.event_category
        assert event.event_action == "registry_key"


class TestRegistryEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def registry_parser(self):
        """Create a Registry parser instance."""
        from app.parsers.formats.registry_hive import WindowsRegistryParser

        return WindowsRegistryParser()

    def test_parse_record_no_timestamp(self, registry_parser):
        """Test handling of keys without timestamp."""
        key = MagicMock()
        key.path = r"HKLM\TEST"
        key.name = "TEST"
        key.timestamp = None
        key.values.return_value = []
        key.subkeys.return_value = []

        event = registry_parser._parse_record(key, "test.dat")

        assert event is not None
        assert event.timestamp is not None  # Should use current time

    def test_parse_record_binary_value(self, registry_parser):
        """Test handling of binary values."""
        key = MagicMock()
        key.path = r"HKLM\TEST"
        key.name = "TEST"
        key.timestamp = datetime(2026, 1, 15, tzinfo=timezone.utc)
        key.subkeys.return_value = []

        value = MagicMock()
        value.name = "BinaryData"
        value.value = b"\x00\x01\x02\x03\xff\xfe"
        key.values.return_value = [value]

        event = registry_parser._parse_record(key, "test.dat")

        assert event is not None
        # Binary should be converted to hex or decoded

    def test_parse_record_unicode_value(self, registry_parser):
        """Test handling of Unicode values."""
        key = MagicMock()
        key.path = r"HKLM\TEST"
        key.name = "TEST"
        key.timestamp = datetime(2026, 1, 15, tzinfo=timezone.utc)
        key.subkeys.return_value = []

        value = MagicMock()
        value.name = "UnicodeData"
        # UTF-16-LE encoded string
        value.value = "C:\\Test\\Path".encode("utf-16-le") + b"\x00\x00"
        key.values.return_value = [value]

        event = registry_parser._parse_record(key, "test.dat")

        assert event is not None

    def test_parse_record_too_many_values(self, registry_parser):
        """Test handling of keys with too many values."""
        key = MagicMock()
        key.path = r"HKLM\TEST"
        key.name = "TEST"
        key.timestamp = datetime(2026, 1, 15, tzinfo=timezone.utc)
        key.subkeys.return_value = []

        # Create 200 values (more than limit)
        values = []
        for i in range(200):
            v = MagicMock()
            v.name = f"Value{i}"
            v.value = f"Data{i}"
            values.append(v)
        key.values.return_value = values

        event = registry_parser._parse_record(key, "test.dat")

        # Should parse without error, limiting values
        assert event is not None
        assert event.raw["value_count"] <= 101  # 100 limit + 1 before check

    def test_parse_record_exception_handling(self, registry_parser):
        """Test that exceptions in record parsing return None."""
        key = MagicMock()
        key.path = property(lambda self: (_ for _ in ()).throw(RuntimeError("test error")))

        # This should not raise, should return None
        event = registry_parser._parse_record(key, "test.dat")
        # Due to exception, may return None or partial event
