"""Mock IRIS adapter for testing."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class MockIRISAdapter:
    """Mock implementation of IRIS adapter for testing."""

    def __init__(self):
        self.name = "iris"
        self.connected = False
        self._cases = {}
        self._assets = {}
        self._iocs = {}
        self._notes = {}

    async def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self.connected = False

    async def health_check(self) -> dict:
        """Return mock health status."""
        return {
            "status": "healthy",
            "connected": self.connected,
            "version": "2.3.0",
            "server_url": "https://iris.local:8443",
            "case_count": len(self._cases),
        }

    async def list_cases(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> dict:
        """Return mock case list."""
        cases = list(self._cases.values())
        if status:
            cases = [c for c in cases if c.get("status") == status]
        total = len(cases)
        cases = cases[offset:offset + limit]
        return {
            "cases": cases,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_case(self, external_id: str) -> dict | None:
        """Return mock case details."""
        return self._cases.get(external_id)

    async def create_case(
        self,
        title: str,
        description: str | None = None,
        severity: str = "medium",
        tags: list[str] | None = None,
    ) -> dict:
        """Simulate case creation."""
        case_id = str(uuid4())
        case = {
            "id": case_id,
            "case_number": f"IRIS-{len(self._cases) + 1:04d}",
            "title": title,
            "description": description or "",
            "severity": severity,
            "status": "open",
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cases[case_id] = case
        return case

    async def update_case(
        self,
        external_id: str,
        title: str | None = None,
        description: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        """Simulate case update."""
        if external_id not in self._cases:
            return None

        case = self._cases[external_id]
        if title:
            case["title"] = title
        if description:
            case["description"] = description
        if severity:
            case["severity"] = severity
        if status:
            case["status"] = status
        if tags is not None:
            case["tags"] = tags
        case["updated_at"] = datetime.now(timezone.utc).isoformat()

        return case

    async def close_case(self, external_id: str, resolution: str | None = None) -> dict | None:
        """Simulate case closure."""
        if external_id not in self._cases:
            return None

        case = self._cases[external_id]
        case["status"] = "closed"
        case["resolution"] = resolution or "Resolved"
        case["closed_at"] = datetime.now(timezone.utc).isoformat()
        case["updated_at"] = datetime.now(timezone.utc).isoformat()

        return case

    async def sync_case(self, eleanor_id: str, external_id: str) -> dict:
        """Simulate case synchronization."""
        return {
            "eleanor_id": eleanor_id,
            "external_id": external_id,
            "sync_status": "synced",
            "last_sync": datetime.now(timezone.utc).isoformat(),
        }

    async def list_assets(self, case_id: str) -> list[dict]:
        """Return mock asset list for a case."""
        return self._assets.get(case_id, [])

    async def add_asset(self, case_id: str, asset: dict) -> dict:
        """Add mock asset to case."""
        asset_id = str(uuid4())
        asset_record = {
            "id": asset_id,
            "case_id": case_id,
            **asset,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if case_id not in self._assets:
            self._assets[case_id] = []
        self._assets[case_id].append(asset_record)

        return asset_record

    async def list_iocs(self, case_id: str) -> list[dict]:
        """Return mock IOC list for a case."""
        return self._iocs.get(case_id, [])

    async def add_ioc(self, case_id: str, ioc: dict) -> dict:
        """Add mock IOC to case."""
        ioc_id = str(uuid4())
        ioc_record = {
            "id": ioc_id,
            "case_id": case_id,
            **ioc,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if case_id not in self._iocs:
            self._iocs[case_id] = []
        self._iocs[case_id].append(ioc_record)

        return ioc_record

    async def list_notes(self, case_id: str) -> list[dict]:
        """Return mock note list for a case."""
        return self._notes.get(case_id, [])

    async def add_note(self, case_id: str, note: dict) -> dict:
        """Add mock note to case."""
        note_id = str(uuid4())
        note_record = {
            "id": note_id,
            "case_id": case_id,
            **note,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if case_id not in self._notes:
            self._notes[case_id] = []
        self._notes[case_id].append(note_record)

        return note_record


class MockIRISCase:
    """Helper class for mock IRIS case data."""

    @staticmethod
    def create_sample_case() -> dict:
        """Create a sample IRIS case for testing."""
        return {
            "id": str(uuid4()),
            "case_number": "IRIS-0001",
            "title": "Sample Security Incident",
            "description": "A sample security incident for testing",
            "severity": "high",
            "status": "open",
            "tags": ["test", "sample"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "assets": [],
            "iocs": [],
            "notes": [],
        }

    @staticmethod
    def create_sample_asset() -> dict:
        """Create a sample asset for testing."""
        return {
            "name": "WORKSTATION-001",
            "asset_type": "computer",
            "ip_address": "192.168.1.101",
            "description": "Affected workstation",
            "compromise_status": "compromised",
        }

    @staticmethod
    def create_sample_ioc() -> dict:
        """Create a sample IOC for testing."""
        return {
            "value": "malicious.example.com",
            "ioc_type": "domain",
            "tlp": "amber",
            "description": "C2 domain",
            "tags": ["c2", "malware"],
        }
