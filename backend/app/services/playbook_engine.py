"""Playbook execution engine for response automation.

This service orchestrates playbook execution, managing step progression,
conditional branching, approval gates, and error handling.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.playbook import (
    ApprovalStatus,
    ExecutionStatus,
    Playbook,
    PlaybookApproval,
    PlaybookExecution,
    PlaybookStatus,
    StepType,
)
from app.services.action_executor import get_action_executor

logger = logging.getLogger(__name__)


class PlaybookEngine:
    """Engine for executing playbooks."""

    def __init__(self):
        """Initialize the playbook engine."""
        self.action_executor = get_action_executor()

    async def start_execution(
        self,
        playbook_id: UUID,
        input_data: dict[str, Any],
        trigger_type: str | None,
        trigger_id: UUID | None,
        started_by: UUID | None,
        db: AsyncSession,
    ) -> PlaybookExecution:
        """Start a new playbook execution.

        Args:
            playbook_id: Playbook to execute
            input_data: Input parameters for the playbook
            trigger_type: What triggered this execution (alert, incident, manual)
            trigger_id: ID of the triggering entity
            started_by: User who started the execution
            db: Database session

        Returns:
            The created execution record
        """
        # Load playbook
        result = await db.execute(
            select(Playbook).where(Playbook.id == playbook_id)
        )
        playbook = result.scalar_one_or_none()

        if not playbook:
            raise ValueError(f"Playbook {playbook_id} not found")

        if playbook.status != PlaybookStatus.ACTIVE:
            raise ValueError(f"Playbook {playbook.name} is not active")

        # Create execution record
        execution = PlaybookExecution(
            playbook_id=playbook_id,
            tenant_id=playbook.tenant_id,
            status=ExecutionStatus.PENDING,
            trigger_type=trigger_type,
            trigger_id=trigger_id,
            input_data=input_data,
            started_by=started_by,
        )

        db.add(execution)
        await db.flush()

        # Update playbook stats
        playbook.execution_count += 1

        logger.info(
            "Started playbook execution: %s (%s)",
            playbook.name,
            execution.id,
        )

        return execution

    async def execute(
        self,
        execution_id: UUID,
        db: AsyncSession,
    ) -> PlaybookExecution:
        """Execute a playbook from start to completion.

        Args:
            execution_id: Execution to run
            db: Database session

        Returns:
            Updated execution record
        """
        # Load execution with playbook
        result = await db.execute(
            select(PlaybookExecution)
            .options(joinedload(PlaybookExecution.playbook))
            .where(PlaybookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        playbook = execution.playbook
        steps = playbook.steps

        if not steps:
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(UTC)
            await db.commit()
            return execution

        # Start execution
        execution.status = ExecutionStatus.RUNNING
        execution.current_step_id = steps[0].get("id")

        try:
            # Build step lookup
            step_map = {s["id"]: s for s in steps}

            # Execute steps
            current_step_id = steps[0]["id"]

            while current_step_id:
                step = step_map.get(current_step_id)
                if not step:
                    raise ValueError(f"Step {current_step_id} not found")

                execution.current_step_id = current_step_id

                # Execute step
                step_result = await self._execute_step(
                    execution, step, db
                )

                # Record result
                execution.step_results = [
                    *execution.step_results,
                    step_result,
                ]

                # Check for approval wait
                if step_result.get("status") == "waiting_approval":
                    execution.status = ExecutionStatus.WAITING_APPROVAL
                    await db.commit()
                    return execution

                # Determine next step
                if step_result.get("status") == "completed":
                    current_step_id = step.get("on_success")
                else:
                    current_step_id = step.get("on_failure")
                    if not current_step_id:
                        # No failure handler, fail execution
                        raise Exception(step_result.get("error", "Step failed"))

            # Execution completed successfully
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(UTC)
            execution.duration_seconds = int(
                (execution.completed_at - execution.started_at).total_seconds()
            )
            playbook.success_count += 1

            # Collect outputs
            execution.output_data = self._collect_outputs(execution.step_results)

            logger.info(
                "Playbook execution completed: %s (%s) in %ds",
                playbook.name,
                execution.id,
                execution.duration_seconds,
            )

        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.error_step_id = execution.current_step_id
            execution.completed_at = datetime.now(UTC)
            playbook.failure_count += 1

            logger.error(
                "Playbook execution failed: %s (%s) - %s",
                playbook.name,
                execution.id,
                str(e),
            )

        await db.commit()
        return execution

    async def resume_execution(
        self,
        execution_id: UUID,
        approved: bool,
        decision_comment: str | None,
        decided_by: UUID,
        db: AsyncSession,
    ) -> PlaybookExecution:
        """Resume an execution after approval decision.

        Args:
            execution_id: Execution to resume
            approved: Whether the step was approved
            decision_comment: Optional comment from approver
            decided_by: User who made the decision
            db: Database session

        Returns:
            Updated execution record
        """
        # Load execution
        result = await db.execute(
            select(PlaybookExecution)
            .options(joinedload(PlaybookExecution.playbook))
            .options(joinedload(PlaybookExecution.approvals))
            .where(PlaybookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        if execution.status != ExecutionStatus.WAITING_APPROVAL:
            raise ValueError("Execution is not waiting for approval")

        # Find pending approval
        pending_approval = None
        for approval in execution.approvals:
            if approval.status == ApprovalStatus.PENDING:
                pending_approval = approval
                break

        if not pending_approval:
            raise ValueError("No pending approval found")

        # Update approval
        pending_approval.status = (
            ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        )
        pending_approval.approved_by = decided_by
        pending_approval.decision_comment = decision_comment
        pending_approval.decided_at = datetime.now(UTC)

        # Update step result
        step_results = list(execution.step_results)
        for i, result in enumerate(step_results):
            if result.get("step_id") == pending_approval.step_id:
                step_results[i] = {
                    **result,
                    "status": "completed" if approved else "denied",
                    "approved": approved,
                    "decision_comment": decision_comment,
                    "decided_by": str(decided_by),
                    "decided_at": datetime.now(UTC).isoformat(),
                }
                break

        execution.step_results = step_results

        if not approved:
            # Approval denied - check for denial handler
            playbook = execution.playbook
            step_map = {s["id"]: s for s in playbook.steps}
            current_step = step_map.get(pending_approval.step_id)

            if current_step and current_step.get("on_deny"):
                # Continue with denial handler
                execution.current_step_id = current_step["on_deny"]
                execution.status = ExecutionStatus.RUNNING
            else:
                # No denial handler - mark as failed
                execution.status = ExecutionStatus.FAILED
                execution.error_message = "Approval denied"
                execution.completed_at = datetime.now(UTC)
        else:
            # Continue execution
            playbook = execution.playbook
            step_map = {s["id"]: s for s in playbook.steps}
            current_step = step_map.get(pending_approval.step_id)

            if current_step and current_step.get("on_approve"):
                execution.current_step_id = current_step["on_approve"]
                execution.status = ExecutionStatus.RUNNING
            else:
                execution.status = ExecutionStatus.COMPLETED
                execution.completed_at = datetime.now(UTC)

        await db.commit()

        # If still running, continue execution
        if execution.status == ExecutionStatus.RUNNING:
            return await self.execute(execution_id, db)

        return execution

    async def cancel_execution(
        self,
        execution_id: UUID,
        cancelled_by: UUID,
        db: AsyncSession,
    ) -> PlaybookExecution:
        """Cancel a running or pending execution.

        Args:
            execution_id: Execution to cancel
            cancelled_by: User cancelling the execution
            db: Database session

        Returns:
            Updated execution record
        """
        result = await db.execute(
            select(PlaybookExecution).where(PlaybookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        if execution.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }:
            raise ValueError("Execution is already finished")

        execution.status = ExecutionStatus.CANCELLED
        execution.error_message = f"Cancelled by user {cancelled_by}"
        execution.completed_at = datetime.now(UTC)

        await db.commit()

        logger.info("Playbook execution cancelled: %s", execution_id)
        return execution

    async def _execute_step(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute a single playbook step.

        Args:
            execution: Current execution
            step: Step configuration
            db: Database session

        Returns:
            Step result dictionary
        """
        step_id = step["id"]
        step_type = StepType(step.get("type", "action"))
        started_at = datetime.now(UTC)

        result = {
            "step_id": step_id,
            "step_name": step.get("name", step_id),
            "type": step_type.value,
            "started_at": started_at.isoformat(),
        }

        try:
            match step_type:
                case StepType.ACTION:
                    output = await self._execute_action_step(execution, step)
                    result["output"] = output
                    result["status"] = "completed"

                case StepType.APPROVAL:
                    # Create approval request
                    approval = await self._create_approval(execution, step, db)
                    result["approval_id"] = str(approval.id)
                    result["status"] = "waiting_approval"

                case StepType.DELAY:
                    duration = step.get("duration_seconds", 60)
                    await asyncio.sleep(min(duration, 300))  # Cap at 5 minutes
                    result["status"] = "completed"

                case StepType.CONDITION:
                    branch = await self._evaluate_condition(execution, step)
                    result["evaluated_branch"] = branch
                    result["status"] = "completed"

                case StepType.NOTIFICATION:
                    await self._send_notification(execution, step)
                    result["status"] = "completed"

                case StepType.SOAR:
                    output = await self._execute_soar_workflow(execution, step)
                    result["output"] = output
                    result["status"] = "completed"

                case _:
                    raise ValueError(f"Unknown step type: {step_type}")

            result["completed_at"] = datetime.now(UTC).isoformat()

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["completed_at"] = datetime.now(UTC).isoformat()
            logger.error(
                "Step %s failed in execution %s: %s",
                step_id,
                execution.id,
                str(e),
            )

        return result

    async def _execute_action_step(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an action step."""
        action = step.get("action")
        parameters = step.get("parameters", {})

        # Resolve template variables in parameters
        resolved_params = self._resolve_templates(
            parameters, execution.input_data, execution.step_results
        )

        # Execute action
        return await self.action_executor.execute(
            action,
            resolved_params,
            execution.tenant_id,
        )

    async def _create_approval(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
        db: AsyncSession,
    ) -> PlaybookApproval:
        """Create an approval request."""
        timeout_hours = step.get("timeout_hours", 24)

        approval = PlaybookApproval(
            execution_id=execution.id,
            tenant_id=execution.tenant_id,
            step_id=step["id"],
            step_name=step.get("name", step["id"]),
            context={
                "playbook_name": execution.playbook.name,
                "action": step.get("action_description", "Requires approval"),
                "parameters": step.get("parameters", {}),
                "input_data": execution.input_data,
            },
            required_approvers=step.get("approvers", []),
            expires_at=datetime.now(UTC) + timedelta(hours=timeout_hours),
        )

        db.add(approval)
        await db.flush()

        logger.info(
            "Created approval request %s for step %s",
            approval.id,
            step["id"],
        )

        return approval

    async def _evaluate_condition(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
    ) -> str:
        """Evaluate a condition step and return the branch to follow."""
        conditions = step.get("conditions", [])
        default_branch = step.get("default", "on_success")

        # Merge context for evaluation
        context = {
            **execution.input_data,
            "step_results": {r["step_id"]: r for r in execution.step_results},
        }

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator", "eq")
            value = condition.get("value")
            branch = condition.get("branch")

            # Get field value from context
            field_value = self._get_nested_value(context, field)

            # Evaluate condition
            matched = False
            match operator:
                case "eq":
                    matched = field_value == value
                case "neq":
                    matched = field_value != value
                case "contains":
                    matched = value in str(field_value)
                case "gt":
                    matched = field_value > value
                case "lt":
                    matched = field_value < value
                case "exists":
                    matched = field_value is not None

            if matched:
                return branch

        return default_branch

    async def _send_notification(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
    ) -> None:
        """Send a notification."""
        # TODO: Implement notification sending
        logger.info(
            "Notification step: %s - %s",
            step.get("channel", "default"),
            step.get("message", "Playbook notification"),
        )

    async def _execute_soar_workflow(
        self,
        execution: PlaybookExecution,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a SOAR workflow via Shuffle adapter."""
        workflow_id = step.get("workflow_id")
        parameters = step.get("parameters", {})

        # Resolve templates
        resolved_params = self._resolve_templates(
            parameters, execution.input_data, execution.step_results
        )

        return await self.action_executor.execute_soar_workflow(
            workflow_id,
            resolved_params,
            execution.tenant_id,
        )

    def _resolve_templates(
        self,
        parameters: dict[str, Any],
        input_data: dict[str, Any],
        step_results: list[dict],
    ) -> dict[str, Any]:
        """Resolve template variables in parameters."""
        import re

        context = {
            "input": input_data,
            "steps": {r["step_id"]: r.get("output", {}) for r in step_results},
        }

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # Find {{ variable }} patterns
                pattern = r"\{\{\s*([^}]+)\s*\}\}"
                matches = re.findall(pattern, value)
                for match in matches:
                    resolved = self._get_nested_value(context, match.strip())
                    if resolved is not None:
                        if value == f"{{{{ {match} }}}}":
                            return resolved
                        value = value.replace(f"{{{{ {match} }}}}", str(resolved))
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            return value

        return resolve_value(parameters)

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get a nested value from a dictionary."""
        keys = path.split(".")
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def _collect_outputs(self, step_results: list[dict]) -> dict[str, Any]:
        """Collect outputs from all steps."""
        outputs = {}
        for result in step_results:
            if result.get("output"):
                outputs[result["step_id"]] = result["output"]
        return outputs


# Module-level instance
_playbook_engine: PlaybookEngine | None = None


def get_playbook_engine() -> PlaybookEngine:
    """Get the playbook engine instance."""
    global _playbook_engine
    if _playbook_engine is None:
        _playbook_engine = PlaybookEngine()
    return _playbook_engine
