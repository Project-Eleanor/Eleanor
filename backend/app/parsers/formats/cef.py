"""CEF (Common Event Format) log parser.

Parses ArcSight CEF format logs used by many SIEMs and security products.
CEF format: CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
"""

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# CEF header pattern
CEF_HEADER_PATTERN = re.compile(
    r"^CEF:(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|(.*)$"
)

# Extension key-value pattern (handles escaped characters)
CEF_EXTENSION_PATTERN = re.compile(r"(\w+)=((?:[^\\= ]|\\.)*)")

# CEF severity to numeric mapping
SEVERITY_MAP = {
    "0": 0,
    "unknown": 0,
    "1": 10,
    "low": 10,
    "2": 20,
    "3": 30,
    "medium": 30,
    "4": 40,
    "5": 50,
    "6": 60,
    "high": 60,
    "7": 70,
    "8": 80,
    "very-high": 80,
    "9": 90,
    "10": 100,
    "critical": 100,
}

# CEF extension field to ECS mapping
CEF_TO_ECS = {
    # Source fields
    "src": "source_ip",
    "spt": "source_port",
    "smac": "source_mac",
    "shost": "source_host",
    "suid": "source_user_id",
    "suser": "source_user",
    "sntdom": "source_domain",
    # Destination fields
    "dst": "destination_ip",
    "dpt": "destination_port",
    "dmac": "destination_mac",
    "dhost": "destination_host",
    "duid": "destination_user_id",
    "duser": "destination_user",
    "dntdom": "destination_domain",
    # Network fields
    "proto": "network_protocol",
    "in": "bytes_in",
    "out": "bytes_out",
    "bytesIn": "bytes_in",
    "bytesOut": "bytes_out",
    # Process fields
    "sproc": "source_process",
    "dproc": "destination_process",
    "fname": "file_name",
    "filePath": "file_path",
    "fsize": "file_size",
    "fileHash": "file_hash",
    # Time fields
    "rt": "receipt_time",
    "start": "start_time",
    "end": "end_time",
    # Request/Response
    "request": "url",
    "requestMethod": "http_method",
    "requestContext": "request_context",
    "cs1": "custom_string_1",
    "cs2": "custom_string_2",
    "cs3": "custom_string_3",
    "cs4": "custom_string_4",
    "cs5": "custom_string_5",
    "cs6": "custom_string_6",
    "cn1": "custom_number_1",
    "cn2": "custom_number_2",
    "cn3": "custom_number_3",
    # Outcome
    "outcome": "event_outcome",
    "reason": "reason",
    # Device
    "dvc": "device_ip",
    "dvchost": "device_hostname",
    "dvcmac": "device_mac",
    "dvcpid": "device_process_id",
    # Message
    "msg": "message",
    "act": "action",
    "cat": "category",
    # External ID
    "externalId": "external_id",
    "oldFileHash": "old_file_hash",
    "fileCreateTime": "file_create_time",
    "fileModificationTime": "file_modification_time",
}


