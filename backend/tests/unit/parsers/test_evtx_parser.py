"""Unit tests for the Windows EVTX parser.

Tests the WindowsEvtxParser class for correct parsing behavior,
magic byte detection, and ECS field mapping.
"""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestWindowsEvtxParser:
    """Tests for WindowsEvtxParser class."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    def test_parser_name(self, evtx_parser):
        """Test parser name property."""
        assert evtx_parser.name == "windows_evtx"

    def test_parser_category(self, evtx_parser):
        """Test parser category is LOGS."""
        from app.parsers.base import ParserCategory

        assert evtx_parser.category == ParserCategory.LOGS

    def test_parser_description(self, evtx_parser):
        """Test parser has a description."""
        assert "evtx" in evtx_parser.description.lower()

    def test_supported_extensions(self, evtx_parser):
        """Test parser supports .evtx extension."""
        assert ".evtx" in evtx_parser.supported_extensions

    def test_supported_mime_types(self, evtx_parser):
        """Test parser supports evtx mime type."""
        assert "application/x-ms-evtx" in evtx_parser.supported_mime_types

    def test_can_parse_by_magic_bytes(self, evtx_parser, minimal_evtx_header):
        """Test detection by EVTX magic bytes."""
        assert evtx_parser.can_parse(content=minimal_evtx_header) is True

    def test_can_parse_invalid_magic_bytes(self, evtx_parser):
        """Test rejection of non-EVTX content."""
        invalid_content = b"NOT_EVTX_FILE_CONTENT"
        assert evtx_parser.can_parse(content=invalid_content) is False

    def test_can_parse_by_extension(self, evtx_parser, tmp_path):
        """Test detection by .evtx file extension."""
        evtx_file = tmp_path / "test.evtx"
        evtx_file.write_bytes(b"")  # Empty file, extension-based check
        assert evtx_parser.can_parse(file_path=evtx_file) is True

    def test_cannot_parse_wrong_extension(self, evtx_parser, tmp_path):
        """Test rejection of non-evtx extension without magic bytes."""
        wrong_file = tmp_path / "test.txt"
        wrong_file.write_bytes(b"just text content")
        # With no magic bytes and wrong extension, should fail
        assert evtx_parser.can_parse(file_path=wrong_file) is False

    def test_can_parse_short_content(self, evtx_parser):
        """Test handling of content shorter than magic bytes."""
        short_content = b"Elf"  # Less than 8 bytes
        assert evtx_parser.can_parse(content=short_content) is False


class TestEvtxEventCategoryMapping:
    """Tests for event ID to ECS category mapping."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    def test_authentication_event_mapping(self):
        """Test Event ID 4624 maps to authentication category."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[4624]
        assert "authentication" in categories
        assert action == "user_logon"

    def test_failed_login_event_mapping(self):
        """Test Event ID 4625 maps to authentication with failure."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[4625]
        assert "authentication" in categories
        assert action == "user_logon_failed"

    def test_process_creation_event_mapping(self):
        """Test Event ID 4688 maps to process category."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[4688]
        assert "process" in categories
        assert "start" in types
        assert action == "process_created"

    def test_user_creation_event_mapping(self):
        """Test Event ID 4720 maps to IAM category."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[4720]
        assert "iam" in categories
        assert "user" in types
        assert "creation" in types

    def test_service_install_event_mapping(self):
        """Test Event ID 7045 maps to configuration category."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[7045]
        assert "configuration" in categories
        assert action == "service_installed"

    def test_powershell_event_mapping(self):
        """Test Event ID 4104 maps to process category."""
        from app.parsers.formats.evtx import EVENT_CATEGORY_MAP

        categories, types, action = EVENT_CATEGORY_MAP[4104]
        assert "process" in categories
        assert action == "powershell_script_block"


class TestEvtxMessageBuilding:
    """Tests for human-readable message generation."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    def test_logon_message(self, evtx_parser):
        """Test message for successful logon event."""
        data = {
            "TargetUserName": "admin",
            "TargetDomainName": "CORP",
            "LogonType": "10",
        }
        message = evtx_parser._build_message(4624, "Security", data)
        assert "admin" in message
        assert "CORP" in message
        assert "10" in message

    def test_failed_login_message(self, evtx_parser):
        """Test message for failed login event."""
        data = {
            "TargetUserName": "baduser",
            "TargetDomainName": "CORP",
        }
        message = evtx_parser._build_message(4625, "Security", data)
        assert "Failed" in message
        assert "baduser" in message

    def test_process_created_message(self, evtx_parser):
        """Test message for process creation event."""
        data = {
            "NewProcessName": "C:\\Windows\\System32\\cmd.exe",
            "SubjectUserName": "admin",
        }
        message = evtx_parser._build_message(4688, "Security", data)
        assert "Process created" in message
        assert "cmd.exe" in message

    def test_service_installed_message(self, evtx_parser):
        """Test message for service installation event."""
        data = {
            "ServiceName": "MaliciousService",
        }
        message = evtx_parser._build_message(7045, "System", data)
        assert "Service installed" in message
        assert "MaliciousService" in message

    def test_unknown_event_message(self, evtx_parser):
        """Test message for unmapped event ID."""
        data = {"SomeField": "SomeValue"}
        message = evtx_parser._build_message(9999, "Custom", data)
        assert "9999" in message


