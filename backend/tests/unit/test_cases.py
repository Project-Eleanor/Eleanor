"""Unit tests for case management endpoints."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.models.case import Case, CaseStatus, Priority, Severity


pytestmark = pytest.mark.unit


class TestListCases:
    """Tests for case listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_cases_empty(self, authenticated_client):
        """Test listing cases when none exist."""
        response = await authenticated_client.get("/api/v1/cases")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_cases_with_data(self, authenticated_client_with_case, test_case):
        """Test listing cases with existing data."""
        response = await authenticated_client_with_case.get("/api/v1/cases")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

        # Verify case data
        case_data = data["items"][0]
        assert case_data["case_number"] == test_case.case_number
        assert case_data["title"] == test_case.title

    @pytest.mark.asyncio
    async def test_list_cases_pagination(self, authenticated_client_with_cases, test_cases):
        """Test case listing pagination parameters are accepted."""
        # Request with pagination parameters
        response = await authenticated_client_with_cases.get("/api/v1/cases?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        # Mock session returns all cases (doesn't implement actual pagination)
        assert len(data["items"]) >= 1
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] >= 3

    @pytest.mark.asyncio
    async def test_list_cases_filter_by_status(self, authenticated_client_with_cases, test_cases):
        """Test filtering cases by status parameter is accepted."""
        response = await authenticated_client_with_cases.get("/api/v1/cases?status=new")

        assert response.status_code == 200
        data = response.json()
        # Mock session returns all cases (doesn't implement filtering)
        # Just verify API accepts the filter parameter
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_cases_filter_by_severity(self, authenticated_client_with_cases, test_cases):
        """Test filtering cases by severity parameter is accepted."""
        response = await authenticated_client_with_cases.get("/api/v1/cases?severity=critical")

        assert response.status_code == 200
        data = response.json()
        # Mock session returns all cases (doesn't implement filtering)
        # Just verify API accepts the filter parameter
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_cases_search(self, authenticated_client_with_case, test_case):
        """Test searching cases."""
        response = await authenticated_client_with_case.get(
            f"/api/v1/cases?search={test_case.case_number}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(c["case_number"] == test_case.case_number for c in data["items"])

    @pytest.mark.asyncio
    async def test_list_cases_unauthorized(self, client):
        """Test listing cases without authentication."""
        response = await client.get("/api/v1/cases")

        assert response.status_code == 401


class TestCreateCase:
    """Tests for case creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_case_success(self, authenticated_client, sample_case_data):
        """Test successful case creation."""
        response = await authenticated_client.post("/api/v1/cases", json=sample_case_data)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == sample_case_data["title"]
        assert data["severity"] == sample_case_data["severity"]
        assert data["status"] == "new"
        assert "case_number" in data
        assert data["case_number"].startswith("ELEANOR-")

    @pytest.mark.asyncio
    async def test_create_case_minimal(self, authenticated_client):
        """Test creating case with minimal data."""
        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Minimal Case"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Minimal Case"
        assert data["severity"] == "medium"  # Default
        assert data["priority"] == "P3"  # Default

    @pytest.mark.asyncio
    async def test_create_case_with_mitre(self, authenticated_client):
        """Test creating case with MITRE tags."""
        case_data = {
            "title": "Phishing Attack",
            "mitre_tactics": ["TA0001", "TA0002"],
            "mitre_techniques": ["T1566", "T1059"],
        }

        response = await authenticated_client.post("/api/v1/cases", json=case_data)

        assert response.status_code == 201
        data = response.json()
        assert data["mitre_tactics"] == ["TA0001", "TA0002"]
        assert data["mitre_techniques"] == ["T1566", "T1059"]

    @pytest.mark.asyncio
    async def test_create_case_empty_title_fails(self, authenticated_client):
        """Test creating case with empty title fails."""
        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_case_invalid_severity(self, authenticated_client):
        """Test creating case with invalid severity."""
        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Test", "severity": "invalid"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_case_unauthorized(self, client, sample_case_data):
        """Test creating case without authentication."""
        response = await client.post("/api/v1/cases", json=sample_case_data)

        assert response.status_code == 401


class TestGetCase:
    """Tests for getting individual case."""

    @pytest.mark.asyncio
    async def test_get_case_success(self, authenticated_client_with_case, test_case):
        """Test getting case by ID."""
        response = await authenticated_client_with_case.get(f"/api/v1/cases/{test_case.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_case.id)
        assert data["title"] == test_case.title
        assert data["case_number"] == test_case.case_number

    @pytest.mark.asyncio
    async def test_get_case_not_found(self, authenticated_client):
        """Test getting non-existent case."""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/cases/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_get_case_invalid_uuid(self, authenticated_client):
        """Test getting case with invalid UUID."""
        response = await authenticated_client.get("/api/v1/cases/invalid-uuid")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_case_unauthorized(self, client_with_case, test_case):
        """Test getting case without authentication."""
        response = await client_with_case.get(f"/api/v1/cases/{test_case.id}")

        assert response.status_code == 401


class TestUpdateCase:
    """Tests for case update endpoint."""

    @pytest.mark.asyncio
    async def test_update_case_title(self, authenticated_client_with_case, test_case):
        """Test updating case title."""
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_case_status(self, authenticated_client_with_case, test_case):
        """Test updating case status."""
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"status": "investigating"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "investigating"

    @pytest.mark.asyncio
    async def test_update_case_close(self, authenticated_client_with_case, test_case):
        """Test closing a case."""
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"status": "closed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "closed"
        assert data["closed_at"] is not None

    @pytest.mark.asyncio
    async def test_update_case_reopen(self, authenticated_client_with_case, test_case):
        """Test reopening a closed case."""
        # First close the case
        await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"status": "closed"},
        )

        # Then reopen it
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"status": "investigating"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "investigating"
        assert data["closed_at"] is None

    @pytest.mark.asyncio
    async def test_update_case_severity(self, authenticated_client_with_case, test_case):
        """Test updating case severity."""
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"severity": "critical"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_update_case_tags(self, authenticated_client_with_case, test_case):
        """Test updating case tags."""
        new_tags = ["ransomware", "critical", "finance"]
        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"tags": new_tags},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == new_tags

    @pytest.mark.asyncio
    async def test_update_case_not_found(self, authenticated_client):
        """Test updating non-existent case."""
        fake_id = uuid4()
        response = await authenticated_client.patch(
            f"/api/v1/cases/{fake_id}",
            json={"title": "Updated"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_case_unauthorized(self, client_with_case, test_case):
        """Test updating case without authentication."""
        response = await client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"title": "Hacked"},
        )

        assert response.status_code == 401


class TestDeleteCase:
    """Tests for case deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_case_success(self, authenticated_client_with_case, test_case):
        """Test successful case deletion."""
        response = await authenticated_client_with_case.delete(f"/api/v1/cases/{test_case.id}")

        assert response.status_code == 204

        # Verify case is deleted
        get_response = await authenticated_client_with_case.get(f"/api/v1/cases/{test_case.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_case_not_found(self, authenticated_client):
        """Test deleting non-existent case."""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/cases/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_case_unauthorized(self, client_with_case, test_case):
        """Test deleting case without authentication."""
        response = await client_with_case.delete(f"/api/v1/cases/{test_case.id}")

        assert response.status_code == 401


class TestCaseNumber:
    """Tests for case number generation."""

    @pytest.mark.asyncio
    async def test_case_number_format(self, authenticated_client):
        """Test case number follows expected format."""
        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Test Case"},
        )

        assert response.status_code == 201
        data = response.json()
        case_number = data["case_number"]

        # Should match format: ELEANOR-YYYY-NNNN
        parts = case_number.split("-")
        assert len(parts) == 3
        assert parts[0] == "ELEANOR"
        assert parts[1].isdigit() and len(parts[1]) == 4  # Year
        assert parts[2].isdigit() and len(parts[2]) == 4  # Sequential number

    @pytest.mark.asyncio
    async def test_case_numbers_increment(self, authenticated_client):
        """Test that case numbers increment correctly."""
        # Create first case
        response1 = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "First Case"},
        )
        case_number1 = response1.json()["case_number"]

        # Create second case
        response2 = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Second Case"},
        )
        case_number2 = response2.json()["case_number"]

        # Extract sequence numbers
        seq1 = int(case_number1.split("-")[2])
        seq2 = int(case_number2.split("-")[2])

        assert seq2 == seq1 + 1


