"""osquery log parser.

Parses osquery result logs in JSON format, including scheduled query results,
differential results, and snapshot results.
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


# osquery query name to ECS category mapping
OSQUERY_CATEGORY_MAP = {
    # Process queries
    "processes": ["process"],
    "process_events": ["process"],
    "process_open_sockets": ["process", "network"],
    "process_memory_map": ["process"],
    # Network queries
    "listening_ports": ["network"],
    "socket_events": ["network"],
    "arp_cache": ["network"],
    "routes": ["network"],
    "interface_addresses": ["network"],
    "dns_resolvers": ["network"],
    # File queries
    "file": ["file"],
    "file_events": ["file"],
    "hash": ["file"],
    "yara": ["file", "malware"],
    "mounts": ["file"],
    # User/Auth queries
    "users": ["iam"],
    "groups": ["iam"],
    "logged_in_users": ["authentication"],
    "last": ["authentication"],
    "user_ssh_keys": ["authentication"],
    "authorized_keys": ["authentication"],
    "shadow": ["iam"],
    # System queries
    "system_info": ["host"],
    "os_version": ["host"],
    "kernel_info": ["host"],
    "uptime": ["host"],
    "load_average": ["host"],
    "memory_info": ["host"],
    # Security queries
    "certificates": ["configuration"],
    "browser_plugins": ["package"],
    "chrome_extensions": ["package"],
    "firefox_addons": ["package"],
    "scheduled_tasks": ["process"],
    "crontab": ["process"],
    "startup_items": ["process"],
    "launchd": ["process"],
    "services": ["process"],
    "systemd_units": ["process"],
    # Windows specific
    "registry": ["configuration"],
    "windows_events": ["process"],
    "wmi_cli_event_consumers": ["process"],
    "powershell_events": ["process"],
    "windows_security_products": ["package"],
    # macOS specific
    "apps": ["package"],
    "safari_extensions": ["package"],
    "keychain_items": ["iam"],
    # Linux specific
    "deb_packages": ["package"],
    "rpm_packages": ["package"],
    "apt_sources": ["configuration"],
    "yum_sources": ["configuration"],
    "selinux_settings": ["configuration"],
    "iptables": ["network"],
    # Default
    "default": ["host"],
}


@register_parser
class OsqueryParser(BaseParser):
    """Parser for osquery result logs."""

    @property
    def name(self) -> str:
        return "osquery"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "osquery scheduled and ad-hoc query result log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".log"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json", "text/plain"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is osquery log format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:10]:
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue

                    try:
                        data = json.loads(line)
                        # osquery result logs have specific fields
                        if "name" in data and any(
                            k in data for k in ["columns", "snapshot", "diffResults"]
                        ):
                            return True
                        # osquery status logs
                        if "hostIdentifier" in data and "calendarTime" in data:
                            return True
                    except json.JSONDecodeError:
                        pass

            except Exception:
                pass

        if file_path:
            name = file_path.name.lower()
            if any(kw in name for kw in ["osquery", "osqueryd"]):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse osquery log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_lines(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_lines(text_stream, source_str)

    def _parse_lines(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse JSON lines from file."""
        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                yield from self._parse_record(record, source_name, line_num)
            except json.JSONDecodeError as e:
                logger.debug(f"JSON parse error at line {line_num}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Parse error at line {line_num}: {e}")
                continue

    def _parse_record(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> Iterator[ParsedEvent]:
        """Parse a single osquery record.

        osquery can emit different record types:
        - Snapshot: Full table results
        - Differential: Added/removed rows
        - Event-based: Real-time file/process events
        """
        # Determine record type
        if "diffResults" in record:
            yield from self._parse_differential(record, source_name, line_num)
        elif "snapshot" in record:
            yield from self._parse_snapshot(record, source_name, line_num)
        elif "columns" in record:
            # Single result row (from some logging formats)
            yield self._parse_single_row(record, source_name, line_num)
        else:
            # Status or other log type
            event = self._parse_status(record, source_name, line_num)
            if event:
                yield event

    def _parse_differential(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> Iterator[ParsedEvent]:
        """Parse differential query results."""
        query_name = record.get("name", "unknown")
        host_identifier = record.get("hostIdentifier", "")
        timestamp = self._parse_timestamp(record)

        diff_results = record.get("diffResults", {})

        # Added rows
        for row in diff_results.get("added", []):
            event = self._create_event(
                row=row,
                query_name=query_name,
                host_identifier=host_identifier,
                timestamp=timestamp,
                action="added",
                source_name=source_name,
                line_num=line_num,
            )
            event.raw["osquery_action"] = "added"
            yield event

        # Removed rows
        for row in diff_results.get("removed", []):
            event = self._create_event(
                row=row,
                query_name=query_name,
                host_identifier=host_identifier,
                timestamp=timestamp,
                action="removed",
                source_name=source_name,
                line_num=line_num,
            )
            event.raw["osquery_action"] = "removed"
            yield event

    def _parse_snapshot(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> Iterator[ParsedEvent]:
        """Parse snapshot query results."""
        query_name = record.get("name", "unknown")
        host_identifier = record.get("hostIdentifier", "")
        timestamp = self._parse_timestamp(record)

        snapshot = record.get("snapshot", [])

        for row in snapshot:
            event = self._create_event(
                row=row,
                query_name=query_name,
                host_identifier=host_identifier,
                timestamp=timestamp,
                action="snapshot",
                source_name=source_name,
                line_num=line_num,
            )
            yield event

    def _parse_single_row(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent:
        """Parse a single result row."""
        query_name = record.get("name", "unknown")
        host_identifier = record.get("hostIdentifier", "")
        timestamp = self._parse_timestamp(record)
        row = record.get("columns", {})

        return self._create_event(
            row=row,
            query_name=query_name,
            host_identifier=host_identifier,
            timestamp=timestamp,
            action="result",
            source_name=source_name,
            line_num=line_num,
        )

    def _parse_status(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse osquery status/info log."""
        if "severity" not in record and "message" not in record:
            return None

        timestamp = self._parse_timestamp(record)
        host_identifier = record.get("hostIdentifier", "")

        event = ParsedEvent(
            timestamp=timestamp,
            message=record.get("message", "osquery status"),
            source_type="osquery:status",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_category=["host"],
            event_type=["info"],
        )

        if host_identifier:
            event.host_name = host_identifier

        # Map severity
        severity = record.get("severity", 0)
        severity_map = {0: 10, 1: 40, 2: 70, 3: 100}
        event.event_severity = severity_map.get(severity, 10)

        event.raw = record
        event.labels["osquery_version"] = record.get("version", "")

        return event

    def _create_event(
        self,
        row: dict[str, Any],
        query_name: str,
        host_identifier: str,
        timestamp: datetime,
        action: str,
        source_name: str,
        line_num: int,
    ) -> ParsedEvent:
        """Create event from osquery result row."""
        message = self._generate_message(query_name, row, action)

        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type=f"osquery:{query_name}",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
        )

        # Set categories based on query name
        event.event_category = self._get_categories(query_name)

        # Map action to event type
        if action == "added":
            event.event_type = ["creation"]
        elif action == "removed":
            event.event_type = ["deletion"]
        else:
            event.event_type = ["info"]

        event.event_action = query_name

        # Set host
        if host_identifier:
            event.host_name = host_identifier

        # Map common fields
        self._map_fields(event, row, query_name)

        # Store raw data
        event.raw = row
        event.labels["osquery_query"] = query_name

        return event

    def _parse_timestamp(self, record: dict[str, Any]) -> datetime:
        """Parse timestamp from osquery record."""
        # Try different timestamp fields
        for field in ["unixTime", "time", "timestamp"]:
            if field in record:
                try:
                    value = record[field]
                    if isinstance(value, (int, float)):
                        return datetime.fromtimestamp(value, tz=UTC)
                    elif isinstance(value, str):
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, OSError):
                    pass

        # Try calendarTime (human readable)
        if "calendarTime" in record:
            try:
                # Format: "Mon Jan  2 15:04:05 2006 UTC"
                dt = datetime.strptime(record["calendarTime"], "%a %b %d %H:%M:%S %Y %Z")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                pass

        return datetime.now(UTC)

    def _get_categories(self, query_name: str) -> list[str]:
        """Get ECS categories for query name."""
        # Check exact match
        if query_name in OSQUERY_CATEGORY_MAP:
            return OSQUERY_CATEGORY_MAP[query_name]

        # Check partial match
        query_lower = query_name.lower()
        for key, cats in OSQUERY_CATEGORY_MAP.items():
            if key in query_lower:
                return cats

        return OSQUERY_CATEGORY_MAP["default"]

    def _generate_message(
        self,
        query_name: str,
        row: dict[str, Any],
        action: str,
    ) -> str:
        """Generate human-readable message."""
        # Process-related
        if "processes" in query_name or "process_events" in query_name:
            name = row.get("name", row.get("path", "?"))
            pid = row.get("pid", "?")
            cmdline = row.get("cmdline", "")[:100]
            return f"Process {action}: {name} (PID: {pid}) {cmdline}"

        # Network-related
        if "listening_ports" in query_name or "socket" in query_name:
            port = row.get("port", row.get("local_port", "?"))
            proto = row.get("protocol", "?")
            addr = row.get("address", row.get("local_address", "*"))
            return f"Socket {action}: {addr}:{port} ({proto})"

        # File-related
        if "file" in query_name:
            path = row.get("path", row.get("filename", "?"))
            return f"File {action}: {path}"

        # User-related
        if "users" in query_name or "logged_in" in query_name:
            user = row.get("username", row.get("user", "?"))
            return f"User {action}: {user}"

        # Hash-related
        if "hash" in query_name:
            path = row.get("path", "?")
            sha256 = row.get("sha256", "")[:16]
            return f"File hash: {path} ({sha256}...)"

        # Package-related
        if any(pkg in query_name for pkg in ["packages", "apps", "extensions"]):
            name = row.get("name", row.get("identifier", "?"))
            version = row.get("version", "")
            return f"Package {action}: {name} {version}"

        # Default
        return f"osquery {query_name}: {action}"

    def _map_fields(
        self,
        event: ParsedEvent,
        row: dict[str, Any],
        query_name: str,
    ) -> None:
        """Map osquery fields to ECS fields."""
        # Process fields
        if "pid" in row:
            try:
                event.process_pid = int(row["pid"])
            except (ValueError, TypeError):
                pass

        if "parent" in row:
            try:
                event.process_ppid = int(row["parent"])
            except (ValueError, TypeError):
                pass

        if "name" in row and "process" in query_name:
            event.process_name = row["name"]
        elif "path" in row and "process" in query_name:
            event.process_executable = row["path"]

        if "cmdline" in row:
            event.process_command_line = row["cmdline"]

        # User fields
        if "username" in row:
            event.user_name = row["username"]
        elif "user" in row:
            event.user_name = row["user"]

        if "uid" in row:
            event.user_id = str(row["uid"])

        # File fields
        if "path" in row and "file" in query_name:
            event.file_path = row["path"]
            if "/" in row["path"]:
                event.file_name = row["path"].split("/")[-1]
            elif "\\" in row["path"]:
                event.file_name = row["path"].split("\\")[-1]

        # Hash fields
        if "md5" in row:
            event.file_hash_md5 = row["md5"]
        if "sha1" in row:
            event.file_hash_sha1 = row["sha1"]
        if "sha256" in row:
            event.file_hash_sha256 = row["sha256"]

        # Network fields
        if "local_address" in row or "address" in row:
            event.source_ip = row.get("local_address", row.get("address"))
        if "local_port" in row or "port" in row:
            try:
                event.source_port = int(row.get("local_port", row.get("port")))
            except (ValueError, TypeError):
                pass

        if "remote_address" in row:
            event.destination_ip = row["remote_address"]
        if "remote_port" in row:
            try:
                event.destination_port = int(row["remote_port"])
            except (ValueError, TypeError):
                pass

        if "protocol" in row:
            proto_map = {"6": "tcp", "17": "udp", "1": "icmp"}
            proto = row["protocol"]
            event.network_protocol = proto_map.get(str(proto), str(proto).lower())

        # Host fields
        if "hostname" in row:
            event.host_name = row["hostname"]

        # Additional labels for useful fields
        useful_fields = [
            "version",
            "description",
            "state",
            "mode",
            "permissions",
            "type",
            "action",
            "status",
        ]
        for field in useful_fields:
            if field in row:
                event.labels[field] = str(row[field])
