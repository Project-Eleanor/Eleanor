"""Action executor for playbook response actions.

This service executes individual response actions like blocking IPs,
isolating hosts, disabling users, and integrating with external tools.
"""

import logging
from typing import Any
from uuid import UUID

from app.adapters import get_registry
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ActionExecutor:
    """Executes response actions for playbooks."""

    # Registry of available actions
    ACTIONS = {
        "block_ip": {
            "name": "Block IP Address",
            "description": "Block an IP address at the firewall",
            "parameters": {
                "ip": {"type": "string", "required": True, "description": "IP to block"},
                "duration_hours": {
                    "type": "integer",
                    "default": 24,
                    "description": "Block duration",
                },
                "reason": {"type": "string", "description": "Reason for blocking"},
            },
        },
        "isolate_host": {
            "name": "Isolate Host",
            "description": "Network isolate a compromised host",
            "parameters": {
                "hostname": {"type": "string", "required": True, "description": "Host to isolate"},
                "isolation_level": {
                    "type": "string",
                    "default": "full",
                    "description": "full or partial",
                },
            },
        },
        "disable_user": {
            "name": "Disable User Account",
            "description": "Disable a user account in Active Directory",
            "parameters": {
                "username": {"type": "string", "required": True, "description": "User to disable"},
                "reset_password": {
                    "type": "boolean",
                    "default": False,
                    "description": "Also reset password",
                },
            },
        },
        "collect_evidence": {
            "name": "Collect Evidence",
            "description": "Trigger forensic collection from endpoint",
            "parameters": {
                "hostname": {"type": "string", "required": True, "description": "Target host"},
                "collection_profile": {
                    "type": "string",
                    "default": "full",
                    "description": "Collection profile",
                },
            },
        },
        "create_ticket": {
            "name": "Create Ticket",
            "description": "Create a ticket in the ticketing system",
            "parameters": {
                "title": {"type": "string", "required": True, "description": "Ticket title"},
                "description": {
                    "type": "string",
                    "required": True,
                    "description": "Ticket description",
                },
                "priority": {"type": "string", "default": "high", "description": "Ticket priority"},
                "assignee": {"type": "string", "description": "Assignee username"},
            },
        },
        "send_email": {
            "name": "Send Email",
            "description": "Send an email notification",
            "parameters": {
                "to": {"type": "array", "required": True, "description": "Recipients"},
                "subject": {"type": "string", "required": True, "description": "Email subject"},
                "body": {"type": "string", "required": True, "description": "Email body"},
                "html": {"type": "boolean", "default": False, "description": "Body is HTML"},
            },
        },
        "run_query": {
            "name": "Run Search Query",
            "description": "Execute a search query and return results",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "Search query"},
                "index_pattern": {
                    "type": "string",
                    "default": "events-*",
                    "description": "Index pattern",
                },
                "time_range": {"type": "string", "default": "24h", "description": "Time range"},
            },
        },
        "enrich_ioc": {
            "name": "Enrich IOC",
            "description": "Enrich an IOC with threat intelligence",
            "parameters": {
                "ioc_type": {
                    "type": "string",
                    "required": True,
                    "description": "IOC type (ip, domain, hash)",
                },
                "ioc_value": {"type": "string", "required": True, "description": "IOC value"},
            },
        },
        "http_request": {
            "name": "HTTP Request",
            "description": "Make an HTTP request to an external API",
            "parameters": {
                "method": {"type": "string", "default": "GET", "description": "HTTP method"},
                "url": {"type": "string", "required": True, "description": "Request URL"},
                "headers": {"type": "object", "default": {}, "description": "Request headers"},
                "body": {"type": "object", "description": "Request body"},
            },
        },
    }

    async def execute(
        self,
        action: str,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Execute an action with the given parameters.

        Args:
            action: Action identifier
            parameters: Action parameters
            tenant_id: Tenant context

        Returns:
            Action result
        """
        if action not in self.ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        logger.info("Executing action: %s with params: %s", action, parameters)

        # Dispatch to specific handler
        handler = getattr(self, f"_action_{action}", None)
        if handler:
            return await handler(parameters, tenant_id)

        # Generic handler
        return await self._generic_action(action, parameters, tenant_id)

    async def execute_soar_workflow(
        self,
        workflow_id: str,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Execute a SOAR workflow via Shuffle.

        Args:
            workflow_id: Shuffle workflow ID
            parameters: Workflow parameters
            tenant_id: Tenant context

        Returns:
            Workflow execution result
        """
        registry = get_registry()
        shuffle = registry.get("shuffle")

        if not shuffle:
            raise RuntimeError("Shuffle adapter not configured")

        try:
            execution_id = await shuffle.trigger_workflow(workflow_id, parameters)

            # Wait for completion (with timeout)
            import asyncio

            max_wait = 300  # 5 minutes
            poll_interval = 5

            for _ in range(max_wait // poll_interval):
                status = await shuffle.get_execution_status(execution_id)
                if status.get("status") in {"FINISHED", "ABORTED", "FAILED"}:
                    return {
                        "execution_id": execution_id,
                        "status": status.get("status"),
                        "result": status.get("result"),
                    }
                await asyncio.sleep(poll_interval)

            return {
                "execution_id": execution_id,
                "status": "TIMEOUT",
                "error": "Workflow execution timed out",
            }

        except Exception as e:
            logger.error("SOAR workflow execution failed: %s", str(e))
            return {
                "status": "FAILED",
                "error": str(e),
            }

    async def _action_block_ip(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Block an IP address."""
        ip = parameters.get("ip")
        duration = parameters.get("duration_hours", 24)
        reason = parameters.get("reason", "Blocked by playbook")

        # Try Shuffle workflow first
        registry = get_registry()
        shuffle = registry.get("shuffle")

        if shuffle:
            try:
                result = await shuffle.block_ip_workflow(ip)
                return {
                    "success": True,
                    "action": "block_ip",
                    "ip": ip,
                    "method": "shuffle_workflow",
                    "result": result,
                }
            except Exception as e:
                logger.warning("Shuffle block_ip failed, using fallback: %s", str(e))

        # Fallback: Log for manual action
        logger.warning(
            "MANUAL ACTION REQUIRED: Block IP %s for %d hours. Reason: %s",
            ip,
            duration,
            reason,
        )

        return {
            "success": True,
            "action": "block_ip",
            "ip": ip,
            "method": "manual_required",
            "message": f"Manual action required: Block IP {ip}",
        }

    async def _action_isolate_host(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Isolate a host."""
        hostname = parameters.get("hostname")
        level = parameters.get("isolation_level", "full")

        # Try Velociraptor
        registry = get_registry()
        velo = registry.get("velociraptor")

        if velo:
            try:
                # Get client ID for hostname
                clients = await velo.search_clients(hostname)
                if clients:
                    client_id = clients[0].get("client_id")
                    # Run isolation artifact
                    result = await velo.collect_artifact(
                        client_id,
                        (
                            "Windows.Remediation.Quarantine"
                            if level == "full"
                            else "Windows.Remediation.QuarantinePartial"
                        ),
                    )
                    return {
                        "success": True,
                        "action": "isolate_host",
                        "hostname": hostname,
                        "method": "velociraptor",
                        "result": result,
                    }
            except Exception as e:
                logger.warning("Velociraptor isolation failed: %s", str(e))

        # Try Shuffle
        shuffle = registry.get("shuffle")
        if shuffle:
            try:
                result = await shuffle.isolate_host_workflow(hostname)
                return {
                    "success": True,
                    "action": "isolate_host",
                    "hostname": hostname,
                    "method": "shuffle_workflow",
                    "result": result,
                }
            except Exception as e:
                logger.warning("Shuffle isolation failed: %s", str(e))

        return {
            "success": True,
            "action": "isolate_host",
            "hostname": hostname,
            "method": "manual_required",
            "message": f"Manual action required: Isolate host {hostname}",
        }

    async def _action_disable_user(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Disable a user account."""
        username = parameters.get("username")
        parameters.get("reset_password", False)

        registry = get_registry()
        shuffle = registry.get("shuffle")

        if shuffle:
            try:
                result = await shuffle.disable_user_workflow(username)
                return {
                    "success": True,
                    "action": "disable_user",
                    "username": username,
                    "method": "shuffle_workflow",
                    "result": result,
                }
            except Exception as e:
                logger.warning("Shuffle disable_user failed: %s", str(e))

        return {
            "success": True,
            "action": "disable_user",
            "username": username,
            "method": "manual_required",
            "message": f"Manual action required: Disable user {username}",
        }

    async def _action_collect_evidence(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Collect forensic evidence from endpoint."""
        hostname = parameters.get("hostname")
        profile = parameters.get("collection_profile", "full")

        registry = get_registry()
        velo = registry.get("velociraptor")

        if velo:
            try:
                clients = await velo.search_clients(hostname)
                if clients:
                    client_id = clients[0].get("client_id")

                    # Select artifact based on profile
                    artifacts = {
                        "full": "Windows.KapeFiles.Targets",
                        "memory": "Windows.Memory.Acquisition",
                        "triage": "Windows.Collection.Triage",
                    }
                    artifact = artifacts.get(profile, artifacts["triage"])

                    result = await velo.collect_artifact(client_id, artifact)
                    return {
                        "success": True,
                        "action": "collect_evidence",
                        "hostname": hostname,
                        "method": "velociraptor",
                        "artifact": artifact,
                        "result": result,
                    }
            except Exception as e:
                logger.warning("Velociraptor collection failed: %s", str(e))

        return {
            "success": True,
            "action": "collect_evidence",
            "hostname": hostname,
            "method": "manual_required",
            "message": f"Manual action required: Collect evidence from {hostname}",
        }

    async def _action_enrich_ioc(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Enrich an IOC with threat intelligence."""
        ioc_type = parameters.get("ioc_type")
        ioc_value = parameters.get("ioc_value")

        registry = get_registry()
        opencti = registry.get("opencti")

        if opencti:
            try:
                result = await opencti.search_observable(ioc_value, ioc_type)
                return {
                    "success": True,
                    "action": "enrich_ioc",
                    "ioc_type": ioc_type,
                    "ioc_value": ioc_value,
                    "method": "opencti",
                    "result": result,
                }
            except Exception as e:
                logger.warning("OpenCTI enrichment failed: %s", str(e))

        return {
            "success": True,
            "action": "enrich_ioc",
            "ioc_type": ioc_type,
            "ioc_value": ioc_value,
            "method": "not_available",
            "message": "Threat intelligence enrichment not available",
        }

    async def _action_http_request(
        self,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Make an HTTP request."""
        import httpx

        method = parameters.get("method", "GET")
        url = parameters.get("url")
        headers = parameters.get("headers", {})
        body = parameters.get("body")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
            )

            return {
                "success": response.is_success,
                "action": "http_request",
                "status_code": response.status_code,
                "response": (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else response.text[:1000]
                ),
            }

    async def _generic_action(
        self,
        action: str,
        parameters: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Generic action handler for unimplemented actions."""
        logger.info(
            "Generic action execution: %s with params: %s",
            action,
            parameters,
        )

        return {
            "success": True,
            "action": action,
            "method": "logged_only",
            "message": f"Action {action} logged for manual review",
            "parameters": parameters,
        }

    @classmethod
    def list_actions(cls) -> list[dict[str, Any]]:
        """List all available actions with their schemas."""
        return [{"id": action_id, **action_def} for action_id, action_def in cls.ACTIONS.items()]


# Module-level instance
_action_executor: ActionExecutor | None = None


def get_action_executor() -> ActionExecutor:
    """Get the action executor instance."""
    global _action_executor
    if _action_executor is None:
        _action_executor = ActionExecutor()
    return _action_executor
