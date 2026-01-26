"""Remote access application log parsers.

Parses logs from popular remote access tools:
- TeamViewer: Connections_incoming.txt, Connections.txt
- AnyDesk: ad_svc.trace, ad.trace
- RustDesk: Various log files
- Splashtop: Various log files

These are critical for detecting unauthorized remote access.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata

logger = logging.getLogger(__name__)


class TeamViewerParser(BaseParser):
    """Parser for TeamViewer log files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="teamviewer",
            display_name="TeamViewer Log Parser",
            description="Parses TeamViewer connection and activity logs",
            supported_extensions=[".txt", ".log"],
            mime_types=["text/plain"],
            category="remote_access",
            priority=80,
        )

    # TeamViewer log patterns
    INCOMING_PATTERN = re.compile(
        r"(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})\s+"  # Timestamp
        r"(\d+)\s+"  # Remote ID
        r"([^\t]+)\t+"  # Remote name
        r"(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})?\s*"  # End time (optional)
        r"([^\t]*)\t*"  # Local user
        r"(.*)"  # Connection type
    )

    OUTGOING_PATTERN = re.compile(
        r"(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})\s+"  # Timestamp
        r"(\d+)\s+"  # Remote ID
        r"(.+)"  # Connection info
    )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse TeamViewer log file."""
        filename = file_path.name.lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if "incoming" in filename:
                async for event in self._parse_incoming(content, file_path, case_id, evidence_id):
                    yield event
            else:
                async for event in self._parse_outgoing(content, file_path, case_id, evidence_id):
                    yield event

        except Exception as e:
            logger.error(f"Failed to parse TeamViewer log: {e}")
            raise

    async def _parse_incoming(
        self,
        content: str,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse incoming connections log."""
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = self.INCOMING_PATTERN.match(line)
            if match:
                start_time = self._parse_timestamp(match.group(1))
                remote_id = match.group(2)
                remote_name = match.group(3).strip()
                end_time = self._parse_timestamp(match.group(4)) if match.group(4) else None
                local_user = match.group(5).strip() if match.group(5) else None
                conn_type = match.group(6).strip() if match.group(6) else None

                yield self._create_event(
                    {
                        "direction": "incoming",
                        "remote_id": remote_id,
                        "remote_name": remote_name,
                        "local_user": local_user,
                        "connection_type": conn_type,
                        "start_time": start_time,
                        "end_time": end_time,
                        "log_file": str(file_path),
                    },
                    case_id,
                    evidence_id,
                )

    async def _parse_outgoing(
        self,
        content: str,
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse outgoing connections log."""
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = self.OUTGOING_PATTERN.match(line)
            if match:
                timestamp = self._parse_timestamp(match.group(1))
                remote_id = match.group(2)
                info = match.group(3).strip()

                yield self._create_event(
                    {
                        "direction": "outgoing",
                        "remote_id": remote_id,
                        "connection_info": info,
                        "start_time": timestamp,
                        "log_file": str(file_path),
                    },
                    case_id,
                    evidence_id,
                )

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from TeamViewer entry."""
        timestamp = entry.get("start_time") or datetime.now(timezone.utc)
        direction = entry.get("direction", "unknown")
        remote_id = entry.get("remote_id", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"TeamViewer {direction}: Remote ID {remote_id}",
            source="teamviewer",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["network", "session"],
                    "type": ["connection", "start"],
                    "action": f"remote_access_{direction}",
                    "module": "teamviewer",
                    "dataset": "remote_access.teamviewer",
                    "start": timestamp.isoformat() if timestamp else None,
                    "end": entry.get("end_time").isoformat() if entry.get("end_time") else None,
                },
                "user": {
                    "name": entry.get("local_user"),
                } if entry.get("local_user") else None,
                "source": {
                    "user": {"name": entry.get("remote_name")},
                } if direction == "incoming" else None,
                "destination": {
                    "user": {"id": remote_id},
                } if direction == "outgoing" else None,
                "network": {
                    "application": "TeamViewer",
                    "direction": "inbound" if direction == "incoming" else "outbound",
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "teamviewer",
                    "artifact_type": "remote_access",
                    "remote_id": remote_id,
                    "remote_name": entry.get("remote_name"),
                    "connection_type": entry.get("connection_type"),
                    "log_file": entry.get("log_file"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse TeamViewer timestamp."""
        try:
            # Format: DD-MM-YYYY HH:MM:SS
            return datetime.strptime(ts_str, "%d-%m-%Y %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None


class AnyDeskParser(BaseParser):
    """Parser for AnyDesk log/trace files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="anydesk",
            display_name="AnyDesk Log Parser",
            description="Parses AnyDesk trace and connection logs",
            supported_extensions=[".trace", ".txt", ".log"],
            mime_types=["text/plain"],
            category="remote_access",
            priority=80,
        )

    # AnyDesk patterns
    CONNECTION_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)"  # Timestamp
        r".*?(?:Logged in from|Connection from|Connecting to)"
        r"\s+(\d+)"  # AnyDesk ID
    )

    SESSION_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)"  # Timestamp
        r".*?(Session|Connection)\s+(\w+)"  # Session action
    )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse AnyDesk log file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    # Check for connection events
                    conn_match = self.CONNECTION_PATTERN.search(line)
                    if conn_match:
                        timestamp = self._parse_timestamp(conn_match.group(1))
                        remote_id = conn_match.group(2)

                        direction = "incoming" if "from" in line.lower() else "outgoing"

                        yield self._create_event(
                            {
                                "direction": direction,
                                "remote_id": remote_id,
                                "timestamp": timestamp,
                                "raw_line": line,
                                "line_number": line_num,
                                "log_file": str(file_path),
                            },
                            case_id,
                            evidence_id,
                        )

        except Exception as e:
            logger.error(f"Failed to parse AnyDesk log: {e}")
            raise

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from AnyDesk entry."""
        timestamp = entry.get("timestamp") or datetime.now(timezone.utc)
        direction = entry.get("direction", "unknown")
        remote_id = entry.get("remote_id", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"AnyDesk {direction}: Remote ID {remote_id}",
            source="anydesk",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["network", "session"],
                    "type": ["connection"],
                    "action": f"remote_access_{direction}",
                    "module": "anydesk",
                    "dataset": "remote_access.anydesk",
                },
                "network": {
                    "application": "AnyDesk",
                    "direction": "inbound" if direction == "incoming" else "outbound",
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "anydesk",
                    "artifact_type": "remote_access",
                    "remote_id": remote_id,
                    "raw_line": entry.get("raw_line"),
                    "log_file": entry.get("log_file"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse AnyDesk timestamp."""
        try:
            # Format: YYYY-MM-DD HH:MM:SS.mmm
            if "." in ts_str:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            else:
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None


