"""Google Cloud Platform logging connector.

Ingests logs from GCP Cloud Logging (formerly Stackdriver) via the
Cloud Logging API, supporting various GCP log types including:
- Audit logs
- VPC Flow logs
- Cloud Functions logs
- GKE logs
- Application logs
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import (
    ConnectorConfig,
    PollingConnector,
    RawEvent,
)

logger = logging.getLogger(__name__)


class GCPLoggingConnector(PollingConnector):
    """Google Cloud Logging connector.

    Polls GCP Cloud Logging API for log entries matching configured filters.
    Supports filtering by log name, resource type, severity, and custom filters.

    Configuration:
        project_id: GCP project ID
        credentials_path: Path to service account JSON key (optional, uses ADC if not set)
        log_filter: Cloud Logging filter expression
        log_names: List of specific log names to ingest
        resource_types: List of resource types to filter
        severity_min: Minimum log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """

    name = "gcp_logging"
    description = "Google Cloud Platform Cloud Logging connector"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.project_id = config.extra.get("project_id", "")
        self.credentials_path = config.extra.get("credentials_path")
        self.log_filter = config.extra.get("log_filter", "")
        self.log_names = config.extra.get("log_names", [])
        self.resource_types = config.extra.get("resource_types", [])
        self.severity_min = config.extra.get("severity_min", "INFO")

        self._client = None
        self._last_timestamp: str | None = None

    async def connect(self) -> bool:
        """Connect to GCP Cloud Logging API."""
        try:
            from google.cloud import logging as gcp_logging

            if self.credentials_path:
                self._client = gcp_logging.Client.from_service_account_json(
                    self.credentials_path,
                    project=self.project_id,
                )
            else:
                # Use Application Default Credentials
                self._client = gcp_logging.Client(project=self.project_id)

            logger.info(f"Connected to GCP Logging for project: {self.project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to GCP Logging: {e}")
            self.record_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from GCP Logging."""
        if self._client:
            self._client.close()
            self._client = None

    async def health_check(self) -> dict[str, Any]:
        """Check GCP Logging connectivity."""
        if not self._client:
            return {
                "status": "unhealthy",
                "error": "Not connected",
            }

        try:
            # Try to list a single entry to verify connectivity
            import asyncio

            await asyncio.to_thread(
                self._list_entries,
                filter_str="severity >= DEFAULT",
                max_results=1,
            )

            return {
                "status": "healthy",
                "project_id": self.project_id,
                "connected": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def poll(self) -> AsyncIterator[RawEvent]:
        """Poll for new log entries."""
        import asyncio

        if not self._client:
            return

        try:
            filter_str = self._build_filter()

            entries = await asyncio.to_thread(
                self._list_entries,
                filter_str=filter_str,
                max_results=self.config.batch_size,
            )

            for entry in entries:
                try:
                    event = self._entry_to_event(entry)
                    if event:
                        self.record_event(len(str(event.data)))
                        yield event

                        # Track last timestamp for incremental polling
                        if entry.timestamp:
                            self._last_timestamp = entry.timestamp.isoformat()

                except Exception as e:
                    logger.debug(f"Error processing entry: {e}")
                    self.record_error(str(e))

        except Exception as e:
            logger.error(f"GCP Logging poll error: {e}")
            self.record_error(str(e))

    def _build_filter(self) -> str:
        """Build Cloud Logging filter expression."""
        filters = []

        # Time filter for incremental polling
        if self._last_timestamp:
            filters.append(f'timestamp > "{self._last_timestamp}"')
        else:
            # On first poll, get last hour
            from datetime import timedelta

            start_time = datetime.now(UTC) - timedelta(hours=1)
            filters.append(f'timestamp >= "{start_time.isoformat()}"')

        # Log name filter
        if self.log_names:
            log_filter = " OR ".join(
                f'logName="projects/{self.project_id}/logs/{name}"' for name in self.log_names
            )
            filters.append(f"({log_filter})")

        # Resource type filter
        if self.resource_types:
            resource_filter = " OR ".join(f'resource.type="{rt}"' for rt in self.resource_types)
            filters.append(f"({resource_filter})")

        # Severity filter
        severity_map = {
            "DEBUG": "DEBUG",
            "INFO": "INFO",
            "WARNING": "WARNING",
            "ERROR": "ERROR",
            "CRITICAL": "CRITICAL",
        }
        if self.severity_min in severity_map:
            filters.append(f"severity >= {severity_map[self.severity_min]}")

        # Custom filter
        if self.log_filter:
            filters.append(f"({self.log_filter})")

        return " AND ".join(filters) if filters else ""

    def _list_entries(
        self,
        filter_str: str,
        max_results: int = 1000,
    ) -> list:
        """List log entries from Cloud Logging."""
        if not self._client:
            return []

        # Order by timestamp to get newest entries
        return list(
            self._client.list_entries(
                filter_=filter_str,
                order_by="timestamp desc",
                max_results=max_results,
                projects=[self.project_id],
            )
        )

    def _entry_to_event(self, entry) -> RawEvent | None:
        """Convert Cloud Logging entry to RawEvent."""
        try:
            # Get timestamp
            timestamp = entry.timestamp
            if not timestamp:
                timestamp = datetime.now(UTC)

            # Build payload dict
            payload: dict[str, Any] = {}

            # Proto payload (most structured logs)
            if hasattr(entry, "proto_payload") and entry.proto_payload:
                payload = self._proto_to_dict(entry.proto_payload)
            # JSON payload
            elif hasattr(entry, "json_payload") and entry.json_payload:
                payload = dict(entry.json_payload)
            # Text payload
            elif hasattr(entry, "text_payload") and entry.text_payload:
                payload = {"message": entry.text_payload}

            # Add metadata
            payload["_gcp"] = {
                "logName": entry.log_name,
                "severity": entry.severity if hasattr(entry, "severity") else None,
                "insertId": entry.insert_id if hasattr(entry, "insert_id") else None,
                "resource": self._resource_to_dict(entry.resource) if entry.resource else None,
                "labels": dict(entry.labels) if entry.labels else None,
                "trace": entry.trace if hasattr(entry, "trace") else None,
                "spanId": entry.span_id if hasattr(entry, "span_id") else None,
            }

            # Determine source type
            source = entry.log_name.split("/")[-1] if entry.log_name else "unknown"

            return RawEvent(
                data=payload,
                source=f"gcp:{source}",
                timestamp=timestamp,
                metadata={
                    "project_id": self.project_id,
                    "log_name": entry.log_name,
                    "severity": str(entry.severity) if hasattr(entry, "severity") else None,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to convert entry: {e}")
            return None

    def _proto_to_dict(self, proto_payload) -> dict[str, Any]:
        """Convert protobuf payload to dictionary."""
        from google.protobuf.json_format import MessageToDict

        try:
            return MessageToDict(proto_payload)
        except Exception:
            return {"_raw_proto": str(proto_payload)}

    def _resource_to_dict(self, resource) -> dict[str, Any]:
        """Convert resource to dictionary."""
        return {
            "type": resource.type,
            "labels": dict(resource.labels) if resource.labels else {},
        }


# Audit log specific handling
AUDIT_LOG_CATEGORIES = {
    "activity": "admin_activity",
    "data_access": "data_access",
    "system_event": "system_event",
    "policy": "policy",
}


def parse_audit_log(payload: dict) -> dict[str, Any]:
    """Parse GCP audit log payload into structured format.

    Args:
        payload: Raw audit log payload

    Returns:
        Parsed audit log with key fields extracted
    """
    proto_payload = payload.get("protoPayload", payload)

    result = {
        "type": "gcp_audit",
        "service_name": proto_payload.get("serviceName"),
        "method_name": proto_payload.get("methodName"),
        "resource_name": proto_payload.get("resourceName"),
    }

    # Authentication info
    auth_info = proto_payload.get("authenticationInfo", {})
    result["principal_email"] = auth_info.get("principalEmail")
    result["principal_subject"] = auth_info.get("principalSubject")

    # Authorization info
    auth_infos = proto_payload.get("authorizationInfo", [])
    if auth_infos:
        result["permissions"] = [a.get("permission") for a in auth_infos if a.get("granted")]

    # Request metadata
    request_metadata = proto_payload.get("requestMetadata", {})
    result["caller_ip"] = request_metadata.get("callerIp")
    result["caller_user_agent"] = request_metadata.get("callerSuppliedUserAgent")

    # Request/Response (truncated for size)
    if "request" in proto_payload:
        result["request"] = _truncate_dict(proto_payload["request"], 500)
    if "response" in proto_payload:
        result["response"] = _truncate_dict(proto_payload["response"], 500)

    # Status
    status = proto_payload.get("status", {})
    result["status_code"] = status.get("code", 0)
    result["status_message"] = status.get("message")

    return result


def _truncate_dict(d: dict, max_size: int) -> dict:
    """Truncate dictionary values to max size."""
    import json

    result = {}
    current_size = 0

    for key, value in d.items():
        value_str = json.dumps(value)
        if current_size + len(value_str) > max_size:
            break
        result[key] = value
        current_size += len(value_str)

    return result
