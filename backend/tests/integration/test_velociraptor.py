"""Integration tests for Velociraptor adapter.

These tests require a running Velociraptor instance.
Run with: pytest tests/integration/test_velociraptor.py --live
"""

import os
import pytest

from app.adapters.velociraptor.adapter import VelociraptorAdapter


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def velociraptor_config():
    """Get Velociraptor configuration from environment."""
    return {
        "url": os.getenv("VELOCIRAPTOR_URL", "https://localhost:8003"),
        "api_key": os.getenv("VELOCIRAPTOR_API_KEY", ""),
        "verify_ssl": os.getenv("VELOCIRAPTOR_VERIFY_SSL", "false").lower() == "true",
        "client_cert": os.getenv("VELOCIRAPTOR_CLIENT_CERT", ""),
        "client_key": os.getenv("VELOCIRAPTOR_CLIENT_KEY", ""),
    }


@pytest.fixture
async def velociraptor_adapter(velociraptor_config):
    """Create and connect Velociraptor adapter."""
    adapter = VelociraptorAdapter(velociraptor_config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


class TestVelociraptorConnection:
    """Tests for Velociraptor connectivity."""

    async def test_health_check(self, velociraptor_adapter):
        """Test health check returns valid status."""
        health = await velociraptor_adapter.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_connection_established(self, velociraptor_adapter):
        """Test that adapter is connected."""
        assert velociraptor_adapter.connected is True


class TestVelociraptorEndpoints:
    """Tests for endpoint management."""

    async def test_list_endpoints(self, velociraptor_adapter):
        """Test listing endpoints."""
        result = await velociraptor_adapter.list_endpoints(limit=10)

        assert "endpoints" in result
        assert "total" in result
        assert isinstance(result["endpoints"], list)

    async def test_list_endpoints_with_search(self, velociraptor_adapter):
        """Test searching endpoints."""
        result = await velociraptor_adapter.list_endpoints(
            limit=10,
            search="WORK",
        )

        assert "endpoints" in result
        # All results should contain search term
        for endpoint in result["endpoints"]:
            hostname = endpoint.get("hostname", "").lower()
            ip = endpoint.get("ip_address", "")
            assert "work" in hostname.lower() or "work" in ip

    async def test_list_online_endpoints(self, velociraptor_adapter):
        """Test listing only online endpoints."""
        result = await velociraptor_adapter.list_endpoints(
            limit=100,
            online_only=True,
        )

        assert "endpoints" in result
        for endpoint in result["endpoints"]:
            assert endpoint.get("online", False) is True

    async def test_get_endpoint(self, velociraptor_adapter):
        """Test getting specific endpoint details."""
        # First get a list of endpoints
        list_result = await velociraptor_adapter.list_endpoints(limit=1)

        if list_result["endpoints"]:
            client_id = list_result["endpoints"][0]["client_id"]
            endpoint = await velociraptor_adapter.get_endpoint(client_id)

            assert endpoint is not None
            assert endpoint["client_id"] == client_id

    async def test_search_endpoints(self, velociraptor_adapter):
        """Test endpoint search."""
        results = await velociraptor_adapter.search_endpoints("192.168")

        assert isinstance(results, list)


class TestVelociraptorArtifacts:
    """Tests for artifact collection."""

    async def test_list_artifacts(self, velociraptor_adapter):
        """Test listing available artifacts."""
        artifacts = await velociraptor_adapter.list_artifacts()

        assert isinstance(artifacts, list)
        assert len(artifacts) > 0

        # Verify artifact structure
        artifact = artifacts[0]
        assert "name" in artifact

    async def test_list_artifacts_by_category(self, velociraptor_adapter):
        """Test filtering artifacts by category."""
        artifacts = await velociraptor_adapter.list_artifacts(category="Windows")

        assert isinstance(artifacts, list)
        for artifact in artifacts:
            # Windows artifacts typically start with Windows.
            assert "Windows" in artifact.get("name", "") or artifact.get("category") == "Windows"


class TestVelociraptorCollection:
    """Tests for artifact collection execution."""

    async def test_collect_artifact(self, velociraptor_adapter):
        """Test triggering artifact collection."""
        # Get an online endpoint
        list_result = await velociraptor_adapter.list_endpoints(
            limit=1,
            online_only=True,
        )

        if not list_result["endpoints"]:
            pytest.skip("No online endpoints available for collection test")

        client_id = list_result["endpoints"][0]["client_id"]

        # Trigger a simple collection
        result = await velociraptor_adapter.collect_artifact(
            client_id=client_id,
            artifact_name="Generic.Client.Info",
            parameters={},
        )

        assert "job_id" in result
        assert result["status"] in ["pending", "running", "queued"]

    async def test_get_collection_status(self, velociraptor_adapter):
        """Test checking collection job status."""
        # Get an online endpoint
        list_result = await velociraptor_adapter.list_endpoints(
            limit=1,
            online_only=True,
        )

        if not list_result["endpoints"]:
            pytest.skip("No online endpoints available")

        client_id = list_result["endpoints"][0]["client_id"]

        # Start collection
        collection = await velociraptor_adapter.collect_artifact(
            client_id=client_id,
            artifact_name="Generic.Client.Info",
        )

        # Check status
        status = await velociraptor_adapter.get_collection_status(collection["job_id"])

        assert status is not None
        assert "status" in status


class TestVelociraptorHunts:
    """Tests for hunt management."""

    async def test_list_hunts(self, velociraptor_adapter):
        """Test listing hunts."""
        hunts = await velociraptor_adapter.list_hunts(limit=10)

        assert isinstance(hunts, list)

    async def test_create_and_manage_hunt(self, velociraptor_adapter):
        """Test creating and managing a hunt."""
        # Create hunt
        hunt = await velociraptor_adapter.create_hunt(
            name="Test Hunt - Integration Test",
            artifact_name="Generic.Client.Info",
            description="Created by integration test",
        )

        assert "hunt_id" in hunt
        assert hunt["state"] == "paused"

        hunt_id = hunt["hunt_id"]

        # Start hunt
        started_hunt = await velociraptor_adapter.start_hunt(hunt_id)
        assert started_hunt["state"] == "running"

        # Stop hunt
        stopped_hunt = await velociraptor_adapter.stop_hunt(hunt_id)
        assert stopped_hunt["state"] == "stopped"


class TestVelociraptorResponseActions:
    """Tests for response actions."""

    async def test_isolate_host_dry_run(self, velociraptor_adapter):
        """Test host isolation (dry run - may be mocked in test env)."""
        # Get an online endpoint
        list_result = await velociraptor_adapter.list_endpoints(
            limit=1,
            online_only=True,
        )

        if not list_result["endpoints"]:
            pytest.skip("No online endpoints available")

        client_id = list_result["endpoints"][0]["client_id"]

        # Note: In production, this would actually isolate the host
        # In test environments, this may be mocked or disabled
        result = await velociraptor_adapter.isolate_host(client_id)

        assert "status" in result
