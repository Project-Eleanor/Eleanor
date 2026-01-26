"""Integration tests for Timesketch adapter.

These tests require a running Timesketch instance.
Run with: pytest tests/integration/test_timesketch.py --live
"""

import os
import pytest
import tempfile

from app.adapters.timesketch.adapter import TimesketchAdapter


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def timesketch_config():
    """Get Timesketch configuration from environment."""
    return {
        "url": os.getenv("TIMESKETCH_URL", "http://localhost:5000"),
        "api_key": os.getenv("TIMESKETCH_API_KEY", ""),
        "username": os.getenv("TIMESKETCH_USERNAME", ""),
        "password": os.getenv("TIMESKETCH_PASSWORD", ""),
        "verify_ssl": os.getenv("TIMESKETCH_VERIFY_SSL", "true").lower() == "true",
    }


@pytest.fixture
async def timesketch_adapter(timesketch_config):
    """Create and connect Timesketch adapter."""
    adapter = TimesketchAdapter(timesketch_config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


class TestTimesketchConnection:
    """Tests for Timesketch connectivity."""

    async def test_health_check(self, timesketch_adapter):
        """Test health check returns valid status."""
        health = await timesketch_adapter.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_connection_established(self, timesketch_adapter):
        """Test that adapter is connected."""
        assert timesketch_adapter.connected is True


class TestTimesketchSketches:
    """Tests for sketch management."""

    async def test_list_sketches(self, timesketch_adapter):
        """Test listing sketches."""
        result = await timesketch_adapter.list_sketches(limit=10)

        assert "sketches" in result
        assert "total" in result
        assert isinstance(result["sketches"], list)

    async def test_create_sketch(self, timesketch_adapter):
        """Test creating a sketch."""
        sketch = await timesketch_adapter.create_sketch(
            name="Integration Test Sketch",
            description="Created by Eleanor integration tests",
        )

        assert sketch is not None
        assert "id" in sketch
        assert sketch["name"] == "Integration Test Sketch"

        # Clean up
        await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_get_sketch(self, timesketch_adapter):
        """Test getting sketch details."""
        # Create a sketch first
        sketch = await timesketch_adapter.create_sketch(
            name="Test Sketch",
            description="For testing",
        )

        # Get it
        retrieved = await timesketch_adapter.get_sketch(sketch["id"])

        assert retrieved is not None
        assert retrieved["id"] == sketch["id"]
        assert retrieved["name"] == "Test Sketch"

        # Clean up
        await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_delete_sketch(self, timesketch_adapter):
        """Test deleting a sketch."""
        # Create a sketch
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch to Delete",
        )

        # Delete it
        result = await timesketch_adapter.delete_sketch(sketch["id"])

        assert result is True

        # Verify deleted
        retrieved = await timesketch_adapter.get_sketch(sketch["id"])
        assert retrieved is None


