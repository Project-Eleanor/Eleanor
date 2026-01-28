"""Chrome browser history and artifacts parser.

Parses Chrome browser SQLite databases including History, Downloads,
Cookies, and Login Data.
"""

import logging
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.parsers.base import ParsedEvent, ParserCategory
from app.parsers.formats.browser_sqlite_base import BrowserSQLiteParser
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Chrome uses WebKit timestamps (microseconds since Jan 1, 1601)
WEBKIT_EPOCH_OFFSET = 11644473600000000  # Microseconds between 1601 and 1970


def webkit_to_datetime(webkit_timestamp: int | None) -> datetime:
    """Convert WebKit timestamp to datetime."""
    if not webkit_timestamp or webkit_timestamp == 0:
        return datetime.now(UTC)

    try:
        # Convert to Unix timestamp (seconds)
        unix_ts = (webkit_timestamp - WEBKIT_EPOCH_OFFSET) / 1000000
        return datetime.fromtimestamp(unix_ts, tz=UTC)
    except (OSError, ValueError, OverflowError):
        return datetime.now(UTC)


@register_parser
class ChromeHistoryParser(BrowserSQLiteParser):
    """Parser for Chrome browser History database."""

    @property
    def name(self) -> str:
        return "chrome_history"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Chrome browser history and downloads parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".sqlite", ".db"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-sqlite3", "application/vnd.sqlite3"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for Chrome History database."""
        # Check magic bytes for SQLite
        if content and len(content) >= 16:
            if not content[:16].startswith(b"SQLite format 3"):
                return False

        if file_path:
            name = file_path.name.lower()
            # Chrome history files
            if name in ("history", "history-journal"):
                return True
            # Chrome profile databases
            if "chrome" in str(file_path).lower() and name in ("history", "web data", "login data"):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse Chrome History database."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            with self._db_context(source) as conn:
                # Parse URL visits
                yield from self._parse_visits(conn, source_str)

                # Parse downloads
                yield from self._parse_downloads(conn, source_str)

        except sqlite3.Error as e:
            logger.error("SQLite error parsing Chrome history: %s", e)
        except Exception as e:
            logger.error("Failed to parse Chrome history: %s", e)
            raise

    def _parse_visits(self, conn: sqlite3.Connection, source_name: str) -> Iterator[ParsedEvent]:
        """Parse URL visits from history."""
        try:
            cursor = conn.execute("""
                SELECT
                    urls.url,
                    urls.title,
                    urls.visit_count,
                    urls.typed_count,
                    urls.last_visit_time,
                    visits.visit_time,
                    visits.from_visit,
                    visits.transition
                FROM urls
                LEFT JOIN visits ON urls.id = visits.url
                ORDER BY visits.visit_time DESC
            """)

            for row in cursor:
                url = row["url"]
                title = row["title"] or ""
                visit_time = webkit_to_datetime(row["visit_time"])
                visit_count = row["visit_count"] or 0
                typed_count = row["typed_count"] or 0
                transition = row["transition"] or 0

                # Parse transition type
                transition_type = self._get_transition_type(transition)

                # Extract domain using base class helper
                domain = self._extract_domain(url)

                message = f"Chrome visit: {title or url}"
                if len(message) > 200:
                    message = message[:197] + "..."

                raw = {
                    "url": url,
                    "title": title,
                    "visit_count": visit_count,
                    "typed_count": typed_count,
                    "transition_type": transition_type,
                    "transition_raw": transition,
                }

                yield ParsedEvent(
                    timestamp=visit_time,
                    message=message,
                    source_type="chrome_history",
                    source_file=source_name,
                    event_kind="event",
                    event_category=["web"],
                    event_type=["access", "info"],
                    event_action="url_visit",
                    url_full=url,
                    url_domain=domain,
                    raw=raw,
                    labels={
                        "browser": "chrome",
                        "visit_type": transition_type,
                    },
                    tags=["browser_history", "user_activity"],
                )

        except sqlite3.Error as e:
            logger.debug(f"Failed to parse visits: {e}")

    def _parse_downloads(self, conn: sqlite3.Connection, source_name: str) -> Iterator[ParsedEvent]:
        """Parse downloads from history."""
        try:
            cursor = conn.execute("""
                SELECT
                    target_path,
                    tab_url,
                    tab_referrer_url,
                    start_time,
                    end_time,
                    received_bytes,
                    total_bytes,
                    state,
                    danger_type,
                    interrupt_reason,
                    mime_type,
                    original_mime_type
                FROM downloads
                ORDER BY start_time DESC
            """)

            for row in cursor:
                target_path = row["target_path"]
                tab_url = row["tab_url"]
                start_time = webkit_to_datetime(row["start_time"])
                total_bytes = row["total_bytes"] or 0
                danger_type = row["danger_type"] or 0
                mime_type = row["mime_type"]

                # Extract filename
                filename = None
                if target_path:
                    filename = Path(target_path).name

                # Map danger type
                danger_map = {
                    0: "safe",
                    1: "dangerous_file",
                    2: "dangerous_url",
                    3: "dangerous_content",
                    4: "maybe_dangerous_content",
                    5: "uncommon_content",
                    6: "user_validated",
                    7: "dangerous_host",
                    8: "potentially_unwanted",
                }
                danger_str = danger_map.get(danger_type, f"unknown_{danger_type}")

                message = f"Chrome download: {filename or target_path}"
                if len(message) > 200:
                    message = message[:197] + "..."

                raw = {
                    "target_path": target_path,
                    "source_url": tab_url,
                    "referrer_url": row["tab_referrer_url"],
                    "total_bytes": total_bytes,
                    "received_bytes": row["received_bytes"],
                    "state": row["state"],
                    "danger_type": danger_str,
                    "mime_type": mime_type,
                }

                tags = ["browser_download", "user_activity"]
                if danger_type > 0:
                    tags.append("potentially_dangerous")

                yield ParsedEvent(
                    timestamp=start_time,
                    message=message,
                    source_type="chrome_history",
                    source_file=source_name,
                    event_kind="event",
                    event_category=["web", "file"],
                    event_type=["creation", "info"],
                    event_action="file_download",
                    url_full=tab_url,
                    file_name=filename,
                    file_path=target_path,
                    raw=raw,
                    labels={
                        "browser": "chrome",
                        "danger_type": danger_str,
                        "mime_type": mime_type or "",
                    },
                    tags=tags,
                )

        except sqlite3.Error as e:
            logger.debug(f"Failed to parse downloads: {e}")

    def _get_transition_type(self, transition: int) -> str:
        """Get human-readable transition type."""
        core_type = transition & 0xFF
        transition_map = {
            0: "link",
            1: "typed",
            2: "auto_bookmark",
            3: "auto_subframe",
            4: "manual_subframe",
            5: "generated",
            6: "auto_toplevel",
            7: "form_submit",
            8: "reload",
            9: "keyword",
            10: "keyword_generated",
        }
        return transition_map.get(core_type, f"unknown_{core_type}")


