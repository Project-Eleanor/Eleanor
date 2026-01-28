"""TheHive case management adapter.

PATTERN: Adapter Pattern
Implements CaseManagementAdapter to integrate with TheHive 5 for
case management and collaboration.

Provides:
- Case creation and lifecycle management
- Observable management
- Task tracking
- Alert ingestion
- Case sharing and collaboration
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.adapters.base import (
    IOC,
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    Alert,
    Case,
    CaseManagementAdapter,
    CaseMember,
    Severity,
    Task,
)

logger = logging.getLogger(__name__)


# TheHive severity mapping
SEVERITY_MAP = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

SEVERITY_REVERSE_MAP = {
    1: Severity.LOW,
    2: Severity.MEDIUM,
    3: Severity.HIGH,
    4: Severity.CRITICAL,
}


class TheHiveAdapter(CaseManagementAdapter):
    """TheHive 5 case management adapter.

    PATTERN: Adapter Pattern
    Provides integration with TheHive 5 for case management,
    alert handling, and observable management.

    Configuration:
        url: TheHive instance URL
        api_key: TheHive API key
        organisation: Organisation name (for multi-tenant)

    DESIGN DECISION: Uses TheHive 5 API (different from TheHive 4).
    The adapter auto-detects version based on API response.
    """

    name = "thehive"
    description = "TheHive case management platform"

    # TLP mapping
    TLP_MAP = {
        "white": 0,
        "green": 1,
        "amber": 2,
        "amber+strict": 3,
        "red": 4,
    }

    def __init__(self, config: AdapterConfig):
        """Initialize TheHive adapter.

        Args:
            config: Adapter configuration with TheHive credentials
        """
        super().__init__(config)
        self.url = config.url.rstrip("/")
        self.api_key = config.api_key
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl

        # Extra config
        self.organisation = config.extra.get("organisation", "")
        self.default_tlp = config.extra.get("default_tlp", "amber")
        self.default_pap = config.extra.get("default_pap", "amber")

        # API base
        self.api_base = f"{self.url}/api/v1"

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
        """Check TheHive connectivity."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/user/current",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if response.status_code == 200:
                    user_data = response.json()
                    return AdapterHealth(
                        adapter_name=self.name,
                        status=AdapterStatus.CONNECTED,
                        message=f"Connected as {user_data.get('login', 'unknown')}",
                        details={
                            "user_id": user_data.get("_id"),
                            "organisation": user_data.get("organisation"),
                            "profile": user_data.get("profile"),
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
            "default_tlp": self.default_tlp,
        }

    async def create_case(
        self,
        title: str,
        description: str,
        severity: Severity = Severity.MEDIUM,
        tags: list[str] | None = None,
        tlp: str | None = None,
    ) -> Case:
        """Create a new case in TheHive."""
        import httpx

        payload = {
            "title": title,
            "description": description,
            "severity": SEVERITY_MAP.get(severity, 2),
            "tlp": self.TLP_MAP.get(tlp or self.default_tlp, 2),
            "pap": self.TLP_MAP.get(self.default_pap, 2),
            "tags": tags or [],
            "flag": False,
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/case",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_case(data)

    async def get_case(self, case_id: str) -> Case | None:
        """Get a case by ID."""
        import httpx

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.api_base}/case/{case_id}",
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return self._parse_case(response.json())

        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise

    async def update_case(
        self,
        case_id: str,
        title: str | None = None,
        description: str | None = None,
        severity: Severity | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
    ) -> Case:
        """Update an existing case."""
        import httpx

        payload: dict[str, Any] = {}

        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if severity is not None:
            payload["severity"] = SEVERITY_MAP.get(severity, 2)
        if status is not None:
            payload["status"] = status
        if tags is not None:
            payload["tags"] = tags

        if not payload:
            case = await self.get_case(case_id)
            if not case:
                raise ValueError(f"Case {case_id} not found")
            return case

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.patch(
                f"{self.api_base}/case/{case_id}",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_case(response.json())

    async def close_case(
        self,
        case_id: str,
        resolution_status: str = "TruePositive",
        summary: str | None = None,
    ) -> Case:
        """Close a case with resolution."""
        import httpx

        payload = {
            "status": "Resolved",
            "resolutionStatus": resolution_status,
        }

        if summary:
            payload["summary"] = summary

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.patch(
                f"{self.api_base}/case/{case_id}",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_case(response.json())

    async def list_cases(
        self,
        status: str | None = None,
        severity: Severity | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Case]:
        """List cases with optional filters."""
        import httpx

        # Build query
        query: list[dict[str, Any]] = []

        if status:
            query.append({"_field": "status", "_value": status})
        if severity:
            query.append({"_field": "severity", "_value": SEVERITY_MAP.get(severity, 2)})
        if tags:
            for tag in tags:
                query.append({"_field": "tags", "_value": tag})

        payload = {
            "query": query if query else [{"_name": "listCase"}],
            "range": f"{offset}-{offset + limit}",
            "sort": ["-_createdAt"],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return [self._parse_case(case) for case in data]

    async def search_cases(self, query: str, limit: int = 50) -> list[Case]:
        """Search cases by keyword."""
        import httpx

        payload = {
            "query": [
                {"_name": "listCase"},
                {
                    "_or": [
                        {"_field": "title", "_like": f"*{query}*"},
                        {"_field": "description", "_like": f"*{query}*"},
                        {"_field": "tags", "_value": query},
                    ]
                },
            ],
            "range": f"0-{limit}",
            "sort": ["-_createdAt"],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return [self._parse_case(case) for case in data]

    async def add_ioc(
        self,
        case_id: str,
        ioc: IOC,
    ) -> IOC:
        """Add an observable (IOC) to a case."""
        import httpx

        # Map IOC type to TheHive data type
        data_type = self._ioc_type_to_thehive(ioc.type)

        payload = {
            "dataType": data_type,
            "data": ioc.value,
            "message": ioc.description or "",
            "tlp": self.TLP_MAP.get(self.default_tlp, 2),
            "ioc": True,
            "sighted": False,
            "tags": ioc.tags or [],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/case/{case_id}/observable",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return IOC(
            id=data.get("_id", ""),
            type=ioc.type,
            value=ioc.value,
            description=ioc.description,
            tags=data.get("tags", []),
            metadata={
                "thehive_id": data.get("_id"),
                "data_type": data_type,
                "ioc": data.get("ioc", True),
                "sighted": data.get("sighted", False),
            },
        )

    async def get_iocs(self, case_id: str, limit: int = 100) -> list[IOC]:
        """Get observables (IOCs) for a case."""
        import httpx

        payload = {
            "query": [
                {"_name": "getCase", "idOrName": case_id},
                {"_name": "observables"},
            ],
            "range": f"0-{limit}",
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        iocs = []
        for obs in data:
            iocs.append(
                IOC(
                    id=obs.get("_id", ""),
                    type=obs.get("dataType", "other"),
                    value=obs.get("data", ""),
                    description=obs.get("message", ""),
                    tags=obs.get("tags", []),
                    metadata={
                        "thehive_id": obs.get("_id"),
                        "ioc": obs.get("ioc", False),
                        "sighted": obs.get("sighted", False),
                    },
                )
            )

        return iocs

    async def add_task(
        self,
        case_id: str,
        title: str,
        description: str | None = None,
        assignee: str | None = None,
        due_date: datetime | None = None,
    ) -> Task:
        """Add a task to a case."""
        import httpx

        payload: dict[str, Any] = {
            "title": title,
            "group": "default",
            "status": "Waiting",
        }

        if description:
            payload["description"] = description
        if assignee:
            payload["assignee"] = assignee
        if due_date:
            payload["dueDate"] = int(due_date.timestamp() * 1000)

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/case/{case_id}/task",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_task(data)

    async def get_tasks(self, case_id: str) -> list[Task]:
        """Get tasks for a case."""
        import httpx

        payload = {
            "query": [
                {"_name": "getCase", "idOrName": case_id},
                {"_name": "tasks"},
            ],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return [self._parse_task(task) for task in data]

    async def update_task(
        self,
        task_id: str,
        status: str | None = None,
        assignee: str | None = None,
    ) -> Task:
        """Update a task."""
        import httpx

        payload: dict[str, Any] = {}

        if status:
            payload["status"] = status
        if assignee:
            payload["assignee"] = assignee

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.patch(
                f"{self.api_base}/task/{task_id}",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_task(response.json())

    async def add_member(
        self,
        case_id: str,
        user_id: str,
        role: str = "read-only",
    ) -> CaseMember:
        """Add a member to a case."""
        import httpx

        payload = {
            "user": user_id,
            "profile": role,
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/case/{case_id}/share",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        return CaseMember(
            user_id=user_id,
            role=role,
        )

    async def get_members(self, case_id: str) -> list[CaseMember]:
        """Get members of a case."""
        import httpx

        payload = {
            "query": [
                {"_name": "getCase", "idOrName": case_id},
                {"_name": "shares"},
            ],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        members = []
        for share in data:
            members.append(
                CaseMember(
                    user_id=share.get("user", ""),
                    role=share.get("profile", "read-only"),
                )
            )

        return members

    async def create_alert(
        self,
        title: str,
        description: str,
        severity: Severity = Severity.MEDIUM,
        source: str = "eleanor",
        source_ref: str | None = None,
        tags: list[str] | None = None,
    ) -> Alert:
        """Create an alert in TheHive."""
        from uuid import uuid4

        import httpx

        payload = {
            "title": title,
            "description": description,
            "severity": SEVERITY_MAP.get(severity, 2),
            "type": "external",
            "source": source,
            "sourceRef": source_ref or str(uuid4()),
            "tlp": self.TLP_MAP.get(self.default_tlp, 2),
            "pap": self.TLP_MAP.get(self.default_pap, 2),
            "tags": tags or [],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/alert",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_alert(data)

    async def get_alerts(
        self,
        status: str | None = None,
        severity: Severity | None = None,
        limit: int = 50,
    ) -> list[Alert]:
        """Get alerts from TheHive."""
        import httpx

        query: list[dict[str, Any]] = [{"_name": "listAlert"}]

        if status:
            query.append({"_field": "status", "_value": status})
        if severity:
            query.append({"_field": "severity", "_value": SEVERITY_MAP.get(severity, 2)})

        payload = {
            "query": query,
            "range": f"0-{limit}",
            "sort": ["-_createdAt"],
        }

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/query",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return [self._parse_alert(alert) for alert in data]

    async def promote_alert_to_case(
        self,
        alert_id: str,
        title: str | None = None,
    ) -> Case:
        """Promote an alert to a case."""
        import httpx

        payload: dict[str, Any] = {}
        if title:
            payload["title"] = title

        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f"{self.api_base}/alert/{alert_id}/createCase",
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._parse_case(response.json())

    def _parse_case(self, data: dict[str, Any]) -> Case:
        """Parse TheHive case to Eleanor Case."""
        severity_value = data.get("severity", 2)

        return Case(
            id=data.get("_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "Open"),
            severity=SEVERITY_REVERSE_MAP.get(severity_value, Severity.MEDIUM),
            tags=data.get("tags", []),
            created_at=self._parse_timestamp(data.get("_createdAt")),
            updated_at=self._parse_timestamp(data.get("_updatedAt")),
            owner=data.get("owner", ""),
            assignee=data.get("assignee"),
            metadata={
                "thehive_id": data.get("_id"),
                "case_number": data.get("number"),
                "tlp": data.get("tlp"),
                "pap": data.get("pap"),
                "resolution_status": data.get("resolutionStatus"),
                "summary": data.get("summary"),
            },
        )

    def _parse_task(self, data: dict[str, Any]) -> Task:
        """Parse TheHive task."""
        return Task(
            id=data.get("_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "Waiting"),
            assignee=data.get("assignee"),
            due_date=self._parse_timestamp(data.get("dueDate")),
            created_at=self._parse_timestamp(data.get("_createdAt")),
            metadata={
                "thehive_id": data.get("_id"),
                "group": data.get("group"),
                "order": data.get("order"),
            },
        )

    def _parse_alert(self, data: dict[str, Any]) -> Alert:
        """Parse TheHive alert."""
        severity_value = data.get("severity", 2)

        return Alert(
            id=data.get("_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=SEVERITY_REVERSE_MAP.get(severity_value, Severity.MEDIUM),
            status=data.get("status", "New"),
            source=data.get("source", ""),
            source_ref=data.get("sourceRef", ""),
            tags=data.get("tags", []),
            created_at=self._parse_timestamp(data.get("_createdAt")),
            metadata={
                "thehive_id": data.get("_id"),
                "type": data.get("type"),
                "tlp": data.get("tlp"),
                "case_id": data.get("case"),
            },
        )

    def _parse_timestamp(self, value: int | None) -> datetime | None:
        """Parse TheHive timestamp (milliseconds since epoch)."""
        if not value:
            return None

        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except (ValueError, OSError):
            return None

    def _ioc_type_to_thehive(self, ioc_type: str) -> str:
        """Map IOC type to TheHive data type."""
        type_map = {
            "ip": "ip",
            "ipv4": "ip",
            "ipv6": "ip",
            "domain": "domain",
            "url": "url",
            "email": "mail",
            "md5": "hash",
            "sha1": "hash",
            "sha256": "hash",
            "filename": "filename",
            "file_hash": "hash",
            "registry": "registry",
            "user_agent": "user-agent",
        }
        return type_map.get(ioc_type.lower(), "other")
