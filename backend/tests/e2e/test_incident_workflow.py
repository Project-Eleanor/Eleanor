"""End-to-end tests for incident investigation workflow.

Tests the complete lifecycle: Case creation → Investigation → Closure
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4


pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestIncidentWorkflow:
    """Tests for complete incident investigation workflow."""

    async def test_complete_incident_lifecycle(self, authenticated_client, test_user):
        """Test complete incident from creation to closure.

        Workflow:
        1. Create case from alert
        2. Update case status to investigating
        3. Add evidence
        4. Add timeline events
        5. Update MITRE tags
        6. Close case with resolution
        """
        # Step 1: Create case from simulated alert
        case_response = await authenticated_client.post(
            "/api/v1/cases",
            json={
                "title": "Suspicious PowerShell Activity on WORKSTATION-001",
                "description": "Alert triggered for encoded PowerShell command execution",
                "severity": "high",
                "priority": "P2",
                "tags": ["alert-triggered", "powershell"],
                "metadata": {
                    "alert_id": "ALERT-12345",
                    "source": "SIEM",
                },
            },
        )

        assert case_response.status_code == 201
        case = case_response.json()
        case_id = case["id"]

        assert case["status"] == "new"
        assert case["severity"] == "high"

        # Step 2: Begin investigation - update status
        update_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "investigating"},
        )

        assert update_response.status_code == 200
        assert update_response.json()["status"] == "investigating"

        # Step 3: Add MITRE ATT&CK tags based on investigation
        mitre_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={
                "mitre_tactics": ["TA0002", "TA0005"],
                "mitre_techniques": ["T1059.001", "T1027"],
            },
        )

        assert mitre_response.status_code == 200
        assert "T1059.001" in mitre_response.json()["mitre_techniques"]

        # Step 4: Case has been contained
        contained_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "contained"},
        )

        assert contained_response.status_code == 200
        assert contained_response.json()["status"] == "contained"

        # Step 5: Eradicate threat
        eradicated_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "eradicated"},
        )

        assert eradicated_response.status_code == 200

        # Step 6: Systems recovered
        recovered_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "recovered"},
        )

        assert recovered_response.status_code == 200

        # Step 7: Close case with resolution
        close_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={
                "status": "closed",
                "metadata": {
                    "alert_id": "ALERT-12345",
                    "source": "SIEM",
                    "resolution": "Malware removed, system reimaged",
                    "root_cause": "Phishing email with malicious attachment",
                    "lessons_learned": "Need better email filtering",
                },
            },
        )

        assert close_response.status_code == 200
        closed_case = close_response.json()
        assert closed_case["status"] == "closed"
        assert closed_case["closed_at"] is not None

        # Verify final case state
        final_response = await authenticated_client.get(f"/api/v1/cases/{case_id}")
        assert final_response.status_code == 200
        final_case = final_response.json()

        assert final_case["status"] == "closed"
        assert final_case["severity"] == "high"
        assert "T1059.001" in final_case["mitre_techniques"]

    async def test_case_assignment_workflow(self, authenticated_client, admin_client, test_user, admin_user):
        """Test case assignment workflow.

        Workflow:
        1. Admin creates case
        2. Admin assigns to analyst
        3. Analyst investigates
        4. Analyst closes case
        """
        # Admin creates case
        create_response = await admin_client.post(
            "/api/v1/cases",
            json={
                "title": "Case for Assignment Test",
                "severity": "medium",
            },
        )

        assert create_response.status_code == 201
        case_id = create_response.json()["id"]

        # Admin assigns to analyst (test_user)
        assign_response = await admin_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"assignee_id": str(test_user.id)},
        )

        assert assign_response.status_code == 200
        assert assign_response.json()["assignee_id"] == str(test_user.id)

        # Analyst (test_user) investigates
        investigate_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "investigating"},
        )

        assert investigate_response.status_code == 200

        # Analyst closes case
        close_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={"status": "closed"},
        )

        assert close_response.status_code == 200

    async def test_case_escalation_workflow(self, authenticated_client, admin_client):
        """Test case escalation workflow.

        Workflow:
        1. Create low severity case
        2. Investigation reveals higher impact
        3. Escalate severity and priority
        """
        # Create initial low severity case
        create_response = await authenticated_client.post(
            "/api/v1/cases",
            json={
                "title": "Minor Suspicious Activity",
                "severity": "low",
                "priority": "P4",
            },
        )

        case_id = create_response.json()["id"]

        # Investigation reveals ransomware indicators
        escalate_response = await authenticated_client.patch(
            f"/api/v1/cases/{case_id}",
            json={
                "title": "ESCALATED: Ransomware Incident",
                "severity": "critical",
                "priority": "P1",
                "tags": ["ransomware", "escalated"],
            },
        )

        assert escalate_response.status_code == 200
        escalated_case = escalate_response.json()
        assert escalated_case["severity"] == "critical"
        assert escalated_case["priority"] == "P1"
        assert "escalated" in escalated_case["tags"]


class TestMultiCaseManagement:
    """Tests for managing multiple related cases."""

    async def test_related_cases_workflow(self, authenticated_client):
        """Test managing multiple related cases.

        Workflow:
        1. Create parent incident case
        2. Create child cases for individual hosts
        3. Track across all cases
        """
        # Create parent case
        parent_response = await authenticated_client.post(
            "/api/v1/cases",
            json={
                "title": "Organization-wide Phishing Campaign",
                "severity": "high",
                "tags": ["phishing", "campaign", "parent"],
            },
        )

        parent_id = parent_response.json()["id"]

        # Create child cases for individual affected hosts
        child_cases = []
        hosts = ["WORKSTATION-001", "WORKSTATION-002", "SERVER-001"]

        for host in hosts:
            child_response = await authenticated_client.post(
                "/api/v1/cases",
                json={
                    "title": f"Phishing Compromise - {host}",
                    "severity": "medium",
                    "tags": ["phishing", "child"],
                    "metadata": {"parent_case_id": parent_id, "affected_host": host},
                },
            )

            assert child_response.status_code == 201
            child_cases.append(child_response.json())

        # Verify we have all cases
        list_response = await authenticated_client.get(
            "/api/v1/cases?search=phishing"
        )

        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 4  # Parent + 3 children

        # Close all child cases
        for child in child_cases:
            await authenticated_client.patch(
                f"/api/v1/cases/{child['id']}",
                json={"status": "closed"},
            )

        # Close parent case
        close_response = await authenticated_client.patch(
            f"/api/v1/cases/{parent_id}",
            json={"status": "closed"},
        )

        assert close_response.status_code == 200


class TestCaseFiltering:
    """Tests for case filtering and search in realistic scenarios."""

    async def test_analyst_daily_workflow(self, authenticated_client, test_user):
        """Test typical analyst daily case management.

        Workflow:
        1. View my assigned cases
        2. Filter by status (investigating)
        3. Filter by severity (critical/high)
        """
        # Create various cases
        severities = ["critical", "high", "medium", "low"]
        for i, sev in enumerate(severities):
            await authenticated_client.post(
                "/api/v1/cases",
                json={
                    "title": f"{sev.title()} Severity Case {i}",
                    "severity": sev,
                    "status": "new" if i % 2 == 0 else "investigating",
                },
            )

        # Filter investigating cases
        investigating_response = await authenticated_client.get(
            "/api/v1/cases?status=investigating"
        )

        assert investigating_response.status_code == 200
        for case in investigating_response.json()["items"]:
            assert case["status"] == "investigating"

        # Filter high severity and above
        critical_response = await authenticated_client.get(
            "/api/v1/cases?severity=critical"
        )

        assert critical_response.status_code == 200
        for case in critical_response.json()["items"]:
            assert case["severity"] == "critical"
