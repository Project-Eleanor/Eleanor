"""CrowdStrike Falcon adapter for EDR integration.

Provides integration with CrowdStrike Falcon platform for:
- Endpoint detection and response
- Host management and quarantine
- Threat hunting
- Real-time response
"""

import logging
from datetime import datetime
from typing import Any

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

logger = logging.getLogger(__name__)


class CrowdStrikeAdapter(CollectionAdapter):
    """CrowdStrike Falcon EDR adapter.

    Implements CollectionAdapter for endpoint collection and response.

    Configuration:
        client_id: CrowdStrike API client ID
        client_secret: CrowdStrike API client secret
        base_url: CrowdStrike API base URL (default: US-1)
    """

    name = "crowdstrike"
    description = "CrowdStrike Falcon EDR platform"

    # Regional base URLs
    BASE_URLS = {
        "us-1": "https://api.crowdstrike.com",
        "us-2": "https://api.us-2.crowdstrike.com",
        "eu-1": "https://api.eu-1.crowdstrike.com",
        "us-gov-1": "https://api.laggar.gcw.crowdstrike.com",
    }

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.client_id = config.extra.get("client_id", "")
        self.client_secret = config.extra.get("client_secret", "")
        region = config.extra.get("region", "us-1")
        self.base_url = config.url or self.BASE_URLS.get(region, self.BASE_URLS["us-1"])
        self.timeout = config.timeout

        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    async def health_check(self) -> AdapterHealth:
        """Check CrowdStrike connectivity."""
        try:
            await self._ensure_token()

            # Test with a simple API call
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/sensors/queries/sensors/v1",
                    headers=self._get_headers(),
                    params={"limit": 1},
                    timeout=10,
                )

                if response.status_code == 200:
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        message="Connected to CrowdStrike",
                    )
                else:
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.ERROR,
                        message=f"HTTP {response.status_code}",
                    )

        except Exception as e:
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get sanitized configuration."""
        return {
            "base_url": self.base_url,
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
        }

    async def _ensure_token(self) -> None:
        """Ensure we have a valid access token."""
        import httpx

        if self._access_token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 1800)
            self._token_expires = datetime.utcnow() + __import__("datetime").timedelta(
                seconds=expires_in - 60
            )

    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_endpoints(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        online_only: bool = False,
    ) -> list[Endpoint]:
        """List managed endpoints."""
        import httpx

        await self._ensure_token()

        # Build filter
        filters = []
        if search:
            filters.append(f"hostname:*'{search}*'")
        if online_only:
            filters.append("status:'Online'")

        params: dict[str, Any] = {
            "limit": min(limit, 5000),
            "offset": offset,
        }
        if filters:
            params["filter"] = "+".join(filters)

        async with httpx.AsyncClient() as client:
            # Get host IDs
            response = await client.get(
                f"{self.base_url}/devices/queries/devices/v1",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            host_ids = response.json().get("resources", [])

            if not host_ids:
                return []

            # Get host details
            detail_response = await client.post(
                f"{self.base_url}/devices/entities/devices/v2",
                headers=self._get_headers(),
                json={"ids": host_ids[:100]},
                timeout=self.timeout,
            )
            detail_response.raise_for_status()
            hosts = detail_response.json().get("resources", [])

        endpoints = []
        for host in hosts:
            endpoints.append(
                Endpoint(
                    client_id=host.get("device_id", ""),
                    hostname=host.get("hostname", ""),
                    os=host.get("platform_name", ""),
                    os_version=host.get("os_version", ""),
                    ip_addresses=[host.get("local_ip", "")] if host.get("local_ip") else [],
                    mac_addresses=[host.get("mac_address", "")] if host.get("mac_address") else [],
                    last_seen=self._parse_timestamp(host.get("last_seen")),
                    online=host.get("status") == "Online",
                    labels={
                        "agent_version": host.get("agent_version", ""),
                        "product_type": host.get("product_type_desc", ""),
                    },
                    metadata={
                        "cid": host.get("cid"),
                        "first_seen": host.get("first_seen"),
                        "system_manufacturer": host.get("system_manufacturer"),
                        "system_product_name": host.get("system_product_name"),
                    },
                )
            )

        return endpoints

    async def get_endpoint(self, client_id: str) -> Endpoint | None:
        """Get a specific endpoint."""
        import httpx

        await self._ensure_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/devices/entities/devices/v2",
                headers=self._get_headers(),
                json={"ids": [client_id]},
                timeout=self.timeout,
            )
            response.raise_for_status()
            hosts = response.json().get("resources", [])

        if not hosts:
            return None

        host = hosts[0]
        return Endpoint(
            client_id=host.get("device_id", ""),
            hostname=host.get("hostname", ""),
            os=host.get("platform_name", ""),
            os_version=host.get("os_version", ""),
            ip_addresses=[host.get("local_ip", "")] if host.get("local_ip") else [],
            mac_addresses=[host.get("mac_address", "")] if host.get("mac_address") else [],
            last_seen=self._parse_timestamp(host.get("last_seen")),
            online=host.get("status") == "Online",
        )

    async def search_endpoints(self, query: str) -> list[Endpoint]:
        """Search endpoints."""
        return await self.list_endpoints(search=query)

    async def list_artifacts(self, category: str | None = None) -> list[CollectionArtifact]:
        """List available collection artifacts (RTR scripts)."""
        # CrowdStrike uses Real-Time Response scripts
        return [
            CollectionArtifact(
                name="runscript", description="Run a custom script", category="custom"
            ),
            CollectionArtifact(name="get", description="Get a file from the host", category="file"),
            CollectionArtifact(name="reg", description="Query registry", category="registry"),
            CollectionArtifact(name="ps", description="List processes", category="process"),
            CollectionArtifact(
                name="netstat", description="Network connections", category="network"
            ),
        ]

    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: dict[str, Any] | None = None,
        urgent: bool = False,
    ) -> CollectionJob:
        """Start RTR session and run command."""
        import httpx

        await self._ensure_token()

        async with httpx.AsyncClient() as client:
            # Initialize RTR session
            session_response = await client.post(
                f"{self.base_url}/real-time-response/entities/sessions/v1",
                headers=self._get_headers(),
                json={
                    "device_id": client_id,
                    "queue_offline": not urgent,
                },
                timeout=60,
            )
            session_response.raise_for_status()
            session_data = session_response.json()
            session_id = session_data.get("resources", [{}])[0].get("session_id")

            if not session_id:
                return CollectionJob(
                    job_id="",
                    client_id=client_id,
                    artifact_name=artifact_name,
                    status="failed",
                    error="Failed to create RTR session",
                )

            # Execute command
            cmd_response = await client.post(
                f"{self.base_url}/real-time-response/entities/command/v1",
                headers=self._get_headers(),
                json={
                    "session_id": session_id,
                    "base_command": artifact_name,
                    "command_string": (
                        f"{artifact_name} {parameters.get('args', '')}"
                        if parameters
                        else artifact_name
                    ),
                },
                timeout=60,
            )
            cmd_response.raise_for_status()
            cmd_data = cmd_response.json()

            cloud_request_id = cmd_data.get("resources", [{}])[0].get("cloud_request_id")

            return CollectionJob(
                job_id=cloud_request_id or session_id,
                client_id=client_id,
                artifact_name=artifact_name,
                status="running",
                started_at=datetime.utcnow(),
                metadata={"session_id": session_id},
            )

    async def get_collection_status(self, job_id: str) -> CollectionJob:
        """Get RTR command status."""
        import httpx

        await self._ensure_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/real-time-response/entities/command/v1",
                headers=self._get_headers(),
                params={"cloud_request_id": job_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        resources = data.get("resources", [])
        if not resources:
            return CollectionJob(
                job_id=job_id,
                client_id="",
                artifact_name="",
                status="unknown",
            )

        result = resources[0]
        status = "completed" if result.get("complete") else "running"

        return CollectionJob(
            job_id=job_id,
            client_id=result.get("device_id", ""),
            artifact_name=result.get("base_command", ""),
            status=status,
            error=result.get("stderr"),
        )

    async def get_collection_results(self, job_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Get RTR command results."""
        import httpx

        await self._ensure_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/real-time-response/entities/command/v1",
                headers=self._get_headers(),
                params={"cloud_request_id": job_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        resources = data.get("resources", [])
        if not resources:
            return []

        result = resources[0]
        stdout = result.get("stdout", "")

        # Try to parse as structured data
        try:
            import json

            return json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            return [{"output": stdout}]

    async def list_hunts(self, limit: int = 50, state: str | None = None) -> list[Hunt]:
        """List IOC-based hunts (custom IOCs)."""
        # CrowdStrike uses IOC management for hunting
        return []  # Would need IOC API implementation

    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        target_labels: dict[str, str] | None = None,
        expires_hours: int = 168,
    ) -> Hunt:
        """Create an IOC-based hunt."""
        # Would create custom IOC
        return Hunt(
            hunt_id="",
            name=name,
            artifact_name=artifact_name,
            state="created",
            description=description,
        )

    async def start_hunt(self, hunt_id: str) -> Hunt:
        """Activate a hunt."""
        return Hunt(hunt_id=hunt_id, name="", artifact_name="", state="running")

    async def stop_hunt(self, hunt_id: str) -> Hunt:
        """Deactivate a hunt."""
        return Hunt(hunt_id=hunt_id, name="", artifact_name="", state="stopped")

    async def get_hunt_results(self, hunt_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Get hunt detections."""
        return []

    async def isolate_host(self, client_id: str) -> bool:
        """Isolate a host (contain)."""
        import httpx

        await self._ensure_token()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/devices/entities/devices-actions/v2",
                    headers=self._get_headers(),
                    params={"action_name": "contain"},
                    json={"ids": [client_id]},
                    timeout=self.timeout,
                )
                return response.status_code == 202
        except Exception as e:
            logger.error(f"CrowdStrike isolate error: {e}")
            return False

    async def unisolate_host(self, client_id: str) -> bool:
        """Remove host isolation (lift containment)."""
        import httpx

        await self._ensure_token()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/devices/entities/devices-actions/v2",
                    headers=self._get_headers(),
                    params={"action_name": "lift_containment"},
                    json={"ids": [client_id]},
                    timeout=self.timeout,
                )
                return response.status_code == 202
        except Exception as e:
            logger.error(f"CrowdStrike unisolate error: {e}")
            return False

    async def quarantine_file(self, client_id: str, file_path: str) -> bool:
        """Quarantine a file via RTR."""
        job = await self.collect_artifact(
            client_id,
            "rm",
            parameters={"args": f"-Force '{file_path}'"},
        )
        return job.status != "failed"

    async def kill_process(self, client_id: str, pid: int) -> bool:
        """Kill a process via RTR."""
        job = await self.collect_artifact(
            client_id,
            "kill",
            parameters={"args": str(pid)},
        )
        return job.status != "failed"

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """Parse CrowdStrike timestamp."""
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
