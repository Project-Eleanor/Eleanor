"""Zeek (formerly Bro) network security monitor log parser.

Parses Zeek log files in TSV format with the standard field definitions.
Supports conn, dns, http, ssl, x509, files, notice, and other log types.
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# Zeek log type to ECS category mapping
ZEEK_CATEGORY_MAP = {
    "conn": ["network"],
    "dns": ["network"],
    "http": ["web", "network"],
    "ssl": ["network"],
    "x509": ["network"],
    "files": ["file"],
    "smtp": ["email"],
    "ftp": ["network"],
    "ssh": ["authentication", "network"],
    "rdp": ["network"],
    "dhcp": ["network"],
    "ntp": ["network"],
    "kerberos": ["authentication"],
    "ntlm": ["authentication"],
    "smb_files": ["file"],
    "smb_mapping": ["network"],
    "pe": ["file"],
    "notice": ["intrusion_detection"],
    "weird": ["intrusion_detection"],
    "intel": ["threat"],
    "software": ["package"],
    "known_hosts": ["host"],
    "known_services": ["network"],
    "tunnel": ["network"],
}


@register_parser
class ZeekParser(BaseParser):
    """Parser for Zeek network security monitor logs."""

    @property
    def name(self) -> str:
        return "zeek"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.NETWORK

    @property
    def description(self) -> str:
        return "Zeek (Bro) network security monitor log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".log", ".zeek"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["text/plain", "application/octet-stream"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is Zeek log format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.split("\n")

                # Look for Zeek header markers
                for line in lines[:20]:
                    if line.startswith("#separator"):
                        return True
                    if line.startswith("#fields"):
                        return True
                    if line.startswith("#path"):
                        return True

            except Exception:
                pass

        if file_path:
            # Common Zeek log file names
            name = file_path.name.lower()
            zeek_names = [
                "conn.log",
                "dns.log",
                "http.log",
                "ssl.log",
                "x509.log",
                "files.log",
                "smtp.log",
                "ftp.log",
                "ssh.log",
                "rdp.log",
                "dhcp.log",
                "kerberos.log",
                "ntlm.log",
                "notice.log",
                "weird.log",
                "intel.log",
                "pe.log",
                "smb_files.log",
            ]
            if any(name.endswith(zn) or name == zn for zn in zeek_names):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse Zeek log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_file(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse Zeek log with header metadata."""
        separator = "\t"
        fields = []
        types = []
        log_path = "unknown"
        set_separator = ","
        empty_field = "(empty)"
        unset_field = "-"

        line_num = 0
        for line in file_handle:
            line_num += 1
            line = line.rstrip("\n\r")

            if not line:
                continue

            # Parse header lines
            if line.startswith("#"):
                key, _, value = line[1:].partition(" ")
                value = value.strip()

                if key == "separator":
                    # Handle hex-encoded separator
                    if value.startswith("\\x"):
                        separator = bytes.fromhex(value[2:]).decode("utf-8")
                    else:
                        separator = value
                elif key == "fields":
                    fields = value.split(separator)
                elif key == "types":
                    types = value.split(separator)
                elif key == "path":
                    log_path = value
                elif key == "set_separator":
                    set_separator = value
                elif key == "empty_field":
                    empty_field = value
                elif key == "unset_field":
                    unset_field = value
                continue

            if not fields:
                continue

            # Parse data line
            values = line.split(separator)

            if len(values) != len(fields):
                logger.debug(f"Field count mismatch at line {line_num}")
                continue

            try:
                event = self._parse_record(
                    dict(zip(fields, values)),
                    types,
                    fields,
                    log_path,
                    source_name,
                    line_num,
                    set_separator,
                    empty_field,
                    unset_field,
                )
                if event:
                    yield event
            except Exception as e:
                logger.debug(f"Failed to parse line {line_num}: {e}")
                continue

    def _parse_record(
        self,
        record: dict[str, str],
        types: list[str],
        fields: list[str],
        log_path: str,
        source_name: str,
        line_num: int,
        set_separator: str,
        empty_field: str,
        unset_field: str,
    ) -> ParsedEvent | None:
        """Parse a single Zeek record."""
        # Clean up unset/empty values
        cleaned = {}
        for key, value in record.items():
            if value not in (empty_field, unset_field):
                cleaned[key] = value

        # Extract timestamp
        timestamp = self._extract_timestamp(cleaned)

        # Generate message
        message = self._generate_message(cleaned, log_path)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type=f"zeek:{log_path}",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
        )

        # Set categories based on log type
        event.event_category = ZEEK_CATEGORY_MAP.get(log_path, ["network"])
        event.event_type = ["connection"]

        # Map common fields
        self._map_connection_fields(event, cleaned)

        # Map log-type specific fields
        mapper = getattr(self, f"_map_{log_path}", None)
        if mapper:
            mapper(event, cleaned, set_separator)

        # Store raw data
        event.raw = cleaned
        event.labels["zeek_path"] = log_path

        return event

    def _extract_timestamp(self, record: dict[str, str]) -> datetime:
        """Extract timestamp from Zeek record."""
        # Zeek uses Unix epoch with microseconds
        ts_field = record.get("ts")
        if ts_field:
            try:
                epoch = float(ts_field)
                return datetime.fromtimestamp(epoch, tz=UTC)
            except (ValueError, OSError):
                pass
        return datetime.now(UTC)

    def _generate_message(self, record: dict[str, str], log_path: str) -> str:
        """Generate human-readable message."""
        if log_path == "conn":
            src = record.get("id.orig_h", "?")
            dst = record.get("id.resp_h", "?")
            dport = record.get("id.resp_p", "?")
            proto = record.get("proto", "?")
            return f"Connection {src} -> {dst}:{dport} ({proto})"

        elif log_path == "dns":
            query = record.get("query", "?")
            qtype = record.get("qtype_name", "?")
            return f"DNS {qtype} query: {query}"

        elif log_path == "http":
            method = record.get("method", "GET")
            host = record.get("host", "?")
            uri = record.get("uri", "/")
            return f"HTTP {method} {host}{uri}"

        elif log_path == "ssl":
            server_name = record.get("server_name", record.get("id.resp_h", "?"))
            version = record.get("version", "?")
            return f"SSL/TLS to {server_name} ({version})"

        elif log_path == "files":
            filename = record.get("filename", "unknown")
            mime = record.get("mime_type", "?")
            return f"File transfer: {filename} ({mime})"

        elif log_path == "notice":
            note = record.get("note", "?")
            msg = record.get("msg", "")
            return f"Notice: {note} - {msg}"

        elif log_path == "ssh":
            client = record.get("client", "?")
            server = record.get("server", "?")
            return f"SSH connection: {client} -> {server}"

        elif log_path == "smtp":
            from_addr = record.get("from", "?")
            to = record.get("to", "?")
            return f"SMTP: {from_addr} -> {to}"

        else:
            # Generic message
            uid = record.get("uid", "")
            return f"Zeek {log_path}: {uid}"

    def _map_connection_fields(self, event: ParsedEvent, record: dict[str, str]) -> None:
        """Map common Zeek connection fields to ECS."""
        # Source
        if "id.orig_h" in record:
            event.source_ip = record["id.orig_h"]
        if "id.orig_p" in record:
            try:
                event.source_port = int(record["id.orig_p"])
            except ValueError:
                pass

        # Destination
        if "id.resp_h" in record:
            event.destination_ip = record["id.resp_h"]
        if "id.resp_p" in record:
            try:
                event.destination_port = int(record["id.resp_p"])
            except ValueError:
                pass

        # Protocol
        if "proto" in record:
            event.network_protocol = record["proto"].lower()

        # UID as event ID
        if "uid" in record:
            event.labels["zeek_uid"] = record["uid"]

    def _map_conn(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map conn.log specific fields."""
        event.event_type = ["connection"]

        # Connection state
        state = record.get("conn_state", "")
        if state in ("S0", "REJ", "RSTO", "RSTOS0"):
            event.event_outcome = "failure"
        elif state in ("SF", "S1", "S2", "S3", "RSTR"):
            event.event_outcome = "success"

        # Direction
        if "local_orig" in record and "local_resp" in record:
            lo = record["local_orig"] == "T"
            lr = record["local_resp"] == "T"
            if lo and not lr:
                event.network_direction = "outbound"
            elif not lo and lr:
                event.network_direction = "inbound"
            elif lo and lr:
                event.network_direction = "internal"
            else:
                event.network_direction = "external"

        # Service
        if "service" in record:
            event.labels["service"] = record["service"]

        # Bytes
        if "orig_bytes" in record:
            event.labels["bytes_out"] = record["orig_bytes"]
        if "resp_bytes" in record:
            event.labels["bytes_in"] = record["resp_bytes"]

    def _map_dns(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map dns.log specific fields."""
        event.event_category = ["network"]
        event.event_type = ["protocol"]
        event.event_action = "dns-query"

        if "query" in record:
            event.url_domain = record["query"]

        if "rcode_name" in record:
            rcode = record["rcode_name"]
            if rcode == "NOERROR":
                event.event_outcome = "success"
            elif rcode in ("NXDOMAIN", "SERVFAIL", "REFUSED"):
                event.event_outcome = "failure"

        # DNS answers
        if "answers" in record:
            event.labels["dns_answers"] = record["answers"]

        if "qtype_name" in record:
            event.labels["dns_query_type"] = record["qtype_name"]

    def _map_http(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map http.log specific fields."""
        event.event_category = ["web", "network"]
        event.event_type = ["access"]

        if "method" in record:
            event.event_action = record["method"]

        # URL construction
        host = record.get("host", "")
        uri = record.get("uri", "/")
        if host:
            event.url_full = f"http://{host}{uri}"
            event.url_domain = host

        # Response code
        if "status_code" in record:
            try:
                code = int(record["status_code"])
                event.labels["http_status"] = str(code)
                if 200 <= code < 400:
                    event.event_outcome = "success"
                elif code >= 400:
                    event.event_outcome = "failure"
            except ValueError:
                pass

        # User agent
        if "user_agent" in record:
            event.labels["user_agent"] = record["user_agent"]

        # Referrer
        if "referrer" in record:
            event.labels["http_referrer"] = record["referrer"]

    def _map_ssl(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map ssl.log specific fields."""
        event.event_type = ["connection"]
        event.event_action = "tls-handshake"

        if "server_name" in record:
            event.url_domain = record["server_name"]

        if "version" in record:
            event.labels["tls_version"] = record["version"]

        if "cipher" in record:
            event.labels["tls_cipher"] = record["cipher"]

        if "established" in record:
            event.event_outcome = "success" if record["established"] == "T" else "failure"

        if "validation_status" in record:
            event.labels["cert_validation"] = record["validation_status"]

    def _map_x509(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map x509.log specific fields."""
        event.event_type = ["info"]
        event.event_action = "certificate-observed"

        if "certificate.subject" in record:
            event.labels["cert_subject"] = record["certificate.subject"]
        if "certificate.issuer" in record:
            event.labels["cert_issuer"] = record["certificate.issuer"]
        if "san.dns" in record:
            event.labels["cert_san_dns"] = record["san.dns"]

    def _map_files(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map files.log specific fields."""
        event.event_category = ["file"]
        event.event_type = ["creation"]

        if "filename" in record:
            event.file_name = record["filename"]

        if "mime_type" in record:
            event.labels["mime_type"] = record["mime_type"]

        # File hashes
        if "md5" in record:
            event.file_hash_md5 = record["md5"]
        if "sha1" in record:
            event.file_hash_sha1 = record["sha1"]
        if "sha256" in record:
            event.file_hash_sha256 = record["sha256"]

        if "total_bytes" in record:
            event.labels["file_size"] = record["total_bytes"]

    def _map_notice(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map notice.log specific fields."""
        event.event_category = ["intrusion_detection"]
        event.event_kind = "alert"
        event.event_type = ["info"]

        if "note" in record:
            event.event_action = record["note"]

        if "msg" in record:
            event.message = record["msg"]

        # Indicators
        if "src" in record:
            event.source_ip = record["src"]
        if "dst" in record:
            event.destination_ip = record["dst"]

        if "actions" in record:
            event.labels["notice_actions"] = record["actions"]

    def _map_ssh(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map ssh.log specific fields."""
        event.event_category = ["authentication", "network"]
        event.event_type = ["start"]
        event.event_action = "ssh-connection"

        if "auth_success" in record:
            event.event_outcome = "success" if record["auth_success"] == "T" else "failure"

        if "client" in record:
            event.labels["ssh_client"] = record["client"]
        if "server" in record:
            event.labels["ssh_server"] = record["server"]

    def _map_smtp(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map smtp.log specific fields."""
        event.event_category = ["email"]
        event.event_type = ["info"]
        event.event_action = "smtp-transaction"

        if "from" in record:
            event.labels["email_from"] = record["from"]
        if "to" in record:
            event.labels["email_to"] = record["to"]
        if "subject" in record:
            event.labels["email_subject"] = record["subject"]

    def _map_kerberos(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map kerberos.log specific fields."""
        event.event_category = ["authentication"]
        event.event_type = ["start"]
        event.event_action = "kerberos-auth"

        if "client" in record:
            event.user_name = record["client"]

        if "service" in record:
            event.labels["kerberos_service"] = record["service"]

        if "success" in record:
            event.event_outcome = "success" if record["success"] == "T" else "failure"

        if "error_msg" in record:
            event.labels["error_message"] = record["error_msg"]

    def _map_ntlm(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map ntlm.log specific fields."""
        event.event_category = ["authentication"]
        event.event_type = ["start"]
        event.event_action = "ntlm-auth"

        if "username" in record:
            event.user_name = record["username"]
        if "domainname" in record:
            event.user_domain = record["domainname"]
        if "hostname" in record:
            event.host_name = record["hostname"]

        if "success" in record:
            event.event_outcome = "success" if record["success"] == "T" else "failure"

    def _map_intel(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map intel.log specific fields."""
        event.event_category = ["threat"]
        event.event_kind = "alert"
        event.event_type = ["indicator"]

        if "indicator" in record:
            event.labels["indicator"] = record["indicator"]
        if "indicator_type" in record:
            event.labels["indicator_type"] = record["indicator_type"]
        if "seen.where" in record:
            event.labels["seen_where"] = record["seen.where"]
        if "sources" in record:
            event.labels["intel_sources"] = record["sources"]

    def _map_weird(self, event: ParsedEvent, record: dict[str, str], set_sep: str) -> None:
        """Map weird.log specific fields."""
        event.event_category = ["intrusion_detection"]
        event.event_kind = "alert"
        event.event_type = ["info"]

        if "name" in record:
            event.event_action = record["name"]

        if "addl" in record:
            event.labels["additional_info"] = record["addl"]
