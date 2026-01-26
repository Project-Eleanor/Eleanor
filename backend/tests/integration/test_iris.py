"""Integration tests for IRIS adapter.

These tests require a running IRIS instance.
Run with: pytest tests/integration/test_iris.py --live
"""

import os
import pytest

from app.adapters.iris.adapter import IRISAdapter


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def iris_config():
    """Get IRIS configuration from environment."""
    return {
        "url": os.getenv("IRIS_URL", "https://localhost:8443"),
        "api_key": os.getenv("IRIS_API_KEY", ""),
        "verify_ssl": os.getenv("IRIS_VERIFY_SSL", "false").lower() == "true",
    }


@pytest.fixture
async def iris_adapter(iris_config):
    """Create and connect IRIS adapter."""
    adapter = IRISAdapter(iris_config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


class TestIRISConnection:
    """Tests for IRIS connectivity."""

    async def test_health_check(self, iris_adapter):
        """Test health check returns valid status."""
        health = await iris_adapter.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_connection_established(self, iris_adapter):
        """Test that adapter is connected."""
        assert iris_adapter.connected is True


class TestIRISCaseManagement:
    """Tests for IRIS case management."""

    async def test_list_cases(self, iris_adapter):
        """Test listing cases."""
        result = await iris_adapter.list_cases(limit=10)

        assert "cases" in result
        assert "total" in result
        assert isinstance(result["cases"], list)

    async def test_create_case(self, iris_adapter):
        """Test creating a case."""
        case = await iris_adapter.create_case(
            title="Integration Test Case",
            description="Created by Eleanor integration tests",
            severity="medium",
            tags=["test", "integration"],
        )

        assert case is not None
        assert "id" in case
        assert case["title"] == "Integration Test Case"
        assert case["status"] == "open"

        # Clean up - close the case
        await iris_adapter.close_case(case["id"], "Test completed")

    async def test_update_case(self, iris_adapter):
        """Test updating a case."""
        # Create a case first
        case = await iris_adapter.create_case(
            title="Case to Update",
            severity="low",
        )

        # Update it
        updated = await iris_adapter.update_case(
            external_id=case["id"],
            title="Updated Case Title",
            severity="high",
        )

        assert updated["title"] == "Updated Case Title"
        assert updated["severity"] == "high"

        # Clean up
        await iris_adapter.close_case(case["id"])

    async def test_close_case(self, iris_adapter):
        """Test closing a case."""
        # Create a case
        case = await iris_adapter.create_case(
            title="Case to Close",
            severity="low",
        )

        # Close it
        closed = await iris_adapter.close_case(
            external_id=case["id"],
            resolution="Closed by integration test",
        )

        assert closed["status"] == "closed"

    async def test_get_case(self, iris_adapter):
        """Test getting case details."""
        # Create a case
        case = await iris_adapter.create_case(
            title="Case to Retrieve",
            severity="medium",
        )

        # Get it
        retrieved = await iris_adapter.get_case(case["id"])

        assert retrieved is not None
        assert retrieved["id"] == case["id"]
        assert retrieved["title"] == "Case to Retrieve"

        # Clean up
        await iris_adapter.close_case(case["id"])


class TestIRISAssets:
    """Tests for IRIS asset management."""

    async def test_add_asset(self, iris_adapter):
        """Test adding asset to a case."""
        # Create a case
        case = await iris_adapter.create_case(
            title="Case with Assets",
            severity="medium",
        )

        # Add asset
        asset = await iris_adapter.add_asset(
            case_id=case["id"],
            asset={
                "name": "WORKSTATION-TEST",
                "asset_type": "computer",
                "ip_address": "192.168.1.200",
                "description": "Test workstation",
            },
        )

        assert asset is not None
        assert asset["name"] == "WORKSTATION-TEST"

        # Clean up
        await iris_adapter.close_case(case["id"])

    async def test_list_assets(self, iris_adapter):
        """Test listing assets for a case."""
        # Create a case with an asset
        case = await iris_adapter.create_case(
            title="Case with Assets",
            severity="medium",
        )

        await iris_adapter.add_asset(
            case_id=case["id"],
            asset={
                "name": "TEST-ASSET",
                "asset_type": "computer",
            },
        )

        # List assets
        assets = await iris_adapter.list_assets(case["id"])

        assert isinstance(assets, list)
        assert len(assets) >= 1

        # Clean up
        await iris_adapter.close_case(case["id"])


class TestIRISIOCs:
    """Tests for IRIS IOC management."""

    async def test_add_ioc(self, iris_adapter):
        """Test adding IOC to a case."""
        # Create a case
        case = await iris_adapter.create_case(
            title="Case with IOCs",
            severity="high",
        )

        # Add IOC
        ioc = await iris_adapter.add_ioc(
            case_id=case["id"],
            ioc={
                "value": "malicious.example.com",
                "ioc_type": "domain",
                "tlp": "amber",
                "description": "Test IOC",
                "tags": ["malware", "c2"],
            },
        )

        assert ioc is not None
        assert ioc["value"] == "malicious.example.com"

        # Clean up
        await iris_adapter.close_case(case["id"])

    async def test_list_iocs(self, iris_adapter):
        """Test listing IOCs for a case."""
        # Create a case with IOC
        case = await iris_adapter.create_case(
            title="Case with IOCs",
            severity="high",
        )

        await iris_adapter.add_ioc(
            case_id=case["id"],
            ioc={
                "value": "198.51.100.50",
                "ioc_type": "ip",
            },
        )

        # List IOCs
        iocs = await iris_adapter.list_iocs(case["id"])

        assert isinstance(iocs, list)
        assert len(iocs) >= 1

        # Clean up
        await iris_adapter.close_case(case["id"])


class TestIRISNotes:
    """Tests for IRIS note management."""

    async def test_add_note(self, iris_adapter):
        """Test adding note to a case."""
        # Create a case
        case = await iris_adapter.create_case(
            title="Case with Notes",
            severity="medium",
        )

        # Add note
        note = await iris_adapter.add_note(
            case_id=case["id"],
            note={
                "title": "Investigation Update",
                "content": "Initial analysis completed. Malware identified.",
            },
        )

        assert note is not None
        assert note["title"] == "Investigation Update"

        # Clean up
        await iris_adapter.close_case(case["id"])

    async def test_list_notes(self, iris_adapter):
        """Test listing notes for a case."""
        # Create a case with note
        case = await iris_adapter.create_case(
            title="Case with Notes",
            severity="medium",
        )

        await iris_adapter.add_note(
            case_id=case["id"],
            note={
                "title": "Test Note",
                "content": "This is a test note.",
            },
        )

        # List notes
        notes = await iris_adapter.list_notes(case["id"])

        assert isinstance(notes, list)
        assert len(notes) >= 1

        # Clean up
        await iris_adapter.close_case(case["id"])


class TestIRISSync:
    """Tests for Eleanor-IRIS synchronization."""

    async def test_sync_case(self, iris_adapter):
        """Test syncing case between Eleanor and IRIS."""
        # Create an IRIS case
        iris_case = await iris_adapter.create_case(
            title="Sync Test Case",
            severity="medium",
        )

        # Simulate sync
        sync_result = await iris_adapter.sync_case(
            eleanor_id="eleanor-test-123",
            external_id=iris_case["id"],
        )

        assert sync_result["sync_status"] == "synced"
        assert sync_result["eleanor_id"] == "eleanor-test-123"

        # Clean up
        await iris_adapter.close_case(iris_case["id"])
