"""Linux authentication log parser.

Parses Linux auth.log, secure, and similar authentication log files
to extract authentication events.
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

# Common auth log patterns
AUTH_PATTERNS = {
    # SSH authentication
    "ssh_accepted": re.compile(
        r"Accepted\s+(?P<method>\S+)\s+for\s+(?P<user>\S+)\s+from\s+(?P<src_ip>\S+)\s+port\s+(?P<src_port>\d+)"
    ),
    "ssh_failed": re.compile(
        r"Failed\s+(?P<method>\S+)\s+for\s+(?:invalid user\s+)?(?P<user>\S+)\s+from\s+(?P<src_ip>\S+)\s+port\s+(?P<src_port>\d+)"
    ),
    "ssh_invalid_user": re.compile(r"Invalid user\s+(?P<user>\S+)\s+from\s+(?P<src_ip>\S+)"),
    "ssh_disconnect": re.compile(
        r"Disconnected from\s+(?:user\s+(?P<user>\S+)\s+)?(?P<src_ip>\S+)\s+port\s+(?P<src_port>\d+)"
    ),
    "ssh_connection_closed": re.compile(
        r"Connection closed by\s+(?:(?P<type>authenticating|invalid)\s+user\s+)?(?P<user>\S+)?\s*(?P<src_ip>\S+)\s+port\s+(?P<src_port>\d+)"
    ),
    # sudo events
    "sudo_command": re.compile(
        r"(?P<user>\S+)\s+:\s+TTY=(?P<tty>\S+)\s+;\s+PWD=(?P<pwd>[^;]+)\s*;\s+USER=(?P<target_user>\S+)\s*;\s+COMMAND=(?P<command>.+)"
    ),
    "sudo_failed": re.compile(
        r"(?P<user>\S+)\s+:\s+(?P<attempts>\d+)\s+incorrect password attempts?"
    ),
    "sudo_auth_failure": re.compile(
        r"pam_unix\(sudo:auth\):\s+authentication failure;.*user=(?P<user>\S+)"
    ),
    # su events
    "su_success": re.compile(r"Successful su for\s+(?P<target_user>\S+)\s+by\s+(?P<user>\S+)"),
    "su_failed": re.compile(r"FAILED su for\s+(?P<target_user>\S+)\s+by\s+(?P<user>\S+)"),
    "su_session": re.compile(
        r"pam_unix\(su(?:-l)?:session\):\s+session\s+(?P<action>opened|closed)\s+for user\s+(?P<target_user>\S+)(?:\s+by\s+(?P<user>\S+)|\(uid=(?P<uid>\d+)\))?"
    ),
    # PAM events
    "pam_session": re.compile(
        r"pam_unix\((?P<service>\S+):session\):\s+session\s+(?P<action>opened|closed)\s+for user\s+(?P<user>\S+)"
    ),
    "pam_auth_failure": re.compile(
        r"pam_unix\((?P<service>\S+):auth\):\s+authentication failure;.*user=(?P<user>\S+)"
    ),
    # User/group management
    "useradd": re.compile(r"new user: name=(?P<user>\S+),\s*UID=(?P<uid>\d+),\s*GID=(?P<gid>\d+)"),
    "userdel": re.compile(r"delete user '(?P<user>\S+)'"),
    "usermod": re.compile(r"change user '(?P<user>\S+)'"),
    "groupadd": re.compile(r"new group: name=(?P<group>\S+),\s*GID=(?P<gid>\d+)"),
    "passwd_change": re.compile(r"password changed for\s+(?P<user>\S+)"),
    # System events
    "cron_session": re.compile(
        r"pam_unix\(cron:session\):\s+session\s+(?P<action>opened|closed)\s+for user\s+(?P<user>\S+)"
    ),
}

# Syslog timestamp pattern
SYSLOG_TS_PATTERN = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})"
)


@register_parser
class LinuxAuthLogParser(BaseParser):
    """Parser for Linux authentication log files."""

    @property
    def name(self) -> str:
        return "linux_auth"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "Linux auth.log and secure log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".log", ".1", ".2", ".gz"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/plain", "application/gzip"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if this is a Linux auth log."""
        if file_path:
            name = file_path.name.lower()
            if name in ("auth.log", "secure", "auth", "auth.log.1", "secure.1"):
                return True
            if name.startswith(("auth.log", "secure")):
                return True

        if content:
            try:
                text = content.decode("utf-8", errors="ignore")[:2000]
                # Check for common auth log indicators
                auth_indicators = [
                    "sshd[",
                    "sudo:",
                    "su[",
                    "pam_unix",
                    "systemd-logind",
                    "Accepted password",
                    "Failed password",
                    "session opened",
                ]
                if any(ind in text for ind in auth_indicators):
                    return True
            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse auth log file."""
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
                # Check if gzipped
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
            logger.error(f"Failed to parse auth log {source_str}: {e}")
            raise

    def _parse_line(self, line: str, source_name: str, line_num: int) -> ParsedEvent | None:
        """Parse a single log line."""
        try:
            # Extract timestamp
            timestamp = self._parse_timestamp(line)

            # Extract hostname and process
            hostname = None
            process = None
            pid = None

            # Standard syslog format: Month Day Time Hostname Process[PID]: Message
            parts = line.split(None, 5)
            if len(parts) >= 5:
                hostname = parts[3]
                process_part = parts[4]
                if "[" in process_part:
                    process = process_part.split("[")[0]
                    pid_match = re.search(r"\[(\d+)\]", process_part)
                    if pid_match:
                        pid = int(pid_match.group(1))
                else:
                    process = process_part.rstrip(":")

            # Try each pattern
            for pattern_name, pattern in AUTH_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    return self._create_event(
                        pattern_name,
                        match,
                        line,
                        timestamp,
                        hostname,
                        process,
                        pid,
                        source_name,
                        line_num,
                    )

            # Generic parsing for unmatched lines if they contain auth keywords
            if any(kw in line.lower() for kw in ["auth", "login", "password", "session", "user"]):
                return self._create_generic_event(
                    line, timestamp, hostname, process, pid, source_name, line_num
                )

            return None

        except Exception as e:
            logger.debug(f"Failed to parse line {line_num}: {e}")
            return None

    def _parse_timestamp(self, line: str) -> datetime:
        """Parse syslog timestamp from line."""
        match = SYSLOG_TS_PATTERN.match(line)
        if not match:
            return datetime.now(UTC)

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

        month = month_map.get(match.group("month"), 1)
        day = int(match.group("day"))
        time_str = match.group("time")

        # Use current year since syslog doesn't include year
        current_year = datetime.now().year

        try:
            ts = datetime.strptime(f"{current_year} {month} {day} {time_str}", "%Y %m %d %H:%M:%S")
            return ts.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    def _create_event(
        self,
        pattern_name: str,
        match: re.Match,
        line: str,
        timestamp: datetime,
        hostname: str | None,
        process: str | None,
        pid: int | None,
        source_name: str,
        line_num: int,
    ) -> ParsedEvent:
        """Create ParsedEvent from pattern match."""
        groups = match.groupdict()

        # Determine event category and type based on pattern
        category_map = {
            "ssh_accepted": (["authentication"], ["start"], "ssh_login_success", "success"),
            "ssh_failed": (["authentication"], ["start"], "ssh_login_failure", "failure"),
            "ssh_invalid_user": (["authentication"], ["start"], "ssh_invalid_user", "failure"),
            "ssh_disconnect": (["authentication"], ["end"], "ssh_disconnect", None),
            "ssh_connection_closed": (["authentication"], ["end"], "ssh_connection_closed", None),
            "sudo_command": (["process"], ["start"], "sudo_command", "success"),
            "sudo_failed": (["authentication"], ["start"], "sudo_auth_failure", "failure"),
            "sudo_auth_failure": (["authentication"], ["start"], "sudo_auth_failure", "failure"),
            "su_success": (["authentication"], ["start"], "su_success", "success"),
            "su_failed": (["authentication"], ["start"], "su_failure", "failure"),
            "su_session": (["authentication"], ["info"], "su_session", None),
            "pam_session": (["authentication"], ["info"], "session_change", None),
            "pam_auth_failure": (["authentication"], ["start"], "pam_auth_failure", "failure"),
            "useradd": (["iam"], ["user", "creation"], "user_created", "success"),
            "userdel": (["iam"], ["user", "deletion"], "user_deleted", "success"),
            "usermod": (["iam"], ["user", "change"], "user_modified", "success"),
            "groupadd": (["iam"], ["group", "creation"], "group_created", "success"),
            "passwd_change": (["iam"], ["user", "change"], "password_changed", "success"),
            "cron_session": (["process"], ["info"], "cron_session", None),
        }

        categories, types, action, outcome = category_map.get(
            pattern_name, (["authentication"], ["info"], pattern_name, None)
        )

        # Build message
        message = f"{action.replace('_', ' ').title()}"
        if groups.get("user"):
            message += f": {groups['user']}"
        if groups.get("src_ip"):
            message += f" from {groups['src_ip']}"

        # Build raw data
        raw = {"pattern": pattern_name, **groups}

        # Extract network info
        src_ip = groups.get("src_ip")
        src_port = groups.get("src_port")
        if src_port:
            src_port = int(src_port)

        # Extract command for sudo events
        command_line = groups.get("command")

        tags = ["linux_auth"]
        if "ssh" in pattern_name:
            tags.append("ssh")
        if "sudo" in pattern_name:
            tags.append("sudo")
        if "su_" in pattern_name:
            tags.append("su")
        if outcome == "failure":
            tags.append("auth_failure")

        return ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="linux_auth",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_category=categories,
            event_type=types,
            event_action=action,
            event_outcome=outcome,
            host_name=hostname,
            user_name=groups.get("user"),
            source_ip=src_ip,
            source_port=src_port,
            process_name=process,
            process_pid=pid,
            process_command_line=command_line,
            raw=raw,
            labels={
                "process": process or "",
                "auth_pattern": pattern_name,
            },
            tags=tags,
        )

    def _create_generic_event(
        self,
        line: str,
        timestamp: datetime,
        hostname: str | None,
        process: str | None,
        pid: int | None,
        source_name: str,
        line_num: int,
    ) -> ParsedEvent:
        """Create generic event for unmatched auth-related lines."""
        # Truncate long lines
        message = line[:200] + "..." if len(line) > 200 else line

        return ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="linux_auth",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_category=["authentication"],
            event_type=["info"],
            event_action="auth_log_entry",
            host_name=hostname,
            process_name=process,
            process_pid=pid,
            raw={"raw_line": line},
            labels={
                "process": process or "",
            },
            tags=["linux_auth"],
        )
