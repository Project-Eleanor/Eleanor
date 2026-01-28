"""Microsoft Edge browser parser.

Parses Edge (Chromium-based) browser artifacts:
- History (browsing history)
- Downloads
- Cookies
- Login Data (saved passwords)
- Bookmarks

Location: %LocalAppData%\\Microsoft\\Edge\\User Data\\Default\\
"""

import json
import logging
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.formats.browser_sqlite_base import BrowserSQLiteParser
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser
class EdgeHistoryParser(BrowserSQLiteParser):
    """Parser for Microsoft Edge browser history."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="edge_history",
            display_name="Microsoft Edge History Parser",
            description="Parses Microsoft Edge browsing history",
            supported_extensions=[""],  # No extension (History file)
            mime_types=["application/x-sqlite3", "application/octet-stream"],
            category="browser",
            priority=80,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Edge History SQLite database."""
        try:
            conn = self._connect_readonly(file_path)
            cursor = conn.cursor()

            # Query browsing history
            cursor.execute("""
                SELECT
                    urls.id,
                    urls.url,
                    urls.title,
                    urls.visit_count,
                    urls.typed_count,
                    urls.last_visit_time,
                    urls.hidden,
                    visits.visit_time,
                    visits.from_visit,
                    visits.transition,
                    visits.visit_duration
                FROM urls
                LEFT JOIN visits ON urls.id = visits.url
                ORDER BY visits.visit_time DESC
            """)

            for row in cursor.fetchall():
                entry = dict(row)
                entry["browser"] = "Microsoft Edge"
                entry["file_path"] = str(file_path)

                # Convert Chrome timestamp (microseconds since 1601-01-01)
                if entry.get("visit_time"):
                    entry["visit_time"] = self._chrome_time_to_datetime(entry["visit_time"])
                if entry.get("last_visit_time"):
                    entry["last_visit_time"] = self._chrome_time_to_datetime(
                        entry["last_visit_time"]
                    )

                yield self._create_event(entry, case_id, evidence_id)

            conn.close()

        except Exception as e:
            logger.error(f"Failed to parse Edge history: {e}")
            raise

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Edge history entry."""
        url = entry.get("url", "")
        title = entry.get("title", "")
        timestamp = entry.get("visit_time") or entry.get("last_visit_time") or datetime.now(UTC)

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Edge visit: {title[:50] or url[:50]}",
            source="edge",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web"],
                    "type": ["access"],
                    "action": "browser_visit",
                    "module": "edge",
                    "dataset": "browser.edge.history",
                },
                "url": {
                    "original": url,
                    "domain": self._extract_domain(url),
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "edge_history",
                    "artifact_type": "browser_history",
                    "browser": "Microsoft Edge",
                    "title": title,
                    "visit_count": entry.get("visit_count"),
                    "typed_count": entry.get("typed_count"),
                    "hidden": entry.get("hidden"),
                    "transition": entry.get("transition"),
                    "visit_duration_us": entry.get("visit_duration"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _chrome_time_to_datetime(self, chrome_time: int) -> datetime | None:
        """Convert Chrome/Edge timestamp to datetime."""
        try:
            if chrome_time == 0:
                return None
            # Chrome time: microseconds since 1601-01-01
            # Convert to Unix timestamp (seconds since 1970-01-01)
            epoch_diff = 11644473600  # Seconds between 1601 and 1970
            unix_time = (chrome_time / 1000000) - epoch_diff
            return datetime.fromtimestamp(unix_time, tz=UTC)
        except Exception:
            return None

    def _extract_domain(self, url: str) -> str | None:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.netloc or None
        except Exception:
            return None


@register_parser
class EdgeDownloadsParser(BaseParser):
    """Parser for Microsoft Edge browser downloads."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="edge_downloads",
            display_name="Microsoft Edge Downloads Parser",
            description="Parses Microsoft Edge download history",
            supported_extensions=[""],
            mime_types=["application/x-sqlite3", "application/octet-stream"],
            category="browser",
            priority=80,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Edge downloads from History SQLite database."""
        if not SQLITE_AVAILABLE:
            logger.error("sqlite3 module required for Edge downloads parsing")
            return

        try:
            conn = sqlite3.connect(f"file:{file_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query downloads
            cursor.execute("""
                SELECT
                    id,
                    current_path,
                    target_path,
                    start_time,
                    end_time,
                    received_bytes,
                    total_bytes,
                    state,
                    danger_type,
                    interrupt_reason,
                    hash,
                    opened,
                    last_access_time,
                    referrer,
                    tab_url,
                    tab_referrer_url,
                    mime_type,
                    original_mime_type
                FROM downloads
                ORDER BY start_time DESC
            """)

            for row in cursor.fetchall():
                entry = dict(row)
                entry["browser"] = "Microsoft Edge"
                entry["file_path"] = str(file_path)

                # Convert timestamps
                if entry.get("start_time"):
                    entry["start_time"] = self._chrome_time_to_datetime(entry["start_time"])
                if entry.get("end_time"):
                    entry["end_time"] = self._chrome_time_to_datetime(entry["end_time"])
                if entry.get("last_access_time"):
                    entry["last_access_time"] = self._chrome_time_to_datetime(
                        entry["last_access_time"]
                    )

                yield self._create_event(entry, case_id, evidence_id)

            conn.close()

        except Exception as e:
            logger.error(f"Failed to parse Edge downloads: {e}")
            raise

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Edge download entry."""
        target_path = entry.get("target_path") or entry.get("current_path", "")
        timestamp = entry.get("start_time") or datetime.now(UTC)
        tab_url = entry.get("tab_url", "")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Edge download: {Path(target_path).name if target_path else 'unknown'}",
            source="edge",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web", "file"],
                    "type": ["creation"],
                    "action": "browser_download",
                    "module": "edge",
                    "dataset": "browser.edge.downloads",
                },
                "url": {
                    "original": tab_url,
                },
                "file": {
                    "path": target_path,
                    "name": Path(target_path).name if target_path else None,
                    "size": entry.get("total_bytes"),
                    "mime_type": entry.get("mime_type"),
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "edge_downloads",
                    "artifact_type": "browser_download",
                    "browser": "Microsoft Edge",
                    "received_bytes": entry.get("received_bytes"),
                    "state": entry.get("state"),
                    "danger_type": entry.get("danger_type"),
                    "opened": entry.get("opened"),
                    "referrer": entry.get("referrer"),
                    "hash": entry.get("hash"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _chrome_time_to_datetime(self, chrome_time: int) -> datetime | None:
        """Convert Chrome/Edge timestamp to datetime."""
        try:
            if chrome_time == 0:
                return None
            epoch_diff = 11644473600
            unix_time = (chrome_time / 1000000) - epoch_diff
            return datetime.fromtimestamp(unix_time, tz=UTC)
        except Exception:
            return None


@register_parser
class EdgeBookmarksParser(BaseParser):
    """Parser for Microsoft Edge bookmarks."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="edge_bookmarks",
            display_name="Microsoft Edge Bookmarks Parser",
            description="Parses Microsoft Edge bookmarks JSON file",
            supported_extensions=[""],  # No extension (Bookmarks file)
            mime_types=["application/json"],
            category="browser",
            priority=75,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Edge Bookmarks JSON file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Parse roots
            roots = data.get("roots", {})
            for root_name, root_data in roots.items():
                if isinstance(root_data, dict):
                    async for event in self._parse_folder(
                        root_data, [root_name], file_path, case_id, evidence_id
                    ):
                        yield event

        except Exception as e:
            logger.error(f"Failed to parse Edge bookmarks: {e}")
            raise

    async def _parse_folder(
        self,
        folder: dict,
        path: list[str],
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Recursively parse bookmark folder."""
        children = folder.get("children", [])

        for item in children:
            item_type = item.get("type")

            if item_type == "url":
                # Bookmark
                entry = {
                    "browser": "Microsoft Edge",
                    "file_path": str(file_path),
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "folder_path": "/".join(path),
                    "date_added": self._chrome_time_to_datetime(int(item.get("date_added", 0))),
                    "date_modified": self._chrome_time_to_datetime(
                        int(item.get("date_modified", 0))
                    ),
                    "guid": item.get("guid"),
                }

                yield self._create_event(entry, case_id, evidence_id)

            elif item_type == "folder":
                # Recurse into folder
                async for event in self._parse_folder(
                    item, path + [item.get("name", "unnamed")], file_path, case_id, evidence_id
                ):
                    yield event

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from bookmark entry."""
        url = entry.get("url", "")
        name = entry.get("name", "")
        timestamp = entry.get("date_added") or datetime.now(UTC)

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Edge bookmark: {name[:50]}",
            source="edge",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web"],
                    "type": ["info"],
                    "action": "browser_bookmark",
                    "module": "edge",
                    "dataset": "browser.edge.bookmarks",
                },
                "url": {
                    "original": url,
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "edge_bookmarks",
                    "artifact_type": "browser_bookmark",
                    "browser": "Microsoft Edge",
                    "bookmark_name": name,
                    "folder_path": entry.get("folder_path"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _chrome_time_to_datetime(self, chrome_time: int) -> datetime | None:
        """Convert Chrome/Edge timestamp to datetime."""
        try:
            if chrome_time == 0:
                return None
            epoch_diff = 11644473600
            unix_time = (chrome_time / 1000000) - epoch_diff
            return datetime.fromtimestamp(unix_time, tz=UTC)
        except Exception:
            return None
