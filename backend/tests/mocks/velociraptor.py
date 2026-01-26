"""Mock Velociraptor adapter for testing."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class MockVelociraptorAdapter:
    """Mock implementation of Velociraptor adapter for testing."""

    def __init__(self):
        self.name = "velociraptor"
        self.connected = False
        self._endpoints = self._generate_sample_endpoints()
        self._artifacts = self._generate_sample_artifacts()
        self._jobs = {}
        self._hunts = {}

    def _generate_sample_endpoints(self) -> list[dict]:
        """Generate sample endpoint data."""
        return [
            {
                "client_id": "C.abc123def456",
                "hostname": "WORKSTATION-001",
                "os": "Windows 10 Enterprise 21H2",
                "ip_address": "192.168.1.101",
                "mac_address": "00:11:22:33:44:55",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "first_seen": "2024-01-15T10:30:00Z",
                "online": True,
                "labels": ["production", "finance"],
                "agent_version": "0.7.0",
            },
            {
                "client_id": "C.xyz789ghi012",
                "hostname": "SERVER-001",
                "os": "Windows Server 2019 Datacenter",
                "ip_address": "192.168.1.10",
                "mac_address": "00:11:22:33:44:66",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "first_seen": "2024-01-10T08:00:00Z",
                "online": True,
                "labels": ["production", "infrastructure", "ad-server"],
                "agent_version": "0.7.0",
            },
            {
                "client_id": "C.jkl345mno678",
                "hostname": "WORKSTATION-002",
                "os": "Windows 11 Enterprise",
                "ip_address": "192.168.1.102",
                "mac_address": "00:11:22:33:44:77",
                "last_seen": "2024-01-20T15:00:00Z",
                "first_seen": "2024-01-18T09:00:00Z",
                "online": False,
                "labels": ["production", "hr"],
                "agent_version": "0.7.0",
            },
        ]

    def _generate_sample_artifacts(self) -> list[dict]:
        """Generate sample artifact definitions."""
        return [
            {
                "name": "Windows.System.Pslist",
                "description": "List running processes",
                "category": "system",
                "parameters": [],
            },
            {
                "name": "Windows.System.Services",
                "description": "List Windows services",
                "category": "system",
                "parameters": [],
            },
            {
                "name": "Windows.Network.Netstat",
                "description": "List network connections",
                "category": "network",
                "parameters": [],
            },
            {
                "name": "Windows.EventLogs.Security",
                "description": "Collect Security event logs",
                "category": "logs",
                "parameters": [
                    {"name": "StartDate", "type": "timestamp", "required": False},
                    {"name": "EndDate", "type": "timestamp", "required": False},
                ],
            },
            {
                "name": "Windows.NTFS.MFT",
                "description": "Parse NTFS Master File Table",
                "category": "forensics",
                "parameters": [
                    {"name": "PathRegex", "type": "string", "required": False},
                ],
            },
            {
                "name": "Generic.Forensic.Timeline",
                "description": "Create forensic timeline",
                "category": "forensics",
                "parameters": [],
            },
        ]

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
            "version": "0.7.0",
            "server_url": "https://velociraptor.local:8003",
            "client_count": len(self._endpoints),
        }

    async def list_endpoints(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        online_only: bool = False,
    ) -> dict:
        """Return mock endpoint list."""
        endpoints = self._endpoints.copy()

        if search:
            search_lower = search.lower()
            endpoints = [
                e for e in endpoints
                if search_lower in e["hostname"].lower()
                or search_lower in e.get("ip_address", "")
            ]

        if online_only:
            endpoints = [e for e in endpoints if e.get("online", False)]

        total = len(endpoints)
        endpoints = endpoints[offset:offset + limit]

        return {
            "endpoints": endpoints,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_endpoint(self, client_id: str) -> dict | None:
        """Return mock endpoint details."""
        for endpoint in self._endpoints:
            if endpoint["client_id"] == client_id:
                return endpoint
        return None

    async def search_endpoints(self, query: str) -> list[dict]:
        """Search endpoints by hostname or IP."""
        query_lower = query.lower()
        return [
            e for e in self._endpoints
            if query_lower in e["hostname"].lower()
            or query_lower in e.get("ip_address", "")
        ]

    async def list_artifacts(self, category: str | None = None) -> list[dict]:
        """Return mock artifact list."""
        if category:
            return [a for a in self._artifacts if a.get("category") == category]
        return self._artifacts

    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: dict | None = None,
        urgent: bool = False,
    ) -> dict:
        """Simulate artifact collection."""
        job_id = str(uuid4())
        self._jobs[job_id] = {
            "job_id": job_id,
            "client_id": client_id,
            "artifact_name": artifact_name,
            "parameters": parameters or {},
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "progress": 0,
        }
        return self._jobs[job_id]

    async def get_collection_status(self, job_id: str) -> dict | None:
        """Return mock collection status."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            # Simulate progress
            if job["status"] == "running":
                job["progress"] = min(100, job["progress"] + 25)
                if job["progress"] >= 100:
                    job["status"] = "completed"
            return job
        return None

    async def get_collection_results(self, job_id: str, limit: int = 1000) -> dict:
        """Return mock collection results."""
        return {
            "job_id": job_id,
            "rows": [
                {"Name": "explorer.exe", "Pid": 1234, "Ppid": 456},
                {"Name": "chrome.exe", "Pid": 5678, "Ppid": 1234},
                {"Name": "svchost.exe", "Pid": 789, "Ppid": 4},
            ],
            "total_rows": 3,
        }

    async def list_hunts(self, limit: int = 100, state: str | None = None) -> list[dict]:
        """Return mock hunt list."""
        hunts = list(self._hunts.values())
        if state:
            hunts = [h for h in hunts if h.get("state") == state]
        return hunts[:limit]

    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: str | None = None,
        parameters: dict | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Simulate hunt creation."""
        hunt_id = f"H.{uuid4().hex[:12]}"
        hunt = {
            "hunt_id": hunt_id,
            "name": name,
            "description": description or "",
            "artifact_name": artifact_name,
            "parameters": parameters or {},
            "labels": labels or [],
            "state": "paused",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_clients": 0,
            "completed_clients": 0,
        }
        self._hunts[hunt_id] = hunt
        return hunt

    async def start_hunt(self, hunt_id: str) -> dict | None:
        """Start a hunt."""
        if hunt_id in self._hunts:
            self._hunts[hunt_id]["state"] = "running"
            self._hunts[hunt_id]["total_clients"] = len(self._endpoints)
            return self._hunts[hunt_id]
        return None

    async def stop_hunt(self, hunt_id: str) -> dict | None:
        """Stop a hunt."""
        if hunt_id in self._hunts:
            self._hunts[hunt_id]["state"] = "stopped"
            return self._hunts[hunt_id]
        return None

    async def get_hunt_results(self, hunt_id: str, limit: int = 1000) -> dict:
        """Return mock hunt results."""
        return {
            "hunt_id": hunt_id,
            "results": [
                {"client_id": e["client_id"], "hostname": e["hostname"], "data": {}}
                for e in self._endpoints
            ],
            "total": len(self._endpoints),
        }

    async def isolate_host(self, client_id: str) -> dict:
        """Simulate host isolation."""
        return {
            "client_id": client_id,
            "action": "isolate",
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def unisolate_host(self, client_id: str) -> dict:
        """Simulate host unisolation."""
        return {
            "client_id": client_id,
            "action": "unisolate",
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def quarantine_file(self, client_id: str, file_path: str) -> dict:
        """Simulate file quarantine."""
        return {
            "client_id": client_id,
            "file_path": file_path,
            "action": "quarantine",
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def kill_process(self, client_id: str, pid: int) -> dict:
        """Simulate process termination."""
        return {
            "client_id": client_id,
            "pid": pid,
            "action": "kill_process",
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
