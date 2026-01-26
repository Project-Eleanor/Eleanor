"""Mock Shuffle adapter for testing."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.adapters.base import ApprovalRequest, Workflow, WorkflowExecution


class MockShuffleAdapter:
    """Mock implementation of Shuffle adapter for testing."""

    def __init__(self):
        self.name = "shuffle"
        self.connected = False
        self._workflows = self._generate_sample_workflows()
        self._executions = {}
        self._approvals = {}

    def _generate_sample_workflows(self) -> dict[str, Workflow]:
        """Generate sample workflow definitions."""
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        updated_time = datetime(2024, 1, 15, tzinfo=timezone.utc)

        return {
            "wf-isolate-host": Workflow(
                workflow_id="wf-isolate-host",
                name="Isolate Host",
                description="Isolate a compromised host from the network",
                category="response",
                is_active=True,
                parameters=[
                    {"name": "hostname", "type": "string", "required": True, "description": "Target hostname"},
                    {"name": "reason", "type": "string", "required": True, "description": "Isolation reason"},
                    {"name": "case_id", "type": "string", "required": False, "description": "Associated case ID"},
                ],
                created_at=base_time,
                updated_at=updated_time,
                metadata={"requires_approval": True, "execution_count": 42},
            ),
            "wf-block-ip": Workflow(
                workflow_id="wf-block-ip",
                name="Block IP Address",
                description="Block an IP address on the perimeter firewall",
                category="response",
                is_active=True,
                parameters=[
                    {"name": "ip_address", "type": "string", "required": True, "description": "IP to block"},
                    {"name": "duration", "type": "integer", "required": False, "description": "Block duration in hours"},
                    {"name": "case_id", "type": "string", "required": False, "description": "Associated case ID"},
                ],
                created_at=base_time,
                updated_at=updated_time,
                metadata={"requires_approval": True, "execution_count": 128},
            ),
            "wf-disable-user": Workflow(
                workflow_id="wf-disable-user",
                name="Disable User Account",
                description="Disable a user account in Active Directory",
                category="response",
                is_active=True,
                parameters=[
                    {"name": "username", "type": "string", "required": True, "description": "Username to disable"},
                    {"name": "reason", "type": "string", "required": True, "description": "Disable reason"},
                ],
                created_at=base_time,
                updated_at=updated_time,
                metadata={"requires_approval": True, "execution_count": 15},
            ),
            "wf-enrich-ioc": Workflow(
                workflow_id="wf-enrich-ioc",
                name="Enrich IOC",
                description="Automatically enrich indicators with threat intelligence",
                category="enrichment",
                is_active=True,
                parameters=[
                    {"name": "ioc_value", "type": "string", "required": True, "description": "IOC value"},
                    {"name": "ioc_type", "type": "string", "required": True, "description": "IOC type"},
                ],
                created_at=base_time,
                updated_at=updated_time,
                metadata={"requires_approval": False, "execution_count": 1500},
            ),
            "wf-send-notification": Workflow(
                workflow_id="wf-send-notification",
                name="Send Notification",
                description="Send alert notification via multiple channels",
                category="notification",
                is_active=True,
                parameters=[
                    {"name": "message", "type": "string", "required": True, "description": "Notification message"},
                    {"name": "channels", "type": "array", "required": True, "description": "Notification channels"},
                    {"name": "severity", "type": "string", "required": False, "description": "Alert severity"},
                ],
                created_at=base_time,
                updated_at=updated_time,
                metadata={"requires_approval": False, "execution_count": 3200},
            ),
        }

    async def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self.connected = False

    async def health_check(self) -> dict:
        """Return mock health status."""
        return {
            "status": "healthy",
            "connected": self.connected,
            "version": "1.3.0",
            "server_url": "http://shuffle.local:3001",
            "workflows_count": len(self._workflows),
            "active_executions": len([e for e in self._executions.values() if e["status"] == "running"]),
        }

    async def list_workflows(
        self,
        category: str | None = None,
        active_only: bool = False,
    ) -> list[Workflow]:
        """Return mock workflow list."""
        workflows = list(self._workflows.values())
        if category:
            workflows = [w for w in workflows if w.category == category]
        if active_only:
            workflows = [w for w in workflows if w.is_active]
        return workflows

    async def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Return mock workflow details."""
        return self._workflows.get(workflow_id)

    async def trigger_workflow(
        self,
        workflow_id: str,
        parameters: dict,
        triggered_by: str | None = None,
    ) -> WorkflowExecution:
        """Simulate workflow execution."""
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self._workflows[workflow_id]
        execution_id = str(uuid4())
        requires_approval = workflow.metadata.get("requires_approval", False)

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            status="waiting_approval" if requires_approval else "running",
            started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by or "api",
            parameters=parameters,
        )

        # If approval required, create approval request
        if requires_approval:
            approval_id = str(uuid4())
            self._approvals[approval_id] = ApprovalRequest(
                approval_id=approval_id,
                execution_id=execution_id,
                workflow_name=workflow.name,
                action="execute",
                description=f"Execute {workflow.name}",
                requested_at=datetime.now(timezone.utc),
                requested_by=triggered_by,
                parameters=parameters,
            )

        self._executions[execution_id] = execution
        return execution

    async def get_execution_status(self, execution_id: str) -> WorkflowExecution | None:
        """Return mock execution status."""
        return self._executions.get(execution_id)

    async def list_executions(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowExecution]:
        """Return mock execution list."""
        executions = list(self._executions.values())
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        if status:
            executions = [e for e in executions if e.status == status]
        return executions[:limit]

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution. Returns True if cancelled, False otherwise."""
        if execution_id in self._executions:
            execution = self._executions[execution_id]
            if execution.status in ["pending", "running", "waiting_approval"]:
                execution.status = "cancelled"
                execution.completed_at = datetime.now(timezone.utc)
                return True
            return False  # Already completed/cancelled
        return False  # Not found

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        """Return pending approval requests."""
        return list(self._approvals.values())

    async def approve_request(
        self,
        approval_id: str,
        approved_by: str,
        comment: str | None = None,
    ) -> bool:
        """Approve a pending request."""
        if approval_id not in self._approvals:
            return False

        approval = self._approvals[approval_id]
        # Update associated execution
        execution_id = approval.execution_id
        if execution_id in self._executions:
            execution = self._executions[execution_id]
            execution.status = "running"

        return True

    async def deny_request(
        self,
        approval_id: str,
        denied_by: str,
        reason: str | None = None,
    ) -> bool:
        """Deny a pending request."""
        if approval_id not in self._approvals:
            return False

        approval = self._approvals[approval_id]
        # Update associated execution
        execution_id = approval.execution_id
        if execution_id in self._executions:
            execution = self._executions[execution_id]
            execution.status = "cancelled"
            execution.completed_at = datetime.now(timezone.utc)

        return True

    # Convenience methods for common workflows
    async def isolate_host_workflow(self, hostname: str, case_id: str | None = None) -> WorkflowExecution:
        """Trigger host isolation workflow."""
        return await self.trigger_workflow(
            "wf-isolate-host",
            {"hostname": hostname, "reason": "Security incident response", "case_id": case_id},
        )

    async def block_ip_workflow(self, ip_address: str, case_id: str | None = None) -> WorkflowExecution:
        """Trigger IP block workflow."""
        return await self.trigger_workflow(
            "wf-block-ip",
            {"ip_address": ip_address, "case_id": case_id},
        )

    async def disable_user_workflow(self, username: str, case_id: str | None = None) -> WorkflowExecution:
        """Trigger user disable workflow."""
        return await self.trigger_workflow(
            "wf-disable-user",
            {"username": username, "reason": "Security incident response"},
        )


class MockShuffleExecution:
    """Helper class for mock Shuffle execution data."""

    @staticmethod
    def create_completed_execution() -> WorkflowExecution:
        """Create a completed execution record."""
        return WorkflowExecution(
            execution_id=str(uuid4()),
            workflow_id="wf-enrich-ioc",
            workflow_name="Enrich IOC",
            status="completed",
            started_at=datetime(2024, 1, 20, 10, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 20, 10, 0, 5, tzinfo=timezone.utc),
            triggered_by="api",
            parameters={"ioc_value": "malicious.com", "ioc_type": "domain"},
            results={"success": True, "enrichment": {"threat_score": 85, "labels": ["malware", "c2"]}},
        )

    @staticmethod
    def create_failed_execution() -> WorkflowExecution:
        """Create a failed execution record."""
        return WorkflowExecution(
            execution_id=str(uuid4()),
            workflow_id="wf-block-ip",
            workflow_name="Block IP Address",
            status="failed",
            started_at=datetime(2024, 1, 20, 11, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 20, 11, 0, 10, tzinfo=timezone.utc),
            triggered_by="api",
            parameters={"ip_address": "192.168.1.1"},
            error="Firewall API connection timeout",
        )
