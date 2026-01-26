"""Unit tests for search and hunting endpoints."""

import pytest
from unittest.mock import AsyncMock, patch

from app.api.v1.search import kql_to_elasticsearch


pytestmark = pytest.mark.unit


class TestKQLParser:
    """Tests for KQL to Elasticsearch query parsing."""

    def test_wildcard_query(self):
        """Test wildcard query returns match_all."""
        result = kql_to_elasticsearch("*")
        assert result == {"match_all": {}}

    def test_empty_query(self):
        """Test empty query returns match_all."""
        result = kql_to_elasticsearch("")
        assert result == {"match_all": {}}

    def test_simple_equality(self):
        """Test simple field == value query."""
        result = kql_to_elasticsearch('user.name == "jsmith"')
        assert result == {"term": {"user.name": "jsmith"}}

    def test_not_equal(self):
        """Test field != value query."""
        result = kql_to_elasticsearch('status != "closed"')
        assert result == {"bool": {"must_not": [{"term": {"status": "closed"}}]}}

    def test_contains_operator(self):
        """Test contains operator."""
        result = kql_to_elasticsearch('message contains "error"')
        assert result == {"match": {"message": "error"}}

    def test_startswith_operator(self):
        """Test startswith operator."""
        result = kql_to_elasticsearch('host.name startswith "WORK"')
        assert result == {"prefix": {"host.name": "WORK"}}

    def test_endswith_operator(self):
        """Test endswith operator."""
        result = kql_to_elasticsearch('file.name endswith ".exe"')
        assert result == {"wildcard": {"file.name": "*.exe"}}

    def test_in_operator(self):
        """Test in operator."""
        result = kql_to_elasticsearch('status in ("new", "investigating")')
        assert result == {"terms": {"status": ["new", "investigating"]}}

    def test_greater_than(self):
        """Test > operator."""
        result = kql_to_elasticsearch("severity > 5")
        assert result == {"range": {"severity": {"gt": 5}}}

    def test_greater_or_equal(self):
        """Test >= operator."""
        result = kql_to_elasticsearch("count >= 10")
        assert result == {"range": {"count": {"gte": 10}}}

    def test_less_than(self):
        """Test < operator."""
        result = kql_to_elasticsearch("priority < 3")
        assert result == {"range": {"priority": {"lt": 3}}}

    def test_less_or_equal(self):
        """Test <= operator."""
        result = kql_to_elasticsearch("risk_score <= 50")
        assert result == {"range": {"risk_score": {"lte": 50}}}

    def test_and_operator(self):
        """Test AND operator."""
        result = kql_to_elasticsearch('user.name == "jsmith" and host.name == "WORK-001"')
        assert "bool" in result
        assert "must" in result["bool"]
        assert len(result["bool"]["must"]) == 2

    def test_or_operator(self):
        """Test OR operator."""
        result = kql_to_elasticsearch('status == "new" or status == "investigating"')
        assert "bool" in result
        assert "should" in result["bool"]
        assert result["bool"]["minimum_should_match"] == 1

    def test_not_operator(self):
        """Test NOT operator."""
        result = kql_to_elasticsearch('not status == "closed"')
        assert "bool" in result
        assert "must_not" in result["bool"]

    def test_complex_query(self):
        """Test complex query with multiple operators."""
        query = 'host.name == "SERVER-001" and (event_type == "login" or event_type == "logout")'
        result = kql_to_elasticsearch(query)
        assert "bool" in result

    def test_pipe_syntax_stripped(self):
        """Test that table | where syntax is handled."""
        result = kql_to_elasticsearch('SecurityEvent | where user.name == "admin"')
        assert result == {"term": {"user.name": "admin"}}

    def test_has_operator(self):
        """Test has operator."""
        result = kql_to_elasticsearch('tags has "malware"')
        assert result == {"match": {"tags": {"query": "malware", "operator": "and"}}}


