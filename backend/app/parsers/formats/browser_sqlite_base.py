"""Base class for browser SQLite database parsers.

PATTERN: Template Method Pattern
This module provides a base class for parsing browser SQLite databases,
encapsulating common functionality:
- Temporary file creation for stream-based inputs
- Read-only SQLite connection setup
- Domain extraction from URLs
- Automatic resource cleanup via context manager

Subclasses implement specific parsing logic while reusing common infrastructure.

Usage:
    class ChromeHistoryParser(BrowserSQLiteParser):
        def parse(self, source, source_name=None):
            with self._db_context(source) as conn:
                yield from self._parse_visits(conn)
"""

import logging
import sqlite3
import tempfile
from abc import ABC
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class BrowserSQLiteParser(BaseParser, ABC):
    """Base class for browser SQLite database parsers.

    Provides common utility methods for:
    - Creating temporary files from binary streams
    - Establishing read-only SQLite connections
    - Extracting domains from URLs
    - Context manager for automatic cleanup

    Subclasses should use the _db_context() method to safely access
    the database and ensure proper cleanup of temporary files.
    """

    @staticmethod
    def _create_temp_file(stream: BinaryIO, suffix: str = ".db") -> Path:
        """Create a temporary file from a binary stream.

        SQLite requires file-based access, so streams must be written
        to a temporary file before parsing.

        Args:
            stream: Binary stream containing SQLite database
            suffix: File extension for the temp file (default: .db)

        Returns:
            Path to the created temporary file

        Note:
            Caller is responsible for cleanup. Use _db_context() for
            automatic cleanup, or manually unlink the file.
        """
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(stream.read())
            return Path(tmp.name)

    @staticmethod
    def _connect_readonly(db_path: Path) -> sqlite3.Connection:
        """Open a read-only SQLite connection.

        Uses URI mode with ?mode=ro to prevent accidental writes
        to the evidence database.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            SQLite connection with Row factory enabled

        Raises:
            sqlite3.Error: If connection fails (file not found, corrupted, etc.)
        """
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        """Extract the domain from a URL.

        Args:
            url: Full URL string

        Returns:
            Domain/hostname from the URL, or None if extraction fails
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or None
        except Exception:
            return None

    @contextmanager
    def _db_context(
        self,
        source: Path | BinaryIO,
    ) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for safe database access with automatic cleanup.

        Handles both file paths and binary streams, creating temporary
        files as needed and ensuring cleanup on exit.

        Args:
            source: Path to database file, or binary stream

        Yields:
            SQLite connection with Row factory enabled

        Example:
            with self._db_context(source) as conn:
                cursor = conn.execute("SELECT * FROM urls")
                for row in cursor:
                    yield self._create_event(row)

        Note:
            Any sqlite3.Error during connection is caught and logged.
            The generator will exit cleanly without yielding a connection.
        """
        cleanup_path: Path | None = None
        conn: sqlite3.Connection | None = None

        try:
            # Handle stream vs path input
            if isinstance(source, BinaryIO) or hasattr(source, "read"):
                cleanup_path = self._create_temp_file(source)
                db_path = cleanup_path
            else:
                db_path = Path(source)

            conn = self._connect_readonly(db_path)
            yield conn

        except sqlite3.Error as e:
            logger.error("SQLite error opening database: %s", e)
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass  # Best effort close

            if cleanup_path:
                cleanup_path.unlink(missing_ok=True)
