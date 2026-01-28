"""Microsoft Sentinel SIEM adapter implementation.

Provides integration with Microsoft Sentinel for:
- Incident management
- Alert retrieval
- KQL query execution
- Entity lookup
- Watchlist management
- Hunting queries
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    BaseAdapter,
    ExternalCase,
    Severity,
)
from app.adapters.sentinel.schemas import (
    IncidentClassification,
    IncidentSeverity,
    IncidentStatus,
    KQLQueryResult,
    SentinelAlert,
    SentinelAnalyticsRule,
    SentinelComment,
    SentinelEntity,
    SentinelHuntingQuery,
    SentinelIncident,
    SentinelWatchlist,
    SentinelWatchlistItem,
)

logger = logging.getLogger(__name__)


class SentinelAdapter(BaseAdapter):
    """Microsoft Sentinel SIEM adapter.

    Provides access to Microsoft Sentinel's security capabilities
    through Azure Resource Manager and Log Analytics APIs.
    """

    name = "sentinel"
    description = "Microsoft Sentinel SIEM"

    # Azure API endpoints
    AUTHORITY_URL = "https://login.microsoftonline.com"
    MANAGEMENT_URL = "https://management.azure.com"
    LOG_ANALYTICS_URL = "https://api.loganalytics.io"
    API_VERSION = "2023-02-01"
    LOG_API_VERSION = "v1"

    def __init__(self, config: AdapterConfig):
        """Initialize Sentinel adapter.

        Args:
            config: Adapter configuration with Azure credentials in 'extra' dict:
                - tenant_id: Azure AD tenant ID
                - client_id: Application (client) ID
                - client_secret: Client secret
                - subscription_id: Azure subscription ID
                - resource_group: Resource group containing workspace
                - workspace_name: Log Analytics workspace name
        """
        super().__init__(config)
        self._token: str | None = None
        self._log_token: str | None = None
        self._token_expires: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._log_client: httpx.AsyncClient | None = None

        # Extract Azure credentials
        self._tenant_id = config.extra.get("tenant_id", "")
        self._client_id = config.extra.get("client_id", "")
        self._client_secret = config.extra.get("client_secret", "")
        self._subscription_id = config.extra.get("subscription_id", "")
        self._resource_group = config.extra.get("resource_group", "")
        self._workspace_name = config.extra.get("workspace_name", "")

        # Build resource URI for Sentinel
        self._workspace_id: str | None = None

    @property
    def _sentinel_base_path(self) -> str:
        """Get Sentinel API base path."""
        return (
            f"/subscriptions/{self._subscription_id}"
            f"/resourceGroups/{self._resource_group}"
            f"/providers/Microsoft.OperationalInsights"
            f"/workspaces/{self._workspace_name}"
            f"/providers/Microsoft.SecurityInsights"
        )

    async def _get_token(self, resource: str) -> str:
        """Get OAuth2 access token for specified resource.

        Args:
            resource: Resource URL to get token for.

        Returns:
            Access token string.
        """
        import msal

        authority = f"{self.AUTHORITY_URL}/{self._tenant_id}"
        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=authority,
            client_credential=self._client_secret,
        )

        scope = [f"{resource}/.default"]
        result = app.acquire_token_for_client(scopes=scope)

        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise RuntimeError(f"Failed to acquire token: {error}")

        return result["access_token"]

    async def _get_management_client(self) -> httpx.AsyncClient:
        """Get HTTP client for Azure Resource Manager API."""
        if self._client is None:
            token = await self._get_token(self.MANAGEMENT_URL)
            self._client = httpx.AsyncClient(
                base_url=self.MANAGEMENT_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def _get_log_client(self) -> httpx.AsyncClient:
        """Get HTTP client for Log Analytics API."""
        if self._log_client is None:
            token = await self._get_token(self.LOG_ANALYTICS_URL)
            self._log_client = httpx.AsyncClient(
                base_url=self.LOG_ANALYTICS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._log_client

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make authenticated management API request."""
        client = await self._get_management_client()

        # Refresh token
        token = await self._get_token(self.MANAGEMENT_URL)
        client.headers["Authorization"] = f"Bearer {token}"

        # Add API version to params
        if params is None:
            params = {}
        params["api-version"] = self.API_VERSION

        response = await client.request(method, path, params=params, **kwargs)
        response.raise_for_status()

        if response.status_code == 204:
            return {}
        return response.json()

    async def _log_request(
        self,
        query: str,
        timespan: str | None = None,
    ) -> dict[str, Any]:
        """Execute KQL query via Log Analytics API."""
        client = await self._get_log_client()

        # Refresh token
        token = await self._get_token(self.LOG_ANALYTICS_URL)
        client.headers["Authorization"] = f"Bearer {token}"

        # Get workspace ID if not cached
        if not self._workspace_id:
            await self._get_workspace_id()

        data = {"query": query}
        if timespan:
            data["timespan"] = timespan

        response = await client.post(
            f"/{self.LOG_API_VERSION}/workspaces/{self._workspace_id}/query",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def _get_workspace_id(self) -> str:
        """Get the Log Analytics workspace ID."""
        path = (
            f"/subscriptions/{self._subscription_id}"
            f"/resourceGroups/{self._resource_group}"
            f"/providers/Microsoft.OperationalInsights"
            f"/workspaces/{self._workspace_name}"
        )
        result = await self._request("GET", path)
        self._workspace_id = result.get("properties", {}).get("customerId")
        if not self._workspace_id:
            raise RuntimeError("Could not get workspace ID")
        return self._workspace_id

    async def connect(self) -> bool:
        """Test connection to Sentinel."""
        try:
            await self._get_token(self.MANAGEMENT_URL)
            await self._get_workspace_id()
            self._status = AdapterStatus.CONNECTED
            logger.info("Connected to Microsoft Sentinel")
            return True
        except Exception as e:
            logger.error("Failed to connect to Sentinel: %s", e)
            self._status = AdapterStatus.ERROR
            return False

    async def disconnect(self) -> None:
        """Clean up HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._log_client:
            await self._log_client.aclose()
            self._log_client = None
        self._token = None
        self._log_token = None
        self._status = AdapterStatus.DISCONNECTED

    async def health_check(self) -> AdapterHealth:
        """Check Sentinel API health."""
        try:
            await self._get_token(self.MANAGEMENT_URL)

            # Try to list incidents to verify access
            await self.list_incidents(limit=1)

            self._status = AdapterStatus.CONNECTED
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                message="Connected to Microsoft Sentinel",
                details={
                    "workspace": self._workspace_name,
                    "subscription": self._subscription_id[:8] + "...",
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
            "subscription_id": self._subscription_id[:8] + "..." if self._subscription_id else None,
            "workspace": self._workspace_name,
            "resource_group": self._resource_group,
        }

    # =========================================================================
    # Incident Management
    # =========================================================================

    async def list_incidents(
        self,
        limit: int = 100,
        filter_query: str | None = None,
        orderby: str | None = None,
    ) -> list[SentinelIncident]:
        """List incidents.

        Args:
            limit: Maximum incidents to return.
            filter_query: OData filter query.
            orderby: OData orderby clause.

        Returns:
            List of SentinelIncident objects.
        """
        params = {"$top": limit}
        if filter_query:
            params["$filter"] = filter_query
        if orderby:
            params["$orderby"] = orderby

        path = f"{self._sentinel_base_path}/incidents"
        result = await self._request("GET", path, params=params)

        incidents = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            props["etag"] = item.get("etag")
            incidents.append(SentinelIncident(**props))

        return incidents

    async def get_incident(self, incident_id: str) -> SentinelIncident | None:
        """Get incident by ID."""
        try:
            path = f"{self._sentinel_base_path}/incidents/{incident_id}"
            result = await self._request("GET", path)

            props = result.get("properties", {})
            props["id"] = result.get("id")
            props["name"] = result.get("name")
            props["etag"] = result.get("etag")
            return SentinelIncident(**props)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def update_incident(
        self,
        incident_id: str,
        title: str | None = None,
        description: str | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        classification: IncidentClassification | None = None,
        classification_comment: str | None = None,
        owner_id: str | None = None,
        labels: list[str] | None = None,
    ) -> SentinelIncident:
        """Update an incident.

        Args:
            incident_id: Incident ID to update.
            title: New title.
            description: New description.
            severity: New severity.
            status: New status.
            classification: Classification (when closing).
            classification_comment: Comment for classification.
            owner_id: Assign to user by object ID.
            labels: List of label names.

        Returns:
            Updated SentinelIncident.
        """
        # Get current incident to preserve etag
        current = await self.get_incident(incident_id)
        if not current:
            raise ValueError(f"Incident not found: {incident_id}")

        properties: dict[str, Any] = {}
        if title:
            properties["title"] = title
        if description:
            properties["description"] = description
        if severity:
            properties["severity"] = severity.value
        if status:
            properties["status"] = status.value
        if classification:
            properties["classification"] = classification.value
        if classification_comment:
            properties["classificationComment"] = classification_comment
        if owner_id:
            properties["owner"] = {"objectId": owner_id}
        if labels is not None:
            properties["labels"] = [{"labelName": label} for label in labels]

        path = f"{self._sentinel_base_path}/incidents/{incident_id}"
        result = await self._request(
            "PUT",
            path,
            json={"etag": current.etag, "properties": properties},
        )

        props = result.get("properties", {})
        props["id"] = result.get("id")
        props["name"] = result.get("name")
        props["etag"] = result.get("etag")
        return SentinelIncident(**props)

    async def get_incident_alerts(
        self,
        incident_id: str,
    ) -> list[SentinelAlert]:
        """Get alerts related to an incident."""
        path = f"{self._sentinel_base_path}/incidents/{incident_id}/alerts"
        result = await self._request("POST", path)

        alerts = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            alerts.append(SentinelAlert(**props))

        return alerts

    async def get_incident_entities(
        self,
        incident_id: str,
    ) -> list[SentinelEntity]:
        """Get entities related to an incident."""
        path = f"{self._sentinel_base_path}/incidents/{incident_id}/entities"
        result = await self._request("POST", path)

        entities = []
        for item in result.get("entities", []):
            props = item.get("properties", {})
            entity = SentinelEntity(
                id=item.get("id", ""),
                name=item.get("name", ""),
                kind=item.get("kind"),
                properties=props,
                friendly_name=props.get("friendlyName"),
            )
            entities.append(entity)

        return entities

    async def add_incident_comment(
        self,
        incident_id: str,
        message: str,
    ) -> SentinelComment:
        """Add a comment to an incident."""
        import uuid

        comment_id = str(uuid.uuid4())
        path = f"{self._sentinel_base_path}/incidents/{incident_id}/comments/{comment_id}"

        result = await self._request(
            "PUT",
            path,
            json={"properties": {"message": message}},
        )

        props = result.get("properties", {})
        return SentinelComment(
            id=result.get("id", ""),
            name=result.get("name"),
            message=props.get("message"),
            author=props.get("author"),
            created_time_utc=props.get("createdTimeUtc"),
        )

    async def get_incident_comments(
        self,
        incident_id: str,
    ) -> list[SentinelComment]:
        """Get comments for an incident."""
        path = f"{self._sentinel_base_path}/incidents/{incident_id}/comments"
        result = await self._request("GET", path)

        comments = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            comments.append(
                SentinelComment(
                    id=item.get("id", ""),
                    name=item.get("name"),
                    message=props.get("message"),
                    author=props.get("author"),
                    created_time_utc=props.get("createdTimeUtc"),
                )
            )

        return comments

    # =========================================================================
    # KQL Queries
    # =========================================================================

    async def run_kql_query(
        self,
        query: str,
        timespan: str | None = None,
    ) -> KQLQueryResult:
        """Execute a KQL query against Log Analytics.

        Args:
            query: KQL query string.
            timespan: ISO 8601 timespan (e.g., "P1D" for last day).

        Returns:
            KQLQueryResult with tables and rows.
        """
        result = await self._log_request(query, timespan)
        return KQLQueryResult(**result)

    async def run_hunting_query(
        self,
        query_id: str,
    ) -> KQLQueryResult:
        """Execute a saved hunting query."""
        # Get the hunting query
        hunting_query = await self.get_hunting_query(query_id)
        if not hunting_query or not hunting_query.query:
            raise ValueError(f"Hunting query not found or has no query: {query_id}")

        return await self.run_kql_query(hunting_query.query)

    # =========================================================================
    # Hunting Queries
    # =========================================================================

    async def list_hunting_queries(self) -> list[SentinelHuntingQuery]:
        """List available hunting queries."""
        path = f"{self._sentinel_base_path}/huntingQueries"
        result = await self._request("GET", path)

        queries = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            props["etag"] = item.get("etag")
            queries.append(SentinelHuntingQuery(**props))

        return queries

    async def get_hunting_query(
        self,
        query_id: str,
    ) -> SentinelHuntingQuery | None:
        """Get a hunting query by ID."""
        try:
            path = f"{self._sentinel_base_path}/huntingQueries/{query_id}"
            result = await self._request("GET", path)

            props = result.get("properties", {})
            props["id"] = result.get("id")
            props["name"] = result.get("name")
            props["etag"] = result.get("etag")
            return SentinelHuntingQuery(**props)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # =========================================================================
    # Watchlists
    # =========================================================================

    async def list_watchlists(self) -> list[SentinelWatchlist]:
        """List all watchlists."""
        path = f"{self._sentinel_base_path}/watchlists"
        result = await self._request("GET", path)

        watchlists = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            props["etag"] = item.get("etag")
            watchlists.append(SentinelWatchlist(**props))

        return watchlists

    async def get_watchlist(
        self,
        watchlist_alias: str,
    ) -> SentinelWatchlist | None:
        """Get watchlist by alias."""
        try:
            path = f"{self._sentinel_base_path}/watchlists/{watchlist_alias}"
            result = await self._request("GET", path)

            props = result.get("properties", {})
            props["id"] = result.get("id")
            props["name"] = result.get("name")
            props["etag"] = result.get("etag")
            return SentinelWatchlist(**props)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_watchlist_items(
        self,
        watchlist_alias: str,
    ) -> list[SentinelWatchlistItem]:
        """Get items from a watchlist."""
        path = f"{self._sentinel_base_path}/watchlists/{watchlist_alias}/watchlistItems"
        result = await self._request("GET", path)

        items = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            props["etag"] = item.get("etag")
            items.append(SentinelWatchlistItem(**props))

        return items

    async def add_watchlist_item(
        self,
        watchlist_alias: str,
        item_values: dict[str, Any],
    ) -> SentinelWatchlistItem:
        """Add an item to a watchlist.

        Args:
            watchlist_alias: Watchlist alias.
            item_values: Dictionary of key-value pairs for the item.

        Returns:
            Created watchlist item.
        """
        import uuid

        item_id = str(uuid.uuid4())
        path = f"{self._sentinel_base_path}/watchlists/{watchlist_alias}/watchlistItems/{item_id}"

        result = await self._request(
            "PUT",
            path,
            json={"properties": {"itemsKeyValue": item_values}},
        )

        props = result.get("properties", {})
        props["id"] = result.get("id")
        props["name"] = result.get("name")
        props["etag"] = result.get("etag")
        return SentinelWatchlistItem(**props)

    async def delete_watchlist_item(
        self,
        watchlist_alias: str,
        item_id: str,
    ) -> bool:
        """Delete an item from a watchlist."""
        try:
            path = (
                f"{self._sentinel_base_path}/watchlists/{watchlist_alias}"
                f"/watchlistItems/{item_id}"
            )
            await self._request("DELETE", path)
            return True
        except Exception as e:
            logger.error("Failed to delete watchlist item: %s", e)
            return False

    # =========================================================================
    # Analytics Rules
    # =========================================================================

    async def list_analytics_rules(self) -> list[SentinelAnalyticsRule]:
        """List analytics rules."""
        path = f"{self._sentinel_base_path}/alertRules"
        result = await self._request("GET", path)

        rules = []
        for item in result.get("value", []):
            props = item.get("properties", {})
            props["id"] = item.get("id")
            props["name"] = item.get("name")
            props["etag"] = item.get("etag")
            props["kind"] = item.get("kind")
            rules.append(SentinelAnalyticsRule(**props))

        return rules

    async def get_analytics_rule(
        self,
        rule_id: str,
    ) -> SentinelAnalyticsRule | None:
        """Get an analytics rule by ID."""
        try:
            path = f"{self._sentinel_base_path}/alertRules/{rule_id}"
            result = await self._request("GET", path)

            props = result.get("properties", {})
            props["id"] = result.get("id")
            props["name"] = result.get("name")
            props["etag"] = result.get("etag")
            props["kind"] = result.get("kind")
            return SentinelAnalyticsRule(**props)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def enable_analytics_rule(
        self,
        rule_id: str,
        enabled: bool = True,
    ) -> SentinelAnalyticsRule:
        """Enable or disable an analytics rule."""
        current = await self.get_analytics_rule(rule_id)
        if not current:
            raise ValueError(f"Analytics rule not found: {rule_id}")

        path = f"{self._sentinel_base_path}/alertRules/{rule_id}"

        # Must include the kind in the PUT request
        result = await self._request(
            "PUT",
            path,
            json={
                "kind": current.kind,
                "etag": current.etag,
                "properties": {"enabled": enabled},
            },
        )

        props = result.get("properties", {})
        props["id"] = result.get("id")
        props["name"] = result.get("name")
        props["etag"] = result.get("etag")
        props["kind"] = result.get("kind")
        return SentinelAnalyticsRule(**props)

    # =========================================================================
    # Helper Methods for Eleanor Integration
    # =========================================================================

    def _map_severity(self, sentinel_severity: IncidentSeverity | None) -> Severity:
        """Map Sentinel severity to Eleanor severity."""
        if not sentinel_severity:
            return Severity.INFORMATIONAL

        mapping = {
            IncidentSeverity.HIGH: Severity.HIGH,
            IncidentSeverity.MEDIUM: Severity.MEDIUM,
            IncidentSeverity.LOW: Severity.LOW,
            IncidentSeverity.INFORMATIONAL: Severity.INFORMATIONAL,
        }
        return mapping.get(sentinel_severity, Severity.INFORMATIONAL)

    async def get_incident_as_case(
        self,
        incident_id: str,
    ) -> ExternalCase | None:
        """Get incident as an Eleanor ExternalCase.

        Convenience method for integration with Eleanor's case management.
        """
        incident = await self.get_incident(incident_id)
        if not incident:
            return None

        return ExternalCase(
            external_id=incident.name,
            title=incident.title or f"Incident {incident.incident_number}",
            description=incident.description,
            status=incident.status.value if incident.status else None,
            severity=self._map_severity(incident.severity),
            created_at=incident.created_time_utc,
            updated_at=incident.last_modified_time_utc,
            closed_at=None,  # Sentinel doesn't expose this directly
            assignee=incident.owner.get("assignedTo") if incident.owner else None,
            tags=[label.get("labelName", "") for label in incident.labels],
            metadata={
                "incident_number": incident.incident_number,
                "classification": incident.classification.value if incident.classification else None,
                "tactics": incident.tactics,
                "alerts_count": incident.alerts_count,
                "provider": incident.provider_name,
            },
        )
