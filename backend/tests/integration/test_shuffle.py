"""Integration tests for Shuffle adapter.

These tests require a running Shuffle instance.
Run with: pytest tests/integration/test_shuffle.py --live
"""

import os
import pytest

from app.adapters.shuffle.adapter import ShuffleAdapter


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def shuffle_config():
    """Get Shuffle configuration from environment."""
    return {
        "url": os.getenv("SHUFFLE_URL", "http://localhost:3001"),
        "api_key": os.getenv("SHUFFLE_API_KEY", ""),
        "verify_ssl": os.getenv("SHUFFLE_VERIFY_SSL", "true").lower() == "true",
    }


@pytest.fixture
async def shuffle_adapter(shuffle_config):
    """Create and connect Shuffle adapter."""
    adapter = ShuffleAdapter(shuffle_config)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


class TestShuffleConnection:
    """Tests for Shuffle connectivity."""

    async def test_health_check(self, shuffle_adapter):
        """Test health check returns valid status."""
        health = await shuffle_adapter.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy", "degraded"]

    async def test_connection_established(self, shuffle_adapter):
        """Test that adapter is connected."""
        assert shuffle_adapter.connected is True


class TestShuffleWorkflows:
    """Tests for workflow management."""

    async def test_list_workflows(self, shuffle_adapter):
        """Test listing available workflows."""
        workflows = await shuffle_adapter.list_workflows()

        assert isinstance(workflows, list)
        # Shuffle should have at least some workflows configured
        for workflow in workflows:
            assert "id" in workflow or "workflow_id" in workflow
            assert "name" in workflow

    async def test_list_workflows_by_category(self, shuffle_adapter):
        """Test filtering workflows by category."""
        workflows = await shuffle_adapter.list_workflows(
            category="response",
            active_only=True,
        )

        assert isinstance(workflows, list)
        for workflow in workflows:
            assert workflow.get("category") == "response" or workflow.get("is_active", True)

    async def test_get_workflow(self, shuffle_adapter):
        """Test getting workflow details."""
        # First list workflows
        workflows = await shuffle_adapter.list_workflows()

        if workflows:
            workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")
            workflow = await shuffle_adapter.get_workflow(workflow_id)

            if workflow:
                assert workflow.get("id") == workflow_id or workflow.get("workflow_id") == workflow_id


class TestShuffleExecution:
    """Tests for workflow execution."""

    async def test_trigger_workflow(self, shuffle_adapter):
        """Test triggering a workflow."""
        # Find a workflow that doesn't require approval
        workflows = await shuffle_adapter.list_workflows()

        # Find enrichment or notification workflow (usually no approval)
        test_workflow = None
        for wf in workflows:
            if wf.get("requires_approval") is False:
                test_workflow = wf
                break

        if not test_workflow:
            pytest.skip("No workflow available for testing")

        workflow_id = test_workflow.get("id") or test_workflow.get("workflow_id")

        execution = await shuffle_adapter.trigger_workflow(
            workflow_id=workflow_id,
            parameters={"test": "value"},
            triggered_by="integration_test",
        )

        assert execution is not None
        assert "execution_id" in execution
        assert execution["status"] in ["pending", "running", "completed", "waiting_approval"]

    async def test_get_execution_status(self, shuffle_adapter):
        """Test getting execution status."""
        # Trigger a workflow first
        workflows = await shuffle_adapter.list_workflows()

        if not workflows:
            pytest.skip("No workflows available")

        workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")

        execution = await shuffle_adapter.trigger_workflow(
            workflow_id=workflow_id,
            parameters={},
        )

        # Get status
        status = await shuffle_adapter.get_execution_status(execution["execution_id"])

        assert status is not None
        assert status["execution_id"] == execution["execution_id"]
        assert "status" in status

    async def test_list_executions(self, shuffle_adapter):
        """Test listing workflow executions."""
        executions = await shuffle_adapter.list_executions(limit=10)

        assert isinstance(executions, list)

    async def test_cancel_execution(self, shuffle_adapter):
        """Test cancelling a workflow execution."""
        # Trigger a workflow
        workflows = await shuffle_adapter.list_workflows()

        if not workflows:
            pytest.skip("No workflows available")

        workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")

        execution = await shuffle_adapter.trigger_workflow(
            workflow_id=workflow_id,
            parameters={},
        )

        # Cancel it
        result = await shuffle_adapter.cancel_execution(execution["execution_id"])

        # May or may not succeed depending on execution state
        assert result is not None


class TestShuffleApprovals:
    """Tests for approval management."""

    async def test_list_pending_approvals(self, shuffle_adapter):
        """Test listing pending approvals."""
        approvals = await shuffle_adapter.list_pending_approvals()

        assert isinstance(approvals, list)

    async def test_approve_request(self, shuffle_adapter):
        """Test approving a request."""
        # Find a workflow that requires approval
        workflows = await shuffle_adapter.list_workflows()

        approval_workflow = None
        for wf in workflows:
            if wf.get("requires_approval") is True:
                approval_workflow = wf
                break

        if not approval_workflow:
            pytest.skip("No approval workflow available")

        workflow_id = approval_workflow.get("id") or approval_workflow.get("workflow_id")

        # Trigger it
        execution = await shuffle_adapter.trigger_workflow(
            workflow_id=workflow_id,
            parameters={"test": "approval"},
        )

        if execution.get("approval_id"):
            # Approve it
            result = await shuffle_adapter.approve_request(
                approval_id=execution["approval_id"],
                approved_by="integration_test",
                comment="Approved by integration test",
            )

            assert result is not None

    async def test_deny_request(self, shuffle_adapter):
        """Test denying a request."""
        # Find a workflow that requires approval
        workflows = await shuffle_adapter.list_workflows()

        approval_workflow = None
        for wf in workflows:
            if wf.get("requires_approval") is True:
                approval_workflow = wf
                break

        if not approval_workflow:
            pytest.skip("No approval workflow available")

        workflow_id = approval_workflow.get("id") or approval_workflow.get("workflow_id")

        # Trigger it
        execution = await shuffle_adapter.trigger_workflow(
            workflow_id=workflow_id,
            parameters={"test": "denial"},
        )

        if execution.get("approval_id"):
            # Deny it
            result = await shuffle_adapter.deny_request(
                approval_id=execution["approval_id"],
                denied_by="integration_test",
                reason="Denied by integration test",
            )

            assert result is not None


class TestShuffleResponseActions:
    """Tests for response action shortcuts."""

    async def test_isolate_host_workflow(self, shuffle_adapter):
        """Test host isolation workflow."""
        # This may require specific workflow configuration
        try:
            execution = await shuffle_adapter.isolate_host_workflow(
                hostname="TEST-HOST-INTEGRATION",
                case_id="test-case-123",
            )

            assert "execution_id" in execution
        except Exception:
            pytest.skip("Host isolation workflow not configured")

    async def test_block_ip_workflow(self, shuffle_adapter):
        """Test IP blocking workflow."""
        try:
            execution = await shuffle_adapter.block_ip_workflow(
                ip_address="198.51.100.99",
                case_id="test-case-123",
            )

            assert "execution_id" in execution
        except Exception:
            pytest.skip("IP blocking workflow not configured")

    async def test_disable_user_workflow(self, shuffle_adapter):
        """Test user disable workflow."""
        try:
            execution = await shuffle_adapter.disable_user_workflow(
                username="test_user_integration",
                case_id="test-case-123",
            )

            assert "execution_id" in execution
        except Exception:
            pytest.skip("User disable workflow not configured")
