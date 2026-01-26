"""Unit tests for analytics and detection rules endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4


pytestmark = pytest.mark.unit


def mock_execution_result():
    """Create a mock result dict for detection engine execution."""
    return {
        "threshold_exceeded": False,
        "hits": [],
        "hit_count": 0,
        "events_scanned": 0,
    }


class TestListRules:
    """Tests for rule listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_rules_empty(self, authenticated_client):
        """Test listing rules when none exist."""
        response = await authenticated_client.get("/api/v1/analytics/rules")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_rules_pagination(self, authenticated_client):
        """Test rule listing pagination."""
        # Create several rules first
        for i in range(5):
            await authenticated_client.post(
                "/api/v1/analytics/rules",
                json={
                    "name": f"Test Rule {i}",
                    "query": "test:query",
                },
            )

        response = await authenticated_client.get(
            "/api/v1/analytics/rules?page=1&page_size=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_severity(self, authenticated_client):
        """Test filtering rules by severity."""
        # Create rule with specific severity
        await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "High Severity Rule",
                "query": "severity:high",
                "severity": "high",
            },
        )

        response = await authenticated_client.get(
            "/api/v1/analytics/rules?severity=high"
        )

        assert response.status_code == 200
        data = response.json()
        for rule in data["items"]:
            assert rule["severity"] == "high"

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_status(self, authenticated_client):
        """Test filtering rules by status."""
        response = await authenticated_client.get(
            "/api/v1/analytics/rules?status=enabled"
        )

        assert response.status_code == 200
        data = response.json()
        for rule in data["items"]:
            assert rule["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_list_rules_search(self, authenticated_client):
        """Test searching rules by name."""
        await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "PowerShell Detection",
                "query": 'process.name == "powershell.exe"',
            },
        )

        response = await authenticated_client.get(
            "/api/v1/analytics/rules?search=PowerShell"
        )

        assert response.status_code == 200
        data = response.json()
        assert any("PowerShell" in rule["name"] for rule in data["items"])

    @pytest.mark.asyncio
    async def test_list_rules_unauthorized(self, client):
        """Test listing rules without authentication."""
        response = await client.get("/api/v1/analytics/rules")

        assert response.status_code == 401


class TestCreateRule:
    """Tests for rule creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_rule_success(self, authenticated_client):
        """Test successful rule creation."""
        rule_data = {
            "name": "Detect Mimikatz",
            "description": "Detects Mimikatz credential dumping tool",
            "rule_type": "scheduled",
            "severity": "critical",
            "query": 'process.name == "mimikatz.exe" or process.command_line contains "sekurlsa"',
            "query_language": "kql",
            "indices": ["eleanor-events-*"],
            "schedule_interval": 15,
            "lookback_period": 60,
            "mitre_tactics": ["TA0006"],
            "mitre_techniques": ["T1003"],
            "tags": ["mimikatz", "credential-dumping"],
            "category": "credential-access",
        }

        response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json=rule_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == rule_data["name"]
        assert data["severity"] == "critical"
        assert data["status"] == "disabled"  # New rules start disabled
        assert data["mitre_techniques"] == ["T1003"]

    @pytest.mark.asyncio
    async def test_create_rule_minimal(self, authenticated_client):
        """Test creating rule with minimal data."""
        response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Simple Rule",
                "query": "error:true",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Simple Rule"
        assert data["severity"] == "medium"  # Default
        assert data["rule_type"] == "scheduled"  # Default

    @pytest.mark.asyncio
    async def test_create_rule_empty_name_fails(self, authenticated_client):
        """Test creating rule with empty name fails."""
        response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "",
                "query": "test",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_rule_empty_query_fails(self, authenticated_client):
        """Test creating rule with empty query fails."""
        response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_rule_with_threshold(self, authenticated_client):
        """Test creating threshold-based rule."""
        response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Brute Force Detection",
                "query": 'event_type == "authentication_failure"',
                "threshold_count": 10,
                "threshold_field": "user.name",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["threshold_count"] == 10
        assert data["threshold_field"] == "user.name"


class TestGetRule:
    """Tests for getting individual rule."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, authenticated_client):
        """Test getting rule by ID."""
        # Create a rule first
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test",
            },
        )
        rule_id = create_response.json()["id"]

        response = await authenticated_client.get(f"/api/v1/analytics/rules/{rule_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == rule_id
        assert data["name"] == "Test Rule"

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, authenticated_client):
        """Test getting non-existent rule."""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/analytics/rules/{fake_id}")

        assert response.status_code == 404


