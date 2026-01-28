"""GCP Audit Log parser.

Parses Google Cloud Platform audit logs including:
- Admin Activity logs
- Data Access logs
- System Event logs
- Policy Denied logs
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


# GCP service to ECS category mapping
GCP_SERVICE_CATEGORY_MAP = {
    # Compute
    "compute.googleapis.com": ["host"],
    "container.googleapis.com": ["host"],
    "run.googleapis.com": ["host"],
    "appengine.googleapis.com": ["web"],
    "cloudfunctions.googleapis.com": ["process"],
    # Storage
    "storage.googleapis.com": ["file"],
    "bigquery.googleapis.com": ["database"],
    "spanner.googleapis.com": ["database"],
    "firestore.googleapis.com": ["database"],
    "bigtable.googleapis.com": ["database"],
    # IAM/Security
    "iam.googleapis.com": ["iam"],
    "cloudkms.googleapis.com": ["configuration"],
    "secretmanager.googleapis.com": ["configuration"],
    "securitycenter.googleapis.com": ["intrusion_detection"],
    # Network
    "dns.googleapis.com": ["network"],
    "networkmanagement.googleapis.com": ["network"],
    "compute.googleapis.com/firewalls": ["network"],
    # Default
    "default": ["configuration"],
}

# Method patterns to event types
METHOD_PATTERNS = {
    "create": ["creation"],
    "insert": ["creation"],
    "add": ["creation"],
    "delete": ["deletion"],
    "remove": ["deletion"],
    "update": ["change"],
    "patch": ["change"],
    "modify": ["change"],
    "set": ["change"],
    "get": ["access"],
    "list": ["access"],
    "read": ["access"],
}


@register_parser
class GCPAuditLogParser(BaseParser):
    """Parser for GCP Audit Logs."""

    @property
    def name(self) -> str:
        return "gcp_audit"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.CLOUD

    @property
    def description(self) -> str:
        return "Google Cloud Platform audit log parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".jsonl", ".ndjson"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is GCP audit log format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:5]:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        # GCP audit logs have specific fields
                        if "protoPayload" in data and "@type" in data.get("protoPayload", {}):
                            type_url = data["protoPayload"]["@type"]
                            if "AuditLog" in type_url:
                                return True
                        # Also check for Cloud Logging format
                        if "resource" in data and data.get("resource", {}).get("type") in (
                            "gce_instance",
                            "gcs_bucket",
                            "cloud_function",
                            "k8s_cluster",
                            "bigquery_dataset",
                        ):
                            return True
                    except json.JSONDecodeError:
                        pass

            except Exception:
                pass

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse GCP audit log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_lines(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_lines(text_stream, source_str)

    def _parse_lines(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse JSON lines."""
        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                event = self._parse_record(record, source_name, line_num)
                if event:
                    yield event
            except json.JSONDecodeError as e:
                logger.debug(f"JSON parse error at line {line_num}: {e}")
            except Exception as e:
                logger.debug(f"Parse error at line {line_num}: {e}")

    def _parse_record(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse a single GCP audit log record."""
        # Extract proto payload (audit log data)
        proto_payload = record.get("protoPayload", {})
        if not proto_payload:
            # Try direct format (from connector)
            if "_gcp" in record:
                return self._parse_connector_format(record, source_name, line_num)
            return None

        # Extract timestamp
        timestamp = self._parse_timestamp(record)

        # Extract key fields
        service_name = proto_payload.get("serviceName", "")
        method_name = proto_payload.get("methodName", "")
        resource_name = proto_payload.get("resourceName", "")

        # Generate message
        message = self._generate_message(proto_payload)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="gcp_audit",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
        )

        # Set event action
        event.event_action = method_name

        # Set categories
        event.event_category = self._get_categories(service_name)
        event.event_type = self._get_event_type(method_name)

        # Extract user/principal
        auth_info = proto_payload.get("authenticationInfo", {})
        if auth_info.get("principalEmail"):
            event.user_name = auth_info["principalEmail"]
        if auth_info.get("principalSubject"):
            event.user_id = auth_info["principalSubject"]

        # Extract caller IP
        request_metadata = proto_payload.get("requestMetadata", {})
        if request_metadata.get("callerIp"):
            event.source_ip = request_metadata["callerIp"]

        # Set outcome from status
        status = proto_payload.get("status", {})
        status_code = status.get("code", 0)
        if status_code == 0:
            event.event_outcome = "success"
        else:
            event.event_outcome = "failure"

        # Labels
        event.labels = {
            "service_name": service_name,
            "method_name": method_name,
            "resource_name": resource_name[:200] if resource_name else "",
        }

        # Add resource info
        resource = record.get("resource", {})
        if resource:
            event.labels["resource_type"] = resource.get("type", "")
            resource_labels = resource.get("labels", {})
            if "project_id" in resource_labels:
                event.labels["project_id"] = resource_labels["project_id"]
            if "zone" in resource_labels:
                event.labels["zone"] = resource_labels["zone"]

        # Map resource-specific fields
        self._map_resource_fields(event, proto_payload, service_name)

        # Store raw
        event.raw = record

        # Set severity
        severity = record.get("severity", "")
        event.event_severity = self._map_severity(severity)

        return event

    def _parse_connector_format(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse record from GCP connector format."""
        gcp_meta = record.get("_gcp", {})

        timestamp = self._parse_timestamp(record)
        message = record.get("message", str(record))

        event = ParsedEvent(
            timestamp=timestamp,
            message=message[:500] if isinstance(message, str) else str(message)[:500],
            source_type="gcp",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
            event_category=["cloud"],
            event_type=["info"],
        )

        # Extract source from log name
        log_name = gcp_meta.get("logName", "")
        if log_name:
            event.labels["log_name"] = log_name.split("/")[-1]

        # Resource
        resource = gcp_meta.get("resource", {})
        if resource:
            event.labels["resource_type"] = resource.get("type", "")

        event.raw = record

        return event

    def _parse_timestamp(self, record: dict) -> datetime:
        """Parse timestamp from GCP record."""
        # Try different timestamp fields
        for field in ["timestamp", "receiveTimestamp"]:
            if field in record:
                try:
                    ts = record[field]
                    if isinstance(ts, str):
                        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    pass

        return datetime.now(UTC)

    def _generate_message(self, proto_payload: dict) -> str:
        """Generate human-readable message."""
        proto_payload.get("serviceName", "unknown")
        method = proto_payload.get("methodName", "unknown")
        resource = proto_payload.get("resourceName", "")

        # Shorten resource name if too long
        if len(resource) > 100:
            resource = "..." + resource[-97:]

        auth_info = proto_payload.get("authenticationInfo", {})
        principal = auth_info.get("principalEmail", "unknown")

        status = proto_payload.get("status", {})
        status_code = status.get("code", 0)
        outcome = "success" if status_code == 0 else f"failed ({status.get('message', 'error')})"

        return f"GCP: {principal} called {method} on {resource} ({outcome})"

    def _get_categories(self, service_name: str) -> list[str]:
        """Get ECS categories for GCP service."""
        if service_name in GCP_SERVICE_CATEGORY_MAP:
            return GCP_SERVICE_CATEGORY_MAP[service_name]

        # Check partial matches
        for key, cats in GCP_SERVICE_CATEGORY_MAP.items():
            if key in service_name:
                return cats

        return ["cloud"]

    def _get_event_type(self, method_name: str) -> list[str]:
        """Determine event type from method name."""
        method_lower = method_name.lower()

        for pattern, event_type in METHOD_PATTERNS.items():
            if pattern in method_lower:
                return event_type

        return ["info"]

    def _map_severity(self, severity: str) -> int:
        """Map GCP severity to numeric 0-100."""
        severity_map = {
            "DEFAULT": 0,
            "DEBUG": 10,
            "INFO": 30,
            "NOTICE": 40,
            "WARNING": 50,
            "ERROR": 70,
            "CRITICAL": 90,
            "ALERT": 95,
            "EMERGENCY": 100,
        }
        return severity_map.get(severity.upper(), 30)

    def _map_resource_fields(
        self,
        event: ParsedEvent,
        proto_payload: dict,
        service_name: str,
    ) -> None:
        """Map resource-specific fields based on service."""
        # Compute Engine
        if "compute.googleapis.com" in service_name:
            request = proto_payload.get("request", {})
            if "instance" in request:
                event.host_name = request.get("name", "")
            response = proto_payload.get("response", {})
            if "targetLink" in response:
                # Extract instance name from target link
                link = response["targetLink"]
                if "/instances/" in link:
                    event.host_name = link.split("/instances/")[-1]

        # IAM
        elif "iam.googleapis.com" in service_name:
            request = proto_payload.get("request", {})
            if "serviceAccount" in request:
                sa = request["serviceAccount"]
                if "email" in sa:
                    event.labels["service_account"] = sa["email"]

        # Storage
        elif "storage.googleapis.com" in service_name:
            resource_name = proto_payload.get("resourceName", "")
            if "/buckets/" in resource_name:
                parts = resource_name.split("/buckets/")[-1].split("/")
                event.labels["bucket"] = parts[0]
                if len(parts) > 2 and parts[1] == "objects":
                    event.file_path = "/".join(parts[2:])
                    event.file_name = parts[-1]

        # BigQuery
        elif "bigquery.googleapis.com" in service_name:
            request = proto_payload.get("request", {})
            if "query" in request:
                # Don't log full query, just note it exists
                event.labels["has_query"] = "true"
            job = proto_payload.get("serviceData", {}).get("jobCompletedEvent", {})
            if job:
                event.labels["job_id"] = job.get("job", {}).get("jobName", {}).get("jobId", "")

        # Cloud Functions
        elif "cloudfunctions.googleapis.com" in service_name:
            resource_name = proto_payload.get("resourceName", "")
            if "/functions/" in resource_name:
                event.labels["function_name"] = resource_name.split("/functions/")[-1]

        # GKE
        elif "container.googleapis.com" in service_name:
            resource_name = proto_payload.get("resourceName", "")
            if "/clusters/" in resource_name:
                parts = resource_name.split("/clusters/")[-1].split("/")
                event.labels["cluster_name"] = parts[0]

        # Secret Manager
        elif "secretmanager.googleapis.com" in service_name:
            resource_name = proto_payload.get("resourceName", "")
            if "/secrets/" in resource_name:
                parts = resource_name.split("/secrets/")[-1].split("/")
                event.labels["secret_name"] = parts[0]
