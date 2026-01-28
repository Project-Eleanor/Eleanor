"""Okta adapter for identity and access management.

Provides integration with Okta for:
- User and group management
- Authentication event logs
- System logs
- Application access logs
"""

import logging
from datetime import datetime
from typing import Any

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    BaseAdapter,
)

logger = logging.getLogger(__name__)


class OktaAdapter(BaseAdapter):
    """Okta identity management adapter.

    Integrates with Okta APIs for:
    - System Log API for security events
    - Users API for user management
    - Groups API for group management
    - Applications API for app access

    Configuration:
        domain: Okta organization domain (e.g., "company.okta.com")
        api_token: Okta API token with appropriate scopes
    """

    name = "okta"
    description = "Okta identity and access management adapter"

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.domain = config.extra.get("domain", "")
        self.api_token = config.api_key
        self.base_url = f"https://{self.domain}/api/v1"
        self.timeout = config.timeout

    async def health_check(self) -> AdapterHealth:
        """Check Okta API connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/org",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        version=data.get("companyName", ""),
                        message="Connected to Okta",
                        details={
                            "org_id": data.get("id"),
                            "subdomain": data.get("subdomain"),
                        },
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
            "domain": self.domain,
            "api_key_configured": bool(self.api_token),
        }

    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"SSWS {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get_system_logs(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        filter_query: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get system log events.

        Args:
            since: Start time for events
            until: End time for events
            filter_query: Okta filter expression
            limit: Maximum events to return

        Returns:
            List of log events
        """
        import httpx

        params: dict[str, Any] = {"limit": min(limit, 1000)}

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if filter_query:
            params["filter"] = filter_query

        events = []

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            url = f"{self.base_url}/logs"

            while url and len(events) < limit:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params if url == f"{self.base_url}/logs" else None,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                events.extend(response.json())

                # Handle pagination
                url = None
                link_header = response.headers.get("Link", "")
                if 'rel="next"' in link_header:
                    for link in link_header.split(","):
                        if 'rel="next"' in link:
                            url = link.split(";")[0].strip("<>")
                            params = {}
                            break

        return events[:limit]

    async def list_users(
        self,
        search: str | None = None,
        filter_query: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List users.

        Args:
            search: Search query
            filter_query: Okta filter expression
            limit: Maximum users to return

        Returns:
            List of users
        """
        import httpx

        params: dict[str, Any] = {"limit": min(limit, 200)}

        if search:
            params["search"] = search
        if filter_query:
            params["filter"] = filter_query

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/users",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get a specific user.

        Args:
            user_id: User ID or login

        Returns:
            User data or None
        """
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def list_user_groups(self, user_id: str) -> list[dict[str, Any]]:
        """List groups for a user.

        Args:
            user_id: User ID

        Returns:
            List of groups
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}/groups",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def list_user_apps(self, user_id: str) -> list[dict[str, Any]]:
        """List applications assigned to a user.

        Args:
            user_id: User ID

        Returns:
            List of app links
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}/appLinks",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def suspend_user(self, user_id: str) -> bool:
        """Suspend a user account.

        Args:
            user_id: User ID to suspend

        Returns:
            True if successful
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/users/{user_id}/lifecycle/suspend",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return response.status_code == 200

    async def unsuspend_user(self, user_id: str) -> bool:
        """Unsuspend a user account.

        Args:
            user_id: User ID to unsuspend

        Returns:
            True if successful
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.post(
                f"{self.base_url}/users/{user_id}/lifecycle/unsuspend",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return response.status_code == 200

    async def clear_user_sessions(self, user_id: str) -> bool:
        """Clear all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.delete(
                f"{self.base_url}/users/{user_id}/sessions",
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            return response.status_code == 204

    async def list_groups(
        self,
        search: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List groups.

        Args:
            search: Search query
            limit: Maximum groups to return

        Returns:
            List of groups
        """
        import httpx

        params: dict[str, Any] = {"limit": min(limit, 200)}
        if search:
            params["q"] = search

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/groups",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def get_group_members(
        self,
        group_id: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Get members of a group.

        Args:
            group_id: Group ID
            limit: Maximum members to return

        Returns:
            List of users
        """
        import httpx

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/groups/{group_id}/users",
                headers=self._get_headers(),
                params={"limit": min(limit, 200)},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    async def list_applications(
        self,
        filter_query: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """List applications.

        Args:
            filter_query: Okta filter expression
            limit: Maximum apps to return

        Returns:
            List of applications
        """
        import httpx

        params: dict[str, Any] = {"limit": min(limit, 200)}
        if filter_query:
            params["filter"] = filter_query

        async with httpx.AsyncClient(verify=self.config.verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/apps",
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
