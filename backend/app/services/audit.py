"""Audit logging service for Eleanor.

Provides comprehensive audit logging for security-sensitive operations
including response actions, case management, and user actions.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.response_action import ResponseAction, ResponseActionStatus, ResponseActionType

logger = logging.getLogger(__name__)


class AuditService:
    """Service for creating and querying audit logs."""

    def __init__(self, db: AsyncSession):
        """Initialize audit service with database session."""
        self.db = db

    async def log_action(
        self,
        action: str,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            action: Action performed (e.g., 'login', 'case.create', 'response.isolate')
            user_id: ID of user performing action
            username: Username for display
            resource_type: Type of resource (case, evidence, endpoint, etc.)
            resource_id: ID of affected resource
            details: Additional details about the action
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created AuditLog entry
        """
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            "Audit: %s by %s on %s/%s",
            action,
            username or "system",
            resource_type or "n/a",
            resource_id or "n/a",
        )

        return audit_log

    async def log_response_action(
        self,
        action_type: ResponseActionType,
        user_id: UUID,
        username: str,
        client_id: str,
        hostname: Optional[str] = None,
        case_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        target_details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a response action with full context.

        Args:
            action_type: Type of response action
            user_id: User performing the action
            username: Username for audit
            client_id: Target endpoint client ID
            hostname: Target hostname
            case_id: Associated case ID
            reason: Reason for action
            target_details: Additional target info (file path, PID, etc.)
            ip_address: Client IP address

        Returns:
            Created AuditLog entry
        """
        details = {
            "action_type": action_type.value,
            "client_id": client_id,
            "hostname": hostname,
            "reason": reason,
            "target_details": target_details or {},
        }

        if case_id:
            details["case_id"] = str(case_id)

        return await self.log_action(
            action=f"response.{action_type.value}",
            user_id=user_id,
            username=username,
            resource_type="endpoint",
            details=details,
            ip_address=ip_address,
        )

    async def get_audit_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[AuditLog]:
        """Query audit logs with filters.

        Args:
            limit: Maximum records to return
            offset: Pagination offset
            action: Filter by action prefix (e.g., 'response.' for all response actions)
            user_id: Filter by user
            resource_type: Filter by resource type
            resource_id: Filter by specific resource
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of matching AuditLog entries
        """
        query = select(AuditLog).order_by(AuditLog.created_at.desc())

        if action:
            query = query.where(AuditLog.action.startswith(action))
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if start_time:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            query = query.where(AuditLog.created_at <= end_time)

        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())


class ResponseActionService:
    """Service for managing response actions with audit logging."""

    def __init__(self, db: AsyncSession, audit_service: AuditService):
        """Initialize response action service."""
        self.db = db
        self.audit = audit_service

    async def create_action(
        self,
        tenant_id: UUID,
        user_id: UUID,
        action_type: ResponseActionType,
        client_id: str,
        hostname: Optional[str] = None,
        case_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        target_details: Optional[dict[str, Any]] = None,
    ) -> ResponseAction:
        """Create a new response action record.

        Args:
            tenant_id: Tenant ID
            user_id: User performing the action
            action_type: Type of response action
            client_id: Target endpoint client ID
            hostname: Target hostname
            case_id: Associated case ID
            reason: Reason for the action
            target_details: Additional target info

        Returns:
            Created ResponseAction record
        """
        action = ResponseAction(
            tenant_id=tenant_id,
            user_id=user_id,
            case_id=case_id,
            action_type=action_type.value,
            status=ResponseActionStatus.PENDING.value,
            client_id=client_id,
            hostname=hostname,
            target_details=target_details or {},
            reason=reason,
        )

        self.db.add(action)
        await self.db.flush()

        return action

    async def update_action_status(
        self,
        action_id: UUID,
        status: ResponseActionStatus,
        job_id: Optional[str] = None,
        result: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ResponseAction]:
        """Update response action status.

        Args:
            action_id: Response action ID
            status: New status
            job_id: Collection job ID if applicable
            result: Action result data
            error_message: Error message if failed

        Returns:
            Updated ResponseAction or None if not found
        """
        query = select(ResponseAction).where(ResponseAction.id == action_id)
        result_row = await self.db.execute(query)
        action = result_row.scalar_one_or_none()

        if not action:
            return None

        action.status = status.value
        if job_id:
            action.job_id = job_id
        if result:
            action.result = result
        if error_message:
            action.error_message = error_message

        now = datetime.utcnow()
        if status == ResponseActionStatus.IN_PROGRESS:
            action.started_at = now
        elif status in (ResponseActionStatus.COMPLETED, ResponseActionStatus.FAILED):
            action.completed_at = now

        await self.db.flush()
        return action

    async def get_action(self, action_id: UUID) -> Optional[ResponseAction]:
        """Get a response action by ID."""
        query = select(ResponseAction).where(ResponseAction.id == action_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_actions_by_client(
        self,
        client_id: str,
        tenant_id: UUID,
        limit: int = 50,
    ) -> list[ResponseAction]:
        """Get response actions for a specific client."""
        query = (
            select(ResponseAction)
            .where(
                ResponseAction.client_id == client_id,
                ResponseAction.tenant_id == tenant_id,
            )
            .order_by(ResponseAction.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_actions_by_case(
        self,
        case_id: UUID,
        limit: int = 100,
    ) -> list[ResponseAction]:
        """Get response actions linked to a case."""
        query = (
            select(ResponseAction)
            .where(ResponseAction.case_id == case_id)
            .order_by(ResponseAction.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pending_actions(
        self,
        tenant_id: UUID,
        limit: int = 100,
    ) -> list[ResponseAction]:
        """Get pending response actions for a tenant."""
        query = (
            select(ResponseAction)
            .where(
                ResponseAction.tenant_id == tenant_id,
                ResponseAction.status.in_([
                    ResponseActionStatus.PENDING.value,
                    ResponseActionStatus.IN_PROGRESS.value,
                ]),
            )
            .order_by(ResponseAction.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_action_history(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        action_type: Optional[ResponseActionType] = None,
        status: Optional[ResponseActionStatus] = None,
        client_id: Optional[str] = None,
    ) -> list[ResponseAction]:
        """Get response action history with filters."""
        query = (
            select(ResponseAction)
            .where(ResponseAction.tenant_id == tenant_id)
            .order_by(ResponseAction.created_at.desc())
        )

        if action_type:
            query = query.where(ResponseAction.action_type == action_type.value)
        if status:
            query = query.where(ResponseAction.status == status.value)
        if client_id:
            query = query.where(ResponseAction.client_id == client_id)

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_isolation_status(
        self,
        client_id: str,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Get current isolation status for a client.

        Returns the most recent isolate/release action to determine current state.
        """
        query = (
            select(ResponseAction)
            .where(
                ResponseAction.client_id == client_id,
                ResponseAction.tenant_id == tenant_id,
                ResponseAction.action_type.in_([
                    ResponseActionType.ISOLATE.value,
                    ResponseActionType.RELEASE.value,
                ]),
                ResponseAction.status == ResponseActionStatus.COMPLETED.value,
            )
            .order_by(ResponseAction.completed_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        action = result.scalar_one_or_none()

        if not action:
            return {
                "is_isolated": False,
                "last_action": None,
                "last_action_at": None,
                "last_action_by": None,
            }

        return {
            "is_isolated": action.action_type == ResponseActionType.ISOLATE.value,
            "last_action": action.action_type,
            "last_action_at": action.completed_at.isoformat() if action.completed_at else None,
            "last_action_by": str(action.user_id),
        }
