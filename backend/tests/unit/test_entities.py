"""Unit tests for entity profile endpoints."""

import pytest
from unittest.mock import AsyncMock, patch


pytestmark = pytest.mark.unit


class TestHostProfile:
    """Tests for host entity profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_host_profile(self, authenticated_client, mock_elasticsearch):
        """Test getting host profile."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 100}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-01T00:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T15:30:00Z"},
                "cases": {"buckets": [{"key": "case-1"}, {"key": "case-2"}]},
                "event_types": {"buckets": [
                    {"key": "process", "doc_count": 50},
                    {"key": "network", "doc_count": 30},
                ]},
                "users": {"buckets": [{"key": "jsmith"}, {"key": "admin"}]},
                "processes": {"buckets": [{"key": "chrome.exe"}, {"key": "explorer.exe"}]},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/entities/hosts/WORKSTATION-001")

        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "host"
        assert data["identifier"] == "WORKSTATION-001"
        assert data["event_count"] == 100
        assert len(data["related_cases"]) == 2
        assert "event_types" in data["summary"]
        assert "users" in data["summary"]
        assert "top_processes" in data["summary"]

    @pytest.mark.asyncio
    async def test_get_host_profile_not_found(self, authenticated_client, mock_elasticsearch):
        """Test getting profile for host with no events."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 0}},
            "aggregations": {
                "first_seen": {},
                "last_seen": {},
                "cases": {"buckets": []},
                "event_types": {"buckets": []},
                "users": {"buckets": []},
                "processes": {"buckets": []},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/entities/hosts/NONEXISTENT")

        assert response.status_code == 200
        data = response.json()
        assert data["event_count"] == 0
        assert data["related_cases"] == []

    @pytest.mark.asyncio
    async def test_get_host_profile_unauthorized(self, client):
        """Test getting host profile without authentication."""
        response = await client.get("/api/v1/entities/hosts/WORKSTATION-001")

        assert response.status_code == 401


class TestUserProfile:
    """Tests for user entity profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_profile(self, authenticated_client, mock_elasticsearch):
        """Test getting user profile."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 250}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-05T08:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T17:00:00Z"},
                "cases": {"buckets": [{"key": "case-3"}]},
                "event_types": {"buckets": [
                    {"key": "authentication", "doc_count": 100},
                    {"key": "file_access", "doc_count": 80},
                ]},
                "hosts": {"buckets": [{"key": "WORKSTATION-001"}, {"key": "SERVER-001"}]},
                "processes": {"buckets": [{"key": "outlook.exe"}, {"key": "chrome.exe"}]},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/entities/users/jsmith")

        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "user"
        assert data["identifier"] == "jsmith"
        assert data["event_count"] == 250
        assert "hosts" in data["summary"]

    @pytest.mark.asyncio
    async def test_get_user_profile_special_characters(self, authenticated_client, mock_elasticsearch):
        """Test getting profile for username with domain."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 50}},
            "aggregations": {
                "first_seen": {},
                "last_seen": {},
                "cases": {"buckets": []},
                "event_types": {"buckets": []},
                "hosts": {"buckets": []},
                "processes": {"buckets": []},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/entities/users/DOMAIN%5Cuser")

        assert response.status_code == 200


class TestIPProfile:
    """Tests for IP address entity profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_ip_profile(self, authenticated_client, mock_elasticsearch):
        """Test getting IP address profile."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 500}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-10T00:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T23:59:59Z"},
                "cases": {"buckets": [{"key": "case-5"}]},
                "event_types": {"buckets": [
                    {"key": "connection", "doc_count": 400},
                    {"key": "dns", "doc_count": 100},
                ]},
                "hosts": {"buckets": [{"key": "FIREWALL"}, {"key": "PROXY"}]},
                "ports": {"buckets": [{"key": 443}, {"key": 80}]},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get("/api/v1/entities/ips/192.168.1.100")

        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "ip"
        assert data["identifier"] == "192.168.1.100"
        assert data["event_count"] == 500
        assert "ports" in data["summary"]

    @pytest.mark.asyncio
    async def test_get_ip_profile_ipv6(self, authenticated_client, mock_elasticsearch):
        """Test getting IPv6 address profile."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 10}},
            "aggregations": {
                "first_seen": {},
                "last_seen": {},
                "cases": {"buckets": []},
                "event_types": {"buckets": []},
                "hosts": {"buckets": []},
                "ports": {"buckets": []},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            # URL encoded IPv6
            response = await authenticated_client.get(
                "/api/v1/entities/ips/2001%3A0db8%3A85a3%3A0000%3A0000%3A8a2e%3A0370%3A7334"
            )

        assert response.status_code == 200


class TestEntityEvents:
    """Tests for entity events endpoint."""

    @pytest.mark.asyncio
    async def test_get_host_events(self, authenticated_client, mock_elasticsearch):
        """Test getting events for a host."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 50},
                "hits": [
                    {
                        "_id": "event-1",
                        "_source": {
                            "@timestamp": "2024-01-20T10:00:00Z",
                            "event_type": "process",
                            "message": "Process created",
                            "case_id": "case-1",
                        },
                    },
                    {
                        "_id": "event-2",
                        "_source": {
                            "@timestamp": "2024-01-20T10:01:00Z",
                            "event_type": "network",
                            "message": "Connection established",
                            "case_id": "case-1",
                        },
                    },
                ],
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/entities/host/WORKSTATION-001/events"
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "event-1"

    @pytest.mark.asyncio
    async def test_get_user_events(self, authenticated_client, mock_elasticsearch):
        """Test getting events for a user."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 10},
                "hits": [
                    {
                        "_id": "event-3",
                        "_source": {
                            "@timestamp": "2024-01-20T09:00:00Z",
                            "event_type": "login",
                            "message": "User logged in",
                        },
                    },
                ],
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/entities/user/jsmith/events"
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_ip_events(self, authenticated_client, mock_elasticsearch):
        """Test getting events for an IP address."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 25},
                "hits": [],
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/entities/ip/198.51.100.50/events"
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_events_invalid_entity_type(self, authenticated_client, mock_elasticsearch):
        """Test getting events with invalid entity type."""
        # Must patch get_elasticsearch since it's called directly, not via DI
        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/entities/invalid_type/test/events"
            )

        assert response.status_code == 400
        assert "Unknown entity type" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_get_events_pagination(self, authenticated_client, mock_elasticsearch):
        """Test events pagination."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 100},
                "hits": [],
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.get(
                "/api/v1/entities/host/TEST/events?from=50&size=25"
            )

        assert response.status_code == 200
        # Verify search was called with correct pagination
        mock_elasticsearch.search.assert_called_once()
        call_args = mock_elasticsearch.search.call_args
        assert call_args[1]["body"]["from"] == 50
        assert call_args[1]["body"]["size"] == 25
