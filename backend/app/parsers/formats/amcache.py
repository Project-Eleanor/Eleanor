"""Windows Amcache parser.

Amcache.hve contains information about program execution, including:
- Application paths and timestamps
- SHA1 hashes of executables
- PE metadata (version, publisher, etc.)
- Driver and shortcut information

Location: C:\\Windows\\AppCompat\\Programs\\Amcache.hve
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

try:
    from dissect.regf import RegistryHive
    from dissect.regf.regf import RegistryKey
    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False
    RegistryKey = None  # type: ignore[misc, assignment]


@register_parser
class AmcacheParser(BaseParser):
    """Parser for Windows Amcache.hve registry hive."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="amcache",
            display_name="Windows Amcache Parser",
            description="Parses Windows Amcache.hve for program execution and file metadata",
            supported_extensions=[".hve", ""],
            mime_types=["application/octet-stream"],
            category="windows",
            priority=85,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse Amcache.hve entries."""
        if not DISSECT_AVAILABLE:
            logger.error("dissect.regf required for Amcache parsing")
            return

        try:
            with open(file_path, "rb") as f:
                hive = RegistryHive(f)

            # Parse InventoryApplicationFile entries (Windows 10+)
            async for event in self._parse_inventory_application_file(hive, case_id, evidence_id):
                yield event

            # Parse InventoryApplication entries
            async for event in self._parse_inventory_application(hive, case_id, evidence_id):
                yield event

            # Parse File entries (older format)
            async for event in self._parse_file_entries(hive, case_id, evidence_id):
                yield event

            # Parse InventoryDriverBinary entries
            async for event in self._parse_driver_entries(hive, case_id, evidence_id):
                yield event

        except Exception as e:
            logger.error(f"Failed to parse Amcache: {e}")
            raise

    async def _parse_inventory_application_file(
        self,
        hive: "RegistryHive",
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse InventoryApplicationFile entries (Windows 10 1607+)."""
        try:
            root = hive.open("Root\\InventoryApplicationFile")
        except Exception:
            return

        for subkey in root.subkeys():
            try:
                entry = self._parse_inventory_app_file_key(subkey)
                if entry:
                    yield self._create_file_event(entry, case_id, evidence_id)
            except Exception as e:
                logger.debug(f"Failed to parse InventoryApplicationFile entry: {e}")

    async def _parse_inventory_application(
        self,
        hive: "RegistryHive",
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse InventoryApplication entries."""
        try:
            root = hive.open("Root\\InventoryApplication")
        except Exception:
            return

        for subkey in root.subkeys():
            try:
                entry = self._parse_inventory_app_key(subkey)
                if entry:
                    yield self._create_application_event(entry, case_id, evidence_id)
            except Exception as e:
                logger.debug(f"Failed to parse InventoryApplication entry: {e}")

    async def _parse_file_entries(
        self,
        hive: "RegistryHive",
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse legacy File entries (pre-1607)."""
        try:
            root = hive.open("Root\\File")
        except Exception:
            return

        for volume_key in root.subkeys():
            for file_key in volume_key.subkeys():
                try:
                    entry = self._parse_legacy_file_key(file_key)
                    if entry:
                        yield self._create_file_event(entry, case_id, evidence_id)
                except Exception as e:
                    logger.debug(f"Failed to parse File entry: {e}")

    async def _parse_driver_entries(
        self,
        hive: "RegistryHive",
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse InventoryDriverBinary entries."""
        try:
            root = hive.open("Root\\InventoryDriverBinary")
        except Exception:
            return

        for subkey in root.subkeys():
            try:
                entry = self._parse_driver_key(subkey)
                if entry:
                    yield self._create_driver_event(entry, case_id, evidence_id)
            except Exception as e:
                logger.debug(f"Failed to parse driver entry: {e}")

    def _parse_inventory_app_file_key(self, key: "RegistryKey") -> dict[str, Any] | None:
        """Parse InventoryApplicationFile registry key."""
        entry = {"key_name": key.name}

        for value in key.values():
            name = value.name
            try:
                val = value.value
                if name == "LowerCaseLongPath":
                    entry["path"] = val
                elif name == "Name":
                    entry["name"] = val
                elif name == "Publisher":
                    entry["publisher"] = val
                elif name == "Version":
                    entry["version"] = val
                elif name == "BinFileVersion":
                    entry["bin_file_version"] = val
                elif name == "BinaryType":
                    entry["binary_type"] = val
                elif name == "ProductName":
                    entry["product_name"] = val
                elif name == "ProductVersion":
                    entry["product_version"] = val
                elif name == "LinkDate":
                    entry["link_date"] = val
                elif name == "BinProductVersion":
                    entry["bin_product_version"] = val
                elif name == "Size":
                    entry["size"] = val
                elif name == "Language":
                    entry["language"] = val
                elif name == "IsPeFile":
                    entry["is_pe"] = val
                elif name == "IsOsComponent":
                    entry["is_os_component"] = val
                elif name == "FileId":
                    # FileId contains SHA1 hash
                    if isinstance(val, str) and len(val) >= 40:
                        entry["sha1"] = val[-40:].lower()
            except Exception:
                continue

        return entry if entry.get("path") or entry.get("name") else None

    def _parse_inventory_app_key(self, key: Any) -> dict[str, Any] | None:
        """Parse InventoryApplication registry key."""
        entry = {"key_name": key.name}

        for value in key.values():
            name = value.name
            try:
                val = value.value
                if name == "Name":
                    entry["name"] = val
                elif name == "Publisher":
                    entry["publisher"] = val
                elif name == "Version":
                    entry["version"] = val
                elif name == "InstallDate":
                    entry["install_date"] = val
                elif name == "Source":
                    entry["source"] = val
                elif name == "RootDirPath":
                    entry["root_dir"] = val
                elif name == "UninstallString":
                    entry["uninstall_string"] = val
                elif name == "Type":
                    entry["type"] = val
            except Exception:
                continue

        return entry if entry.get("name") else None

    def _parse_legacy_file_key(self, key: Any) -> dict[str, Any] | None:
        """Parse legacy File registry key."""
        entry = {"key_name": key.name}

        # Key name format: <volume_id>|<file_id>|<sha1>
        parts = key.name.split("|")
        if len(parts) >= 3:
            entry["sha1"] = parts[2].lower() if len(parts[2]) == 40 else None

        for value in key.values():
            name = value.name
            try:
                val = value.value
                if name == "15":  # Full path
                    entry["path"] = val
                elif name == "0":  # Product name
                    entry["product_name"] = val
                elif name == "1":  # Company name
                    entry["publisher"] = val
                elif name == "5":  # Product version
                    entry["product_version"] = val
                elif name == "6":  # File size
                    entry["size"] = val
                elif name == "11":  # Last modification time
                    entry["modified"] = self._filetime_to_datetime(val)
                elif name == "12":  # Creation time
                    entry["created"] = self._filetime_to_datetime(val)
                elif name == "17":  # Link timestamp
                    entry["link_date"] = val
            except Exception:
                continue

        return entry if entry.get("path") else None

    def _parse_driver_key(self, key: Any) -> dict[str, Any] | None:
        """Parse InventoryDriverBinary registry key."""
        entry = {"key_name": key.name}

        for value in key.values():
            name = value.name
            try:
                val = value.value
                if name == "DriverName":
                    entry["driver_name"] = val
                elif name == "DriverVersion":
                    entry["version"] = val
                elif name == "Product":
                    entry["product"] = val
                elif name == "ProductVersion":
                    entry["product_version"] = val
                elif name == "DriverCompany":
                    entry["company"] = val
                elif name == "Inf":
                    entry["inf"] = val
                elif name == "Service":
                    entry["service"] = val
                elif name == "DriverSigned":
                    entry["signed"] = val
                elif name == "DriverCheckSum":
                    entry["checksum"] = val
            except Exception:
                continue

        return entry if entry.get("driver_name") else None

    def _create_file_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event for file entry."""
        path = entry.get("path") or entry.get("name", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=entry.get("modified") or entry.get("created") or datetime.now(timezone.utc),
            message=f"Amcache File: {path}",
            source="amcache",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["process", "file"],
                    "type": ["info"],
                    "action": "amcache_file_entry",
                    "module": "amcache",
                    "dataset": "windows.amcache",
                },
                "file": {
                    "path": path,
                    "name": Path(path).name if path else None,
                    "size": entry.get("size"),
                    "hash": {
                        "sha1": entry.get("sha1"),
                    } if entry.get("sha1") else None,
                    "pe": {
                        "product": entry.get("product_name"),
                        "company": entry.get("publisher"),
                        "file_version": entry.get("bin_file_version") or entry.get("version"),
                    } if entry.get("product_name") or entry.get("publisher") else None,
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "amcache",
                    "artifact_type": "amcache_file",
                    "language": entry.get("language"),
                    "is_pe": entry.get("is_pe"),
                    "is_os_component": entry.get("is_os_component"),
                    "link_date": entry.get("link_date"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _create_application_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event for application entry."""
        name = entry.get("name", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            message=f"Amcache Application: {name}",
            source="amcache",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["package"],
                    "type": ["info"],
                    "action": "amcache_application_entry",
                    "module": "amcache",
                    "dataset": "windows.amcache",
                },
                "package": {
                    "name": name,
                    "version": entry.get("version"),
                    "type": entry.get("type"),
                    "installed": entry.get("install_date"),
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "amcache",
                    "artifact_type": "amcache_application",
                    "publisher": entry.get("publisher"),
                    "source": entry.get("source"),
                    "root_dir": entry.get("root_dir"),
                    "uninstall_string": entry.get("uninstall_string"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _create_driver_event(
        self,
        entry: dict[str, Any],
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event for driver entry."""
        name = entry.get("driver_name", "unknown")

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            message=f"Amcache Driver: {name}",
            source="amcache",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": ["driver"],
                    "type": ["info"],
                    "action": "amcache_driver_entry",
                    "module": "amcache",
                    "dataset": "windows.amcache",
                },
                "file": {
                    "name": name,
                },
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "amcache",
                    "artifact_type": "amcache_driver",
                    "version": entry.get("version"),
                    "product": entry.get("product"),
                    "company": entry.get("company"),
                    "inf": entry.get("inf"),
                    "service": entry.get("service"),
                    "signed": entry.get("signed"),
                    "checksum": entry.get("checksum"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _filetime_to_datetime(self, filetime: int) -> datetime | None:
        """Convert Windows FILETIME to datetime."""
        try:
            if filetime == 0:
                return None
            epoch_diff = 116444736000000000
            timestamp = (filetime - epoch_diff) / 10000000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except Exception:
            return None
