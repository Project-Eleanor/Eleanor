"""Generic JSON log parser.

Parses JSON and JSONL (JSON Lines) log files with automatic field mapping
to ECS format. Supports common log formats like CloudTrail, Azure AD, etc.
"""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.parsers.base import BaseParser, ParsedEvent, ParserCategory
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

# Common timestamp field names and their formats
TIMESTAMP_FIELDS = [
    "@timestamp",
    "timestamp",
    "time",
    "datetime",
    "date",
    "eventTime",
    "EventTime",
    "createdDateTime",
    "activityDateTime",
    "timeGenerated",
    "TimeGenerated",
    "eventTimestamp",
    "created_at",
    "created",
    "ts",
    "_time",
]

# Common timestamp formats
TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",
]

# Log type detection patterns
LOG_TYPE_PATTERNS = {
    "aws_cloudtrail": ["Records", "eventSource", "awsRegion"],
    "azure_signin": ["createdDateTime", "userPrincipalName", "conditionalAccessStatus"],
    "azure_audit": ["activityDateTime", "operationType", "targetResources"],
    "gcp_audit": ["protoPayload", "resource", "severity"],
    "okta": ["actor", "outcome", "eventType"],
    "o365_audit": ["Workload", "Operation", "UserId"],
}


@register_parser
class GenericJSONParser(BaseParser):
    """Parser for JSON and JSONL log files."""

    @property
    def name(self) -> str:
        return "json"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.LOGS

    @property
    def description(self) -> str:
        return "Generic JSON/JSONL log parser with ECS mapping"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".jsonl", ".ndjson"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json", "application/x-ndjson"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is valid JSON/JSONL."""
        if content:
            try:
                # Try to decode first line
                text = content.decode("utf-8", errors="ignore").strip()
                if text.startswith("{") or text.startswith("["):
                    return True
            except Exception:
                pass

        if file_path:
            ext = file_path.suffix.lower()
            if ext in [".json", ".jsonl", ".ndjson"]:
                return True

        return False

    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse JSON/JSONL file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_file(f, source_str)
        else:
            # Handle binary stream
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse an open file handle."""
        # Read first line to detect format
        first_line = file_handle.readline().strip()
        if not first_line:
            return

        # Check if it's a JSON array or object
        if first_line.startswith("[") or first_line.startswith("{"):
            # Try to parse as complete JSON (array or object)
            file_handle.seek(0)
            try:
                data = json.load(file_handle)
                if isinstance(data, list):
                    # Check for CloudTrail format
                    if "Records" in data[0] if data else False:
                        for item in data:
                            for record in item.get("Records", []):
                                yield self._parse_record(record, source_name, 0)
                    else:
                        for i, record in enumerate(data):
                            yield self._parse_record(record, source_name, i + 1)
                elif isinstance(data, dict):
                    # Check for wrapped records (CloudTrail, etc.)
                    if "Records" in data:
                        for i, record in enumerate(data["Records"]):
                            yield self._parse_record(record, source_name, i + 1)
                    else:
                        yield self._parse_record(data, source_name, 1)
            except json.JSONDecodeError:
                # Failed to parse as complete JSON, try JSONL
                file_handle.seek(0)
                yield from self._parse_jsonl(file_handle, source_name)
        else:
            # JSONL format - parse line by line
            file_handle.seek(0)
            yield from self._parse_jsonl(file_handle, source_name)

    def _parse_jsonl(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse JSONL (JSON Lines) format."""
        for line_num, line in enumerate(file_handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
                yield self._parse_record(record, source_name, line_num)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse line {line_num}: {e}")
                continue

    def _parse_record(self, record: dict, source_name: str, line_num: int) -> ParsedEvent:
        """Parse a single JSON record to ParsedEvent."""
        # Detect log type
        log_type = self._detect_log_type(record)

        # Extract timestamp
        timestamp = self._extract_timestamp(record)

        # Extract message
        message = self._extract_message(record, log_type)

        # Map to ECS fields based on log type
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type=log_type or "json",
            source_file=source_name,
            source_line=line_num,
            raw=record,
        )

        # Apply type-specific mapping
        if log_type == "aws_cloudtrail":
            self._map_cloudtrail(event, record)
        elif log_type == "azure_signin":
            self._map_azure_signin(event, record)
        elif log_type == "azure_audit":
            self._map_azure_audit(event, record)
        elif log_type == "gcp_audit":
            self._map_gcp_audit(event, record)
        elif log_type == "okta":
            self._map_okta(event, record)
        elif log_type == "o365_audit":
            self._map_o365_audit(event, record)
        else:
            self._map_generic(event, record)

        return event

    def _detect_log_type(self, record: dict) -> str | None:
        """Detect the log type from record fields."""
        for log_type, patterns in LOG_TYPE_PATTERNS.items():
            matches = sum(1 for p in patterns if p in record)
            if matches >= 2:
                return log_type
        return None

    def _extract_timestamp(self, record: dict) -> datetime:
        """Extract timestamp from record."""
        for field in TIMESTAMP_FIELDS:
            if field in record:
                value = record[field]
                if isinstance(value, str):
                    ts = self._parse_timestamp(value)
                    if ts:
                        return ts
                elif isinstance(value, (int, float)):
                    # Unix timestamp
                    try:
                        if value > 1e12:  # Milliseconds
                            return datetime.fromtimestamp(value / 1000, tz=UTC)
                        return datetime.fromtimestamp(value, tz=UTC)
                    except Exception:
                        pass

        return datetime.now(UTC)

    def _parse_timestamp(self, value: str) -> datetime | None:
        """Parse a timestamp string."""
        for fmt in TIMESTAMP_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                continue

        # Try ISO format
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass

        return None

    def _extract_message(self, record: dict, log_type: str | None) -> str:
        """Extract or generate message from record."""
        # Check common message fields
        for field in ["message", "msg", "description", "eventName", "operationName", "Operation"]:
            if field in record and record[field]:
                return str(record[field])

        # Generate based on log type
        if log_type == "aws_cloudtrail":
            event_name = record.get("eventName", "")
            user = record.get("userIdentity", {}).get(
                "userName", record.get("userIdentity", {}).get("arn", "unknown")
            )
            return f"CloudTrail: {event_name} by {user}"

        elif log_type == "azure_signin":
            user = record.get("userPrincipalName", "unknown")
            status = record.get("status", {}).get("errorCode", 0)
            return f"Azure Sign-in: {user} (status: {status})"

        # Fallback
        return json.dumps(record, default=str)[:200]

    def _map_cloudtrail(self, event: ParsedEvent, record: dict) -> None:
        """Map CloudTrail fields to ECS."""
        event.event_category = ["cloud"]

        event_name = record.get("eventName", "")
        if "Create" in event_name or "Put" in event_name:
            event.event_type = ["creation"]
        elif "Delete" in event_name or "Remove" in event_name:
            event.event_type = ["deletion"]
        elif "Update" in event_name or "Modify" in event_name:
            event.event_type = ["change"]
        else:
            event.event_type = ["access"]

        event.event_action = event_name

        user_identity = record.get("userIdentity", {})
        event.user_name = user_identity.get("userName") or user_identity.get("arn")
        event.user_id = user_identity.get("accountId")

        event.source_ip = record.get("sourceIPAddress")

        event.labels = {
            "aws_region": record.get("awsRegion", ""),
            "event_source": record.get("eventSource", ""),
            "event_type": record.get("eventType", ""),
        }

        error = record.get("errorCode")
        if error:
            event.event_outcome = "failure"
            event.labels["error_code"] = error
        else:
            event.event_outcome = "success"

    def _map_azure_signin(self, event: ParsedEvent, record: dict) -> None:
        """Map Azure AD sign-in fields to ECS."""
        event.event_category = ["authentication"]
        event.event_type = ["start"]
        event.event_action = "user_signin"

        event.user_name = record.get("userPrincipalName")
        event.user_id = record.get("userId")

        event.source_ip = record.get("ipAddress")

        status = record.get("status", {})
        if status.get("errorCode") == 0:
            event.event_outcome = "success"
        else:
            event.event_outcome = "failure"

        event.labels = {
            "app_display_name": record.get("appDisplayName", ""),
            "client_app_used": record.get("clientAppUsed", ""),
            "conditional_access": record.get("conditionalAccessStatus", ""),
        }

    def _map_azure_audit(self, event: ParsedEvent, record: dict) -> None:
        """Map Azure AD audit fields to ECS."""
        event.event_category = ["iam"]

        op_type = record.get("operationType", "")
        if op_type == "Add":
            event.event_type = ["creation"]
        elif op_type == "Delete":
            event.event_type = ["deletion"]
        elif op_type in ["Update", "Modify"]:
            event.event_type = ["change"]
        else:
            event.event_type = ["info"]

        event.event_action = record.get("operationType")

        initiated_by = record.get("initiatedBy", {})
        user = initiated_by.get("user", {})
        event.user_name = user.get("userPrincipalName")
        event.user_id = user.get("id")

        event.source_ip = user.get("ipAddress")

        result = record.get("result", "")
        event.event_outcome = "success" if result == "success" else "failure"

    def _map_gcp_audit(self, event: ParsedEvent, record: dict) -> None:
        """Map GCP audit fields to ECS."""
        event.event_category = ["cloud"]
        event.event_type = ["access"]

        proto = record.get("protoPayload", {})
        event.event_action = proto.get("methodName")

        auth_info = proto.get("authenticationInfo", {})
        event.user_name = auth_info.get("principalEmail")

        request_metadata = proto.get("requestMetadata", {})
        event.source_ip = request_metadata.get("callerIp")

        event.labels = {
            "service_name": proto.get("serviceName", ""),
            "resource_type": record.get("resource", {}).get("type", ""),
        }

    def _map_okta(self, event: ParsedEvent, record: dict) -> None:
        """Map Okta fields to ECS."""
        event.event_category = ["authentication"]
        event.event_action = record.get("eventType")

        actor = record.get("actor", {})
        event.user_name = actor.get("alternateId")
        event.user_id = actor.get("id")

        client = record.get("client", {})
        event.source_ip = client.get("ipAddress")

        outcome = record.get("outcome", {})
        event.event_outcome = "success" if outcome.get("result") == "SUCCESS" else "failure"

        if "authentication" in (record.get("eventType") or "").lower():
            event.event_type = ["start"]
        else:
            event.event_type = ["info"]

    def _map_o365_audit(self, event: ParsedEvent, record: dict) -> None:
        """Map Office 365 audit fields to ECS."""
        workload = record.get("Workload", "")
        if workload == "Exchange":
            event.event_category = ["email"]
        elif workload == "SharePoint" or workload == "OneDrive":
            event.event_category = ["file"]
        elif workload == "AzureActiveDirectory":
            event.event_category = ["authentication"]
        else:
            event.event_category = ["web"]

        event.event_action = record.get("Operation")
        event.user_name = record.get("UserId")
        event.source_ip = record.get("ClientIP")

        result = record.get("ResultStatus", "")
        event.event_outcome = "success" if result in ["Succeeded", "Success", "True"] else "failure"

    def _map_generic(self, event: ParsedEvent, record: dict) -> None:
        """Apply generic field mapping."""
        # Try to find user
        for field in ["user", "username", "user_name", "userName", "actor", "principal"]:
            if field in record:
                val = record[field]
                if isinstance(val, str):
                    event.user_name = val
                    break
                elif isinstance(val, dict):
                    event.user_name = val.get("name") or val.get("username")
                    event.user_id = val.get("id")
                    break

        # Try to find IP
        for field in [
            "ip",
            "ip_address",
            "ipAddress",
            "source_ip",
            "src_ip",
            "client_ip",
            "remote_addr",
        ]:
            if field in record and record[field]:
                event.source_ip = record[field]
                break

        # Try to find action
        for field in ["action", "event", "eventName", "event_name", "operation", "method"]:
            if field in record and record[field]:
                event.event_action = record[field]
                break

        event.event_category = ["process"]
        event.event_type = ["info"]
