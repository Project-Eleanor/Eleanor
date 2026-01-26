"""Windows LNK (Shortcut) file parser.

LNK files contain metadata about target files, including:
- Target path and command line arguments
- Creation/modification/access timestamps
- Volume and drive information
- Machine ID and MAC address (NetBIOS)

Commonly found in: Recent, Desktop, Start Menu, Quick Launch
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

try:
    from dissect.shellitem import lnk
    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False


# LNK file signature
LNK_SIGNATURE = b"\x4c\x00\x00\x00"
LNK_GUID = b"\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46"


@register_parser
class LnkParser(BaseParser):
    """Parser for Windows LNK (shortcut) files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="lnk",
            display_name="Windows LNK (Shortcut) Parser",
            description="Parses Windows shortcut files for target and timestamp information",
            supported_extensions=[".lnk", ".LNK"],
            mime_types=["application/x-ms-shortcut"],
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
        """Parse LNK file."""
        if DISSECT_AVAILABLE:
            async for event in self._parse_with_dissect(file_path, case_id, evidence_id):
                yield event
        else:
            async for event in self._parse_manual(file_path, case_id, evidence_id):
                yield event

    async def _parse_with_dissect(
        self,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse LNK file using dissect library."""
        try:
            with open(file_path, "rb") as f:
                lnk_file = lnk.Lnk(f)

            entry = {
                "lnk_path": str(file_path),
                "target_path": str(lnk_file.target) if lnk_file.target else None,
                "arguments": lnk_file.arguments,
                "working_dir": lnk_file.working_dir,
                "icon_location": lnk_file.icon_location,
                "description": lnk_file.description,
                "creation_time": lnk_file.creation_time,
                "modification_time": lnk_file.modification_time,
                "access_time": lnk_file.access_time,
                "file_size": lnk_file.file_size,
                "file_attributes": lnk_file.file_attributes,
                "drive_type": lnk_file.drive_type,
                "volume_label": lnk_file.volume_label,
                "drive_serial": lnk_file.drive_serial,
                "machine_id": lnk_file.machine_id,
                "droid_volume_id": str(lnk_file.droid_volume_id) if lnk_file.droid_volume_id else None,
                "droid_file_id": str(lnk_file.droid_file_id) if lnk_file.droid_file_id else None,
            }

            yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse LNK with dissect: {e}")
            # Fall back to manual parsing
            async for event in self._parse_manual(file_path, case_id, evidence_id):
                yield event

    async def _parse_manual(
        self,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Manual LNK file parsing without dissect."""
        try:
            with open(file_path, "rb") as f:
                data = f.read()

            if len(data) < 76:
                return

            # Verify signature
            if data[0:4] != LNK_SIGNATURE:
                return

            entry = self._parse_lnk_header(data, file_path)
            if entry:
                yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse LNK manually: {e}")
            raise

    def _parse_lnk_header(self, data: bytes, file_path: Path) -> dict[str, Any] | None:
        """Parse LNK file header."""
        entry = {
            "lnk_path": str(file_path),
        }

        try:
            # Link flags at offset 20
            link_flags = struct.unpack("<I", data[20:24])[0]
            entry["has_target_id_list"] = bool(link_flags & 0x01)
            entry["has_link_info"] = bool(link_flags & 0x02)
            entry["has_name"] = bool(link_flags & 0x04)
            entry["has_relative_path"] = bool(link_flags & 0x08)
            entry["has_working_dir"] = bool(link_flags & 0x10)
            entry["has_arguments"] = bool(link_flags & 0x20)
            entry["has_icon_location"] = bool(link_flags & 0x40)

            # File attributes at offset 24
            file_attrs = struct.unpack("<I", data[24:28])[0]
            entry["file_attributes"] = file_attrs

            # Timestamps
            entry["creation_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[28:36])[0]
            )
            entry["access_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[36:44])[0]
            )
            entry["modification_time"] = self._filetime_to_datetime(
                struct.unpack("<Q", data[44:52])[0]
            )

            # File size at offset 52
            entry["file_size"] = struct.unpack("<I", data[52:56])[0]

            # Parse string data sections
            offset = 76

            # Skip target ID list if present
            if entry["has_target_id_list"] and offset + 2 <= len(data):
                id_list_size = struct.unpack("<H", data[offset:offset+2])[0]
                offset += 2 + id_list_size

            # Parse link info if present
            if entry["has_link_info"] and offset + 4 <= len(data):
                link_info_size = struct.unpack("<I", data[offset:offset+4])[0]
                if link_info_size > 0 and offset + link_info_size <= len(data):
                    link_info = data[offset:offset + link_info_size]
                    entry.update(self._parse_link_info(link_info))
                offset += link_info_size

            # Parse string data
            strings = ["name", "relative_path", "working_dir", "arguments", "icon_location"]
            for i, string_name in enumerate(strings):
                has_attr = f"has_{string_name}" if string_name != "name" else "has_name"
                if entry.get(has_attr) and offset + 2 <= len(data):
                    str_len = struct.unpack("<H", data[offset:offset+2])[0]
                    offset += 2
                    if str_len > 0 and offset + str_len * 2 <= len(data):
                        entry[string_name] = data[offset:offset + str_len * 2].decode(
                            "utf-16-le", errors="ignore"
                        )
                        offset += str_len * 2

        except Exception as e:
            logger.debug(f"Failed to parse LNK header: {e}")

        return entry

    def _parse_link_info(self, data: bytes) -> dict[str, Any]:
        """Parse LinkInfo structure."""
        info = {}

        try:
            if len(data) < 28:
                return info

            # LinkInfoFlags at offset 8
            flags = struct.unpack("<I", data[8:12])[0]
            has_volume_id = bool(flags & 0x01)
            has_common_path = bool(flags & 0x02)

            # Volume ID offset at offset 12
            vol_id_offset = struct.unpack("<I", data[12:16])[0]

            # Local base path offset at offset 16
            base_path_offset = struct.unpack("<I", data[16:20])[0]

            # Common path suffix offset at offset 24
            common_path_offset = struct.unpack("<I", data[24:28])[0]

            # Parse volume ID
            if has_volume_id and vol_id_offset > 0 and vol_id_offset + 16 <= len(data):
                vol_data = data[vol_id_offset:]
                if len(vol_data) >= 16:
                    info["drive_type"] = struct.unpack("<I", vol_data[4:8])[0]
                    info["drive_serial"] = struct.unpack("<I", vol_data[8:12])[0]
                    # Volume label offset
                    vol_label_offset = struct.unpack("<I", vol_data[12:16])[0]
                    if vol_label_offset > 0:
                        label_start = vol_label_offset
                        label_end = vol_data.find(b"\x00", label_start)
                        if label_end > label_start:
                            info["volume_label"] = vol_data[label_start:label_end].decode(
                                "ascii", errors="ignore"
                            )

            # Parse local base path
            if base_path_offset > 0 and base_path_offset < len(data):
                path_end = data.find(b"\x00", base_path_offset)
                if path_end > base_path_offset:
                    info["target_path"] = data[base_path_offset:path_end].decode(
                        "ascii", errors="ignore"
                    )

        except Exception as e:
            logger.debug(f"Failed to parse LinkInfo: {e}")

        return info

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from LNK entry."""
        target_path = entry.get("target_path") or entry.get("relative_path") or "unknown"
        lnk_path = entry.get("lnk_path", "unknown")
        modification_time = entry.get("modification_time") or datetime.now(timezone.utc)

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=modification_time,
            message=f"LNK: {Path(lnk_path).name} -> {target_path}",
            source="lnk",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["file"],
                    "type": ["info"],
                    "action": "shortcut_created",
                    "module": "lnk",
                    "dataset": "windows.lnk",
                },
                "file": {
                    "path": lnk_path,
                    "name": Path(lnk_path).name,
                    "created": entry.get("creation_time").isoformat() if entry.get("creation_time") else None,
                    "accessed": entry.get("access_time").isoformat() if entry.get("access_time") else None,
                    "mtime": modification_time.isoformat() if modification_time else None,
                    "target_path": target_path,
                },
                "process": {
                    "executable": target_path,
                    "args": entry.get("arguments").split() if entry.get("arguments") else None,
                    "working_directory": entry.get("working_dir"),
                } if target_path else None,
                "host": {
                    "os": {"type": "windows"},
                    "name": entry.get("machine_id"),
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "lnk",
                    "artifact_type": "shortcut",
                    "arguments": entry.get("arguments"),
                    "working_dir": entry.get("working_dir"),
                    "icon_location": entry.get("icon_location"),
                    "description": entry.get("description"),
                    "drive_type": entry.get("drive_type"),
                    "volume_label": entry.get("volume_label"),
                    "drive_serial": entry.get("drive_serial"),
                    "machine_id": entry.get("machine_id"),
                    "droid_volume_id": entry.get("droid_volume_id"),
                    "droid_file_id": entry.get("droid_file_id"),
                    "target_file_size": entry.get("file_size"),
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