class TestTimesketchTimelines:
    """Tests for timeline management."""

    async def test_list_timelines(self, timesketch_adapter):
        """Test listing timelines in a sketch."""
        # Create a sketch first
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch with Timeline",
        )

        timelines = await timesketch_adapter.list_timelines(sketch["id"])

        assert isinstance(timelines, list)

        # Clean up
        await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_upload_timeline(self, timesketch_adapter):
        """Test uploading a timeline."""
        # Create a sketch
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Upload",
        )

        # Create a minimal JSONL file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Test event 1", "timestamp_desc": "Test"}\n')
            f.write('{"datetime": "2024-01-20T10:01:00Z", "message": "Test event 2", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            timeline = await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            assert timeline is not None
            assert "id" in timeline
            assert timeline["status"] in ["processing", "ready", "pending"]

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_delete_timeline(self, timesketch_adapter):
        """Test deleting a timeline."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Timeline Delete",
        )

        # Create a minimal timeline file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Test", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            timeline = await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Timeline to Delete",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Delete timeline
            result = await timesketch_adapter.delete_timeline(
                sketch_id=sketch["id"],
                timeline_id=timeline["id"],
            )

            assert result is True

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])


class TestTimesketchSearch:
    """Tests for event search."""

    async def test_search_events(self, timesketch_adapter):
        """Test searching events in a sketch."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Search",
        )

        # Create test timeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Login event user admin", "timestamp_desc": "Login"}\n')
            f.write('{"datetime": "2024-01-20T10:01:00Z", "message": "File access document.pdf", "timestamp_desc": "FileAccess"}\n')
            temp_path = f.name

        try:
            await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Search Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Wait a bit for indexing
            import asyncio
            await asyncio.sleep(2)

            # Search
            results = await timesketch_adapter.search_events(
                sketch_id=sketch["id"],
                query="admin",
                limit=100,
            )

            assert "events" in results
            assert isinstance(results["events"], list)

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_get_event(self, timesketch_adapter):
        """Test getting a specific event."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Event Get",
        )

        # Create test timeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Test event", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Event Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Wait for indexing
            import asyncio
            await asyncio.sleep(2)

            # Search for event
            results = await timesketch_adapter.search_events(
                sketch_id=sketch["id"],
                query="*",
                limit=1,
            )

            if results["events"]:
                event_id = results["events"][0]["id"]
                event = await timesketch_adapter.get_event(
                    sketch_id=sketch["id"],
                    event_id=event_id,
                )

                assert event is not None
                assert event["id"] == event_id

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])


class TestTimesketchAnnotations:
    """Tests for event annotations."""

    async def test_tag_event(self, timesketch_adapter):
        """Test tagging an event."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Tagging",
        )

        # Create test timeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Event to tag", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Tag Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Wait for indexing
            import asyncio
            await asyncio.sleep(2)

            # Get an event
            results = await timesketch_adapter.search_events(
                sketch_id=sketch["id"],
                query="*",
                limit=1,
            )

            if results["events"]:
                event_id = results["events"][0]["id"]

                # Tag it
                result = await timesketch_adapter.tag_event(
                    sketch_id=sketch["id"],
                    event_id=event_id,
                    tags=["suspicious", "investigate"],
                )

                assert result is not None
                assert "suspicious" in result.get("tags", [])

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_star_event(self, timesketch_adapter):
        """Test starring an event."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Starring",
        )

        # Create test timeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Event to star", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Star Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Wait for indexing
            import asyncio
            await asyncio.sleep(2)

            # Get an event
            results = await timesketch_adapter.search_events(
                sketch_id=sketch["id"],
                query="*",
                limit=1,
            )

            if results["events"]:
                event_id = results["events"][0]["id"]

                # Star it
                result = await timesketch_adapter.star_event(
                    sketch_id=sketch["id"],
                    event_id=event_id,
                    starred=True,
                )

                assert result is not None
                assert result.get("starred") is True

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_add_comment(self, timesketch_adapter):
        """Test adding a comment to an event."""
        # Create sketch with timeline
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Comments",
        )

        # Create test timeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"datetime": "2024-01-20T10:00:00Z", "message": "Event for comment", "timestamp_desc": "Test"}\n')
            temp_path = f.name

        try:
            await timesketch_adapter.upload_timeline(
                sketch_id=sketch["id"],
                name="Comment Test Timeline",
                file_path=temp_path,
                source_type="jsonl",
            )

            # Wait for indexing
            import asyncio
            await asyncio.sleep(2)

            # Get an event
            results = await timesketch_adapter.search_events(
                sketch_id=sketch["id"],
                query="*",
                limit=1,
            )

            if results["events"]:
                event_id = results["events"][0]["id"]

                # Add comment
                result = await timesketch_adapter.add_comment(
                    sketch_id=sketch["id"],
                    event_id=event_id,
                    comment="This is a test comment from integration tests",
                )

                assert result is not None
                assert "comment" in result

        finally:
            os.unlink(temp_path)
            await timesketch_adapter.delete_sketch(sketch["id"])


class TestTimesketchSavedViews:
    """Tests for saved view management."""

    async def test_create_saved_view(self, timesketch_adapter):
        """Test creating a saved view."""
        # Create sketch
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for Saved Views",
        )

        try:
            view = await timesketch_adapter.create_saved_view(
                sketch_id=sketch["id"],
                name="Suspicious Activity",
                query="*powershell* OR *cmd*",
                description="Find command line activity",
            )

            assert view is not None
            assert view["name"] == "Suspicious Activity"

        finally:
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_list_saved_views(self, timesketch_adapter):
        """Test listing saved views."""
        # Create sketch with saved view
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for View List",
        )

        try:
            await timesketch_adapter.create_saved_view(
                sketch_id=sketch["id"],
                name="Test View",
                query="*",
            )

            views = await timesketch_adapter.list_saved_views(sketch["id"])

            assert isinstance(views, list)
            assert len(views) >= 1

        finally:
            await timesketch_adapter.delete_sketch(sketch["id"])

    async def test_delete_saved_view(self, timesketch_adapter):
        """Test deleting a saved view."""
        # Create sketch with saved view
        sketch = await timesketch_adapter.create_sketch(
            name="Sketch for View Delete",
        )

        try:
            view = await timesketch_adapter.create_saved_view(
                sketch_id=sketch["id"],
                name="View to Delete",
                query="*",
            )

            # Delete it
            result = await timesketch_adapter.delete_saved_view(
                sketch_id=sketch["id"],
                view_id=view["id"],
            )

            assert result is True

        finally:
            await timesketch_adapter.delete_sketch(sketch["id"])
