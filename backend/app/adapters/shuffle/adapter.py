"""Shuffle adapter implementation.

Provides integration with Shuffle SOAR for:
- Workflow execution and monitoring
- Approval management
- Response action automation

Shuffle API: https://shuffler.io/docs/API
"""

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    ApprovalRequest,
    SOARAdapter,
    Workflow,
    WorkflowExecution,
)
from app.adapters.shuffle.schemas import (
    ShuffleExecution,
    ShuffleWorkflow,
)

logger = logging.getLogger(__name__)


class ShuffleAdapter(SOARAdapter):
    """Adapter for Shuffle SOAR platform."""

    name = "shuffle"
    description = "Shuffle SOAR workflow automation"

    # Common workflow IDs for response actions
    # These should be configured per deployment
    WORKFLOW_HOST_ISOLATION = "host_isolation"
    WORKFLOW_BLOCK_IP = "block_ip"
    WORKFLOW_DISABLE_USER = "disable_user"
    WORKFLOW_COLLECT_EVIDENCE = "collect_evidence"

    def __init__(self, config: AdapterConfig):
        """Initialize Shuffle adapter."""
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._version: str | None = None
        self._org_id: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url.rstrip("/"),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make API request to Shuffle."""
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()

        # Handle empty responses
        if not response.content:
            return {}

        return response.json()

    async def health_check(self) -> AdapterHealth:
        """Check Shuffle connectivity."""
        try:
            # Get health status
            result = await self._request("GET", "/api/v1/health")
            self._status = AdapterStatus.CONNECTED

            # Try to get org info
            try:
                org_result = await self._request("GET", "/api/v1/orgs")
                if org_result and isinstance(org_result, list) and org_result:
                    self._org_id = org_result[0].get("id")
            except Exception:
                pass

            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                version=result.get("version", "unknown"),
                message="Connected to Shuffle",
                details={"org_id": self._org_id},
            )
        except httpx.HTTPError as e:
            logger.error("Shuffle health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"HTTP error: {e}",
            )
        except Exception as e:
            logger.error("Shuffle health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized)."""
        return {
            "url": self.config.url,
            "verify_ssl": self.config.verify_ssl,
            "has_api_key": bool(self.config.api_key),
            "org_id": self._org_id,
        }

    def _shuffle_workflow_to_workflow(
        self,
        shuffle_wf: ShuffleWorkflow,
    ) -> Workflow:
        """Convert Shuffle workflow to our Workflow model."""
        return Workflow(
            workflow_id=shuffle_wf.id,
            name=shuffle_wf.name,
            description=shuffle_wf.description,
            category=shuffle_wf.tags[0] if shuffle_wf.tags else None,
            triggers=shuffle_wf.trigger_types,
            is_active=shuffle_wf.status == "production",
            parameters=[
                {"name": variable.get("name"), "type": variable.get("type", "string")}
                for variable in shuffle_wf.workflow_variables
            ],
            created_at=shuffle_wf.created,
            updated_at=shuffle_wf.edited,
            metadata={
                "action_count": shuffle_wf.action_count,
                "public": shuffle_wf.public,
                "is_valid": shuffle_wf.is_valid,
            },
        )

    def _shuffle_execution_to_execution(
        self,
        shuffle_exec: ShuffleExecution,
        workflow_name: str = "",
    ) -> WorkflowExecution:
        """Convert Shuffle execution to our WorkflowExecution model."""
        # Map Shuffle status to our status
        status_map = {
            "EXECUTING": "running",
            "FINISHED": "completed",
            "ABORTED": "failed",
            "WAITING": "waiting_approval",
        }

        return WorkflowExecution(
            execution_id=shuffle_exec.execution_id,
            workflow_id=shuffle_exec.workflow_id,
            workflow_name=workflow_name,
            status=status_map.get(shuffle_exec.status, "pending"),
            started_at=shuffle_exec.started_at,
            completed_at=shuffle_exec.completed_at if shuffle_exec.is_finished else None,
            parameters=(
                json.loads(shuffle_exec.execution_argument)
                if shuffle_exec.execution_argument
                else {}
            ),
            results={"output": shuffle_exec.result} if shuffle_exec.result else {},
            error=shuffle_exec.result if shuffle_exec.status == "ABORTED" else None,
        )

    # =========================================================================
    # Workflow Management
    # =========================================================================

    async def list_workflows(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[Workflow]:
        """List available workflows."""
        result = await self._request("GET", "/api/v1/workflows")

        # Shuffle returns a list directly
        workflows_data = result if isinstance(result, list) else []

        workflows = []
        for wf_data in workflows_data:
            shuffle_wf = ShuffleWorkflow(**wf_data)

            # Filter by category/tag
            if category and category.lower() not in [t.lower() for t in shuffle_wf.tags]:
                continue

            # Filter by active status
            if active_only and shuffle_wf.status != "production":
                continue

            workflows.append(self._shuffle_workflow_to_workflow(shuffle_wf))

        return workflows

    async def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get workflow details."""
        try:
            result = await self._request("GET", f"/api/v1/workflows/{workflow_id}")
            shuffle_wf = ShuffleWorkflow(**result)
            return self._shuffle_workflow_to_workflow(shuffle_wf)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def trigger_workflow(
        self,
        workflow_id: str,
        parameters: dict[str, Any] | None = None,
        triggered_by: str | None = None,
    ) -> WorkflowExecution:
        """Trigger a workflow execution."""
        # Get workflow name for reference
        workflow = await self.get_workflow(workflow_id)
        workflow_name = workflow.name if workflow else workflow_id

        # Build execution payload
        payload = {
            "execution_argument": json.dumps(parameters or {}),
            "execution_source": "eleanor",
        }

        if triggered_by:
            payload["execution_source"] = f"eleanor:{triggered_by}"

        result = await self._request(
            "POST",
            f"/api/v1/workflows/{workflow_id}/execute",
            json=payload,
        )

        execution_id = result.get("execution_id", "")

        return WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status="pending",
            started_at=datetime.utcnow(),
            triggered_by=triggered_by,
            parameters=parameters or {},
        )

    async def get_execution_status(
        self,
        execution_id: str,
    ) -> WorkflowExecution:
        """Get workflow execution status."""
        result = await self._request(
            "GET",
            f"/api/v1/workflows/executions/{execution_id}",
        )
        shuffle_exec = ShuffleExecution(**result)

        # Get workflow name
        workflow = await self.get_workflow(shuffle_exec.workflow_id)
        workflow_name = workflow.name if workflow else shuffle_exec.workflow_id

        return self._shuffle_execution_to_execution(shuffle_exec, workflow_name)

    async def list_executions(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowExecution]:
        """List workflow executions."""
        if workflow_id:
            result = await self._request(
                "GET",
                f"/api/v1/workflows/{workflow_id}/executions",
            )
        else:
            result = await self._request("GET", "/api/v1/workflows/executions")

        # Filter by status if specified
        executions_data = result if isinstance(result, list) else []

        # Build a cache of workflow names
        workflow_names: dict[str, str] = {}

        executions = []
        for exec_data in executions_data[:limit]:
            shuffle_exec = ShuffleExecution(**exec_data)

            # Status filter
            if status:
                status_map = {
                    "running": "EXECUTING",
                    "completed": "FINISHED",
                    "failed": "ABORTED",
                    "waiting_approval": "WAITING",
                }
                if shuffle_exec.status != status_map.get(status, status):
                    continue

            # Get workflow name (cached)
            wf_id = shuffle_exec.workflow_id
            if wf_id not in workflow_names:
                workflow = await self.get_workflow(wf_id)
                workflow_names[wf_id] = workflow.name if workflow else wf_id

            executions.append(
                self._shuffle_execution_to_execution(
                    shuffle_exec,
                    workflow_names[wf_id],
                )
            )

        return executions

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running workflow execution."""
        try:
            await self._request(
                "GET",  # Shuffle uses GET for abort
                f"/api/v1/workflows/executions/{execution_id}/abort",
            )
            return True
        except Exception as e:
            logger.error("Failed to cancel execution %s: %s", execution_id, e)
            return False

    # =========================================================================
    # Approval Management
    # =========================================================================

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        """List pending approval requests.

        Note: Shuffle uses "user input" nodes for approvals.
        This queries executions that are in WAITING status.
        """
        result = await self._request("GET", "/api/v1/workflows/executions")
        executions_data = result if isinstance(result, list) else []

        approvals = []
        for exec_data in executions_data:
            shuffle_exec = ShuffleExecution(**exec_data)
            if shuffle_exec.status == "WAITING":
                # Get workflow details
                workflow = await self.get_workflow(shuffle_exec.workflow_id)
                workflow_name = workflow.name if workflow else shuffle_exec.workflow_id

                approvals.append(
                    ApprovalRequest(
                        approval_id=shuffle_exec.execution_id,
                        execution_id=shuffle_exec.execution_id,
                        workflow_name=workflow_name,
                        action="User Input Required",
                        description=f"Workflow '{workflow_name}' is waiting for input",
                        requested_at=shuffle_exec.started_at or datetime.utcnow(),
                        parameters=(
                            json.loads(shuffle_exec.execution_argument)
                            if shuffle_exec.execution_argument
                            else {}
                        ),
                    )
                )

        return approvals

    async def approve_request(
        self,
        approval_id: str,
        approved_by: str,
        comment: str | None = None,
    ) -> bool:
        """Approve a waiting execution.

        Shuffle approvals work by continuing execution with provided input.
        """
        try:
            await self._request(
                "POST",
                f"/api/v1/workflows/executions/{approval_id}/continue",
                json={
                    "authorization": "",
                    "result": json.dumps(
                        {
                            "approved": True,
                            "approved_by": approved_by,
                            "comment": comment or "",
                        }
                    ),
                },
            )
            return True
        except Exception as e:
            logger.error("Failed to approve %s: %s", approval_id, e)
            return False

    async def deny_request(
        self,
        approval_id: str,
        denied_by: str,
        reason: str | None = None,
    ) -> bool:
        """Deny a waiting execution."""
        try:
            # Abort the execution
            await self._request(
                "GET",
                f"/api/v1/workflows/executions/{approval_id}/abort",
            )
            return True
        except Exception as e:
            logger.error("Failed to deny %s: %s", approval_id, e)
            return False

    # =========================================================================
    # Response Action Shortcuts
    # =========================================================================

    async def isolate_host_workflow(
        self,
        hostname: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger host isolation workflow."""
        # Try to find the host isolation workflow by name/tag
        workflows = await self.list_workflows(category="isolation")
        if workflows:
            workflow_id = workflows[0].workflow_id
        else:
            # Fall back to configured ID
            workflow_id = self.WORKFLOW_HOST_ISOLATION

        return await self.trigger_workflow(
            workflow_id,
            parameters={
                "hostname": hostname,
                "case_id": case_id or "",
                "action": "isolate",
            },
            triggered_by="eleanor",
        )

    async def block_ip_workflow(
        self,
        ip_address: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger IP blocking workflow."""
        workflows = await self.list_workflows(category="firewall")
        if workflows:
            workflow_id = workflows[0].workflow_id
        else:
            workflow_id = self.WORKFLOW_BLOCK_IP

        return await self.trigger_workflow(
            workflow_id,
            parameters={
                "ip_address": ip_address,
                "case_id": case_id or "",
                "action": "block",
            },
            triggered_by="eleanor",
        )

    async def disable_user_workflow(
        self,
        username: str,
        case_id: str | None = None,
    ) -> WorkflowExecution:
        """Trigger user disable workflow."""
        workflows = await self.list_workflows(category="identity")
        if workflows:
            workflow_id = workflows[0].workflow_id
        else:
            workflow_id = self.WORKFLOW_DISABLE_USER

        return await self.trigger_workflow(
            workflow_id,
            parameters={
                "username": username,
                "case_id": case_id or "",
                "action": "disable",
            },
            triggered_by="eleanor",
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