class TestUpdateRule:
    """Tests for rule update endpoint."""

    @pytest.mark.asyncio
    async def test_update_rule_name(self, authenticated_client):
        """Test updating rule name."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Original Name",
                "query": "test",
            },
        )
        rule_id = create_response.json()["id"]

        response = await authenticated_client.patch(
            f"/api/v1/analytics/rules/{rule_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_rule_query(self, authenticated_client):
        """Test updating rule query."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "original:query",
            },
        )
        rule_id = create_response.json()["id"]

        response = await authenticated_client.patch(
            f"/api/v1/analytics/rules/{rule_id}",
            json={"query": "updated:query"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "updated:query"

    @pytest.mark.asyncio
    async def test_update_rule_severity(self, authenticated_client):
        """Test updating rule severity."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test",
                "severity": "low",
            },
        )
        rule_id = create_response.json()["id"]

        response = await authenticated_client.patch(
            f"/api/v1/analytics/rules/{rule_id}",
            json={"severity": "critical"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["severity"] == "critical"


class TestDeleteRule:
    """Tests for rule deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self, authenticated_client):
        """Test successful rule deletion."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "To Delete",
                "query": "delete:me",
            },
        )
        rule_id = create_response.json()["id"]

        response = await authenticated_client.delete(f"/api/v1/analytics/rules/{rule_id}")

        assert response.status_code == 204

        # Verify deleted
        get_response = await authenticated_client.get(f"/api/v1/analytics/rules/{rule_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self, authenticated_client):
        """Test deleting non-existent rule."""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/analytics/rules/{fake_id}")

        assert response.status_code == 404


class TestEnableDisableRule:
    """Tests for rule enable/disable endpoints."""

    @pytest.mark.asyncio
    async def test_enable_rule(self, authenticated_client):
        """Test enabling a rule."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test",
            },
        )
        rule_id = create_response.json()["id"]
        assert create_response.json()["status"] == "disabled"

        response = await authenticated_client.post(
            f"/api/v1/analytics/rules/{rule_id}/enable"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_disable_rule(self, authenticated_client):
        """Test disabling a rule."""
        # Create and enable
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test",
            },
        )
        rule_id = create_response.json()["id"]
        await authenticated_client.post(f"/api/v1/analytics/rules/{rule_id}/enable")

        # Disable
        response = await authenticated_client.post(
            f"/api/v1/analytics/rules/{rule_id}/disable"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"


class TestRunRule:
    """Tests for manual rule execution."""

    @pytest.mark.asyncio
    async def test_run_rule(self, authenticated_client):
        """Test manually triggering a rule."""
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test:manual",
            },
        )
        rule_id = create_response.json()["id"]

        # Mock the detection engine to avoid Elasticsearch connection
        mock_engine = AsyncMock()
        mock_engine.execute_rule = AsyncMock(return_value=mock_execution_result())

        with patch("app.api.v1.analytics.get_detection_engine", return_value=mock_engine):
            response = await authenticated_client.post(
                f"/api/v1/analytics/rules/{rule_id}/run"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["rule_id"] == rule_id
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_run_rule_not_found(self, authenticated_client):
        """Test running non-existent rule."""
        fake_id = uuid4()
        response = await authenticated_client.post(
            f"/api/v1/analytics/rules/{fake_id}/run"
        )

        assert response.status_code == 404


class TestRuleExecutions:
    """Tests for rule execution history."""

    @pytest.mark.asyncio
    async def test_list_rule_executions(self, authenticated_client):
        """Test listing rule executions endpoint."""
        # Create a rule first
        create_response = await authenticated_client.post(
            "/api/v1/analytics/rules",
            json={
                "name": "Test Rule",
                "query": "test",
            },
        )
        rule_id = create_response.json()["id"]

        # Test that the executions endpoint returns a list
        # Note: Mock session doesn't persist executions between requests,
        # so we only verify the endpoint returns a valid list format
        response = await authenticated_client.get(
            f"/api/v1/analytics/rules/{rule_id}/executions"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAnalyticsStats:
    """Tests for analytics statistics."""

    @pytest.mark.asyncio
    async def test_get_analytics_stats(self, authenticated_client):
        """Test getting analytics statistics."""
        # Create some rules
        for severity in ["low", "medium", "high"]:
            await authenticated_client.post(
                "/api/v1/analytics/rules",
                json={
                    "name": f"{severity.title()} Rule",
                    "query": "test",
                    "severity": severity,
                },
            )

        response = await authenticated_client.get("/api/v1/analytics/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert "by_status" in data
        assert "by_severity" in data
        assert "total_hits" in data