class RustDeskParser(BaseParser):
    """Parser for RustDesk log files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="rustdesk",
            display_name="RustDesk Log Parser",
            description="Parses RustDesk connection and activity logs",
            supported_extensions=[".log", ".txt"],
            mime_types=["text/plain"],
            category="remote_access",
            priority=75,
        )

    # RustDesk patterns
    CONNECTION_PATTERN = re.compile(
        r"\[(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})"  # Timestamp
        r".*?(?:new\s+connection|connecting\s+to|connection\s+from)"
        r".*?(\d{9,})",  # RustDesk ID (9+ digits)
        re.IGNORECASE,
    )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse RustDesk log file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    conn_match = self.CONNECTION_PATTERN.search(line)
                    if conn_match:
                        timestamp = self._parse_timestamp(conn_match.group(1))
                        remote_id = conn_match.group(2)
                        direction = "incoming" if "from" in line.lower() else "outgoing"

                        yield ParsedEvent(
                            id=str(uuid4()),
                            timestamp=timestamp or datetime.now(timezone.utc),
                            message=f"RustDesk {direction}: Remote ID {remote_id}",
                            source="rustdesk",
                            raw_data={
                                "direction": direction,
                                "remote_id": remote_id,
                                "raw_line": line,
                                "log_file": str(file_path),
                            },
                            normalized={
                                "event": {
                                    "kind": "event",
                                    "category": ["network", "session"],
                                    "type": ["connection"],
                                    "action": f"remote_access_{direction}",
                                    "module": "rustdesk",
                                    "dataset": "remote_access.rustdesk",
                                },
                                "network": {
                                    "application": "RustDesk",
                                    "direction": "inbound" if direction == "incoming" else "outbound",
                                },
                                "eleanor": {
                                    "case_id": case_id,
                                    "evidence_id": evidence_id,
                                    "parser": "rustdesk",
                                    "artifact_type": "remote_access",
                                    "remote_id": remote_id,
                                },
                            },
                            case_id=case_id,
                            evidence_id=evidence_id,
                        )

        except Exception as e:
            logger.error(f"Failed to parse RustDesk log: {e}")
            raise

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse RustDesk timestamp."""
        try:
            ts_str = ts_str.replace("T", " ")
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None
