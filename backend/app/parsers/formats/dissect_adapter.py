"""Base adapter for Dissect-based parsers.

Provides a common interface for wrapping Dissect plugins while conforming
to the Eleanor BaseParser interface. Handles common functionality like
error handling, record normalization, and timestamp extraction.
"""

import logging
from abc import abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory

logger = logging.getLogger(__name__)


class DissectParserAdapter(BaseParser):
    """Base adapter for Dissect-based parsers.

    Subclasses should implement:
    - name: Parser identifier
    - category: Parser category
    - description: Human-readable description
    - supported_extensions: File extensions
    - supported_mime_types: MIME types
    - _get_dissect_parser: Returns the Dissect parser instance
    - _parse_record: Converts a Dissect record to ParsedEvent
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this parser."""
        ...

    @property
    def category(self) -> ParserCategory:
        """Default category for Dissect parsers."""
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        """Human-readable description."""
        return f"Dissect-based {self.name} parser"

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser supports."""
        return []

    @property
    def supported_mime_types(self) -> list[str]:
        """MIME types this parser supports."""
        return ["application/octet-stream"]

    @abstractmethod
    def _get_dissect_parser(self, source: Path | BinaryIO) -> Any:
        """Get the Dissect parser instance for the source.

        Args:
            source: Path or file-like object to parse

        Returns:
            Dissect parser instance
        """
        ...

    @abstractmethod
    def _parse_record(self, record: Any, source_name: str) -> ParsedEvent | None:
        """Convert a Dissect record to a ParsedEvent.

        Args:
            record: Dissect record object
            source_name: Name of the source file

        Returns:
            ParsedEvent or None if record should be skipped
        """
        ...

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if this parser can handle the input.

        Subclasses may override for more specific detection.
        """
        if file_path:
            ext = file_path.suffix.lower()
            if ext in [e.lower() for e in self.supported_extensions]:
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse the source and yield events.

        Args:
            source: Path or file-like object to parse
            source_name: Optional name for logging

        Yields:
            ParsedEvent objects for each record
        """
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            parser = self._get_dissect_parser(source)

            for record in self._iterate_records(parser):
                try:
                    event = self._parse_record(record, source_str)
                    if event:
                        yield event
                except Exception as e:
                    logger.debug(f"Failed to parse record: {e}")
                    continue

        except ImportError as e:
            logger.error(f"Dissect library not available: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse {source_str}: {e}")
            raise

    def _iterate_records(self, parser: Any) -> Iterator[Any]:
        """Iterate over records from the parser.

        Override in subclasses for custom iteration logic.
        """
        if hasattr(parser, "__iter__"):
            yield from parser
        elif hasattr(parser, "records"):
            yield from parser.records()
        elif hasattr(parser, "entries"):
            yield from parser.entries()
        else:
            raise ValueError(f"Don't know how to iterate over {type(parser)}")

    def _to_datetime(self, value: Any) -> datetime:
        """Convert various timestamp formats to datetime.

        Args:
            value: Timestamp value (datetime, int, float, or string)

        Returns:
            datetime in UTC
        """
        if value is None:
            return datetime.now(timezone.utc)

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        if isinstance(value, (int, float)):
            # Assume Unix timestamp
            try:
                # Check if nanoseconds
                if value > 1e12:
                    value = value / 1e9
                elif value > 1e9:
                    value = value / 1e3
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OSError, ValueError):
                return datetime.now(timezone.utc)

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass

        return datetime.now(timezone.utc)

    def _safe_str(self, value: Any) -> str | None:
        """Safely convert value to string."""
        if value is None:
            return None
        try:
            return str(value)
        except Exception:
            return None

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _extract_path_parts(self, path: str | None) -> tuple[str | None, str | None]:
        """Extract directory and filename from path.

        Args:
            path: Full file path

        Returns:
            Tuple of (directory, filename)
        """
        if not path:
            return None, None

        try:
            p = Path(path)
            return str(p.parent), p.name
        except Exception:
            return None, path
