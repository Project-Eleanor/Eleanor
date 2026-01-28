"""CrowdStrike Falcon Data Replicator (FDR) parser.

PATTERN: Strategy Pattern (via BaseParser)
Parses CrowdStrike FDR exports containing endpoint telemetry data
including process executions, network connections, file events, and more.

FDR data is delivered as JSON/JSONL files from S3 or Falcon LogScale.
"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# CrowdStrike event type to ECS category mapping
FDR_EVENT_CATEGORY_MAP = {
    # Process events
    "ProcessRollup2": ["process"],
    "SyntheticProcessRollup2": ["process"],
    "ProcessBlocked": ["process", "intrusion_detection"],
    "ProcessInjection": ["process", "intrusion_detection"],
    # File events
    "DirectoryCreate": ["file"],
    "DirectoryDelete": ["file"],
    "FileWritten": ["file"],
    "FileDeleted": ["file"],
    "FileRename": ["file"],
    "FileOpenInfo": ["file"],
    "RansomwareFileAccess": ["file", "intrusion_detection"],
    # Network events
    "NetworkConnectIP4": ["network"],
    "NetworkConnectIP6": ["network"],
    "NetworkReceiveAcceptIP4": ["network"],
    "NetworkReceiveAcceptIP6": ["network"],
    "DnsRequest": ["network"],
    "HttpRequest": ["network", "web"],
    # Registry events
    "RegKeyValueSet": ["registry"],
    "RegKeyCreated": ["registry"],
    "RegKeyDeleted": ["registry"],
    "RegValueDeleted": ["registry"],
    # Authentication events
    "UserLogon": ["authentication"],
    "UserLogonFailed": ["authentication"],
    "UserLogoff": ["authentication"],
    # Script events
    "ScriptControlScan": ["process"],
    "AmsiScriptContent": ["process"],
    # Module/DLL events
    "ModuleLoad": ["process"],
    "ImageLoad": ["process"],
    # Detection events
    "DetectionSummaryEvent": ["intrusion_detection"],
    "IncidentSummaryEvent": ["intrusion_detection"],
    "IdpDetectionSummaryEvent": ["intrusion_detection"],
    # Other
    "ScheduledTaskRegistered": ["process", "configuration"],
    "ScheduledTaskModified": ["process", "configuration"],
    "ScheduledTaskDeleted": ["configuration"],
    "ServiceStarted": ["process"],
    "ServiceStopped": ["process"],
    "DriverLoad": ["driver"],
    "AsepValueUpdate": ["configuration"],
    "CriticalFileAccess": ["file"],
}


@register_parser
class CrowdStrikeFDRParser(BaseParser):
    """Parser for CrowdStrike Falcon Data Replicator exports.

    PATTERN: Strategy Pattern
    Parses FDR JSON/JSONL files and normalizes to ECS format.

    Supports:
    - Process execution events (ProcessRollup2)
    - Network connection events
    - File system events
    - Registry modification events
    - Authentication events
    - Detection/alert events
    """

    @property
    def name(self) -> str:
        return "crowdstrike_fdr"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.EDR

    @property
    def description(self) -> str:
        return "CrowdStrike Falcon Data Replicator event parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".jsonl"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json", "application/x-ndjson"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is CrowdStrike FDR format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:5]:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        # FDR events have specific CrowdStrike fields
                        if "event_simpleName" in data or "name" in data:
                            # Check for FDR-specific fields
                            if any(
                                field in data
                                for field in [
                                    "aid",
                                    "cid",
                                    "ComputerName",
                                    "ContextProcessId",
                                    "ParentProcessId",
                                    "fdr_event_type",
                                ]
                            ):
                                return True
                    except json.JSONDecodeError:
                        pass

            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse CrowdStrike FDR file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as file_handle:
                yield from self._parse_file(file_handle, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse file content."""
        # Try to detect format
        first_char = file_handle.read(1)
        file_handle.seek(0)

        if first_char == "[":
            # JSON array
            try:
                data = json.load(file_handle)
                for index, record in enumerate(data):
                    event = self._parse_record(record, source_name, index + 1)
                    if event:
                        yield event
            except json.JSONDecodeError:
                pass
        else:
            # JSONL
            for line_number, line in enumerate(file_handle, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    event = self._parse_record(record, source_name, line_number)
                    if event:
                        yield event
                except json.JSONDecodeError:
                    logger.debug(f"JSON parse error at line {line_number}")

    def _parse_record(
        self,
        record: dict[str, Any],
        source_name: str,
        line_number: int,
    ) -> ParsedEvent | None:
        """Parse a single FDR event record."""
        # Extract event type
        event_type = record.get("event_simpleName") or record.get("name", "unknown")

        # Extract timestamp
        timestamp = self._parse_timestamp(record)

        # Generate message
        message = self._generate_message(record, event_type)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="crowdstrike_fdr",
            source_file=source_name,
            source_line=line_number,
            event_kind="event",
        )

        # Set action
        event.event_action = event_type

        # Set categories
        event.event_category = FDR_EVENT_CATEGORY_MAP.get(event_type, ["host"])

        # Determine event type based on action
        if "Create" in event_type or "Rollup" in event_type or "Load" in event_type:
            event.event_type = ["start"]
        elif "Delete" in event_type or "Blocked" in event_type:
            event.event_type = ["end"]
        elif "Connect" in event_type or "Request" in event_type:
            event.event_type = ["connection"]
        elif "Logon" in event_type or "Logoff" in event_type:
            event.event_type = ["start"] if "Logon" in event_type else ["end"]
        else:
            event.event_type = ["info"]

        # Host information
        event.host_name = record.get("ComputerName", "")
        event.host_id = record.get("aid", "")

        # User information
        if record.get("UserName"):
            event.user_name = record["UserName"]
        if record.get("UserSid"):
            event.user_id = record["UserSid"]

        # Process information
        self._parse_process_fields(record, event)

        # Network information
        self._parse_network_fields(record, event)

        # File information
        self._parse_file_fields(record, event)

        # Registry information
        self._parse_registry_fields(record, event)

        # Detection information
        self._parse_detection_fields(record, event)

        # Common labels
        event.labels["cid"] = record.get("cid", "")
        event.labels["aid"] = record.get("aid", "")

        if record.get("event_platform"):
            event.labels["platform"] = record["event_platform"]

        if record.get("ConfigBuild"):
            event.labels["sensor_version"] = record["ConfigBuild"]

        # Determine severity
        event.event_severity = self._calculate_severity(record, event_type)

        # Store raw
        event.raw = record

        return event

    def _parse_process_fields(self, record: dict, event: ParsedEvent) -> None:
        """Extract process-related fields."""
        # Main process
        if record.get("ImageFileName"):
            event.process_name = Path(record["ImageFileName"]).name
            event.process_executable = record["ImageFileName"]

        if record.get("FileName"):
            event.process_name = record["FileName"]

        if record.get("TargetProcessId"):
            event.process_pid = int(record["TargetProcessId"])
        elif record.get("ContextProcessId"):
            event.process_pid = int(record["ContextProcessId"])

        if record.get("CommandLine"):
            event.process_command_line = record["CommandLine"]

        # Process hashes
        if record.get("SHA256HashData"):
            event.labels["process_sha256"] = record["SHA256HashData"]
        if record.get("MD5HashData"):
            event.labels["process_md5"] = record["MD5HashData"]

        # Parent process
        if record.get("ParentProcessId"):
            event.labels["parent_pid"] = str(record["ParentProcessId"])
        if record.get("ParentImageFileName"):
            event.labels["parent_executable"] = record["ParentImageFileName"]
        if record.get("ParentCommandLine"):
            event.labels["parent_command_line"] = record["ParentCommandLine"]

        # Grandparent process
        if record.get("GrandparentImageFileName"):
            event.labels["grandparent_executable"] = record["GrandparentImageFileName"]
        if record.get("GrandparentCommandLine"):
            event.labels["grandparent_command_line"] = record["GrandparentCommandLine"]

    def _parse_network_fields(self, record: dict, event: ParsedEvent) -> None:
        """Extract network-related fields."""
        # Local address
        if record.get("LocalAddressIP4"):
            event.source_ip = record["LocalAddressIP4"]
        elif record.get("LocalAddressIP6"):
            event.source_ip = record["LocalAddressIP6"]

        if record.get("LocalPort"):
            event.labels["source_port"] = str(record["LocalPort"])

        # Remote address
        if record.get("RemoteAddressIP4"):
            event.destination_ip = record["RemoteAddressIP4"]
        elif record.get("RemoteAddressIP6"):
            event.destination_ip = record["RemoteAddressIP6"]

        if record.get("RemotePort"):
            event.labels["destination_port"] = str(record["RemotePort"])

        # Protocol
        if record.get("Protocol"):
            protocol_map = {6: "tcp", 17: "udp", 1: "icmp"}
            event.labels["protocol"] = protocol_map.get(record["Protocol"], str(record["Protocol"]))

        # DNS
        if record.get("DomainName"):
            event.labels["dns_query"] = record["DomainName"]
        if record.get("QueryType"):
            event.labels["dns_query_type"] = str(record["QueryType"])
        if record.get("RespondingDnsServer"):
            event.labels["dns_server"] = record["RespondingDnsServer"]

        # HTTP
        if record.get("HttpHost"):
            event.labels["http_host"] = record["HttpHost"]
        if record.get("HttpPath"):
            event.url_path = record["HttpPath"]
        if record.get("HttpMethod"):
            event.labels["http_method"] = record["HttpMethod"]

    def _parse_file_fields(self, record: dict, event: ParsedEvent) -> None:
        """Extract file-related fields."""
        if record.get("TargetFileName"):
            event.file_path = record["TargetFileName"]
            event.file_name = Path(record["TargetFileName"]).name

        if record.get("TargetDirectoryName"):
            event.labels["target_directory"] = record["TargetDirectoryName"]

        if record.get("SourceFileName"):
            event.labels["source_file"] = record["SourceFileName"]

        # File hashes
        if record.get("TargetFileSHA256"):
            event.file_hash_sha256 = record["TargetFileSHA256"]
        if record.get("TargetFileMD5"):
            event.labels["file_md5"] = record["TargetFileMD5"]

    def _parse_registry_fields(self, record: dict, event: ParsedEvent) -> None:
        """Extract registry-related fields."""
        if record.get("RegObjectName"):
            event.registry_key = record["RegObjectName"]

        if record.get("RegValueName"):
            event.labels["registry_value_name"] = record["RegValueName"]

        if record.get("RegStringValue"):
            event.labels["registry_value_data"] = record["RegStringValue"][:500]

        if record.get("RegType"):
            reg_type_map = {
                1: "REG_SZ",
                2: "REG_EXPAND_SZ",
                3: "REG_BINARY",
                4: "REG_DWORD",
                7: "REG_MULTI_SZ",
                11: "REG_QWORD",
            }
            event.labels["registry_value_type"] = reg_type_map.get(
                record["RegType"], str(record["RegType"])
            )

    def _parse_detection_fields(self, record: dict, event: ParsedEvent) -> None:
        """Extract detection/alert-related fields."""
        if record.get("Severity"):
            event.labels["detection_severity"] = str(record["Severity"])

        if record.get("SeverityName"):
            event.labels["detection_severity_name"] = record["SeverityName"]

        if record.get("Technique"):
            event.labels["mitre_technique"] = record["Technique"]

        if record.get("Tactic"):
            event.labels["mitre_tactic"] = record["Tactic"]

        if record.get("PatternDispositionValue"):
            event.labels["disposition"] = str(record["PatternDispositionValue"])

        if record.get("DetectName"):
            event.labels["detection_name"] = record["DetectName"]

        if record.get("DetectDescription"):
            event.labels["detection_description"] = record["DetectDescription"][:500]

        if record.get("IOC"):
            event.labels["ioc"] = record["IOC"]

        if record.get("IOCType"):
            event.labels["ioc_type"] = record["IOCType"]

    def _parse_timestamp(self, record: dict) -> datetime:
        """Parse timestamp from FDR event."""
        # FDR uses various timestamp fields
        for field in ["timestamp", "ContextTimeStamp", "ProcessStartTime", "UtcTime"]:
            if field in record:
                try:
                    value = record[field]
                    if isinstance(value, (int, float)):
                        # Unix timestamp (seconds or milliseconds)
                        if value > 1e12:  # Milliseconds
                            return datetime.fromtimestamp(value / 1000, tz=UTC)
                        return datetime.fromtimestamp(value, tz=UTC)
                    elif isinstance(value, str):
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, OSError):
                    pass

        return datetime.now(UTC)

    def _generate_message(self, record: dict, event_type: str) -> str:
        """Generate human-readable message."""
        computer = record.get("ComputerName", "Unknown")
        user = record.get("UserName", "")

        # Build context-specific message
        if event_type in ("ProcessRollup2", "SyntheticProcessRollup2"):
            image = record.get("ImageFileName", "Unknown")
            cmd = record.get("CommandLine", "")[:100]
            return f"CrowdStrike: Process on {computer} - {image} {cmd}"

        elif event_type in ("NetworkConnectIP4", "NetworkConnectIP6"):
            remote_ip = record.get("RemoteAddressIP4") or record.get("RemoteAddressIP6", "")
            remote_port = record.get("RemotePort", "")
            return f"CrowdStrike: Network connection from {computer} to {remote_ip}:{remote_port}"

        elif event_type == "DnsRequest":
            domain = record.get("DomainName", "Unknown")
            return f"CrowdStrike: DNS query from {computer} for {domain}"

        elif event_type in ("UserLogon", "UserLogonFailed"):
            result = "successful" if event_type == "UserLogon" else "failed"
            return f"CrowdStrike: {result.capitalize()} logon on {computer} by {user}"

        elif event_type.startswith("File"):
            file_name = record.get("TargetFileName", "Unknown")
            return f"CrowdStrike: {event_type} on {computer} - {file_name}"

        elif event_type.startswith("Reg"):
            reg_key = record.get("RegObjectName", "Unknown")
            return f"CrowdStrike: {event_type} on {computer} - {reg_key}"

        elif event_type == "DetectionSummaryEvent":
            detect_name = record.get("DetectName", "Unknown")
            severity = record.get("SeverityName", "")
            return f"CrowdStrike: Detection on {computer} - {detect_name} ({severity})"

        else:
            return f"CrowdStrike: {event_type} on {computer}"

    def _calculate_severity(self, record: dict, event_type: str) -> int:
        """Calculate event severity based on event type and content."""
        # Detection events have explicit severity
        if record.get("Severity"):
            severity = record["Severity"]
            if severity >= 4:
                return 80
            elif severity >= 3:
                return 60
            elif severity >= 2:
                return 40
            else:
                return 20

        # Event type based severity
        if event_type in ("DetectionSummaryEvent", "IncidentSummaryEvent"):
            return 80
        elif event_type in ("ProcessBlocked", "ProcessInjection", "RansomwareFileAccess"):
            return 70
        elif event_type in ("UserLogonFailed",):
            return 40
        elif event_type in ("ProcessRollup2", "SyntheticProcessRollup2"):
            return 20
        else:
            return 20
