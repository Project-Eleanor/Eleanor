"""Unit tests for the Chrome browser parser.

Tests the ChromeHistoryParser and ChromeLoginDataParser classes for correct
parsing behavior, SQLite detection, and ECS field mapping.
"""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestChromeHistoryParser:
    """Tests for ChromeHistoryParser class."""

    @pytest.fixture
    def chrome_parser(self):
        """Create a Chrome history parser instance."""
        from app.parsers.formats.browser_chrome import ChromeHistoryParser

        return ChromeHistoryParser()

    def test_parser_name(self, chrome_parser):
        """Test parser name property."""
        assert chrome_parser.name == "chrome_history"

    def test_parser_category(self, chrome_parser):
        """Test parser category is ARTIFACTS."""
        from app.parsers.base import ParserCategory

        assert chrome_parser.category == ParserCategory.ARTIFACTS

    def test_parser_description(self, chrome_parser):
        """Test parser has a description."""
        assert "chrome" in chrome_parser.description.lower()
        assert "history" in chrome_parser.description.lower()

    def test_supported_extensions(self, chrome_parser):
        """Test parser supports SQLite extensions."""
        assert ".sqlite" in chrome_parser.supported_extensions
        assert ".db" in chrome_parser.supported_extensions

    def test_supported_mime_types(self, chrome_parser):
        """Test parser supports SQLite mime types."""
        assert "application/x-sqlite3" in chrome_parser.supported_mime_types


class TestChromeCanParse:
    """Tests for can_parse detection."""

    @pytest.fixture
    def chrome_parser(self):
        """Create a Chrome history parser instance."""
        from app.parsers.formats.browser_chrome import ChromeHistoryParser

        return ChromeHistoryParser()

    @pytest.fixture
    def sqlite_magic(self):
        """SQLite file magic bytes."""
        return b"SQLite format 3\x00"

    def test_can_parse_by_sqlite_magic(self, chrome_parser, sqlite_magic):
        """Test detection requires SQLite magic."""
        # SQLite magic alone is not enough
        assert chrome_parser.can_parse(content=sqlite_magic) is False

    def test_can_parse_invalid_magic_bytes(self, chrome_parser):
        """Test rejection of non-SQLite content."""
        invalid_content = b"NOT_SQLITE_FILE_CONTENT"
        assert chrome_parser.can_parse(content=invalid_content) is False

    def test_can_parse_by_filename(self, chrome_parser, tmp_path):
        """Test detection by 'History' filename."""
        history_file = tmp_path / "History"
        history_file.write_bytes(b"")
        assert chrome_parser.can_parse(file_path=history_file) is True

    def test_can_parse_chrome_profile_path(self, chrome_parser, tmp_path):
        """Test detection by Chrome profile path."""
        chrome_dir = tmp_path / "Chrome" / "Default"
        chrome_dir.mkdir(parents=True)
        history_file = chrome_dir / "History"
        history_file.write_bytes(b"")
        assert chrome_parser.can_parse(file_path=history_file) is True

    def test_cannot_parse_wrong_filename(self, chrome_parser, tmp_path):
        """Test rejection of non-History filename."""
        wrong_file = tmp_path / "random.db"
        wrong_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
        assert chrome_parser.can_parse(file_path=wrong_file) is False


class TestWebkitTimestamp:
    """Tests for WebKit timestamp conversion."""

    def test_webkit_to_datetime_valid(self):
        """Test valid WebKit timestamp conversion."""
        from app.parsers.formats.browser_chrome import webkit_to_datetime

        # WebKit timestamp for 2026-01-15 10:30:00 UTC
        # Unix epoch in microseconds + offset
        # 2026-01-15 10:30:00 = 1768564200 seconds from Unix epoch
        webkit_ts = (1768564200 * 1000000) + 11644473600000000

        result = webkit_to_datetime(webkit_ts)

        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_webkit_to_datetime_zero(self):
        """Test WebKit timestamp of zero."""
        from app.parsers.formats.browser_chrome import webkit_to_datetime

        result = webkit_to_datetime(0)

        # Should return current time for zero
        assert result is not None
        assert isinstance(result, datetime)

    def test_webkit_to_datetime_none(self):
        """Test WebKit timestamp of None."""
        from app.parsers.formats.browser_chrome import webkit_to_datetime

        result = webkit_to_datetime(None)

        # Should return current time for None
        assert result is not None
        assert isinstance(result, datetime)