class TestSearchEndpoint:
    """Tests for search query endpoint."""

    @pytest.mark.asyncio
    async def test_search_query_success(self, authenticated_client, mock_elasticsearch):
        """Test successful search query."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 5,
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "1", "_index": "test", "_source": {"message": "test1"}},
                    {"_id": "2", "_index": "test", "_source": {"message": "test2"}},
                ],
            },
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.post(
                "/api/v1/search/query",
                json={"query": "error"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["hits"]) == 2

    @pytest.mark.asyncio
    async def test_search_query_with_indices(self, authenticated_client, mock_elasticsearch):
        """Test search query with specific indices."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 5,
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "hits": [],
            },
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.post(
                "/api/v1/search/query",
                json={"query": "*", "indices": ["eleanor-events-2024.01"]},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_query_unauthorized(self, client):
        """Test search without authentication."""
        response = await client.post(
            "/api/v1/search/query",
            json={"query": "*"},
        )

        assert response.status_code == 401


class TestKQLEndpoint:
    """Tests for KQL query endpoint."""

    @pytest.mark.asyncio
    async def test_kql_query_success(self, authenticated_client, mock_elasticsearch):
        """Test successful KQL query."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 3,
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [
                    {"_id": "1", "_index": "test", "_source": {"user.name": "admin"}},
                ],
            },
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.post(
                "/api/v1/search/kql",
                json={"query": 'user.name == "admin"'},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_kql_query_parse_error(self, authenticated_client, mock_elasticsearch):
        """Test KQL query with parse error fallback."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 1,
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "hits": [],
            },
        })

        # Invalid KQL should fall back to query_string
        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.post(
                "/api/v1/search/kql",
                json={"query": "some invalid @#$ query"},
            )

        # Should succeed with fallback
        assert response.status_code in [200, 400]


class TestSavedQueries:
    """Tests for saved query management."""

    @pytest.mark.asyncio
    async def test_create_saved_query(self, authenticated_client):
        """Test creating a saved query."""
        query_data = {
            "name": "Find Suspicious PowerShell",
            "description": "Detect encoded PowerShell commands",
            "query": 'process.name == "powershell.exe" and process.command_line contains "-enc"',
            "indices": ["eleanor-events-*"],
            "category": "detection",
            "mitre_techniques": ["T1059.001"],
            "is_public": True,
        }

        response = await authenticated_client.post(
            "/api/v1/search/saved",
            json=query_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == query_data["name"]
        assert data["query"] == query_data["query"]
        assert data["is_public"] is True

    @pytest.mark.asyncio
    async def test_list_saved_queries(self, authenticated_client):
        """Test listing saved queries."""
        # First create a query
        await authenticated_client.post(
            "/api/v1/search/saved",
            json={
                "name": "Test Query",
                "query": "test:query",
            },
        )

        response = await authenticated_client.get("/api/v1/search/saved")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_delete_saved_query(self, authenticated_client):
        """Test deleting a saved query."""
        # Create a query
        create_response = await authenticated_client.post(
            "/api/v1/search/saved",
            json={
                "name": "To Delete",
                "query": "delete:me",
            },
        )
        query_id = create_response.json()["id"]

        # Delete it
        response = await authenticated_client.delete(f"/api/v1/search/saved/{query_id}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_other_users_query_forbidden(
        self, authenticated_client, admin_client, test_session
    ):
        """Test that users cannot delete other users' private queries."""
        # Admin creates a private query
        create_response = await admin_client.post(
            "/api/v1/search/saved",
            json={
                "name": "Admin Query",
                "query": "admin:only",
                "is_public": False,
            },
        )
        query_id = create_response.json()["id"]

        # Regular user tries to delete it
        response = await authenticated_client.delete(f"/api/v1/search/saved/{query_id}")

        assert response.status_code == 403


class TestSearchIndices:
    """Tests for index listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_indices(self, authenticated_client, mock_elasticsearch):
        """Test listing available indices."""
        mock_elasticsearch.cat.indices = AsyncMock(return_value=[
            {"index": "eleanor-events-2024.01", "docs.count": "1000", "store.size": "10mb", "health": "green"},
            {"index": "eleanor-timeline-2024.01", "docs.count": "500", "store.size": "5mb", "health": "green"},
        ])

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/search/indices")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestSearchSchema:
    """Tests for index schema endpoint."""

    @pytest.mark.asyncio
    async def test_get_index_schema(self, authenticated_client, mock_elasticsearch):
        """Test getting index field mappings."""
        mock_elasticsearch.indices.get_mapping = AsyncMock(return_value={
            "eleanor-events-2024.01": {
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "message": {"type": "text"},
                        "host.name": {"type": "keyword"},
                    }
                }
            }
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/search/schema/eleanor-events-2024.01"
            )

        assert response.status_code == 200
        data = response.json()
        assert "mappings" in data
        assert "properties" in data["mappings"]