class TestEvtxXmlParsing:
    """Tests for XML record parsing with mocked data."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    @pytest.fixture
    def sample_xml_4624(self):
        """Sample XML for Event ID 4624 (successful logon)."""
        return """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Microsoft-Windows-Security-Auditing"/>
        <EventID>4624</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00.123456Z"/>
        <Computer>WORKSTATION01</Computer>
        <Channel>Security</Channel>
    </System>
    <EventData>
        <Data Name="TargetUserName">jsmith</Data>
        <Data Name="TargetDomainName">CORP</Data>
        <Data Name="TargetUserSid">S-1-5-21-123-456-789</Data>
        <Data Name="LogonType">10</Data>
        <Data Name="IpAddress">192.168.1.100</Data>
        <Data Name="ProcessName">C:\\Windows\\System32\\svchost.exe</Data>
    </EventData>
</Event>"""

    @pytest.fixture
    def sample_xml_4688(self):
        """Sample XML for Event ID 4688 (process creation)."""
        return """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Microsoft-Windows-Security-Auditing"/>
        <EventID>4688</EventID>
        <TimeCreated SystemTime="2026-01-15T10:31:00.000000Z"/>
        <Computer>WORKSTATION01</Computer>
        <Channel>Security</Channel>
    </System>
    <EventData>
        <Data Name="SubjectUserName">admin</Data>
        <Data Name="SubjectDomainName">CORP</Data>
        <Data Name="NewProcessName">C:\\Windows\\System32\\cmd.exe</Data>
        <Data Name="NewProcessId">0x1234</Data>
        <Data Name="ParentProcessId">0x5678</Data>
        <Data Name="CommandLine">cmd.exe /c whoami</Data>
    </EventData>