class TestChromeHistoryParsing:
    """Tests for parsing Chrome History database."""

    @pytest.fixture
    def chrome_parser(self):
        """Create a Chrome history parser instance."""
        from app.parsers.formats.browser_chrome import ChromeHistoryParser

        return ChromeHistoryParser()

    @pytest.fixture
    def sample_history_db(self, tmp_path):
        """Create a sample Chrome History database."""
        db_path = tmp_path / "History"

        conn = sqlite3.connect(str(db_path))

        # Create urls table
        conn.execute("""
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                visit_count INTEGER,
                typed_count INTEGER,
                last_visit_time INTEGER
            )
        """)

        # Create visits table
        conn.execute("""
            CREATE TABLE visits (
                id INTEGER PRIMARY KEY,
                url INTEGER,
                visit_time INTEGER,
                from_visit INTEGER,
                transition INTEGER
            )
        """)

        # Insert sample data
        # WebKit timestamp for 2026-01-15 10:30:00 UTC
        visit_time = (1768564200 * 1000000) + 11644473600000000

        conn.execute(
            "INSERT INTO urls VALUES (1, 'https://example.com/page', 'Example Page', 5, 1, ?)",
            (visit_time,)
        )
        conn.execute(
            "INSERT INTO visits VALUES (1, 1, ?, 0, 1)",  # transition 1 = typed
            (visit_time,)
        )

        # Add another visit
        conn.execute(
            "INSERT INTO urls VALUES (2, 'https://malware.example.com/payload', 'Suspicious Site', 1, 0, ?)",
            (visit_time + 60000000,)  # 1 minute later
        )
        conn.execute(
            "INSERT INTO visits VALUES (2, 2, ?, 0, 0)",  # transition 0 = link
            (visit_time + 60000000,)
        )

        conn.commit()
        conn.close()

        return db_path

    def test_parse_visits(self, chrome_parser, sample_history_db):
        """Test parsing URL visits from history."""
        events = list(chrome_parser.parse(sample_history_db, "History"))

        assert len(events) >= 2

        # Find the example.com visit
        example_event = next((e for e in events if "example.com" in e.url_full and "malware" not in e.url_full), None)
        assert example_event is not None
        assert example_event.event_action == "url_visit"
        assert "web" in example_event.event_category
        assert example_event.url_domain == "example.com"

    def test_visit_event_fields(self, chrome_parser, sample_history_db):
        """Test visit event has correct ECS fields."""
        events = list(chrome_parser.parse(sample_history_db, "History"))
        event = events[0]

        assert event.source_type == "chrome_history"
        assert event.event_kind == "event"
        assert "browser" in event.labels
        assert event.labels["browser"] == "chrome"
        assert "browser_history" in event.tags

    def test_visit_transition_types(self, chrome_parser, sample_history_db):
        """Test transition type parsing."""
        events = list(chrome_parser.parse(sample_history_db, "History"))

        # Find typed visit
        typed_event = next((e for e in events if e.raw.get("transition_type") == "typed"), None)
        assert typed_event is not None

        # Find link visit
        link_event = next((e for e in events if e.raw.get("transition_type") == "link"), None)
        assert link_event is not None


