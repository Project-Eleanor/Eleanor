"""Unit tests for SOAR workflow endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks.shuffle import MockShuffleAdapter


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_soar_adapter():
    """Create mock SOAR adapter for testing."""
    return MockShuffleAdapter()


class TestListWorkflows:
    """Tests for workflow listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_workflows_success(self, authenticated_client, mock_soar_adapter):
        """Test listing available workflows."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_list_workflows_filter_by_category(self, authenticated_client, mock_soar_adapter):
        """Test filtering workflows by category."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get(
                "/api/v1/workflows/?category=response"
            )

        assert response.status_code == 200
        data = response.json()
        for workflow in data:
            assert workflow["category"] == "response"

    @pytest.mark.asyncio
    async def test_list_workflows_no_soar_adapter(self, authenticated_client):
        """Test listing workflows when SOAR adapter not configured."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = None
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/")

        assert response.status_code == 503
        # Eleanor uses custom error format with "message" instead of "detail"
        assert "No SOAR adapter configured" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_list_workflows_unauthorized(self, client):
        """Test listing workflows without authentication."""
        response = await client.get("/api/v1/workflows/")

        assert response.status_code == 401


class TestGetWorkflow:
    """Tests for getting individual workflow."""

    @pytest.mark.asyncio
    async def test_get_workflow_success(self, authenticated_client, mock_soar_adapter):
        """Test getting workflow by ID."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/wf-isolate-host")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == "wf-isolate-host"
        assert data["name"] == "Isolate Host"

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, authenticated_client, mock_soar_adapter):
        """Test getting non-existent workflow."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/nonexistent")

        assert response.status_code == 404


class TestTriggerWorkflow:
    """Tests for workflow triggering endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_workflow_success(self, authenticated_client, mock_soar_adapter):
        """Test triggering a workflow."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                "/api/v1/workflows/trigger",
                json={
                    "workflow_id": "wf-enrich-ioc",
                    "parameters": {"ioc_value": "malicious.com", "ioc_type": "domain"},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["workflow_id"] == "wf-enrich-ioc"

    @pytest.mark.asyncio
    async def test_trigger_workflow_requires_approval(self, authenticated_client, mock_soar_adapter):
        """Test triggering workflow that requires approval."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                "/api/v1/workflows/trigger",
                json={
                    "workflow_id": "wf-isolate-host",
                    "parameters": {"hostname": "WORKSTATION-001", "reason": "Compromise"},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "waiting_approval"  # Waiting for approval


class TestWorkflowExecutions:
    """Tests for workflow execution management."""

    @pytest.mark.asyncio
    async def test_list_executions(self, authenticated_client, mock_soar_adapter):
        """Test listing workflow executions."""
        # Trigger a workflow first
        await mock_soar_adapter.trigger_workflow(
            "wf-enrich-ioc",
            {"ioc_value": "test.com", "ioc_type": "domain"},
        )

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/executions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_execution_status(self, authenticated_client, mock_soar_adapter):
        """Test getting execution status."""
        # Trigger a workflow first
        execution = await mock_soar_adapter.trigger_workflow(
            "wf-enrich-ioc",
            {"ioc_value": "test.com", "ioc_type": "domain"},
        )

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get(
                f"/api/v1/workflows/executions/{execution.execution_id}"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == execution.execution_id

    @pytest.mark.asyncio
    async def test_cancel_execution(self, authenticated_client, mock_soar_adapter):
        """Test cancelling a workflow execution."""
        execution = await mock_soar_adapter.trigger_workflow(
            "wf-enrich-ioc",
            {"ioc_value": "test.com", "ioc_type": "domain"},
        )

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                f"/api/v1/workflows/executions/{execution.execution_id}/cancel"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestApprovals:
    """Tests for approval management endpoints."""

    @pytest.mark.asyncio
    async def test_list_pending_approvals(self, authenticated_client, mock_soar_adapter):
        """Test listing pending approvals."""
        # Trigger a workflow that requires approval
        await mock_soar_adapter.trigger_workflow(
            "wf-isolate-host",
            {"hostname": "TEST", "reason": "Test"},
        )

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.get("/api/v1/workflows/approvals")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_approve_request(self, authenticated_client, mock_soar_adapter):
        """Test approving a pending request."""
        # Create pending approval
        await mock_soar_adapter.trigger_workflow(
            "wf-isolate-host",
            {"hostname": "TEST", "reason": "Test"},
        )
        # Get the approval_id from the adapter's internal storage
        approval_id = list(mock_soar_adapter._approvals.keys())[0]

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                f"/api/v1/workflows/approvals/{approval_id}/approve",
                json={"comment": "Approved for testing"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "approved"

    @pytest.mark.asyncio
    async def test_deny_request(self, authenticated_client, mock_soar_adapter):
        """Test denying a pending request."""
        await mock_soar_adapter.trigger_workflow(
            "wf-isolate-host",
            {"hostname": "TEST", "reason": "Test"},
        )
        # Get the approval_id from the adapter's internal storage
        approval_id = list(mock_soar_adapter._approvals.keys())[0]

        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                f"/api/v1/workflows/approvals/{approval_id}/deny",
                json={"comment": "Not necessary"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "denied"


class TestResponseActions:
    """Tests for common response action shortcuts."""

    @pytest.mark.asyncio
    async def test_isolate_host_action(self, authenticated_client, mock_soar_adapter):
        """Test host isolation action."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                "/api/v1/workflows/actions/isolate-host",
                json={
                    "target": "WORKSTATION-001",
                    "case_id": "case-123",
                    "reason": "Suspected compromise",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "isolate" in data["workflow_name"].lower()

    @pytest.mark.asyncio
    async def test_block_ip_action(self, authenticated_client, mock_soar_adapter):
        """Test IP blocking action."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                "/api/v1/workflows/actions/block-ip",
                json={
                    "target": "198.51.100.50",
                    "case_id": "case-456",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data

    @pytest.mark.asyncio
    async def test_disable_user_action(self, authenticated_client, mock_soar_adapter):
        """Test user disable action."""
        with patch("app.api.v1.workflows.get_registry") as mock_registry:
            mock_reg_instance = MagicMock()
            mock_reg_instance.get_soar.return_value = mock_soar_adapter
            mock_registry.return_value = mock_reg_instance

            response = await authenticated_client.post(
                "/api/v1/workflows/actions/disable-user",
                json={
                    "target": "compromised_user",
                    "reason": "Account compromise",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
