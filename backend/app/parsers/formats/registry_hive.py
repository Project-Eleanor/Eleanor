"""Windows Registry hive parser using Dissect.

Parses Windows Registry hive files (SAM, SYSTEM, SOFTWARE, NTUSER.DAT, etc.)
and extracts forensically relevant information.
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from app.parsers.base import ParsedEvent, ParserCategory
from app.parsers.formats.dissect_adapter import DissectParserAdapter
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Registry hive magic bytes
REGF_MAGIC = b"regf"

# Common registry paths of forensic interest
FORENSIC_PATHS = {
    # Run keys (persistence)
    r"Microsoft\Windows\CurrentVersion\Run": "persistence",
    r"Microsoft\Windows\CurrentVersion\RunOnce": "persistence",
    r"Microsoft\Windows\CurrentVersion\RunServices": "persistence",
    r"Microsoft\Windows NT\CurrentVersion\Winlogon": "persistence",
    # Services
    r"ControlSet001\Services": "service",
    r"ControlSet002\Services": "service",
    r"CurrentControlSet\Services": "service",
    # Network
    r"Microsoft\Windows NT\CurrentVersion\NetworkList": "network",
    r"ControlSet001\Services\Tcpip\Parameters\Interfaces": "network",
    # USB devices
    r"ControlSet001\Enum\USB": "usb_device",
    r"ControlSet001\Enum\USBSTOR": "usb_storage",
    # Recent documents
    r"Microsoft\Windows\CurrentVersion\Explorer\RecentDocs": "recent_docs",
    r"Microsoft\Windows\CurrentVersion\Explorer\ComDlg32": "recent_docs",
    # User activity
    r"Microsoft\Windows\CurrentVersion\Explorer\TypedPaths": "user_activity",
    r"Microsoft\Windows\CurrentVersion\Explorer\RunMRU": "user_activity",
    r"Microsoft\Windows\CurrentVersion\Explorer\UserAssist": "user_activity",
    # Shell bags
    r"Microsoft\Windows\Shell\Bags": "shellbag",
    r"Microsoft\Windows\Shell\BagMRU": "shellbag",
    # SAM users
    r"SAM\Domains\Account\Users": "user_account",
    # Time zone
    r"ControlSet001\Control\TimeZoneInformation": "system_config",
    # Computer name
    r"ControlSet001\Control\ComputerName": "system_config",
}


@register_parser
class WindowsRegistryParser(DissectParserAdapter):
    """Parser for Windows Registry hive files."""

    @property
    def name(self) -> str:
        return "windows_registry"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Windows Registry hive parser (SAM, SYSTEM, SOFTWARE, NTUSER.DAT)"

    @property
    def supported_extensions(self) -> list[str]:
        return [".dat", ".SAM", ".SYSTEM", ".SOFTWARE", ".SECURITY", ".DEFAULT"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for registry hive magic bytes."""
        if content and len(content) >= 4:
            return content[:4] == REGF_MAGIC

        if file_path:
            # Check by name for common hive files
            name = file_path.name.upper()
            if name in (
                "SAM",
                "SYSTEM",
                "SOFTWARE",
                "SECURITY",
                "DEFAULT",
                "NTUSER.DAT",
                "USRCLASS.DAT",
            ):
                return True

            # Check by extension
            if file_path.suffix.lower() == ".dat":
                try:
                    with open(file_path, "rb") as f:
                        return f.read(4) == REGF_MAGIC
                except Exception:
                    pass

        return False

    def _get_dissect_parser(self, source: Path | BinaryIO) -> Any:
        """Get Dissect registry parser."""
        from dissect.regf import regf

        if isinstance(source, Path):
            return regf.RegistryHive(open(source, "rb"))
        return regf.RegistryHive(source)

    def _iterate_records(self, parser: Any) -> Iterator[Any]:
        """Recursively iterate over registry keys."""

        def walk_keys(key, depth=0):
            yield key

            if depth > 50:  # Prevent infinite recursion
                return

            try:
                for subkey in key.subkeys():
                    yield from walk_keys(subkey, depth + 1)
            except Exception:
                pass

        try:
            root = parser.root()
            yield from walk_keys(root)
        except Exception as e:
            logger.error(f"Failed to get registry root: {e}")

    def _parse_record(self, record: Any, source_name: str) -> ParsedEvent | None:
        """Convert a registry key to ParsedEvent."""
        try:
            key_path = record.path if hasattr(record, "path") else str(record)
            key_name = record.name if hasattr(record, "name") else ""

            # Get timestamp
            timestamp = datetime.now(UTC)
            if hasattr(record, "timestamp") and record.timestamp:
                timestamp = self._to_datetime(record.timestamp)

            # Determine event category based on path
            # Sort patterns by length (descending) to match most specific pattern first
            event_category = "registry"
            key_path_lower = key_path.lower()
            for pattern, category in sorted(
                FORENSIC_PATHS.items(), key=lambda x: len(x[0]), reverse=True
            ):
                if pattern.lower() in key_path_lower:
                    event_category = category
                    break

            # Build message
            message = f"Registry key: {key_path}"

            # Extract values
            values = {}
            value_count = 0
            try:
                for value in record.values():
                    value_count += 1
                    if value_count > 100:  # Limit values to prevent memory issues
                        break

                    value_name = value.name if hasattr(value, "name") else str(value)
                    try:
                        value_data = value.value if hasattr(value, "value") else None
                        if isinstance(value_data, bytes):
                            # Try to decode as string, otherwise hex
                            try:
                                value_data = value_data.decode("utf-16-le").rstrip("\x00")
                            except Exception:
                                value_data = value_data.hex()[:200]  # Limit hex length
                        elif value_data is not None:
                            value_data = str(value_data)[:500]  # Limit string length

                        values[value_name] = value_data
                    except Exception:
                        pass
            except Exception:
                pass

            # Build raw data
            raw = {
                "key_path": key_path,
                "key_name": key_name,
                "value_count": value_count,
            }
            if values:
                raw["values"] = values

            # Map to ECS categories
            ecs_categories = ["configuration"]
            ecs_types = ["info"]
            action = "registry_key"

            if event_category == "persistence":
                ecs_categories = ["configuration", "persistence"]
                ecs_types = ["info"]
                action = "registry_persistence"
            elif event_category == "service":
                ecs_categories = ["configuration", "process"]
                action = "registry_service"
            elif event_category == "user_account":
                ecs_categories = ["iam"]
                action = "registry_user"
            elif event_category == "network":
                ecs_categories = ["network", "configuration"]
                action = "registry_network"
            elif event_category == "usb_device" or event_category == "usb_storage":
                ecs_categories = ["file", "configuration"]
                action = "registry_usb"

            return ParsedEvent(
                timestamp=timestamp,
                message=message,
                source_type="windows_registry",
                source_file=source_name,
                event_kind="event",
                event_category=ecs_categories,
                event_type=ecs_types,
                event_action=action,
                raw=raw,
                labels={
                    "registry_key": key_path,
                    "forensic_category": event_category,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to parse registry key: {e}")
            return None
