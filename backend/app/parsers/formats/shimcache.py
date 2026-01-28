"""Windows Shimcache (Application Compatibility Cache) parser.

Shimcache tracks program execution for application compatibility purposes.
It's a key artifact for determining what programs have been executed on a system.

Location: SYSTEM registry hive
Key: HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\AppCompatCache
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

try:
    from dissect.target import Target
    from dissect.target.filesystem import VirtualFilesystem

    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False
    logger.warning("dissect.target not available, ShimcacheParser will be limited")


@register_parser
class ShimcacheParser(BaseParser):
    """Parser for Windows Shimcache (AppCompatCache) from registry."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="shimcache",
            display_name="Windows Shimcache Parser",
            description="Parses Windows Application Compatibility Cache for program execution evidence",
            supported_extensions=[".reg", ".SYSTEM", ""],
            mime_types=["application/octet-stream"],
            category="windows",
            priority=85,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Shimcache entries from SYSTEM registry hive."""
        if not DISSECT_AVAILABLE:
            logger.error("dissect.target required for Shimcache parsing")
            return

        try:
            from dissect.regf import RegistryHive
            from dissect.target.plugins.os.windows.regf.shimcache import ShimcachePlugin
        except ImportError:
            logger.error("dissect.regf required for Shimcache parsing")
            return

        try:
            # Open registry hive
            with open(file_path, "rb") as f:
                hive = RegistryHive(f)

            # Find AppCompatCache key
            try:
                key = hive.open("ControlSet001\\Control\\Session Manager\\AppCompatCache")
            except Exception:
                try:
                    key = hive.open("CurrentControlSet\\Control\\Session Manager\\AppCompatCache")
                except Exception:
                    logger.warning("AppCompatCache key not found in registry")
                    return

            # Get AppCompatCache value
            try:
                value = key.value("AppCompatCache")
                data = value.value
            except Exception:
                logger.warning("AppCompatCache value not found")
                return

            # Parse shimcache data
            entries = self._parse_shimcache_data(data)

            for idx, entry in enumerate(entries):
                yield ParsedEvent(
                    id=str(uuid4()),
                    timestamp=entry.get("last_modified", datetime.now(UTC)),
                    message=f"Shimcache: {entry.get('path', 'unknown')}",
                    source="shimcache",
                    raw_data=entry,
                    normalized={
                        "event": {
                            "kind": "event",
                            "category": ["process"],
                            "type": ["info"],
                            "action": "shimcache_entry",
                            "module": "shimcache",
                            "dataset": "windows.shimcache",
                        },
                        "file": {
                            "path": entry.get("path"),
                            "name": Path(entry.get("path", "")).name if entry.get("path") else None,
                        },
                        "process": {
                            "executable": entry.get("path"),
                        },
                        "host": {
                            "os": {"type": "windows"},
                        },
                        "eleanor": {
                            "case_id": case_id,
                            "evidence_id": evidence_id,
                            "parser": "shimcache",
                            "artifact_type": "shimcache",
                            "entry_index": idx,
                            "executed": entry.get("executed"),
                            "file_size": entry.get("size"),
                        },
                    },
                    case_id=case_id,
                    evidence_id=evidence_id,
                )

        except Exception as e:
            logger.error(f"Failed to parse Shimcache: {e}")
            raise

    def _parse_shimcache_data(self, data: bytes) -> list[dict[str, Any]]:
        """Parse raw shimcache data based on Windows version."""
        entries = []

        if len(data) < 4:
            return entries

        # Detect format based on header
        header = int.from_bytes(data[:4], "little")

        try:
            if header == 0xDEADBEEF:
                # Windows XP format
                entries = self._parse_xp_format(data)
            elif header in (0xBADC0FEE, 0xBADC0FFE):
                # Windows Vista/7 format
                entries = self._parse_vista7_format(data)
            elif header == 0x00000080 or header == 0x00000030:
                # Windows 8/8.1/10 format
                entries = self._parse_win8plus_format(data)
            else:
                # Try Windows 10 format
                entries = self._parse_win10_format(data)
        except Exception as e:
            logger.warning(f"Failed to parse shimcache format: {e}")

        return entries

    def _parse_xp_format(self, data: bytes) -> list[dict[str, Any]]:
        """Parse Windows XP shimcache format."""
        entries = []
        offset = 8  # Skip header

        try:
            num_entries = int.from_bytes(data[4:8], "little")

            for _ in range(min(num_entries, 1000)):
                if offset + 552 > len(data):
                    break

                path = (
                    data[offset : offset + 520].decode("utf-16-le", errors="ignore").rstrip("\x00")
                )
                last_mod = self._filetime_to_datetime(data[offset + 528 : offset + 536])
                size = int.from_bytes(data[offset + 536 : offset + 544], "little")

                entries.append(
                    {
                        "path": path,
                        "last_modified": last_mod,
                        "size": size,
                        "executed": None,
                    }
                )
                offset += 552

        except Exception as e:
            logger.debug(f"XP format parse error: {e}")

        return entries

    def _parse_vista7_format(self, data: bytes) -> list[dict[str, Any]]:
        """Parse Windows Vista/7 shimcache format."""
        entries = []
        offset = 128  # Skip header

        try:
            while offset + 32 < len(data):
                path_len = int.from_bytes(data[offset : offset + 2], "little")
                if path_len == 0 or path_len > 520:
                    break

                path_offset = offset + 16
                path = data[path_offset : path_offset + path_len].decode(
                    "utf-16-le", errors="ignore"
                )

                time_offset = path_offset + path_len
                if time_offset + 8 <= len(data):
                    last_mod = self._filetime_to_datetime(data[time_offset : time_offset + 8])
                else:
                    last_mod = None

                entries.append(
                    {
                        "path": path,
                        "last_modified": last_mod,
                        "size": None,
                        "executed": None,
                    }
                )

                # Move to next entry
                offset = time_offset + 16
                if offset >= len(data):
                    break

        except Exception as e:
            logger.debug(f"Vista/7 format parse error: {e}")

        return entries

    def _parse_win8plus_format(self, data: bytes) -> list[dict[str, Any]]:
        """Parse Windows 8/8.1/10 shimcache format."""
        entries = []
        offset = int.from_bytes(data[:4], "little")

        try:
            while offset + 12 < len(data):
                sig = data[offset : offset + 4]
                if sig != b"10ts":
                    break

                entry_size = int.from_bytes(data[offset + 8 : offset + 12], "little")
                path_size = int.from_bytes(data[offset + 12 : offset + 14], "little")

                if path_size > 0 and offset + 16 + path_size <= len(data):
                    path = data[offset + 16 : offset + 16 + path_size].decode(
                        "utf-16-le", errors="ignore"
                    )

                    time_offset = offset + 16 + path_size
                    if time_offset + 8 <= len(data):
                        last_mod = self._filetime_to_datetime(data[time_offset : time_offset + 8])
                    else:
                        last_mod = None

                    entries.append(
                        {
                            "path": path,
                            "last_modified": last_mod,
                            "size": None,
                            "executed": None,
                        }
                    )

                offset += entry_size
                if entry_size == 0:
                    break

        except Exception as e:
            logger.debug(f"Win8+ format parse error: {e}")

        return entries

    def _parse_win10_format(self, data: bytes) -> list[dict[str, Any]]:
        """Parse Windows 10 shimcache format."""
        # Similar to win8+ but with variations
        return self._parse_win8plus_format(data)

    def _filetime_to_datetime(self, data: bytes) -> datetime | None:
        """Convert Windows FILETIME to datetime."""
        try:
            filetime = int.from_bytes(data, "little")
            if filetime == 0:
                return None
            # FILETIME is 100-nanosecond intervals since 1601-01-01
            epoch_diff = 116444736000000000
            timestamp = (filetime - epoch_diff) / 10000000
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except Exception:
            return None
