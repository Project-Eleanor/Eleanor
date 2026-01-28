"""Cortex SOAR adapter for analysis and response.

PATTERN: Adapter Pattern
Implements SOARAdapter to integrate with Cortex for automated
analysis and response actions.

Provides:
- Analyzer execution (VirusTotal, MISP, etc.)
- Responder execution (containment, blocking)
- Job management and results
- Analyzer/Responder configuration
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    PlaybookExecution,
    PlaybookStatus,
    SOARAdapter,
)

logger = logging.getLogger(__name__)


class CortexAdapter(SOARAdapter):
    """Cortex analysis and response adapter.

    PATTERN: Adapter Pattern
    Provides integration with Cortex for running analyzers and
    responders on observables.

    Configuration:
        url: Cortex instance URL
        api_key: Cortex API key
        organisation: Organisation name (for multi-tenant)

    DESIGN DECISION: Maps Cortex analyzers/responders to Eleanor's
    playbook concept for unified SOAR interface.
    """

    name = "cortex"
    description = "Cortex analysis and response platform"

    def __init__(self, config: AdapterConfig):
        """Initialize Cortex adapter.

        Args:
            config: Adapter configuration with Cortex credentials
        """
        super().__init__(config)
        self.url = config.url.rstrip("/")
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl

        # Extra config
        self.organisation = config.extra.get("organisation", "")

        # API base
        self.api_base = f"{self.url}/api"

    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.organisation:
            headers["X-Organisation"] = self.organisation
        return headers

    async def health_check(self) -> AdapterHealth:
        """Check Cortex connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/status",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        version=data.get("versions", {}).get("Cortex"),
                        message="Connected to Cortex",
                        details={
                            "elasticsearch": data.get("versions", {}).get("Elasticsearch"),
                        },
                    )
                elif response.status_code == 401:
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.AUTH_ERROR,
                        message="Authentication failed",
                    )
                else:
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.ERROR,
                        message=f"HTTP {response.status_code}",
                    )

        except Exception as error:
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(error),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get sanitized configuration."""
        return {
            "url": self.url,
            "api_key_configured": bool(self.api_key),
            "organisation": self.organisation,
        }

    async def list_playbooks(self, tags: list[str] | None = None) -> list[dict[str, Any]]:
        """List available analyzers as playbooks."""
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            # Get analyzers
            response = await client.get(
                f"{self.api_base}/analyzer",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            analyzers = response.json()

            # Get responders
            response = await client.get(
                f"{self.api_base}/responder",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            responders = response.json()

        playbooks = []

        # Convert analyzers to playbooks
        for analyzer in analyzers:
            if not analyzer.get("enabled", True):
                continue

            playbook = {
                "id": f"analyzer:{analyzer['id']}",
                "name": analyzer.get("name", ""),
                "description": analyzer.get("description", ""),
                "type": "analyzer",
                "data_types": analyzer.get("dataTypeList", []),
                "enabled": True,
                "tags": ["analyzer"] + analyzer.get("dataTypeList", []),
            }

            # Filter by tags if specified
            if tags:
                if not any(tag in playbook["tags"] for tag in tags):
                    continue

            playbooks.append(playbook)

        # Convert responders to playbooks
        for responder in responders:
            if not responder.get("enabled", True):
                continue

            playbook = {
                "id": f"responder:{responder['id']}",
                "name": responder.get("name", ""),
                "description": responder.get("description", ""),
                "type": "responder",
                "data_types": responder.get("dataTypeList", []),
                "enabled": True,
                "tags": ["responder"] + responder.get("dataTypeList", []),
            }

            if tags:
                if not any(tag in playbook["tags"] for tag in tags):
                    continue

            playbooks.append(playbook)

        return playbooks

    async def run_playbook(
        self,
        playbook_id: str,
        parameters: dict[str, Any],
        target: str | None = None,
    ) -> PlaybookExecution:
        """Run an analyzer or responder.

        Args:
            playbook_id: Format "analyzer:<id>" or "responder:<id>"
            parameters: Must include "data" (the observable value) and "dataType"
            target: Optional target identifier

        Returns:
            Execution job information
        """
        import httpx

        # Parse playbook ID
        parts = playbook_id.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid playbook ID format: {playbook_id}")

        playbook_type, cortex_id = parts

        # Build payload
        payload = {
            "data": parameters.get("data", target or ""),
            "dataType": parameters.get("dataType", "other"),
            "message": parameters.get("message", "Executed from Eleanor"),
        }

        # Add TLP if specified
        if "tlp" in parameters:
            payload["tlp"] = parameters["tlp"]

        # Additional parameters for the analyzer/responder
        if "parameters" in parameters:
            payload["parameters"] = parameters["parameters"]

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            if playbook_type == "analyzer":
                response = await client.post(
                    f"{self.api_base}/analyzer/{cortex_id}/run",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=self.timeout,
                )
            elif playbook_type == "responder":
                response = await client.post(
                    f"{self.api_base}/responder/{cortex_id}/run",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=self.timeout,
                )
            else:
                raise ValueError(f"Unknown playbook type: {playbook_type}")

            response.raise_for_status()
            data = response.json()

        return PlaybookExecution(
            execution_id=data.get("id", ""),
            playbook_id=playbook_id,
            status=self._map_status(data.get("status", "Waiting")),
            started_at=self._parse_timestamp(data.get("startDate")),
            parameters=parameters,
            metadata={
                "cortex_id": cortex_id,
                "type": playbook_type,
                "analyzer_name": data.get("analyzerName"),
                "responder_name": data.get("responderName"),
            },
        )

    async def get_execution(self, execution_id: str) -> PlaybookExecution | None:
        """Get analyzer/responder job status."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/job/{execution_id}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

            # Determine playbook type from job data
            playbook_type = "analyzer"
            cortex_id = data.get("analyzerId", "")
            if data.get("responderId"):
                playbook_type = "responder"
                cortex_id = data["responderId"]

            return PlaybookExecution(
                execution_id=execution_id,
                playbook_id=f"{playbook_type}:{cortex_id}",
                status=self._map_status(data.get("status", "Unknown")),
                started_at=self._parse_timestamp(data.get("startDate")),
                completed_at=self._parse_timestamp(data.get("endDate")),
                result=data.get("report"),
                error=data.get("errorMessage"),
                metadata={
                    "cortex_id": cortex_id,
                    "type": playbook_type,
                    "data": data.get("data"),
                    "data_type": data.get("dataType"),
                },
            )

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def get_execution_results(self, execution_id: str) -> dict[str, Any]:
        """Get full results of an analyzer/responder job."""
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/job/{execution_id}/report",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running job (not supported by Cortex)."""
        # Cortex doesn't support job cancellation
        logger.warning(
            "Job cancellation not supported by Cortex",
            extra={"execution_id": execution_id},
        )
        return False

    async def list_executions(
        self,
        playbook_id: str | None = None,
        status: PlaybookStatus | None = None,
        limit: int = 50,
    ) -> list[PlaybookExecution]:
        """List recent analyzer/responder jobs."""
        import httpx

        params: dict[str, Any] = {
            "range": f"0-{limit}",
            "sort": "-startDate",
        }

        if status:
            params["status"] = self._status_to_cortex(status)

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/job",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            jobs = response.json()

        executions = []
        for job in jobs:
            # Determine playbook type
            playbook_type = "analyzer"
            cortex_id = job.get("analyzerId", "")
            if job.get("responderId"):
                playbook_type = "responder"
                cortex_id = job["responderId"]

            job_playbook_id = f"{playbook_type}:{cortex_id}"

            # Filter by playbook if specified
            if playbook_id and job_playbook_id != playbook_id:
                continue

            executions.append(
                PlaybookExecution(
                    execution_id=job.get("id", ""),
                    playbook_id=job_playbook_id,
                    status=self._map_status(job.get("status", "Unknown")),
                    started_at=self._parse_timestamp(job.get("startDate")),
                    completed_at=self._parse_timestamp(job.get("endDate")),
                    error=job.get("errorMessage"),
                    metadata={
                        "cortex_id": cortex_id,
                        "type": playbook_type,
                        "data": job.get("data"),
                        "data_type": job.get("dataType"),
                    },
                )
            )

        return executions

    # Additional Cortex-specific methods

    async def get_analyzers_for_type(self, data_type: str) -> list[dict[str, Any]]:
        """Get analyzers that can process a specific data type.

        Args:
            data_type: Observable type (e.g., "ip", "domain", "hash")

        Returns:
            List of applicable analyzers
        """
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/analyzer/type/{data_type}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def get_responders_for_type(self, data_type: str) -> list[dict[str, Any]]:
        """Get responders that can handle a specific data type.

        Args:
            data_type: Entity type (e.g., "thehive:case", "thehive:alert")

        Returns:
            List of applicable responders
        """
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/responder/type/{data_type}",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def run_analyzer(
        self,
        analyzer_id: str,
        data: str,
        data_type: str,
        tlp: int = 2,
        message: str | None = None,
    ) -> PlaybookExecution:
        """Convenience method to run an analyzer.

        Args:
            analyzer_id: Cortex analyzer ID
            data: Observable value
            data_type: Observable type
            tlp: Traffic Light Protocol level
            message: Optional description

        Returns:
            Execution information
        """
        return await self.run_playbook(
            f"analyzer:{analyzer_id}",
            {
                "data": data,
                "dataType": data_type,
                "tlp": tlp,
                "message": message or f"Analysis of {data_type}: {data}",
            },
        )

    async def run_responder(
        self,
        responder_id: str,
        data: dict[str, Any],
        data_type: str,
        tlp: int = 2,
        message: str | None = None,
    ) -> PlaybookExecution:
        """Convenience method to run a responder.

        Args:
            responder_id: Cortex responder ID
            data: Entity data (varies by responder)
            data_type: Entity type (e.g., "thehive:case")
            tlp: Traffic Light Protocol level
            message: Optional description

        Returns:
            Execution information
        """
        return await self.run_playbook(
            f"responder:{responder_id}",
            {
                "data": data,
                "dataType": data_type,
                "tlp": tlp,
                "message": message or f"Response action on {data_type}",
            },
        )

    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 2.0,
    ) -> PlaybookExecution:
        """Wait for a job to complete.

        Args:
            job_id: Job/execution ID
            timeout_seconds: Maximum wait time
            poll_interval: Seconds between status checks

        Returns:
            Completed execution

        Raises:
            TimeoutError: If job doesn't complete in time
        """
        import asyncio

        start_time = datetime.now(UTC)
        while True:
            execution = await self.get_execution(job_id)
            if not execution:
                raise ValueError(f"Job {job_id} not found")

            if execution.status in (PlaybookStatus.COMPLETED, PlaybookStatus.FAILED):
                return execution

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout_seconds}s")

            await asyncio.sleep(poll_interval)

    def _map_status(self, cortex_status: str) -> PlaybookStatus:
        """Map Cortex job status to PlaybookStatus."""
        status_map = {
            "Waiting": PlaybookStatus.PENDING,
            "InProgress": PlaybookStatus.RUNNING,
            "Success": PlaybookStatus.COMPLETED,
            "Failure": PlaybookStatus.FAILED,
            "Deleted": PlaybookStatus.CANCELLED,
        }
        return status_map.get(cortex_status, PlaybookStatus.PENDING)

    def _status_to_cortex(self, status: PlaybookStatus) -> str:
        """Map PlaybookStatus to Cortex status."""
        status_map = {
            PlaybookStatus.PENDING: "Waiting",
            PlaybookStatus.RUNNING: "InProgress",
            PlaybookStatus.COMPLETED: "Success",
            PlaybookStatus.FAILED: "Failure",
            PlaybookStatus.CANCELLED: "Deleted",
        }
        return status_map.get(status, "Waiting")

    def _parse_timestamp(self, value: int | None) -> datetime | None:
        """Parse Cortex timestamp (milliseconds since epoch)."""
        if not value:
            return None

        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except (ValueError, OSError):
            return None
