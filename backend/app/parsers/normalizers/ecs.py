"""Elastic Common Schema (ECS) normalizer.

Provides utilities for normalizing parsed events to ECS format
for consistent storage and querying in Elasticsearch.
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from app.parsers.base import ParsedEvent


class ECSNormalizer:
    """Normalizes parsed events to Elastic Common Schema format.

    ECS is a specification for structuring data in Elasticsearch,
    providing consistent field names and types across all data sources.

    Reference: https://www.elastic.co/guide/en/ecs/current/index.html
    """

    # ECS version this normalizer targets
    ECS_VERSION = "8.11"

    # IP address patterns
    IPV4_PATTERN = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    IPV6_PATTERN = re.compile(
        r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$|^(?:[0-9a-fA-F]{1,4}:){1,6}::$"
    )

    # Hash patterns
    MD5_PATTERN = re.compile(r"^[a-fA-F0-9]{32}$")
    SHA1_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")
    SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
    SHA512_PATTERN = re.compile(r"^[a-fA-F0-9]{128}$")

    def normalize(self, event: ParsedEvent) -> dict[str, Any]:
        """Normalize a parsed event to ECS format.

        Args:
            event: Parsed event to normalize

        Returns:
            Dictionary in ECS format
        """
        doc = {
            "@timestamp": event.timestamp.isoformat(),
            "ecs": {"version": self.ECS_VERSION},
            "event": self._build_event_fields(event),
        }

        # Add optional field sets
        if event.message:
            doc["message"] = event.message

        # Host
        host = self._build_host_fields(event)
        if host:
            doc["host"] = host

        # User
        user = self._build_user_fields(event)
        if user:
            doc["user"] = user

        # Process
        process = self._build_process_fields(event)
        if process:
            doc["process"] = process

        # File
        file_fields = self._build_file_fields(event)
        if file_fields:
            doc["file"] = file_fields

        # Network
        source, destination, network = self._build_network_fields(event)
        if source:
            doc["source"] = source
        if destination:
            doc["destination"] = destination
        if network:
            doc["network"] = network

        # URL
        url = self._build_url_fields(event)
        if url:
            doc["url"] = url

        # Labels and tags
        if event.labels:
            doc["labels"] = event.labels
        if event.tags:
            doc["tags"] = event.tags

        # Source metadata
        doc["_eleanor"] = {
            "source_type": event.source_type,
            "source_file": event.source_file,
            "source_line": event.source_line,
            "indexed_at": datetime.now(UTC).isoformat(),
        }

        # Generate document ID for deduplication
        doc["_id"] = self._generate_doc_id(event)

        return doc

    def _build_event_fields(self, event: ParsedEvent) -> dict[str, Any]:
        """Build ECS event.* fields."""
        fields: dict[str, Any] = {
            "kind": event.event_kind,
            "category": event.event_category if event.event_category else ["process"],
            "type": event.event_type if event.event_type else ["info"],
        }

        if event.event_action:
            fields["action"] = event.event_action
        if event.event_outcome:
            fields["outcome"] = event.event_outcome
        if event.event_severity is not None:
            fields["severity"] = event.event_severity

        # Add original event info
        fields["original"] = event.message or ""
        fields["created"] = datetime.now(UTC).isoformat()

        return fields

    def _build_host_fields(self, event: ParsedEvent) -> dict[str, Any] | None:
        """Build ECS host.* fields."""
        if not event.host_name:
            return None

        fields: dict[str, Any] = {"name": event.host_name}

        if event.host_ip:
            fields["ip"] = self._normalize_ip_list(event.host_ip)
        if event.host_mac:
            fields["mac"] = [self._normalize_mac(m) for m in event.host_mac]
        if event.host_os_name:
            os_fields: dict[str, Any] = {"name": event.host_os_name}
            fields["os"] = os_fields
            if event.host_os_version:
                os_fields["version"] = event.host_os_version

        return fields

    def _build_user_fields(self, event: ParsedEvent) -> dict[str, Any] | None:
        """Build ECS user.* fields."""
        if not event.user_name and not event.user_id:
            return None

        fields = {}
        if event.user_name:
            fields["name"] = event.user_name
        if event.user_id:
            fields["id"] = event.user_id
        if event.user_domain:
            fields["domain"] = event.user_domain

        return fields

    def _build_process_fields(self, event: ParsedEvent) -> dict[str, Any] | None:
        """Build ECS process.* fields."""
        if not event.process_name and not event.process_pid:
            return None

        fields: dict[str, Any] = {}
        if event.process_name:
            fields["name"] = event.process_name
        if event.process_pid is not None:
            fields["pid"] = event.process_pid
        if event.process_executable:
            fields["executable"] = event.process_executable
        if event.process_command_line:
            fields["command_line"] = event.process_command_line
            # Also extract args
            fields["args"] = self._parse_command_line(event.process_command_line)

        if event.process_ppid is not None:
            fields["parent"] = {"pid": event.process_ppid}

        return fields

    def _build_file_fields(self, event: ParsedEvent) -> dict[str, Any] | None:
        """Build ECS file.* fields."""
        if not event.file_name and not event.file_path:
            return None

        fields: dict[str, Any] = {}
        if event.file_name:
            fields["name"] = event.file_name
        if event.file_path:
            fields["path"] = event.file_path
            # Extract directory and extension
            parts = event.file_path.rsplit("/", 1)
            if len(parts) > 1:
                fields["directory"] = parts[0]
            if event.file_name and "." in event.file_name:
                fields["extension"] = event.file_name.rsplit(".", 1)[1]

        # File hashes
        hashes: dict[str, str] = {}
        if event.file_hash_sha256:
            hashes["sha256"] = event.file_hash_sha256.lower()
        if event.file_hash_sha1:
            hashes["sha1"] = event.file_hash_sha1.lower()
        if event.file_hash_md5:
            hashes["md5"] = event.file_hash_md5.lower()
        if hashes:
            fields["hash"] = hashes

        return fields

    def _build_network_fields(
        self, event: ParsedEvent
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
        """Build ECS source.*, destination.*, and network.* fields."""
        source: dict[str, Any] | None = None
        destination: dict[str, Any] | None = None
        network: dict[str, Any] | None = None

        if event.source_ip:
            source = {"ip": event.source_ip}
            if event.source_port:
                source["port"] = event.source_port

        if event.destination_ip:
            destination = {"ip": event.destination_ip}
            if event.destination_port:
                destination["port"] = event.destination_port

        if event.network_protocol or event.network_direction:
            network = {}
            if event.network_protocol:
                network["protocol"] = event.network_protocol.lower()
            if event.network_direction:
                network["direction"] = event.network_direction

        return source, destination, network

    def _build_url_fields(self, event: ParsedEvent) -> dict[str, Any] | None:
        """Build ECS url.* fields."""
        if not event.url_full:
            return None

        fields: dict[str, Any] = {"full": event.url_full}

        if event.url_domain:
            fields["domain"] = event.url_domain

        # Parse URL components
        try:
            from urllib.parse import urlparse

            parsed = urlparse(event.url_full)
            if parsed.scheme:
                fields["scheme"] = parsed.scheme
            if parsed.netloc:
                fields["domain"] = parsed.netloc.split(":")[0]
                if ":" in parsed.netloc:
                    fields["port"] = int(parsed.netloc.split(":")[1])
            if parsed.path:
                fields["path"] = parsed.path
            if parsed.query:
                fields["query"] = parsed.query
        except Exception:
            pass

        return fields

    def _generate_doc_id(self, event: ParsedEvent) -> str:
        """Generate a unique document ID for deduplication.

        Uses a hash of key fields to ensure the same event
        always generates the same ID.
        """
        key_parts = [
            event.timestamp.isoformat(),
            event.source_type,
            event.source_file,
            str(event.source_line or 0),
            event.message or "",
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:20]

    def _normalize_ip_list(self, ips: list[str]) -> list[str]:
        """Normalize a list of IP addresses."""
        normalized = []
        for ip in ips:
            ip = ip.strip()
            if self.IPV4_PATTERN.match(ip) or self.IPV6_PATTERN.match(ip):
                normalized.append(ip)
        return normalized

    def _normalize_mac(self, mac: str) -> str:
        """Normalize a MAC address to lowercase with colons."""
        mac = mac.strip().lower()
        # Remove any existing separators
        mac = mac.replace(":", "").replace("-", "").replace(".", "")
        # Add colons
        return ":".join(mac[i : i + 2] for i in range(0, len(mac), 2))

    def _parse_command_line(self, command_line: str) -> list[str]:
        """Parse a command line into arguments."""
        import shlex

        try:
            return shlex.split(command_line)
        except ValueError:
            # Handle malformed command lines
            return command_line.split()

    @classmethod
    def identify_hash_type(cls, hash_value: str) -> str | None:
        """Identify the type of a hash value.

        Args:
            hash_value: Hash string to identify

        Returns:
            Hash type (md5, sha1, sha256, sha512) or None
        """
        hash_value = hash_value.strip().lower()

        if cls.MD5_PATTERN.match(hash_value):
            return "md5"
        elif cls.SHA1_PATTERN.match(hash_value):
            return "sha1"
        elif cls.SHA256_PATTERN.match(hash_value):
            return "sha256"
        elif cls.SHA512_PATTERN.match(hash_value):
            return "sha512"

        return None

    @classmethod
    def validate_ecs_document(cls, doc: dict[str, Any]) -> list[str]:
        """Validate an ECS document for common issues.

        Args:
            doc: ECS document to validate

        Returns:
            List of validation warning messages
        """
        warnings = []

        # Check required fields
        if "@timestamp" not in doc:
            warnings.append("Missing @timestamp field")

        if "event" not in doc:
            warnings.append("Missing event field")
        elif not isinstance(doc["event"], dict):
            warnings.append("event field should be an object")
        else:
            if "category" not in doc["event"]:
                warnings.append("Missing event.category")
            if "type" not in doc["event"]:
                warnings.append("Missing event.type")

        # Check field types
        if "host" in doc and "ip" in doc["host"]:
            if not isinstance(doc["host"]["ip"], list):
                warnings.append("host.ip should be an array")

        if "tags" in doc and not isinstance(doc["tags"], list):
            warnings.append("tags should be an array")

        return warnings
