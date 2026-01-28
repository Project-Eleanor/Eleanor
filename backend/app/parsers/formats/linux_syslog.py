"""Linux syslog parser.

Parses Linux syslog, messages, and kern.log files.
"""

import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Syslog timestamp patterns
SYSLOG_PATTERNS = [
    # Standard syslog: Month Day HH:MM:SS
    re.compile(
        r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s*(?P<message>.*)$"
    ),
    # RFC 3164 with year: YYYY-MM-DD HH:MM:SS
    re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T?\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<hostname>\S+)\s+(?P<process>[^\[:]+)(?:\[(?P<pid>\d+)\])?:\s*(?P<message>.*)$"
    ),
    # RFC 5424: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID
    re.compile(
        r"^<(?P<pri>\d+)>(?P<version>\d)?\s*(?P<timestamp>\S+)\s+(?P<hostname>\S+)\s+(?P<appname>\S+)\s+(?P<procid>\S+)\s+(?P<msgid>\S+)\s+(?P<sd>-|\[.*?\])\s*(?P<message>.*)$"
    ),
]

# Process patterns for categorization
PROCESS_CATEGORIES = {
    "kernel": "kernel",
    "systemd": "system",
    "systemd-logind": "authentication",
    "sshd": "authentication",
    "sudo": "authentication",
    "su": "authentication",
    "login": "authentication",
    "cron": "scheduled",
    "anacron": "scheduled",
    "NetworkManager": "network",
    "dhclient": "network",
    "firewalld": "network",
    "iptables": "network",
    "ufw": "network",
    "audit": "audit",
    "auditd": "audit",
    "polkitd": "authentication",
}


@register_parser
class LinuxSyslogParser(BaseParser):
    """Parser for Linux syslog files."""

    @property
    def name(self) -> str:
        return "linux_syslog"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "Linux syslog, messages, and kern.log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".log", ".1", ".2", ".gz"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check for syslog format."""
        if file_path:
            name = file_path.name.lower()
            syslog_names = [
                "syslog",
                "messages",
                "kern.log",
                "daemon.log",
                "user.log",
                "mail.log",
                "debug",
            ]
            if any(name.startswith(n) for n in syslog_names):
                return True

        if content:
            try:
                text = content.decode("utf-8", errors="ignore")[:2000]
                # Check for syslog patterns
                for pattern in SYSLOG_PATTERNS:
                    if pattern.search(text):
                        return True
            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse syslog file."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        try:
            # Handle gzipped files
            if isinstance(source, Path) and source.suffix == ".gz":
                import gzip

                opener = gzip.open(source, "rt", encoding="utf-8", errors="ignore")
            elif isinstance(source, Path):
                opener = open(source, encoding="utf-8", errors="ignore")
            else:
                import io

                content = source.read()
                if content[:2] == b"\x1f\x8b":
                    import gzip

                    content = gzip.decompress(content)
                text = content.decode("utf-8", errors="ignore")
                opener = io.StringIO(text)

            with opener as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    event = self._parse_line(line, source_str, line_num)
                    if event:
                        yield event

        except Exception as e:
            logger.error(f"Failed to parse syslog {source_str}: {e}")
            raise

    def _parse_line(self, line: str, source_name: str, line_num: int) -> ParsedEvent | None:
        """Parse a single syslog line."""
        for pattern in SYSLOG_PATTERNS:
            match = pattern.match(line)
            if match:
                return self._create_event(match, source_name, line_num)

        # Fallback for unmatched lines
        return None

    def _create_event(self, match: re.Match, source_name: str, line_num: int) -> ParsedEvent:
        """Create ParsedEvent from regex match."""
        groups = match.groupdict()

        # Parse timestamp
        timestamp = self._parse_timestamp(groups)

        hostname = groups.get("hostname")
        process = groups.get("process") or groups.get("appname")
        pid = groups.get("pid") or groups.get("procid")
        message = groups.get("message", "")

        if pid and pid != "-":
            pid = int(pid)
        else:
            pid = None

        # Determine category based on process
        category = "system"
        if process:
            process_lower = process.lower().strip()
            category = PROCESS_CATEGORIES.get(process_lower, "system")

        # Parse priority if present
        priority = None
        facility = None
        severity = None
        if groups.get("pri"):
            pri = int(groups["pri"])
            facility = pri >> 3
            severity = pri & 7

        # Map to ECS categories
        ecs_categories = ["host"]
        if category == "authentication":
            ecs_categories = ["authentication"]
        elif category == "network":
            ecs_categories = ["network"]
        elif category == "kernel":
            ecs_categories = ["host", "driver"]

        # Truncate message for event message field
        event_message = message[:200] + "..." if len(message) > 200 else message

        raw = {
            "raw_message": message,
        }
        if priority is not None:
            raw["priority"] = priority
            raw["facility"] = facility
            raw["severity"] = severity

        tags = ["syslog"]
        if category != "system":
            tags.append(category)

        return ParsedEvent(
            timestamp=timestamp,
            message=event_message,
            source_type="linux_syslog",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_category=ecs_categories,
            event_type=["info"],
            event_action="syslog_entry",
            host_name=hostname,
            process_name=process.strip() if process else None,
            process_pid=pid,
            raw=raw,
            labels={
                "log_category": category,
                "process": process.strip() if process else "",
            },
            tags=tags,
        )

    def _parse_timestamp(self, groups: dict) -> datetime:
        """Parse timestamp from matched groups."""
        # Try ISO format first
        if groups.get("timestamp"):
            ts_str = groups["timestamp"]
            try:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Try traditional syslog format
        if groups.get("month") and groups.get("day") and groups.get("time"):
            month_map = {
                "Jan": 1,
                "Feb": 2,
                "Mar": 3,
                "Apr": 4,
                "May": 5,
                "Jun": 6,
                "Jul": 7,
                "Aug": 8,
                "Sep": 9,
                "Oct": 10,
                "Nov": 11,
                "Dec": 12,
            }

            month = month_map.get(groups["month"], 1)
            day = int(groups["day"])
            time_str = groups["time"]
            current_year = datetime.now().year

            try:
                ts = datetime.strptime(
                    f"{current_year} {month} {day} {time_str}", "%Y %m %d %H:%M:%S"
                )
                return ts.replace(tzinfo=UTC)
            except ValueError:
                pass

        return datetime.now(UTC)
