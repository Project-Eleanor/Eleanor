"""Okta System Log parser.

Parses Okta System Log events for authentication, authorization,
and administrative activities.
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


# Okta event type to ECS category mapping
OKTA_EVENT_CATEGORY_MAP = {
    # Authentication
    "user.session.start": ["authentication"],
    "user.session.end": ["authentication"],
    "user.authentication.auth_via_mfa": ["authentication"],
    "user.authentication.sso": ["authentication"],
    "user.authentication.auth_via_radius": ["authentication"],
    "user.authentication.auth_via_IDP": ["authentication"],
    # Authorization failures
    "user.session.access_admin_app": ["authentication"],
    "policy.evaluate_sign_on": ["authentication"],
    # Account lifecycle
    "user.lifecycle.create": ["iam"],
    "user.lifecycle.activate": ["iam"],
    "user.lifecycle.deactivate": ["iam"],
    "user.lifecycle.suspend": ["iam"],
    "user.lifecycle.unsuspend": ["iam"],
    "user.lifecycle.delete": ["iam"],
    # Password
    "user.account.update_password": ["iam"],
    "user.credential.forgot_password": ["iam"],
    "user.credential.reset_password": ["iam"],
    # MFA
    "user.mfa.factor.activate": ["iam"],
    "user.mfa.factor.deactivate": ["iam"],
    "user.mfa.factor.reset_all": ["iam"],
    # Group management
    "group.user_membership.add": ["iam"],
    "group.user_membership.remove": ["iam"],
    # Application
    "application.user_membership.add": ["configuration"],
    "application.user_membership.remove": ["configuration"],
    # System
    "system.org.rate_limit.violation": ["network"],
    "system.org.rate_limit.warning": ["network"],
}


@register_parser
class OktaParser(BaseParser):
    """Parser for Okta System Log events."""

    @property
    def name(self) -> str:
        return "okta"

    @property
    def category(self) -> ParserCategory:
        return ParserCategory.CLOUD

    @property
    def description(self) -> str:
        return "Okta System Log event parser"

    @property
    def supported_extensions(self) -> list[str]:
        return [".json", ".jsonl"]

    @property
    def supported_mime_types(self) -> list[str]:
        return ["application/json"]

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if content is Okta log format."""
        if content:
            try:
                text = content.decode("utf-8", errors="ignore")
                lines = text.strip().split("\n")

                for line in lines[:5]:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        # Okta events have specific fields
                        if all(f in data for f in ["actor", "outcome", "eventType"]):
                            return True
                        if "uuid" in data and "published" in data and "actor" in data:
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
        """Parse Okta log file and yield events."""
        source_str = source_name or (str(source) if isinstance(source, Path) else "stream")

        if isinstance(source, Path):
            with open(source, encoding="utf-8", errors="replace") as f:
                yield from self._parse_file(f, source_str)
        else:
            import io

            text_stream = io.TextIOWrapper(source, encoding="utf-8", errors="replace")
            yield from self._parse_file(text_stream, source_str)

    def _parse_file(self, file_handle, source_name: str) -> Iterator[ParsedEvent]:
        """Parse file content."""
        # Try to detect format
        first_char = file_handle.read(1)
        file_handle.seek(0)

        if first_char == "[":
            # JSON array
            try:
                data = json.load(file_handle)
                for i, record in enumerate(data):
                    event = self._parse_record(record, source_name, i + 1)
                    if event:
                        yield event
            except json.JSONDecodeError:
                pass
        else:
            # JSONL
            for line_num, line in enumerate(file_handle, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    event = self._parse_record(record, source_name, line_num)
                    if event:
                        yield event
                except json.JSONDecodeError:
                    logger.debug(f"JSON parse error at line {line_num}")

    def _parse_record(
        self,
        record: dict[str, Any],
        source_name: str,
        line_num: int,
    ) -> ParsedEvent | None:
        """Parse a single Okta event."""
        # Extract timestamp
        timestamp = self._parse_timestamp(record)

        # Get event type
        event_type = record.get("eventType", "unknown")

        # Generate message
        message = self._generate_message(record)

        # Create event
        event = ParsedEvent(
            timestamp=timestamp,
            message=message,
            source_type="okta",
            source_file=source_name,
            source_line=line_num,
            event_kind="event",
        )

        # Set action
        event.event_action = event_type

        # Set categories
        event.event_category = OKTA_EVENT_CATEGORY_MAP.get(event_type, ["iam"])

        # Determine event type
        if "authentication" in event_type.lower() or "session" in event_type.lower():
            event.event_type = (
                ["start"] if "start" in event_type else ["end"] if "end" in event_type else ["info"]
            )
        elif "create" in event_type.lower() or "add" in event_type.lower():
            event.event_type = ["creation"]
        elif "delete" in event_type.lower() or "remove" in event_type.lower():
            event.event_type = ["deletion"]
        elif "update" in event_type.lower() or "reset" in event_type.lower():
            event.event_type = ["change"]
        else:
            event.event_type = ["info"]

        # Extract actor (user who performed action)
        actor = record.get("actor", {})
        if actor:
            event.user_name = actor.get("alternateId") or actor.get("displayName")
            event.user_id = actor.get("id")

        # Extract client info
        client = record.get("client", {})
        if client:
            event.source_ip = client.get("ipAddress")

            # User agent
            user_agent = client.get("userAgent", {})
            if user_agent:
                event.labels["user_agent"] = user_agent.get("rawUserAgent", "")[:200]
                event.labels["browser"] = user_agent.get("browser", "")
                event.labels["os"] = user_agent.get("os", "")

            # Geo location
            geo = client.get("geographicalContext", {})
            if geo:
                event.labels["city"] = geo.get("city", "")
                event.labels["state"] = geo.get("state", "")
                event.labels["country"] = geo.get("country", "")

        # Outcome
        outcome = record.get("outcome", {})
        result = outcome.get("result", "").upper()
        if result == "SUCCESS":
            event.event_outcome = "success"
        elif result in ("FAILURE", "DENY"):
            event.event_outcome = "failure"
        else:
            event.event_outcome = "unknown"

        if outcome.get("reason"):
            event.labels["outcome_reason"] = outcome["reason"]

        # Target
        targets = record.get("target", [])
        if targets:
            target = targets[0]
            event.labels["target_type"] = target.get("type", "")
            event.labels["target_id"] = target.get("id", "")
            event.labels["target_name"] = target.get("alternateId") or target.get("displayName", "")

        # Authentication context
        auth_context = record.get("authenticationContext", {})
        if auth_context:
            if auth_context.get("authenticationProvider"):
                event.labels["auth_provider"] = auth_context["authenticationProvider"]
            if auth_context.get("credentialType"):
                event.labels["credential_type"] = auth_context["credentialType"]
            if auth_context.get("externalSessionId"):
                event.labels["external_session_id"] = auth_context["externalSessionId"]

        # Security context
        security_context = record.get("securityContext", {})
        if security_context:
            if security_context.get("asNumber"):
                event.labels["asn"] = str(security_context["asNumber"])
            if security_context.get("asOrg"):
                event.labels["as_org"] = security_context["asOrg"]
            if security_context.get("isp"):
                event.labels["isp"] = security_context["isp"]
            if security_context.get("isProxy"):
                event.labels["is_proxy"] = str(security_context["isProxy"])

        # Debug context for additional info
        debug_context = record.get("debugContext", {})
        if debug_context:
            debug_data = debug_context.get("debugData", {})
            if debug_data.get("requestUri"):
                event.url_full = debug_data["requestUri"]
            if debug_data.get("deviceFingerprint"):
                event.labels["device_fingerprint"] = debug_data["deviceFingerprint"]

        # Transaction
        transaction = record.get("transaction", {})
        if transaction:
            event.labels["transaction_id"] = transaction.get("id", "")
            event.labels["transaction_type"] = transaction.get("type", "")

        # Core labels
        event.labels["uuid"] = record.get("uuid", "")
        event.labels["version"] = record.get("version", "")

        # Set severity based on event type and outcome
        if event.event_outcome == "failure":
            if "authentication" in event_type.lower():
                event.event_severity = 60  # Auth failures are important
            else:
                event.event_severity = 40
        elif "suspend" in event_type.lower() or "deactivate" in event_type.lower():
            event.event_severity = 50
        elif "delete" in event_type.lower():
            event.event_severity = 50
        else:
            event.event_severity = 20

        # Store raw
        event.raw = record

        return event

    def _parse_timestamp(self, record: dict) -> datetime:
        """Parse timestamp from Okta event."""
        for field in ["published", "timestamp"]:
            if field in record:
                try:
                    return datetime.fromisoformat(record[field].replace("Z", "+00:00"))
                except ValueError:
                    pass

        return datetime.now(UTC)

    def _generate_message(self, record: dict) -> str:
        """Generate human-readable message."""
        event_type = record.get("eventType", "unknown")
        display_message = record.get("displayMessage", "")

        if display_message:
            return display_message

        actor = record.get("actor", {})
        actor_name = actor.get("alternateId") or actor.get("displayName", "Unknown")

        targets = record.get("target", [])
        target_info = ""
        if targets:
            target = targets[0]
            target_name = target.get("alternateId") or target.get("displayName", "")
            if target_name:
                target_info = f" on {target_name}"

        outcome = record.get("outcome", {})
        result = outcome.get("result", "")
        result_info = f" ({result})" if result else ""

        return f"Okta: {actor_name} - {event_type}{target_info}{result_info}"
