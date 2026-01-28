"""Timesketch adapter implementation.

Provides integration with Timesketch for:
- Sketch management (create, search, annotate)
- Timeline upload and search
- Event tagging and starring
- Saved views

Timesketch API: https://timesketch.org/guides/user/api/
"""

import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    SavedView,
    Sketch,
    Timeline,
    TimelineAdapter,
    TimelineEvent,
)
from app.adapters.timesketch.schemas import (
    TimesketchEvent as TSEvent,
)
from app.adapters.timesketch.schemas import (
    TimesketchSavedView,
    TimesketchSketch,
    TimesketchTimeline,
)

logger = logging.getLogger(__name__)


class TimesketchAdapter(TimelineAdapter):
    """Adapter for Timesketch timeline analysis platform."""

    name = "timesketch"
    description = "Timesketch timeline analysis"

    def __init__(self, config: AdapterConfig):
        """Initialize Timesketch adapter."""
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._version: str | None = None
        self._session_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }

            # Timesketch supports both API key and session auth
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            elif self._session_token:
                headers["Cookie"] = f"session={self._session_token}"

            self._client = httpx.AsyncClient(
                base_url=self.config.url.rstrip("/"),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers=headers,
            )

        return self._client

    async def _authenticate(self) -> None:
        """Authenticate with username/password if no API key."""
        if self.config.api_key:
            return

        if self._session_token:
            # Already authenticated
            return

        username = self.config.extra.get("username", "")
        password = self.config.extra.get("password", "")

        if not username or not password:
            raise ValueError("Timesketch requires API key or username/password")

        # Create a temporary client for authentication (without auth headers)
        async with httpx.AsyncClient(
            base_url=self.config.url.rstrip("/"),
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        ) as auth_client:
            # First, get the login page to obtain CSRF token
            login_page = await auth_client.get("/login/")

            # Extract CSRF token from hidden form field
            csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page.text)
            if not csrf_match:
                raise ValueError("Could not find CSRF token in login page")

            csrf_token = csrf_match.group(1)
            logger.debug("Found CSRF token for Timesketch login")

            # Perform login with CSRF token
            response = await auth_client.post(
                "/login/",
                data={
                    "username": username,
                    "password": password,
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

            # Check if login was successful (redirect to dashboard)
            if response.status_code == 302:
                # Extract the new session cookie after successful login
                if "session" in auth_client.cookies:
                    self._session_token = auth_client.cookies["session"]
                    logger.info("Timesketch authentication successful")
                    # Force recreation of main client with new session
                    if self._client:
                        await self._client.aclose()
                    self._client = None
                else:
                    raise ValueError("Login succeeded but no session cookie received")
            elif response.status_code == 400:
                raise ValueError("Login failed: Invalid credentials or CSRF error")
            else:
                raise ValueError(f"Login failed with status {response.status_code}")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make API request to Timesketch."""
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()

        if not response.content:
            return {}

        result = response.json()

        # Timesketch wraps responses in objects envelope
        if isinstance(result, dict) and "objects" in result:
            return result
        return result

    async def health_check(self) -> AdapterHealth:
        """Check Timesketch connectivity."""
        try:
            # Try to authenticate if needed
            await self._authenticate()

            # Check version endpoint
            result = await self._request("GET", "/api/v1/version/")
            self._version = result.get("meta", {}).get("version", "unknown")
            self._status = AdapterStatus.CONNECTED

            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                version=self._version,
                message="Connected to Timesketch",
            )
        except httpx.HTTPError as e:
            logger.error("Timesketch health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"HTTP error: {e}",
            )
        except Exception as e:
            logger.error("Timesketch health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized)."""
        return {
            "url": self.config.url,
            "verify_ssl": self.config.verify_ssl,
            "has_api_key": bool(self.config.api_key),
            "has_credentials": bool(
                self.config.extra.get("username") and self.config.extra.get("password")
            ),
        }

    def _ts_sketch_to_sketch(self, ts_sketch: TimesketchSketch) -> Sketch:
        """Convert Timesketch sketch to our Sketch model."""
        return Sketch(
            sketch_id=str(ts_sketch.id),
            name=ts_sketch.name,
            description=ts_sketch.description,
            created_at=ts_sketch.created_at,
            updated_at=ts_sketch.updated_at,
            owner=ts_sketch.owner,
            status=ts_sketch.status_name,
            timeline_count=ts_sketch.timeline_count,
            metadata={
                "labels": ts_sketch.label_string,
            },
        )

    def _ts_timeline_to_timeline(
        self,
        ts_timeline: TimesketchTimeline,
        sketch_id: str,
    ) -> Timeline:
        """Convert Timesketch timeline to our Timeline model."""
        return Timeline(
            timeline_id=str(ts_timeline.id),
            sketch_id=sketch_id,
            name=ts_timeline.name,
            description=ts_timeline.description,
            created_at=ts_timeline.created_at,
            source_type=ts_timeline.searchindex.get("data_type", "unknown"),
            metadata={
                "index_name": ts_timeline.index_name,
                "status": ts_timeline.status_name,
                "color": ts_timeline.color,
            },
        )

    def _ts_event_to_event(self, ts_event: TSEvent) -> TimelineEvent:
        """Convert Timesketch event to our TimelineEvent model."""
        return TimelineEvent(
            event_id=ts_event.event_id,
            timestamp=ts_event.timestamp or datetime.utcnow(),
            message=ts_event.message,
            source=ts_event.source_name,
            source_short=ts_event.source_short,
            timestamp_desc=ts_event.timestamp_desc,
            tags=ts_event.tags,
            starred=ts_event.starred,
            comments=ts_event.comments,
            attributes=ts_event.attributes,
        )

    # =========================================================================
    # Sketch Management
    # =========================================================================

    async def list_sketches(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Sketch]:
        """List timeline sketches."""
        result = await self._request("GET", "/api/v1/sketches/")
        objects = result.get("objects", [])

        sketches = []
        for obj in objects[offset : offset + limit]:
            ts_sketch = TimesketchSketch(**obj)
            sketches.append(self._ts_sketch_to_sketch(ts_sketch))

        return sketches

    async def get_sketch(self, sketch_id: str) -> Sketch | None:
        """Get sketch details."""
        try:
            result = await self._request("GET", f"/api/v1/sketches/{sketch_id}/")
            objects = result.get("objects", [])
            if not objects:
                return None
            ts_sketch = TimesketchSketch(**objects[0])
            return self._ts_sketch_to_sketch(ts_sketch)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_sketch(
        self,
        name: str,
        description: str | None = None,
    ) -> Sketch:
        """Create a new sketch."""
        payload = {
            "name": name,
            "description": description or "",
        }

        result = await self._request(
            "POST",
            "/api/v1/sketches/",
            json=payload,
        )
        objects = result.get("objects", [])
        ts_sketch = TimesketchSketch(**objects[0])
        return self._ts_sketch_to_sketch(ts_sketch)

    async def delete_sketch(self, sketch_id: str) -> bool:
        """Delete a sketch."""
        try:
            await self._request("DELETE", f"/api/v1/sketches/{sketch_id}/")
            return True
        except Exception as e:
            logger.error("Failed to delete sketch %s: %s", sketch_id, e)
            return False

    # =========================================================================
    # Timeline Management
    # =========================================================================

    async def list_timelines(self, sketch_id: str) -> list[Timeline]:
        """List timelines in a sketch."""
        result = await self._request("GET", f"/api/v1/sketches/{sketch_id}/timelines/")
        objects = result.get("objects", [])

        return [
            self._ts_timeline_to_timeline(TimesketchTimeline(**obj), sketch_id) for obj in objects
        ]

    async def upload_timeline(
        self,
        sketch_id: str,
        name: str,
        file_path: str,
        source_type: str = "jsonl",
    ) -> Timeline:
        """Upload a timeline file to a sketch.

        Note: For large files, consider using Timesketch importer CLI.
        """
        client = await self._get_client()

        with open(file_path, "rb") as f:
            files = {"file": (name, f, "application/octet-stream")}
            data = {
                "name": name,
                "sketch_id": sketch_id,
            }

            response = await client.post(
                f"/api/v1/sketches/{sketch_id}/timelines/",
                files=files,
                data=data,
            )
            response.raise_for_status()
            result = response.json()

        objects = result.get("objects", [])
        ts_timeline = TimesketchTimeline(**objects[0])
        return self._ts_timeline_to_timeline(ts_timeline, sketch_id)

    async def delete_timeline(
        self,
        sketch_id: str,
        timeline_id: str,
    ) -> bool:
        """Delete a timeline from a sketch."""
        try:
            await self._request(
                "DELETE",
                f"/api/v1/sketches/{sketch_id}/timelines/{timeline_id}/",
            )
            return True
        except Exception as e:
            logger.error("Failed to delete timeline %s: %s", timeline_id, e)
            return False

    # =========================================================================
    # Event Search
    # =========================================================================

    async def search_events(
        self,
        sketch_id: str,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
        timeline_ids: list[str] | None = None,
    ) -> list[TimelineEvent]:
        """Search events in a sketch."""
        # Build search query
        payload: dict[str, Any] = {
            "query_string": query,
            "query_filter": {
                "size": limit,
                "terminate_after": limit * 2,
            },
        }

        # Add time filters
        if start_time or end_time:
            time_filter = {}
            if start_time:
                time_filter["start_time"] = start_time.isoformat()
            if end_time:
                time_filter["end_time"] = end_time.isoformat()
            payload["query_filter"]["time_start"] = start_time.isoformat() if start_time else None
            payload["query_filter"]["time_end"] = end_time.isoformat() if end_time else None

        # Add timeline filter
        if timeline_ids:
            payload["query_filter"]["indices"] = [f"timesketch_{tid}" for tid in timeline_ids]

        result = await self._request(
            "POST",
            f"/api/v1/sketches/{sketch_id}/explore/",
            json=payload,
        )

        objects = result.get("objects", [])
        events = []

        for obj in objects:
            # Timesketch returns events in _source format
            ts_event = TSEvent(**obj)
            events.append(self._ts_event_to_event(ts_event))

        return events

    async def get_event(
        self,
        sketch_id: str,
        event_id: str,
    ) -> TimelineEvent | None:
        """Get a specific event."""
        # Search for specific event by ID
        events = await self.search_events(
            sketch_id=sketch_id,
            query=f'_id:"{event_id}"',
            limit=1,
        )
        return events[0] if events else None

    # =========================================================================
    # Annotations
    # =========================================================================

    async def tag_event(
        self,
        sketch_id: str,
        event_id: str,
        tags: list[str],
    ) -> TimelineEvent:
        """Add tags to an event."""
        payload = {
            "tag": tags,
            "events": {"_id": event_id},
        }

        await self._request(
            "POST",
            f"/api/v1/sketches/{sketch_id}/event/annotate/",
            json=payload,
        )

        # Fetch updated event
        event = await self.get_event(sketch_id, event_id)
        if event:
            return event

        # Return placeholder if not found
        return TimelineEvent(
            event_id=event_id,
            timestamp=datetime.utcnow(),
            message="",
            tags=tags,
        )

    async def star_event(
        self,
        sketch_id: str,
        event_id: str,
        starred: bool = True,
    ) -> TimelineEvent:
        """Star/unstar an event."""
        tag = "__ts_star" if starred else "-__ts_star"
        return await self.tag_event(sketch_id, event_id, [tag])

    async def add_comment(
        self,
        sketch_id: str,
        event_id: str,
        comment: str,
    ) -> TimelineEvent:
        """Add a comment to an event."""
        payload = {
            "annotation": comment,
            "annotation_type": "comment",
            "events": {"_id": event_id},
        }

        await self._request(
            "POST",
            f"/api/v1/sketches/{sketch_id}/event/annotate/",
            json=payload,
        )

        event = await self.get_event(sketch_id, event_id)
        if event:
            return event

        return TimelineEvent(
            event_id=event_id,
            timestamp=datetime.utcnow(),
            message="",
            comments=[comment],
        )

    # =========================================================================
    # Saved Views
    # =========================================================================

    async def list_saved_views(self, sketch_id: str) -> list[SavedView]:
        """List saved views in a sketch."""
        result = await self._request("GET", f"/api/v1/sketches/{sketch_id}/views/")
        objects = result.get("objects", [])

        views = []
        for obj in objects:
            ts_view = TimesketchSavedView(**obj)
            views.append(
                SavedView(
                    view_id=str(ts_view.id),
                    sketch_id=sketch_id,
                    name=ts_view.name,
                    query=ts_view.query,
                    created_at=ts_view.created_at,
                    owner=ts_view.owner,
                )
            )

        return views

    async def create_saved_view(
        self,
        sketch_id: str,
        name: str,
        query: str,
    ) -> SavedView:
        """Create a saved view."""
        payload = {
            "name": name,
            "query_string": query,
        }

        result = await self._request(
            "POST",
            f"/api/v1/sketches/{sketch_id}/views/",
            json=payload,
        )

        objects = result.get("objects", [])
        ts_view = TimesketchSavedView(**objects[0])

        return SavedView(
            view_id=str(ts_view.id),
            sketch_id=sketch_id,
            name=ts_view.name,
            query=ts_view.query,
            created_at=ts_view.created_at,
        )

    async def delete_saved_view(
        self,
        sketch_id: str,
        view_id: str,
    ) -> bool:
        """Delete a saved view."""
        try:
            await self._request(
                "DELETE",
                f"/api/v1/sketches/{sketch_id}/views/{view_id}/",
            )
            return True
        except Exception as e:
            logger.error("Failed to delete view %s: %s", view_id, e)
            return False

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
