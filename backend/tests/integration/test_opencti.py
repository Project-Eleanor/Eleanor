"""Integration tests for OpenCTI adapter.

These tests require a running OpenCTI instance.
Run with: pytest tests/integration/test_opencti.py --live
"""

import os
import pytest

from app.adapters.opencti.adapter import OpenCTIAdapter


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def opencti_config():
    """Get OpenCTI configuration from environment."""
    return {
        "url": os.getenv("OPENCTI_URL", "http://localhost:8080"),
        "api_key": os.getenv("OPENCTI_API_KEY", ""),
        "verify_ssl": os.getenv("OPENCTI_VERIFY_SSL", "true").lower() == "true",
    }


@pytest.fixture
async def opencti_adapter(opencti_config):
    """Create and connect OpenCTI adapter."""
    adapter = OpenCTIAdapter(opencti_config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


class TestOpenCTIConnection:
    """Tests for OpenCTI connectivity."""

    async def test_health_check(self, opencti_adapter):
        """Test health check returns valid status."""
        health = await opencti_adapter.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_connection_established(self, opencti_adapter):
        """Test that adapter is connected."""
        assert opencti_adapter.connected is True


class TestOpenCTIEnrichment:
    """Tests for indicator enrichment."""

    async def test_enrich_known_domain(self, opencti_adapter):
        """Test enriching a known malicious domain."""
        result = await opencti_adapter.enrich_indicator(
            value="malware.testphish.com",  # Use a known test indicator
            indicator_type="domain",
        )

        assert result is not None
        assert "value" in result
        assert result["value"] == "malware.testphish.com"

    async def test_enrich_unknown_indicator(self, opencti_adapter):
        """Test enriching an unknown indicator."""
        result = await opencti_adapter.enrich_indicator(
            value="definitely-not-malicious-" + os.urandom(8).hex() + ".example.com",
            indicator_type="domain",
        )

        # Should return result with low/no confidence
        assert result is not None
        assert result.get("found", True) is False or result.get("confidence", 100) == 0

    async def test_enrich_ip_address(self, opencti_adapter):
        """Test enriching an IP address."""
        result = await opencti_adapter.enrich_indicator(
            value="198.51.100.50",
            indicator_type="ipv4",
        )

        assert result is not None
        assert "value" in result

    async def test_enrich_file_hash(self, opencti_adapter):
        """Test enriching a file hash."""
        # Use empty file SHA256 as test
        result = await opencti_adapter.enrich_indicator(
            value="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            indicator_type="sha256",
        )

        assert result is not None
        assert "value" in result

    async def test_bulk_enrich(self, opencti_adapter):
        """Test bulk enrichment of indicators."""
        indicators = [
            {"value": "test1.example.com", "type": "domain"},
            {"value": "192.168.1.1", "type": "ipv4"},
            {"value": "d41d8cd98f00b204e9800998ecf8427e", "type": "md5"},
        ]

        results = await opencti_adapter.bulk_enrich(indicators)

        assert isinstance(results, list)
        assert len(results) == len(indicators)


class TestOpenCTIThreatActors:
    """Tests for threat actor queries."""

    async def test_search_threat_actors(self, opencti_adapter):
        """Test searching threat actors."""
        results = await opencti_adapter.search_threat_actors(
            query="APT",
            limit=5,
        )

        assert isinstance(results, list)
        # May or may not have results depending on database content

    async def test_get_threat_actor(self, opencti_adapter):
        """Test getting specific threat actor."""
        # First search for actors
        actors = await opencti_adapter.search_threat_actors(query="APT", limit=1)

        if actors:
            actor_name = actors[0]["name"]
            actor = await opencti_adapter.get_threat_actor(actor_name)

            if actor:
                assert actor["name"] == actor_name
                assert "description" in actor


class TestOpenCTICampaigns:
    """Tests for campaign queries."""

    async def test_search_campaigns(self, opencti_adapter):
        """Test searching campaigns."""
        results = await opencti_adapter.search_campaigns(
            query="Operation",
            limit=5,
        )

        assert isinstance(results, list)

    async def test_get_campaign(self, opencti_adapter):
        """Test getting specific campaign."""
        # First search for campaigns
        campaigns = await opencti_adapter.search_campaigns(query="", limit=1)

        if campaigns:
            campaign_name = campaigns[0]["name"]
            campaign = await opencti_adapter.get_campaign(campaign_name)

            if campaign:
                assert campaign["name"] == campaign_name


class TestOpenCTIRelatedIndicators:
    """Tests for related indicator queries."""

    async def test_get_related_indicators(self, opencti_adapter):
        """Test getting related indicators."""
        # First enrich an indicator
        enrichment = await opencti_adapter.enrich_indicator(
            value="malware.example.com",
            indicator_type="domain",
        )

        if enrichment and enrichment.get("found"):
            related = await opencti_adapter.get_related_indicators(
                value="malware.example.com",
                indicator_type="domain",
                limit=10,
            )

            assert isinstance(related, list)


class TestOpenCTIIndicatorSubmission:
    """Tests for submitting new indicators."""

    async def test_submit_indicator(self, opencti_adapter):
        """Test submitting a new indicator."""
        # Generate unique indicator for test
        unique_domain = f"test-{os.urandom(4).hex()}.example.org"

        result = await opencti_adapter.submit_indicator(
            value=unique_domain,
            indicator_type="domain",
            description="Test indicator from Eleanor integration tests",
            labels=["test"],
            confidence=50,
            tlp="white",
        )

        assert result is not None
        assert result["value"] == unique_domain
        assert "id" in result
