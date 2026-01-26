"""NTFS USN Journal parser using Dissect.

Parses NTFS USN Journal ($UsnJrnl:$J) to extract filesystem change records.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# USN reason flags
USN_REASONS = {
    0x00000001: "DATA_OVERWRITE",
    0x00000002: "DATA_EXTEND",
    0x00000004: "DATA_TRUNCATION",
    0x00000010: "NAMED_DATA_OVERWRITE",
    0x00000020: "NAMED_DATA_EXTEND",
    0x00000040: "NAMED_DATA_TRUNCATION",
    0x00000100: "FILE_CREATE",
    0x00000200: "FILE_DELETE",
    0x00000400: "EA_CHANGE",
    0x00000800: "SECURITY_CHANGE",
    0x00001000: "RENAME_OLD_NAME",
    0x00002000: "RENAME_NEW_NAME",
    0x00004000: "INDEXABLE_CHANGE",
    0x00008000: "BASIC_INFO_CHANGE",
    0x00010000: "HARD_LINK_CHANGE",
    0x00020000: "COMPRESSION_CHANGE",
    0x00040000: "ENCRYPTION_CHANGE",
    0x00080000: "OBJECT_ID_CHANGE",
    0x00100000: "REPARSE_POINT_CHANGE",
    0x00200000: "STREAM_CHANGE",
    0x00400000: "TRANSACTED_CHANGE",
    0x00800000: "INTEGRITY_CHANGE",
    0x80000000: "CLOSE",
}


@register_parser
class UsnJournalParser(BaseParser):
    """Parser for NTFS USN Journal files."""

    @property
    def name(self) -> str:
        return "usn_journal"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.DISK

    @property
    def description(self) -> str:
        return "NTFS USN Journal ($UsnJrnl:$J) filesystem change parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".$J", ".usn", ".usnjournal"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for USN Journal patterns."""
        if file_path:
            name = file_path.name.upper()
            if name in ("$J", "$USNJRNL", "USNJRNL"):
                return True
            if "$USNJRNL" in str(file_path).upper():
                return True

        # USN records have a specific structure but no magic bytes
        # Try to detect based on record structure
        if content and len(content) >= 60:
            # Check for valid record length (should be reasonable)
            try:
                record_len = int.from_bytes(content[0:4], "little")
                if 60 <= record_len <= 600:
                    return True
            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse USN Journal and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            # Try dissect.ntfs first
            try:
                from dissect.ntfs import usn

                if isinstance(source, Path):
                    with open(source, "rb") as f:
                        yield from self._parse_with_dissect(usn, f, source_str)
                else:
                    yield from self._parse_with_dissect(usn, source, source_str)
                return

            except ImportError:
                logger.info("dissect.ntfs not available, using manual parsing")

            # Fall back to manual parsing
            if isinstance(source, Path):
                with open(source, "rb") as f:
                    yield from self._parse_manual(f, source_str)
            else:
                yield from self._parse_manual(source, source_str)

        except Exception as e:
            logger.error(f"Failed to parse USN Journal {source_str}: {e}")
            raise

    def _parse_with_dissect(self, usn_module, fh: BinaryIO, source_name: str) -> Iterator[ParsedEvent]:
        """Parse using dissect.ntfs.usn module."""
        for record in usn_module.UsnParser(fh):
            try:
                event = self._record_to_event(record, source_name)
                if event:
                    yield event
            except Exception as e:
                logger.debug(f"Failed to parse USN record: {e}")

    def _parse_manual(self, fh: BinaryIO, source_name: str) -> Iterator[ParsedEvent]:
        """Manual parsing of USN records."""
        record_num = 0

        while True:
            # Read record length
            length_bytes = fh.read(4)
            if len(length_bytes) < 4:
                break

            record_len = int.from_bytes(length_bytes, "little")

            # Skip empty/invalid records
            if record_len < 60 or record_len > 600:
                # Try to find next valid record
                fh.read(4)  # Skip 4 bytes
                continue

            # Read rest of record
            record_data = length_bytes + fh.read(record_len - 4)
            if len(record_data) < record_len:
                break

            try:
                record_num += 1
                event = self._parse_usn_record(record_data, source_name, record_num)
                if event:
                    yield event
            except Exception as e:
                logger.debug(f"Failed to parse USN record {record_num}: {e}")

    def _parse_usn_record(self, data: bytes, source_name: str, record_num: int) -> ParsedEvent | None:
        """Parse a single USN v2/v3 record."""
        if len(data) < 60:
            return None

        # USN_RECORD_V2 structure
        # 0x00: RecordLength (4)
        # 0x04: MajorVersion (2)
        # 0x06: MinorVersion (2)
        # 0x08: FileReferenceNumber (8)
        # 0x10: ParentFileReferenceNumber (8)
        # 0x18: Usn (8)
        # 0x20: TimeStamp (8) - FILETIME
        # 0x28: Reason (4)
        # 0x2C: SourceInfo (4)
        # 0x30: SecurityId (4)
        # 0x34: FileAttributes (4)
        # 0x38: FileNameLength (2)
        # 0x3A: FileNameOffset (2)
        # 0x3C: FileName (variable)

        major_version = int.from_bytes(data[4:6], "little")
        minor_version = int.from_bytes(data[6:8], "little")

        if major_version not in (2, 3):
            return None

        # Parse timestamp (Windows FILETIME)
        filetime = int.from_bytes(data[0x20:0x28], "little")
        timestamp = self._filetime_to_datetime(filetime)

        # Parse reason flags
        reason = int.from_bytes(data[0x28:0x2C], "little")
        reason_strs = self._decode_reason(reason)

        # Parse file attributes
        attributes = int.from_bytes(data[0x34:0x38], "little")
        is_directory = bool(attributes & 0x10)

        # Parse filename
        filename_length = int.from_bytes(data[0x38:0x3A], "little")
        filename_offset = int.from_bytes(data[0x3A:0x3C], "little")

        if filename_offset + filename_length > len(data):
            return None

        try:
            filename = data[filename_offset:filename_offset + filename_length].decode("utf-16-le")
        except Exception:
            filename = "Unknown"

        # Build message
        action = ", ".join(reason_strs[:3])  # Limit to 3 reasons for message
        item_type = "Directory" if is_directory else "File"
        message = f"USN {item_type}: {filename} ({action})"

        # Determine event type based on reason
        ecs_types = ["info"]
        event_action = "file_change"

        if reason & 0x00000100:  # FILE_CREATE
            ecs_types = ["creation"]
            event_action = "file_created"
        elif reason & 0x00000200:  # FILE_DELETE
            ecs_types = ["deletion"]
            event_action = "file_deleted"
        elif reason & 0x00001000 or reason & 0x00002000:  # RENAME
            ecs_types = ["change"]
            event_action = "file_renamed"
        elif reason & 0x00000001 or reason & 0x00000002:  # DATA_OVERWRITE/EXTEND
            ecs_types = ["change"]
            event_action = "file_modified"

        raw = {
            "record_number": record_num,
            "usn": int.from_bytes(data[0x18:0x20], "little"),
            "reason_flags": reason,
            "reasons": reason_strs,
            "file_attributes": attributes,
            "is_directory": is_directory,
            "version": f"{major_version}.{minor_version}",
        }

        return ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="usn_journal",
            source_file=source_name,
            source_line=record_num,
            event_kind="event",
            event_category=["file"],
            event_type=ecs_types,
            event_action=event_action,
            file_name=filename,
            raw=raw,
            labels={
                "is_directory": str(is_directory).lower(),
            },
            tags=["filesystem", "usn_journal"],
        )

    def _record_to_event(self, record: Any, source_name: str) -> ParsedEvent | None:
        """Convert a dissect USN record to ParsedEvent."""
        try:
            filename = record.filename if hasattr(record, "filename") else str(record)
            timestamp = self._filetime_to_datetime(record.timestamp.value) if hasattr(record, "timestamp") else datetime.now(timezone.utc)
            reason = record.reason if hasattr(record, "reason") else 0
            attributes = record.file_attributes if hasattr(record, "file_attributes") else 0

            reason_strs = self._decode_reason(reason)
            is_directory = bool(attributes & 0x10)

            action = ", ".join(reason_strs[:3])
            item_type = "Directory" if is_directory else "File"
            message = f"USN {item_type}: {filename} ({action})"

            # Determine event type
            ecs_types = ["info"]
            event_action = "file_change"

            if reason & 0x00000100:
                ecs_types = ["creation"]
                event_action = "file_created"
            elif reason & 0x00000200:
                ecs_types = ["deletion"]
                event_action = "file_deleted"
            elif reason & 0x00001000 or reason & 0x00002000:
                ecs_types = ["change"]
                event_action = "file_renamed"

            raw = {
                "usn": record.usn if hasattr(record, "usn") else 0,
                "reason_flags": reason,
                "reasons": reason_strs,
                "is_directory": is_directory,
            }

            return ParsedEvent(
                timestamp=timestamp,
                message=message,
                source_type="usn_journal",
                source_file=source_name,
                event_kind="event",
                event_category=["file"],
                event_type=ecs_types,
                event_action=event_action,
                file_name=filename,
                raw=raw,
                tags=["filesystem", "usn_journal"],
            )

        except Exception as e:
            logger.debug(f"Failed to convert USN record: {e}")
            return None

    def _filetime_to_datetime(self, filetime: int) -> datetime:
        """Convert Windows FILETIME to datetime."""
        if not filetime:
            return datetime.now(timezone.utc)

        try:
            # FILETIME is 100-nanosecond intervals since Jan 1, 1601
            unix_ts = (filetime - 116444736000000000) / 10000000
            return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return datetime.now(timezone.utc)

    def _decode_reason(self, reason: int) -> list[str]:
        """Decode USN reason flags to human-readable strings."""
        reasons = []
        for flag, name in USN_REASONS.items():
            if reason & flag:
                reasons.append(name)
        return reasons if reasons else ["UNKNOWN"]
