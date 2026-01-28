"""Base parser interface and data structures.

Defines the abstract interface that all parsers must implement,
along with common data structures for parsed events.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO


class ParserCategory(str, Enum):
    """Categories of evidence parsers."""

    LOGS = "logs"
    ARTIFACTS = "artifacts"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CLOUD = "cloud"


@dataclass
class ParserMetadata:
    """Metadata describing a parser's capabilities.

    Used by parsers that implement the get_metadata() classmethod pattern.
    """

    name: str
    display_name: str
    description: str
    supported_extensions: list[str] = field(default_factory=list)
    mime_types: list[str] = field(default_factory=list)
    category: str = "artifacts"
    priority: int = 50  # Higher = more likely to be selected when multiple parsers match


@dataclass
class ParsedEvent:
    """Represents a single parsed event/record.

    Fields follow Elastic Common Schema (ECS) conventions where applicable.
    """

    # Core fields
    timestamp: datetime
    message: str | None = None

    # Source identification
    source_type: str = ""
    source_file: str = ""
    source_line: int | None = None

    # ECS base fields
    event_kind: str = "event"  # alert, enrichment, event, metric, state, pipeline_error, signal
    event_category: list[str] = field(
        default_factory=list
    )  # authentication, file, network, process, etc.
    event_type: list[str] = field(
        default_factory=list
    )  # access, change, creation, deletion, info, etc.
    event_action: str | None = None
    event_outcome: str | None = None  # success, failure, unknown
    event_severity: int | None = None  # 0-100

    # ECS host fields
    host_name: str | None = None
    host_ip: list[str] = field(default_factory=list)
    host_mac: list[str] = field(default_factory=list)
    host_os_name: str | None = None
    host_os_version: str | None = None

    # ECS user fields
    user_name: str | None = None
    user_domain: str | None = None
    user_id: str | None = None

    # ECS process fields
    process_name: str | None = None
    process_pid: int | None = None
    process_ppid: int | None = None
    process_command_line: str | None = None
    process_executable: str | None = None

    # ECS file fields
    file_name: str | None = None
    file_path: str | None = None
    file_hash_sha256: str | None = None
    file_hash_sha1: str | None = None
    file_hash_md5: str | None = None

    # ECS network fields
    source_ip: str | None = None
    source_port: int | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    network_protocol: str | None = None
    network_direction: str | None = None  # inbound, outbound, internal, external, unknown

    # ECS URL fields
    url_full: str | None = None
    url_domain: str | None = None

    # Raw data and custom fields
    raw: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "@timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "event": {
                "kind": self.event_kind,
                "category": self.event_category,
                "type": self.event_type,
            },
        }

        event_dict: dict[str, Any] = result["event"]
        if self.event_action:
            event_dict["action"] = self.event_action
        if self.event_outcome:
            event_dict["outcome"] = self.event_outcome
        if self.event_severity is not None:
            event_dict["severity"] = self.event_severity

        # Host
        if self.host_name:
            host_dict: dict[str, Any] = {"name": self.host_name}
            result["host"] = host_dict
            if self.host_ip:
                host_dict["ip"] = self.host_ip
            if self.host_mac:
                host_dict["mac"] = self.host_mac
            if self.host_os_name:
                os_dict: dict[str, Any] = {"name": self.host_os_name}
                host_dict["os"] = os_dict
                if self.host_os_version:
                    os_dict["version"] = self.host_os_version

        # User
        if self.user_name:
            user_dict: dict[str, Any] = {"name": self.user_name}
            result["user"] = user_dict
            if self.user_domain:
                user_dict["domain"] = self.user_domain
            if self.user_id:
                user_dict["id"] = self.user_id

        # Process
        if self.process_name or self.process_pid:
            process_dict: dict[str, Any] = {}
            result["process"] = process_dict
            if self.process_name:
                process_dict["name"] = self.process_name
            if self.process_pid:
                process_dict["pid"] = self.process_pid
            if self.process_ppid:
                process_dict["parent"] = {"pid": self.process_ppid}
            if self.process_command_line:
                process_dict["command_line"] = self.process_command_line
            if self.process_executable:
                process_dict["executable"] = self.process_executable

        # File
        if self.file_name or self.file_path:
            file_dict: dict[str, Any] = {}
            result["file"] = file_dict
            if self.file_name:
                file_dict["name"] = self.file_name
            if self.file_path:
                file_dict["path"] = self.file_path
            if self.file_hash_sha256 or self.file_hash_sha1 or self.file_hash_md5:
                hash_dict: dict[str, Any] = {}
                file_dict["hash"] = hash_dict
                if self.file_hash_sha256:
                    hash_dict["sha256"] = self.file_hash_sha256
                if self.file_hash_sha1:
                    hash_dict["sha1"] = self.file_hash_sha1
                if self.file_hash_md5:
                    hash_dict["md5"] = self.file_hash_md5

        # Network
        if self.source_ip or self.destination_ip:
            if self.source_ip:
                source_dict: dict[str, Any] = {"ip": self.source_ip}
                result["source"] = source_dict
                if self.source_port:
                    source_dict["port"] = self.source_port
            if self.destination_ip:
                dest_dict: dict[str, Any] = {"ip": self.destination_ip}
                result["destination"] = dest_dict
                if self.destination_port:
                    dest_dict["port"] = self.destination_port
            if self.network_protocol:
                network_dict: dict[str, Any] = {"protocol": self.network_protocol}
                result["network"] = network_dict
                if self.network_direction:
                    network_dict["direction"] = self.network_direction

        # URL
        if self.url_full:
            url_dict: dict[str, Any] = {"full": self.url_full}
            result["url"] = url_dict
            if self.url_domain:
                url_dict["domain"] = self.url_domain

        # Custom fields
        if self.labels:
            result["labels"] = self.labels
        if self.tags:
            result["tags"] = self.tags
        if self.raw:
            result["_raw"] = self.raw

        source_meta: dict[str, Any] = {
            "type": self.source_type,
            "file": self.source_file,
        }
        result["_source"] = source_meta
        if self.source_line:
            source_meta["line"] = self.source_line

        return result


@dataclass
class ParserResult:
    """Result of a parsing operation."""

    success: bool
    events: list[ParsedEvent]
    total_records: int = 0
    parsed_records: int = 0
    failed_records: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base class for all evidence parsers.

    Subclasses can implement either:
    1. Properties: name, category, description, supported_extensions, supported_mime_types
       and method: can_parse()
    2. Classmethod: get_metadata() returning ParserMetadata

    All parsers must implement: parse()
    """

    _metadata: ParserMetadata | None = None

    @classmethod
    def get_metadata(cls) -> ParserMetadata | None:
        """Return parser metadata. Override in subclasses using metadata pattern."""
        return None

    def _get_metadata(self) -> ParserMetadata | None:
        """Get cached metadata instance."""
        if self._metadata is None:
            self._metadata = self.__class__.get_metadata()
        return self._metadata

    @property
    def name(self) -> str:
        """Unique identifier for this parser."""
        meta = self._get_metadata()
        if meta:
            return meta.name
        return self.__class__.__name__.lower().replace("parser", "")

    @property
    def category(self) -> ParserCategory:
        """Category of evidence this parser handles."""
        meta = self._get_metadata()
        if meta:
            # Map string category to enum
            cat_map = {
                "logs": ParserCategory.LOGS,
                "artifacts": ParserCategory.ARTIFACTS,
                "memory": ParserCategory.MEMORY,
                "disk": ParserCategory.DISK,
                "network": ParserCategory.NETWORK,
                "cloud": ParserCategory.CLOUD,
                "windows": ParserCategory.ARTIFACTS,
                "browser": ParserCategory.ARTIFACTS,
                "webserver": ParserCategory.LOGS,
                "ssh": ParserCategory.ARTIFACTS,
                "remoteaccess": ParserCategory.ARTIFACTS,
            }
            return cat_map.get(meta.category, ParserCategory.ARTIFACTS)
        return ParserCategory.ARTIFACTS

    @property
    def description(self) -> str:
        """Human-readable description of what this parser handles."""
        meta = self._get_metadata()
        if meta:
            return meta.description
        return ""

    @property
    def supported_extensions(self) -> list[str]:
        """List of file extensions this parser can handle."""
        meta = self._get_metadata()
        if meta:
            return meta.supported_extensions
        return []

    @property
    def supported_mime_types(self) -> list[str]:
        """List of MIME types this parser can handle."""
        meta = self._get_metadata()
        if meta:
            return meta.mime_types
        return []

    def can_parse(self, file_path: Path | None = None, content: bytes | None = None) -> bool:
        """Check if this parser can handle the given input.

        Default implementation checks file extension against supported_extensions.

        Args:
            file_path: Path to the file to check
            content: First N bytes of file content for magic number detection

        Returns:
            True if this parser can handle the input
        """
        if file_path and self.supported_extensions:
            ext = file_path.suffix.lower()
            return ext in self.supported_extensions or ext.lstrip(".") in [
                e.lstrip(".") for e in self.supported_extensions
            ]
        return True  # Default to True if no extension check possible

    @abstractmethod
    def parse(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
    ) -> Iterator[ParsedEvent]:
        """Parse the input and yield parsed events.

        Args:
            source: Path to file or file-like object to parse
            source_name: Optional name for the source (used in logging)

        Yields:
            ParsedEvent objects for each parsed record
        """
        ...

    def parse_all(
        self,
        source: Path | BinaryIO,
        source_name: str | None = None,
        max_errors: int = 100,
    ) -> ParserResult:
        """Parse all events and return a result summary.

        Args:
            source: Path to file or file-like object to parse
            source_name: Optional name for the source
            max_errors: Maximum number of errors before stopping

        Returns:
            ParserResult with all events and statistics
        """
        events = []
        errors = []
        total = 0
        failed = 0

        try:
            for event in self.parse(source, source_name):
                total += 1
                events.append(event)
        except Exception as e:
            errors.append(f"Parser error: {e}")
            failed += 1

            if len(errors) >= max_errors:
                errors.append(f"Too many errors ({max_errors}), stopping parse")

        return ParserResult(
            success=len(errors) == 0,
            events=events,
            total_records=total,
            parsed_records=len(events),
            failed_records=failed,
            errors=errors,
        )
