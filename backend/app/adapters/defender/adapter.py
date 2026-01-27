"""Microsoft Defender for Endpoint adapter implementation.

Provides integration with Microsoft Defender for Endpoint API for:
- Device inventory and management
- Alert retrieval and management
- Response actions (isolation, quarantine, etc.)
- Live response capabilities
"""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    CollectionAdapter,
    CollectionArtifact,
    CollectionJob,
    Endpoint,
    Hunt,
)
from app.adapters.defender.schemas import (
    ActionStatus,
    ActionType,
    AlertSeverity,
    AlertStatus,
    DefenderAction,
    DefenderAlert,
    DefenderDevice,
    DefenderInvestigation,
    LiveResponseCommand,
    LiveResponseSession,
)

logger = logging.getLogger(__name__)


class DefenderAdapter(CollectionAdapter):
    """Microsoft Defender for Endpoint adapter.

    Implements CollectionAdapter interface for endpoint management
    and response actions via Microsoft's security APIs.

    Authentication uses MSAL (Microsoft Authentication Library) for
    OAuth2 client credentials flow.
    """

    name = "defender"
    description = "Microsoft Defender for Endpoint"

    # Microsoft API endpoints
    AUTHORITY_URL = "https://login.microsoftonline.com"
    RESOURCE_URL = "https://api.securitycenter.microsoft.com"
    API_VERSION = "v1.0"

    def __init__(self, config: AdapterConfig):
        """Initialize Defender adapter.

        Args:
            config: Adapter configuration with tenant_id, client_id, client_secret
                   in the 'extra' dict.
        """
        super().__init__(config)
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._client: httpx.AsyncClient | None = None

        # Extract Azure AD credentials from extra config
        self._tenant_id = config.extra.get("tenant_id", "")
        self._client_id = config.extra.get("client_id", "")
        self._client_secret = config.extra.get("client_secret", "")

    async def _get_token(self) -> str:
        """Get OAuth2 access token using MSAL.

        Returns:
            Access token string.
        """
        import msal

        # Check if we have a valid cached token
        if self._token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return self._token

        # Create MSAL confidential client
        authority = f"{self.AUTHORITY_URL}/{self._tenant_id}"
        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=authority,
            client_credential=self._client_secret,
        )

        # Acquire token for the security center scope
        scope = [f"{self.RESOURCE_URL}/.default"]
        result = app.acquire_token_for_client(scopes=scope)

        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise RuntimeError(f"Failed to acquire token: {error}")

        self._token = result["access_token"]
        # Token typically expires in 1 hour, refresh a bit early
        self._token_expires = datetime.utcnow()

        return self._token

    async def _get_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client with auth headers."""
        if self._client is None:
            token = await self._get_token()
            self._client = httpx.AsyncClient(
                base_url=f"{self.RESOURCE_URL}/api",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make authenticated API request."""
        client = await self._get_client()

        # Refresh token if needed
        token = await self._get_token()
        client.headers["Authorization"] = f"Bearer {token}"

        response = await client.request(method, path, **kwargs)
        response.raise_for_status()

        if response.status_code == 204:
            return {}
        return response.json()

    async def connect(self) -> bool:
        """Test connection by acquiring token."""
        try:
            await self._get_token()
            self._status = AdapterStatus.CONNECTED
            logger.info("Connected to Microsoft Defender for Endpoint")
            return True
        except Exception as e:
            logger.error("Failed to connect to Defender: %s", e)
            self._status = AdapterStatus.ERROR
            return False

    async def disconnect(self) -> None:
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._token = None
        self._token_expires = None
        self._status = AdapterStatus.DISCONNECTED

    async def health_check(self) -> AdapterHealth:
        """Check Defender API health."""
        try:
            # Try to list machines (limited) to verify connectivity
            await self._get_token()
            result = await self._request("GET", "/machines?$top=1")

            self._status = AdapterStatus.CONNECTED
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                message="Connected to Microsoft Defender for Endpoint",
                details={
                    "tenant_id": self._tenant_id[:8] + "..." if self._tenant_id else None,
                    "has_machines": len(result.get("value", [])) > 0,
                },
            )
        except Exception as e:
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get sanitized configuration."""
        return {
            "tenant_id": self._tenant_id[:8] + "..." if self._tenant_id else None,
            "client_id": self._client_id[:8] + "..." if self._client_id else None,
            "api_endpoint": self.RESOURCE_URL,
        }

    # =========================================================================
    # Device Management
    # =========================================================================

    async def list_devices(
        self,
        limit: int = 100,
        offset: int = 0,
        filter_query: str | None = None,
    ) -> list[DefenderDevice]:
        """List devices/machines from Defender.

        Args:
            limit: Maximum devices to return.
            offset: Skip this many devices.
            filter_query: OData filter query.

        Returns:
            List of DefenderDevice objects.
        """
        params = {"$top": limit, "$skip": offset}
        if filter_query:
            params["$filter"] = filter_query

        result = await self._request("GET", "/machines", params=params)
        return [DefenderDevice(**device) for device in result.get("value", [])]

    async def get_device(self, device_id: str) -> DefenderDevice | None:
        """Get device by ID."""
        try:
            result = await self._request("GET", f"/machines/{device_id}")
            return DefenderDevice(**result)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def search_devices(self, query: str) -> list[DefenderDevice]:
        """Search devices by hostname or IP."""
        # Use OData filter for searching
        filter_query = (
            f"contains(computerDnsName, '{query}') or "
            f"contains(lastIpAddress, '{query}')"
        )
        return await self.list_devices(filter_query=filter_query)

    async def get_device_alerts(self, device_id: str) -> list[DefenderAlert]:
        """Get alerts for a specific device."""
        result = await self._request("GET", f"/machines/{device_id}/alerts")
        return [DefenderAlert(**alert) for alert in result.get("value", [])]

    # =========================================================================
    # Alert Management
    # =========================================================================

    async def list_alerts(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: AlertSeverity | None = None,
        status: AlertStatus | None = None,
        filter_query: str | None = None,
    ) -> list[DefenderAlert]:
        """List alerts.

        Args:
            limit: Maximum alerts to return.
            offset: Skip this many alerts.
            severity: Filter by severity.
            status: Filter by status.
            filter_query: OData filter query.

        Returns:
            List of DefenderAlert objects.
        """
        params = {"$top": limit, "$skip": offset}

        filters = []
        if severity:
            filters.append(f"severity eq '{severity.value}'")
        if status:
            filters.append(f"status eq '{status.value}'")
        if filter_query:
            filters.append(filter_query)

        if filters:
            params["$filter"] = " and ".join(filters)

        result = await self._request("GET", "/alerts", params=params)
        return [DefenderAlert(**alert) for alert in result.get("value", [])]

    async def get_alert(self, alert_id: str) -> DefenderAlert | None:
        """Get alert by ID."""
        try:
            result = await self._request("GET", f"/alerts/{alert_id}")
            return DefenderAlert(**result)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def update_alert(
        self,
        alert_id: str,
        status: AlertStatus | None = None,
        assigned_to: str | None = None,
        classification: str | None = None,
        determination: str | None = None,
        comment: str | None = None,
    ) -> DefenderAlert:
        """Update alert status/assignment."""
        data: dict[str, Any] = {}
        if status:
            data["status"] = status.value
        if assigned_to:
            data["assignedTo"] = assigned_to
        if classification:
            data["classification"] = classification
        if determination:
            data["determination"] = determination
        if comment:
            data["comment"] = comment

        result = await self._request("PATCH", f"/alerts/{alert_id}", json=data)
        return DefenderAlert(**result)

    # =========================================================================
    # Response Actions
    # =========================================================================

    async def isolate_device(
        self,
        device_id: str,
        comment: str,
        isolation_type: str = "Full",
    ) -> DefenderAction:
        """Isolate a device from the network.

        Args:
            device_id: Device ID to isolate.
            comment: Reason for isolation.
            isolation_type: "Full" or "Selective".

        Returns:
            DefenderAction tracking the isolation request.
        """
        data = {
            "Comment": comment,
            "IsolationType": isolation_type,
        }
        result = await self._request(
            "POST",
            f"/machines/{device_id}/isolate",
            json=data,
        )
        return DefenderAction(**result)

    async def unisolate_device(
        self,
        device_id: str,
        comment: str,
    ) -> DefenderAction:
        """Remove isolation from a device.

        Args:
            device_id: Device ID to unisolate.
            comment: Reason for removing isolation.

        Returns:
            DefenderAction tracking the request.
        """
        data = {"Comment": comment}
        result = await self._request(
            "POST",
            f"/machines/{device_id}/unisolate",
            json=data,
        )
        return DefenderAction(**result)

    async def run_antivirus_scan(
        self,
        device_id: str,
        comment: str,
        scan_type: str = "Quick",
    ) -> DefenderAction:
        """Trigger antivirus scan on device.

        Args:
            device_id: Device ID to scan.
            comment: Reason for scan.
            scan_type: "Quick" or "Full".

        Returns:
            DefenderAction tracking the scan request.
        """
        data = {
            "Comment": comment,
            "ScanType": scan_type,
        }
        result = await self._request(
            "POST",
            f"/machines/{device_id}/runAntiVirusScan",
            json=data,
        )
        return DefenderAction(**result)

    async def collect_investigation_package(
        self,
        device_id: str,
        comment: str,
    ) -> DefenderAction:
        """Collect forensic investigation package from device.

        Args:
            device_id: Device ID to collect from.
            comment: Reason for collection.

        Returns:
            DefenderAction tracking the collection request.
        """
        data = {"Comment": comment}
        result = await self._request(
            "POST",
            f"/machines/{device_id}/collectInvestigationPackage",
            json=data,
        )
        return DefenderAction(**result)

    async def restrict_app_execution(
        self,
        device_id: str,
        comment: str,
    ) -> DefenderAction:
        """Restrict application execution on device.

        Args:
            device_id: Device ID.
            comment: Reason for restriction.

        Returns:
            DefenderAction tracking the request.
        """
        data = {"Comment": comment}
        result = await self._request(
            "POST",
            f"/machines/{device_id}/restrictCodeExecution",
            json=data,
        )
        return DefenderAction(**result)

    async def unrestrict_app_execution(
        self,
        device_id: str,
        comment: str,
    ) -> DefenderAction:
        """Remove app execution restriction from device.

        Args:
            device_id: Device ID.
            comment: Reason for unrestriction.

        Returns:
            DefenderAction tracking the request.
        """
        data = {"Comment": comment}
        result = await self._request(
            "POST",
            f"/machines/{device_id}/unrestrictCodeExecution",
            json=data,
        )
        return DefenderAction(**result)

    async def stop_and_quarantine_file(
        self,
        device_id: str,
        sha1: str,
        comment: str,
    ) -> DefenderAction:
        """Stop process and quarantine file by SHA1.

        Args:
            device_id: Device ID.
            sha1: SHA1 hash of file to quarantine.
            comment: Reason for quarantine.

        Returns:
            DefenderAction tracking the request.
        """
        data = {
            "Comment": comment,
            "Sha1": sha1,
        }
        result = await self._request(
            "POST",
            f"/machines/{device_id}/StopAndQuarantineFile",
            json=data,
        )
        return DefenderAction(**result)

    async def get_action_status(self, action_id: str) -> DefenderAction:
        """Get status of a machine action.

        Args:
            action_id: Action ID to check.

        Returns:
            DefenderAction with current status.
        """
        result = await self._request("GET", f"/machineactions/{action_id}")
        return DefenderAction(**result)

    async def list_actions(
        self,
        device_id: str | None = None,
        status: ActionStatus | None = None,
        limit: int = 100,
    ) -> list[DefenderAction]:
        """List machine actions.

        Args:
            device_id: Filter by device ID.
            status: Filter by status.
            limit: Maximum actions to return.

        Returns:
            List of DefenderAction objects.
        """
        params = {"$top": limit}

        filters = []
        if device_id:
            filters.append(f"machineId eq '{device_id}'")
        if status:
            filters.append(f"status eq '{status.value}'")

        if filters:
            params["$filter"] = " and ".join(filters)

        result = await self._request("GET", "/machineactions", params=params)
        return [DefenderAction(**action) for action in result.get("value", [])]

    # =========================================================================
    # Live Response
    # =========================================================================

    async def start_live_response(
        self,
        device_id: str,
    ) -> LiveResponseSession:
        """Start a live response session on device.

        Args:
            device_id: Device ID to connect to.

        Returns:
            LiveResponseSession with session details.
        """
        data = {"machineId": device_id}
        result = await self._request(
            "POST",
            "/machines/liveResponseSessions",
            json=data,
        )
        return LiveResponseSession(**result)

    async def run_live_response_command(
        self,
        session_id: str,
        command: str,
    ) -> LiveResponseCommand:
        """Run a command in a live response session.

        Args:
            session_id: Live response session ID.
            command: Command to execute.

        Returns:
            LiveResponseCommand with results.
        """
        data = {"Commands": [{"type": "RunScript", "params": [{"key": "ScriptName", "value": command}]}]}
        result = await self._request(
            "POST",
            f"/machines/liveResponseSessions/{session_id}/runCommand",
            json=data,
        )
        return LiveResponseCommand(**result)

    async def get_live_response_result(
        self,
        session_id: str,
        command_index: int,
    ) -> LiveResponseCommand:
        """Get result of a live response command.

        Args:
            session_id: Session ID.
            command_index: Index of the command.

        Returns:
            LiveResponseCommand with results.
        """
        result = await self._request(
            "GET",
            f"/machines/liveResponseSessions/{session_id}/commandresults/{command_index}",
        )
        return LiveResponseCommand(**result)

    # =========================================================================
    # Investigation
    # =========================================================================

    async def get_investigation(
        self,
        investigation_id: str,
    ) -> DefenderInvestigation:
        """Get automated investigation details.

        Args:
            investigation_id: Investigation ID.

        Returns:
            DefenderInvestigation with details.
        """
        result = await self._request("GET", f"/investigations/{investigation_id}")
        return DefenderInvestigation(**result)

    async def start_investigation(
        self,
        device_id: str,
        comment: str,
    ) -> DefenderInvestigation:
        """Start automated investigation on device.

        Args:
            device_id: Device ID to investigate.
            comment: Reason for investigation.

        Returns:
            DefenderInvestigation tracking the investigation.
        """
        data = {
            "machineId": device_id,
            "comment": comment,
        }
        result = await self._request(
            "POST",
            "/investigations",
            json=data,
        )
        return DefenderInvestigation(**result)

    # =========================================================================
    # CollectionAdapter Interface Implementation
    # =========================================================================

    async def list_endpoints(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        online_only: bool = False,
    ) -> list[Endpoint]:
        """List endpoints (implements CollectionAdapter)."""
        filter_query = None
        if online_only:
            filter_query = "healthStatus eq 'Active'"
        if search:
            search_filter = (
                f"contains(computerDnsName, '{search}') or "
                f"contains(lastIpAddress, '{search}')"
            )
            if filter_query:
                filter_query = f"({filter_query}) and ({search_filter})"
            else:
                filter_query = search_filter

        devices = await self.list_devices(limit, offset, filter_query)

        return [
            Endpoint(
                client_id=device.id,
                hostname=device.computer_dns_name or "",
                os=device.os_platform,
                os_version=device.os_version,
                ip_addresses=[device.last_ip_address] if device.last_ip_address else [],
                last_seen=device.last_seen,
                online=device.health_status == "Active" if device.health_status else False,
                labels={tag: "true" for tag in device.machine_tags},
                metadata={
                    "aad_device_id": device.aad_device_id,
                    "risk_score": device.risk_score.value if device.risk_score else None,
                    "exposure_level": device.exposure_level,
                },
            )
            for device in devices
        ]

    async def get_endpoint(self, client_id: str) -> Endpoint | None:
        """Get endpoint by ID (implements CollectionAdapter)."""
        device = await self.get_device(client_id)
        if not device:
            return None

        return Endpoint(
            client_id=device.id,
            hostname=device.computer_dns_name or "",
            os=device.os_platform,
            os_version=device.os_version,
            ip_addresses=[device.last_ip_address] if device.last_ip_address else [],
            last_seen=device.last_seen,
            online=device.health_status == "Active" if device.health_status else False,
            labels={tag: "true" for tag in device.machine_tags},
        )

    async def search_endpoints(self, query: str) -> list[Endpoint]:
        """Search endpoints (implements CollectionAdapter)."""
        return await self.list_endpoints(search=query)

    async def list_artifacts(
        self,
        category: str | None = None,
    ) -> list[CollectionArtifact]:
        """List available collection artifacts.

        Defender has limited artifact collection compared to Velociraptor.
        Returns the available response action types.
        """
        return [
            CollectionArtifact(
                name="investigation_package",
                description="Collect forensic investigation package",
                category="collection",
            ),
            CollectionArtifact(
                name="antivirus_scan",
                description="Run antivirus scan (Quick or Full)",
                category="scan",
                parameters={"scan_type": ["Quick", "Full"]},
            ),
        ]

    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: dict[str, Any] | None = None,
        urgent: bool = False,
    ) -> CollectionJob:
        """Collect artifact from endpoint (implements CollectionAdapter)."""
        params = parameters or {}
        comment = params.get("comment", "Collected via Eleanor")

        if artifact_name == "investigation_package":
            action = await self.collect_investigation_package(client_id, comment)
        elif artifact_name == "antivirus_scan":
            scan_type = params.get("scan_type", "Quick")
            action = await self.run_antivirus_scan(client_id, comment, scan_type)
        else:
            raise ValueError(f"Unknown artifact: {artifact_name}")

        return CollectionJob(
            job_id=action.id,
            client_id=client_id,
            artifact_name=artifact_name,
            status=action.status.value if action.status else "pending",
            started_at=action.creation_date_time_utc,
        )

    async def get_collection_status(self, job_id: str) -> CollectionJob:
        """Get collection job status (implements CollectionAdapter)."""
        action = await self.get_action_status(job_id)
        return CollectionJob(
            job_id=action.id,
            client_id=action.machine_id or "",
            artifact_name=action.type.value if action.type else "",
            status=action.status.value if action.status else "pending",
            started_at=action.creation_date_time_utc,
            completed_at=action.last_update_date_time_utc
            if action.status in (ActionStatus.SUCCEEDED, ActionStatus.FAILED)
            else None,
            error=action.troubleshoot_info,
        )

    async def get_collection_results(
        self,
        job_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get collection results (implements CollectionAdapter).

        Note: Defender investigation packages need to be downloaded separately.
        """
        action = await self.get_action_status(job_id)
        return [action.model_dump()]

    async def list_hunts(
        self,
        limit: int = 50,
        state: str | None = None,
    ) -> list[Hunt]:
        """List hunts (not supported in Defender - returns empty)."""
        return []

    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        target_labels: dict[str, str] | None = None,
        expires_hours: int = 168,
    ) -> Hunt:
        """Create hunt (not supported in Defender)."""
        raise NotImplementedError("Hunts are not supported in Microsoft Defender")

    async def start_hunt(self, hunt_id: str) -> Hunt:
        """Start hunt (not supported in Defender)."""
        raise NotImplementedError("Hunts are not supported in Microsoft Defender")

    async def stop_hunt(self, hunt_id: str) -> Hunt:
        """Stop hunt (not supported in Defender)."""
        raise NotImplementedError("Hunts are not supported in Microsoft Defender")

    async def get_hunt_results(
        self,
        hunt_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get hunt results (not supported in Defender)."""
        raise NotImplementedError("Hunts are not supported in Microsoft Defender")

    async def isolate_host(self, client_id: str) -> bool:
        """Isolate host (implements CollectionAdapter)."""
        try:
            await self.isolate_device(client_id, "Isolated via Eleanor")
            return True
        except Exception as e:
            logger.error("Failed to isolate device %s: %s", client_id, e)
            return False

    async def unisolate_host(self, client_id: str) -> bool:
        """Unisolate host (implements CollectionAdapter)."""
        try:
            await self.unisolate_device(client_id, "Unisolated via Eleanor")
            return True
        except Exception as e:
            logger.error("Failed to unisolate device %s: %s", client_id, e)
            return False

    async def quarantine_file(
        self,
        client_id: str,
        file_path: str,
    ) -> bool:
        """Quarantine file (implements CollectionAdapter).

        Note: Defender uses SHA1 hash, not file path.
        The file_path parameter is treated as SHA1 hash.
        """
        try:
            await self.stop_and_quarantine_file(
                client_id,
                file_path,  # Actually SHA1
                "Quarantined via Eleanor",
            )
            return True
        except Exception as e:
            logger.error("Failed to quarantine file %s: %s", file_path, e)
            return False

    async def kill_process(
        self,
        client_id: str,
        pid: int,
    ) -> bool:
        """Kill process (requires live response session)."""
        try:
            # Start live response session
            session = await self.start_live_response(client_id)

            # Run taskkill command
            await self.run_live_response_command(
                session.id,
                f"taskkill /PID {pid} /F",
            )
            return True
        except Exception as e:
            logger.error("Failed to kill process %s on %s: %s", pid, client_id, e)
            return False
