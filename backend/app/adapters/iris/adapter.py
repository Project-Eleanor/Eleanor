"""IRIS adapter implementation.

Provides integration with DFIR-IRIS for:
- Case management (create, update, close)
- Asset tracking
- IOC management
- Investigation notes
- Case synchronization with Eleanor

IRIS API: https://docs.dfir-iris.org/operations/api/
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    CaseManagementAdapter,
    ExternalAsset,
    ExternalCase,
    ExternalIOC,
    ExternalNote,
    IndicatorType,
    Severity,
)
from app.adapters.iris.schemas import (
    IRISAsset,
    IRISCase,
    IRISIOCEntry,
    IRISNote,
)

logger = logging.getLogger(__name__)


# IRIS IOC type mapping
IOC_TYPE_MAP = {
    IndicatorType.IPV4: "ip",
    IndicatorType.IPV6: "ipv6",
    IndicatorType.DOMAIN: "domain",
    IndicatorType.URL: "url",
    IndicatorType.EMAIL: "email",
    IndicatorType.FILE_HASH_MD5: "md5",
    IndicatorType.FILE_HASH_SHA1: "sha1",
    IndicatorType.FILE_HASH_SHA256: "sha256",
    IndicatorType.FILE_NAME: "filename",
    IndicatorType.REGISTRY_KEY: "registry",
    IndicatorType.USER_AGENT: "user-agent",
}

# IRIS severity mapping
SEVERITY_MAP = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFORMATIONAL: 1,
}


class IRISAdapter(CaseManagementAdapter):
    """Adapter for DFIR-IRIS case management system."""

    name = "iris"
    description = "DFIR-IRIS case management"

    def __init__(self, config: AdapterConfig):
        """Initialize IRIS adapter."""
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._version: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url.rstrip("/"),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make API request to IRIS."""
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        result = response.json()

        # IRIS wraps responses in a data envelope
        # For endpoints like /api/ping, data is an empty list
        if isinstance(result, dict):
            if "data" in result and isinstance(result["data"], dict):
                return result["data"]
            return result  # Return full response for ping, etc.
        return result

    async def health_check(self) -> AdapterHealth:
        """Check IRIS connectivity."""
        try:
            # Get raw JSON response for ping (includes status and message)
            client = await self._get_client()
            response = await client.get("/api/ping")
            response.raise_for_status()
            result = response.json()

            # Ping returns {"status": "success", "message": "pong", "data": []}
            if result.get("status") == "success":
                self._status = AdapterStatus.CONNECTED
                # Try to get version from a separate endpoint
                try:
                    ver_response = await client.get("/api/versions")
                    ver_result = ver_response.json()
                    ver_data = ver_result.get("data", {})
                    self._version = ver_data.get("iris_current", ver_data.get("iris_version", "unknown"))
                except Exception:
                    self._version = "connected"

                return AdapterHealth(
                    adapter_name=self.name,
                    status=AdapterStatus.CONNECTED,
                    version=self._version,
                    message="Connected to IRIS",
                )
            else:
                raise ValueError(f"Unexpected response: {result}")
        except httpx.HTTPError as e:
            logger.error("IRIS health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"HTTP error: {e}",
            )
        except Exception as e:
            logger.error("IRIS health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized)."""
        return {
            "url": self.config.url,
            "verify_ssl": self.config.verify_ssl,
            "has_api_key": bool(self.config.api_key),
        }

    def _iris_case_to_external(self, iris_case: IRISCase) -> ExternalCase:
        """Convert IRIS case to ExternalCase."""
        # Map IRIS severity to our Severity enum
        severity_reverse = {v: k for k, v in SEVERITY_MAP.items()}
        severity = severity_reverse.get(iris_case.severity_id, Severity.MEDIUM)

        return ExternalCase(
            external_id=str(iris_case.case_id),
            title=iris_case.case_name,
            description=iris_case.case_description,
            status=iris_case.status_name,
            severity=severity,
            created_at=iris_case.open_date,
            closed_at=iris_case.close_date,
            assignee=iris_case.owner,
            tags=[iris_case.classification_name] if iris_case.classification_name else [],
            metadata={
                "case_uuid": iris_case.case_uuid,
                "case_soc_id": iris_case.case_soc_id,
                "client_name": iris_case.client_name,
                "status_id": iris_case.status_id,
                "severity_id": iris_case.severity_id,
            },
        )

    # =========================================================================
    # Case Management
    # =========================================================================

    async def list_cases(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[ExternalCase]:
        """List cases from IRIS."""
        params = {}
        if status:
            # IRIS uses status IDs
            status_id_map = {
                "open": 1,
                "closed": 2,
                "investigation": 3,
                "containment": 4,
            }
            if status.lower() in status_id_map:
                params["status_id"] = status_id_map[status.lower()]

        result = await self._request("GET", "/api/v2/cases", params=params)
        cases_data = result if isinstance(result, list) else result.get("cases", [])

        cases = []
        for case_data in cases_data[offset : offset + limit]:
            iris_case = IRISCase(**case_data)
            cases.append(self._iris_case_to_external(iris_case))

        return cases

    async def get_case(self, external_id: str) -> Optional[ExternalCase]:
        """Get a specific case by IRIS case ID."""
        try:
            result = await self._request("GET", f"/api/v2/cases/{external_id}")
            iris_case = IRISCase(**result)
            return self._iris_case_to_external(iris_case)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_case(
        self,
        title: str,
        description: Optional[str] = None,
        severity: Optional[Severity] = None,
        tags: Optional[list[str]] = None,
    ) -> ExternalCase:
        """Create a new case in IRIS."""
        payload = {
            "case_name": title,
            "case_description": description or "",
            "case_customer": 1,  # Default customer
            "case_soc_id": "",
        }

        if severity:
            payload["case_severity_id"] = SEVERITY_MAP.get(severity, 3)

        result = await self._request("POST", "/api/v2/cases", json=payload)
        iris_case = IRISCase(**result)
        return self._iris_case_to_external(iris_case)

    async def update_case(
        self,
        external_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[Severity] = None,
    ) -> ExternalCase:
        """Update an existing case."""
        payload = {}
        if title:
            payload["case_name"] = title
        if description:
            payload["case_description"] = description
        if status:
            status_map = {"open": 1, "closed": 2, "investigation": 3, "containment": 4}
            if status.lower() in status_map:
                payload["status_id"] = status_map[status.lower()]
        if severity:
            payload["severity_id"] = SEVERITY_MAP.get(severity, 3)

        result = await self._request(
            "PUT",
            f"/api/v2/cases/{external_id}",
            json=payload,
        )
        iris_case = IRISCase(**result)
        return self._iris_case_to_external(iris_case)

    async def close_case(
        self,
        external_id: str,
        resolution: Optional[str] = None,
    ) -> ExternalCase:
        """Close a case."""
        payload = {
            "status_id": 2,  # Closed status
        }
        if resolution:
            payload["case_description"] = resolution

        result = await self._request(
            "PUT",
            f"/api/v2/cases/{external_id}",
            json=payload,
        )
        iris_case = IRISCase(**result)
        return self._iris_case_to_external(iris_case)

    async def sync_case(
        self,
        eleanor_id: UUID,
        external_id: str,
    ) -> bool:
        """Sync Eleanor case with IRIS case.

        This stores Eleanor's case ID in IRIS custom attributes.
        """
        try:
            await self._request(
                "PUT",
                f"/api/v2/cases/{external_id}",
                json={
                    "custom_attributes": {
                        "eleanor_case_id": str(eleanor_id),
                    }
                },
            )
            return True
        except Exception as e:
            logger.error("Failed to sync case %s: %s", external_id, e)
            return False

    # =========================================================================
    # Asset Management
    # =========================================================================

    async def list_assets(self, case_id: str) -> list[ExternalAsset]:
        """List assets for a case."""
        result = await self._request(
            "GET",
            f"/api/v2/cases/{case_id}/assets",
        )
        assets_data = result if isinstance(result, list) else result.get("assets", [])

        assets = []
        for asset_data in assets_data:
            iris_asset = IRISAsset(**asset_data)
            assets.append(
                ExternalAsset(
                    external_id=str(iris_asset.asset_id),
                    name=iris_asset.asset_name,
                    asset_type=iris_asset.asset_type_name.lower(),
                    ip_address=iris_asset.asset_ip or None,
                    hostname=iris_asset.asset_domain or None,
                    description=iris_asset.asset_description,
                    compromised=iris_asset.asset_compromise_status_id > 0,
                    metadata={
                        "asset_uuid": iris_asset.asset_uuid,
                        "asset_type_id": iris_asset.asset_type_id,
                    },
                )
            )

        return assets

    async def add_asset(
        self,
        case_id: str,
        asset: ExternalAsset,
    ) -> ExternalAsset:
        """Add an asset to a case."""
        # Map asset type to IRIS type ID
        type_map = {
            "host": 1,
            "windows": 1,
            "linux": 2,
            "account": 3,
            "network": 4,
            "other": 9,
        }
        type_id = type_map.get(asset.asset_type.lower(), 9)

        payload = {
            "asset_name": asset.name,
            "asset_description": asset.description or "",
            "asset_type_id": type_id,
            "asset_ip": asset.ip_address or "",
            "asset_domain": asset.hostname or "",
            "analysis_status_id": 1,
        }

        result = await self._request(
            "POST",
            f"/api/v2/cases/{case_id}/assets",
            json=payload,
        )
        iris_asset = IRISAsset(**result)

        return ExternalAsset(
            external_id=str(iris_asset.asset_id),
            name=iris_asset.asset_name,
            asset_type=iris_asset.asset_type_name.lower(),
            ip_address=iris_asset.asset_ip or None,
            hostname=iris_asset.asset_domain or None,
            description=iris_asset.asset_description,
        )

    # =========================================================================
    # IOC Management
    # =========================================================================

    async def list_iocs(self, case_id: str) -> list[ExternalIOC]:
        """List IOCs for a case."""
        result = await self._request(
            "GET",
            f"/api/v2/cases/{case_id}/iocs",
        )
        iocs_data = result if isinstance(result, list) else result.get("iocs", [])

        iocs = []
        for ioc_data in iocs_data:
            iris_ioc = IRISIOCEntry(**ioc_data)

            # Reverse map IOC type
            type_reverse = {v: k for k, v in IOC_TYPE_MAP.items()}
            ioc_type = type_reverse.get(
                iris_ioc.ioc_type.lower(),
                IndicatorType.FILE_HASH_SHA256,
            )

            iocs.append(
                ExternalIOC(
                    external_id=str(iris_ioc.ioc_id),
                    value=iris_ioc.ioc_value,
                    ioc_type=ioc_type,
                    description=iris_ioc.ioc_description,
                    tlp=iris_ioc.tlp,
                    tags=iris_ioc.ioc_tags.split(",") if iris_ioc.ioc_tags else [],
                    metadata={"ioc_uuid": iris_ioc.ioc_uuid},
                )
            )

        return iocs

    async def add_ioc(
        self,
        case_id: str,
        ioc: ExternalIOC,
    ) -> ExternalIOC:
        """Add an IOC to a case."""
        # Map TLP to IRIS TLP ID
        tlp_map = {"red": 1, "amber": 2, "green": 3, "white": 4}
        tlp_id = tlp_map.get(ioc.tlp.lower(), 2)

        # Map indicator type to IRIS IOC type ID
        type_name = IOC_TYPE_MAP.get(ioc.ioc_type, "other")

        payload = {
            "ioc_value": ioc.value,
            "ioc_description": ioc.description or "",
            "ioc_type_id": 1,  # Will be overridden by type name lookup
            "ioc_tlp_id": tlp_id,
            "ioc_tags": ",".join(ioc.tags) if ioc.tags else "",
        }

        # IRIS needs type name for auto-detection
        payload["ioc_type"] = type_name

        result = await self._request(
            "POST",
            f"/api/v2/cases/{case_id}/iocs",
            json=payload,
        )
        iris_ioc = IRISIOCEntry(**result)

        return ExternalIOC(
            external_id=str(iris_ioc.ioc_id),
            value=iris_ioc.ioc_value,
            ioc_type=ioc.ioc_type,
            description=iris_ioc.ioc_description,
            tlp=iris_ioc.tlp,
        )

    # =========================================================================
    # Notes
    # =========================================================================

    async def list_notes(self, case_id: str) -> list[ExternalNote]:
        """List notes for a case."""
        result = await self._request(
            "GET",
            f"/api/v2/cases/{case_id}/notes",
        )
        notes_data = result if isinstance(result, list) else result.get("notes", [])

        notes = []
        for note_data in notes_data:
            iris_note = IRISNote(**note_data)
            notes.append(
                ExternalNote(
                    external_id=str(iris_note.note_id),
                    title=iris_note.note_title,
                    content=iris_note.note_content,
                    created_at=iris_note.note_creationdate,
                    metadata={
                        "note_uuid": iris_note.note_uuid,
                        "group_title": iris_note.group_title,
                    },
                )
            )

        return notes

    async def add_note(
        self,
        case_id: str,
        note: ExternalNote,
    ) -> ExternalNote:
        """Add a note to a case."""
        payload = {
            "note_title": note.title,
            "note_content": note.content,
            "group_id": 1,  # Default group
        }

        result = await self._request(
            "POST",
            f"/api/v2/cases/{case_id}/notes",
            json=payload,
        )
        iris_note = IRISNote(**result)

        return ExternalNote(
            external_id=str(iris_note.note_id),
            title=iris_note.note_title,
            content=iris_note.note_content,
            created_at=iris_note.note_creationdate,
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
