"""Jira adapter for ticket management.

PATTERN: Adapter Pattern
Implements TicketingAdapter to integrate with Atlassian Jira for
incident ticket management and case tracking.

Provides:
- Ticket creation and updates
- Comment management
- Status workflow transitions
- Eleanor case linking via custom field or labels
- Attachment support
"""

import logging
from datetime import datetime, UTC
from typing import Any

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    Ticket,
    TicketComment,
    TicketingAdapter,
    TicketPriority,
    TicketTransition,
)

logger = logging.getLogger(__name__)


# Priority mapping from Eleanor to Jira priority names
PRIORITY_MAP = {
    TicketPriority.CRITICAL: "Highest",
    TicketPriority.HIGH: "High",
    TicketPriority.MEDIUM: "Medium",
    TicketPriority.LOW: "Low",
    TicketPriority.TRIVIAL: "Lowest",
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "trivial": "Lowest",
}

# Reverse mapping from Jira to Eleanor
JIRA_PRIORITY_MAP = {
    "Highest": TicketPriority.CRITICAL,
    "High": TicketPriority.HIGH,
    "Medium": TicketPriority.MEDIUM,
    "Low": TicketPriority.LOW,
    "Lowest": TicketPriority.TRIVIAL,
}


class JiraAdapter(TicketingAdapter):
    """Jira ticketing system adapter.

    PATTERN: Adapter Pattern
    Provides integration with Atlassian Jira Cloud and Server for
    incident ticket management.

    Configuration:
        url: Jira instance URL (e.g., https://company.atlassian.net)
        username: Jira username (email for Cloud)
        api_token: API token (Cloud) or password (Server)
        default_project: Default project key for new tickets
        default_issue_type: Default issue type (e.g., "Task", "Bug")
        case_link_field: Custom field ID for Eleanor case links

    DESIGN DECISION: Uses Jira REST API v3 for Cloud, v2 for Server.
    Auto-detects based on URL pattern.
    """

    name = "jira"
    description = "Atlassian Jira issue tracker"

    def __init__(self, config: AdapterConfig):
        """Initialize the Jira adapter.

        Args:
            config: Adapter configuration with Jira credentials
        """
        super().__init__(config)
        self.url = config.url.rstrip("/")
        self.username = config.username
        self.api_token = config.api_key  # API token stored in api_key field
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl

        # Extract extra configuration
        self.default_project = config.extra.get("default_project", "")
        self.default_issue_type = config.extra.get("default_issue_type", "Task")
        self.case_link_field = config.extra.get("case_link_field", "")

        # Detect Cloud vs Server
        self.is_cloud = "atlassian.net" in self.url

        # API version path
        self.api_base = f"{self.url}/rest/api/{'3' if self.is_cloud else '2'}"

    async def health_check(self) -> AdapterHealth:
        """Check Jira connectivity and permissions."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/myself",
                    auth=(self.username, self.api_token),
                    timeout=10,
                )

                if response.status_code == 200:
                    user_data = response.json()
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        message=f"Connected as {user_data.get('displayName', 'unknown')}",
                        details={
                            "account_id": user_data.get("accountId"),
                            "email": user_data.get("emailAddress"),
                            "is_cloud": self.is_cloud,
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
            "is_cloud": self.is_cloud,
            "default_project": self.default_project,
            "default_issue_type": self.default_issue_type,
            "case_link_field_configured": bool(self.case_link_field),
        }

    def _get_auth(self) -> tuple[str, str]:
        """Get authentication tuple for requests."""
        return (self.username, self.api_token)

    async def create_ticket(
        self,
        title: str,
        description: str,
        priority: TicketPriority | str = TicketPriority.MEDIUM,
        labels: list[str] | None = None,
        assignee: str | None = None,
        project_key: str | None = None,
        issue_type: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Ticket:
        """Create a new Jira issue."""
        import httpx

        project = project_key or self.default_project
        if not project:
            raise ValueError("Project key is required")

        issue_type_name = issue_type or self.default_issue_type

        # Build issue fields
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": title,
            "issuetype": {"name": issue_type_name},
        }

        # Description - Jira Cloud uses ADF, Server uses wiki markup
        if self.is_cloud:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            }
        else:
            fields["description"] = description

        # Priority
        jira_priority = PRIORITY_MAP.get(priority, "Medium")
        fields["priority"] = {"name": jira_priority}

        # Labels
        if labels:
            fields["labels"] = labels

        # Assignee
        if assignee:
            if self.is_cloud:
                fields["assignee"] = {"accountId": assignee}
            else:
                fields["assignee"] = {"name": assignee}

        # Custom fields
        if custom_fields:
            fields.update(custom_fields)

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/issue",
                auth=self._get_auth(),
                json={"fields": fields},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        issue_key = data["key"]
        issue_id = data["id"]

        # Fetch full issue to return complete ticket
        return await self.get_ticket(issue_key) or Ticket(
            ticket_id=issue_id,
            key=issue_key,
            title=title,
            description=description,
            status="Open",
            priority=str(priority),
            labels=labels or [],
            url=f"{self.url}/browse/{issue_key}",
        )

    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Get a Jira issue by key or ID."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/issue/{ticket_id}",
                    auth=self._get_auth(),
                    params={"expand": "renderedFields"},
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()

            return self._parse_issue(data)

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: TicketPriority | str | None = None,
        labels: list[str] | None = None,
        assignee: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Ticket:
        """Update a Jira issue."""
        import httpx

        fields: dict[str, Any] = {}

        if title is not None:
            fields["summary"] = title

        if description is not None:
            if self.is_cloud:
                fields["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                }
            else:
                fields["description"] = description

        if priority is not None:
            jira_priority = PRIORITY_MAP.get(priority, "Medium")
            fields["priority"] = {"name": jira_priority}

        if labels is not None:
            fields["labels"] = labels

        if assignee is not None:
            if self.is_cloud:
                fields["assignee"] = {"accountId": assignee} if assignee else None
            else:
                fields["assignee"] = {"name": assignee} if assignee else None

        if custom_fields:
            fields.update(custom_fields)

        if not fields:
            # Nothing to update, just return current ticket
            ticket = await self.get_ticket(ticket_id)
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            return ticket

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.put(
                f"{self.api_base}/issue/{ticket_id}",
                auth=self._get_auth(),
                json={"fields": fields},
                timeout=self.timeout,
            )
            response.raise_for_status()

        ticket = await self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found after update")
        return ticket

    async def add_comment(
        self,
        ticket_id: str,
        comment: str,
        is_internal: bool = False,
    ) -> TicketComment:
        """Add a comment to a Jira issue."""
        import httpx

        # Build comment body
        if self.is_cloud:
            body: Any = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        else:
            body = comment

        payload: dict[str, Any] = {"body": body}

        # Jira Service Management supports internal comments
        if is_internal and self.is_cloud:
            payload["visibility"] = {
                "type": "role",
                "value": "Administrators",
            }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/issue/{ticket_id}/comment",
                auth=self._get_auth(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_comment(data, ticket_id)

    async def get_comments(
        self,
        ticket_id: str,
        limit: int = 50,
    ) -> list[TicketComment]:
        """Get comments on a Jira issue."""
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/issue/{ticket_id}/comment",
                auth=self._get_auth(),
                params={"maxResults": limit, "orderBy": "-created"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        comments = []
        for comment_data in data.get("comments", []):
            comments.append(self._parse_comment(comment_data, ticket_id))

        return comments

    async def link_to_case(
        self,
        ticket_id: str,
        case_id: str,
        link_type: str = "relates_to",
    ) -> bool:
        """Link a Jira issue to an Eleanor case.

        DESIGN DECISION: Uses custom field if configured, otherwise adds
        a label and comment with the case reference.
        """
        import httpx

        try:
            if self.case_link_field:
                # Use custom field
                async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                    response = await client.put(
                        f"{self.api_base}/issue/{ticket_id}",
                        auth=self._get_auth(),
                        json={"fields": {self.case_link_field: case_id}},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
            else:
                # Add label and comment
                ticket = await self.get_ticket(ticket_id)
                if not ticket:
                    return False

                new_labels = list(ticket.labels) + [f"eleanor-case:{case_id}"]
                await self.update_ticket(ticket_id, labels=new_labels)

                # Add linking comment
                await self.add_comment(
                    ticket_id,
                    f"Linked to Eleanor case: {case_id}",
                    is_internal=True,
                )

            logger.info(
                "Linked Jira issue to Eleanor case",
                extra={"ticket_id": ticket_id, "case_id": case_id},
            )
            return True

        except Exception as error:
            logger.error(
                "Failed to link Jira issue to case",
                extra={"ticket_id": ticket_id, "case_id": case_id, "error": str(error)},
            )
            return False

    async def get_transitions(self, ticket_id: str) -> list[TicketTransition]:
        """Get available status transitions for an issue."""
        import httpx

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f"{self.api_base}/issue/{ticket_id}/transitions",
                auth=self._get_auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        transitions = []
        for transition_data in data.get("transitions", []):
            # Check for required fields
            required_fields = []
            for field_key, field_info in transition_data.get("fields", {}).items():
                if field_info.get("required"):
                    required_fields.append(field_key)

            transitions.append(
                TicketTransition(
                    transition_id=transition_data["id"],
                    name=transition_data["name"],
                    to_status=transition_data.get("to", {}).get("name", ""),
                    requires_fields=required_fields,
                )
            )

        return transitions

    async def transition_ticket(
        self,
        ticket_id: str,
        transition_id: str,
        resolution: str | None = None,
        comment: str | None = None,
    ) -> Ticket:
        """Transition a Jira issue to a new status."""
        import httpx

        payload: dict[str, Any] = {"transition": {"id": transition_id}}

        if resolution:
            payload["fields"] = {"resolution": {"name": resolution}}

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/issue/{ticket_id}/transitions",
                auth=self._get_auth(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        if comment:
            await self.add_comment(ticket_id, comment)

        ticket = await self.get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found after transition")
        return ticket

    async def close_ticket(
        self,
        ticket_id: str,
        resolution: str = "Done",
        comment: str | None = None,
    ) -> Ticket:
        """Close a Jira issue.

        DESIGN DECISION: Finds the appropriate close transition automatically
        by looking for transitions to "Done", "Closed", or "Resolved" statuses.
        """
        transitions = await self.get_transitions(ticket_id)

        # Find close transition
        close_transition = None
        for transition in transitions:
            status_lower = transition.to_status.lower()
            if status_lower in ("done", "closed", "resolved"):
                close_transition = transition
                break

        if not close_transition:
            # Try finding any transition with "close" or "done" in name
            for transition in transitions:
                name_lower = transition.name.lower()
                if "close" in name_lower or "done" in name_lower or "resolve" in name_lower:
                    close_transition = transition
                    break

        if not close_transition:
            raise ValueError(
                f"No close transition found for ticket {ticket_id}. "
                f"Available transitions: {[t.name for t in transitions]}"
            )

        return await self.transition_ticket(
            ticket_id,
            close_transition.transition_id,
            resolution=resolution,
            comment=comment,
        )

    async def search_tickets(
        self,
        query: str,
        project_key: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        limit: int = 50,
    ) -> list[Ticket]:
        """Search Jira issues using JQL."""
        import httpx

        # Build JQL query
        jql_parts = []

        if query:
            # Check if query is already JQL or just text search
            if any(op in query for op in ["=", "~", "AND", "OR", "ORDER BY"]):
                jql_parts.append(f"({query})")
            else:
                jql_parts.append(f'text ~ "{query}"')

        if project_key:
            jql_parts.append(f'project = "{project_key}"')

        if status:
            jql_parts.append(f'status = "{status}"')

        if assignee:
            if self.is_cloud:
                jql_parts.append(f'assignee = "{assignee}"')
            else:
                jql_parts.append(f'assignee = "{assignee}"')

        if labels:
            for label in labels:
                jql_parts.append(f'labels = "{label}"')

        jql = " AND ".join(jql_parts) if jql_parts else "ORDER BY created DESC"

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/search",
                auth=self._get_auth(),
                json={
                    "jql": jql,
                    "maxResults": limit,
                    "fields": [
                        "summary",
                        "description",
                        "status",
                        "priority",
                        "assignee",
                        "reporter",
                        "labels",
                        "created",
                        "updated",
                        "resolution",
                        "resolutiondate",
                    ],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        tickets = []
        for issue in data.get("issues", []):
            tickets.append(self._parse_issue(issue))

        return tickets

    async def add_attachment(
        self,
        ticket_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """Add an attachment to a Jira issue."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.api_base}/issue/{ticket_id}/attachments",
                    auth=self._get_auth(),
                    headers={"X-Atlassian-Token": "no-check"},
                    files={"file": (filename, content, content_type)},
                    timeout=60,  # Longer timeout for uploads
                )
                response.raise_for_status()

            logger.info(
                "Added attachment to Jira issue",
                extra={"ticket_id": ticket_id, "filename": filename},
            )
            return True

        except Exception as error:
            logger.error(
                "Failed to add attachment to Jira issue",
                extra={"ticket_id": ticket_id, "filename": filename, "error": str(error)},
            )
            return False

    def _parse_issue(self, data: dict[str, Any]) -> Ticket:
        """Parse Jira issue response to Ticket."""
        fields = data.get("fields", {})

        # Extract description text
        description = ""
        desc_field = fields.get("description")
        if desc_field:
            if isinstance(desc_field, str):
                description = desc_field
            elif isinstance(desc_field, dict):
                # ADF format - extract text
                description = self._extract_adf_text(desc_field)

        # Parse priority
        priority_data = fields.get("priority", {})
        priority_name = priority_data.get("name", "Medium") if priority_data else "Medium"
        priority = JIRA_PRIORITY_MAP.get(priority_name, TicketPriority.MEDIUM).value

        # Parse assignee
        assignee_data = fields.get("assignee")
        assignee = None
        if assignee_data:
            assignee = assignee_data.get("accountId") or assignee_data.get("name")

        # Parse reporter
        reporter_data = fields.get("reporter")
        reporter = None
        if reporter_data:
            reporter = reporter_data.get("displayName") or reporter_data.get("name")

        # Parse resolution
        resolution_data = fields.get("resolution")
        resolution = resolution_data.get("name") if resolution_data else None

        # Extract Eleanor case ID from labels if present
        case_id = None
        labels = fields.get("labels", [])
        for label in labels:
            if label.startswith("eleanor-case:"):
                case_id = label.split(":", 1)[1]
                break

        issue_key = data["key"]

        return Ticket(
            ticket_id=data["id"],
            key=issue_key,
            title=fields.get("summary", ""),
            description=description,
            status=fields.get("status", {}).get("name", "Unknown"),
            priority=priority,
            assignee=assignee,
            reporter=reporter,
            labels=labels,
            created_at=self._parse_jira_timestamp(fields.get("created")),
            updated_at=self._parse_jira_timestamp(fields.get("updated")),
            resolved_at=self._parse_jira_timestamp(fields.get("resolutiondate")),
            resolution=resolution,
            case_id=case_id,
            url=f"{self.url}/browse/{issue_key}",
            metadata={
                "project": fields.get("project", {}).get("key"),
                "issue_type": fields.get("issuetype", {}).get("name"),
            },
        )

    def _parse_comment(self, data: dict[str, Any], ticket_id: str) -> TicketComment:
        """Parse Jira comment response to TicketComment."""
        # Extract author
        author_data = data.get("author", {})
        author = author_data.get("displayName") or author_data.get("name", "Unknown")

        # Extract body text
        body = ""
        body_field = data.get("body")
        if body_field:
            if isinstance(body_field, str):
                body = body_field
            elif isinstance(body_field, dict):
                body = self._extract_adf_text(body_field)

        # Check if internal
        is_internal = "visibility" in data

        return TicketComment(
            comment_id=data["id"],
            ticket_id=ticket_id,
            author=author,
            body=body,
            created_at=self._parse_jira_timestamp(data.get("created")),
            updated_at=self._parse_jira_timestamp(data.get("updated")),
            is_internal=is_internal,
        )

    def _extract_adf_text(self, adf: dict) -> str:
        """Extract plain text from Atlassian Document Format.

        DESIGN DECISION: Simple recursive extraction. For full ADF support,
        consider using atlassian-python-api's ADF renderer.
        """
        text_parts = []

        content = adf.get("content", [])
        for node in content:
            node_type = node.get("type")

            if node_type == "text":
                text_parts.append(node.get("text", ""))
            elif node_type in ("paragraph", "heading", "blockquote"):
                text_parts.append(self._extract_adf_text(node))
                text_parts.append("\n")
            elif node_type == "bulletList" or node_type == "orderedList":
                for item in node.get("content", []):
                    text_parts.append("• " + self._extract_adf_text(item) + "\n")
            elif node_type == "codeBlock":
                for inner in node.get("content", []):
                    text_parts.append(inner.get("text", ""))
                text_parts.append("\n")
            elif "content" in node:
                text_parts.append(self._extract_adf_text(node))

        return "".join(text_parts).strip()

    def _parse_jira_timestamp(self, value: str | None) -> datetime | None:
        """Parse Jira timestamp to datetime."""
        if not value:
            return None

        try:
            # Jira uses ISO 8601 format with timezone
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
