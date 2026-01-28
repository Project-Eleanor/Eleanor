"""Web server log parsers.

Parses access and error logs from:
- Apache HTTP Server (Combined/Common log formats)
- Nginx
- Microsoft IIS (W3C Extended Log Format)

Critical for investigating web-based attacks and data exfiltration.
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


@register_parser
class ApacheAccessParser(BaseParser):
    """Parser for Apache HTTP Server access logs."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="apache_access",
            display_name="Apache Access Log Parser",
            description="Parses Apache HTTP Server access logs (Combined/Common format)",
            supported_extensions=[".log", ".txt", ""],
            mime_types=["text/plain"],
            category="webserver",
            priority=70,
        )

    # Combined Log Format:
    # %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"
    COMBINED_PATTERN = re.compile(
        r'^(\S+)\s+'  # Remote host (IP)
        r'(\S+)\s+'  # Ident (usually -)
        r'(\S+)\s+'  # Remote user
        r'\[([^\]]+)\]\s+'  # Timestamp
        r'"([^"]*(?:\\.[^"]*)*)"\s+'  # Request line
        r'(\d{3})\s+'  # Status code
        r'(\S+)'  # Bytes sent
        r'(?:\s+"([^"]*(?:\\.[^"]*)*)"\s+'  # Referer (optional)
        r'"([^"]*(?:\\.[^"]*)*)")?'  # User-Agent (optional)
    )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Apache access log file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    match = self.COMBINED_PATTERN.match(line)
                    if match:
                        entry = self._parse_match(match)
                        entry["log_file"] = str(file_path)
                        entry["line_number"] = line_num
                        yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse Apache access log: {e}")
            raise

    def _parse_match(self, match: re.Match) -> dict[str, Any]:
        """Parse regex match into entry dict."""
        request = match.group(5)
        request_parts = request.split() if request else []

        return {
            "client_ip": match.group(1),
            "ident": match.group(2) if match.group(2) != "-" else None,
            "user": match.group(3) if match.group(3) != "-" else None,
            "timestamp": self._parse_timestamp(match.group(4)),
            "request": request,
            "method": request_parts[0] if len(request_parts) >= 1 else None,
            "uri": request_parts[1] if len(request_parts) >= 2 else None,
            "protocol": request_parts[2] if len(request_parts) >= 3 else None,
            "status_code": int(match.group(6)),
            "bytes_sent": int(match.group(7)) if match.group(7) != "-" else 0,
            "referer": match.group(8) if match.group(8) and match.group(8) != "-" else None,
            "user_agent": match.group(9) if match.group(9) else None,
        }

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Apache entry."""
        timestamp = entry.get("timestamp") or datetime.now(UTC)
        method = entry.get("method", "GET")
        uri = entry.get("uri", "/")
        status = entry.get("status_code", 0)

        # Determine event outcome
        if status >= 500:
            outcome = "failure"
        elif status >= 400:
            outcome = "failure"
        else:
            outcome = "success"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"{method} {uri} - {status}",
            source="apache",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web", "network"],
                    "type": ["access"],
                    "action": "http_request",
                    "outcome": outcome,
                    "module": "apache",
                    "dataset": "apache.access",
                },
                "http": {
                    "request": {
                        "method": method,
                    },
                    "response": {
                        "status_code": status,
                        "bytes": entry.get("bytes_sent"),
                    },
                },
                "url": {
                    "original": uri,
                    "path": uri.split("?")[0] if uri else None,
                    "query": uri.split("?")[1] if uri and "?" in uri else None,
                },
                "source": {
                    "ip": entry.get("client_ip"),
                },
                "user": {
                    "name": entry.get("user"),
                } if entry.get("user") else None,
                "user_agent": {
                    "original": entry.get("user_agent"),
                } if entry.get("user_agent") else None,
                "http.request.referrer": entry.get("referer"),
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "apache_access",
                    "artifact_type": "webserver_access",
                    "protocol": entry.get("protocol"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse Apache timestamp format."""
        try:
            # Format: 10/Oct/2000:13:55:36 -0700
            return datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
        except Exception:
            try:
                # Without timezone
                return datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S").replace(tzinfo=UTC)
            except Exception:
                return None


