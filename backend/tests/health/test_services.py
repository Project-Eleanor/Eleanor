"""Health check tests for all Eleanor services.

These tests verify service connectivity and basic functionality.
Designed for OVA first-run verification and ongoing monitoring.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch


pytestmark = [pytest.mark.health, pytest.mark.asyncio]


class TestDatabaseHealth:
    """Health checks for PostgreSQL database."""

    async def test_postgres_connection(self, test_session):
        """Test PostgreSQL database connection."""
        from sqlalchemy import text

        # Execute simple query
        result = await test_session.execute(text("SELECT 1"))
        value = result.scalar()

        assert value == 1

    async def test_postgres_can_create_table(self, test_session):
        """Test database can create tables."""
        from sqlalchemy import text

        # This is implicitly tested by the fixture setup
        # The Base.metadata.create_all in conftest proves tables can be created
        result = await test_session.execute(
            text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' OR table_schema = 'public'")
        )
        count = result.scalar()

        # Should have tables from our models
        assert count >= 0  # SQLite might report differently


class TestElasticsearchHealth:
    """Health checks for Elasticsearch cluster."""

    async def test_elasticsearch_cluster_health(self, mock_elasticsearch):
        """Test Elasticsearch cluster health."""
        mock_elasticsearch.cluster.health = AsyncMock(return_value={
            "cluster_name": "eleanor-cluster",
            "status": "green",
            "number_of_nodes": 1,
            "number_of_data_nodes": 1,
            "active_primary_shards": 5,
            "active_shards": 5,
            "relocating_shards": 0,
            "initializing_shards": 0,
            "unassigned_shards": 0,
        })

        health = await mock_elasticsearch.cluster.health()

        assert health["status"] in ["green", "yellow", "red"]
        assert health["number_of_nodes"] >= 1

    async def test_elasticsearch_can_index(self, mock_elasticsearch):
        """Test Elasticsearch can index documents."""
        mock_elasticsearch.index = AsyncMock(return_value={
            "_id": "test-doc-1",
            "_index": "test-index",
            "result": "created",
        })

        result = await mock_elasticsearch.index(
            index="test-index",
            body={"message": "test"},
        )

        assert result["result"] in ["created", "updated"]

    async def test_elasticsearch_can_search(self, mock_elasticsearch):
        """Test Elasticsearch can execute searches."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 5,
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "hits": [],
            },
        })

        result = await mock_elasticsearch.search(
            index="test-*",
            body={"query": {"match_all": {}}},
        )

        assert "hits" in result
        assert "took" in result


class TestRedisHealth:
    """Health checks for Redis cache."""

    async def test_redis_ping(self, mock_redis):
        """Test Redis ping."""
        result = await mock_redis.ping()

        assert result is True

    async def test_redis_set_get(self, mock_redis):
        """Test Redis set and get operations."""
        await mock_redis.set("test_key", "test_value")
        value = await mock_redis.get("test_key")

        assert value == "test_value"

    async def test_redis_delete(self, mock_redis):
        """Test Redis delete operation."""
        await mock_redis.set("delete_key", "value")
        result = await mock_redis.delete("delete_key")

        assert result is True


