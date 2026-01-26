"""Windows Recycle Bin parser.

Parses $I and $R files from the Windows Recycle Bin ($Recycle.Bin).
- $I files contain metadata (original path, deletion time, size)
- $R files contain the actual deleted file content

Location: C:\$Recycle.Bin\<SID>\
"""

import logging
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser
class RecycleBinParser(BaseParser):
    """Parser for Windows Recycle Bin $I metadata files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="recyclebin",
            display_name="Windows Recycle Bin Parser",
            description="Parses Windows Recycle Bin $I files for deleted file metadata",
            supported_extensions=[""],  # $I files have no extension
            mime_types=["application/octet-stream"],
            category="windows",
            priority=75,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Recycle Bin $I file."""
        # Check if this is a $I file
        if not file_path.name.startswith("$I"):
            logger.debug(f"Not a $I file: {file_path}")
            return

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            entry = self._parse_i_file(data, file_path)
            if entry:
                yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse Recycle Bin file: {e}")
            raise

    def _parse_i_file(self, data: bytes, file_path: Path) -> dict[str, Any] | None:
        """Parse $I file format."""
        if len(data) < 28:
            return None

        entry = {
            "i_file_path": str(file_path),
            "r_file_name": "$R" + file_path.name[2:],  # Corresponding $R file
        }

        try:
            # Parse header
            header = struct.unpack("<Q", data[0:8])[0]

            if header == 1:
                # Windows Vista/7 format
                entry["format"] = "vista"
                entry["file_size"] = struct.unpack("<Q", data[8:16])[0]
                entry["deleted_time"] = self._filetime_to_datetime(
                    struct.unpack("<Q", data[16:24])[0]
                )
                # Path is variable length, starts at offset 24
                path_len = struct.unpack("<I", data[24:28])[0]
                if len(data) >= 28 + path_len * 2:
                    entry["original_path"] = data[28:28 + path_len * 2].decode(
                        "utf-16-le", errors="ignore"
                    ).rstrip("\x00")

            elif header == 2:
                # Windows 10 format
                entry["format"] = "win10"
                entry["file_size"] = struct.unpack("<Q", data[8:16])[0]
                entry["deleted_time"] = self._filetime_to_datetime(
                    struct.unpack("<Q", data[16:24])[0]
                )
                # Path length at offset 24
                path_len = struct.unpack("<I", data[24:28])[0]
                if len(data) >= 28 + path_len * 2:
                    entry["original_path"] = data[28:28 + path_len * 2].decode(
                        "utf-16-le", errors="ignore"
                    ).rstrip("\x00")

            else:
                # Try legacy format (pre-Vista)
                entry["format"] = "legacy"
                entry["file_size"] = struct.unpack("<Q", data[0:8])[0]
                entry["deleted_time"] = self._filetime_to_datetime(
                    struct.unpack("<Q", data[8:16])[0]
                )
                # Path at offset 16, fixed 520 bytes
                if len(data) >= 536:
                    entry["original_path"] = data[16:536].decode(
                        "utf-16-le", errors="ignore"
                    ).rstrip("\x00")

            # Extract SID from parent directory
            parent = file_path.parent.name
            if parent.startswith("S-1-"):
                entry["user_sid"] = parent

        except Exception as e:
            logger.debug(f"Failed to parse $I file: {e}")
            return None

        return entry if entry.get("original_path") else None

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Recycle Bin entry."""
        original_path = entry.get("original_path", "unknown")
        deleted_time = entry.get("deleted_time") or datetime.now(timezone.utc)
        file_size = entry.get("file_size", 0)

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=deleted_time,
            message=f"Deleted: {original_path} ({file_size} bytes)",
            source="recyclebin",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["file"],
                    "type": ["deletion"],
                    "action": "file_deleted",
                    "module": "recyclebin",
                    "dataset": "windows.recyclebin",
                },
                "file": {
                    "path": original_path,
                    "name": Path(original_path).name if original_path else None,
                    "size": file_size,
                    "directory": str(Path(original_path).parent) if original_path else None,
                },
                "user": {
                    "id": entry.get("user_sid"),
                } if entry.get("user_sid") else None,
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "recyclebin",
                    "artifact_type": "deleted_file",
                    "i_file_path": entry.get("i_file_path"),
                    "r_file_name": entry.get("r_file_name"),
                    "format": entry.get("format"),
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
            if timestamp < 0 or timestamp > 4102444800:
                return None
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except Exception:
            return None
