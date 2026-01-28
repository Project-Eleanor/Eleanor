"""SSH artifact parsers.

Parses SSH-related artifacts:
- authorized_keys: Allowed public keys for passwordless auth
- known_hosts: Previously connected hosts (TOFU)
- ssh_config: Client configuration
- sshd_config: Server configuration
- PuTTY registry keys

Critical for identifying lateral movement and persistence.
"""

import base64
import hashlib
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
class AuthorizedKeysParser(BaseParser):
    """Parser for SSH authorized_keys files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="authorized_keys",
            display_name="SSH Authorized Keys Parser",
            description="Parses SSH authorized_keys files for allowed public keys",
            supported_extensions=[""],  # No extension
            mime_types=["text/plain"],
            category="ssh",
            priority=75,
        )

    # SSH key types
    KEY_TYPES = {
        "ssh-rsa": "RSA",
        "ssh-dss": "DSA",
        "ssh-ed25519": "Ed25519",
        "ecdsa-sha2-nistp256": "ECDSA-256",
        "ecdsa-sha2-nistp384": "ECDSA-384",
        "ecdsa-sha2-nistp521": "ECDSA-521",
        "sk-ssh-ed25519@openssh.com": "Ed25519-SK",
        "sk-ecdsa-sha2-nistp256@openssh.com": "ECDSA-SK",
    }

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse authorized_keys file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    entry = self._parse_key_line(line)
                    if entry:
                        entry["file_path"] = str(file_path)
                        entry["line_number"] = line_num

                        # Try to extract username from path
                        parts = file_path.parts
                        if "home" in parts:
                            idx = parts.index("home")
                            if idx + 1 < len(parts):
                                entry["local_user"] = parts[idx + 1]

                        yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse authorized_keys: {e}")
            raise

    def _parse_key_line(self, line: str) -> dict[str, Any] | None:
        """Parse a single authorized_keys line."""
        entry = {"raw_line": line}

        # Check for options at start (anything before key type)
        parts = line.split()
        if len(parts) < 2:
            return None

        # Find key type
        key_type_idx = None
        for i, part in enumerate(parts):
            if part in self.KEY_TYPES:
                key_type_idx = i
                break

        if key_type_idx is None:
            return None

        # Extract options if present
        if key_type_idx > 0:
            entry["options"] = " ".join(parts[:key_type_idx])
            self._parse_options(entry["options"], entry)

        entry["key_type"] = parts[key_type_idx]
        entry["key_type_name"] = self.KEY_TYPES.get(parts[key_type_idx], "Unknown")

        if key_type_idx + 1 < len(parts):
            entry["key_data"] = parts[key_type_idx + 1]

            # Calculate fingerprint
            try:
                key_bytes = base64.b64decode(entry["key_data"])
                entry["fingerprint_md5"] = hashlib.md5(key_bytes).hexdigest()
                entry["fingerprint_sha256"] = base64.b64encode(
                    hashlib.sha256(key_bytes).digest()
                ).decode().rstrip("=")
            except Exception:
                pass

        if key_type_idx + 2 < len(parts):
            entry["comment"] = " ".join(parts[key_type_idx + 2:])

            # Extract user@host from comment
            if "@" in entry["comment"]:
                match = re.search(r"(\S+)@(\S+)", entry["comment"])
                if match:
                    entry["key_user"] = match.group(1)
                    entry["key_host"] = match.group(2)

        return entry

    def _parse_options(self, options_str: str, entry: dict) -> None:
        """Parse authorized_keys options."""
        entry["parsed_options"] = {}

        # Common options
        if "command=" in options_str:
            match = re.search(r'command="([^"]+)"', options_str)
            if match:
                entry["parsed_options"]["command"] = match.group(1)
                entry["forced_command"] = match.group(1)

        if "from=" in options_str:
            match = re.search(r'from="([^"]+)"', options_str)
            if match:
                entry["parsed_options"]["from"] = match.group(1)
                entry["allowed_hosts"] = match.group(1)

        simple_options = [
            "no-port-forwarding", "no-X11-forwarding", "no-agent-forwarding",
            "no-pty", "restrict", "cert-authority"
        ]
        for opt in simple_options:
            if opt in options_str:
                entry["parsed_options"][opt.replace("-", "_")] = True

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from authorized_keys entry."""
        comment = entry.get("comment", "")
        key_type = entry.get("key_type_name", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),  # No timestamp in authorized_keys
            message=f"SSH authorized key: {key_type} - {comment[:50]}",
            source="ssh",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["authentication", "configuration"],
                    "type": ["info"],
                    "action": "ssh_authorized_key",
                    "module": "ssh",
                    "dataset": "ssh.authorized_keys",
                },
                "user": {
                    "name": entry.get("local_user"),
                },
                "host": {
                    "os": {"type": "linux"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "authorized_keys",
                    "artifact_type": "ssh_authorized_key",
                    "key_type": entry.get("key_type"),
                    "key_type_name": key_type,
                    "fingerprint_sha256": entry.get("fingerprint_sha256"),
                    "fingerprint_md5": entry.get("fingerprint_md5"),
                    "comment": comment,
                    "key_user": entry.get("key_user"),
                    "key_host": entry.get("key_host"),
                    "options": entry.get("options"),
                    "forced_command": entry.get("forced_command"),
                    "allowed_hosts": entry.get("allowed_hosts"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )


@register_parser
class KnownHostsParser(BaseParser):
    """Parser for SSH known_hosts files."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="known_hosts",
            display_name="SSH Known Hosts Parser",
            description="Parses SSH known_hosts files for previously connected hosts",
            supported_extensions=[""],  # No extension
            mime_types=["text/plain"],
            category="ssh",
            priority=75,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse known_hosts file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    entry = self._parse_known_host_line(line)
                    if entry:
                        entry["file_path"] = str(file_path)
                        entry["line_number"] = line_num

                        # Try to extract username from path
                        parts = file_path.parts
                        if "home" in parts:
                            idx = parts.index("home")
                            if idx + 1 < len(parts):
                                entry["local_user"] = parts[idx + 1]

                        yield self._create_event(entry, case_id, evidence_id)

        except Exception as e:
            logger.error(f"Failed to parse known_hosts: {e}")
            raise

    def _parse_known_host_line(self, line: str) -> dict[str, Any] | None:
        """Parse a single known_hosts line."""
        parts = line.split()
        if len(parts) < 3:
            return None

        entry = {"raw_line": line}

        # Check for hashed hostnames
        if parts[0].startswith("|1|"):
            entry["hashed"] = True
            entry["hostname"] = parts[0]
        else:
            entry["hashed"] = False
            # Hostname can be comma-separated list of names/IPs
            entry["hostname"] = parts[0]
            entry["hostnames"] = [h.strip("[]") for h in parts[0].split(",")]

            # Extract port if in [hostname]:port format
            for host in entry["hostnames"]:
                if host.startswith("[") and "]:" in host:
                    entry["has_custom_port"] = True
                    break

        entry["key_type"] = parts[1]
        entry["key_data"] = parts[2]

        # Calculate fingerprint
        try:
            key_bytes = base64.b64decode(entry["key_data"])
            entry["fingerprint_sha256"] = base64.b64encode(
                hashlib.sha256(key_bytes).digest()
            ).decode().rstrip("=")
        except Exception:
            pass

        if len(parts) > 3:
            entry["comment"] = " ".join(parts[3:])

        return entry

    def _create_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from known_hosts entry."""
        hostname = entry.get("hostname", "unknown")
        key_type = entry.get("key_type", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(UTC),
            message=f"SSH known host: {hostname} ({key_type})",
            source="ssh",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["network", "configuration"],
                    "type": ["info"],
                    "action": "ssh_known_host",
                    "module": "ssh",
                    "dataset": "ssh.known_hosts",
                },
                "destination": {
                    "domain": hostname if not hostname.startswith("|1|") else None,
                },
                "user": {
                    "name": entry.get("local_user"),
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "known_hosts",
                    "artifact_type": "ssh_known_host",
                    "hostname": hostname,
                    "hostnames": entry.get("hostnames"),
                    "hashed": entry.get("hashed"),
                    "key_type": key_type,
                    "fingerprint_sha256": entry.get("fingerprint_sha256"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )


@register_parser
class PuTTYParser(BaseParser):
    """Parser for PuTTY registry exports containing SSH information."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="putty",
            display_name="PuTTY Config Parser",
            description="Parses PuTTY registry exports for SSH sessions and keys",
            supported_extensions=[".reg"],
            mime_types=["text/plain"],
            category="ssh",
            priority=70,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse PuTTY registry export."""
        try:
            with open(file_path, encoding="utf-16", errors="ignore") as f:
                content = f.read()
        except Exception:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

        current_key = None
        current_values = {}

        for line in content.split("\n"):
            line = line.strip()

            # Registry key header
            if line.startswith("[") and line.endswith("]"):
                # Save previous key if it was a session or SSH host key
                if current_key:
                    if "Sessions" in current_key or "SshHostKeys" in current_key:
                        async for event in self._process_key(
                            current_key, current_values, file_path, case_id, evidence_id
                        ):
                            yield event

                current_key = line[1:-1]
                current_values = {}

            # Registry value
            elif "=" in line and current_key:
                key, _, value = line.partition("=")
                key = key.strip('"')
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                current_values[key] = value

        # Process last key
        if current_key and ("Sessions" in current_key or "SshHostKeys" in current_key):
            async for event in self._process_key(
                current_key, current_values, file_path, case_id, evidence_id
            ):
                yield event

    async def _process_key(
        self,
        key_path: str,
        values: dict[str, str],
        file_path: Path,
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Process a PuTTY registry key."""
        if "Sessions" in key_path:
            # Session configuration
            session_name = key_path.split("\\")[-1]
            hostname = values.get("HostName", "")
            port = values.get("PortNumber", "22")
            username = values.get("UserName", "")

            if hostname:
                yield ParsedEvent(
                    id=str(uuid4()),
                    timestamp=datetime.now(UTC),
                    message=f"PuTTY session: {session_name} -> {hostname}",
                    source="putty",
                    raw_data={"key_path": key_path, "values": values},
                    normalized={
                        "event": {
                            "kind": "event",
                            "category": ["configuration"],
                            "type": ["info"],
                            "action": "putty_session",
                            "module": "putty",
                            "dataset": "ssh.putty",
                        },
                        "destination": {
                            "domain": hostname,
                            "port": int(port) if port.isdigit() else 22,
                        },
                        "user": {
                            "name": username,
                        } if username else None,
                        "host": {
                            "os": {"type": "windows"},
                        },
                        "eleanor": {
                            "case_id": case_id,
                            "evidence_id": evidence_id,
                            "parser": "putty",
                            "artifact_type": "putty_session",
                            "session_name": session_name,
                            "protocol": values.get("Protocol"),
                        },
                    },
                    case_id=case_id,
                    evidence_id=evidence_id,
                )

        elif "SshHostKeys" in key_path:
            # Known host keys
            for key_name, key_value in values.items():
                # Key format: rsa2@22:hostname or ed25519@22:hostname
                if "@" in key_name and ":" in key_name:
                    parts = key_name.split("@", 1)
                    key_type = parts[0]
                    port_host = parts[1].split(":", 1)
                    port = port_host[0]
                    hostname = port_host[1] if len(port_host) > 1 else ""

                    yield ParsedEvent(
                        id=str(uuid4()),
                        timestamp=datetime.now(UTC),
                        message=f"PuTTY known host: {hostname} ({key_type})",
                        source="putty",
                        raw_data={"key_name": key_name, "key_value": key_value},
                        normalized={
                            "event": {
                                "kind": "event",
                                "category": ["network", "configuration"],
                                "type": ["info"],
                                "action": "putty_known_host",
                                "module": "putty",
                                "dataset": "ssh.putty",
                            },
                            "destination": {
                                "domain": hostname,
                                "port": int(port) if port.isdigit() else 22,
                            },
                            "host": {
                                "os": {"type": "windows"},
                            },
                            "eleanor": {
                                "case_id": case_id,
                                "evidence_id": evidence_id,
                                "parser": "putty",
                                "artifact_type": "putty_known_host",
                                "key_type": key_type,
                            },
                        },
                        case_id=case_id,
                        evidence_id=evidence_id,
                    )
