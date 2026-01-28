"""Firefox browser history and artifacts parser.

Parses Firefox browser SQLite databases including places.sqlite for
history and bookmarks.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

from app.parsers.base import ParsedEvent, ParserCategory
from app.parsers.formats.browser_sqlite_base import BrowserSQLiteParser
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


def moz_timestamp_to_datetime(moz_timestamp: int | None) -> datetime:
    """Convert Mozilla PRTime (microseconds since Unix epoch) to datetime."""
    if not moz_timestamp or moz_timestamp == 0:
        return datetime.now(timezone.utc)

    try:
        # PRTime is microseconds since Unix epoch
        unix_ts = moz_timestamp / 1000000
        return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return datetime.now(timezone.utc)


@register_parser
class FirefoxHistoryParser(BrowserSQLiteParser):
    """Parser for Firefox places.sqlite database."""

    @property
    def name(self) -> str:
        return "firefox_history"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Firefox browser history and bookmarks parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".sqlite"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for Firefox places.sqlite database."""
        if content and len(content) >= 16:
            if not content[:16].startswith(b"SQLite format 3"):
                return False

        if file_path:
            name = file_path.name.lower()
            if name == "places.sqlite":
                return True
            # Check path for Firefox profile
            if "firefox" in str(file_path).lower() and name.endswith(".sqlite"):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse Firefox places.sqlite database."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            with self._db_context(source) as conn:
                # Parse history visits
                yield from self._parse_visits(conn, source_str)

                # Parse downloads
                yield from self._parse_downloads(conn, source_str)

                # Parse bookmarks
                yield from self._parse_bookmarks(conn, source_str)

        except sqlite3.Error as e:
            logger.error("SQLite error parsing Firefox history: %s", e)
        except Exception as e:
            logger.error("Failed to parse Firefox history: %s", e)
            raise

    def _parse_visits(self, conn: sqlite3.Connection, source_name: str) -> Iterator[ParsedEvent]:
        """Parse URL visits from moz_historyvisits and moz_places."""
        try:
            cursor = conn.execute("""
                SELECT
                    moz_places.url,
                    moz_places.title,
                    moz_places.visit_count,
                    moz_places.frecency,
                    moz_historyvisits.visit_date,
                    moz_historyvisits.visit_type,
                    moz_historyvisits.from_visit
                FROM moz_places
                LEFT JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
                WHERE moz_historyvisits.visit_date IS NOT NULL
                ORDER BY moz_historyvisits.visit_date DESC
            """)

            for row in cursor:
                url = row["url"]
                title = row["title"] or ""
                visit_date = moz_timestamp_to_datetime(row["visit_date"])
                visit_type = row["visit_type"]
                visit_count = row["visit_count"] or 0

                # Map visit type
                visit_type_map = {
                    1: "link",
                    2: "typed",
                    3: "bookmark",
                    4: "embed",
                    5: "redirect_permanent",
                    6: "redirect_temporary",
                    7: "download",
                    8: "framed_link",
                    9: "reload",
                }
                visit_type_str = visit_type_map.get(visit_type, f"unknown_{visit_type}")

                # Extract domain
                domain = None
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    domain = parsed.netloc
                except Exception:
                    pass

                message = f"Firefox visit: {title or url}"
                if len(message) > 200:
                    message = message[:197] + "..."

                raw = {
                    "url": url,
                    "title": title,
                    "visit_count": visit_count,
                    "visit_type": visit_type_str,
                    "frecency": row["frecency"],
                }

                yield ParsedEvent(
                    timestamp=visit_date,
                    message=message,
                    source_type="firefox_history",
                    source_file=source_name,
                    event_kind="event",
                    event_category=["web"],
                    event_type=["access", "info"],
                    event_action="url_visit",
                    url_full=url,
                    url_domain=domain,
                    raw=raw,
                    labels={
                        "browser": "firefox",
                        "visit_type": visit_type_str,
                    },
                    tags=["browser_history", "user_activity"],
                )

        except sqlite3.Error as e:
            logger.debug(f"Failed to parse visits: {e}")

    def _parse_downloads(self, conn: sqlite3.Connection, source_name: str) -> Iterator[ParsedEvent]:
        """Parse downloads from moz_annos (annotations)."""
        try:
            # Firefox stores download info in annotations
            cursor = conn.execute("""
                SELECT
                    moz_places.url,
                    moz_annos.content,
                    moz_annos.dateAdded,
                    moz_annos.anno_attribute_id
                FROM moz_annos
                JOIN moz_places ON moz_annos.place_id = moz_places.id
                WHERE moz_annos.anno_attribute_id IN (
                    SELECT id FROM moz_anno_attributes
                    WHERE name LIKE '%download%'
                )
                ORDER BY moz_annos.dateAdded DESC
            """)

            for row in cursor:
                url = row["url"]
                content = row["content"]
                date_added = moz_timestamp_to_datetime(row["dateAdded"])

                # Try to extract filename from content
                filename = None
                target_path = None
                if content:
                    try:
                        import json
                        data = json.loads(content)
                        target_path = data.get("targetFileSpec") or data.get("target")
                        if target_path:
                            filename = Path(target_path).name
                    except (json.JSONDecodeError, TypeError):
                        if content.startswith("file://"):
                            target_path = content
                            filename = Path(content).name

                if not filename:
                    continue

                message = f"Firefox download: {filename}"

                raw = {
                    "url": url,
                    "target_path": target_path,
                    "filename": filename,
                }

                yield ParsedEvent(
                    timestamp=date_added,
                    message=message,
                    source_type="firefox_history",
                    source_file=source_name,
                    event_kind="event",
                    event_category=["web", "file"],
                    event_type=["creation", "info"],
                    event_action="file_download",
                    url_full=url,
                    file_name=filename,
                    file_path=target_path,
                    raw=raw,
                    labels={
                        "browser": "firefox",
                    },
                    tags=["browser_download", "user_activity"],
                )

        except sqlite3.Error as e:
            logger.debug(f"Failed to parse downloads: {e}")

    def _parse_bookmarks(self, conn: sqlite3.Connection, source_name: str) -> Iterator[ParsedEvent]:
        """Parse bookmarks from moz_bookmarks."""
        try:
            cursor = conn.execute("""
                SELECT
                    moz_bookmarks.title,
                    moz_bookmarks.dateAdded,
                    moz_bookmarks.lastModified,
                    moz_places.url
                FROM moz_bookmarks
                LEFT JOIN moz_places ON moz_bookmarks.fk = moz_places.id
                WHERE moz_bookmarks.type = 1  -- TYPE_BOOKMARK
                AND moz_places.url IS NOT NULL
                ORDER BY moz_bookmarks.dateAdded DESC
            """)

            for row in cursor:
                title = row["title"] or ""
                url = row["url"]
                date_added = moz_timestamp_to_datetime(row["dateAdded"])

                # Extract domain
                domain = None
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    domain = parsed.netloc
                except Exception:
                    pass

                message = f"Firefox bookmark: {title or url}"
                if len(message) > 200:
                    message = message[:197] + "..."

                raw = {
                    "title": title,
                    "url": url,
                    "date_added": str(date_added),
                    "last_modified": str(moz_timestamp_to_datetime(row["lastModified"])),
                }

                yield ParsedEvent(
                    timestamp=date_added,
                    message=message,
                    source_type="firefox_history",
                    source_file=source_name,
                    event_kind="event",
                    event_category=["web"],
                    event_type=["creation", "info"],
                    event_action="bookmark_created",
                    url_full=url,
                    url_domain=domain,
                    raw=raw,
                    labels={
                        "browser": "firefox",
                        "artifact_type": "bookmark",
                    },
                    tags=["browser_bookmark", "user_activity"],
                )

        except sqlite3.Error as e:
            logger.debug(f"Failed to parse bookmarks: {e}")
