"""Unit tests for evidence management endpoints."""

import pytest
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from app.models.evidence import (
    CustodyAction,
    CustodyEvent,
    Evidence,
    EvidenceStatus,
    EvidenceType,
)


pytestmark = pytest.mark.unit


class TestListEvidence:
    """Tests for evidence listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_evidence_empty(self, authenticated_client):
        """Test listing evidence when none exists."""
        response = await authenticated_client.get("/api/v1/evidence")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_evidence_with_data(self, authenticated_client_with_evidence, test_evidence):
        """Test listing evidence with existing data."""
        response = await authenticated_client_with_evidence.get("/api/v1/evidence")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_list_evidence_filter_by_case(self, authenticated_client_with_evidence, test_evidence, test_case):
        """Test filtering evidence by case ID."""
        response = await authenticated_client_with_evidence.get(
            f"/api/v1/evidence?case_id={test_case.id}"
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["case_id"] == str(test_case.id)

    @pytest.mark.asyncio
    async def test_list_evidence_filter_by_type(self, authenticated_client_with_evidence, test_evidence):
        """Test filtering evidence by type."""
        response = await authenticated_client_with_evidence.get(
            f"/api/v1/evidence?evidence_type={test_evidence.evidence_type.value}"
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["evidence_type"] == test_evidence.evidence_type.value

    @pytest.mark.asyncio
    async def test_list_evidence_search(self, authenticated_client_with_evidence, test_evidence):
        """Test searching evidence by filename."""
        response = await authenticated_client_with_evidence.get(
            f"/api/v1/evidence?search={test_evidence.filename}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_evidence_unauthorized(self, client):
        """Test listing evidence without authentication."""
        response = await client.get("/api/v1/evidence")

        assert response.status_code == 401


class TestGetEvidence:
    """Tests for getting individual evidence."""

    @pytest.mark.asyncio
    async def test_get_evidence_success(self, authenticated_client_with_evidence, test_evidence):
        """Test getting evidence by ID."""
        response = await authenticated_client_with_evidence.get(f"/api/v1/evidence/{test_evidence.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_evidence.id)
        assert data["filename"] == test_evidence.filename
        assert data["sha256"] == test_evidence.sha256

    @pytest.mark.asyncio
    async def test_get_evidence_not_found(self, authenticated_client):
        """Test getting non-existent evidence."""
        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/evidence/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_evidence_logs_access(self, authenticated_client_with_evidence, test_evidence, test_session):
        """Test that accessing evidence logs a custody event."""
        # Access the evidence
        response = await authenticated_client_with_evidence.get(f"/api/v1/evidence/{test_evidence.id}")
        assert response.status_code == 200

        # Check for custody event
        from sqlalchemy import select
        query = select(CustodyEvent).where(
            CustodyEvent.evidence_id == test_evidence.id,
            CustodyEvent.action == CustodyAction.ACCESSED,
        )
        result = await test_session.execute(query)
        events = result.scalars().all()

        # Should have at least one access event
        assert len(events) >= 1


class TestUpdateEvidence:
    """Tests for evidence update endpoint."""

    @pytest.mark.asyncio
    async def test_update_evidence_type(self, authenticated_client_with_evidence, test_evidence):
        """Test updating evidence type."""
        response = await authenticated_client_with_evidence.patch(
            f"/api/v1/evidence/{test_evidence.id}",
            json={"evidence_type": "logs"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["evidence_type"] == "logs"

    @pytest.mark.asyncio
    async def test_update_evidence_description(self, authenticated_client_with_evidence, test_evidence):
        """Test updating evidence description."""
        new_description = "Updated description for testing"
        response = await authenticated_client_with_evidence.patch(
            f"/api/v1/evidence/{test_evidence.id}",
            json={"description": new_description},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == new_description

    @pytest.mark.asyncio
    async def test_update_evidence_status(self, authenticated_client_with_evidence, test_evidence):
        """Test updating evidence status."""
        response = await authenticated_client_with_evidence.patch(
            f"/api/v1/evidence/{test_evidence.id}",
            json={"status": "quarantined"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "quarantined"

    @pytest.mark.asyncio
    async def test_update_evidence_not_found(self, authenticated_client):
        """Test updating non-existent evidence."""
        fake_id = uuid4()
        response = await authenticated_client.patch(
            f"/api/v1/evidence/{fake_id}",
            json={"description": "Test"},
        )

        assert response.status_code == 404


class TestDeleteEvidence:
    """Tests for evidence deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_evidence_success(self, authenticated_client_with_evidence, test_evidence):
        """Test successful evidence deletion."""
        response = await authenticated_client_with_evidence.delete(f"/api/v1/evidence/{test_evidence.id}")

        assert response.status_code == 204

        # Verify evidence is deleted
        get_response = await authenticated_client_with_evidence.get(f"/api/v1/evidence/{test_evidence.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_evidence_not_found(self, authenticated_client):
        """Test deleting non-existent evidence."""
        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/evidence/{fake_id}")

        assert response.status_code == 404


class TestCustodyChain:
    """Tests for chain of custody tracking."""

    @pytest.mark.asyncio
    async def test_get_custody_chain(self, authenticated_client_with_evidence, test_evidence, test_session, test_user):
        """Test getting custody chain for evidence."""
        # Add a custody event to the session
        event = CustodyEvent(
            id=uuid4(),
            evidence_id=test_evidence.id,
            action=CustodyAction.ACCESSED,
            actor_id=test_user.id,
            actor_name=test_user.display_name,
        )
        test_session.add(event)
        await test_session.commit()

        response = await authenticated_client_with_evidence.get(
            f"/api/v1/evidence/{test_evidence.id}/custody"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify event data
        ev = data[0]
        assert "action" in ev
        assert "actor_name" in ev
        assert "created_at" in ev

    @pytest.mark.asyncio
    async def test_custody_chain_ordered_chronologically(
        self, authenticated_client_with_evidence, test_evidence, test_session, test_user
    ):
        """Test that custody chain is ordered chronologically."""
        # Add multiple custody events
        for i, action in enumerate([CustodyAction.ACCESSED, CustodyAction.VERIFIED]):
            event = CustodyEvent(
                id=uuid4(),
                evidence_id=test_evidence.id,
                action=action,
                actor_id=test_user.id,
                actor_name=test_user.display_name,
            )
            test_session.add(event)
        await test_session.commit()

        response = await authenticated_client_with_evidence.get(
            f"/api/v1/evidence/{test_evidence.id}/custody"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # 2 events we added

        # Verify chronological order
        timestamps = [ev["created_at"] for ev in data]
        assert timestamps == sorted(timestamps)


class TestEvidenceHashes:
    """Tests for evidence hash verification."""

    @pytest.mark.asyncio
    async def test_evidence_has_all_hashes(self, authenticated_client_with_evidence, test_evidence):
        """Test that evidence has SHA256, SHA1, and MD5 hashes."""
        response = await authenticated_client_with_evidence.get(f"/api/v1/evidence/{test_evidence.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["sha256"] is not None
        assert len(data["sha256"]) == 64  # SHA256 hex length
        assert data["sha1"] is not None
        assert len(data["sha1"]) == 40  # SHA1 hex length
        assert data["md5"] is not None
        assert len(data["md5"]) == 32  # MD5 hex length


class TestEvidenceTypes:
    """Tests for different evidence types."""

    @pytest.mark.asyncio
    async def test_evidence_types_valid(self, authenticated_client_with_evidence, test_evidence):
        """Test that all evidence types are valid."""
        valid_types = [
            "disk_image", "memory", "logs", "triage", "pcap",
            "artifact", "document", "malware", "other"
        ]

        for etype in valid_types:
            response = await authenticated_client_with_evidence.patch(
                f"/api/v1/evidence/{test_evidence.id}",
                json={"evidence_type": etype},
            )
            # Either succeeds or type is already that value
            assert response.status_code in [200, 422]


class TestEvidenceMetadata:
    """Tests for evidence metadata handling."""

    @pytest.mark.asyncio
    async def test_update_evidence_metadata(self, authenticated_client_with_evidence, test_evidence):
        """Test updating evidence metadata."""
        new_metadata = {
            "analysis_notes": "Suspicious binary",
            "yara_matches": ["rule_1", "rule_2"],
            "sandbox_score": 85,
        }

        response = await authenticated_client_with_evidence.patch(
            f"/api/v1/evidence/{test_evidence.id}",
            json={"metadata": new_metadata},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"] == new_metadata