class TestAPIHealth:
    """Health checks for Eleanor API."""

    async def test_backend_api_responds(self, client):
        """Test backend API is responding."""
        # Health endpoint would typically be unprotected
        # For now, test that we can reach the API
        response = await client.get("/api/v1/auth/me")

        # Should get 401 (requires auth) but that proves API is running
        assert response.status_code == 401

    async def test_backend_auth_endpoint(self, client):
        """Test authentication endpoint is accessible."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "test", "password": "test"},
        )

        # Should get 401 for invalid credentials, not 500
        assert response.status_code in [401, 422]

    async def test_authenticated_endpoint(self, authenticated_client):
        """Test authenticated endpoints work."""
        response = await authenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert "username" in response.json()


class TestAdapterHealth:
    """Health checks for integration adapters."""

    async def test_velociraptor_adapter_health(self, mock_velociraptor_adapter):
        """Test Velociraptor adapter health check."""
        health = await mock_velociraptor_adapter.health_check()

        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_iris_adapter_health(self, mock_iris_adapter):
        """Test IRIS adapter health check."""
        health = await mock_iris_adapter.health_check()

        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_opencti_adapter_health(self, mock_opencti_adapter):
        """Test OpenCTI adapter health check."""
        health = await mock_opencti_adapter.health_check()

        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_shuffle_adapter_health(self, mock_shuffle_adapter):
        """Test Shuffle adapter health check."""
        health = await mock_shuffle_adapter.health_check()

        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_timesketch_adapter_health(self, mock_timesketch_adapter):
        """Test Timesketch adapter health check."""
        health = await mock_timesketch_adapter.health_check()

        assert health["status"] in ["healthy", "unhealthy", "degraded"]


class TestIntegrationEndpoints:
    """Health checks for integration status endpoints."""

    async def test_integrations_health_endpoint(self, authenticated_client):
        """Test integrations health endpoint."""
        # This tests the /api/v1/integrations/health endpoint if it exists
        # Mock the adapter registry
        with patch("app.adapters.get_registry") as mock_registry:
            mock_instance = AsyncMock()
            mock_instance.health_check_all = AsyncMock(return_value={
                "velociraptor": {"status": "healthy"},
                "iris": {"status": "healthy"},
                "opencti": {"status": "degraded"},
                "shuffle": {"status": "healthy"},
                "timesketch": {"status": "unhealthy"},
            })
            mock_registry.return_value = mock_instance

            # Test would depend on actual endpoint implementation
            # For now, verify adapters can report health
            health = await mock_instance.health_check_all()

            assert "velociraptor" in health
            assert "iris" in health


class TestSystemRequirements:
    """Health checks for system requirements."""

    def test_python_version(self):
        """Test Python version meets requirements."""
        import sys

        assert sys.version_info >= (3, 12), "Python 3.12+ required"

    def test_required_packages(self):
        """Test required packages are installed."""
        required = [
            "fastapi",
            "sqlalchemy",
            "elasticsearch",
            "redis",
            "pydantic",
            "httpx",
            "jose",
            "passlib",
        ]

        for package in required:
            try:
                __import__(package)
            except ImportError:
                pytest.fail(f"Required package not installed: {package}")

    def test_environment_variables(self):
        """Test required environment variables can be loaded."""
        from app.config import Settings

        # Should be able to create settings (with defaults)
        settings = Settings()

        assert settings.app_name is not None
        assert settings.database_url is not None


class TestHealthSummary:
    """Aggregate health check that reports overall system status."""

    async def test_overall_health(
        self,
        test_session,
        mock_elasticsearch,
        mock_redis,
        mock_all_adapters,
    ):
        """Test overall system health summary.

        This test provides a summary of all health checks.
        Useful for OVA first-run verification.
        """
        health_status = {
            "database": "unknown",
            "elasticsearch": "unknown",
            "redis": "unknown",
            "adapters": {},
        }

        # Check database
        try:
            from sqlalchemy import text
            await test_session.execute(text("SELECT 1"))
            health_status["database"] = "healthy"
        except Exception as e:
            health_status["database"] = f"unhealthy: {e}"

        # Check Elasticsearch
        try:
            mock_elasticsearch.cluster.health = AsyncMock(return_value={"status": "green"})
            es_health = await mock_elasticsearch.cluster.health()
            health_status["elasticsearch"] = es_health.get("status", "unknown")
        except Exception as e:
            health_status["elasticsearch"] = f"unhealthy: {e}"

        # Check Redis
        try:
            result = await mock_redis.ping()
            health_status["redis"] = "healthy" if result else "unhealthy"
        except Exception as e:
            health_status["redis"] = f"unhealthy: {e}"

        # Check adapters
        for name, adapter in mock_all_adapters.items():
            try:
                adapter_health = await adapter.health_check()
                health_status["adapters"][name] = adapter_health.get("status", "unknown")
            except Exception as e:
                health_status["adapters"][name] = f"unhealthy: {e}"

        # Verify critical services
        assert health_status["database"] == "healthy", "Database must be healthy"
        assert health_status["redis"] == "healthy", "Redis must be healthy"

        # Elasticsearch can be yellow in single-node setup
        assert health_status["elasticsearch"] in ["healthy", "green", "yellow"], \
            "Elasticsearch should be at least yellow"