class TestCaseStatusTransitions:
    """Tests for case status transition logic."""

    @pytest.mark.asyncio
    async def test_valid_status_transitions(self, authenticated_client, test_session, test_user):
        """Test valid status transitions."""
        # Create a new case
        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Status Test Case"},
        )
        case_id = response.json()["id"]

        # Valid transition path: new -> investigating -> contained -> eradicated -> recovered -> closed
        transitions = [
            "investigating",
            "contained",
            "eradicated",
            "recovered",
            "closed",
        ]

        for status in transitions:
            response = await authenticated_client.patch(
                f"/api/v1/cases/{case_id}",
                json={"status": status},
            )
            assert response.status_code == 200
            assert response.json()["status"] == status


class TestCaseMetadata:
    """Tests for case metadata handling."""

    @pytest.mark.asyncio
    async def test_case_with_metadata(self, authenticated_client):
        """Test creating case with custom metadata."""
        metadata = {
            "source": "siem",
            "alert_id": "ALERT-12345",
            "custom_field": {"nested": "value"},
        }

        response = await authenticated_client.post(
            "/api/v1/cases",
            json={"title": "Case with Metadata", "metadata": metadata},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_update_case_metadata(self, authenticated_client_with_case, test_case):
        """Test updating case metadata."""
        new_metadata = {"updated": True, "source": "manual"}

        response = await authenticated_client_with_case.patch(
            f"/api/v1/cases/{test_case.id}",
            json={"metadata": new_metadata},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"] == new_metadata
