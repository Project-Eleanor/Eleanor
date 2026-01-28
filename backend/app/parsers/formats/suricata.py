"""Suricata IDS/IPS log parser.

Parses Suricata EVE JSON logs and fast.log alert format.
EVE JSON is the primary format containing alerts, flows, HTTP, DNS, TLS, etc.
"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)


# Suricata EVE event type to ECS category mapping
SURICATA_CATEGORY_MAP = {
    "alert": ["intrusion_detection"],
    "anomaly": ["intrusion_detection"],
    "flow": ["network"],
    "http": ["web", "network"],
    "dns": ["network"],
    "tls": ["network"],
    "fileinfo": ["file"],
    "smtp": ["email"],
    "ssh": ["authentication", "network"],
    "stats": ["host"],
    "dhcp": ["network"],
    "nfs": ["network"],
    "smb": ["network"],
    "krb5": ["authentication"],
    "ikev2": ["network"],
    "tftp": ["network"],
    "rdp": ["network"],
    "snmp": ["network"],
    "sip": ["network"],
    "rfb": ["network"],
    "mqtt": ["network"],
    "http2": ["web", "network"],
    "pgsql": ["database"],
    "quic": ["network"],
}

# Suricata severity mapping
SEVERITY_MAP = {
    1: 100,  # High (Critical)
    2: 70,  # Medium (High)
    3: 40,  # Low (Medium)
    4: 10,  # Informational
}


@register_parser
class SuricataParser(BaseParser):
    """Parser for Suricata IDS/IPS logs."""

    @property
    def name(self) -> str:
        return "suricata"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.NETWORK

    @property
    def description(self) -> str:
        return "Suricata IDS/IPS EVE JSON and fast.log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".log"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json", "text/plain"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is Suricata log format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:10]:
                    line = line.strip()
                    if not line:
                        continue

                    # Check for EVE JSON format
                    if line.startswith("{"):
                        try:
                            data = json.loads(line)
                            if "event_type" in data and "timestamp" in data:
                                return True
                            if data.get("event_type") in SURICATA_CATEGORY_MAP:
                                return True
                        except json.JSONDecodeError:
                            pass

                    # Check for fast.log format
                    if "**" in line and "Priority:" in line and "Classification:" in line:
                        return True
                    if "[**]" in line and "[" in line:
                        return True

            except Exception:
                pass

        if file_path:
            name = file_path.name.lower()
            if "eve" in name and name.endswith(".json"):
                return True
            if name in ("fast.log", "suricata.log", "eve.json"):
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse Suricata log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_file(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Detect format and parse file."""
        first_line = file_handle.readline()
        if not first_line:
            return

        first_line = first_line.strip()
        file_handle.seek(0)

        # Detect format
        if first_line.startswith("{"):
            yield from self._parse_eve_json(file_handle, source_name)
        else:
            yield from self._parse_fast_log(file_handle, source_name)

    def _parse_eve_json(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse EVE JSON format."""
        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                event = self._parse_eve_record(record, source_name, line_num)
                if event:
                    yield event
            except json.JSONDecodeError as e:
                logger.debug(f"JSON parse error at line {line_num}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Parse error at line {line_num}: {e}")
                continue

    def _parse_eve_record(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse a single EVE JSON record."""
        event_type = record.get("event_type", "unknown")

        # Extract timestamp
        timestamp = self._parse_timestamp(record.get("timestamp"))

        # Generate message
        message = self._generate_message(record, event_type)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type=f"suricata:{event_type}",
            source_file=source_name,
            source_line=line_num,
        )

        # Set categories
        event.event_category = SURICATA_CATEGORY_MAP.get(event_type, ["network"])

        # Map common fields
        self._map_common_fields(event, record)

        # Map event-type specific fields
        if event_type == "alert":
            self._map_alert(event, record)
        elif event_type == "flow":
            self._map_flow(event, record)
        elif event_type == "http":
            self._map_http(event, record)
        elif event_type == "dns":
            self._map_dns(event, record)
        elif event_type == "tls":
            self._map_tls(event, record)
        elif event_type == "fileinfo":
            self._map_fileinfo(event, record)
        elif event_type == "ssh":
            self._map_ssh(event, record)
        elif event_type == "smtp":
            self._map_smtp(event, record)
        elif event_type == "anomaly":
            self._map_anomaly(event, record)
        else:
            event.event_type = ["info"]

        # Store raw data
        event.raw = record

        return event

    def _parse_timestamp(self, ts_str: str | None) -> datetime:
        """Parse Suricata timestamp."""
        if not ts_str:
            return datetime.now(UTC)

        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue

        # Try ISO format
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        return datetime.now(UTC)

    def _generate_message(self, record: dict, event_type: str) -> str:
        """Generate message based on event type."""
        src = record.get("src_ip", "?")
        dst = record.get("dest_ip", "?")
        dport = record.get("dest_port", "?")

        if event_type == "alert":
            alert = record.get("alert", {})
            signature = alert.get("signature", "Unknown alert")
            return f"Alert: {signature} ({src} -> {dst}:{dport})"

        elif event_type == "http":
            http = record.get("http", {})
            method = http.get("http_method", "GET")
            host = http.get("hostname", dst)
            uri = http.get("url", "/")
            return f"HTTP {method} {host}{uri}"

        elif event_type == "dns":
            dns = record.get("dns", {})
            qtype = dns.get("rrtype", "A")
            query = dns.get("rrname", "?")
            return f"DNS {qtype} query: {query}"

        elif event_type == "tls":
            tls = record.get("tls", {})
            sni = tls.get("sni", dst)
            version = tls.get("version", "?")
            return f"TLS to {sni} ({version})"

        elif event_type == "flow":
            proto = record.get("proto", "?")
            return f"Flow {src} -> {dst}:{dport} ({proto})"

        elif event_type == "fileinfo":
            fileinfo = record.get("fileinfo", {})
            filename = fileinfo.get("filename", "unknown")
            return f"File: {filename}"

        elif event_type == "ssh":
            ssh = record.get("ssh", {})
            client = ssh.get("client", {}).get("software_version", "?")
            return f"SSH connection from {src} (client: {client})"

        else:
            return f"Suricata {event_type}: {src} -> {dst}"

    def _map_common_fields(self, event: ParsedEvent, record: dict) -> None:
        """Map common Suricata fields to ECS."""
        # Source
        if "src_ip" in record:
            event.source_ip = record["src_ip"]
        if "src_port" in record:
            event.source_port = record["src_port"]

        # Destination
        if "dest_ip" in record:
            event.destination_ip = record["dest_ip"]
        if "dest_port" in record:
            event.destination_port = record["dest_port"]

        # Protocol
        if "proto" in record:
            event.network_protocol = record["proto"].lower()

        # App protocol
        if "app_proto" in record:
            event.labels["app_protocol"] = record["app_proto"]

        # Flow ID
        if "flow_id" in record:
            event.labels["flow_id"] = str(record["flow_id"])

        # Community ID (for correlation with Zeek)
        if "community_id" in record:
            event.labels["community_id"] = record["community_id"]

        # In reply to
        if "in_iface" in record:
            event.labels["interface"] = record["in_iface"]

    def _map_alert(self, event: ParsedEvent, record: dict) -> None:
        """Map alert-specific fields."""
        event.event_kind = "alert"
        event.event_type = ["info"]

        alert = record.get("alert", {})

        # Signature info
        event.event_action = alert.get("signature", "unknown")
        event.labels["signature_id"] = str(alert.get("signature_id", ""))
        event.labels["gid"] = str(alert.get("gid", ""))
        event.labels["rev"] = str(alert.get("rev", ""))

        # Category
        if "category" in alert:
            event.labels["alert_category"] = alert["category"]

        # Severity
        severity = alert.get("severity", 3)
        event.event_severity = SEVERITY_MAP.get(severity, 40)

        # Metadata
        if "metadata" in alert:
            meta = alert["metadata"]
            if isinstance(meta, dict):
                for key, value in meta.items():
                    if isinstance(value, list):
                        event.labels[f"meta_{key}"] = ", ".join(str(v) for v in value)
                    else:
                        event.labels[f"meta_{key}"] = str(value)

        # Tags from rule
        if "tags" in alert:
            event.tags = alert["tags"] if isinstance(alert["tags"], list) else [alert["tags"]]

        # Payload
        if "payload" in record:
            event.labels["has_payload"] = "true"
        if "payload_printable" in record:
            event.labels["payload_preview"] = record["payload_printable"][:200]

    def _map_flow(self, event: ParsedEvent, record: dict) -> None:
        """Map flow-specific fields."""
        event.event_type = ["connection"]

        flow = record.get("flow", {})

        if "bytes_toserver" in flow:
            event.labels["bytes_out"] = str(flow["bytes_toserver"])
        if "bytes_toclient" in flow:
            event.labels["bytes_in"] = str(flow["bytes_toclient"])
        if "pkts_toserver" in flow:
            event.labels["packets_out"] = str(flow["pkts_toserver"])
        if "pkts_toclient" in flow:
            event.labels["packets_in"] = str(flow["pkts_toclient"])

        if "state" in flow:
            state = flow["state"]
            event.labels["flow_state"] = state
            if state in ("closed", "established"):
                event.event_outcome = "success"
            elif state in ("new", "syn_sent"):
                event.event_outcome = "unknown"

        if "reason" in flow:
            event.labels["flow_reason"] = flow["reason"]

    def _map_http(self, event: ParsedEvent, record: dict) -> None:
        """Map HTTP-specific fields."""
        event.event_type = ["access"]
        event.event_action = "http-request"

        http = record.get("http", {})

        # URL
        host = http.get("hostname", record.get("dest_ip", ""))
        uri = http.get("url", "/")
        if host:
            event.url_full = f"http://{host}{uri}"
            event.url_domain = host

        # Method
        if "http_method" in http:
            event.labels["http_method"] = http["http_method"]

        # Response
        if "status" in http:
            code = http["status"]
            event.labels["http_status"] = str(code)
            if 200 <= code < 400:
                event.event_outcome = "success"
            elif code >= 400:
                event.event_outcome = "failure"

        # Headers
        if "http_user_agent" in http:
            event.labels["user_agent"] = http["http_user_agent"]
        if "http_refer" in http:
            event.labels["http_referrer"] = http["http_refer"]
        if "http_content_type" in http:
            event.labels["content_type"] = http["http_content_type"]

        # Length
        if "length" in http:
            event.labels["http_length"] = str(http["length"])

    def _map_dns(self, event: ParsedEvent, record: dict) -> None:
        """Map DNS-specific fields."""
        event.event_type = ["protocol"]
        event.event_action = "dns-query"

        dns = record.get("dns", {})

        if "rrname" in dns:
            event.url_domain = dns["rrname"]

        if "rrtype" in dns:
            event.labels["dns_query_type"] = dns["rrtype"]

        if "rcode" in dns:
            rcode = dns["rcode"]
            event.labels["dns_rcode"] = rcode
            if rcode == "NOERROR":
                event.event_outcome = "success"
            else:
                event.event_outcome = "failure"

        if "type" in dns:
            event.labels["dns_type"] = dns["type"]

        # Answers
        if "answers" in dns:
            answers = dns["answers"]
            if isinstance(answers, list):
                event.labels["dns_answers"] = ", ".join(
                    str(a.get("rdata", "")) for a in answers[:5]
                )

        # Grouped for query/answer
        if "grouped" in dns:
            grouped = dns["grouped"]
            for key, values in grouped.items():
                if isinstance(values, list):
                    event.labels[f"dns_{key.lower()}"] = ", ".join(str(v) for v in values[:5])

    def _map_tls(self, event: ParsedEvent, record: dict) -> None:
        """Map TLS-specific fields."""
        event.event_type = ["connection"]
        event.event_action = "tls-handshake"

        tls = record.get("tls", {})

        if "sni" in tls:
            event.url_domain = tls["sni"]

        if "version" in tls:
            event.labels["tls_version"] = tls["version"]

        if "ja3" in tls:
            ja3 = tls["ja3"]
            if "hash" in ja3:
                event.labels["ja3_hash"] = ja3["hash"]

        if "ja3s" in tls:
            ja3s = tls["ja3s"]
            if "hash" in ja3s:
                event.labels["ja3s_hash"] = ja3s["hash"]

        if "subject" in tls:
            event.labels["cert_subject"] = tls["subject"]
        if "issuerdn" in tls:
            event.labels["cert_issuer"] = tls["issuerdn"]

        if "fingerprint" in tls:
            event.labels["cert_fingerprint"] = tls["fingerprint"]

        if "notbefore" in tls:
            event.labels["cert_not_before"] = tls["notbefore"]
        if "notafter" in tls:
            event.labels["cert_not_after"] = tls["notafter"]

    def _map_fileinfo(self, event: ParsedEvent, record: dict) -> None:
        """Map file info fields."""
        event.event_category = ["file"]
        event.event_type = ["creation"]

        fileinfo = record.get("fileinfo", {})

        if "filename" in fileinfo:
            event.file_name = fileinfo["filename"]

        if "magic" in fileinfo:
            event.labels["file_magic"] = fileinfo["magic"]

        if "md5" in fileinfo:
            event.file_hash_md5 = fileinfo["md5"]
        if "sha1" in fileinfo:
            event.file_hash_sha1 = fileinfo["sha1"]
        if "sha256" in fileinfo:
            event.file_hash_sha256 = fileinfo["sha256"]

        if "size" in fileinfo:
            event.labels["file_size"] = str(fileinfo["size"])

        if "stored" in fileinfo:
            event.labels["file_stored"] = str(fileinfo["stored"])

        if "state" in fileinfo:
            event.labels["file_state"] = fileinfo["state"]

    def _map_ssh(self, event: ParsedEvent, record: dict) -> None:
        """Map SSH-specific fields."""
        event.event_category = ["authentication", "network"]
        event.event_type = ["start"]
        event.event_action = "ssh-connection"

        ssh = record.get("ssh", {})

        client = ssh.get("client", {})
        server = ssh.get("server", {})

        if "software_version" in client:
            event.labels["ssh_client"] = client["software_version"]
        if "proto_version" in client:
            event.labels["ssh_client_proto"] = client["proto_version"]

        if "software_version" in server:
            event.labels["ssh_server"] = server["software_version"]

    def _map_smtp(self, event: ParsedEvent, record: dict) -> None:
        """Map SMTP-specific fields."""
        event.event_category = ["email"]
        event.event_type = ["info"]
        event.event_action = "smtp-transaction"

        smtp = record.get("smtp", {})

        if "mail_from" in smtp:
            event.labels["email_from"] = smtp["mail_from"]
        if "rcpt_to" in smtp:
            rcpts = smtp["rcpt_to"]
            if isinstance(rcpts, list):
                event.labels["email_to"] = ", ".join(rcpts)
            else:
                event.labels["email_to"] = rcpts

        if "helo" in smtp:
            event.labels["smtp_helo"] = smtp["helo"]

    def _map_anomaly(self, event: ParsedEvent, record: dict) -> None:
        """Map anomaly-specific fields."""
        event.event_kind = "alert"
        event.event_type = ["info"]

        anomaly = record.get("anomaly", {})

        if "type" in anomaly:
            event.event_action = anomaly["type"]

        if "event" in anomaly:
            event.labels["anomaly_event"] = anomaly["event"]

        if "layer" in anomaly:
            event.labels["anomaly_layer"] = anomaly["layer"]

    def _parse_fast_log(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse fast.log format."""
        import re

        # fast.log format:
        # MM/DD/YYYY-HH:MM:SS.NNNNNN  [**] [gid:sid:rev] signature [**] [Classification: class] [Priority: N] {proto} src:port -> dst:port
        pattern = re.compile(
            r"(\d{2}/\d{2}/\d{4}-\d{2}:\d{2}:\d{2}\.\d+)\s+"
            r"\[\*\*\]\s+\[(\d+):(\d+):(\d+)\]\s+(.+?)\s+\[\*\*\]\s+"
            r"\[Classification:\s*([^\]]*)\]\s+"
            r"\[Priority:\s*(\d+)\]\s+"
            r"\{(\w+)\}\s+"
            r"(\d+\.\d+\.\d+\.\d+):(\d+)\s+->\s+(\d+\.\d+\.\d+\.\d+):(\d+)"
        )

        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if not match:
                continue

            try:
                (
                    timestamp_str,
                    gid,
                    sid,
                    rev,
                    signature,
                    classification,
                    priority,
                    proto,
                    src_ip,
                    src_port,
                    dst_ip,
                    dst_port,
                ) = match.groups()

                # Parse timestamp
                try:
                    timestamp = datetime.strptime(timestamp_str, "%m/%d/%Y-%H:%M:%S.%f")
                    timestamp = timestamp.replace(tzinfo=UTC)
                except ValueError:
                    timestamp = datetime.now(UTC)

                event = ParsedEvent(
                    timestamp=timestamp,
                    message=f"Alert: {signature} ({src_ip}:{src_port} -> {dst_ip}:{dst_port})",
                    source_type="suricata:alert",
                    source_file=source_name,
                    source_line=line_num,
                    event_kind="alert",
                    event_category=["intrusion_detection"],
                    event_type=["info"],
                    event_action=signature,
                    event_severity=SEVERITY_MAP.get(int(priority), 40),
                    source_ip=src_ip,
                    source_port=int(src_port),
                    destination_ip=dst_ip,
                    destination_port=int(dst_port),
                    network_protocol=proto.lower(),
                )

                event.labels = {
                    "gid": gid,
                    "signature_id": sid,
                    "rev": rev,
                    "alert_category": classification.strip(),
                    "priority": priority,
                }

                event.raw = {"raw_line": line}

                yield event

            except Exception as e:
                logger.debug(f"Failed to parse fast.log line {line_num}: {e}")
                continue
