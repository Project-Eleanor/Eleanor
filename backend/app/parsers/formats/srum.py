"""Windows SRUM (System Resource Usage Monitor) parser.

SRUM tracks system resource usage including:
- Application resource usage (CPU time, bytes read/written)
- Network data usage per application
- Network connectivity events
- Energy usage
- Push notifications

Location: C:\Windows\System32\sru\SRUDB.dat (ESE database)
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from app.parsers.base import BaseParser, ParsedEvent, ParserMetadata
from app.parsers.registry import register_parser

logger = logging.getLogger(__name__)

try:
    from dissect.esedb import EseDB
    DISSECT_AVAILABLE = True
except ImportError:
    DISSECT_AVAILABLE = False


# SRUM table GUIDs
SRUM_TABLES = {
    "{D10CA2FE-6FCF-4F6D-848E-B2E99266FA89}": "ApplicationResourceUsage",
    "{973F5D5C-1D90-4944-BE8E-24B94231A174}": "NetworkConnectivity",
    "{DD6636C4-8929-4683-974E-22C046A43763}": "NetworkDataUsage",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}": "EnergyUsage",
    "{FEE4E14F-02A9-4550-B5CE-5FA2DA202E37}LT": "EnergyUsageLongTerm",
    "{DA73FB89-2BEA-4DDC-86B8-6E048C6DA477}": "PushNotification",
    "{7ACBBAA3-D029-4BE4-9A7A-0885927F1D8F}": "SDPCpuProvider",
    "{C03217C4-4ED2-4B89-92A7-26FA4D1C74E8}": "SDPNetworkProvider",
}


@register_parser
class SRUMParser(BaseParser):
    """Parser for Windows System Resource Usage Monitor database."""

    @classmethod
    def get_metadata(cls) -> ParserMetadata:
        return ParserMetadata(
            name="srum",
            display_name="Windows SRUM Parser",
            description="Parses Windows SRUDB.dat for application and network usage data",
            supported_extensions=[".dat", ".DAT"],
            mime_types=["application/octet-stream"],
            category="windows",
            priority=80,
        )

    async def parse(
        self,
        file_path: Path,
        case_id: str | None = None,
        evidence_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse SRUDB.dat ESE database."""
        if not DISSECT_AVAILABLE:
            logger.error("dissect.esedb required for SRUM parsing")
            return

        try:
            with open(file_path, "rb") as f:
                db = EseDB(f)

            # Parse SruDbIdMapTable for ID to name mappings
            id_map = self._build_id_map(db)

            # Parse each SRUM table
            for table_name in db.tables():
                if table_name.startswith("{"):
                    table_type = SRUM_TABLES.get(table_name, "Unknown")
                    async for event in self._parse_srum_table(
                        db, table_name, table_type, id_map, case_id, evidence_id
                    ):
                        yield event

        except Exception as e:
            logger.error(f"Failed to parse SRUM database: {e}")
            raise

    def _build_id_map(self, db: Any) -> dict[int, str]:
        """Build mapping from SRUM IDs to application names."""
        id_map = {}

        try:
            table = db.table("SruDbIdMapTable")
            for record in table.records():
                try:
                    id_val = record.get("IdIndex")
                    id_blob = record.get("IdBlob")

                    if id_val and id_blob:
                        # IdBlob is typically UTF-16 encoded
                        if isinstance(id_blob, bytes):
                            name = id_blob.decode("utf-16-le", errors="ignore").rstrip("\x00")
                        else:
                            name = str(id_blob)
                        id_map[id_val] = name
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Failed to parse SruDbIdMapTable: {e}")

        return id_map

    async def _parse_srum_table(
        self,
        db: Any,
        table_name: str,
        table_type: str,
        id_map: dict[int, str],
        case_id: str | None,
        evidence_id: str | None,
    ) -> AsyncIterator[ParsedEvent]:
        """Parse a SRUM table and yield events."""
        try:
            table = db.table(table_name)
        except Exception:
            return

        for record in table.records():
            try:
                entry = self._parse_record(record, table_type, id_map)
                if entry:
                    yield self._create_event(entry, table_type, case_id, evidence_id)
            except Exception as e:
                logger.debug(f"Failed to parse SRUM record: {e}")

    def _parse_record(
        self,
        record: Any,
        table_type: str,
        id_map: dict[int, str],
    ) -> dict[str, Any] | None:
        """Parse a single SRUM record."""
        entry = {"table_type": table_type}

        # Common fields
        try:
            entry["timestamp"] = self._parse_timestamp(record.get("TimeStamp"))
            entry["auto_inc_id"] = record.get("AutoIncId")

            # Resolve AppId to name
            app_id = record.get("AppId")
            if app_id:
                entry["app_id"] = app_id
                entry["app_name"] = id_map.get(app_id, f"Unknown({app_id})")

            # Resolve UserId to SID
            user_id = record.get("UserId")
            if user_id:
                entry["user_id"] = user_id
                entry["user_sid"] = id_map.get(user_id, f"Unknown({user_id})")

        except Exception:
            pass

        # Table-specific fields
        if table_type == "ApplicationResourceUsage":
            self._parse_app_resource(record, entry)
        elif table_type == "NetworkDataUsage":
            self._parse_network_data(record, entry)
        elif table_type == "NetworkConnectivity":
            self._parse_network_connectivity(record, entry)
        elif table_type == "EnergyUsage":
            self._parse_energy_usage(record, entry)
        elif table_type == "PushNotification":
            self._parse_push_notification(record, entry)

        return entry if entry.get("app_name") or entry.get("timestamp") else None

    def _parse_app_resource(self, record: Any, entry: dict) -> None:
        """Parse ApplicationResourceUsage fields."""
        try:
            entry["foreground_cycle_time"] = record.get("ForegroundCycleTime")
            entry["background_cycle_time"] = record.get("BackgroundCycleTime")
            entry["face_time"] = record.get("FaceTime")
            entry["foreground_context_switches"] = record.get("ForegroundContextSwitches")
            entry["background_context_switches"] = record.get("BackgroundContextSwitches")
            entry["foreground_bytes_read"] = record.get("ForegroundBytesRead")
            entry["foreground_bytes_written"] = record.get("ForegroundBytesWritten")
            entry["background_bytes_read"] = record.get("BackgroundBytesRead")
            entry["background_bytes_written"] = record.get("BackgroundBytesWritten")
            entry["foreground_num_read_operations"] = record.get("ForegroundNumReadOperations")
            entry["foreground_num_write_operations"] = record.get("ForegroundNumWriteOperations")
        except Exception:
            pass

    def _parse_network_data(self, record: Any, entry: dict) -> None:
        """Parse NetworkDataUsage fields."""
        try:
            entry["interface_luid"] = record.get("InterfaceLuid")
            entry["l2_profile_id"] = record.get("L2ProfileId")
            entry["l2_profile_flags"] = record.get("L2ProfileFlags")
            entry["bytes_sent"] = record.get("BytesSent")
            entry["bytes_received"] = record.get("BytesRecvd")
        except Exception:
            pass

    def _parse_network_connectivity(self, record: Any, entry: dict) -> None:
        """Parse NetworkConnectivity fields."""
        try:
            entry["interface_luid"] = record.get("InterfaceLuid")
            entry["l2_profile_id"] = record.get("L2ProfileId")
            entry["connected_time"] = record.get("ConnectedTime")
            entry["connect_start_time"] = self._parse_timestamp(record.get("ConnectStartTime"))
        except Exception:
            pass

    def _parse_energy_usage(self, record: Any, entry: dict) -> None:
        """Parse EnergyUsage fields."""
        try:
            entry["battery_level"] = record.get("BatteryLevel")
            entry["cpu_time"] = record.get("CpuTime")
            entry["network_bytes_raw"] = record.get("NetworkBytesRaw")
            entry["foreground_duration"] = record.get("ForegroundDuration")
        except Exception:
            pass

    def _parse_push_notification(self, record: Any, entry: dict) -> None:
        """Parse PushNotification fields."""
        try:
            entry["notification_type"] = record.get("NotificationType")
            entry["payload_size"] = record.get("PayloadSize")
        except Exception:
            pass

    def _create_event(
        self,
        entry: dict[str, Any],
        table_type: str,
        case_id: str | None,
        evidence_id: str | None,
    ) -> ParsedEvent:
        """Create ECS event from SRUM entry."""
        app_name = entry.get("app_name", "unknown")
        timestamp = entry.get("timestamp") or datetime.now(timezone.utc)

        # Determine event category based on table type
        if table_type in ("NetworkDataUsage", "NetworkConnectivity"):
            category = ["network"]
            action = "network_usage"
        elif table_type == "ApplicationResourceUsage":
            category = ["process"]
            action = "application_resource_usage"
        elif table_type == "EnergyUsage":
            category = ["host"]
            action = "energy_usage"
        else:
            category = ["host"]
            action = "srum_entry"

        # Build message
        if table_type == "NetworkDataUsage":
            sent = entry.get("bytes_sent", 0) or 0
            recv = entry.get("bytes_received", 0) or 0
            message = f"SRUM Network: {app_name} - Sent: {sent}, Received: {recv}"
        elif table_type == "ApplicationResourceUsage":
            message = f"SRUM App Resource: {app_name}"
        else:
            message = f"SRUM {table_type}: {app_name}"

        return ParsedEvent(
            id=str(uuid4()),
            timestamp=timestamp,
            message=message,
            source="srum",
            raw_data=entry,
            normalized={
                "event": {
                    "kind": "event",
                    "category": category,
                    "type": ["info"],
                    "action": action,
                    "module": "srum",
                    "dataset": f"windows.srum.{table_type.lower()}",
                },
                "process": {
                    "name": app_name,
                } if table_type == "ApplicationResourceUsage" else None,
                "network": {
                    "bytes": (entry.get("bytes_sent", 0) or 0) + (entry.get("bytes_received", 0) or 0),
                } if table_type == "NetworkDataUsage" else None,
                "source": {
                    "bytes": entry.get("bytes_sent"),
                } if table_type == "NetworkDataUsage" else None,
                "destination": {
                    "bytes": entry.get("bytes_received"),
                } if table_type == "NetworkDataUsage" else None,
                "user": {
                    "id": entry.get("user_sid"),
                } if entry.get("user_sid") else None,
                "host": {
                    "os": {"type": "windows"},
                },
                "eleanor": {
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "parser": "srum",
                    "artifact_type": f"srum_{table_type.lower()}",
                    "app_id": entry.get("app_id"),
                    "foreground_cycle_time": entry.get("foreground_cycle_time"),
                    "background_cycle_time": entry.get("background_cycle_time"),
                    "foreground_bytes_read": entry.get("foreground_bytes_read"),
                    "foreground_bytes_written": entry.get("foreground_bytes_written"),
                    "interface_luid": entry.get("interface_luid"),
                },
            },
            case_id=case_id,
            evidence_id=evidence_id,
        )

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse timestamp from various formats."""
        if value is None:
            return None

        try:
            if isinstance(value, datetime):
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            elif isinstance(value, (int, float)):
                # Could be FILETIME or Unix timestamp
                if value > 100000000000000:  # FILETIME
                    epoch_diff = 116444736000000000
                    timestamp = (value - epoch_diff) / 10000000
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                else:
                    return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            pass

        return None