class TestChromeDownloadsParsing:
    """Tests for parsing Chrome downloads."""

    @pytest.fixture
    def chrome_parser(self):
        """Create a Chrome history parser instance."""
        from app.parsers.formats.browser_chrome import ChromeHistoryParser

        return ChromeHistoryParser()

    @pytest.fixture
    def sample_downloads_db(self, tmp_path):
        """Create a sample Chrome History database with downloads."""
        db_path = tmp_path / "History"

        conn = sqlite3.connect(str(db_path))

        # Create tables
        conn.execute("""
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                visit_count INTEGER,
                typed_count INTEGER,
                last_visit_time INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE visits (
                id INTEGER PRIMARY KEY,
                url INTEGER,
                visit_time INTEGER,
                from_visit INTEGER,
                transition INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE downloads (
                id INTEGER PRIMARY KEY,
                target_path TEXT,
                tab_url TEXT,
                tab_referrer_url TEXT,
                start_time INTEGER,
                end_time INTEGER,
                received_bytes INTEGER,
                total_bytes INTEGER,
                state INTEGER,
                danger_type INTEGER,
                interrupt_reason INTEGER,
                mime_type TEXT,
                original_mime_type TEXT
            )
        """)

        # WebKit timestamp
        download_time = (1768564200 * 1000000) + 11644473600000000

        # Insert safe download
        conn.execute("""
            INSERT INTO downloads VALUES (
                1,
                '/Users/test/Downloads/document.pdf',
                'https://example.com/files/document.pdf',
                'https://example.com/',
                ?, ?, 1024000, 1024000, 1, 0, 0,
                'application/pdf', 'application/pdf'
            )
        """, (download_time, download_time + 5000000))

        # Insert potentially dangerous download
        conn.execute("""
            INSERT INTO downloads VALUES (
                2,
                '/Users/test/Downloads/setup.exe',
                'https://suspicious.example.com/setup.exe',
                'https://suspicious.example.com/',
                ?, ?, 5000000, 5000000, 1, 1, 0,
                'application/x-msdownload', 'application/x-msdownload'
            )
        """, (download_time + 60000000, download_time + 120000000))

        conn.commit()
        conn.close()

        return db_path

    def test_parse_downloads(self, chrome_parser, sample_downloads_db):
        """Test parsing downloads from history."""
        events = list(chrome_parser.parse(sample_downloads_db, "History"))

        # Find download events
        download_events = [e for e in events if e.event_action == "file_download"]
        assert len(download_events) == 2

    def test_download_event_fields(self, chrome_parser, sample_downloads_db):
        """Test download event has correct fields."""
        events = list(chrome_parser.parse(sample_downloads_db, "History"))
        download_events = [e for e in events if e.event_action == "file_download"]

        # Find the PDF download
        pdf_download = next((e for e in download_events if "document.pdf" in (e.file_name or "")), None)
        assert pdf_download is not None
        assert pdf_download.file_name == "document.pdf"
        assert "file" in pdf_download.event_category
        assert "web" in pdf_download.event_category
        assert "browser_download" in pdf_download.tags

    def test_dangerous_download_flagged(self, chrome_parser, sample_downloads_db):
        """Test dangerous downloads are flagged."""
        events = list(chrome_parser.parse(sample_downloads_db, "History"))
        download_events = [e for e in events if e.event_action == "file_download"]

        # Find the EXE download (danger_type > 0)
        dangerous_download = next((e for e in download_events if "setup.exe" in (e.file_name or "")), None)
        assert dangerous_download is not None
        assert dangerous_download.raw["danger_type"] == "dangerous_file"
        assert "potentially_dangerous" in dangerous_download.tags


class TestChromeLoginDataParser:
    """Tests for ChromeLoginDataParser class."""

    @pytest.fixture
    def login_parser(self):
        """Create a Chrome login data parser instance."""
        from app.parsers.formats.browser_chrome import ChromeLoginDataParser

        return ChromeLoginDataParser()

    def test_parser_name(self, login_parser):
        """Test parser name property."""
        assert login_parser.name == "chrome_logins"

    def test_parser_category(self, login_parser):
        """Test parser category is ARTIFACTS."""
        from app.parsers.base import ParserCategory

        assert login_parser.category == ParserCategory.ARTIFACTS

    def test_can_parse_login_data_file(self, login_parser, tmp_path):
        """Test detection by 'Login Data' filename."""
        login_file = tmp_path / "Login Data"
        login_file.write_bytes(b"")
        assert login_parser.can_parse(file_path=login_file) is True