</Event>"""

    def test_parse_4624_event(self, evtx_parser, sample_xml_4624):
        """Test parsing of successful logon event."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(sample_xml_4624)
        event = evtx_parser._parse_record(root, "Security.evtx", 1)

        assert event.timestamp.year == 2026
        assert event.timestamp.month == 1
        assert event.timestamp.day == 15
        assert event.host_name == "WORKSTATION01"
        assert event.user_name == "jsmith"
        assert event.user_domain == "CORP"
        assert event.source_ip == "192.168.1.100"
        assert "authentication" in event.event_category
        assert event.event_action == "user_logon"
        assert event.event_outcome == "success"

    def test_parse_4688_event(self, evtx_parser, sample_xml_4688):
        """Test parsing of process creation event."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(sample_xml_4688)
        event = evtx_parser._parse_record(root, "Security.evtx", 2)

        assert event.host_name == "WORKSTATION01"
        assert event.user_name == "admin"
        assert event.process_name == "cmd.exe"
        assert event.process_executable == "C:\\Windows\\System32\\cmd.exe"
        assert event.process_pid == 0x1234
        assert event.process_ppid == 0x5678
        assert event.process_command_line == "cmd.exe /c whoami"
        assert "process" in event.event_category
        assert event.event_action == "process_created"

    def test_parse_record_labels(self, evtx_parser, sample_xml_4624):
        """Test that labels contain event metadata."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(sample_xml_4624)
        event = evtx_parser._parse_record(root, "Security.evtx", 1)

        assert event.labels["event_id"] == "4624"
        assert event.labels["channel"] == "Security"
        assert "Microsoft-Windows-Security-Auditing" in event.labels["provider"]

    def test_parse_record_raw_data(self, evtx_parser, sample_xml_4624):
        """Test that raw EventData fields are preserved."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(sample_xml_4624)
        event = evtx_parser._parse_record(root, "Security.evtx", 1)

        assert event.raw["TargetUserName"] == "jsmith"
        assert event.raw["LogonType"] == "10"
        assert event.raw["IpAddress"] == "192.168.1.100"


class TestEvtxEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    def test_missing_timestamp(self, evtx_parser):
        """Test handling of events without timestamp."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Test"/>
        <EventID>1234</EventID>
        <Computer>HOST01</Computer>
    </System>
    <EventData/>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)

        # Should use current time as fallback
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)

    def test_missing_event_data(self, evtx_parser):
        """Test handling of events without EventData section."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Test"/>
        <EventID>1234</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00Z"/>
        <Computer>HOST01</Computer>
    </System>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)

        assert event.host_name == "HOST01"
        assert event.raw == {}

    def test_unmapped_event_id(self, evtx_parser):
        """Test handling of unmapped event IDs."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Custom-Provider"/>
        <EventID>99999</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00Z"/>
        <Computer>HOST01</Computer>
    </System>
    <EventData/>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)

        # Should get default categories for unmapped events
        assert "process" in event.event_category
        assert "info" in event.event_type
        assert event.event_action == "event_99999"

    def test_hex_process_ids(self, evtx_parser):
        """Test parsing of hexadecimal process IDs."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Test"/>
        <EventID>4688</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00Z"/>
        <Computer>HOST01</Computer>
    </System>
    <EventData>
        <Data Name="NewProcessId">0xABCD</Data>
        <Data Name="ParentProcessId">0x1234</Data>
    </EventData>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)

        assert event.process_pid == 0xABCD
        assert event.process_ppid == 0x1234

    def test_decimal_process_ids(self, evtx_parser):
        """Test parsing of decimal process IDs."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Test"/>
        <EventID>4688</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00Z"/>
        <Computer>HOST01</Computer>
    </System>
    <EventData>
        <Data Name="NewProcessId">1234</Data>
        <Data Name="ParentProcessId">5678</Data>
    </EventData>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)

        assert event.process_pid == 1234
        assert event.process_ppid == 5678


class TestEvtxToDictConversion:
    """Tests for ParsedEvent.to_dict() output."""

    @pytest.fixture
    def evtx_parser(self):
        """Create an EVTX parser instance."""
        from app.parsers.formats.evtx import WindowsEvtxParser

        return WindowsEvtxParser()

    def test_to_dict_ecs_structure(self, evtx_parser):
        """Test that to_dict produces valid ECS structure."""
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Security"/>
        <EventID>4624</EventID>
        <TimeCreated SystemTime="2026-01-15T10:30:00.000000Z"/>
        <Computer>HOST01</Computer>
        <Channel>Security</Channel>
    </System>
    <EventData>
        <Data Name="TargetUserName">admin</Data>
        <Data Name="TargetDomainName">CORP</Data>
        <Data Name="IpAddress">10.0.0.1</Data>
    </EventData>
</Event>"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml)
        event = evtx_parser._parse_record(root, "test.evtx", 1)
        result = event.to_dict()

        # Check ECS structure
        assert "@timestamp" in result
        assert "event" in result
        assert "kind" in result["event"]
        assert "category" in result["event"]
        assert "host" in result
        assert "name" in result["host"]
        assert "user" in result
        assert "name" in result["user"]
        assert "source" in result
        assert "ip" in result["source"]
