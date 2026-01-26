"""Mock Timesketch adapter for testing."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class MockTimesketchAdapter:
    """Mock implementation of Timesketch adapter for testing."""

    def __init__(self):
        self.name = "timesketch"
        self.connected = False
        self._sketches = {}
        self._timelines = {}
        self._events = {}
        self._saved_views = {}

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
            "version": "2024.01",
            "server_url": "http://timesketch.local:5000",
            "sketches_count": len(self._sketches),
        }

    async def list_sketches(self, limit: int = 100, offset: int = 0) -> dict:
        """Return mock sketch list."""
        sketches = list(self._sketches.values())
        total = len(sketches)
        return {
            "sketches": sketches[offset:offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_sketch(self, sketch_id: str) -> dict | None:
        """Return mock sketch details."""
        return self._sketches.get(sketch_id)

    async def create_sketch(self, name: str, description: str | None = None) -> dict:
        """Create a new sketch."""
        sketch_id = str(uuid4())
        sketch = {
            "id": sketch_id,
            "name": name,
            "description": description or "",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "timelines": [],
            "saved_views": [],
        }
        self._sketches[sketch_id] = sketch
        return sketch

    async def delete_sketch(self, sketch_id: str) -> bool:
        """Delete a sketch."""
        if sketch_id in self._sketches:
            del self._sketches[sketch_id]
            # Clean up associated timelines
            self._timelines = {
                k: v for k, v in self._timelines.items()
                if v.get("sketch_id") != sketch_id
            }
            return True
        return False

    async def list_timelines(self, sketch_id: str) -> list[dict]:
        """Return timelines for a sketch."""
        return [
            t for t in self._timelines.values()
            if t.get("sketch_id") == sketch_id
        ]

    async def upload_timeline(
        self,
        sketch_id: str,
        name: str,
        file_path: str,
        source_type: str = "plaso",
    ) -> dict:
        """Simulate timeline upload."""
        if sketch_id not in self._sketches:
            raise ValueError(f"Sketch {sketch_id} not found")

        timeline_id = str(uuid4())
        timeline = {
            "id": timeline_id,
            "sketch_id": sketch_id,
            "name": name,
            "source_type": source_type,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "events_count": 0,
        }
        self._timelines[timeline_id] = timeline

        # Update sketch
        self._sketches[sketch_id]["timelines"].append(timeline_id)

        return timeline

    async def delete_timeline(self, sketch_id: str, timeline_id: str) -> bool:
        """Delete a timeline."""
        if timeline_id in self._timelines:
            timeline = self._timelines[timeline_id]
            if timeline.get("sketch_id") == sketch_id:
                del self._timelines[timeline_id]
                # Update sketch
                if sketch_id in self._sketches:
                    self._sketches[sketch_id]["timelines"] = [
                        t for t in self._sketches[sketch_id]["timelines"]
                        if t != timeline_id
                    ]
                return True
        return False

    async def search_events(
        self,
        sketch_id: str,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> dict:
        """Search events in a sketch."""
        # Generate sample events for testing
        sample_events = self._generate_sample_events(sketch_id, query, limit)

        return {
            "events": sample_events,
            "total": len(sample_events),
            "query": query,
            "sketch_id": sketch_id,
        }

    def _generate_sample_events(self, sketch_id: str, query: str, limit: int) -> list[dict]:
        """Generate sample timeline events."""
        events = [
            {
                "id": str(uuid4()),
                "sketch_id": sketch_id,
                "timestamp": "2024-01-20T10:30:00Z",
                "datetime": "2024-01-20T10:30:00Z",
                "message": "User jsmith logged in from 192.168.1.101",
                "source_short": "Security",
                "source_long": "Windows Security Event Log",
                "event_type": "Login",
                "data_type": "windows:evtx:record",
                "starred": False,
                "tags": [],
                "comments": [],
            },
            {
                "id": str(uuid4()),
                "sketch_id": sketch_id,
                "timestamp": "2024-01-20T10:35:00Z",
                "datetime": "2024-01-20T10:35:00Z",
                "message": "Process powershell.exe executed with encoded command",
                "source_short": "Sysmon",
                "source_long": "Microsoft-Windows-Sysmon/Operational",
                "event_type": "Process Creation",
                "data_type": "windows:evtx:record",
                "starred": True,
                "tags": ["suspicious", "encoded"],
                "comments": [],
            },
            {
                "id": str(uuid4()),
                "sketch_id": sketch_id,
                "timestamp": "2024-01-20T10:36:00Z",
                "datetime": "2024-01-20T10:36:00Z",
                "message": "Network connection to 198.51.100.50:443",
                "source_short": "Sysmon",
                "source_long": "Microsoft-Windows-Sysmon/Operational",
                "event_type": "Network Connection",
                "data_type": "windows:evtx:record",
                "starred": True,
                "tags": ["c2", "exfiltration"],
                "comments": ["Known C2 server"],
            },
            {
                "id": str(uuid4()),
                "sketch_id": sketch_id,
                "timestamp": "2024-01-20T10:40:00Z",
                "datetime": "2024-01-20T10:40:00Z",
                "message": "File created: C:\\Users\\jsmith\\AppData\\Local\\Temp\\payload.exe",
                "source_short": "Sysmon",
                "source_long": "Microsoft-Windows-Sysmon/Operational",
                "event_type": "File Creation",
                "data_type": "windows:evtx:record",
                "starred": False,
                "tags": ["malware"],
                "comments": [],
            },
        ]
        return events[:limit]

    async def get_event(self, sketch_id: str, event_id: str) -> dict | None:
        """Get a specific event."""
        # Return a sample event
        return {
            "id": event_id,
            "sketch_id": sketch_id,
            "timestamp": "2024-01-20T10:30:00Z",
            "datetime": "2024-01-20T10:30:00Z",
            "message": "Sample event",
            "source_short": "Test",
            "source_long": "Test Source",
            "event_type": "Test",
            "data_type": "test:data",
            "starred": False,
            "tags": [],
            "comments": [],
            "raw": {"original": "data"},
        }

    async def tag_event(self, sketch_id: str, event_id: str, tags: list[str]) -> dict:
        """Add tags to an event."""
        return {
            "id": event_id,
            "sketch_id": sketch_id,
            "tags": tags,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def star_event(self, sketch_id: str, event_id: str, starred: bool = True) -> dict:
        """Star or unstar an event."""
        return {
            "id": event_id,
            "sketch_id": sketch_id,
            "starred": starred,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def add_comment(self, sketch_id: str, event_id: str, comment: str) -> dict:
        """Add a comment to an event."""
        comment_id = str(uuid4())
        return {
            "id": comment_id,
            "event_id": event_id,
            "sketch_id": sketch_id,
            "comment": comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "test_user",
        }

    async def list_saved_views(self, sketch_id: str) -> list[dict]:
        """Return saved views for a sketch."""
        return [
            v for v in self._saved_views.values()
            if v.get("sketch_id") == sketch_id
        ]

    async def create_saved_view(
        self,
        sketch_id: str,
        name: str,
        query: str,
        description: str | None = None,
    ) -> dict:
        """Create a saved view."""
        view_id = str(uuid4())
        view = {
            "id": view_id,
            "sketch_id": sketch_id,
            "name": name,
            "query": query,
            "description": description or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._saved_views[view_id] = view
        return view

    async def delete_saved_view(self, sketch_id: str, view_id: str) -> bool:
        """Delete a saved view."""
        if view_id in self._saved_views:
            view = self._saved_views[view_id]
            if view.get("sketch_id") == sketch_id:
                del self._saved_views[view_id]
                return True
        return False


class MockTimesketchSketch:
    """Helper class for mock Timesketch sketch data."""

    @staticmethod
    def create_sample_sketch() -> dict:
        """Create a sample sketch for testing."""
        sketch_id = str(uuid4())
        return {
            "id": sketch_id,
            "name": "Incident Investigation 2024-001",
            "description": "Timeline analysis for security incident",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "timelines": [
                {
                    "id": str(uuid4()),
                    "name": "WORKSTATION-001",
                    "source_type": "plaso",
                    "events_count": 50000,
                },
                {
                    "id": str(uuid4()),
                    "name": "SERVER-001",
                    "source_type": "plaso",
                    "events_count": 125000,
                },
            ],
            "saved_views": [
                {"id": str(uuid4()), "name": "Suspicious PowerShell"},
                {"id": str(uuid4()), "name": "Network Connections"},
            ],
        }

    @staticmethod
    def create_sample_timeline_event() -> dict:
        """Create a sample timeline event for testing."""
        return {
            "id": str(uuid4()),
            "timestamp": "2024-01-20T10:30:00Z",
            "datetime": "2024-01-20T10:30:00Z",
            "message": "Process cmd.exe spawned by Word.exe",
            "source_short": "Sysmon",
            "source_long": "Microsoft-Windows-Sysmon/Operational",
            "event_type": "Process Creation",
            "data_type": "windows:evtx:record",
            "starred": True,
            "tags": ["suspicious", "macro-execution"],
            "comments": ["Initial compromise vector"],
        }