class TestChromeLoginDataParsing:
    """Tests for parsing Chrome Login Data database."""

    @pytest.fixture
    def login_parser(self):
        """Create a Chrome login data parser instance."""
        from app.parsers.formats.browser_chrome import ChromeLoginDataParser

        return ChromeLoginDataParser()

    @pytest.fixture
    def sample_login_db(self, tmp_path):
        """Create a sample Chrome Login Data database."""
        db_path = tmp_path / "Login Data"

        conn = sqlite3.connect(str(db_path))

        # Create logins table
        conn.execute("""
            CREATE TABLE logins (
                origin_url TEXT,
                action_url TEXT,
                username_element TEXT,
                username_value TEXT,
                password_element TEXT,
                password_value BLOB,
                date_created INTEGER,
                date_last_used INTEGER,
                times_used INTEGER,
                date_password_modified INTEGER
            )
        """)

        # WebKit timestamp
        created_time = (1768564200 * 1000000) + 11644473600000000
        last_used_time = created_time + (86400 * 1000000)  # 1 day later

        conn.execute("""
            INSERT INTO logins VALUES (
                'https://example.com/',
                'https://example.com/login',
                'username',
                'testuser@example.com',
                'password',
                X'',
                ?, ?, 10, ?
            )
        """, (created_time, last_used_time, last_used_time))

        conn.execute("""
            INSERT INTO logins VALUES (
                'https://banking.example.com/',
                'https://banking.example.com/auth',
                'user_id',
                'john.doe',
                'pass',
                X'',
                ?, ?, 50, ?
            )
        """, (created_time, last_used_time, last_used_time))

        conn.commit()
        conn.close()

        return db_path

    def test_parse_logins(self, login_parser, sample_login_db):
        """Test parsing saved logins."""
        events = list(login_parser.parse(sample_login_db, "Login Data"))

        assert len(events) == 2

    def test_login_event_fields(self, login_parser, sample_login_db):
        """Test login event has correct fields."""
        events = list(login_parser.parse(sample_login_db, "Login Data"))

        # Find the example.com login
        example_login = next((e for e in events if "example.com" in e.url_full and "banking" not in e.url_full), None)
        assert example_login is not None
        assert example_login.user_name == "testuser@example.com"
        assert example_login.url_domain == "example.com"
        assert example_login.event_action == "saved_credential"
        assert "authentication" in example_login.event_category
        assert "web" in example_login.event_category

    def test_login_event_tags(self, login_parser, sample_login_db):
        """Test login events have correct tags."""
        events = list(login_parser.parse(sample_login_db, "Login Data"))
        event = events[0]

        assert "saved_credentials" in event.tags
        assert "browser_artifact" in event.tags
        assert event.labels["browser"] == "chrome"
        assert event.labels["credential_type"] == "password"


class TestChromeTransitionTypes:
    """Tests for Chrome page transition type parsing."""

    @pytest.fixture
    def chrome_parser(self):
        """Create a Chrome history parser instance."""
        from app.parsers.formats.browser_chrome import ChromeHistoryParser

        return ChromeHistoryParser()

    def test_transition_link(self, chrome_parser):
        """Test link transition type."""
        assert chrome_parser._get_transition_type(0) == "link"

    def test_transition_typed(self, chrome_parser):
        """Test typed transition type."""
        assert chrome_parser._get_transition_type(1) == "typed"

    def test_transition_auto_bookmark(self, chrome_parser):
        """Test auto_bookmark transition type."""
        assert chrome_parser._get_transition_type(2) == "auto_bookmark"

    def test_transition_form_submit(self, chrome_parser):
        """Test form_submit transition type."""
        assert chrome_parser._get_transition_type(7) == "form_submit"

    def test_transition_reload(self, chrome_parser):
        """Test reload transition type."""
        assert chrome_parser._get_transition_type(8) == "reload"

    def test_transition_with_flags(self, chrome_parser):
        """Test transition type with additional flags masked."""
        # Transition with flags (0x100 = blocked flag)
        transition = 1 | 0x100  # typed + blocked
        assert chrome_parser._get_transition_type(transition) == "typed"

    def test_transition_unknown(self, chrome_parser):
        """Test unknown transition type."""
        result = chrome_parser._get_transition_type(99)
        assert "unknown" in result
