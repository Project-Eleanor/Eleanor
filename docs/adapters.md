# Eleanor Adapter Architecture

Eleanor uses an adapter-based architecture to integrate with external DFIR tools. This document explains how adapters work and how to extend them.

## Overview

Adapters provide consistent interfaces for different categories of tools:

| Adapter Type | Purpose | Example Implementations |
|--------------|---------|------------------------|
| `CaseManagementAdapter` | Incident case tracking | IRIS, TheHive |
| `CollectionAdapter` | Endpoint collection & response | Velociraptor, OSQuery |
| `ThreatIntelAdapter` | IOC enrichment | OpenCTI, MISP |
| `SOARAdapter` | Workflow automation | Shuffle, Cortex XSOAR |
| `TimelineAdapter` | Timeline analysis | Timesketch |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Eleanor Backend                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Adapter Registry                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │  IRIS   │ │Velocir- │ │OpenCTI  │ │ Shuffle │   │   │
│  │  │ Adapter │ │  aptor  │ │ Adapter │ │ Adapter │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │   │
│  └───────┼──────────┼──────────┼──────────┼──────────┘   │
│          │          │          │          │               │
└──────────┼──────────┼──────────┼──────────┼───────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
     │  IRIS   │ │Velocir- │ │ OpenCTI │ │ Shuffle │
     │  API    │ │  aptor  │ │   API   │ │   API   │
     └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## Base Classes

All adapters inherit from base classes in `backend/app/adapters/base.py`:

### BaseAdapter

```python
class BaseAdapter(ABC):
    """Base class for all adapters."""

    name: str = "base"
    description: str = "Base adapter"

    def __init__(self, config: AdapterConfig):
        self.config = config
        self._status = AdapterStatus.DISCONNECTED

    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check connectivity and return health status."""
        ...

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Return sanitized configuration (no secrets)."""
        ...

    async def connect(self) -> bool:
        """Establish connection to external service."""
        health = await self.health_check()
        self._status = health.status
        return health.status == AdapterStatus.CONNECTED

    async def disconnect(self) -> None:
        """Clean up connection resources."""
        self._status = AdapterStatus.DISCONNECTED
```

### AdapterConfig

```python
@dataclass
class AdapterConfig:
    """Configuration for an adapter."""

    enabled: bool = False
    url: str = ""
    api_key: str = ""
    verify_ssl: bool = True
    timeout: int = 30
    extra: dict[str, Any] = field(default_factory=dict)
```

## Adapter Types

### CaseManagementAdapter

For case/incident management systems:

```python
class CaseManagementAdapter(BaseAdapter):
    """Abstract adapter for case management systems."""

    # Case CRUD
    async def list_cases(...) -> list[ExternalCase]: ...
    async def get_case(external_id: str) -> ExternalCase: ...
    async def create_case(...) -> ExternalCase: ...
    async def update_case(...) -> ExternalCase: ...
    async def close_case(...) -> ExternalCase: ...
    async def sync_case(...) -> bool: ...

    # Assets
    async def list_assets(case_id: str) -> list[ExternalAsset]: ...
    async def add_asset(...) -> ExternalAsset: ...

    # IOCs
    async def list_iocs(case_id: str) -> list[ExternalIOC]: ...
    async def add_ioc(...) -> ExternalIOC: ...

    # Notes
    async def list_notes(case_id: str) -> list[ExternalNote]: ...
    async def add_note(...) -> ExternalNote: ...
```

### CollectionAdapter

For endpoint collection and response tools:

```python
class CollectionAdapter(BaseAdapter):
    """Abstract adapter for endpoint collection tools."""

    # Endpoints
    async def list_endpoints(...) -> list[Endpoint]: ...
    async def get_endpoint(client_id: str) -> Endpoint: ...
    async def search_endpoints(query: str) -> list[Endpoint]: ...

    # Artifact Collection
    async def list_artifacts(...) -> list[CollectionArtifact]: ...
    async def collect_artifact(...) -> CollectionJob: ...
    async def get_collection_status(job_id: str) -> CollectionJob: ...
    async def get_collection_results(...) -> list[dict]: ...

    # Hunts
    async def list_hunts(...) -> list[Hunt]: ...
    async def create_hunt(...) -> Hunt: ...
    async def start_hunt(hunt_id: str) -> Hunt: ...
    async def stop_hunt(hunt_id: str) -> Hunt: ...
    async def get_hunt_results(...) -> list[dict]: ...

    # Response Actions
    async def isolate_host(client_id: str) -> bool: ...
    async def unisolate_host(client_id: str) -> bool: ...
    async def quarantine_file(...) -> bool: ...
    async def kill_process(...) -> bool: ...
```

