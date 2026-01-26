"""NTFS Master File Table (MFT) parser using Dissect.

Parses NTFS MFT files to extract filesystem metadata for timeline analysis.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from app.parsers.base import ParsedEvent, ParserCategory
from app.parsers.formats.dissect_adapter import DissectParserAdapter
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# MFT entry signature
MFT_SIGNATURE = b"FILE"


@register_parser
class NTFSMftParser(DissectParserAdapter):
    """Parser for NTFS Master File Table files."""

    @property
    def name(self) -> str:
        return "ntfs_mft"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.DISK

    @property
    def description(self) -> str:
        return "NTFS Master File Table ($MFT) filesystem timeline parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".$MFT", ".mft", ".MFT"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for MFT signature."""
        if content and len(content) >= 4:
            return content[:4] == MFT_SIGNATURE

        if file_path:
            name = file_path.name.upper()
            if name in ("$MFT", "MFT"):
                return True
            if file_path.suffix.lower() in (".mft", ".$mft"):
                return True

        return False

    def _get_dissect_parser(self, source: Path | BinaryIO) -> Any:
        """Get Dissect MFT parser."""
        from dissect.ntfs import mft

        if isinstance(source, Path):
            return mft.MftParser(open(source, "rb"))
        return mft.MftParser(source)

    def _iterate_records(self, parser: Any) -> Iterator[Any]:
        """Iterate over MFT records."""
        try:
            for record in parser.records():
                if record and record.header.flags & 0x01:  # IN_USE flag
                    yield record
        except Exception as e:
            logger.error(f"Error iterating MFT records: {e}")

    def _parse_record(self, record: Any, source_name: str) -> ParsedEvent | None:
        """Convert an MFT record to ParsedEvent."""
        try:
            # Get filename
            filename = ""
            file_path_full = ""
            if hasattr(record, "filename") and record.filename:
                fn_attr = record.filename
                filename = fn_attr.name if hasattr(fn_attr, "name") else str(fn_attr)
            elif hasattr(record, "get_full_path"):
                file_path_full = record.get_full_path()
                filename = Path(file_path_full).name if file_path_full else ""

            # Skip system files for cleaner output
            if filename.startswith("$") and len(filename) > 1:
                return None

            # Get record number
            record_num = record.segment if hasattr(record, "segment") else 0

            # Get timestamps from $STANDARD_INFORMATION
            si_created = None
            si_modified = None
            si_accessed = None
            si_entry_modified = None

            if hasattr(record, "standard_information") and record.standard_information:
                si = record.standard_information
                if hasattr(si, "creation_time"):
                    si_created = self._to_datetime(si.creation_time)
                if hasattr(si, "modification_time"):
                    si_modified = self._to_datetime(si.modification_time)
                if hasattr(si, "access_time"):
                    si_accessed = self._to_datetime(si.access_time)
                if hasattr(si, "mft_modification_time"):
                    si_entry_modified = self._to_datetime(si.mft_modification_time)

            # Get timestamps from $FILE_NAME (can differ from SI for timestomping detection)
            fn_created = None
            fn_modified = None
            fn_accessed = None

            if hasattr(record, "filename") and record.filename:
                fn = record.filename
                if hasattr(fn, "creation_time"):
                    fn_created = self._to_datetime(fn.creation_time)
                if hasattr(fn, "modification_time"):
                    fn_modified = self._to_datetime(fn.modification_time)
                if hasattr(fn, "access_time"):
                    fn_accessed = self._to_datetime(fn.access_time)

            # Use most relevant timestamp (modification time)
            timestamp = si_modified or fn_modified or datetime.now(timezone.utc)

            # Determine if it's a file or directory
            is_directory = False
            if hasattr(record, "header"):
                is_directory = bool(record.header.flags & 0x02)  # DIRECTORY flag

            # Get file size
            file_size = None
            if hasattr(record, "data") and record.data:
                data_attr = record.data
                if hasattr(data_attr, "size"):
                    file_size = data_attr.size
                elif hasattr(data_attr, "data_size"):
                    file_size = data_attr.data_size

            # Build message
            item_type = "Directory" if is_directory else "File"
            message = f"MFT entry: {item_type} '{filename}'"
            if file_size:
                message += f" ({file_size} bytes)"

            # Check for timestomping indicators
            timestomping_indicator = False
            if si_created and fn_created:
                diff = abs((si_created - fn_created).total_seconds())
                if diff > 1:  # More than 1 second difference
                    timestomping_indicator = True

            # Build raw data
            raw = {
                "record_number": record_num,
                "filename": filename,
                "full_path": file_path_full,
                "is_directory": is_directory,
                "file_size": file_size,
                "timestamps": {
                    "si_created": str(si_created) if si_created else None,
                    "si_modified": str(si_modified) if si_modified else None,
                    "si_accessed": str(si_accessed) if si_accessed else None,
                    "si_entry_modified": str(si_entry_modified) if si_entry_modified else None,
                    "fn_created": str(fn_created) if fn_created else None,
                    "fn_modified": str(fn_modified) if fn_modified else None,
                    "fn_accessed": str(fn_accessed) if fn_accessed else None,
                },
            }

            if timestomping_indicator:
                raw["timestomping_indicator"] = True

            # Determine event category and type
            ecs_categories = ["file"]
            ecs_types = ["info"]

            if is_directory:
                ecs_types = ["info"]
            else:
                ecs_types = ["info"]

            tags = ["filesystem", "ntfs_mft"]
            if timestomping_indicator:
                tags.append("timestomping_indicator")

            return ParsedEvent(
                timestamp=timestamp,
                message=message,
                source_type="ntfs_mft",
                source_file=source_name,
                source_line=record_num,
                event_kind="event",
                event_category=ecs_categories,
                event_type=ecs_types,
                event_action="file_metadata",
                file_name=filename,
                file_path=file_path_full or None,
                raw=raw,
                labels={
                    "mft_record": str(record_num),
                    "is_directory": str(is_directory).lower(),
                },
                tags=tags,
            )

        except Exception as e:
            logger.debug(f"Failed to parse MFT record: {e}")
            return None
