"""Splunk SIEM adapter for bidirectional integration.

PATTERN: Adapter Pattern
Implements SIEMAdapter to integrate with Splunk Enterprise/Cloud for
bidirectional data flow, saved searches, and alert management.

Provides:
- Event querying via Splunk REST API
- Event ingestion via HTTP Event Collector (HEC)
- Saved search management
- Alert retrieval and management
- Index information
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    IndexInfo,
    SavedSearch,
    Severity,
    SIEMAdapter,
    SIEMAlert,
    TimelineEvent,
)

logger = logging.getLogger(__name__)


class SplunkAdapter(SIEMAdapter):
    """Splunk Enterprise/Cloud adapter.

    PATTERN: Adapter Pattern
    Provides bidirectional integration with Splunk for event
    querying, ingestion, and management.

    Configuration:
        url: Splunk management URL (e.g., https://splunk.local:8089)
        username: Splunk username
        password: Splunk password or auth token
        hec_url: HEC endpoint (e.g., https://splunk.local:8088)
        hec_token: HEC authentication token
        default_index: Default index for event ingestion
        verify_ssl: Verify SSL certificates

    DESIGN DECISION: Uses both REST API (for queries/management) and
    HEC (for event ingestion) for optimal performance.
    """

    name = "splunk"
    description = "Splunk Enterprise/Cloud SIEM"

    def __init__(self, config: AdapterConfig):
        """Initialize Splunk adapter.

        Args:
            config: Adapter configuration with Splunk credentials
        """
        super().__init__(config)
        self.url = config.url.rstrip("/")
        self.username = config.username
        self.password = config.api_key  # Password/token in api_key field
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl

        # HEC configuration
        self.hec_url = config.extra.get("hec_url", "").rstrip("/")
        self.hec_token = config.extra.get("hec_token", "")
        self.default_index = config.extra.get("default_index", "main")

        # API endpoints
        self.api_base = f"{self.url}/services"

    def _get_auth(self) -> tuple[str, str]:
        """Get authentication tuple for REST API."""
        return (self.username, self.password)

    def _get_hec_headers(self) -> dict[str, str]:
        """Get headers for HEC requests."""
        return {
            "Authorization": f"Splunk {self.hec_token}",
            "Content-Type": "application/json",
        }

    async def health_check(self) -> AdapterHealth:
        """Check Splunk connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/server/info",
                    auth=self._get_auth(),
                    params={"output_mode": "json"},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    entry = data.get("entry", [{}])[0]
                    content = entry.get("content", {})

                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        version=content.get("version"),
                        message=f"Connected to {content.get('serverName', 'Splunk')}",
                        details={
                            "server_name": content.get("serverName"),
                            "build": content.get("build"),
                            "os_name": content.get("os_name"),
                            "license_state": content.get("license_state"),
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
            "username": self.username,
            "hec_configured": bool(self.hec_url and self.hec_token),
            "default_index": self.default_index,
        }

    # Timeline methods (inherited from TimelineAdapter)

    async def search_events(
        self,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Search events using SPL query."""
        import httpx

        # Build SPL query
        spl = query
        if not query.strip().startswith("|"):
            # Add index if not specified
            if "index=" not in query.lower():
                spl = f"index=* {query}"

        # Add time range
        params: dict[str, Any] = {
            "output_mode": "json",
            "count": limit,
            "search": f"search {spl}",
        }

        if start_time:
            params["earliest_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        if end_time:
            params["latest_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%S")

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            # Create search job
            response = await client.post(
                f"{self.api_base}/search/jobs",
                auth=self._get_auth(),
                data=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            job_data = response.json()
            job_id = job_data.get("sid")

            if not job_id:
                return []

            # Wait for job completion
            await self._wait_for_job(client, job_id)

            # Get results
            results_response = await client.get(
                f"{self.api_base}/search/jobs/{job_id}/results",
                auth=self._get_auth(),
                params={"output_mode": "json", "count": limit},
                timeout=self.timeout,
            )
            results_response.raise_for_status()
            results_data = results_response.json()

        return results_data.get("results", [])

    async def stream_events(
        self,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AsyncIterator[TimelineEvent]:
        """Stream events from search results."""
        results = await self.search_events(query, start_time, end_time, limit=10000)

        for result in results:
            yield self._parse_event(result)

    async def get_event(self, event_id: str) -> TimelineEvent | None:
        """Get a specific event by ID."""
        # Splunk doesn't have direct event ID lookup; search by _cd
        results = await self.search_events(f'_cd="{event_id}"', limit=1)
        if results:
            return self._parse_event(results[0])
        return None

    async def get_event_context(
        self,
        event_id: str,
        before: int = 5,
        after: int = 5,
    ) -> list[TimelineEvent]:
        """Get events around a specific event."""
        # This requires knowing the event's timestamp and source
        event = await self.get_event(event_id)
        if not event or not event.timestamp:
            return []

        # Search for events in time window around the event
        start = event.timestamp
        end = event.timestamp

        # This is a simplified implementation
        results = await self.search_events(
            query=f'source="{event.metadata.get("source", "*")}"',
            start_time=start,
            end_time=end,
            limit=before + after + 1,
        )

        return [self._parse_event(r) for r in results]

    # SIEMAdapter methods

    async def send_events(
        self,
        events: list[dict[str, Any]],
        index: str | None = None,
        source: str = "eleanor",
        sourcetype: str = "eleanor:events",
    ) -> int:
        """Send events via HEC."""
        import httpx

        if not self.hec_url or not self.hec_token:
            raise ValueError("HEC not configured")

        target_index = index or self.default_index
        sent_count = 0

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            for event_data in events:
                payload = {
                    "index": target_index,
                    "source": source,
                    "sourcetype": sourcetype,
                    "event": event_data,
                }

                if "time" in event_data:
                    payload["time"] = event_data["time"]
                elif "timestamp" in event_data:
                    timestamp = event_data["timestamp"]
                    if isinstance(timestamp, datetime):
                        payload["time"] = timestamp.timestamp()
                    elif isinstance(timestamp, str):
                        payload["time"] = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        ).timestamp()

                try:
                    response = await client.post(
                        f"{self.hec_url}/services/collector/event",
                        headers=self._get_hec_headers(),
                        json=payload,
                        timeout=30,
                    )
                    if response.status_code == 200:
                        sent_count += 1
                except Exception as error:
                    logger.warning(
                        "Failed to send event to Splunk HEC",
                        extra={"error": str(error)},
                    )

        logger.info(
            "Sent events to Splunk HEC",
            extra={
                "sent_count": sent_count,
                "total_count": len(events),
                "index": target_index,
            },
        )
        return sent_count

    async def send_event(
        self,
        event: dict[str, Any],
        index: str | None = None,
        source: str = "eleanor",
        sourcetype: str = "eleanor:events",
    ) -> bool:
        """Send a single event via HEC."""
        count = await self.send_events([event], index, source, sourcetype)
        return count == 1

    async def list_saved_searches(
        self,
        owner: str | None = None,
        scheduled_only: bool = False,
        limit: int = 100,
    ) -> list[SavedSearch]:
        """List saved searches."""
        import httpx

        params: dict[str, Any] = {
            "output_mode": "json",
            "count": limit,
        }

        if owner:
            params["search"] = f"eai:acl.owner={owner}"

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/saved/searches",
                auth=self._get_auth(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        searches = []
        for entry in data.get("entry", []):
            content = entry.get("content", {})

            # Filter scheduled if requested
            if scheduled_only and not content.get("is_scheduled"):
                continue

            searches.append(
                SavedSearch(
                    search_id=entry.get("name", ""),
                    name=entry.get("name", ""),
                    query=content.get("search", ""),
                    description=content.get("description", ""),
                    owner=entry.get("acl", {}).get("owner"),
                    is_scheduled=content.get("is_scheduled", False),
                    schedule=content.get("cron_schedule"),
                    enabled=not content.get("disabled", False),
                    metadata={
                        "app": entry.get("acl", {}).get("app"),
                        "dispatch_earliest": content.get("dispatch.earliest_time"),
                        "dispatch_latest": content.get("dispatch.latest_time"),
                    },
                )
            )

        return searches

    async def get_saved_search(self, search_id: str) -> SavedSearch | None:
        """Get a saved search by name."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/saved/searches/{search_id}",
                    auth=self._get_auth(),
                    params={"output_mode": "json"},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

            entries = data.get("entry", [])
            if not entries:
                return None

            entry = entries[0]
            content = entry.get("content", {})

            return SavedSearch(
                search_id=entry.get("name", ""),
                name=entry.get("name", ""),
                query=content.get("search", ""),
                description=content.get("description", ""),
                owner=entry.get("acl", {}).get("owner"),
                is_scheduled=content.get("is_scheduled", False),
                schedule=content.get("cron_schedule"),
                enabled=not content.get("disabled", False),
            )

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def create_saved_search(
        self,
        name: str,
        query: str,
        description: str | None = None,
        schedule: str | None = None,
        enabled: bool = True,
    ) -> SavedSearch:
        """Create a new saved search."""
        import httpx

        payload = {
            "name": name,
            "search": query,
            "output_mode": "json",
        }

        if description:
            payload["description"] = description

        if schedule:
            payload["is_scheduled"] = "1"
            payload["cron_schedule"] = schedule

        if not enabled:
            payload["disabled"] = "1"

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/saved/searches",
                auth=self._get_auth(),
                data=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        # Fetch the created search
        search = await self.get_saved_search(name)
        if not search:
            raise ValueError(f"Failed to create saved search: {name}")
        return search

    async def update_saved_search(
        self,
        search_id: str,
        name: str | None = None,
        query: str | None = None,
        description: str | None = None,
        schedule: str | None = None,
        enabled: bool | None = None,
    ) -> SavedSearch:
        """Update a saved search."""
        import httpx

        payload: dict[str, Any] = {"output_mode": "json"}

        if query is not None:
            payload["search"] = query
        if description is not None:
            payload["description"] = description
        if schedule is not None:
            payload["cron_schedule"] = schedule
            payload["is_scheduled"] = "1" if schedule else "0"
        if enabled is not None:
            payload["disabled"] = "0" if enabled else "1"

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/saved/searches/{search_id}",
                auth=self._get_auth(),
                data=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        search = await self.get_saved_search(search_id)
        if not search:
            raise ValueError(f"Failed to update saved search: {search_id}")
        return search

    async def delete_saved_search(self, search_id: str) -> bool:
        """Delete a saved search."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.delete(
                    f"{self.api_base}/saved/searches/{search_id}",
                    auth=self._get_auth(),
                    timeout=self.timeout,
                )
                return response.status_code in (200, 204)
        except Exception:
            return False

    async def run_saved_search(
        self,
        search_id: str,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Run a saved search."""
        import httpx

        params: dict[str, Any] = {"output_mode": "json"}

        if earliest_time:
            params["dispatch.earliest_time"] = earliest_time.strftime("%Y-%m-%dT%H:%M:%S")
        if latest_time:
            params["dispatch.latest_time"] = latest_time.strftime("%Y-%m-%dT%H:%M:%S")

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            # Dispatch the saved search
            response = await client.post(
                f"{self.api_base}/saved/searches/{search_id}/dispatch",
                auth=self._get_auth(),
                data=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            job_id = data.get("sid")

            if not job_id:
                return []

            # Wait for job
            await self._wait_for_job(client, job_id)

            # Get results
            results_response = await client.get(
                f"{self.api_base}/search/jobs/{job_id}/results",
                auth=self._get_auth(),
                params={"output_mode": "json", "count": 10000},
                timeout=self.timeout,
            )
            results_response.raise_for_status()
            return results_response.json().get("results", [])

    async def list_alerts(
        self,
        severity: Severity | None = None,
        status: str | None = None,
        earliest_time: datetime | None = None,
        latest_time: datetime | None = None,
        limit: int = 100,
    ) -> list[SIEMAlert]:
        """List triggered alerts."""
        import httpx

        params: dict[str, Any] = {
            "output_mode": "json",
            "count": limit,
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/alerts/fired_alerts",
                auth=self._get_auth(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        alerts = []
        for entry in data.get("entry", []):
            content = entry.get("content", {})

            trigger_time = self._parse_timestamp(content.get("trigger_time"))

            # Filter by time if specified
            if earliest_time and trigger_time and trigger_time < earliest_time:
                continue
            if latest_time and trigger_time and trigger_time > latest_time:
                continue

            alert_severity = self._map_severity(content.get("severity", 3))
            if severity and alert_severity != severity:
                continue

            alerts.append(
                SIEMAlert(
                    alert_id=entry.get("name", ""),
                    name=content.get("savedsearch_name", ""),
                    description=content.get("description", ""),
                    severity=alert_severity,
                    status=content.get("state", "unknown"),
                    trigger_time=trigger_time,
                    source_search=content.get("savedsearch_name"),
                    result_count=content.get("triggered_alert_count", 0),
                    metadata={
                        "app": entry.get("acl", {}).get("app"),
                        "owner": entry.get("acl", {}).get("owner"),
                    },
                )
            )

        return alerts

    async def get_alert(self, alert_id: str) -> SIEMAlert | None:
        """Get an alert by ID."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/alerts/fired_alerts/{alert_id}",
                    auth=self._get_auth(),
                    params={"output_mode": "json"},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

            entries = data.get("entry", [])
            if not entries:
                return None

            entry = entries[0]
            content = entry.get("content", {})

            return SIEMAlert(
                alert_id=entry.get("name", ""),
                name=content.get("savedsearch_name", ""),
                severity=self._map_severity(content.get("severity", 3)),
                status=content.get("state", "unknown"),
                trigger_time=self._parse_timestamp(content.get("trigger_time")),
                source_search=content.get("savedsearch_name"),
            )

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def update_alert_status(
        self,
        alert_id: str,
        status: str,
        comment: str | None = None,
    ) -> SIEMAlert:
        """Update alert status (acknowledgement)."""
        import httpx

        # Splunk alert status is limited; we can acknowledge
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/alerts/fired_alerts/{alert_id}",
                auth=self._get_auth(),
                data={"output_mode": "json"},
                timeout=self.timeout,
            )
            response.raise_for_status()

        alert = await self.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        return alert

    async def list_indexes(self) -> list[IndexInfo]:
        """List available indexes."""
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/data/indexes",
                auth=self._get_auth(),
                params={"output_mode": "json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        indexes = []
        for entry in data.get("entry", []):
            content = entry.get("content", {})

            indexes.append(
                IndexInfo(
                    name=entry.get("name", ""),
                    event_count=int(content.get("totalEventCount", 0)),
                    size_bytes=int(content.get("currentDBSizeMB", 0)) * 1024 * 1024,
                    earliest_time=self._parse_timestamp(content.get("minTime")),
                    latest_time=self._parse_timestamp(content.get("maxTime")),
                    metadata={
                        "frozen_path": content.get("frozenTimePeriodInSecs"),
                        "max_size": content.get("maxTotalDataSizeMB"),
                        "data_type": content.get("datatype"),
                    },
                )
            )

        return indexes

    async def get_index_info(self, index_name: str) -> IndexInfo | None:
        """Get information about an index."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/data/indexes/{index_name}",
                    auth=self._get_auth(),
                    params={"output_mode": "json"},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

            entries = data.get("entry", [])
            if not entries:
                return None

            entry = entries[0]
            content = entry.get("content", {})

            return IndexInfo(
                name=entry.get("name", ""),
                event_count=int(content.get("totalEventCount", 0)),
                size_bytes=int(content.get("currentDBSizeMB", 0)) * 1024 * 1024,
                earliest_time=self._parse_timestamp(content.get("minTime")),
                latest_time=self._parse_timestamp(content.get("maxTime")),
            )

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    # Helper methods

    async def _wait_for_job(self, client, job_id: str, timeout: int = 300) -> None:
        """Wait for a search job to complete."""
        import asyncio

        start_time = datetime.now(UTC)
        while True:
            response = await client.get(
                f"{self.api_base}/search/jobs/{job_id}",
                auth=self._get_auth(),
                params={"output_mode": "json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})

            if content.get("isDone"):
                return

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(f"Search job {job_id} timed out")

            await asyncio.sleep(1)

    def _parse_event(self, result: dict[str, Any]) -> TimelineEvent:
        """Parse Splunk result to TimelineEvent."""
        # Parse timestamp
        timestamp = None
        if "_time" in result:
            try:
                timestamp = datetime.fromisoformat(result["_time"].replace("Z", "+00:00"))
            except ValueError:
                pass

        if not timestamp:
            timestamp = datetime.now(UTC)

        return TimelineEvent(
            event_id=result.get("_cd", ""),
            timestamp=timestamp,
            message=result.get("_raw", ""),
            source=result.get("source", ""),
            source_type=result.get("sourcetype", ""),
            metadata={
                "index": result.get("index"),
                "host": result.get("host"),
                "splunk_server": result.get("splunk_server"),
            },
        )

    def _parse_timestamp(self, value: str | int | None) -> datetime | None:
        """Parse Splunk timestamp."""
        if not value:
            return None

        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, tz=UTC)
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OSError):
            return None

    def _map_severity(self, level: int) -> Severity:
        """Map Splunk severity level to Severity enum."""
        if level >= 5:
            return Severity.CRITICAL
        elif level >= 4:
            return Severity.HIGH
        elif level >= 3:
            return Severity.MEDIUM
        else:
            return Severity.LOW
