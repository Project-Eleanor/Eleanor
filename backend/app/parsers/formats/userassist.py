"""Windows UserAssist parser.

UserAssist tracks user interaction with Windows shell objects (programs, shortcuts).
Data is stored in the NTUSER.DAT registry hive with ROT13-encoded key names.

Location: NTUSER.DAT
Key: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\UserAssist
"""

import codecs
import logging
import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

try:
    from dissect.regf import RegistryHive
    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False


# Known UserAssist GUIDs
USERASSIST_GUIDS = {
    "{CEBFF5CD-ACE2-4F4F-9178-9926F41749EA}": "Executable File Execution",
    "{F4E57C4B-2036-45F0-A9AB-443BCFE33D9F}": "Shortcut File Execution",
    "{75048700-EF1F-11D0-9888-006097DEACF9}": "IE Favorites",
    "{FA99DFC7-6AC2-453A-A5E2-5E2AFF4507BD}": "Deleted Files",
    "{5E6AB780-7743-11CF-A12B-00AA004AE837}": "Internet Toolbar",
    "{0D6D4F41-2994-4BA0-8FEF-620E43CD2812}": "Programs and Features",
}


@register_parser
class UserAssistParser(BaseParser):
    """Parser for Windows UserAssist registry entries."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="userassist",
            display_name="Windows UserAssist Parser",
            description="Parses Windows UserAssist for user program execution history",
            supported_extensions=[".DAT", ".dat", ""],
            mime_types=["application/octet-stream"],
            category="windows",
            priority=80,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse UserAssist entries from NTUSER.DAT registry hive."""
        if not DISSECT_AVAILABLE:
            logger.error("dissect.regf required for UserAssist parsing")
            return

        try:
            with open(file_path, "rb") as f:
                hive = RegistryHive(f)

            # Find UserAssist key
            try:
                ua_key = hive.open("Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\UserAssist")
            except Exception:
                logger.warning("UserAssist key not found in registry")
                return

            # Iterate through GUID subkeys
            for guid_key in ua_key.subkeys():
                guid = guid_key.name
                guid_desc = USERASSIST_GUIDS.get(guid, "Unknown")

                try:
                    count_key = guid_key.subkey("Count")
                except Exception:
                    continue

                for value in count_key.values():
                    try:
                        # Decode ROT13-encoded name
                        name = codecs.decode(value.name, "rot_13")
                        data = value.value

                        if isinstance(data, bytes) and len(data) >= 16:
                            entry = self._parse_userassist_data(name, data, guid, guid_desc)
                            if entry:
                                yield self._create_event(entry, case_id, evidence_id)
                    except Exception as e:
                        logger.debug(f"Failed to parse UserAssist value: {e}")

        except Exception as e:
            logger.error(f"Failed to parse UserAssist: {e}")
            raise

    def _parse_userassist_data(
        self,
        name: str,
        data: bytes,
        guid: str,
        guid_desc: str,
    ) -> dict[str, Any] | None:
        """Parse UserAssist binary data."""
        entry = {
            "name": name,
            "guid": guid,
            "guid_description": guid_desc,
        }

        try:
            if len(data) == 16:
                # Windows XP format
                entry["session_id"] = struct.unpack("<I", data[0:4])[0]
                entry["run_count"] = struct.unpack("<I", data[4:8])[0]
                filetime = struct.unpack("<Q", data[8:16])[0]
                entry["last_executed"] = self._filetime_to_datetime(filetime)

            elif len(data) == 72:
                # Windows Vista/7/8/10 format
                entry["session_id"] = struct.unpack("<I", data[0:4])[0]
                entry["run_count"] = struct.unpack("<I", data[4:8])[0]
                entry["focus_count"] = struct.unpack("<I", data[8:12])[0]
                entry["focus_time"] = struct.unpack("<I", data[12:16])[0]  # milliseconds
                filetime = struct.unpack("<Q", data[60:68])[0]
                entry["last_executed"] = self._filetime_to_datetime(filetime)

            else:
                # Unknown format, try to extract what we can
                if len(data) >= 8:
                    entry["run_count"] = struct.unpack("<I", data[4:8])[0]

        except Exception as e:
            logger.debug(f"Failed to parse UserAssist data: {e}")

        return entry if entry.get("name") else None

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from UserAssist entry."""
        name = entry.get("name", "unknown")
        last_exec = entry.get("last_executed")
        run_count = entry.get("run_count", 0)

        # Extract path from name (often has format like {GUID}\path)
        path = name
        if "}" in name and "\\" in name:
            path = name.split("}", 1)[-1].lstrip("\\")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=last_exec or datetime.now(UTC),
            message=f"UserAssist: {path} (executed {run_count} times)",
            source="userassist",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process"],
                    "type": ["start"],
                    "action": "user_program_execution",
                    "module": "userassist",
                    "dataset": "windows.userassist",
                },
                "process": {
                    "executable": path,
                    "name": Path(path).name if path else None,
                },
                "file": {
                    "path": path,
                    "name": Path(path).name if path else None,
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "userassist",
                    "artifact_type": "userassist",
                    "run_count": run_count,
                    "focus_count": entry.get("focus_count"),
                    "focus_time_ms": entry.get("focus_time"),
                    "session_id": entry.get("session_id"),
                    "guid": entry.get("guid"),
                    "guid_description": entry.get("guid_description"),
                    "raw_name": entry.get("name"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _filetime_to_datetime(self, filetime: int) -> datetime | None:
        """Convert Windows FILETIME to datetime."""
        try:
            if filetime == 0:
                return None
            epoch_diff = 116444736000000000
            timestamp = (filetime - epoch_diff) / 10000000
            if timestamp < 0 or timestamp > 4102444800:  # Before 1970 or after 2100
                return None
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except Exception:
            return None
