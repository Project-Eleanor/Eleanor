"""Windows Event Log (EVTX) parser.

Parses Windows Event Log files using the python-evtx library.
Extracts events and normalizes to ECS format.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory

if TYPE_CHECKING:
    from evtx import PyEvtxParser
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# EVTX magic bytes
EVTX_MAGIC = b"ElfFile\x00"

# Common Windows Event IDs and their categories
EVENT_CATEGORY_MAP = {
    # Authentication events
    4624: (["authentication"], ["start"], "user_logon"),
    4625: (["authentication"], ["start"], "user_logon_failed"),
    4634: (["authentication"], ["end"], "user_logoff"),
    4648: (["authentication"], ["start"], "explicit_credential_logon"),
    4672: (["authentication", "iam"], ["admin"], "special_privileges_assigned"),
    # Process events
    4688: (["process"], ["start"], "process_created"),
    4689: (["process"], ["end"], "process_terminated"),
    # Object access
    4663: (["file"], ["access"], "object_access"),
    4656: (["file"], ["access"], "handle_requested"),
    4658: (["file"], ["access"], "handle_closed"),
    # Account management
    4720: (["iam"], ["user", "creation"], "user_account_created"),
    4722: (["iam"], ["user", "change"], "user_account_enabled"),
    4723: (["iam"], ["user", "change"], "password_change_attempt"),
    4724: (["iam"], ["user", "change"], "password_reset_attempt"),
    4725: (["iam"], ["user", "change"], "user_account_disabled"),
    4726: (["iam"], ["user", "deletion"], "user_account_deleted"),
    4732: (["iam"], ["group", "change"], "member_added_to_group"),
    4733: (["iam"], ["group", "change"], "member_removed_from_group"),
    # Security policy
    4719: (["configuration"], ["change"], "audit_policy_changed"),
    4907: (["configuration"], ["change"], "auditing_settings_changed"),
    # Service events
    7045: (["configuration"], ["creation"], "service_installed"),
    7036: (["process"], ["change"], "service_state_changed"),
    # Scheduled tasks
    4698: (["configuration"], ["creation"], "scheduled_task_created"),
    4699: (["configuration"], ["deletion"], "scheduled_task_deleted"),
    4700: (["configuration"], ["change"], "scheduled_task_enabled"),
    4701: (["configuration"], ["change"], "scheduled_task_disabled"),
    4702: (["configuration"], ["change"], "scheduled_task_updated"),
    # PowerShell
    4103: (["process"], ["info"], "powershell_module_logging"),
    4104: (["process"], ["info"], "powershell_script_block"),
    # Network
    5156: (["network"], ["connection"], "wfp_connection_allowed"),
    5157: (["network"], ["connection"], "wfp_connection_blocked"),
}


@register_parser
class WindowsEvtxParser(BaseParser):
    """Parser for Windows Event Log (EVTX) files."""

    @property
    def name(self) -> str:
        return "windows_evtx"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "Windows Event Log (.evtx) parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".evtx"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-ms-evtx"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for EVTX magic bytes."""
        if content and len(content) >= 8:
            return content[:8] == EVTX_MAGIC

        if file_path:
            if file_path.suffix.lower() == ".evtx":
                return True
            try:
                with open(file_path, "rb") as f:
                    header = f.read(8)
                    return header == EVTX_MAGIC
            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse EVTX file and yield events."""
        try:
            import Evtx.Evtx as evtx
            import Evtx.Views as evtx_views
        except ImportError:
            logger.error("python-evtx not installed. Install with: pip install python-evtx")
            return

        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            if isinstance(source, Path):
                with evtx.Evtx(str(source)) as log:
                    yield from self._parse_log(log, source_str)
            else:
                # For file-like objects, we need to save to temp file
                # as python-evtx requires file path
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".evtx", delete=False) as tmp:
                    tmp.write(source.read())
                    tmp_path = tmp.name

                try:
                    with evtx.Evtx(tmp_path) as log:
                        yield from self._parse_log(log, source_str)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to parse EVTX: {e}")
            raise

    def _parse_log(self, log: "PyEvtxParser", source_name: str) -> Iterator[ParsedEvent]:
        """Parse an open EVTX log."""
        for record in log.records():
            try:
                xml_str = record.xml()
                root = ET.fromstring(xml_str)
                yield self._parse_record(root, source_name, record.record_num())
            except Exception as e:
                logger.debug(f"Failed to parse record: {e}")
                continue

    def _parse_record(self, root: ET.Element, source_name: str, record_num: int) -> ParsedEvent:
        """Parse a single EVTX record from XML."""
        ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

        # Extract System fields
        system = root.find("e:System", ns)
        event_id = self._get_text(system, "e:EventID", ns, default="0")
        event_id_int = int(event_id) if event_id.isdigit() else 0

        time_created = system.find("e:TimeCreated", ns)
        timestamp_str = time_created.get("SystemTime") if time_created is not None else None

        if timestamp_str:
            try:
                # Handle various timestamp formats
                timestamp_str = timestamp_str.replace("Z", "+00:00")
                if "." in timestamp_str:
                    # Truncate nanoseconds to microseconds
                    parts = timestamp_str.split(".")
                    frac = parts[1].split("+")[0].split("-")[0][:6]
                    tz = "+" + parts[1].split("+")[1] if "+" in parts[1] else ""
                    if "-" in parts[1] and "+" not in parts[1]:
                        tz = "-" + parts[1].split("-")[1]
                    timestamp_str = f"{parts[0]}.{frac}{tz}"
                timestamp = datetime.fromisoformat(timestamp_str)
            except Exception:
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)

        computer = self._get_text(system, "e:Computer", ns)
        channel = self._get_text(system, "e:Channel", ns)
        provider = system.find("e:Provider", ns)
        provider_name = provider.get("Name") if provider is not None else None

        # Get event category/type/action from mapping
        if event_id_int in EVENT_CATEGORY_MAP:
            categories, types, action = EVENT_CATEGORY_MAP[event_id_int]
        else:
            categories = ["process"]
            types = ["info"]
            action = f"event_{event_id}"

        # Extract EventData fields
        event_data = root.find("e:EventData", ns)
        data_fields = {}
        if event_data is not None:
            for data in event_data.findall("e:Data", ns):
                name = data.get("Name", f"data_{len(data_fields)}")
                data_fields[name] = data.text

        # Build message from event data
        message = self._build_message(event_id_int, provider_name, data_fields)

        # Extract user info
        user_name = data_fields.get("TargetUserName") or data_fields.get("SubjectUserName")
        user_domain = data_fields.get("TargetDomainName") or data_fields.get("SubjectDomainName")
        user_id = data_fields.get("TargetUserSid") or data_fields.get("SubjectUserSid")

        # Extract process info
        process_name = data_fields.get("NewProcessName") or data_fields.get("ProcessName")
        process_id = data_fields.get("NewProcessId") or data_fields.get("ProcessId")
        parent_process_id = data_fields.get("ParentProcessId") or data_fields.get("CreatorProcessId")
        command_line = data_fields.get("CommandLine")

        # Extract network info
        source_ip = data_fields.get("IpAddress") or data_fields.get("SourceAddress")
        source_port = data_fields.get("IpPort") or data_fields.get("SourcePort")
        dest_ip = data_fields.get("DestAddress")
        dest_port = data_fields.get("DestPort")

        # Determine outcome
        outcome = None
        if event_id_int == 4624:
            outcome = "success"
        elif event_id_int == 4625:
            outcome = "failure"

        return ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="windows_evtx",
            source_file=source_name,
            source_line=record_num,
            event_kind="event",
            event_category=categories,
            event_type=types,
            event_action=action,
            event_outcome=outcome,
            host_name=computer,
            user_name=user_name,
            user_domain=user_domain,
            user_id=user_id,
            process_name=self._extract_filename(process_name) if process_name else None,
            process_pid=int(process_id, 16) if process_id and process_id.startswith("0x") else (int(process_id) if process_id and process_id.isdigit() else None),
            process_ppid=int(parent_process_id, 16) if parent_process_id and parent_process_id.startswith("0x") else (int(parent_process_id) if parent_process_id and parent_process_id.isdigit() else None),
            process_command_line=command_line,
            process_executable=process_name,
            source_ip=source_ip,
            source_port=int(source_port) if source_port and source_port.isdigit() else None,
            destination_ip=dest_ip,
            destination_port=int(dest_port) if dest_port and dest_port.isdigit() else None,
            raw=data_fields,
            labels={
                "event_id": event_id,
                "channel": channel or "",
                "provider": provider_name or "",
            },
        )

    def _get_text(self, parent, path: str, ns: dict, default: str = "") -> str:
        """Safely get text from XML element."""
        if parent is None:
            return default
        elem = parent.find(path, ns)
        return elem.text if elem is not None and elem.text else default

    def _build_message(self, event_id: int, provider: str | None, data: dict) -> str:
        """Build human-readable message for common events."""
        provider_str = provider or "Windows"

        if event_id == 4624:
            user = data.get("TargetUserName", "unknown")
            domain = data.get("TargetDomainName", "")
            logon_type = data.get("LogonType", "")
            return f"User {domain}\\{user} logged on (type {logon_type})"

        elif event_id == 4625:
            user = data.get("TargetUserName", "unknown")
            domain = data.get("TargetDomainName", "")
            return f"Failed login attempt for {domain}\\{user}"

        elif event_id == 4688:
            process = data.get("NewProcessName", "unknown")
            user = data.get("SubjectUserName", "")
            return f"Process created: {process} by {user}"

        elif event_id == 4689:
            process = data.get("ProcessName", "unknown")
            return f"Process terminated: {process}"

        elif event_id == 4720:
            user = data.get("TargetUserName", "unknown")
            return f"User account created: {user}"

        elif event_id == 4726:
            user = data.get("TargetUserName", "unknown")
            return f"User account deleted: {user}"

        elif event_id == 7045:
            service = data.get("ServiceName", "unknown")
            return f"Service installed: {service}"

        elif event_id == 4104:
            return "PowerShell script block executed"

        return f"{provider_str} Event {event_id}"

    def _extract_filename(self, path: str) -> str | None:
        """Extract filename from path, handling Windows paths on Linux."""
        if not path:
            return None
        try:
            from pathlib import PurePosixPath, PureWindowsPath

            # Detect Windows path
            if "\\" in path or (len(path) > 1 and path[1] == ":"):
                return PureWindowsPath(path).name
            return PurePosixPath(path).name
        except Exception:
            return path