### ThreatIntelAdapter

For threat intelligence platforms:

```python
class ThreatIntelAdapter(BaseAdapter):
    """Abstract adapter for threat intelligence platforms."""

    # Enrichment
    async def enrich_indicator(...) -> EnrichmentResult: ...
    async def bulk_enrich(...) -> list[EnrichmentResult]: ...

    # Threat Actors
    async def get_threat_actor(name: str) -> ThreatActor: ...
    async def search_threat_actors(...) -> list[ThreatActor]: ...

    # Campaigns
    async def get_campaign(name: str) -> Campaign: ...
    async def search_campaigns(...) -> list[Campaign]: ...

    # Related Indicators
    async def get_related_indicators(...) -> list[ThreatIndicator]: ...

    # Submit
    async def submit_indicator(...) -> ThreatIndicator: ...
```

### SOARAdapter

For workflow automation platforms:

```python
class SOARAdapter(BaseAdapter):
    """Abstract adapter for SOAR platforms."""

    # Workflows
    async def list_workflows(...) -> list[Workflow]: ...
    async def get_workflow(workflow_id: str) -> Workflow: ...
    async def trigger_workflow(...) -> WorkflowExecution: ...
    async def get_execution_status(...) -> WorkflowExecution: ...
    async def list_executions(...) -> list[WorkflowExecution]: ...
    async def cancel_execution(execution_id: str) -> bool: ...

    # Approvals
    async def list_pending_approvals() -> list[ApprovalRequest]: ...
    async def approve_request(...) -> bool: ...
    async def deny_request(...) -> bool: ...

    # Shortcuts
    async def isolate_host_workflow(...) -> WorkflowExecution: ...
    async def block_ip_workflow(...) -> WorkflowExecution: ...
    async def disable_user_workflow(...) -> WorkflowExecution: ...
```

### TimelineAdapter

For timeline analysis tools:

```python
class TimelineAdapter(BaseAdapter):
    """Abstract adapter for timeline analysis tools."""

    # Sketches
    async def list_sketches(...) -> list[Sketch]: ...
    async def get_sketch(sketch_id: str) -> Sketch: ...
    async def create_sketch(...) -> Sketch: ...
    async def delete_sketch(sketch_id: str) -> bool: ...

    # Timelines
    async def list_timelines(sketch_id: str) -> list[Timeline]: ...
    async def upload_timeline(...) -> Timeline: ...
    async def delete_timeline(...) -> bool: ...

    # Events
    async def search_events(...) -> list[TimelineEvent]: ...
    async def get_event(...) -> TimelineEvent: ...

    # Annotations
    async def tag_event(...) -> TimelineEvent: ...
    async def star_event(...) -> TimelineEvent: ...
    async def add_comment(...) -> TimelineEvent: ...

    # Saved Views
    async def list_saved_views(sketch_id: str) -> list[SavedView]: ...
    async def create_saved_view(...) -> SavedView: ...
    async def delete_saved_view(...) -> bool: ...
```

## Adapter Registry

The registry manages adapter lifecycle:

```python
# backend/app/adapters/registry.py

class AdapterRegistry:
    """Global registry for adapter instances."""

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}

    async def configure_from_settings(self, settings: Settings):
        """Configure adapters from application settings."""
        if settings.velociraptor_enabled:
            self.register("velociraptor", VelociraptorAdapter(
                AdapterConfig(
                    enabled=True,
                    url=settings.velociraptor_url,
                    extra={
                        "ca_cert": settings.velociraptor_ca_cert,
                        "client_cert": settings.velociraptor_client_cert,
                        "client_key": settings.velociraptor_client_key,
                    }
                )
            ))
        # ... other adapters

    async def connect_all(self):
        """Connect all registered adapters."""
        for adapter in self._adapters.values():
            await adapter.connect()

    async def disconnect_all(self):
        """Disconnect all adapters."""
        for adapter in self._adapters.values():
            await adapter.disconnect()

    def get(self, name: str) -> Optional[BaseAdapter]:
        """Get adapter by name."""
        return self._adapters.get(name)

    def get_collection(self) -> Optional[CollectionAdapter]:
        """Get the collection adapter."""
        return self._adapters.get("velociraptor")

    def get_case_management(self) -> Optional[CaseManagementAdapter]:
        """Get the case management adapter."""
        return self._adapters.get("iris")

    # ... other typed getters


# Global registry instance
_registry: Optional[AdapterRegistry] = None

def get_registry() -> AdapterRegistry:
    """Get the global adapter registry."""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry
```

