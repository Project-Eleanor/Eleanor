"""Windows Prefetch file parser using Dissect.

Parses Windows Prefetch files (.pf) which contain evidence of program execution.
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

# Prefetch magic bytes
PREFETCH_MAGIC_V17 = b"\x11\x00\x00\x00SCCA"  # Windows XP
PREFETCH_MAGIC_V23 = b"\x17\x00\x00\x00SCCA"  # Windows Vista/7
PREFETCH_MAGIC_V26 = b"\x1a\x00\x00\x00SCCA"  # Windows 8
PREFETCH_MAGIC_V30 = b"\x1e\x00\x00\x00SCCA"  # Windows 10 (compressed)
MAM_MAGIC = b"MAM\x04"  # Windows 10 compressed header


@register_parser
class WindowsPrefetchParser(DissectParserAdapter):
    """Parser for Windows Prefetch files."""

    @property
    def name(self) -> str:
        return "windows_prefetch"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Windows Prefetch (.pf) program execution evidence parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".pf"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-ms-prefetch"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for Prefetch magic bytes."""
        if content:
            # Check for compressed prefetch (MAM) - only needs 4 bytes
            if len(content) >= 4 and content[:4] == MAM_MAGIC:
                return True
            # Check for various prefetch versions (SCCA magic at offset 4)
            if len(content) >= 8 and content[4:8] == b"SCCA":
                return True

        if file_path:
            if file_path.suffix.lower() == ".pf":
                return True

        return False

    def _get_dissect_parser(self, source: Path | BinaryIO) -> Any:
        """Get Dissect prefetch parser."""
        from dissect.target.plugins.os.windows.prefetch import Prefetch

        if isinstance(source, Path):
            return Prefetch.from_file(source)
        # For file-like objects, we need to save to temp
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pf", delete=False) as tmp:
            tmp.write(source.read())
            tmp_path = tmp.name
        try:
            return Prefetch.from_file(Path(tmp_path))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _iterate_records(self, parser: Any) -> Iterator[Any]:
        """Yield the prefetch parser itself as a single record."""
        # Prefetch files are single records
        yield parser

    def _parse_record(self, record: Any, source_name: str) -> ParsedEvent | None:
        """Convert a prefetch record to ParsedEvent."""
        try:
            # Extract executable name
            executable_name = ""
            if hasattr(record, "executable_name"):
                executable_name = record.executable_name
            elif hasattr(record, "name"):
                executable_name = record.name

            # Get run count
            run_count = 0
            if hasattr(record, "run_count"):
                run_count = record.run_count

            # Get last run times (Windows 8+ stores up to 8)
            last_run_times = []
            if hasattr(record, "last_run_times"):
                last_run_times = list(record.last_run_times)
            elif hasattr(record, "last_run_time"):
                last_run_times = [record.last_run_time]

            # Use the most recent run time as the event timestamp
            if last_run_times and last_run_times[0]:
                timestamp = self._to_datetime(last_run_times[0])
            else:
                timestamp = datetime.now(UTC)

            # Get file references (loaded files/directories)
            file_references = []
            file_reference_count = 0
            if hasattr(record, "filenames"):
                all_refs = list(record.filenames)
                file_reference_count = len(all_refs)
                file_references = all_refs[:50]  # Limit to 50 for output
            elif hasattr(record, "files"):
                all_refs = list(record.files)
                file_reference_count = len(all_refs)
                file_references = all_refs[:50]

            # Get volume info
            volumes = []
            if hasattr(record, "volumes"):
                for vol in record.volumes:
                    vol_info = {}
                    if hasattr(vol, "device_path"):
                        vol_info["device_path"] = str(vol.device_path)
                    if hasattr(vol, "serial_number"):
                        vol_info["serial_number"] = (
                            hex(vol.serial_number) if vol.serial_number else None
                        )
                    volumes.append(vol_info)

            # Build message
            message = f"Program executed: {executable_name} (run count: {run_count})"

            # Extract directory and name from executable
            dir_path, file_name = self._extract_path_parts(executable_name)

            # Build raw data
            raw = {
                "executable_name": executable_name,
                "run_count": run_count,
                "last_run_times": [str(t) for t in last_run_times if t],
                "file_reference_count": file_reference_count,
                "prefetch_hash": (
                    hex(record.prefetch_hash) if hasattr(record, "prefetch_hash") else None
                ),
            }
            if file_references:
                raw["file_references"] = file_references[:20]  # Limit in raw data
            if volumes:
                raw["volumes"] = volumes

            return ParsedEvent(
                timestamp=timestamp,
                message=message,
                source_type="windows_prefetch",
                source_file=source_name,
                event_kind="event",
                event_category=["process"],
                event_type=["start", "info"],
                event_action="process_executed",
                process_name=file_name,
                process_executable=executable_name,
                raw=raw,
                labels={
                    "run_count": str(run_count),
                    "execution_evidence": "prefetch",
                },
                tags=["execution_evidence", "windows_prefetch"],
            )

        except Exception as e:
            logger.debug(f"Failed to parse prefetch record: {e}")
            return None

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse prefetch file and yield events.

        For prefetch files with multiple run times (Windows 8+),
        yields an event for each run time.
        """
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            # Try using dissect.target prefetch
            try:
                from dissect.target.plugins.os.windows.prefetch import Prefetch

                if isinstance(source, Path):
                    pf = Prefetch.from_file(source)
                else:
                    import tempfile

                    with tempfile.NamedTemporaryFile(suffix=".pf", delete=False) as tmp:
                        tmp.write(source.read())
                        tmp_path = tmp.name
                    try:
                        pf = Prefetch.from_file(Path(tmp_path))
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

                # Parse main record
                event = self._parse_record(pf, source_str)
                if event:
                    yield event

            except ImportError:
                # Fallback to manual parsing if dissect.target not available
                logger.warning("dissect.target not available, using basic prefetch parsing")
                yield from self._basic_parse(source, source_str)

        except Exception as e:
            logger.error(f"Failed to parse prefetch {source_str}: {e}")
            raise

    def _basic_parse(self, source: Path | BinaryIO, source_name: str) -> Iterator[ParsedEvent]:
        """Basic prefetch parsing without full dissect.target."""
        try:
            from dissect.util.compression import lzxpress_huffman

            if isinstance(source, Path):
                with open(source, "rb") as f:
                    data = f.read()
            else:
                data = source.read()

            # Check for compressed prefetch (Windows 10)
            if data[:4] == MAM_MAGIC:
                # Decompress
                uncompressed_size = int.from_bytes(data[4:8], "little")
                compressed_data = data[8:]
                data = lzxpress_huffman.decompress(compressed_data, uncompressed_size)

            # Parse header
            if len(data) < 84:
                return

            # Version
            version = int.from_bytes(data[0:4], "little")

            # Executable name (offset 16, 60 chars max, UTF-16)
            name_bytes = data[16:76]
            try:
                executable_name = name_bytes.decode("utf-16-le").rstrip("\x00")
            except Exception:
                executable_name = "Unknown"

            # Run count (offset depends on version)
            if version == 23:  # Vista/7
                run_count = int.from_bytes(data[152:156], "little")
            elif version == 26:  # Windows 8
                run_count = int.from_bytes(data[208:212], "little")
            elif version == 30:  # Windows 10
                run_count = int.from_bytes(data[208:212], "little")
            else:
                run_count = 0

            message = f"Program executed: {executable_name} (run count: {run_count})"
            dir_path, file_name = self._extract_path_parts(executable_name)

            yield ParsedEvent(
                timestamp=datetime.now(UTC),
                message=message,
                source_type="windows_prefetch",
                source_file=source_name,
                event_kind="event",
                event_category=["process"],
                event_type=["start", "info"],
                event_action="process_executed",
                process_name=file_name,
                process_executable=executable_name,
                raw={
                    "executable_name": executable_name,
                    "run_count": run_count,
                    "version": version,
                },
                labels={
                    "run_count": str(run_count),
                    "execution_evidence": "prefetch",
                },
                tags=["execution_evidence", "windows_prefetch"],
            )

        except ImportError:
            logger.error("dissect.util not available for prefetch parsing")
        except Exception as e:
            logger.error(f"Basic prefetch parse failed: {e}")