@register_parser
class CEFParser(BaseParser):
    """Parser for CEF (Common Event Format) logs."""

    @property
    def name(self) -> str:
        return "cef"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "ArcSight CEF (Common Event Format) log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".cef", ".log", ".txt"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/plain", "application/octet-stream"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content contains CEF format logs."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                # Check for CEF header pattern
                if "CEF:" in text and "|" in text:
                    lines = text.split("\n")
                    for line in lines[:10]:  # Check first 10 lines
                        if line.strip().startswith("CEF:") or "CEF:" in line:
                            return True
            except Exception:
                pass

        if file_path:
            ext = file_path.suffix.lower()
            if ext == ".cef":
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse CEF log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_lines(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_lines(text_stream, source_str)

    def _parse_lines(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse lines from file handle."""
        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line:
                continue

            # Find CEF start in line (may have syslog prefix)
            cef_start = line.find("CEF:")
            if cef_start == -1:
                continue

            # Extract syslog prefix if present
            syslog_prefix = line[:cef_start].strip() if cef_start > 0 else None
            cef_line = line[cef_start:]

            try:
                event = self._parse_cef_line(cef_line, source_name, line_num, syslog_prefix)
                if event:
                    yield event
            except Exception as e:
                logger.debug(f"Failed to parse CEF line {line_num}: {e}")
                continue

    def _parse_cef_line(
        self,
        line: str,
        source_name: str,
        line_num: int,
        syslog_prefix: str | None = None,
    ) -> ParsedEvent | None:
        """Parse a single CEF line."""
        match = CEF_HEADER_PATTERN.match(line)
        if not match:
            return None

        (
            version,
            device_vendor,
            device_product,
            device_version,
            signature_id,
            name,
            severity,
            extension,
        ) = match.groups()

        # Unescape pipe characters in header fields
        device_vendor = self._unescape_field(device_vendor)
        device_product = self._unescape_field(device_product)
        device_version = self._unescape_field(device_version)
        signature_id = self._unescape_field(signature_id)
        name = self._unescape_field(name)

        # Parse extension fields
        ext_fields = self._parse_extension(extension)

        # Extract timestamp
        timestamp = self._extract_timestamp(ext_fields, syslog_prefix)

        # Map severity to numeric
        severity_num = self._map_severity(severity)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=name,
            source_type="cef",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_severity=severity_num,
        )

        # Set event action from signature ID and name
        event.event_action = f"{signature_id}:{name}" if signature_id else name

        # Map extension fields to ECS
        self._map_to_ecs(event, ext_fields)

        # Store CEF metadata in labels
        event.labels = {
            "cef_version": version,
            "device_vendor": device_vendor,
            "device_product": device_product,
            "device_version": device_version,
            "signature_id": signature_id,
        }

        # Store raw extension
        event.raw = {
            "cef_header": {
                "version": version,
                "device_vendor": device_vendor,
                "device_product": device_product,
                "device_version": device_version,
                "signature_id": signature_id,
                "name": name,
                "severity": severity,
            },
            "extension": ext_fields,
        }

        # Categorize event
        self._categorize_event(event, ext_fields, device_product, name)

        return event

    def _unescape_field(self, value: str) -> str:
        """Unescape CEF field value."""
        return value.replace("\\|", "|").replace("\\\\", "\\")

    def _parse_extension(self, extension: str) -> dict[str, str]:
        """Parse CEF extension into key-value pairs."""
        fields = {}

        if not extension:
            return fields

        # CEF extension parsing is tricky - values can contain spaces
        # and the next key=value pair starts at the next unescaped key=
        current_pos = 0
        current_key = None
        current_value_parts = []

        for match in CEF_EXTENSION_PATTERN.finditer(extension):
            if current_key is not None:
                # Get text between previous match end and current match start
                between = extension[current_pos : match.start()].strip()
                if between:
                    current_value_parts.append(between)
                fields[current_key] = " ".join(current_value_parts).strip()
                current_value_parts = []

            current_key = match.group(1)
            current_value_parts = [match.group(2)]
            current_pos = match.end()

        # Handle last key-value pair
        if current_key is not None:
            remaining = extension[current_pos:].strip()
            if remaining:
                current_value_parts.append(remaining)
            fields[current_key] = " ".join(current_value_parts).strip()

        # Unescape values
        for key in fields:
            fields[key] = self._unescape_value(fields[key])

        return fields

    def _unescape_value(self, value: str) -> str:
        """Unescape CEF extension value."""
        return (
            value.replace("\\=", "=")
            .replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace("\\\\", "\\")
        )

    def _extract_timestamp(
        self,
        ext_fields: dict[str, str],
        syslog_prefix: str | None,
    ) -> datetime:
        """Extract timestamp from extension fields or syslog prefix."""
        # Try common timestamp fields
        for field in ["rt", "start", "end", "deviceReceiptTime"]:
            if field in ext_fields:
                ts = self._parse_timestamp(ext_fields[field])
                if ts:
                    return ts

        # Try syslog prefix
        if syslog_prefix:
            ts = self._parse_syslog_timestamp(syslog_prefix)
            if ts:
                return ts

        return datetime.now(UTC)

    def _parse_timestamp(self, value: str) -> datetime | None:
        """Parse CEF timestamp value."""
        # CEF timestamps can be in various formats
        formats = [
            "%b %d %Y %H:%M:%S",
            "%b %d %H:%M:%S %Y",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                continue

        # Try epoch milliseconds
        try:
            epoch_ms = int(value)
            if epoch_ms > 1e12:  # Milliseconds
                return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
            elif epoch_ms > 1e9:  # Seconds
                return datetime.fromtimestamp(epoch_ms, tz=UTC)
        except ValueError:
            pass

        return None

    def _parse_syslog_timestamp(self, prefix: str) -> datetime | None:
        """Parse timestamp from syslog prefix."""
        # Common syslog format: "Oct 10 14:30:15 hostname"
        match = re.search(r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", prefix)
        if match:
            try:
                ts_str = match.group(1)
                # Add current year
                current_year = datetime.now().year
                dt = datetime.strptime(f"{current_year} {ts_str}", "%Y %b %d %H:%M:%S")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                pass
        return None

    def _map_severity(self, severity: str) -> int:
        """Map CEF severity to numeric 0-100."""
        severity_lower = severity.lower().strip()
        if severity_lower in SEVERITY_MAP:
            return SEVERITY_MAP[severity_lower]

        # Try numeric
        try:
            num = int(severity)
            return min(100, max(0, num * 10))
        except ValueError:
            return 0

    def _map_to_ecs(self, event: ParsedEvent, ext_fields: dict[str, str]) -> None:
        """Map CEF extension fields to ECS event fields."""
        # Source
        if "src" in ext_fields:
            event.source_ip = ext_fields["src"]
        if "spt" in ext_fields:
            try:
                event.source_port = int(ext_fields["spt"])
            except ValueError:
                pass

        # Destination
        if "dst" in ext_fields:
            event.destination_ip = ext_fields["dst"]
        if "dpt" in ext_fields:
            try:
                event.destination_port = int(ext_fields["dpt"])
            except ValueError:
                pass

        # User
        if "suser" in ext_fields:
            event.user_name = ext_fields["suser"]
        elif "duser" in ext_fields:
            event.user_name = ext_fields["duser"]

        if "sntdom" in ext_fields:
            event.user_domain = ext_fields["sntdom"]
        elif "dntdom" in ext_fields:
            event.user_domain = ext_fields["dntdom"]

        # Host
        if "shost" in ext_fields:
            event.host_name = ext_fields["shost"]
        elif "dhost" in ext_fields:
            event.host_name = ext_fields["dhost"]
        elif "dvchost" in ext_fields:
            event.host_name = ext_fields["dvchost"]

        # Process
        if "sproc" in ext_fields:
            event.process_name = ext_fields["sproc"]
        elif "dproc" in ext_fields:
            event.process_name = ext_fields["dproc"]

        # File
        if "fname" in ext_fields:
            event.file_name = ext_fields["fname"]
        if "filePath" in ext_fields:
            event.file_path = ext_fields["filePath"]
        if "fileHash" in ext_fields:
            hash_value = ext_fields["fileHash"]
            if len(hash_value) == 32:
                event.file_hash_md5 = hash_value
            elif len(hash_value) == 40:
                event.file_hash_sha1 = hash_value
            elif len(hash_value) == 64:
                event.file_hash_sha256 = hash_value

        # URL
        if "request" in ext_fields:
            event.url_full = ext_fields["request"]

        # Network
        if "proto" in ext_fields:
            event.network_protocol = ext_fields["proto"].lower()

        # Message override
        if "msg" in ext_fields and ext_fields["msg"]:
            event.message = ext_fields["msg"]

        # Outcome
        if "outcome" in ext_fields:
            outcome = ext_fields["outcome"].lower()
            if outcome in ("success", "allow", "permit"):
                event.event_outcome = "success"
            elif outcome in ("failure", "deny", "block", "fail"):
                event.event_outcome = "failure"
            else:
                event.event_outcome = outcome

    def _categorize_event(
        self,
        event: ParsedEvent,
        ext_fields: dict[str, str],
        device_product: str,
        name: str,
    ) -> None:
        """Categorize event based on content."""
        product_lower = device_product.lower() if device_product else ""
        name_lower = name.lower() if name else ""
        cat = ext_fields.get("cat", "").lower()

        # Network events
        if any(kw in product_lower for kw in ["firewall", "ids", "ips", "router", "switch"]):
            event.event_category = ["network"]
            if any(kw in name_lower for kw in ["block", "deny", "drop"]):
                event.event_type = ["denied"]
            elif any(kw in name_lower for kw in ["allow", "permit", "accept"]):
                event.event_type = ["allowed"]
            else:
                event.event_type = ["connection"]
            return

        # Intrusion detection
        if any(kw in product_lower for kw in ["ids", "ips", "detection", "snort", "suricata"]):
            event.event_category = ["intrusion_detection"]
            event.event_type = ["info"]
            event.event_kind = "alert"
            return

        # Authentication
        if any(kw in name_lower for kw in ["login", "logon", "logoff", "logout", "auth"]):
            event.event_category = ["authentication"]
            if any(kw in name_lower for kw in ["success", "succeeded"]):
                event.event_type = ["start"]
                event.event_outcome = "success"
            elif any(kw in name_lower for kw in ["fail", "failed", "invalid"]):
                event.event_type = ["start"]
                event.event_outcome = "failure"
            elif any(kw in name_lower for kw in ["logout", "logoff"]):
                event.event_type = ["end"]
            else:
                event.event_type = ["info"]
            return

        # File operations
        if any(kw in name_lower for kw in ["file", "write", "read", "delete", "create", "modify"]):
            event.event_category = ["file"]
            if "create" in name_lower:
                event.event_type = ["creation"]
            elif "delete" in name_lower:
                event.event_type = ["deletion"]
            elif "modify" in name_lower or "change" in name_lower:
                event.event_type = ["change"]
            else:
                event.event_type = ["access"]
            return

        # Malware
        if any(kw in cat for kw in ["malware", "virus", "threat", "malicious"]):
            event.event_category = ["malware"]
            event.event_kind = "alert"
            event.event_type = ["info"]
            return

        # Web events
        if any(kw in product_lower for kw in ["proxy", "waf", "web"]) or "request" in ext_fields:
            event.event_category = ["web"]
            event.event_type = ["access"]
            return

        # Default
        event.event_category = ["process"]
        event.event_type = ["info"]