@register_parser
class ChromeLoginDataParser(BrowserSQLiteParser):
    """Parser for Chrome Login Data database."""

    @property
    def name(self) -> str:
        return "chrome_logins"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        return "Chrome browser saved login data parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".sqlite", ".db"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/x-sqlite3", "application/vnd.sqlite3"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for Chrome Login Data database."""
        if content and len(content) >= 16:
            if not content[:16].startswith(b"SQLite format 3"):
                return False

        if file_path:
            name = file_path.name.lower()
            if name in ("login data", "login_data"):
                return True
            if "chrome" in str(file_path).lower() and "login" in name:
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse Chrome Login Data database."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            with self._db_context(source) as conn:
                cursor = conn.execute("""
                    SELECT
                        origin_url,
                        action_url,
                        username_element,
                        username_value,
                        password_element,
                        date_created,
                        date_last_used,
                        times_used,
                        date_password_modified
                    FROM logins
                    ORDER BY date_last_used DESC
                """)

                for row in cursor:
                    origin_url = row["origin_url"]
                    username = row["username_value"]
                    date_created = webkit_to_datetime(row["date_created"])
                    date_last_used = (
                        webkit_to_datetime(row["date_last_used"]) if row["date_last_used"] else None
                    )
                    times_used = row["times_used"] or 0

                    # Extract domain using base class method
                    domain = self._extract_domain(origin_url)

                    message = f"Chrome saved login: {username} @ {domain or origin_url}"

                    raw = {
                        "origin_url": origin_url,
                        "action_url": row["action_url"],
                        "username": username,
                        "date_created": str(date_created),
                        "date_last_used": str(date_last_used) if date_last_used else None,
                        "times_used": times_used,
                    }

                    yield ParsedEvent(
                        timestamp=date_created,
                        message=message,
                        source_type="chrome_logins",
                        source_file=source_str,
                        event_kind="event",
                        event_category=["authentication", "web"],
                        event_type=["info"],
                        event_action="saved_credential",
                        user_name=username,
                        url_full=origin_url,
                        url_domain=domain,
                        raw=raw,
                        labels={
                            "browser": "chrome",
                            "credential_type": "password",
                        },
                        tags=["saved_credentials", "user_activity", "browser_artifact"],
                    )

        except sqlite3.Error as e:
            logger.error("SQLite error parsing Chrome login data: %s", e)
        except Exception as e:
            logger.error("Failed to parse Chrome login data: %s", e)
            raise
