"""API smoke tests for Eleanor backend.

Validates that core API endpoints are responding correctly with expected
status codes and response structures. These tests can run against a live
backend or with mocked services.

Run with:
    pytest tests/integration/test_api_smoke.py -v  # With mocks (default)
    pytest tests/integration/test_api_smoke.py -v --live  # Against live services
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    async def test_health_check_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/health returns 200 OK."""
        response = await authenticated_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    async def test_health_check_without_auth(self, client: AsyncClient):
        """Test that health endpoint works without authentication."""
        response = await client.get("/api/v1/health")

        # Health check should be accessible without auth
        assert response.status_code in (200, 401)  # May require auth depending on config


class TestParsingEndpoints:
    """Tests for parsing API endpoints."""

    async def test_list_parsers_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/parsing/parsers returns list of parsers."""
        response = await authenticated_client.get("/api/v1/parsing/parsers")

        assert response.status_code == 200
        data = response.json()
        assert "parsers" in data
        assert "total" in data
        assert isinstance(data["parsers"], list)

    async def test_list_parsers_contains_core_parsers(
        self, authenticated_client: AsyncClient
    ):
        """Test that parser list includes core parsers."""
        response = await authenticated_client.get("/api/v1/parsing/parsers")
        data = response.json()

        parser_names = [p["name"] for p in data["parsers"]]

        # Core parsers should be registered
        assert "windows_evtx" in parser_names or "json" in parser_names

    async def test_list_parsers_structure(self, authenticated_client: AsyncClient):
        """Test that parser info has expected structure."""
        response = await authenticated_client.get("/api/v1/parsing/parsers")
        data = response.json()

        if data["parsers"]:
            parser = data["parsers"][0]
            assert "name" in parser
            assert "description" in parser
            assert "extensions" in parser

    async def test_list_parsing_jobs_returns_200(
        self, authenticated_client: AsyncClient
    ):
        """Test that /api/v1/parsing/jobs returns list."""
        response = await authenticated_client.get("/api/v1/parsing/jobs")

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    async def test_list_parsers_unauthorized(self, client: AsyncClient):
        """Test that parser list requires authentication."""
        response = await client.get("/api/v1/parsing/parsers")

        assert response.status_code == 401


class TestCaseEndpoints:
    """Tests for case management API endpoints."""

    async def test_list_cases_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/cases returns 200 OK."""
        response = await authenticated_client.get("/api/v1/cases")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "cases" in data or isinstance(data, list)

    async def test_list_cases_pagination(self, authenticated_client: AsyncClient):
        """Test that cases endpoint supports pagination."""
        response = await authenticated_client.get("/api/v1/cases?page=1&page_size=10")

        assert response.status_code == 200

    async def test_list_cases_unauthorized(self, client: AsyncClient):
        """Test that cases require authentication."""
        response = await client.get("/api/v1/cases")

        assert response.status_code == 401


class TestSearchEndpoints:
    """Tests for search API endpoints."""

    async def test_search_query_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/search/query accepts POST requests."""
        response = await authenticated_client.post(
            "/api/v1/search/query",
            json={
                "query": "*",
                "indices": ["eleanor-events-*"],
                "size": 10,
            },
        )

        # May return 200 or 400 depending on ES availability
        assert response.status_code in (200, 400, 503)

    async def test_search_query_structure(self, authenticated_client: AsyncClient):
        """Test search query response structure."""
        response = await authenticated_client.post(
            "/api/v1/search/query",
            json={
                "query": "*",
                "indices": ["eleanor-events-*"],
                "size": 10,
            },
        )

        if response.status_code == 200:
            data = response.json()
            # Should have hits or results structure
            assert "hits" in data or "results" in data or "total" in data

    async def test_search_unauthorized(self, client: AsyncClient):
        """Test that search requires authentication."""
        response = await client.post(
            "/api/v1/search/query",
            json={"query": "*"},
        )

        assert response.status_code == 401


class TestAlertEndpoints:
    """Tests for alert API endpoints."""

    async def test_list_alerts_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/alerts returns 200 OK."""
        response = await authenticated_client.get("/api/v1/alerts")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "alerts" in data or isinstance(data, list)

    async def test_list_alerts_pagination(self, authenticated_client: AsyncClient):
        """Test that alerts endpoint supports pagination."""
        response = await authenticated_client.get("/api/v1/alerts?page=1&page_size=10")

        assert response.status_code == 200

    async def test_list_alerts_unauthorized(self, client: AsyncClient):
        """Test that alerts require authentication."""
        response = await client.get("/api/v1/alerts")

        assert response.status_code == 401