@register_parser
class NginxAccessParser(ApacheAccessParser):
    """Parser for Nginx access logs (uses same format as Apache by default)."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="nginx_access",
            display_name="Nginx Access Log Parser",
            description="Parses Nginx access logs",
            supported_extensions=[".log", ".txt", ""],
            mime_types=["text/plain"],
            category="webserver",
            priority=70,
        )


@register_parser
class IISParser(BaseParser):
    """Parser for Microsoft IIS logs (W3C Extended Log Format)."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="iis",
            display_name="IIS Log Parser",
            description="Parses Microsoft IIS W3C Extended logs",
            supported_extensions=[".log", ".txt"],
            mime_types=["text/plain"],
            category="webserver",
            priority=70,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse IIS W3C log file."""
        try:
            fields = None

            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    # Parse header lines
                    if line.startswith("#Fields:"):
                        fields = line[8:].strip().split()
                        continue
                    elif line.startswith("#"):
                        continue

                    if fields:
                        entry = self._parse_line(line, fields)
                        if entry:
                            entry["log_file"] = str(file_path)
                            entry["line_number"] = line_num
                            yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse IIS log: {e}")
            raise

    def _parse_line(self, line: str, fields: list[str]) -> dict[str, Any] | None:
        """Parse IIS log line using field headers."""
        values = line.split()
        if len(values) != len(fields):
            return None

        entry = {}
        for field, value in zip(fields, values):
            if value != "-":
                entry[field] = value

        # Parse common fields
        result = {}

        # Date and time
        if "date" in entry and "time" in entry:
            try:
                ts_str = f"{entry['date']} {entry['time']}"
                result["timestamp"] = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=UTC
                )
            except Exception:
                result["timestamp"] = None

        # Client IP
        result["client_ip"] = entry.get("c-ip") or entry.get("cs-ip")

        # Server IP
        result["server_ip"] = entry.get("s-ip")

        # Method, URI, query
        result["method"] = entry.get("cs-method")
        result["uri"] = entry.get("cs-uri-stem")
        result["query"] = entry.get("cs-uri-query")

        # Status and bytes
        if "sc-status" in entry:
            try:
                result["status_code"] = int(entry["sc-status"])
            except ValueError:
                pass

        if "sc-bytes" in entry:
            try:
                result["bytes_sent"] = int(entry["sc-bytes"])
            except ValueError:
                pass

        if "cs-bytes" in entry:
            try:
                result["bytes_received"] = int(entry["cs-bytes"])
            except ValueError:
                pass

        # Time taken
        if "time-taken" in entry:
            try:
                result["time_taken_ms"] = int(entry["time-taken"])
            except ValueError:
                pass

        # User agent and referer
        result["user_agent"] = entry.get("cs(User-Agent)")
        result["referer"] = entry.get("cs(Referer)")

        # User
        result["user"] = entry.get("cs-username")

        # Server info
        result["server_name"] = entry.get("s-computername")
        result["server_port"] = entry.get("s-port")

        # Substatus and win32 status
        result["substatus"] = entry.get("sc-substatus")
        result["win32_status"] = entry.get("sc-win32-status")

        return result

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from IIS entry."""
        timestamp = entry.get("timestamp") or datetime.now(UTC)
        method = entry.get("method", "GET")
        uri = entry.get("uri", "/")
        status = entry.get("status_code", 0)

        # Determine event outcome
        if status >= 400:
            outcome = "failure"
        else:
            outcome = "success"

        # Reconstruct full URL
        full_uri = uri
        if entry.get("query"):
            full_uri = f"{uri}?{entry['query']}"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"{method} {full_uri} - {status}",
            source="iis",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web", "network"],
                    "type": ["access"],
                    "action": "http_request",
                    "outcome": outcome,
                    "module": "iis",
                    "dataset": "iis.access",
                    "duration": entry.get("time_taken_ms", 0) * 1000000 if entry.get("time_taken_ms") else None,
                },
                "http": {
                    "request": {
                        "method": method,
                        "bytes": entry.get("bytes_received"),
                    },
                    "response": {
                        "status_code": status,
                        "bytes": entry.get("bytes_sent"),
                    },
                },
                "url": {
                    "original": full_uri,
                    "path": uri,
                    "query": entry.get("query"),
                },
                "source": {
                    "ip": entry.get("client_ip"),
                },
                "destination": {
                    "ip": entry.get("server_ip"),
                    "port": int(entry["server_port"]) if entry.get("server_port") else None,
                },
                "user": {
                    "name": entry.get("user"),
                } if entry.get("user") else None,
                "user_agent": {
                    "original": entry.get("user_agent"),
                } if entry.get("user_agent") else None,
                "host": {
                    "name": entry.get("server_name"),
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "iis",
                    "artifact_type": "webserver_access",
                    "substatus": entry.get("substatus"),
                    "win32_status": entry.get("win32_status"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )


@register_parser
class ApacheErrorParser(BaseParser):
    """Parser for Apache error logs."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="apache_error",
            display_name="Apache Error Log Parser",
            description="Parses Apache HTTP Server error logs",
            supported_extensions=[".log", ".txt"],
            mime_types=["text/plain"],
            category="webserver",
            priority=70,
        )

    # Apache 2.4 error log format:
    # [Fri Sep 09 10:42:29.902022 2011] [core:error] [pid 35708:tid 4328636416] [client 72.15.99.187:54316] File does not exist: /usr/local/apache2/htdocs/favicon.ico
    ERROR_PATTERN = re.compile(
        r"\[([^\]]+)\]\s+"  # Timestamp
        r"\[([^\]]+)\]\s+"  # Module:Level
        r"\[pid\s+(\d+)(?::tid\s+\d+)?\]\s*"  # PID
        r"(?:\[client\s+([^\]]+)\]\s*)?"  # Client (optional)
        r"(.+)"  # Message
    )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Apache error log file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    match = self.ERROR_PATTERN.match(line)
                    if match:
                        entry = {
                            "timestamp": self._parse_timestamp(match.group(1)),
                            "module_level": match.group(2),
                            "pid": int(match.group(3)),
                            "client": match.group(4),
                            "message": match.group(5),
                            "log_file": str(file_path),
                            "line_number": line_num,
                        }

                        # Parse module and level
                        if ":" in entry["module_level"]:
                            parts = entry["module_level"].split(":", 1)
                            entry["module"] = parts[0]
                            entry["level"] = parts[1]
                        else:
                            entry["level"] = entry["module_level"]

                        yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse Apache error log: {e}")
            raise

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from Apache error entry."""
        timestamp = entry.get("timestamp") or datetime.now(UTC)
        level = entry.get("level", "error").lower()
        message = entry.get("message", "")

        # Map to ECS log level
        if level in ("emerg", "alert", "crit"):
            log_level = "critical"
        elif level == "error":
            log_level = "error"
        elif level == "warn":
            log_level = "warning"
        elif level == "notice":
            log_level = "notice"
        elif level == "info":
            log_level = "info"
        else:
            log_level = "debug"

        # Extract client IP if present
        client_ip = None
        if entry.get("client"):
            client_ip = entry["client"].split(":")[0]

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=f"Apache Error: {message[:200]}",
            source="apache",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["web"],
                    "type": ["error"],
                    "action": "http_error",
                    "module": "apache",
                    "dataset": "apache.error",
                },
                "log": {
                    "level": log_level,
                },
                "message": message,
                "process": {
                    "pid": entry.get("pid"),
                },
                "source": {
                    "ip": client_ip,
                } if client_ip else None,
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "apache_error",
                    "artifact_type": "webserver_error",
                    "apache_module": entry.get("module"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """Parse Apache error log timestamp."""
        try:
            # Format: Fri Sep 09 10:42:29.902022 2011
            # or: Fri Sep 09 10:42:29 2011
            for fmt in [
                "%a %b %d %H:%M:%S.%f %Y",
                "%a %b %d %H:%M:%S %Y",
            ]:
                try:
                    return datetime.strptime(ts_str, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
        except Exception:
            pass
        return None
