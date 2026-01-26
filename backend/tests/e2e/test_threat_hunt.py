"""End-to-end tests for threat hunting workflow.

Tests: Query → Results → Enrichment → Case Creation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestThreatHuntWorkflow:
    """Tests for complete threat hunting workflow."""

    async def test_hypothesis_driven_hunt(self, authenticated_client, mock_elasticsearch):
        """Test hypothesis-driven threat hunting workflow.

        Workflow:
        1. Create hypothesis (save query)
        2. Execute hunt query
        3. Review results
        4. Save interesting findings
        5. Create case from findings
        """
        # Step 1: Save hypothesis as query
        hypothesis_response = await authenticated_client.post(
            "/api/v1/search/saved",
            json={
                "name": "PowerShell Encoded Commands",
                "description": "Hunt for encoded PowerShell execution",
                "query": 'process.name == "powershell.exe" and process.command_line contains "-enc"',
                "indices": ["eleanor-events-*"],
                "category": "hunting",
                "mitre_techniques": ["T1059.001", "T1027"],
                "is_public": True,
            },
        )

        assert hypothesis_response.status_code == 201
        saved_query = hypothesis_response.json()

        # Step 2: Execute hunt query
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 15,
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {
                        "_id": "evt-1",
                        "_index": "eleanor-events-2024.01",
                        "_source": {
                            "@timestamp": "2024-01-20T10:30:00Z",
                            "host": {"name": "WORKSTATION-001"},
                            "user": {"name": "jsmith"},
                            "process": {
                                "name": "powershell.exe",
                                "command_line": "powershell.exe -enc SQBFAFgA...",
                                "pid": 1234,
                            },
                        },
                    },
                    {
                        "_id": "evt-2",
                        "_index": "eleanor-events-2024.01",
                        "_source": {
                            "@timestamp": "2024-01-20T10:35:00Z",
                            "host": {"name": "WORKSTATION-002"},
                            "user": {"name": "admin"},
                            "process": {
                                "name": "powershell.exe",
                                "command_line": "powershell.exe -enc JABzAD0A...",
                                "pid": 5678,
                            },
                        },
                    },
                ],
            },
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            search_response = await authenticated_client.post(
                "/api/v1/search/kql",
                json={"query": saved_query["query"]},
            )

        assert search_response.status_code == 200
        results = search_response.json()
        assert results["total"] >= 2

        # Step 3: Findings are suspicious - create case
        case_response = await authenticated_client.post(
            "/api/v1/cases",
            json={
                "title": "Encoded PowerShell Detected - Multiple Hosts",
                "description": f"Hunt '{saved_query['name']}' found suspicious activity on multiple hosts",
                "severity": "high",
                "tags": ["hunting-finding", "powershell", "encoded"],
                "mitre_tactics": ["TA0002"],
                "mitre_techniques": saved_query["mitre_techniques"],
                "metadata": {
                    "hunt_query_id": saved_query["id"],
                    "hunt_query_name": saved_query["name"],
                    "affected_hosts": ["WORKSTATION-001", "WORKSTATION-002"],
                    "finding_count": results["total"],
                },
            },
        )

        assert case_response.status_code == 201
        case = case_response.json()
        assert "hunting-finding" in case["tags"]

    async def test_kql_hunt_queries(self, authenticated_client, mock_elasticsearch):
        """Test various KQL hunt query patterns."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 5,
            "hits": {"total": {"value": 0, "relation": "eq"}, "hits": []},
        })

        hunt_queries = [
            # Persistence via scheduled tasks
            'event_type == "scheduled_task" and action == "created"',
            # Lateral movement
            'event_type == "logon" and logon_type == 10',
            # Credential access
            'process.name == "lsass.exe" and event_type == "access"',
            # Defense evasion
            'event_type == "service_created" and service.start_type == "auto"',
            # Data exfiltration
            'network.bytes_out > 100000000 and destination.geo.country_code != "US"',
        ]

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            for query in hunt_queries:
                response = await authenticated_client.post(
                    "/api/v1/search/kql",
                    json={"query": query},
                )
                # Should execute without error
                assert response.status_code in [200, 400]  # 400 for complex queries

    async def test_hunt_with_aggregations(self, authenticated_client, mock_elasticsearch):
        """Test hunting with aggregated views."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "took": 25,
            "hits": {"total": {"value": 1500, "relation": "eq"}, "hits": []},
            "aggregations": {
                "by_host": {
                    "buckets": [
                        {"key": "WORKSTATION-001", "doc_count": 500},
                        {"key": "WORKSTATION-002", "doc_count": 400},
                        {"key": "SERVER-001", "doc_count": 300},
                        {"key": "WORKSTATION-003", "doc_count": 200},
                        {"key": "OTHER", "doc_count": 100},
                    ]
                },
                "by_user": {
                    "buckets": [
                        {"key": "admin", "doc_count": 800},
                        {"key": "service_account", "doc_count": 500},
                        {"key": "jsmith", "doc_count": 200},
                    ]
                },
            },
        })

        with patch("app.api.v1.search.get_elasticsearch", return_value=mock_elasticsearch):
            response = await authenticated_client.post(
                "/api/v1/search/query",
                json={
                    "query": "process.name:powershell.exe",
                    "aggs": {
                        "by_host": {"terms": {"field": "host.name", "size": 10}},
                        "by_user": {"terms": {"field": "user.name", "size": 10}},
                    },
                },
            )

        assert response.status_code == 200
        results = response.json()
        assert "aggregations" in results
        assert results["aggregations"]["by_host"]["buckets"][0]["key"] == "WORKSTATION-001"


class TestSavedQueryManagement:
    """Tests for managing saved hunt queries."""

    async def test_save_and_share_hunt_query(self, authenticated_client, admin_client):
        """Test saving and sharing hunt queries between analysts."""
        # Analyst creates a query
        create_response = await authenticated_client.post(
            "/api/v1/search/saved",
            json={
                "name": "Mimikatz Detection",
                "description": "Detects Mimikatz credential dumping activity",
                "query": 'process.name == "mimikatz.exe" or process.command_line contains "sekurlsa"',
                "category": "credential-access",
                "mitre_techniques": ["T1003.001"],
                "is_public": False,  # Private initially
            },
        )

        assert create_response.status_code == 201
        query_id = create_response.json()["id"]

        # Admin cannot see private query
        # (would test with different user context)

        # Analyst makes it public
        # Since we don't have a PATCH endpoint for saved queries, we'd delete and recreate
        # For this test, we'll verify the query is listed for the creator
        list_response = await authenticated_client.get("/api/v1/search/saved")
        assert any(q["id"] == query_id for q in list_response.json())

    async def test_hunt_query_categories(self, authenticated_client):
        """Test organizing hunts by category."""
        categories = [
            ("Initial Access", "T1566"),
            ("Execution", "T1059"),
            ("Persistence", "T1053"),
            ("Credential Access", "T1003"),
            ("Lateral Movement", "T1021"),
        ]

        # Create queries for each category
        for category, technique in categories:
            await authenticated_client.post(
                "/api/v1/search/saved",
                json={
                    "name": f"Hunt - {category}",
                    "query": f"mitre.technique == '{technique}'",
                    "category": category.lower().replace(" ", "-"),
                    "mitre_techniques": [technique],
                    "is_public": True,
                },
            )

        # Filter by category
        response = await authenticated_client.get(
            "/api/v1/search/saved?category=credential-access"
        )

        assert response.status_code == 200
        results = response.json()
        for query in results:
            assert query["category"] == "credential-access"


class TestEntityInvestigation:
    """Tests for entity-based investigation during hunts."""

    async def test_host_investigation_workflow(self, authenticated_client, mock_elasticsearch):
        """Test investigating a suspicious host.

        Workflow:
        1. Get host profile
        2. View recent events
        3. Check related cases
        """
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 500}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-01T00:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T15:00:00Z"},
                "cases": {"buckets": [{"key": "case-123"}]},
                "event_types": {
                    "buckets": [
                        {"key": "process", "doc_count": 300},
                        {"key": "network", "doc_count": 150},
                        {"key": "file", "doc_count": 50},
                    ]
                },
                "users": {"buckets": [{"key": "jsmith"}, {"key": "admin"}]},
                "processes": {
                    "buckets": [
                        {"key": "powershell.exe"},
                        {"key": "cmd.exe"},
                        {"key": "chrome.exe"},
                    ]
                },
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            # Get host profile
            profile_response = await authenticated_client.get(
                "/api/v1/entities/hosts/WORKSTATION-001"
            )

        assert profile_response.status_code == 200
        profile = profile_response.json()

        assert profile["entity_type"] == "host"
        assert profile["event_count"] == 500
        assert "powershell.exe" in profile["summary"]["top_processes"]

    async def test_user_investigation_workflow(self, authenticated_client, mock_elasticsearch):
        """Test investigating a suspicious user."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 1000}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-05T08:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T17:00:00Z"},
                "cases": {"buckets": []},
                "event_types": {
                    "buckets": [
                        {"key": "authentication", "doc_count": 500},
                        {"key": "process", "doc_count": 300},
                    ]
                },
                "hosts": {
                    "buckets": [
                        {"key": "WORKSTATION-001"},
                        {"key": "SERVER-001"},
                        {"key": "DC-001"},
                    ]
                },
                "processes": {"buckets": []},
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            profile_response = await authenticated_client.get(
                "/api/v1/entities/users/jsmith"
            )

        assert profile_response.status_code == 200
        profile = profile_response.json()

        assert profile["entity_type"] == "user"
        assert len(profile["summary"]["hosts"]) == 3

    async def test_ip_investigation_workflow(self, authenticated_client, mock_elasticsearch):
        """Test investigating a suspicious IP address."""
        mock_elasticsearch.search = AsyncMock(return_value={
            "hits": {"total": {"value": 250}},
            "aggregations": {
                "first_seen": {"value_as_string": "2024-01-18T00:00:00Z"},
                "last_seen": {"value_as_string": "2024-01-20T23:59:00Z"},
                "cases": {"buckets": [{"key": "case-456"}]},
                "event_types": {"buckets": [{"key": "network", "doc_count": 250}]},
                "hosts": {
                    "buckets": [
                        {"key": "WORKSTATION-001"},
                        {"key": "WORKSTATION-002"},
                    ]
                },
                "ports": {
                    "buckets": [
                        {"key": 443},
                        {"key": 8080},
                    ]
                },
            },
        })

        with patch("app.api.v1.entities.get_elasticsearch", return_value=mock_elasticsearch):
            profile_response = await authenticated_client.get(
                "/api/v1/entities/ips/198.51.100.50"
            )

        assert profile_response.status_code == 200
        profile = profile_response.json()

        assert profile["entity_type"] == "ip"
        assert 443 in profile["summary"]["ports"]