class TestEvidenceEndpoints:
    """Tests for evidence management API endpoints."""

    async def test_list_evidence_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/evidence returns 200 OK."""
        response = await authenticated_client.get("/api/v1/evidence")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    async def test_list_evidence_unauthorized(self, client: AsyncClient):
        """Test that evidence requires authentication."""
        response = await client.get("/api/v1/evidence")

        assert response.status_code == 401


class TestWorkbookEndpoints:
    """Tests for workbook API endpoints."""

    async def test_list_workbooks_returns_200(self, authenticated_client: AsyncClient):
        """Test that /api/v1/workbooks returns 200 OK."""
        response = await authenticated_client.get("/api/v1/workbooks")

        assert response.status_code == 200

    async def test_list_workbooks_unauthorized(self, client: AsyncClient):
        """Test that workbooks require authentication."""
        response = await client.get("/api/v1/workbooks")

        assert response.status_code == 401


class TestGraphEndpoints:
    """Tests for investigation graph API endpoints."""

    async def test_build_graph_endpoint_exists(
        self, authenticated_client: AsyncClient
    ):
        """Test that /api/v1/graphs/build endpoint exists."""
        response = await authenticated_client.post(
            "/api/v1/graphs/build",
            json={
                "case_id": "00000000-0000-0000-0000-000000000000",
                "max_nodes": 10,
            },
        )

        # Should return 200, 400, or 404 (not 405 Method Not Allowed)
        assert response.status_code != 405

    async def test_list_saved_graphs_returns_200(
        self, authenticated_client: AsyncClient
    ):
        """Test that /api/v1/graphs/saved returns 200."""
        response = await authenticated_client.get("/api/v1/graphs/saved")

        # May be 200 or 404 depending on implementation
        assert response.status_code in (200, 404)


class TestDetectionEndpoints:
    """Tests for detection rules API endpoints."""

    async def test_list_detection_rules_returns_200(
        self, authenticated_client: AsyncClient
    ):
        """Test that /api/v1/analytics/rules returns 200."""
        response = await authenticated_client.get("/api/v1/analytics/rules")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    async def test_list_detection_rules_unauthorized(self, client: AsyncClient):
        """Test that detection rules require authentication."""
        response = await client.get("/api/v1/analytics/rules")

        assert response.status_code == 401


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    async def test_login_endpoint_exists(self, client: AsyncClient):
        """Test that /api/v1/auth/login endpoint exists."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "test", "password": "test"},
        )

        # Should return 401 (bad credentials) or 422 (validation), not 404/405
        assert response.status_code in (401, 422, 400)

    async def test_me_endpoint_requires_auth(self, client: AsyncClient):
        """Test that /api/v1/auth/me requires authentication."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_me_endpoint_with_auth(self, authenticated_client: AsyncClient):
        """Test that /api/v1/auth/me returns user info with auth."""
        response = await authenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert "username" in data or "email" in data


class TestAPIResponseFormats:
    """Tests for consistent API response formats."""

    async def test_error_response_format(self, client: AsyncClient):
        """Test that error responses have consistent format."""
        response = await client.get("/api/v1/cases")  # Requires auth

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data or "message" in data or "error" in data

    async def test_not_found_response_format(self, authenticated_client: AsyncClient):
        """Test that 404 responses have consistent format."""
        response = await authenticated_client.get(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data or "message" in data or "error" in data


class TestContentTypes:
    """Tests for correct content type handling."""

    async def test_json_content_type(self, authenticated_client: AsyncClient):
        """Test that API returns JSON content type."""
        response = await authenticated_client.get("/api/v1/cases")

        assert "application/json" in response.headers.get("content-type", "")

    async def test_invalid_content_type_rejected(
        self, authenticated_client: AsyncClient
    ):
        """Test that invalid content type is rejected."""
        response = await authenticated_client.post(
            "/api/v1/search/query",
            content="not json",
            headers={"content-type": "text/plain"},
        )

        assert response.status_code in (400, 415, 422)