## Creating a New Adapter

### 1. Create Adapter Directory

```
backend/app/adapters/myplatform/
├── __init__.py
├── adapter.py
└── schemas.py
```

### 2. Define Schemas

```python
# schemas.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class MyPlatformCase:
    """Case from MyPlatform API."""
    id: str
    name: str
    status: str
    created_at: Optional[datetime] = None
    # ... map to API response
```

### 3. Implement Adapter

```python
# adapter.py
import httpx
from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    CaseManagementAdapter,
    ExternalCase,
)

class MyPlatformAdapter(CaseManagementAdapter):
    """Adapter for MyPlatform case management."""

    name = "myplatform"
    description = "MyPlatform case management integration"

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
        return self._client

    async def health_check(self) -> AdapterHealth:
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/health")
            response.raise_for_status()

            self._status = AdapterStatus.CONNECTED
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                version=response.json().get("version"),
                message="Connected to MyPlatform",
            )
        except Exception as e:
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        return {
            "url": self.config.url,
            "has_api_key": bool(self.config.api_key),
        }

    async def list_cases(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[ExternalCase]:
        client = await self._get_client()
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await client.get("/api/v1/cases", params=params)
        response.raise_for_status()

        cases = []
        for item in response.json()["data"]:
            cases.append(ExternalCase(
                external_id=item["id"],
                title=item["name"],
                status=item["status"],
                # ... map fields
            ))
        return cases

    # Implement other required methods...

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
```

### 4. Register in __init__.py

```python
# backend/app/adapters/__init__.py

from app.adapters.myplatform.adapter import MyPlatformAdapter

__all__ = [
    # ... existing exports
    "MyPlatformAdapter",
]
```

### 5. Add Configuration

```python
# backend/app/config.py

class Settings(BaseSettings):
    # ... existing settings

    # MyPlatform
    myplatform_enabled: bool = False
    myplatform_url: str = ""
    myplatform_api_key: str = ""
```

### 6. Register in Registry

```python
# backend/app/adapters/registry.py

if settings.myplatform_enabled:
    self.register("myplatform", MyPlatformAdapter(
        AdapterConfig(
            enabled=True,
            url=settings.myplatform_url,
            api_key=settings.myplatform_api_key,
        )
    ))
```

## Testing Adapters

### Unit Tests

```python
# tests/adapters/test_myplatform.py

import pytest
from unittest.mock import AsyncMock, patch

from app.adapters.myplatform.adapter import MyPlatformAdapter
from app.adapters.base import AdapterConfig, AdapterStatus

@pytest.fixture
def adapter():
    return MyPlatformAdapter(AdapterConfig(
        enabled=True,
        url="http://localhost:8080",
        api_key="test-key",
    ))

@pytest.mark.asyncio
async def test_health_check_success(adapter):
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.get = AsyncMock(return_value=Mock(
            status_code=200,
            json=lambda: {"version": "1.0.0"}
        ))

        health = await adapter.health_check()

        assert health.status == AdapterStatus.CONNECTED
        assert health.version == "1.0.0"

@pytest.mark.asyncio
async def test_list_cases(adapter):
    # ... test implementation
```

### Integration Tests

```python
# tests/integration/test_myplatform_integration.py

import pytest
from app.adapters.myplatform.adapter import MyPlatformAdapter

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_connection():
    """Test against real MyPlatform instance."""
    adapter = MyPlatformAdapter(AdapterConfig(
        enabled=True,
        url=os.environ["MYPLATFORM_URL"],
        api_key=os.environ["MYPLATFORM_API_KEY"],
    ))

    health = await adapter.health_check()
    assert health.status == AdapterStatus.CONNECTED

    cases = await adapter.list_cases(limit=10)
    assert isinstance(cases, list)
```

## Best Practices

1. **Error Handling**: Always catch and log exceptions, return appropriate AdapterHealth status
2. **Connection Pooling**: Reuse HTTP clients, implement connection pooling
3. **Timeouts**: Respect configured timeouts, fail fast
4. **Rate Limiting**: Implement rate limiting if required by external API
5. **Caching**: Cache frequently accessed data (e.g., artifact definitions)
6. **Logging**: Log all API calls and errors for debugging
7. **Secrets**: Never log or expose API keys/credentials
8. **Testing**: Write comprehensive unit and integration tests
